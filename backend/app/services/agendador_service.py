# -*- coding: utf-8 -*-
"""
Regras de negócio da agenda: quais dias o salão atende, quais horários
estão livres e prevenção de conflitos.

Três ideias principais:

1. DIA ATENDIDO? (`janela_do_dia`)
   Combina, nesta ordem: exceção marcada pelo administrador para a data
   (DiaAgenda) -> modo "só dias marcados" -> semana-padrão do salão ->
   horário próprio do profissional.

2. O QUE BLOQUEIA UM HORÁRIO? (`STATUS_QUE_BLOQUEIAM`)
   Somente agendamentos CONFIRMADOS (ou já concluídos). Solicitações
   PENDENTES não bloqueiam: o cliente só tem o horário garantido depois
   que o administrador aceita.

3. SEM CONFLITO NA HORA DE ACEITAR
   `existe_conflito()` é chamada de novo quando o administrador aceita uma
   solicitação, evitando duas confirmações no mesmo horário.

Este módulo só faz consultas (SELECT); quem grava é a camada de rotas.
"""

import calendar
from datetime import datetime, timedelta, date, time as time_type

from flask import current_app

from app.extensions import db
from app.models.agendamento import Agendamento, StatusAgendamento
from app.models.profissional import Profissional, Indisponibilidade
from app.models.salao import DiaAgenda

# Agenda "fatiada" em intervalos de 15 minutos para sugerir horários.
GRANULARIDADE_MINUTOS = 15

# Só estes status ocupam a agenda. PENDENTE/RECUSADO/CANCELADO não.
STATUS_QUE_BLOQUEIAM = (StatusAgendamento.CONFIRMADO, StatusAgendamento.CONCLUIDO)


# ---------------------------------------------------------------------------
# Conflitos
# ---------------------------------------------------------------------------

def existe_conflito(profissional_id: str, inicio: datetime, fim: datetime,
                    agendamento_id_excluir: str = None) -> bool:
    """
    True se o profissional já tem um agendamento CONFIRMADO/CONCLUÍDO cujo
    intervalo [inicio, fim) se sobrepõe ao informado.
    Duas faixas se sobrepõem quando: a_inicio < b_fim E a_fim > b_inicio.
    """
    query = Agendamento.query.filter(
        Agendamento.profissional_id == profissional_id,
        Agendamento.status.in_(STATUS_QUE_BLOQUEIAM),
        Agendamento.inicio < fim,
        Agendamento.fim > inicio,
    )
    if agendamento_id_excluir:
        query = query.filter(Agendamento.id != agendamento_id_excluir)
    return db.session.query(query.exists()).scalar()


def _esta_dentro_de_indisponibilidade(profissional_id: str, inicio: datetime, fim: datetime) -> bool:
    conflito = Indisponibilidade.query.filter(
        Indisponibilidade.profissional_id == profissional_id,
        Indisponibilidade.inicio < fim,
        Indisponibilidade.fim > inicio,
    ).first()
    return conflito is not None


def _intervalos_ocupados(profissional_id: str, dia: date) -> list:
    """Busca de uma vez só tudo que ocupa o profissional no dia (evita 1 consulta por horário)."""
    inicio_dia = datetime.combine(dia, time_type.min)
    fim_dia = inicio_dia + timedelta(days=1)

    agendados = Agendamento.query.filter(
        Agendamento.profissional_id == profissional_id,
        Agendamento.status.in_(STATUS_QUE_BLOQUEIAM),
        Agendamento.inicio < fim_dia,
        Agendamento.fim > inicio_dia,
    ).all()
    bloqueios = Indisponibilidade.query.filter(
        Indisponibilidade.profissional_id == profissional_id,
        Indisponibilidade.inicio < fim_dia,
        Indisponibilidade.fim > inicio_dia,
    ).all()
    return [(a.inicio, a.fim) for a in agendados] + [(b.inicio, b.fim) for b in bloqueios]


# ---------------------------------------------------------------------------
# Calendário: quais dias o salão atende
# ---------------------------------------------------------------------------

def janela_do_dia(salao, dia: date, profissional=None, excecao: DiaAgenda = None):
    """
    Devolve (hora_inicio, hora_fim) em que há atendimento no dia, ou
    (None, None) se o salão/profissional não atende nele.
    `excecao` permite passar a DiaAgenda já carregada (usado no calendário
    do mês, para não consultar o banco dia a dia).
    """
    if excecao is None:
        excecao = DiaAgenda.query.filter_by(salao_id=salao.id, data=dia).first()

    if excecao is not None:
        if not excecao.aberto:
            return None, None
        inicio = excecao.hora_inicio or salao.horario_abertura
        fim = excecao.hora_fim or salao.horario_fechamento
    elif salao.somente_dias_marcados:
        return None, None
    elif dia.weekday() not in (salao.dias_funcionamento or []):
        return None, None
    else:
        inicio, fim = salao.horario_abertura, salao.horario_fechamento

    if profissional is not None:
        # O horário do profissional só pode ficar DENTRO do horário do dia.
        if profissional.horario_inicio:
            inicio = max(inicio, profissional.horario_inicio)
        if profissional.horario_fim:
            fim = min(fim, profissional.horario_fim)

    if inicio >= fim:
        return None, None
    return inicio, fim


def calendario_do_mes(salao, ano: int, mes: int) -> list:
    """
    Situação de cada dia do mês, para desenhar o calendário (cliente e
    administrador usam o mesmo retorno):

      status:   "disponivel" | "fechado" | "passado"
      excecao:  "aberto" | "fechado" | None  -> o que o administrador marcou
    """
    primeiro = date(ano, mes, 1)
    ultimo = date(ano, mes, calendar.monthrange(ano, mes)[1])
    excecoes = {
        e.data: e
        for e in DiaAgenda.query.filter(
            DiaAgenda.salao_id == salao.id, DiaAgenda.data >= primeiro, DiaAgenda.data <= ultimo
        ).all()
    }

    hoje = date.today()
    limite = hoje + timedelta(days=current_app.config.get("AGENDAMENTO_ANTECEDENCIA_MAXIMA_DIAS", 60))

    dias = []
    dia = primeiro
    while dia <= ultimo:
        excecao = excecoes.get(dia)
        inicio, fim = janela_do_dia(salao, dia, excecao=excecao)
        if dia < hoje:
            status = "passado"
        elif dia > limite or inicio is None:
            status = "fechado"
        else:
            status = "disponivel"

        dias.append({
            "data": dia.isoformat(),
            "status": status,
            "excecao": None if excecao is None else ("aberto" if excecao.aberto else "fechado"),
            "hora_inicio": inicio.strftime("%H:%M") if inicio else None,
            "hora_fim": fim.strftime("%H:%M") if fim else None,
            "motivo": excecao.motivo if excecao else None,
        })
        dia += timedelta(days=1)
    return dias


# ---------------------------------------------------------------------------
# Horários livres
# ---------------------------------------------------------------------------

def obter_horarios_disponiveis(salao, profissional, servico, dia: date) -> list:
    """
    Horários de INÍCIO livres para `servico` com `profissional` no `dia`.
    O fim de cada slot é `slot + servico.duracao_minutos`.
    """
    hora_abertura, hora_fechamento = janela_do_dia(salao, dia, profissional)
    if hora_abertura is None:
        return []

    limite = date.today() + timedelta(days=current_app.config.get("AGENDAMENTO_ANTECEDENCIA_MAXIMA_DIAS", 60))
    if dia > limite:
        return []

    duracao = timedelta(minutes=servico.duracao_minutos)
    passo = timedelta(minutes=GRANULARIDADE_MINUTOS)
    ocupados = _intervalos_ocupados(profissional.id, dia)

    cursor = datetime.combine(dia, hora_abertura)
    fim_do_expediente = datetime.combine(dia, hora_fechamento)
    agora = datetime.now()

    slots = []
    while cursor + duracao <= fim_do_expediente:
        fim_slot = cursor + duracao
        livre = all(not (cursor < o_fim and fim_slot > o_inicio) for o_inicio, o_fim in ocupados)
        if cursor >= agora and livre:
            slots.append(cursor)
        cursor += passo
    return slots


def obter_horarios_qualquer_profissional(salao, servico, dia: date) -> list:
    """
    Quando o cliente não escolhe profissional: junta os horários de todos
    os profissionais ativos. Retorna [(datetime, profissional_id)] sem
    repetir horário (fica com o primeiro profissional livre), em ordem.
    """
    profissionais = Profissional.query.filter_by(salao_id=salao.id, ativo=True).all()
    por_horario = {}
    for profissional in profissionais:
        for slot in obter_horarios_disponiveis(salao, profissional, servico, dia):
            por_horario.setdefault(slot, profissional.id)
    return sorted(por_horario.items())


def escolher_profissional_livre(salao, servico, inicio: datetime):
    """Primeiro profissional ativo que consegue atender `servico` em `inicio`, ou None."""
    profissionais = Profissional.query.filter_by(salao_id=salao.id, ativo=True).all()
    for profissional in profissionais:
        try:
            validar_e_montar_agendamento(salao, profissional, servico, inicio)
            return profissional
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Validação de um horário solicitado
# ---------------------------------------------------------------------------

def validar_e_montar_agendamento(salao, profissional, servico, inicio: datetime,
                                 agendamento_id_excluir: str = None) -> datetime:
    """
    Valida um horário de início e devolve o horário de fim calculado.
    Levanta ValueError com mensagem amigável se não der para atender.
    """
    fim = inicio + timedelta(minutes=servico.duracao_minutos)

    hora_abertura, hora_fechamento = janela_do_dia(salao, inicio.date(), profissional)
    if hora_abertura is None:
        raise ValueError("O salão não atende neste dia.")

    janela_inicio = datetime.combine(inicio.date(), hora_abertura)
    janela_fim = datetime.combine(inicio.date(), hora_fechamento)
    if inicio < janela_inicio or fim > janela_fim:
        raise ValueError("Horário fora do expediente do profissional/salão.")

    if inicio < datetime.now():
        raise ValueError("Não é possível agendar em um horário no passado.")

    limite = datetime.now() + timedelta(days=current_app.config.get("AGENDAMENTO_ANTECEDENCIA_MAXIMA_DIAS", 60))
    if inicio > limite:
        raise ValueError("Ainda não é possível agendar com tanta antecedência.")

    if existe_conflito(profissional.id, inicio, fim, agendamento_id_excluir):
        raise ValueError("Este horário já está ocupado para este profissional.")

    if _esta_dentro_de_indisponibilidade(profissional.id, inicio, fim):
        raise ValueError("O profissional está indisponível neste horário.")

    return fim

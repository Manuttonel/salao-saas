# -*- coding: utf-8 -*-
"""
Regras de negócio do agendamento: cálculo de horários disponíveis e
prevenção de conflitos de agenda.

Este módulo NÃO faz nada com o banco além de consultas (SELECT) — quem
efetivamente cria/cancela um Agendamento é a rota em
app/routes/agendamento_routes.py, que chama `existe_conflito()` logo
antes do INSERT para garantir que dois clientes não consigam reservar o
mesmo horário do mesmo profissional (nem em caso de dois cliques quase
simultâneos — para isso a rota também usa uma trava a nível de
transação, veja o comentário lá).
"""

from datetime import datetime, timedelta, date, time as time_type

from app.extensions import db
from app.models.agendamento import Agendamento, StatusAgendamento
from app.models.profissional import Indisponibilidade

# Agenda é sempre "fatiada" em intervalos de 15 minutos para sugerir
# horários — evita sugerir, por exemplo, 09:07 como opção.
GRANULARIDADE_MINUTOS = 15


def existe_conflito(profissional_id: str, inicio: datetime, fim: datetime, agendamento_id_excluir: str = None) -> bool:
    """
    Retorna True se o profissional já tem um agendamento (não cancelado)
    cujo intervalo [inicio, fim) se sobrepõe ao intervalo informado.

    Duas faixas [a_inicio, a_fim) e [b_inicio, b_fim) se sobrepõem
    quando: a_inicio < b_fim E a_fim > b_inicio.
    """
    query = Agendamento.query.filter(
        Agendamento.profissional_id == profissional_id,
        Agendamento.status != StatusAgendamento.CANCELADO,
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


def _horario_funcionamento_do_dia(salao, profissional, dia: date):
    """
    Descobre a janela de funcionamento (hora início/fim) válida para um
    profissional em um dia específico, considerando: dias de
    funcionamento do salão + horário próprio do profissional (se
    definido) ou, na falta dele, o horário do salão.
    """
    dia_semana = dia.weekday()  # 0 = segunda ... 6 = domingo
    if dia_semana not in (salao.dias_funcionamento or []):
        return None, None

    inicio = profissional.horario_inicio or salao.horario_abertura
    fim = profissional.horario_fim or salao.horario_fechamento
    return inicio, fim


def obter_horarios_disponiveis(salao, profissional, servico, dia: date) -> list[datetime]:
    """
    Calcula os horários de início disponíveis para agendar `servico` com
    `profissional`, no dia informado, respeitando:
      - dias/horário de funcionamento do salão e do profissional;
      - agendamentos já confirmados desse profissional;
      - períodos marcados como indisponíveis;
      - não sugerir horários no passado (se `dia` for hoje).

    Retorna uma lista de objetos datetime (o horário de INÍCIO de cada
    slot livre); o horário de término de cada slot é
    `slot + timedelta(minutes=servico.duracao_minutos)`.
    """
    hora_abertura, hora_fechamento = _horario_funcionamento_do_dia(salao, profissional, dia)
    if hora_abertura is None:
        return []  # salão fechado nesse dia da semana

    duracao = timedelta(minutes=servico.duracao_minutos)
    passo = timedelta(minutes=GRANULARIDADE_MINUTOS)

    cursor = datetime.combine(dia, hora_abertura)
    fim_do_expediente = datetime.combine(dia, hora_fechamento)
    agora = datetime.now()

    slots_disponiveis = []
    while cursor + duracao <= fim_do_expediente:
        fim_slot = cursor + duracao

        horario_valido = cursor >= agora  # não sugere horário que já passou
        if horario_valido and not existe_conflito(profissional.id, cursor, fim_slot):
            if not _esta_dentro_de_indisponibilidade(profissional.id, cursor, fim_slot):
                slots_disponiveis.append(cursor)

        cursor += passo

    return slots_disponiveis


def validar_e_montar_agendamento(salao, profissional, servico, inicio: datetime):
    """
    Valida um horário de início solicitado (usado ao CRIAR um
    agendamento) e devolve o horário de fim calculado. Levanta ValueError
    com uma mensagem amigável se o horário for inválido.
    """
    fim = inicio + timedelta(minutes=servico.duracao_minutos)

    hora_abertura, hora_fechamento = _horario_funcionamento_do_dia(salao, profissional, inicio.date())
    if hora_abertura is None:
        raise ValueError("O salão não funciona neste dia da semana.")

    janela_inicio = datetime.combine(inicio.date(), hora_abertura)
    janela_fim = datetime.combine(inicio.date(), hora_fechamento)
    if inicio < janela_inicio or fim > janela_fim:
        raise ValueError("Horário fora do expediente do profissional/salão.")

    if inicio < datetime.now():
        raise ValueError("Não é possível agendar em um horário no passado.")

    if existe_conflito(profissional.id, inicio, fim):
        raise ValueError("Este horário já está ocupado para este profissional.")

    if _esta_dentro_de_indisponibilidade(profissional.id, inicio, fim):
        raise ValueError("O profissional está indisponível neste horário.")

    return fim

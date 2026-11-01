# -*- coding: utf-8 -*-
"""
Bot de WhatsApp: o cliente conversa pelo WhatsApp e SOLICITA um horário.

O bot é uma "máquina de estados" simples, sem IA: a cada mensagem ele olha
em que etapa a conversa está (tabela ConversaWhatsapp) e interpreta o que
o cliente digitou (quase sempre um número de uma lista).

    menu -> escolher_servico -> escolher_data -> escolher_hora
         -> (pedir_nome) -> confirmar -> solicitação criada (PENDENTE)

Ao final NÃO confirma o horário: cria uma solicitação PENDENTE e avisa os
administradores, exatamente como o pedido feito pelo site. O horário só
fica reservado quando um administrador aceita no painel.

`processar_mensagem()` devolve a lista de respostas (textos) — quem chama
decide se envia pelo WhatsApp (webhook) ou só mostra na tela (simulador do
painel).
"""

import re
import unicodedata
from datetime import datetime, timedelta, date

from app.extensions import db
from app.models.agendamento import Agendamento, StatusAgendamento
from app.models.cliente import Cliente
from app.models.conversa_whatsapp import ConversaWhatsapp
from app.models.salao import Servico, CATEGORIAS_SERVICO
from app.services import agendador_service, whatsapp_service
from app.services.cliente_service import normalizar_telefone, obter_ou_criar_cliente

# Depois deste tempo sem mensagens, a conversa recomeça do menu.
EXPIRA_CONVERSA = timedelta(hours=2)
MAX_DIAS_LISTADOS = 7
MAX_HORARIOS_LISTADOS = 12
DIAS_A_PROCURAR = 30

PALAVRAS_MENU = {"menu", "oi", "ola", "olá", "inicio", "início", "bom dia", "boa tarde", "boa noite", "voltar", "0"}
PALAVRAS_CANCELAR = {"cancelar", "sair", "parar"}


def _normalizar(texto: str) -> str:
    """minúsculas, sem acentos e sem espaços nas pontas: 'Olá ' -> 'ola'."""
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return sem_acento.strip().lower()


def _eh_numero(texto: str, maximo: int):
    """Devolve o número digitado (1..maximo) ou None."""
    achado = re.fullmatch(r"\s*(\d{1,2})\s*", texto or "")
    if not achado:
        return None
    numero = int(achado.group(1))
    return numero if 1 <= numero <= maximo else None


def _dia_curto(dia: date) -> str:
    return f"{whatsapp_service.DIAS_SEMANA[dia.weekday()][:3]} {dia.strftime('%d/%m')}"


# ---------------------------------------------------------------------------
# Conversa (estado salvo no banco)
# ---------------------------------------------------------------------------

def _obter_conversa(salao, telefone: str) -> ConversaWhatsapp:
    conversa = ConversaWhatsapp.query.filter_by(salao_id=salao.id, telefone=telefone).first()
    if conversa is None:
        conversa = ConversaWhatsapp(salao_id=salao.id, telefone=telefone, estado="menu", dados={})
        db.session.add(conversa)
        db.session.flush()
    elif conversa.atualizado_em and datetime.now() - conversa.atualizado_em > EXPIRA_CONVERSA:
        conversa.estado, conversa.dados = "menu", {}
    return conversa


def _definir(conversa: ConversaWhatsapp, estado: str, **dados) -> None:
    """Muda a etapa e mescla `dados`. Cria um dict novo: o SQLAlchemy não percebe mutações no JSON."""
    conversa.estado = estado
    conversa.dados = {**(conversa.dados or {}), **dados}
    conversa.atualizado_em = datetime.now()


def _reiniciar(conversa: ConversaWhatsapp) -> None:
    conversa.estado, conversa.dados = "menu", {}
    conversa.atualizado_em = datetime.now()


# ---------------------------------------------------------------------------
# Textos
# ---------------------------------------------------------------------------

def _texto_menu(salao, nome: str = None) -> str:
    saudacao = f"Olá, {nome.split()[0]}!" if nome else "Olá!"
    return (
        f"{saudacao} Bem-vindo(a) ao *{salao.nome}*.\n\n"
        "Como posso ajudar?\n"
        "*1* - Agendar um procedimento\n"
        "*2* - Marcar uma avaliação\n"
        "*3* - Meus agendamentos\n\n"
        "Responda com o número da opção. Digite *menu* a qualquer momento para voltar."
    )


def _servicos_do_salao(salao) -> list:
    return (
        Servico.query.filter_by(salao_id=salao.id, ativo=True, eh_avaliacao=False)
        .order_by(Servico.categoria, Servico.nome)
        .all()
    )


def _servico_avaliacao(salao):
    return Servico.query.filter_by(salao_id=salao.id, ativo=True, eh_avaliacao=True).first()


# ---------------------------------------------------------------------------
# Etapas
# ---------------------------------------------------------------------------

def _listar_servicos(conversa, salao) -> list:
    servicos = _servicos_do_salao(salao)
    if not servicos:
        _reiniciar(conversa)
        return ["Ainda não temos procedimentos cadastrados. Tente a opção *2* (avaliação) ou fale com o salão."]

    linhas, ids, categoria_atual = ["Qual procedimento você quer?\n"], [], None
    for servico in servicos:
        if servico.categoria != categoria_atual:
            categoria_atual = servico.categoria
            linhas.append(f"\n*{CATEGORIAS_SERVICO.get(categoria_atual, 'Outros')}*")
        ids.append(servico.id)
        preco = f"R$ {float(servico.preco):.2f}".replace(".", ",")
        linhas.append(f"*{len(ids)}* - {servico.nome} ({servico.duracao_minutos} min, {preco})")
    linhas.append("\nResponda com o número. *menu* volta ao início.")

    _definir(conversa, "escolher_servico", opcoes_servicos=ids)
    return ["\n".join(linhas)]


def _listar_dias(conversa, salao, servico) -> list:
    """Procura os próximos dias que realmente têm algum horário livre."""
    dias, hoje = [], date.today()
    for deslocamento in range(DIAS_A_PROCURAR):
        dia = hoje + timedelta(days=deslocamento)
        if agendador_service.janela_do_dia(salao, dia)[0] is None:
            continue
        if agendador_service.obter_horarios_qualquer_profissional(salao, servico, dia):
            dias.append(dia)
        if len(dias) == MAX_DIAS_LISTADOS:
            break

    if not dias:
        _reiniciar(conversa)
        return ["No momento não há horários livres nos próximos dias. Fale com o salão para combinar."]

    linhas = [f"*{servico.nome}* ({servico.duracao_minutos} min)\nQual dia fica melhor?\n"]
    for indice, dia in enumerate(dias, start=1):
        linhas.append(f"*{indice}* - {_dia_curto(dia)}")
    linhas.append("\n*menu* volta ao início.")

    _definir(conversa, "escolher_data", servico_id=servico.id, opcoes_dias=[d.isoformat() for d in dias])
    return ["\n".join(linhas)]


def _listar_horarios(conversa, salao, servico, dia: date) -> list:
    livres = agendador_service.obter_horarios_qualquer_profissional(salao, servico, dia)[:MAX_HORARIOS_LISTADOS]
    if not livres:
        return ["Esse dia acabou de lotar. Escolha outro dia (digite *menu* para recomeçar)."]

    linhas = [f"Horários livres em *{_dia_curto(dia)}*:\n"]
    for indice, (inicio, _prof) in enumerate(livres, start=1):
        linhas.append(f"*{indice}* - {inicio.strftime('%H:%M')}")
    linhas.append("\n*menu* volta ao início.")

    _definir(
        conversa, "escolher_hora", dia=dia.isoformat(),
        opcoes_horarios=[[inicio.isoformat(), prof_id] for inicio, prof_id in livres],
    )
    return ["\n".join(linhas)]


def _resumo_confirmacao(salao, servico, inicio: datetime) -> str:
    return (
        "Confira seu pedido:\n"
        f"*{servico.nome}* ({servico.duracao_minutos} min)\n"
        f"{whatsapp_service.formatar_data_hora(inicio)}\n"
        f"{salao.nome}\n\n"
        "*1* - Enviar solicitação\n"
        "*2* - Cancelar\n\n"
        "O salão vai analisar e você receberá a resposta por aqui."
    )


def _criar_solicitacao(app, conversa, salao, telefone: str, nome_contato: str):
    """Cria o Agendamento PENDENTE e avisa cliente + administradores."""
    dados = conversa.dados
    servico = db.session.get(Servico, dados["servico_id"])
    inicio = datetime.fromisoformat(dados["inicio"])

    # Quem está livre exatamente agora (o horário pode ter sido ocupado enquanto o cliente decidia).
    profissional = agendador_service.escolher_profissional_livre(salao, servico, inicio)
    if profissional is None:
        _reiniciar(conversa)
        return ["Poxa, esse horário acabou de ser ocupado. Digite *menu* para escolher outro."]

    cliente = obter_ou_criar_cliente(
        salao.id, telefone=telefone, nome=dados.get("nome") or nome_contato, origem="whatsapp"
    )
    fim = inicio + timedelta(minutes=servico.duracao_minutos)

    # Mesma proteção do site: o mesmo cliente não duplica um pedido no mesmo período.
    ja_pediu = Agendamento.query.filter(
        Agendamento.cliente_id == cliente.id,
        Agendamento.status.in_([StatusAgendamento.PENDENTE, StatusAgendamento.CONFIRMADO]),
        Agendamento.inicio < fim,
        Agendamento.fim > inicio,
    ).first()
    if ja_pediu is not None:
        _reiniciar(conversa)
        db.session.commit()
        return [
            "Você já tem uma solicitação ou horário nesse período "
            f"({whatsapp_service.formatar_data_hora(ja_pediu.inicio)}). "
            "Digite *3* no *menu* para ver seus agendamentos."
        ]

    agendamento = Agendamento(
        cliente_id=cliente.id,
        profissional_id=profissional.id,
        salao_id=salao.id,
        servico_id=servico.id,
        inicio=inicio,
        fim=fim,
        status=StatusAgendamento.PENDENTE,
        origem="whatsapp",
    )
    db.session.add(agendamento)
    _reiniciar(conversa)
    db.session.commit()

    whatsapp_service.notificar_admins_nova_solicitacao(app, agendamento)
    return [
        "Solicitação enviada! Assim que o salão confirmar, avisamos por aqui.\n"
        "Digite *menu* para voltar ao início."
    ]


def _listar_meus_agendamentos(salao, telefone: str) -> list:
    cliente = Cliente.query.filter_by(salao_id=salao.id, telefone=telefone).first()
    agendamentos = []
    if cliente:
        agendamentos = (
            Agendamento.query.filter(
                Agendamento.cliente_id == cliente.id,
                Agendamento.inicio >= datetime.now(),
                Agendamento.status.in_([StatusAgendamento.PENDENTE, StatusAgendamento.CONFIRMADO]),
            )
            .order_by(Agendamento.inicio)
            .limit(8)
            .all()
        )
    if not agendamentos:
        return ["Você não tem agendamentos futuros. Digite *1* ou *2* no *menu* para marcar."]

    rotulos = {StatusAgendamento.PENDENTE: "aguardando confirmação", StatusAgendamento.CONFIRMADO: "confirmado"}
    linhas = ["Seus próximos horários:\n"]
    for ag in agendamentos:
        linhas.append(f"- {whatsapp_service.formatar_data_hora(ag.inicio)}: {ag.servico.nome} ({rotulos[ag.status]})")
    linhas.append("\nDigite *menu* para voltar.")
    return ["\n".join(linhas)]


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------

def processar_mensagem(app, salao, telefone: str, texto: str, nome_contato: str = None) -> list:
    """Processa UMA mensagem do cliente e devolve as respostas (lista de textos)."""
    telefone = normalizar_telefone(telefone)
    if not telefone:
        return []

    conversa = _obter_conversa(salao, telefone)
    entrada = _normalizar(texto)
    estado = conversa.estado

    # Comandos que funcionam em qualquer etapa.
    if entrada in PALAVRAS_CANCELAR:
        _reiniciar(conversa)
        db.session.commit()
        return ["Ok, cancelei. " + _texto_menu(salao, nome_contato)]
    if entrada in PALAVRAS_MENU and estado != "pedir_nome":
        _reiniciar(conversa)
        db.session.commit()
        return [_texto_menu(salao, nome_contato)]

    respostas = _tratar_etapa(app, conversa, salao, telefone, entrada, texto, nome_contato)
    db.session.commit()
    return respostas


def _tratar_etapa(app, conversa, salao, telefone, entrada, texto_original, nome_contato) -> list:
    estado, dados = conversa.estado, conversa.dados or {}

    if estado == "menu":
        if entrada == "1":
            return _listar_servicos(conversa, salao)
        if entrada == "2":
            avaliacao = _servico_avaliacao(salao)
            if avaliacao is None:
                return ["A avaliação não está disponível no momento. " + _texto_menu(salao, nome_contato)]
            return _listar_dias(conversa, salao, avaliacao)
        if entrada == "3":
            return _listar_meus_agendamentos(salao, telefone)
        return [_texto_menu(salao, nome_contato)]

    if estado == "escolher_servico":
        ids = dados.get("opcoes_servicos", [])
        numero = _eh_numero(entrada, len(ids))
        if numero is None:
            return [f"Não entendi. Responda com um número de 1 a {len(ids)}, ou *menu*."]
        return _listar_dias(conversa, salao, db.session.get(Servico, ids[numero - 1]))

    if estado == "escolher_data":
        dias = dados.get("opcoes_dias", [])
        numero = _eh_numero(entrada, len(dias))
        if numero is None:
            return [f"Não entendi. Responda com um número de 1 a {len(dias)}, ou *menu*."]
        servico = db.session.get(Servico, dados["servico_id"])
        return _listar_horarios(conversa, salao, servico, date.fromisoformat(dias[numero - 1]))

    if estado == "escolher_hora":
        horarios = dados.get("opcoes_horarios", [])
        numero = _eh_numero(entrada, len(horarios))
        if numero is None:
            return [f"Não entendi. Responda com um número de 1 a {len(horarios)}, ou *menu*."]
        inicio_iso = horarios[numero - 1][0]
        _definir(conversa, "confirmar", inicio=inicio_iso)

        # Cliente novo e sem nome de contato: pergunta o nome antes de confirmar.
        ficha = Cliente.query.filter_by(salao_id=salao.id, telefone=telefone).first()
        if not (ficha and ficha.nome) and not nome_contato:
            _definir(conversa, "pedir_nome")
            return ["Para finalizar, qual é o seu *nome*?"]
        servico = db.session.get(Servico, conversa.dados["servico_id"])
        return [_resumo_confirmacao(salao, servico, datetime.fromisoformat(inicio_iso))]

    if estado == "pedir_nome":
        nome = (texto_original or "").strip()[:80]
        if len(nome) < 2:
            return ["Pode me dizer seu nome, por favor?"]
        _definir(conversa, "confirmar", nome=nome)
        servico = db.session.get(Servico, conversa.dados["servico_id"])
        return [_resumo_confirmacao(salao, servico, datetime.fromisoformat(conversa.dados["inicio"]))]

    if estado == "confirmar":
        if entrada == "1":
            return _criar_solicitacao(app, conversa, salao, telefone, nome_contato)
        if entrada == "2":
            _reiniciar(conversa)
            return ["Tudo bem, não enviei nada. " + _texto_menu(salao, nome_contato)]
        return ["Responda *1* para enviar a solicitação ou *2* para cancelar."]

    _reiniciar(conversa)
    return [_texto_menu(salao, nome_contato)]


# ---------------------------------------------------------------------------
# Leitura do que o provedor de WhatsApp envia ao webhook
# ---------------------------------------------------------------------------

def extrair_mensagens_recebidas(payload: dict) -> list:
    """
    Converte o JSON do webhook em [(telefone, texto, nome_contato)].
    Entende os dois provedores suportados e ignora mensagens enviadas por
    nós mesmos (fromMe) e conversas em grupo.
    """
    mensagens = []

    # Evolution API: {"event": "messages.upsert", "data": {"key": {...}, "message": {...}}}
    dados = payload.get("data")
    if isinstance(dados, dict) and isinstance(dados.get("key"), dict):
        chave = dados["key"]
        jid = chave.get("remoteJid", "")
        if not chave.get("fromMe") and jid and not jid.endswith("@g.us"):
            conteudo = dados.get("message") or {}
            texto = conteudo.get("conversation") or (conteudo.get("extendedTextMessage") or {}).get("text") or ""
            if texto:
                mensagens.append((jid.split("@")[0], texto, dados.get("pushName")))

    # Meta Cloud API: {"entry": [{"changes": [{"value": {"messages": [...], "contacts": [...]}}]}]}
    for entrada in payload.get("entry", []) or []:
        for mudanca in entrada.get("changes", []) or []:
            valor = mudanca.get("value", {})
            nomes = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in valor.get("contacts", []) or []}
            for msg in valor.get("messages", []) or []:
                if msg.get("type") == "text":
                    mensagens.append((msg.get("from"), msg["text"].get("body", ""), nomes.get(msg.get("from"))))

    return mensagens

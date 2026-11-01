# -*- coding: utf-8 -*-
"""
Envio de mensagens de WhatsApp (solicitações, confirmações, lembretes e
avisos de cobrança).

Este módulo é uma CAMADA DE ABSTRAÇÃO: o resto da aplicação só chama as
funções `enviar_*` — nenhuma delas sabe qual provedor está por trás. Para
trocar de provedor basta mudar WHATSAPP_PROVIDER no .env.

Dois provedores são suportados:

1. "meta_cloud_api" — WhatsApp Business Cloud API oficial, da Meta.
   Credenciais: WHATSAPP_META_TOKEN e WHATSAPP_META_PHONE_NUMBER_ID.
   Documentação: https://developers.facebook.com/docs/whatsapp/cloud-api

2. "evolution_api" — Evolution API (open-source), conecta por QRCode a um
   número comum, sem aprovação da Meta. Você hospeda a API.
   Credenciais: WHATSAPP_EVOLUTION_BASE_URL, WHATSAPP_EVOLUTION_INSTANCE e
   WHATSAPP_EVOLUTION_API_KEY. Cada salão pode ter a sua própria instância
   (campo Salao.whatsapp_instancia); sem ela, vale a instância do .env.

Enquanto WHATSAPP_MODO_SIMULACAO=true (padrão em desenvolvimento), nada é
enviado de verdade: as mensagens só aparecem no log do servidor.
"""

import logging

import requests

logger = logging.getLogger(__name__)

DIAS_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def formatar_data_hora(momento) -> str:
    """datetime -> 'sexta, 07/11 às 14:30' (usado nas mensagens)."""
    return f"{DIAS_SEMANA[momento.weekday()]}, {momento.strftime('%d/%m')} às {momento.strftime('%H:%M')}"


def _enviar_via_meta_cloud_api(app, telefone: str, mensagem: str) -> None:
    url = f"https://graph.facebook.com/v19.0/{app.config['WHATSAPP_META_PHONE_NUMBER_ID']}/messages"
    headers = {
        "Authorization": f"Bearer {app.config['WHATSAPP_META_TOKEN']}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": telefone,
        "type": "text",
        "text": {"body": mensagem},
    }
    resposta = requests.post(url, json=payload, headers=headers, timeout=10)
    resposta.raise_for_status()


def _enviar_via_evolution_api(app, telefone: str, mensagem: str, instancia: str) -> None:
    base_url = app.config["WHATSAPP_EVOLUTION_BASE_URL"].rstrip("/")
    url = f"{base_url}/message/sendText/{instancia}"
    headers = {"apikey": app.config["WHATSAPP_EVOLUTION_API_KEY"]}
    payload = {"number": telefone, "text": mensagem}
    resposta = requests.post(url, json=payload, headers=headers, timeout=10)
    resposta.raise_for_status()


def enviar_mensagem(app, telefone: str, mensagem: str, salao=None) -> None:
    """
    Envia (ou simula) uma mensagem de texto. Uma falha no envio NUNCA
    derruba a operação principal (ex.: criar agendamento): só é logada.
    """
    if not telefone:
        return

    if app.config.get("WHATSAPP_MODO_SIMULACAO", True):
        logger.info("[WHATSAPP SIMULADO] Para %s: %s", telefone, mensagem)
        return

    provedor = app.config["WHATSAPP_PROVIDER"]
    instancia = (salao.whatsapp_instancia if salao is not None and salao.whatsapp_instancia
                 else app.config["WHATSAPP_EVOLUTION_INSTANCE"])
    try:
        if provedor == "meta_cloud_api":
            _enviar_via_meta_cloud_api(app, telefone, mensagem)
        elif provedor == "evolution_api":
            _enviar_via_evolution_api(app, telefone, mensagem, instancia)
        else:
            raise ValueError(f"WHATSAPP_PROVIDER desconhecido: {provedor}")
        logger.info("Mensagem WhatsApp enviada para %s via %s", telefone, provedor)
    except Exception:
        logger.exception("Falha ao enviar mensagem WhatsApp para %s", telefone)


def _avisar_cliente(app, agendamento, mensagem: str) -> None:
    """Envia ao cliente, respeitando a preferência dele de receber WhatsApp."""
    cliente = agendamento.cliente
    if not cliente.aceita_notificacoes_whatsapp:
        return
    enviar_mensagem(app, cliente.telefone_exibicao, mensagem, agendamento.salao)


# ---------------------------------------------------------------------------
# Fluxo de solicitação -> aceite/recusa
# ---------------------------------------------------------------------------

def enviar_solicitacao_recebida(app, agendamento) -> None:
    """Avisa o cliente que o pedido chegou e está aguardando o salão."""
    _avisar_cliente(app, agendamento, (
        f"Olá, {agendamento.cliente.nome_exibicao}! Recebemos seu pedido de "
        f"{agendamento.servico.nome} para {formatar_data_hora(agendamento.inicio)} "
        f"no {agendamento.salao.nome}. Assim que o salão confirmar, você receberá "
        f"uma mensagem por aqui."
    ))


def notificar_admins_nova_solicitacao(app, agendamento) -> None:
    """Avisa o dono e todos os administradores que há uma solicitação para responder."""
    salao = agendamento.salao
    mensagem = (
        f"Nova solicitação no {salao.nome}: {agendamento.cliente.nome_exibicao} "
        f"quer {agendamento.servico.nome} em {formatar_data_hora(agendamento.inicio)} "
        f"({agendamento.servico.duracao_minutos} min). "
        f"Abra o painel para aceitar ou recusar."
    )
    for admin in salao.administradores():
        enviar_mensagem(app, admin.telefone, mensagem, salao)


def enviar_confirmacao_agendamento(app, agendamento) -> None:
    """O salão ACEITOU: o horário está reservado para o cliente."""
    _avisar_cliente(app, agendamento, (
        f"Olá, {agendamento.cliente.nome_exibicao}! Seu horário no {agendamento.salao.nome} "
        f"foi CONFIRMADO para {formatar_data_hora(agendamento.inicio)} com "
        f"{agendamento.profissional.nome_exibicao} ({agendamento.servico.nome}). Até lá!"
    ))


def enviar_recusa_agendamento(app, agendamento) -> None:
    """O salão RECUSOU o pedido."""
    motivo = f" Motivo: {agendamento.motivo_recusa}." if agendamento.motivo_recusa else ""
    _avisar_cliente(app, agendamento, (
        f"Olá, {agendamento.cliente.nome_exibicao}. Infelizmente o {agendamento.salao.nome} "
        f"não conseguiu atender seu pedido de {formatar_data_hora(agendamento.inicio)}.{motivo} "
        f"Que tal escolher outro horário?"
    ))


def enviar_cancelamento_agendamento(app, agendamento) -> None:
    """Avisa o cliente quando o SALÃO cancela um horário já confirmado."""
    _avisar_cliente(app, agendamento, (
        f"Olá, {agendamento.cliente.nome_exibicao}. Seu horário de "
        f"{formatar_data_hora(agendamento.inicio)} no {agendamento.salao.nome} foi cancelado. "
        f"Entre em contato para remarcar."
    ))


def enviar_lembrete_agendamento(app, agendamento, horas_de_antecedencia: int) -> None:
    """Lembrete ao cliente faltando `horas_de_antecedencia` para o horário."""
    prazo = "amanhã" if horas_de_antecedencia >= 24 else "em 1 hora"
    _avisar_cliente(app, agendamento, (
        f"Olá, {agendamento.cliente.nome_exibicao}! Lembrando que você tem um horário {prazo} "
        f"({formatar_data_hora(agendamento.inicio)}) no {agendamento.salao.nome} com "
        f"{agendamento.profissional.nome_exibicao}. Até já!"
    ))


def enviar_aviso_cobranca(app, salao, mensagem_extra: str = "") -> None:
    """Avisa o dono do salão sobre a situação da assinatura da plataforma."""
    dono = salao.dono
    enviar_mensagem(app, dono.telefone, (
        f"Olá, {dono.nome}! Sobre a assinatura da plataforma para o salão "
        f"{salao.nome}: {mensagem_extra}"
    ), salao)

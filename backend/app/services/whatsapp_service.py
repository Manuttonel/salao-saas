# -*- coding: utf-8 -*-
"""
Envio de mensagens de WhatsApp (confirmação de agendamento, lembretes e
avisos de cobrança).

Este módulo é uma CAMADA DE ABSTRAÇÃO: o resto da aplicação (rotas,
jobs do scheduler) só chama as funções `enviar_confirmacao_agendamento`,
`enviar_lembrete_agendamento` e `enviar_aviso_cobranca` — nenhuma delas
sabe qual provedor de WhatsApp está por trás. Isso permite trocar de
provedor mudando só a variável de ambiente WHATSAPP_PROVIDER, sem tocar
em nenhuma outra parte do código.

Dois provedores são suportados:

1. "meta_cloud_api" — WhatsApp Business Cloud API oficial, da Meta.
   - Requer conta comercial verificada no Meta Business Manager e número
     de telefone aprovado.
   - Documentação: https://developers.facebook.com/docs/whatsapp/cloud-api
   - Credenciais: WHATSAPP_META_TOKEN e WHATSAPP_META_PHONE_NUMBER_ID.
   - Recomendado para produção / uso comercial sério, mas tem processo
     de aprovação mais burocrático.

2. "evolution_api" — Evolution API, projeto open-source muito usado no
   Brasil, que conecta via QRCode a um número de WhatsApp comum (não
   precisa de aprovação da Meta). Você mesmo hospeda essa API (ela roda
   como um serviço próprio, veja https://doc.evolution-api.com).
   - Credenciais: WHATSAPP_EVOLUTION_BASE_URL, WHATSAPP_EVOLUTION_INSTANCE
     e WHATSAPP_EVOLUTION_API_KEY.
   - Mais simples para começar/testar, mas o número fica sujeito às
     regras de uso comum do WhatsApp (risco de bloqueio em uso abusivo).

Para trocar de provedor: mude WHATSAPP_PROVIDER no backend/.env para
"meta_cloud_api" ou "evolution_api" e preencha as credenciais
correspondentes — nenhuma outra alteração de código é necessária.

Enquanto WHATSAPP_MODO_SIMULACAO=true (padrão em desenvolvimento), as
mensagens não são enviadas de verdade: apenas registradas no log. Isso
permite desenvolver e testar o fluxo sem gastar créditos de API nem
precisar de uma instância de WhatsApp configurada.
"""

import logging

import requests

logger = logging.getLogger(__name__)


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


def _enviar_via_evolution_api(app, telefone: str, mensagem: str) -> None:
    base_url = app.config["WHATSAPP_EVOLUTION_BASE_URL"].rstrip("/")
    instancia = app.config["WHATSAPP_EVOLUTION_INSTANCE"]
    url = f"{base_url}/message/sendText/{instancia}"
    headers = {"apikey": app.config["WHATSAPP_EVOLUTION_API_KEY"]}
    payload = {"number": telefone, "text": mensagem}
    resposta = requests.post(url, json=payload, headers=headers, timeout=10)
    resposta.raise_for_status()


def _enviar_mensagem(app, telefone: str, mensagem: str) -> None:
    """
    Função interna que decide, com base em WHATSAPP_PROVIDER, para qual
    provedor real a mensagem deve ir — ou se deve apenas simular o envio.
    """
    if app.config.get("WHATSAPP_MODO_SIMULACAO", True):
        logger.info("[WHATSAPP SIMULADO] Para %s: %s", telefone, mensagem)
        return

    provedor = app.config["WHATSAPP_PROVIDER"]
    try:
        if provedor == "meta_cloud_api":
            _enviar_via_meta_cloud_api(app, telefone, mensagem)
        elif provedor == "evolution_api":
            _enviar_via_evolution_api(app, telefone, mensagem)
        else:
            raise ValueError(f"WHATSAPP_PROVIDER desconhecido: {provedor}")
        logger.info("Mensagem WhatsApp enviada para %s via %s", telefone, provedor)
    except Exception:
        # Uma falha ao enviar WhatsApp não deve derrubar a operação
        # principal (ex.: criar um agendamento) — só registramos o erro.
        logger.exception("Falha ao enviar mensagem WhatsApp para %s", telefone)


def enviar_confirmacao_agendamento(app, agendamento) -> None:
    """Envia ao cliente a confirmação de que o agendamento foi criado."""
    cliente_nome = agendamento.cliente.usuario.nome
    telefone = agendamento.cliente.usuario.telefone
    data_formatada = agendamento.inicio.strftime("%d/%m/%Y às %H:%M")
    mensagem = (
        f"Olá, {cliente_nome}! Seu agendamento em {agendamento.salao.nome} foi "
        f"confirmado para {data_formatada} com {agendamento.profissional.usuario.nome} "
        f"({agendamento.servico.nome}). Até lá!"
    )
    _enviar_mensagem(app, telefone, mensagem)


def enviar_lembrete_agendamento(app, agendamento, horas_de_antecedencia: int) -> None:
    """Envia lembrete ao cliente faltando `horas_de_antecedencia` para o horário."""
    cliente_nome = agendamento.cliente.usuario.nome
    telefone = agendamento.cliente.usuario.telefone
    data_formatada = agendamento.inicio.strftime("%d/%m/%Y às %H:%M")
    if horas_de_antecedencia >= 24:
        prazo = "amanhã"
    else:
        prazo = "em 1 hora"
    mensagem = (
        f"Olá, {cliente_nome}! Lembrando que você tem um horário {prazo} "
        f"({data_formatada}) em {agendamento.salao.nome} com "
        f"{agendamento.profissional.usuario.nome}. Até já!"
    )
    _enviar_mensagem(app, telefone, mensagem)


def enviar_aviso_cobranca(app, salao, mensagem_extra: str = "") -> None:
    """Avisa o dono do salão sobre a situação da assinatura da plataforma."""
    dono = salao.dono
    mensagem = (
        f"Olá, {dono.nome}! Sobre a assinatura da plataforma para o salão "
        f"{salao.nome}: {mensagem_extra}"
    )
    _enviar_mensagem(app, dono.telefone, mensagem)

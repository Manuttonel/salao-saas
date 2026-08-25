# -*- coding: utf-8 -*-
"""
Integração com o Mercado Pago para cobrança recorrente (assinatura
mensal do salão na plataforma).

Usamos o recurso de "preapproval" (assinatura/pré-aprovação) da API do
Mercado Pago, que permite cobrar um valor fixo automaticamente todo mês
do cartão do dono do salão, sem precisar gerar uma cobrança manual.

Documentação oficial:
https://www.mercadopago.com.br/developers/pt/docs/subscriptions/landing

Como funciona neste projeto:
1. `criar_assinatura_recorrente()` cria a preapproval no Mercado Pago e
   devolve a URL de checkout — o dono é redirecionado para lá para
   inserir o cartão e autorizar as cobranças futuras.
2. O Mercado Pago envia notificações (webhooks) para a URL configurada
   em MERCADOPAGO_WEBHOOK_URL sempre que o status de um pagamento ou da
   assinatura muda. Essas notificações chegam em
   app/routes/webhook_routes.py, que chama `buscar_preapproval()` ou
   `buscar_pagamento()` aqui para confirmar o que de fato aconteceu
   (nunca confiamos cegamente no payload do webhook — sempre
   confirmamos consultando a API do Mercado Pago com nosso Access Token).
"""

import logging

import mercadopago

logger = logging.getLogger(__name__)


def _obter_sdk(app):
    """Cria uma instância do SDK do Mercado Pago com o Access Token do .env."""
    access_token = app.config["MERCADOPAGO_ACCESS_TOKEN"]
    if not access_token:
        raise RuntimeError(
            "MERCADOPAGO_ACCESS_TOKEN não configurado. Defina essa variável "
            "no backend/.env com sua chave de teste ou produção, obtida em "
            "https://www.mercadopago.com.br/developers/panel"
        )
    return mercadopago.SDK(access_token)


def criar_assinatura_recorrente(app, salao, email_pagador: str) -> dict:
    """
    Cria uma assinatura recorrente mensal ("preapproval") no Mercado Pago
    para o salão informado.

    Retorna um dicionário com o "id" da preapproval e o "init_point"
    (URL de checkout para o dono autorizar a cobrança).
    """
    sdk = _obter_sdk(app)

    payload = {
        "reason": f"Assinatura mensal plataforma - {salao.nome}",
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": float(app.config["PLATFORM_SUBSCRIPTION_PRICE"]),
            "currency_id": "BRL",
        },
        "back_url": app.config["FRONTEND_URL"] + "/assinatura",
        "payer_email": email_pagador,
        "status": "pending",
        # external_reference nos permite, ao receber o webhook, achar
        # rapidamente a qual Salao/Assinatura do NOSSO banco aquela
        # notificação do Mercado Pago se refere.
        "external_reference": salao.id,
        "notification_url": app.config["MERCADOPAGO_WEBHOOK_URL"],
    }

    resposta = sdk.preapproval().create(payload)
    corpo = resposta.get("response", {})

    if resposta.get("status") not in (200, 201):
        logger.error("Falha ao criar preapproval no Mercado Pago: %s", corpo)
        raise RuntimeError(f"Mercado Pago recusou a criação da assinatura: {corpo}")

    return {
        "preapproval_id": corpo["id"],
        "init_point": corpo.get("init_point"),
        "status": corpo.get("status"),
    }


def buscar_preapproval(app, preapproval_id: str) -> dict:
    """Consulta o status atual de uma assinatura (preapproval) no Mercado Pago."""
    sdk = _obter_sdk(app)
    resposta = sdk.preapproval().get(preapproval_id)
    return resposta.get("response", {})


def cancelar_assinatura(app, preapproval_id: str) -> dict:
    """Cancela a assinatura recorrente no Mercado Pago (status='cancelled')."""
    sdk = _obter_sdk(app)
    resposta = sdk.preapproval().update(preapproval_id, {"status": "cancelled"})
    return resposta.get("response", {})


def buscar_pagamento(app, payment_id: str) -> dict:
    """Consulta os detalhes de um pagamento avulso pelo ID (usado no webhook)."""
    sdk = _obter_sdk(app)
    resposta = sdk.payment().get(payment_id)
    return resposta.get("response", {})


# Mapeia os status que o Mercado Pago usa para preapproval em status do
# nosso model Assinatura (app/models/assinatura.py).
MAPA_STATUS_MERCADO_PAGO = {
    "authorized": "aprovada",
    "pending": "pendente",
    "cancelled": "cancelada",
    "paused": "atrasada",
}

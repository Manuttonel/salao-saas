# -*- coding: utf-8 -*-
"""
Webhook do Mercado Pago: recebe notificações automáticas sempre que uma
assinatura (preapproval) ou um pagamento muda de status.

Este endpoint é PÚBLICO (o Mercado Pago não manda nosso JWT), então a
segurança aqui não vem de autenticação de usuário, e sim da validação
da assinatura HMAC que o Mercado Pago envia no header "x-signature".
Isso garante que a notificação realmente veio do Mercado Pago e não de
um terceiro tentando forjar uma aprovação de pagamento.

Documentação oficial da validação de assinatura:
https://www.mercadopago.com.br/developers/pt/docs/your-integrations/notifications/webhooks#editor_3
"""

import hashlib
import hmac
import logging
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, current_app

from app.extensions import db
from app.models.assinatura import Assinatura, StatusAssinatura
from app.services import mercado_pago_service

logger = logging.getLogger(__name__)

webhook_bp = Blueprint("webhook", __name__)


def _assinatura_do_webhook_e_valida(headers, query_args) -> bool:
    """
    Reconstrói o "manifest" esperado pelo Mercado Pago e compara com o
    HMAC-SHA256 enviado no header x-signature. Se MERCADOPAGO_WEBHOOK_SECRET
    não estiver configurado (ex.: ambiente de desenvolvimento sem conta
    real), pulamos a validação para não travar o teste local — mas em
    produção essa variável deve SEMPRE estar definida.
    """
    segredo = current_app.config.get("MERCADOPAGO_WEBHOOK_SECRET")
    if not segredo:
        logger.warning(
            "MERCADOPAGO_WEBHOOK_SECRET não configurado — pulando validação de "
            "assinatura do webhook (NÃO faça isso em produção)."
        )
        return True

    x_signature = headers.get("x-signature", "")
    x_request_id = headers.get("x-request-id", "")
    data_id = query_args.get("data.id", "")

    partes = dict(item.split("=", 1) for item in x_signature.split(",") if "=" in item)
    ts = partes.get("ts", "")
    v1_recebido = partes.get("v1", "")

    manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
    v1_calculado = hmac.new(
        key=segredo.encode(), msg=manifest.encode(), digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(v1_calculado, v1_recebido)


@webhook_bp.post("/mercadopago")
def webhook_mercadopago():
    if not _assinatura_do_webhook_e_valida(request.headers, request.args):
        logger.warning("Webhook do Mercado Pago recebido com assinatura inválida.")
        return jsonify({"erro": "Assinatura inválida."}), 401

    payload = request.get_json(silent=True) or {}
    tipo = payload.get("type") or request.args.get("type")
    dados_evento = payload.get("data", {})
    recurso_id = dados_evento.get("id") or request.args.get("data.id")

    if not recurso_id:
        # Mercado Pago às vezes envia um "ping" de teste sem dados reais.
        return jsonify({"status": "ignorado"}), 200

    if tipo == "subscription_preapproval" or tipo == "preapproval":
        _processar_atualizacao_preapproval(recurso_id)
    elif tipo == "payment":
        _processar_atualizacao_pagamento(recurso_id)
    else:
        logger.info("Webhook Mercado Pago com tipo não tratado: %s", tipo)

    # O Mercado Pago espera um 200/201 rápido — se demorarmos ou
    # respondermos erro, ele tenta reenviar a notificação depois.
    return jsonify({"status": "recebido"}), 200


def _processar_atualizacao_preapproval(preapproval_id: str) -> None:
    detalhes = mercado_pago_service.buscar_preapproval(current_app, preapproval_id)
    if not detalhes:
        logger.warning("Preapproval %s não encontrada na API do Mercado Pago.", preapproval_id)
        return

    assinatura = Assinatura.query.filter_by(mercado_pago_preapproval_id=preapproval_id).first()
    if assinatura is None:
        logger.warning("Nenhuma Assinatura local associada à preapproval %s.", preapproval_id)
        return

    status_mp = detalhes.get("status")
    novo_status = mercado_pago_service.MAPA_STATUS_MERCADO_PAGO.get(status_mp)
    if novo_status is None:
        logger.warning("Status de preapproval desconhecido recebido do Mercado Pago: %s", status_mp)
        return

    assinatura.status = StatusAssinatura(novo_status)
    if assinatura.status == StatusAssinatura.APROVADA:
        if assinatura.data_inicio is None:
            assinatura.data_inicio = datetime.utcnow()
        # Assinatura mensal: o próximo vencimento é sempre 30 dias após a
        # aprovação mais recente.
        assinatura.data_proximo_vencimento = datetime.utcnow() + timedelta(days=30)

    db.session.commit()
    logger.info("Assinatura %s atualizada para status '%s'.", assinatura.id, assinatura.status.value)


def _processar_atualizacao_pagamento(payment_id: str) -> None:
    """
    Pagamentos avulsos (cada cobrança mensal gera um "payment" vinculado
    à preapproval). Usamos isso principalmente para renovar a data de
    vencimento quando uma cobrança recorrente é aprovada.
    """
    detalhes = mercado_pago_service.buscar_pagamento(current_app, payment_id)
    if not detalhes:
        return

    preapproval_id = (
        detalhes.get("metadata", {}).get("preapproval_id")
        or detalhes.get("point_of_interaction", {}).get("transaction_data", {}).get("subscription_id")
    )
    if not preapproval_id:
        return

    assinatura = Assinatura.query.filter_by(mercado_pago_preapproval_id=preapproval_id).first()
    if assinatura is None:
        return

    if detalhes.get("status") == "approved":
        assinatura.status = StatusAssinatura.APROVADA
        assinatura.data_proximo_vencimento = datetime.utcnow() + timedelta(days=30)
        db.session.commit()
        logger.info("Pagamento aprovado para assinatura %s, vencimento renovado.", assinatura.id)

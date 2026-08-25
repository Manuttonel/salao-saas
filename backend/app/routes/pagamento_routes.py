# -*- coding: utf-8 -*-
"""
Rotas de pagamento: criação e consulta da assinatura mensal do salão na
plataforma, via Mercado Pago.

O fluxo completo:
  1. Dono chama POST /api/pagamentos/assinaturas/<salao_id> -> criamos a
     Assinatura no nosso banco (status=pendente) e a preapproval no
     Mercado Pago, devolvendo a URL de checkout.
  2. Dono é redirecionado para essa URL, insere o cartão e autoriza.
  3. Mercado Pago chama nosso webhook (app/routes/webhook_routes.py)
     avisando que o status mudou -> atualizamos a Assinatura para
     "aprovada" e definimos a próxima data de vencimento.
"""

from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, current_app

from app.extensions import db
from app.models.usuario import PapelUsuario
from app.models.salao import Salao
from app.models.assinatura import Assinatura, StatusAssinatura
from app.routes.auth_routes import papel_requerido, usuario_logado
from app.services import mercado_pago_service

pagamento_bp = Blueprint("pagamento", __name__)


@pagamento_bp.post("/assinaturas/<salao_id>")
@papel_requerido(PapelUsuario.DONO)
def criar_assinatura(salao_id):
    dono = usuario_logado()
    salao = Salao.query.filter_by(id=salao_id, dono_id=dono.id).first()
    if salao is None:
        return jsonify({"erro": "Salão não encontrado."}), 404

    if salao.assinatura and salao.assinatura.status == StatusAssinatura.APROVADA:
        return jsonify({"erro": "Este salão já possui uma assinatura ativa."}), 409

    try:
        resultado_mp = mercado_pago_service.criar_assinatura_recorrente(
            current_app, salao, email_pagador=dono.email
        )
    except RuntimeError as erro:
        return jsonify({"erro": str(erro)}), 502

    if salao.assinatura is None:
        assinatura = Assinatura(
            salao_id=salao.id,
            valor_mensal=current_app.config["PLATFORM_SUBSCRIPTION_PRICE"],
        )
        db.session.add(assinatura)
    else:
        assinatura = salao.assinatura

    assinatura.mercado_pago_preapproval_id = resultado_mp["preapproval_id"]
    assinatura.status = StatusAssinatura.PENDENTE
    db.session.commit()

    return jsonify({
        "assinatura": assinatura.to_dict(),
        "checkout_url": resultado_mp["init_point"],
    }), 201


@pagamento_bp.get("/assinaturas/<salao_id>")
@papel_requerido(PapelUsuario.DONO)
def obter_assinatura(salao_id):
    dono = usuario_logado()
    salao = Salao.query.filter_by(id=salao_id, dono_id=dono.id).first()
    if salao is None:
        return jsonify({"erro": "Salão não encontrado."}), 404

    if salao.assinatura is None:
        return jsonify({"erro": "Este salão ainda não possui assinatura."}), 404

    return jsonify(salao.assinatura.to_dict()), 200


@pagamento_bp.post("/assinaturas/<salao_id>/cancelar")
@papel_requerido(PapelUsuario.DONO)
def cancelar_assinatura(salao_id):
    dono = usuario_logado()
    salao = Salao.query.filter_by(id=salao_id, dono_id=dono.id).first()
    if salao is None or salao.assinatura is None:
        return jsonify({"erro": "Assinatura não encontrada."}), 404

    if salao.assinatura.mercado_pago_preapproval_id:
        mercado_pago_service.cancelar_assinatura(
            current_app, salao.assinatura.mercado_pago_preapproval_id
        )

    salao.assinatura.status = StatusAssinatura.CANCELADA
    db.session.commit()

    return jsonify(salao.assinatura.to_dict()), 200

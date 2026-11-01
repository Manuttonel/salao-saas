# -*- coding: utf-8 -*-
"""
Controle de clientes (CRM) do salão: cadastro, busca, ficha com
observações e histórico de atendimentos.

Só dono/administradores do salão acessam. As fichas são por salão — o
mesmo telefone pode existir em salões diferentes, cada um com as suas
anotações.
"""

from flask import Blueprint, request, jsonify
from sqlalchemy import func, or_

from app.extensions import db
from app.models.cliente import Cliente
from app.models.agendamento import Agendamento, StatusAgendamento
from app.routes.auth_routes import PAPEIS_ADMIN, papel_requerido, usuario_logado
from app.routes.salao_routes import salao_administrado_ou_none
from app.services.cliente_service import normalizar_telefone

cliente_bp = Blueprint("cliente", __name__)


def _ficha_do_admin(cliente_id, usuario):
    ficha = db.session.get(Cliente, cliente_id)
    if ficha is not None and ficha.salao is not None and ficha.salao.eh_administrador(usuario):
        return ficha
    return None


@cliente_bp.get("/")
@papel_requerido(*PAPEIS_ADMIN)
def listar_clientes():
    """Lista as fichas do salão com total de atendimentos e último atendimento. ?salao_id=&busca="""
    usuario = usuario_logado()
    salao_id = request.args.get("salao_id")
    if not salao_id or salao_administrado_ou_none(salao_id, usuario) is None:
        return jsonify({"erro": "Informe um salao_id válido."}), 400

    query = Cliente.query.filter_by(salao_id=salao_id, ativo=True)
    busca = (request.args.get("busca") or "").strip()
    if busca:
        digitos = normalizar_telefone(busca) if any(c.isdigit() for c in busca) else ""
        filtros = [Cliente.nome.ilike(f"%{busca}%"), Cliente.email.ilike(f"%{busca}%")]
        if digitos:
            filtros.append(Cliente.telefone.contains(digitos[-8:]))
        query = query.filter(or_(*filtros))

    fichas = query.all()
    ids = [f.id for f in fichas]
    estatisticas = {}
    if ids:
        linhas = (
            db.session.query(
                Agendamento.cliente_id,
                func.count(Agendamento.id),
                func.max(Agendamento.inicio),
            )
            .filter(Agendamento.cliente_id.in_(ids), Agendamento.status == StatusAgendamento.CONCLUIDO)
            .group_by(Agendamento.cliente_id)
            .all()
        )
        estatisticas = {cid: (total, ultimo) for cid, total, ultimo in linhas}

    resposta = []
    for ficha in fichas:
        total, ultimo = estatisticas.get(ficha.id, (0, None))
        item = ficha.to_dict()
        item["total_atendimentos"] = total
        item["ultimo_atendimento"] = ultimo.isoformat() if ultimo else None
        resposta.append(item)

    resposta.sort(key=lambda c: (c["nome"] or "").lower())
    return jsonify(resposta), 200


@cliente_bp.post("/")
@papel_requerido(*PAPEIS_ADMIN)
def criar_cliente():
    usuario = usuario_logado()
    dados = request.get_json(silent=True) or {}

    salao = salao_administrado_ou_none(dados.get("salao_id", ""), usuario)
    if salao is None:
        return jsonify({"erro": "Informe um salao_id válido."}), 400

    nome = (dados.get("nome") or "").strip()
    telefone = normalizar_telefone(dados.get("telefone"))
    if not nome or len(telefone) < 12:
        return jsonify({"erro": "Informe o nome e o telefone com DDD."}), 400

    existente = Cliente.query.filter_by(salao_id=salao.id, telefone=telefone).first()
    if existente is not None:
        return jsonify({"erro": f"Já existe um cliente com este telefone: {existente.nome_exibicao}."}), 409

    ficha = Cliente(
        salao_id=salao.id, nome=nome, telefone=telefone, origem="manual",
        email=(dados.get("email") or "").strip().lower() or None,
        observacoes=(dados.get("observacoes") or "").strip() or None,
    )
    db.session.add(ficha)
    db.session.commit()
    return jsonify(ficha.to_dict()), 201


@cliente_bp.get("/<cliente_id>")
@papel_requerido(*PAPEIS_ADMIN)
def obter_cliente(cliente_id):
    """Ficha completa com o histórico de agendamentos."""
    ficha = _ficha_do_admin(cliente_id, usuario_logado())
    if ficha is None:
        return jsonify({"erro": "Cliente não encontrado."}), 404

    historico = (
        Agendamento.query.filter_by(cliente_id=ficha.id)
        .order_by(Agendamento.inicio.desc()).limit(50).all()
    )
    resposta = ficha.to_dict()
    resposta["historico"] = [a.to_dict() for a in historico]
    return jsonify(resposta), 200


@cliente_bp.put("/<cliente_id>")
@papel_requerido(*PAPEIS_ADMIN)
def atualizar_cliente(cliente_id):
    ficha = _ficha_do_admin(cliente_id, usuario_logado())
    if ficha is None:
        return jsonify({"erro": "Cliente não encontrado."}), 404

    dados = request.get_json(silent=True) or {}
    if (dados.get("nome") or "").strip():
        ficha.nome = dados["nome"].strip()
    if "telefone" in dados:
        telefone = normalizar_telefone(dados["telefone"])
        if len(telefone) < 12:
            return jsonify({"erro": "Telefone inválido."}), 400
        repetido = Cliente.query.filter(
            Cliente.salao_id == ficha.salao_id, Cliente.telefone == telefone, Cliente.id != ficha.id
        ).first()
        if repetido is not None:
            return jsonify({"erro": "Outro cliente já usa este telefone."}), 409
        ficha.telefone = telefone
    if "email" in dados:
        ficha.email = (dados["email"] or "").strip().lower() or None
    if "observacoes" in dados:
        ficha.observacoes = (dados["observacoes"] or "").strip() or None
    if "aceita_notificacoes_whatsapp" in dados:
        ficha.aceita_notificacoes_whatsapp = bool(dados["aceita_notificacoes_whatsapp"])

    db.session.commit()
    return jsonify(ficha.to_dict()), 200


@cliente_bp.delete("/<cliente_id>")
@papel_requerido(*PAPEIS_ADMIN)
def remover_cliente(cliente_id):
    """Arquiva a ficha (o histórico de agendamentos é preservado)."""
    ficha = _ficha_do_admin(cliente_id, usuario_logado())
    if ficha is None:
        return jsonify({"erro": "Cliente não encontrado."}), 404
    ficha.ativo = False
    db.session.commit()
    return jsonify({"status": "removido"}), 200

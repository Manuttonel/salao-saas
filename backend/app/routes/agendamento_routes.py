# -*- coding: utf-8 -*-
"""
Rotas de agendamento: consulta de horários livres, SOLICITAÇÃO de horário,
resposta do salão (aceitar/recusar), listagem e cancelamento.

Fluxo (veja app/models/agendamento.py):

    cliente  -> POST /                 cria uma solicitação PENDENTE
    admin    -> POST /<id>/aceitar     vira CONFIRMADO (e bloqueia o horário)
    admin    -> POST /<id>/recusar     vira RECUSADO

Só a confirmação segura o horário, então o ponto delicado é o ACEITE: dois
administradores podem tentar aceitar pedidos do mesmo horário ao mesmo
tempo. Por isso `aceitar_agendamento()` trava a linha do profissional no
banco (SELECT ... FOR UPDATE) antes de checar conflito e gravar.
"""

from datetime import datetime, date as date_type, timedelta

from flask import Blueprint, request, jsonify, current_app

from app.extensions import db
from app.models.usuario import PapelUsuario
from app.models.salao import Salao, Servico
from app.models.profissional import Profissional
from app.models.cliente import Cliente
from app.models.agendamento import Agendamento, StatusAgendamento
from app.routes.auth_routes import (
    PAPEIS_ADMIN, papel_requerido, usuario_logado, resposta_se_assinatura_vencida,
)
from app.services import agendador_service, whatsapp_service
from app.services.cliente_service import obter_ou_criar_cliente

agendamento_bp = Blueprint("agendamento", __name__)

STATUS_ATIVOS = (StatusAgendamento.PENDENTE, StatusAgendamento.CONFIRMADO)


def _agendamento_do_admin(agendamento_id, usuario):
    """Agendamento pedido, se o usuário administra o salão dele; senão None."""
    agendamento = db.session.get(Agendamento, agendamento_id)
    if agendamento is not None and agendamento.salao.eh_administrador(usuario):
        return agendamento
    return None


# ---------------------------------------------------------------------------
# Horários livres (público)
# ---------------------------------------------------------------------------

@agendamento_bp.get("/horarios-disponiveis")
def horarios_disponiveis():
    """
    Query params: salao_id, servico_id, data (YYYY-MM-DD) e, opcional,
    profissional_id (sem ele, junta todos os profissionais).
    Resposta: {"horarios": [iso...], "detalhes": [{"inicio", "profissional_id"}]}
    """
    salao_id = request.args.get("salao_id")
    profissional_id = request.args.get("profissional_id")
    servico_id = request.args.get("servico_id")
    data_str = request.args.get("data")

    if not all([salao_id, servico_id, data_str]):
        return jsonify({"erro": "Informe salao_id, servico_id e data (YYYY-MM-DD)."}), 400

    salao = db.session.get(Salao, salao_id)
    servico = db.session.get(Servico, servico_id)
    if not salao or not servico or servico.salao_id != salao.id:
        return jsonify({"erro": "Salão ou procedimento não encontrado."}), 404

    try:
        dia = date_type.fromisoformat(data_str)
    except ValueError:
        return jsonify({"erro": "Data inválida, use o formato YYYY-MM-DD."}), 400

    if profissional_id:
        profissional = db.session.get(Profissional, profissional_id)
        if not profissional or profissional.salao_id != salao.id:
            return jsonify({"erro": "Profissional não encontrado."}), 404
        livres = [(s, profissional.id)
                  for s in agendador_service.obter_horarios_disponiveis(salao, profissional, servico, dia)]
    else:
        livres = agendador_service.obter_horarios_qualquer_profissional(salao, servico, dia)

    return jsonify({
        "horarios": [slot.isoformat() for slot, _ in livres],
        "detalhes": [{"inicio": slot.isoformat(), "profissional_id": pid} for slot, pid in livres],
    }), 200


# ---------------------------------------------------------------------------
# Cliente: solicitar horário
# ---------------------------------------------------------------------------

@agendamento_bp.post("/")
@papel_requerido(PapelUsuario.CLIENTE)
def solicitar_agendamento():
    """
    O cliente SOLICITA um horário. Nasce PENDENTE, não bloqueia a agenda, e
    avisa os administradores. O profissional é opcional ("qualquer um").
    """
    usuario = usuario_logado()
    dados = request.get_json(silent=True) or {}

    faltando = [c for c in ["salao_id", "servico_id", "inicio"] if not dados.get(c)]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios faltando: {', '.join(faltando)}"}), 400

    salao = db.session.get(Salao, dados["salao_id"])
    servico = db.session.get(Servico, dados["servico_id"])
    if not salao or not servico or servico.salao_id != salao.id or not servico.ativo:
        return jsonify({"erro": "Salão ou procedimento inválido."}), 404

    try:
        inicio = datetime.fromisoformat(dados["inicio"]).replace(tzinfo=None)
    except ValueError:
        return jsonify({"erro": "'inicio' deve estar em formato ISO 8601."}), 400

    if dados.get("profissional_id"):
        profissional = Profissional.query.filter_by(
            id=dados["profissional_id"], salao_id=salao.id, ativo=True
        ).first()
        if profissional is None:
            return jsonify({"erro": "Profissional inválido para este salão."}), 404
    else:
        profissional = agendador_service.escolher_profissional_livre(salao, servico, inicio)
        if profissional is None:
            return jsonify({"erro": "Nenhum profissional livre neste horário."}), 409

    try:
        fim = agendador_service.validar_e_montar_agendamento(salao, profissional, servico, inicio)
    except ValueError as erro:
        return jsonify({"erro": str(erro)}), 409

    ficha = obter_ou_criar_cliente(salao.id, usuario=usuario, origem="app")

    # Evita o mesmo cliente pedir duas vezes o mesmo horário (duplo clique).
    ja_pediu = Agendamento.query.filter(
        Agendamento.cliente_id == ficha.id,
        Agendamento.status.in_(STATUS_ATIVOS),
        Agendamento.inicio < fim,
        Agendamento.fim > inicio,
    ).first()
    if ja_pediu is not None:
        db.session.rollback()
        return jsonify({"erro": "Você já tem uma solicitação ou horário nesse período."}), 409

    agendamento = Agendamento(
        cliente_id=ficha.id, profissional_id=profissional.id, salao_id=salao.id,
        servico_id=servico.id, inicio=inicio, fim=fim,
        status=StatusAgendamento.PENDENTE, origem="web",
        observacoes=(dados.get("observacoes") or "").strip()[:500] or None,
    )
    db.session.add(agendamento)
    db.session.commit()

    app = current_app._get_current_object()
    whatsapp_service.enviar_solicitacao_recebida(app, agendamento)
    whatsapp_service.notificar_admins_nova_solicitacao(app, agendamento)

    return jsonify(agendamento.to_dict()), 201


# ---------------------------------------------------------------------------
# Administrador: responder solicitações e agendar manualmente
# ---------------------------------------------------------------------------

@agendamento_bp.post("/<agendamento_id>/aceitar")
@papel_requerido(*PAPEIS_ADMIN)
def aceitar_agendamento(agendamento_id):
    """Confirma a solicitação: o horário passa a ficar indisponível para os outros clientes."""
    usuario = usuario_logado()
    agendamento = _agendamento_do_admin(agendamento_id, usuario)
    if agendamento is None:
        return jsonify({"erro": "Solicitação não encontrada."}), 404
    bloqueio = resposta_se_assinatura_vencida(agendamento.salao)
    if bloqueio:
        return bloqueio

    dados = request.get_json(silent=True) or {}
    profissional_id = dados.get("profissional_id") or agendamento.profissional_id

    # Trava o profissional: dois aceites simultâneos ficam em fila.
    profissional = (
        Profissional.query.filter_by(id=profissional_id, salao_id=agendamento.salao_id, ativo=True)
        .with_for_update().first()
    )
    if profissional is None:
        db.session.rollback()
        return jsonify({"erro": "Profissional inválido."}), 404

    db.session.refresh(agendamento)
    if agendamento.status != StatusAgendamento.PENDENTE:
        db.session.rollback()
        return jsonify({"erro": "Esta solicitação já foi respondida."}), 409

    try:
        agendador_service.validar_e_montar_agendamento(
            agendamento.salao, profissional, agendamento.servico, agendamento.inicio,
            agendamento_id_excluir=agendamento.id,
        )
    except ValueError as erro:
        db.session.rollback()
        return jsonify({"erro": f"Não foi possível aceitar: {erro}"}), 409

    agendamento.profissional_id = profissional.id
    agendamento.status = StatusAgendamento.CONFIRMADO
    agendamento.respondido_por_id = usuario.id
    agendamento.respondido_em = datetime.now()
    db.session.commit()

    whatsapp_service.enviar_confirmacao_agendamento(current_app._get_current_object(), agendamento)
    return jsonify(agendamento.to_dict()), 200


@agendamento_bp.post("/<agendamento_id>/recusar")
@papel_requerido(*PAPEIS_ADMIN)
def recusar_agendamento(agendamento_id):
    usuario = usuario_logado()
    agendamento = _agendamento_do_admin(agendamento_id, usuario)
    if agendamento is None:
        return jsonify({"erro": "Solicitação não encontrada."}), 404
    if agendamento.status != StatusAgendamento.PENDENTE:
        return jsonify({"erro": "Esta solicitação já foi respondida."}), 409

    dados = request.get_json(silent=True) or {}
    agendamento.status = StatusAgendamento.RECUSADO
    agendamento.motivo_recusa = (dados.get("motivo") or "").strip()[:300] or None
    agendamento.respondido_por_id = usuario.id
    agendamento.respondido_em = datetime.now()
    db.session.commit()

    whatsapp_service.enviar_recusa_agendamento(current_app._get_current_object(), agendamento)
    return jsonify(agendamento.to_dict()), 200


@agendamento_bp.post("/manual")
@papel_requerido(*PAPEIS_ADMIN)
def agendar_manualmente():
    """O administrador marca direto na agenda (cliente que ligou ou veio ao balcão): já nasce CONFIRMADO."""
    usuario = usuario_logado()
    dados = request.get_json(silent=True) or {}

    faltando = [c for c in ["cliente_id", "profissional_id", "servico_id", "inicio"] if not dados.get(c)]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios faltando: {', '.join(faltando)}"}), 400

    ficha = db.session.get(Cliente, dados["cliente_id"])
    if ficha is None or ficha.salao_id is None:
        return jsonify({"erro": "Cliente não encontrado."}), 404
    salao = db.session.get(Salao, ficha.salao_id)
    if not salao.eh_administrador(usuario):
        return jsonify({"erro": "Cliente não encontrado."}), 404
    bloqueio = resposta_se_assinatura_vencida(salao)
    if bloqueio:
        return bloqueio

    servico = db.session.get(Servico, dados["servico_id"])
    if not servico or servico.salao_id != salao.id:
        return jsonify({"erro": "Procedimento inválido."}), 404
    try:
        inicio = datetime.fromisoformat(dados["inicio"]).replace(tzinfo=None)
    except ValueError:
        return jsonify({"erro": "'inicio' deve estar em formato ISO 8601."}), 400

    profissional = (
        Profissional.query.filter_by(id=dados["profissional_id"], salao_id=salao.id, ativo=True)
        .with_for_update().first()
    )
    if profissional is None:
        db.session.rollback()
        return jsonify({"erro": "Profissional inválido."}), 404

    try:
        fim = agendador_service.validar_e_montar_agendamento(salao, profissional, servico, inicio)
    except ValueError as erro:
        db.session.rollback()
        return jsonify({"erro": str(erro)}), 409

    agendamento = Agendamento(
        cliente_id=ficha.id, profissional_id=profissional.id, salao_id=salao.id,
        servico_id=servico.id, inicio=inicio, fim=fim,
        status=StatusAgendamento.CONFIRMADO, origem="manual",
        observacoes=(dados.get("observacoes") or "").strip()[:500] or None,
        respondido_por_id=usuario.id, respondido_em=datetime.now(),
    )
    db.session.add(agendamento)
    db.session.commit()

    whatsapp_service.enviar_confirmacao_agendamento(current_app._get_current_object(), agendamento)
    return jsonify(agendamento.to_dict()), 201


@agendamento_bp.post("/<agendamento_id>/concluir")
@papel_requerido(PapelUsuario.PROFISSIONAL, *PAPEIS_ADMIN)
def concluir_agendamento(agendamento_id):
    usuario = usuario_logado()
    agendamento = db.session.get(Agendamento, agendamento_id)
    if agendamento is None:
        return jsonify({"erro": "Agendamento não encontrado."}), 404

    pode = (
        agendamento.salao.eh_administrador(usuario)
        or (usuario.papel == PapelUsuario.PROFISSIONAL and usuario.perfil_profissional
            and agendamento.profissional_id == usuario.perfil_profissional.id)
    )
    if not pode:
        return jsonify({"erro": "Sem permissão."}), 403
    if agendamento.status != StatusAgendamento.CONFIRMADO:
        return jsonify({"erro": "Só é possível concluir um horário confirmado."}), 409

    agendamento.status = StatusAgendamento.CONCLUIDO
    db.session.commit()
    return jsonify(agendamento.to_dict()), 200


# ---------------------------------------------------------------------------
# Listagem e cancelamento
# ---------------------------------------------------------------------------

@agendamento_bp.get("/")
@papel_requerido(PapelUsuario.CLIENTE, PapelUsuario.PROFISSIONAL, *PAPEIS_ADMIN)
def listar_agendamentos():
    """
    Agendamentos conforme o papel: cliente vê os seus (em qualquer salão),
    profissional vê os dele, administrador vê os do salão.
    Filtros: ?salao_id=, ?status=pendente,confirmado, ?data=YYYY-MM-DD, ?futuros=1
    """
    usuario = usuario_logado()
    query = Agendamento.query

    if usuario.papel == PapelUsuario.CLIENTE:
        query = query.join(Cliente, Agendamento.cliente_id == Cliente.id).filter(
            Cliente.usuario_id == usuario.id
        )
    elif usuario.papel == PapelUsuario.PROFISSIONAL:
        perfil = usuario.perfil_profissional
        if perfil is None:
            return jsonify([]), 200
        bloqueio = resposta_se_assinatura_vencida(perfil.salao)
        if bloqueio:
            return bloqueio
        query = query.filter_by(profissional_id=perfil.id)
    else:
        saloes = {s.id: s for s in usuario.saloes_administrados()}
        salao_id = request.args.get("salao_id") or (next(iter(saloes), None))
        if salao_id not in saloes:
            return jsonify({"erro": "Salão não pertence a este usuário."}), 403
        bloqueio = resposta_se_assinatura_vencida(saloes[salao_id])
        if bloqueio:
            return bloqueio
        query = query.filter(Agendamento.salao_id == salao_id)

    status_param = request.args.get("status")
    if status_param:
        try:
            query = query.filter(Agendamento.status.in_([StatusAgendamento(s) for s in status_param.split(",")]))
        except ValueError:
            return jsonify({"erro": "Status inválido."}), 400

    data_str = request.args.get("data")
    if data_str:
        try:
            dia = date_type.fromisoformat(data_str)
        except ValueError:
            return jsonify({"erro": "Data inválida, use o formato YYYY-MM-DD."}), 400
        query = query.filter(Agendamento.inicio >= datetime.combine(dia, datetime.min.time()),
                             Agendamento.inicio < datetime.combine(dia + timedelta(days=1), datetime.min.time()))

    if request.args.get("futuros"):
        query = query.filter(Agendamento.fim >= datetime.now())

    agendamentos = query.order_by(Agendamento.inicio.asc()).limit(500).all()
    return jsonify([a.to_dict() for a in agendamentos]), 200


@agendamento_bp.post("/<agendamento_id>/cancelar")
@papel_requerido(PapelUsuario.CLIENTE, PapelUsuario.PROFISSIONAL, *PAPEIS_ADMIN)
def cancelar_agendamento(agendamento_id):
    usuario = usuario_logado()
    agendamento = db.session.get(Agendamento, agendamento_id)
    if agendamento is None:
        return jsonify({"erro": "Agendamento não encontrado."}), 404

    eh_cliente = (usuario.papel == PapelUsuario.CLIENTE and agendamento.cliente.usuario_id == usuario.id)
    eh_profissional = (usuario.papel == PapelUsuario.PROFISSIONAL and usuario.perfil_profissional
                       and agendamento.profissional_id == usuario.perfil_profissional.id)
    eh_admin = agendamento.salao.eh_administrador(usuario)
    if not (eh_cliente or eh_profissional or eh_admin):
        return jsonify({"erro": "Sem permissão para cancelar este agendamento."}), 403

    if agendamento.status not in STATUS_ATIVOS:
        return jsonify({"erro": "Este agendamento não pode mais ser cancelado."}), 409

    estava_confirmado = agendamento.status == StatusAgendamento.CONFIRMADO
    agendamento.status = StatusAgendamento.CANCELADO
    db.session.commit()

    # Se foi o salão quem desmarcou um horário já confirmado, o cliente precisa saber.
    if estava_confirmado and not eh_cliente:
        whatsapp_service.enviar_cancelamento_agendamento(current_app._get_current_object(), agendamento)

    return jsonify(agendamento.to_dict()), 200

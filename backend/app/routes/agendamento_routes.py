# -*- coding: utf-8 -*-
"""
Rotas de agendamento: consulta de horários livres, criação, listagem e
cancelamento de agendamentos.

O ponto mais delicado aqui é evitar que dois clientes reservem o mesmo
horário do mesmo profissional ao clicar "agendar" quase ao mesmo tempo
(condição de corrida). Para isso, `criar_agendamento()`:
  1. Trava a linha do Profissional no banco (`SELECT ... FOR UPDATE`),
     o que serializa requisições concorrentes para o MESMO profissional
     (requisições para profissionais diferentes continuam paralelas).
  2. Só então checa conflito de horário e insere o novo Agendamento.
  3. Faz commit, liberando a trava.
"""

from datetime import datetime, date as date_type

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models.usuario import PapelUsuario
from app.models.salao import Salao, Servico
from app.models.profissional import Profissional
from app.models.agendamento import Agendamento, StatusAgendamento
from app.routes.auth_routes import papel_requerido, usuario_logado, resposta_se_assinatura_vencida
from app.services import agendador_service, whatsapp_service

agendamento_bp = Blueprint("agendamento", __name__)


@agendamento_bp.get("/horarios-disponiveis")
def horarios_disponiveis():
    """
    Consulta pública (cliente não logado pode ver antes de decidir se
    cria conta). Espera query params: salao_id, profissional_id,
    servico_id, data (YYYY-MM-DD).
    """
    salao_id = request.args.get("salao_id")
    profissional_id = request.args.get("profissional_id")
    servico_id = request.args.get("servico_id")
    data_str = request.args.get("data")

    if not all([salao_id, profissional_id, servico_id, data_str]):
        return jsonify({
            "erro": "Informe salao_id, profissional_id, servico_id e data (YYYY-MM-DD)."
        }), 400

    salao = db.session.get(Salao, salao_id)
    profissional = db.session.get(Profissional, profissional_id)
    servico = db.session.get(Servico, servico_id)
    if not (salao and profissional and servico):
        return jsonify({"erro": "Salão, profissional ou serviço não encontrado."}), 404

    try:
        dia = date_type.fromisoformat(data_str)
    except ValueError:
        return jsonify({"erro": "Data inválida, use o formato YYYY-MM-DD."}), 400

    slots = agendador_service.obter_horarios_disponiveis(salao, profissional, servico, dia)
    return jsonify({"horarios": [slot.isoformat() for slot in slots]}), 200


@agendamento_bp.post("/")
@papel_requerido(PapelUsuario.CLIENTE)
def criar_agendamento():
    cliente_usuario = usuario_logado()
    cliente = cliente_usuario.perfil_cliente
    dados = request.get_json(silent=True) or {}

    campos_obrigatorios = ["salao_id", "profissional_id", "servico_id", "inicio"]
    faltando = [c for c in campos_obrigatorios if not dados.get(c)]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios faltando: {', '.join(faltando)}"}), 400

    salao = db.session.get(Salao, dados["salao_id"])
    servico = db.session.get(Servico, dados["servico_id"])
    if not salao or not servico or servico.salao_id != salao.id:
        return jsonify({"erro": "Salão ou serviço inválido."}), 404

    try:
        inicio = datetime.fromisoformat(dados["inicio"])
    except ValueError:
        return jsonify({"erro": "'inicio' deve estar em formato ISO 8601."}), 400

    # --- Trava a linha do profissional para evitar corrida de agendamento ---
    profissional = (
        Profissional.query.filter_by(id=dados["profissional_id"], salao_id=salao.id)
        .with_for_update()
        .first()
    )
    if profissional is None:
        return jsonify({"erro": "Profissional inválido para este salão."}), 404

    try:
        fim = agendador_service.validar_e_montar_agendamento(salao, profissional, servico, inicio)
    except ValueError as erro:
        db.session.rollback()
        return jsonify({"erro": str(erro)}), 409

    agendamento = Agendamento(
        cliente_id=cliente.id,
        profissional_id=profissional.id,
        salao_id=salao.id,
        servico_id=servico.id,
        inicio=inicio,
        fim=fim,
        status=StatusAgendamento.CONFIRMADO,
        observacoes=dados.get("observacoes"),
    )
    db.session.add(agendamento)
    db.session.commit()

    from flask import current_app
    whatsapp_service.enviar_confirmacao_agendamento(current_app, agendamento)

    return jsonify(agendamento.to_dict()), 201


@agendamento_bp.get("/")
@papel_requerido(PapelUsuario.CLIENTE, PapelUsuario.PROFISSIONAL, PapelUsuario.DONO)
def listar_agendamentos():
    """
    Lista os agendamentos filtrados de acordo com o papel do usuário
    logado: cliente vê os seus, profissional vê os que são com ele, e
    dono vê os do(s) salão(ões) dele (pode filtrar por salao_id).
    """
    usuario = usuario_logado()
    query = Agendamento.query

    if usuario.papel == PapelUsuario.CLIENTE:
        # Cliente final sempre enxerga a própria agenda, mesmo que o
        # salão esteja com a assinatura da plataforma vencida.
        query = query.filter_by(cliente_id=usuario.perfil_cliente.id)
    elif usuario.papel == PapelUsuario.PROFISSIONAL:
        bloqueio = resposta_se_assinatura_vencida(usuario.perfil_profissional.salao)
        if bloqueio:
            return bloqueio
        query = query.filter_by(profissional_id=usuario.perfil_profissional.id)
    elif usuario.papel == PapelUsuario.DONO:
        salao_ids = [s.id for s in usuario.saloes]
        salao_id_filtro = request.args.get("salao_id")
        if salao_id_filtro:
            if salao_id_filtro not in salao_ids:
                return jsonify({"erro": "Salão não pertence a este dono."}), 403
            salao_ids = [salao_id_filtro]
            salao_filtrado = next(s for s in usuario.saloes if s.id == salao_id_filtro)
            bloqueio = resposta_se_assinatura_vencida(salao_filtrado)
            if bloqueio:
                return bloqueio
        query = query.filter(Agendamento.salao_id.in_(salao_ids))

    data_str = request.args.get("data")
    if data_str:
        try:
            dia = date_type.fromisoformat(data_str)
            query = query.filter(db.func.date(Agendamento.inicio) == dia)
        except ValueError:
            return jsonify({"erro": "Data inválida, use o formato YYYY-MM-DD."}), 400

    agendamentos = query.order_by(Agendamento.inicio.asc()).all()
    return jsonify([a.to_dict() for a in agendamentos]), 200


@agendamento_bp.post("/<agendamento_id>/cancelar")
@papel_requerido(PapelUsuario.CLIENTE, PapelUsuario.PROFISSIONAL, PapelUsuario.DONO)
def cancelar_agendamento(agendamento_id):
    usuario = usuario_logado()
    agendamento = db.session.get(Agendamento, agendamento_id)
    if agendamento is None:
        return jsonify({"erro": "Agendamento não encontrado."}), 404

    pode_cancelar = (
        (usuario.papel == PapelUsuario.CLIENTE and agendamento.cliente_id == usuario.perfil_cliente.id)
        or (usuario.papel == PapelUsuario.PROFISSIONAL and agendamento.profissional_id == usuario.perfil_profissional.id)
        or (usuario.papel == PapelUsuario.DONO and agendamento.salao.dono_id == usuario.id)
    )
    if not pode_cancelar:
        return jsonify({"erro": "Sem permissão para cancelar este agendamento."}), 403

    if agendamento.status == StatusAgendamento.CANCELADO:
        return jsonify({"erro": "Este agendamento já está cancelado."}), 409

    agendamento.status = StatusAgendamento.CANCELADO
    db.session.commit()

    return jsonify(agendamento.to_dict()), 200

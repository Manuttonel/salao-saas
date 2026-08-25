# -*- coding: utf-8 -*-
"""
Rotas de gestão do salão: cadastro do salão, profissionais e serviços.

Regras de acesso:
  - Criar/editar salão, cadastrar profissionais e serviços: só o DONO
    dono daquele salão específico.
  - Listar salões e seus serviços: público (cliente final precisa ver
    isso sem estar logado, para escolher onde agendar).
  - Listar profissionais de um salão: público (cliente escolhe com quem
    agendar).
"""

from datetime import datetime

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models.usuario import Usuario, PapelUsuario
from app.models.salao import Salao, Servico
from app.models.profissional import Profissional, Indisponibilidade
from app.routes.auth_routes import papel_requerido, usuario_logado, resposta_se_assinatura_vencida

salao_bp = Blueprint("salao", __name__)


def _salao_do_dono_ou_404(salao_id: str, dono: Usuario):
    """Busca um salão garantindo que pertence ao dono logado, senão retorna None."""
    return Salao.query.filter_by(id=salao_id, dono_id=dono.id).first()


# ---------------------------------------------------------------------------
# Salão
# ---------------------------------------------------------------------------

@salao_bp.get("/")
def listar_saloes():
    """Lista pública de salões cadastrados (para o cliente escolher)."""
    saloes = Salao.query.all()
    return jsonify([s.to_dict() for s in saloes]), 200


@salao_bp.get("/<salao_id>")
def obter_salao(salao_id):
    salao = db.session.get(Salao, salao_id)
    if salao is None:
        return jsonify({"erro": "Salão não encontrado."}), 404
    return jsonify(salao.to_dict()), 200


@salao_bp.post("/")
@papel_requerido(PapelUsuario.DONO)
def criar_salao():
    dono = usuario_logado()
    dados = request.get_json(silent=True) or {}

    campos_obrigatorios = ["nome", "telefone", "horario_abertura", "horario_fechamento"]
    faltando = [c for c in campos_obrigatorios if not dados.get(c)]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios faltando: {', '.join(faltando)}"}), 400

    try:
        abertura = datetime.strptime(dados["horario_abertura"], "%H:%M").time()
        fechamento = datetime.strptime(dados["horario_fechamento"], "%H:%M").time()
    except ValueError:
        return jsonify({"erro": "Horários devem estar no formato HH:MM."}), 400

    salao = Salao(
        dono_id=dono.id,
        nome=dados["nome"].strip(),
        telefone=dados["telefone"].strip(),
        endereco=dados.get("endereco", "").strip() or None,
        horario_abertura=abertura,
        horario_fechamento=fechamento,
        dias_funcionamento=dados.get("dias_funcionamento", [0, 1, 2, 3, 4, 5]),
    )
    db.session.add(salao)
    db.session.commit()

    return jsonify(salao.to_dict()), 201


@salao_bp.put("/<salao_id>")
@papel_requerido(PapelUsuario.DONO)
def atualizar_salao(salao_id):
    dono = usuario_logado()
    salao = _salao_do_dono_ou_404(salao_id, dono)
    if salao is None:
        return jsonify({"erro": "Salão não encontrado."}), 404
    bloqueio = resposta_se_assinatura_vencida(salao)
    if bloqueio:
        return bloqueio

    dados = request.get_json(silent=True) or {}
    if "nome" in dados:
        salao.nome = dados["nome"].strip()
    if "telefone" in dados:
        salao.telefone = dados["telefone"].strip()
    if "endereco" in dados:
        salao.endereco = dados["endereco"].strip() or None
    if "horario_abertura" in dados:
        salao.horario_abertura = datetime.strptime(dados["horario_abertura"], "%H:%M").time()
    if "horario_fechamento" in dados:
        salao.horario_fechamento = datetime.strptime(dados["horario_fechamento"], "%H:%M").time()
    if "dias_funcionamento" in dados:
        salao.dias_funcionamento = dados["dias_funcionamento"]

    db.session.commit()
    return jsonify(salao.to_dict()), 200


# ---------------------------------------------------------------------------
# Serviços do salão (ex.: Corte, Barba, Escova...)
# ---------------------------------------------------------------------------

@salao_bp.get("/<salao_id>/servicos")
def listar_servicos(salao_id):
    servicos = Servico.query.filter_by(salao_id=salao_id, ativo=True).all()
    return jsonify([s.to_dict() for s in servicos]), 200


@salao_bp.post("/<salao_id>/servicos")
@papel_requerido(PapelUsuario.DONO)
def criar_servico(salao_id):
    dono = usuario_logado()
    salao = _salao_do_dono_ou_404(salao_id, dono)
    if salao is None:
        return jsonify({"erro": "Salão não encontrado."}), 404
    bloqueio = resposta_se_assinatura_vencida(salao)
    if bloqueio:
        return bloqueio

    dados = request.get_json(silent=True) or {}
    campos_obrigatorios = ["nome", "duracao_minutos", "preco"]
    faltando = [c for c in campos_obrigatorios if dados.get(c) in (None, "")]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios faltando: {', '.join(faltando)}"}), 400

    servico = Servico(
        salao_id=salao.id,
        nome=dados["nome"].strip(),
        duracao_minutos=int(dados["duracao_minutos"]),
        preco=dados["preco"],
    )
    db.session.add(servico)
    db.session.commit()
    return jsonify(servico.to_dict()), 201


@salao_bp.put("/servicos/<servico_id>")
@papel_requerido(PapelUsuario.DONO)
def atualizar_servico(servico_id):
    dono = usuario_logado()
    servico = db.session.get(Servico, servico_id)
    if servico is None or servico.salao.dono_id != dono.id:
        return jsonify({"erro": "Serviço não encontrado."}), 404
    bloqueio = resposta_se_assinatura_vencida(servico.salao)
    if bloqueio:
        return bloqueio

    dados = request.get_json(silent=True) or {}
    if "nome" in dados:
        servico.nome = dados["nome"].strip()
    if "duracao_minutos" in dados:
        servico.duracao_minutos = int(dados["duracao_minutos"])
    if "preco" in dados:
        servico.preco = dados["preco"]
    if "ativo" in dados:
        servico.ativo = bool(dados["ativo"])

    db.session.commit()
    return jsonify(servico.to_dict()), 200


# ---------------------------------------------------------------------------
# Profissionais do salão
# ---------------------------------------------------------------------------

@salao_bp.get("/<salao_id>/profissionais")
def listar_profissionais(salao_id):
    profissionais = Profissional.query.filter_by(salao_id=salao_id, ativo=True).all()
    return jsonify([p.to_dict() for p in profissionais]), 200


@salao_bp.post("/<salao_id>/profissionais")
@papel_requerido(PapelUsuario.DONO)
def convidar_profissional(salao_id):
    """
    O dono cadastra um profissional para trabalhar no seu salão. Isso
    cria, em uma única operação, o Usuario (papel=profissional) e o
    perfil Profissional vinculado a este salão. Uma senha provisória é
    definida e deve ser trocada no primeiro acesso pelo próprio
    profissional (fluxo de troca de senha fica fora do escopo desta
    entrega, mas o endpoint de login já funciona com a senha provisória).
    """
    dono = usuario_logado()
    salao = _salao_do_dono_ou_404(salao_id, dono)
    if salao is None:
        return jsonify({"erro": "Salão não encontrado."}), 404
    bloqueio = resposta_se_assinatura_vencida(salao)
    if bloqueio:
        return bloqueio

    dados = request.get_json(silent=True) or {}
    campos_obrigatorios = ["nome", "email", "telefone", "senha_provisoria"]
    faltando = [c for c in campos_obrigatorios if not dados.get(c)]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios faltando: {', '.join(faltando)}"}), 400

    if Usuario.query.filter_by(email=dados["email"].lower().strip()).first():
        return jsonify({"erro": "Já existe uma conta com este e-mail."}), 409

    usuario = Usuario(
        nome=dados["nome"].strip(),
        email=dados["email"].lower().strip(),
        telefone=dados["telefone"].strip(),
        papel=PapelUsuario.PROFISSIONAL,
    )
    usuario.set_senha(dados["senha_provisoria"])
    db.session.add(usuario)
    db.session.flush()

    horario_inicio = None
    horario_fim = None
    if dados.get("horario_inicio"):
        horario_inicio = datetime.strptime(dados["horario_inicio"], "%H:%M").time()
    if dados.get("horario_fim"):
        horario_fim = datetime.strptime(dados["horario_fim"], "%H:%M").time()

    profissional = Profissional(
        usuario_id=usuario.id,
        salao_id=salao.id,
        especialidade=dados.get("especialidade"),
        horario_inicio=horario_inicio,
        horario_fim=horario_fim,
    )
    db.session.add(profissional)
    db.session.commit()

    return jsonify(profissional.to_dict()), 201


@salao_bp.post("/profissionais/<profissional_id>/indisponibilidades")
@papel_requerido(PapelUsuario.PROFISSIONAL, PapelUsuario.DONO)
def criar_indisponibilidade(profissional_id):
    """Profissional (ou o dono, em nome dele) marca um período como indisponível."""
    usuario = usuario_logado()
    profissional = db.session.get(Profissional, profissional_id)
    if profissional is None:
        return jsonify({"erro": "Profissional não encontrado."}), 404

    eh_o_proprio_profissional = (
        usuario.papel == PapelUsuario.PROFISSIONAL and profissional.usuario_id == usuario.id
    )
    eh_dono_do_salao = usuario.papel == PapelUsuario.DONO and profissional.salao.dono_id == usuario.id
    if not (eh_o_proprio_profissional or eh_dono_do_salao):
        return jsonify({"erro": "Sem permissão para alterar a agenda deste profissional."}), 403

    dados = request.get_json(silent=True) or {}
    try:
        inicio = datetime.fromisoformat(dados["inicio"])
        fim = datetime.fromisoformat(dados["fim"])
    except (KeyError, ValueError):
        return jsonify({"erro": "Informe 'inicio' e 'fim' em formato ISO 8601."}), 400

    if fim <= inicio:
        return jsonify({"erro": "'fim' deve ser depois de 'inicio'."}), 400

    indisponibilidade = Indisponibilidade(
        profissional_id=profissional.id,
        inicio=inicio,
        fim=fim,
        motivo=dados.get("motivo"),
    )
    db.session.add(indisponibilidade)
    db.session.commit()

    return jsonify(indisponibilidade.to_dict()), 201

# -*- coding: utf-8 -*-
"""
Rotas de autenticação: registro, login e dados do usuário logado.

Também define aqui os decorators de controle de acesso por papel
(`papel_requerido`) e a função `usuario_logado()`, usados por TODAS as
outras rotas protegidas do sistema (salao_routes, agendamento_routes,
pagamento_routes) para restringir cada endpoint ao(s) papel(is) correto(s).
"""

from functools import wraps

from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
)

from app.extensions import db
from app.models.usuario import Usuario, PapelUsuario
from app.models.profissional import Profissional
from app.models.cliente import Cliente

auth_bp = Blueprint("auth", __name__)


def usuario_logado() -> Usuario:
    """Busca no banco o Usuario correspondente ao token JWT da requisição atual."""
    usuario_id = get_jwt_identity()
    return db.session.get(Usuario, usuario_id)


def papel_requerido(*papeis_permitidos: PapelUsuario):
    """
    Decorator que combina @jwt_required() com uma checagem de papel.

    Uso:
        @agendamento_bp.post("/")
        @papel_requerido(PapelUsuario.CLIENTE)
        def criar_agendamento():
            ...

    Se o usuário do token não tiver um dos papéis permitidos, devolve 403.
    """

    def decorador(funcao):
        @wraps(funcao)
        @jwt_required()
        def wrapper(*args, **kwargs):
            usuario = usuario_logado()
            if usuario is None or not usuario.ativo:
                return jsonify({"erro": "Usuário não encontrado ou inativo."}), 401
            if usuario.papel not in papeis_permitidos:
                return jsonify({"erro": "Você não tem permissão para acessar este recurso."}), 403
            return funcao(*args, **kwargs)

        return wrapper

    return decorador


def resposta_se_assinatura_vencida(salao):
    """
    Checagem usada nas rotas de PAINEL do dono/profissional (gestão do
    salão, cadastro de profissionais/serviços, agenda interna). Se a
    assinatura da plataforma estiver vencida, devolve uma resposta 402
    (Payment Required) pronta para ser retornada pela rota; caso
    contrário devolve None e a rota segue normalmente.

    Importante: isso NUNCA é aplicado às rotas públicas usadas pelo
    cliente final (listar salões/serviços/profissionais, consultar
    horários livres, criar agendamento) — o cliente continua enxergando
    e usando a agenda mesmo com o salão inadimplente, só o painel
    administrativo é bloqueado.
    """
    if not salao.esta_com_acesso_liberado():
        return jsonify({
            "erro": "Assinatura da plataforma vencida. Regularize o pagamento "
                    "para voltar a acessar o painel do salão."
        }), 402
    return None


@auth_bp.post("/registrar")
def registrar():
    """
    Cria um novo usuário. O campo "papel" define o tipo de conta:
      - "dono": cria só o Usuario (o salão é criado depois, em
        POST /api/saloes).
      - "cliente": cria o Usuario + o perfil Cliente.
      - "profissional": NÃO é criado por aqui — profissionais são
        convidados pelo dono do salão (veja POST /api/saloes/<id>/profissionais),
        que já cria o Usuario e o perfil Profissional vinculado ao salão.
    """
    dados = request.get_json(silent=True) or {}

    campos_obrigatorios = ["nome", "email", "senha", "telefone", "papel"]
    faltando = [campo for campo in campos_obrigatorios if not dados.get(campo)]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios faltando: {', '.join(faltando)}"}), 400

    papel = dados["papel"]
    if papel not in (PapelUsuario.DONO.value, PapelUsuario.CLIENTE.value):
        return jsonify({
            "erro": "Papel inválido para autocadastro. Use 'dono' ou 'cliente'. "
                    "Profissionais são cadastrados pelo dono do salão."
        }), 400

    if Usuario.query.filter_by(email=dados["email"].lower().strip()).first():
        return jsonify({"erro": "Já existe uma conta com este e-mail."}), 409

    usuario = Usuario(
        nome=dados["nome"].strip(),
        email=dados["email"].lower().strip(),
        telefone=dados["telefone"].strip(),
        papel=PapelUsuario(papel),
    )
    usuario.set_senha(dados["senha"])

    db.session.add(usuario)
    db.session.flush()  # garante que usuario.id já existe antes de criar o perfil

    if usuario.papel == PapelUsuario.CLIENTE:
        db.session.add(Cliente(usuario_id=usuario.id))

    db.session.commit()

    token = create_access_token(identity=usuario.id)
    return jsonify({"usuario": usuario.to_dict(), "access_token": token}), 201


@auth_bp.post("/login")
def login():
    dados = request.get_json(silent=True) or {}
    email = (dados.get("email") or "").lower().strip()
    senha = dados.get("senha") or ""

    usuario = Usuario.query.filter_by(email=email).first()
    if usuario is None or not usuario.checar_senha(senha):
        return jsonify({"erro": "E-mail ou senha inválidos."}), 401

    if not usuario.ativo:
        return jsonify({"erro": "Esta conta está desativada."}), 403

    token = create_access_token(identity=usuario.id)

    resposta = usuario.to_dict()
    # Inclui o id do perfil específico (profissional/cliente) para o
    # frontend já saber para qual dashboard redirecionar.
    if usuario.papel == PapelUsuario.PROFISSIONAL and usuario.perfil_profissional:
        resposta["profissional_id"] = usuario.perfil_profissional.id
        resposta["salao_id"] = usuario.perfil_profissional.salao_id
    if usuario.papel == PapelUsuario.CLIENTE and usuario.perfil_cliente:
        resposta["cliente_id"] = usuario.perfil_cliente.id
    if usuario.papel == PapelUsuario.DONO:
        resposta["saloes"] = [s.id for s in usuario.saloes]

    return jsonify({"usuario": resposta, "access_token": token}), 200


@auth_bp.get("/me")
@jwt_required()
def me():
    usuario = usuario_logado()
    if usuario is None:
        return jsonify({"erro": "Usuário não encontrado."}), 404
    return jsonify(usuario.to_dict()), 200

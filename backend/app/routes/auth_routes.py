# -*- coding: utf-8 -*-
"""
Rotas de autenticação: registro, login, dados do usuário logado e
preferência de tema.

Também define os decorators de controle de acesso por papel
(`papel_requerido`) e a função `usuario_logado()`, usados por TODAS as
outras rotas protegidas do sistema.
"""

import re
from functools import wraps

from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
)

from app.extensions import db
from app.models.usuario import Usuario, PapelUsuario, TEMAS_VALIDOS

auth_bp = Blueprint("auth", __name__)

# Quem pode usar o painel de gestão do salão.
PAPEIS_ADMIN = (PapelUsuario.DONO, PapelUsuario.ADMINISTRADOR)


def usuario_logado() -> Usuario:
    """Busca no banco o Usuario correspondente ao token JWT da requisição atual."""
    usuario_id = get_jwt_identity()
    return db.session.get(Usuario, usuario_id)


def papel_requerido(*papeis_permitidos: PapelUsuario):
    """
    Decorator que combina @jwt_required() com uma checagem de papel.
    Se o usuário não tiver um dos papéis permitidos, devolve 403.
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
    Nas rotas de PAINEL (gestão do salão), devolve 402 se a assinatura da
    plataforma estiver vencida; caso contrário None. Nunca é aplicada às
    rotas públicas do cliente final: ele continua vendo e pedindo horários.
    """
    if not salao.esta_com_acesso_liberado():
        return jsonify({
            "erro": "Assinatura da plataforma vencida. Regularize o pagamento "
                    "para voltar a acessar o painel do salão."
        }), 402
    return None


def montar_resposta_usuario(usuario: Usuario) -> dict:
    """Dados do usuário + ids que o frontend precisa para escolher o painel certo."""
    resposta = usuario.to_dict()
    if usuario.papel == PapelUsuario.PROFISSIONAL and usuario.perfil_profissional:
        resposta["profissional_id"] = usuario.perfil_profissional.id
        resposta["salao_id"] = usuario.perfil_profissional.salao_id
    if usuario.papel in PAPEIS_ADMIN:
        resposta["saloes"] = [s.id for s in usuario.saloes_administrados()]
    return resposta


@auth_bp.post("/registrar")
def registrar():
    """
    Autocadastro. Papéis aceitos: "dono" (cria o salão depois, em
    POST /api/saloes) e "cliente". Administradores e profissionais são
    cadastrados pelo dono do salão, nunca por aqui.
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
                    "Administradores e profissionais são cadastrados pelo dono do salão."
        }), 400

    if Usuario.query.filter_by(email=dados["email"].lower().strip()).first():
        return jsonify({"erro": "Já existe uma conta com este e-mail."}), 409

    usuario = Usuario(
        nome=dados["nome"].strip(),
        email=dados["email"].lower().strip(),
        telefone=dados["telefone"].strip(),
        papel=PapelUsuario(papel),
    )
    # Mantém o tema que a pessoa já estava usando antes de criar a conta.
    if dados.get("tema") in TEMAS_VALIDOS:
        usuario.tema = dados["tema"]
    usuario.set_senha(dados["senha"])

    db.session.add(usuario)
    # A ficha de cliente (CRM) é criada por salão, no primeiro pedido de horário.
    db.session.commit()

    token = create_access_token(identity=usuario.id)
    return jsonify({"usuario": montar_resposta_usuario(usuario), "access_token": token}), 201


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
    return jsonify({"usuario": montar_resposta_usuario(usuario), "access_token": token}), 200


@auth_bp.get("/me")
@jwt_required()
def me():
    usuario = usuario_logado()
    if usuario is None:
        return jsonify({"erro": "Usuário não encontrado."}), 404
    return jsonify(montar_resposta_usuario(usuario)), 200


@auth_bp.patch("/preferencias")
@jwt_required()
def atualizar_preferencias():
    """Salva o tema escolhido ("unisex", "glow" ou "dark") e a cor do tema unisex."""
    usuario = usuario_logado()
    dados = request.get_json(silent=True) or {}

    if "tema" in dados:
        if dados["tema"] not in TEMAS_VALIDOS:
            return jsonify({"erro": f"Tema inválido. Use: {', '.join(TEMAS_VALIDOS)}."}), 400
        usuario.tema = dados["tema"]

    if "cor_primaria" in dados:
        cor = dados["cor_primaria"]
        if cor is not None and not re.fullmatch(r"#[0-9a-fA-F]{6}", cor):
            return jsonify({"erro": "Cor inválida. Use o formato #RRGGBB."}), 400
        usuario.cor_primaria = cor.lower() if cor else None

    db.session.commit()
    return jsonify(montar_resposta_usuario(usuario)), 200

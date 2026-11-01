# -*- coding: utf-8 -*-
"""
Rotas de gestão do salão: dados do salão, calendário de dias disponíveis,
procedimentos, profissionais, administradores e simulador do bot.

Regras de acesso:
  - Gestão (editar salão, procedimentos, equipe, calendário): dono OU
    administradores daquele salão.
  - Gerenciar administradores: só o dono.
  - Consultas que o cliente final precisa (listar salões, procedimentos,
    profissionais e o calendário): públicas.
"""

import re
from datetime import datetime, date

from flask import Blueprint, request, jsonify, current_app

from app.extensions import db
from app.models.usuario import Usuario, PapelUsuario
from app.models.salao import (
    Salao, Servico, DiaAgenda, SalaoAdministrador,
    CATEGORIAS_SERVICO, NOME_SERVICO_AVALIACAO, DURACAO_PADRAO_AVALIACAO,
)
from app.models.profissional import Profissional, Indisponibilidade
from app.routes.auth_routes import (
    PAPEIS_ADMIN, papel_requerido, usuario_logado, resposta_se_assinatura_vencida,
)
from app.services import agendador_service, bot_whatsapp_service

salao_bp = Blueprint("salao", __name__)


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def salao_administrado_ou_none(salao_id: str, usuario: Usuario):
    """Salão pedido, se o usuário for dono/administrador dele; senão None."""
    salao = db.session.get(Salao, salao_id)
    if salao is not None and salao.eh_administrador(usuario):
        return salao
    return None


def _hora(texto: str):
    return datetime.strptime(texto, "%H:%M").time()


def preparar_salao_novo(salao: Salao, dono: Usuario) -> None:
    """
    Cria o que todo salão precisa para já funcionar: o procedimento
    "Marcar Avaliação" e um profissional padrão (o próprio dono), para que
    o salão pequeno possa receber pedidos sem cadastrar equipe.
    """
    db.session.add(Servico(
        salao_id=salao.id, nome=NOME_SERVICO_AVALIACAO, categoria="avaliacao",
        descricao="Conversa rápida para avaliar o que você precisa.",
        duracao_minutos=DURACAO_PADRAO_AVALIACAO, preco=0, eh_avaliacao=True,
    ))
    db.session.add(Profissional(salao_id=salao.id, nome=dono.nome))


def _validar_servico(dados: dict, parcial: bool = False):
    """Valida e normaliza os campos de um procedimento. Devolve (campos, erro)."""
    campos = {}
    if "nome" in dados or not parcial:
        nome = (dados.get("nome") or "").strip()
        if not nome:
            return None, "Informe o nome do procedimento."
        campos["nome"] = nome
    if "categoria" in dados or not parcial:
        categoria = dados.get("categoria") or "outros"
        if categoria not in CATEGORIAS_SERVICO or categoria == "avaliacao":
            return None, "Categoria inválida. Use: cabelo, unhas, estetica, barba ou outros."
        campos["categoria"] = categoria
    if "duracao_minutos" in dados or not parcial:
        try:
            duracao = int(dados.get("duracao_minutos"))
        except (TypeError, ValueError):
            return None, "Duração inválida."
        if not 5 <= duracao <= 600:
            return None, "A duração deve ficar entre 5 e 600 minutos."
        campos["duracao_minutos"] = duracao
    if "preco" in dados or not parcial:
        try:
            preco = float(dados.get("preco") if dados.get("preco") not in (None, "") else 0)
        except (TypeError, ValueError):
            return None, "Preço inválido."
        if preco < 0:
            return None, "O preço não pode ser negativo."
        campos["preco"] = preco
    if "descricao" in dados:
        campos["descricao"] = (dados.get("descricao") or "").strip()[:300] or None
    return campos, None


# ---------------------------------------------------------------------------
# Salão
# ---------------------------------------------------------------------------

@salao_bp.get("/")
def listar_saloes():
    """Lista pública de salões cadastrados (para o cliente escolher)."""
    saloes = Salao.query.order_by(Salao.nome).all()
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
        abertura = _hora(dados["horario_abertura"])
        fechamento = _hora(dados["horario_fechamento"])
    except ValueError:
        return jsonify({"erro": "Horários devem estar no formato HH:MM."}), 400
    if abertura >= fechamento:
        return jsonify({"erro": "O horário de abertura deve ser antes do fechamento."}), 400

    salao = Salao(
        dono_id=dono.id,
        nome=dados["nome"].strip(),
        telefone=dados["telefone"].strip(),
        endereco=(dados.get("endereco") or "").strip() or None,
        horario_abertura=abertura,
        horario_fechamento=fechamento,
        dias_funcionamento=dados.get("dias_funcionamento", [0, 1, 2, 3, 4, 5]),
    )
    db.session.add(salao)
    db.session.flush()
    preparar_salao_novo(salao, dono)
    db.session.commit()

    return jsonify(salao.to_dict()), 201


@salao_bp.put("/<salao_id>")
@papel_requerido(*PAPEIS_ADMIN)
def atualizar_salao(salao_id):
    salao = salao_administrado_ou_none(salao_id, usuario_logado())
    if salao is None:
        return jsonify({"erro": "Salão não encontrado."}), 404
    bloqueio = resposta_se_assinatura_vencida(salao)
    if bloqueio:
        return bloqueio

    dados = request.get_json(silent=True) or {}
    try:
        if "horario_abertura" in dados:
            salao.horario_abertura = _hora(dados["horario_abertura"])
        if "horario_fechamento" in dados:
            salao.horario_fechamento = _hora(dados["horario_fechamento"])
    except ValueError:
        return jsonify({"erro": "Horários devem estar no formato HH:MM."}), 400
    if salao.horario_abertura >= salao.horario_fechamento:
        db.session.rollback()
        return jsonify({"erro": "O horário de abertura deve ser antes do fechamento."}), 400

    if "nome" in dados and dados["nome"].strip():
        salao.nome = dados["nome"].strip()
    if "telefone" in dados and dados["telefone"].strip():
        salao.telefone = dados["telefone"].strip()
    if "endereco" in dados:
        salao.endereco = (dados["endereco"] or "").strip() or None
    if "dias_funcionamento" in dados:
        salao.dias_funcionamento = sorted({int(d) for d in dados["dias_funcionamento"] if 0 <= int(d) <= 6})
    if "somente_dias_marcados" in dados:
        salao.somente_dias_marcados = bool(dados["somente_dias_marcados"])
    if "whatsapp_instancia" in dados:
        instancia = (dados["whatsapp_instancia"] or "").strip()
        if instancia and not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", instancia):
            return jsonify({"erro": "Nome da instância: use apenas letras, números, - e _."}), 400
        salao.whatsapp_instancia = instancia or None

    db.session.commit()
    return jsonify(salao.to_dict()), 200


# ---------------------------------------------------------------------------
# Calendário: dias em que o salão atende
# ---------------------------------------------------------------------------

@salao_bp.get("/<salao_id>/calendario")
def calendario(salao_id):
    """
    Situação de cada dia de um mês (?mes=YYYY-MM). Público: o cliente usa
    para só poder clicar em dias disponíveis; o painel do administrador usa
    o mesmo retorno para mostrar o que foi marcado.
    """
    salao = db.session.get(Salao, salao_id)
    if salao is None:
        return jsonify({"erro": "Salão não encontrado."}), 404

    mes_texto = request.args.get("mes") or date.today().strftime("%Y-%m")
    try:
        ano, mes = (int(parte) for parte in mes_texto.split("-"))
        date(ano, mes, 1)
    except ValueError:
        return jsonify({"erro": "Use o formato ?mes=YYYY-MM."}), 400

    return jsonify({"mes": mes_texto, "dias": agendador_service.calendario_do_mes(salao, ano, mes)}), 200


@salao_bp.put("/<salao_id>/dias-agenda/<data_texto>")
@papel_requerido(*PAPEIS_ADMIN)
def marcar_dia_agenda(salao_id, data_texto):
    """Marca um dia como disponível (aberto=true, com horário opcional) ou indisponível (aberto=false)."""
    salao = salao_administrado_ou_none(salao_id, usuario_logado())
    if salao is None:
        return jsonify({"erro": "Salão não encontrado."}), 404
    bloqueio = resposta_se_assinatura_vencida(salao)
    if bloqueio:
        return bloqueio

    try:
        dia = date.fromisoformat(data_texto)
    except ValueError:
        return jsonify({"erro": "Data inválida, use YYYY-MM-DD."}), 400
    if dia < date.today():
        return jsonify({"erro": "Não é possível alterar dias que já passaram."}), 400

    dados = request.get_json(silent=True) or {}
    if "aberto" not in dados:
        return jsonify({"erro": "Informe 'aberto' (true ou false)."}), 400

    try:
        hora_inicio = _hora(dados["hora_inicio"]) if dados.get("hora_inicio") else None
        hora_fim = _hora(dados["hora_fim"]) if dados.get("hora_fim") else None
    except ValueError:
        return jsonify({"erro": "Horários devem estar no formato HH:MM."}), 400
    if hora_inicio and hora_fim and hora_inicio >= hora_fim:
        return jsonify({"erro": "O horário inicial deve ser antes do final."}), 400

    registro = DiaAgenda.query.filter_by(salao_id=salao.id, data=dia).first()
    if registro is None:
        registro = DiaAgenda(salao_id=salao.id, data=dia)
        db.session.add(registro)
    registro.aberto = bool(dados["aberto"])
    registro.hora_inicio = hora_inicio if registro.aberto else None
    registro.hora_fim = hora_fim if registro.aberto else None
    registro.motivo = (dados.get("motivo") or "").strip()[:120] or None
    db.session.commit()
    return jsonify(registro.to_dict()), 200


@salao_bp.delete("/<salao_id>/dias-agenda/<data_texto>")
@papel_requerido(*PAPEIS_ADMIN)
def limpar_dia_agenda(salao_id, data_texto):
    """Remove a exceção do dia: ele volta a seguir a regra geral do salão."""
    salao = salao_administrado_ou_none(salao_id, usuario_logado())
    if salao is None:
        return jsonify({"erro": "Salão não encontrado."}), 404
    try:
        dia = date.fromisoformat(data_texto)
    except ValueError:
        return jsonify({"erro": "Data inválida, use YYYY-MM-DD."}), 400

    DiaAgenda.query.filter_by(salao_id=salao.id, data=dia).delete()
    db.session.commit()
    return jsonify({"status": "removido"}), 200


# ---------------------------------------------------------------------------
# Procedimentos (serviços)
# ---------------------------------------------------------------------------

@salao_bp.get("/<salao_id>/servicos")
def listar_servicos(salao_id):
    """Procedimentos ativos. A avaliação vem primeiro, depois por categoria e nome."""
    servicos = (
        Servico.query.filter_by(salao_id=salao_id, ativo=True)
        .order_by(Servico.eh_avaliacao.desc(), Servico.categoria, Servico.nome)
        .all()
    )
    return jsonify([s.to_dict() for s in servicos]), 200


@salao_bp.post("/<salao_id>/servicos")
@papel_requerido(*PAPEIS_ADMIN)
def criar_servico(salao_id):
    salao = salao_administrado_ou_none(salao_id, usuario_logado())
    if salao is None:
        return jsonify({"erro": "Salão não encontrado."}), 404
    bloqueio = resposta_se_assinatura_vencida(salao)
    if bloqueio:
        return bloqueio

    campos, erro = _validar_servico(request.get_json(silent=True) or {})
    if erro:
        return jsonify({"erro": erro}), 400

    servico = Servico(salao_id=salao.id, **campos)
    db.session.add(servico)
    db.session.commit()
    return jsonify(servico.to_dict()), 201


@salao_bp.put("/servicos/<servico_id>")
@papel_requerido(*PAPEIS_ADMIN)
def atualizar_servico(servico_id):
    servico = db.session.get(Servico, servico_id)
    if servico is None or not servico.salao.eh_administrador(usuario_logado()):
        return jsonify({"erro": "Procedimento não encontrado."}), 404
    bloqueio = resposta_se_assinatura_vencida(servico.salao)
    if bloqueio:
        return bloqueio

    dados = request.get_json(silent=True) or {}
    if servico.eh_avaliacao:
        dados.pop("categoria", None)  # a avaliação tem categoria fixa
    campos, erro = _validar_servico(dados, parcial=True)
    if erro:
        return jsonify({"erro": erro}), 400

    for chave, valor in campos.items():
        setattr(servico, chave, valor)
    if "ativo" in dados:
        servico.ativo = bool(dados["ativo"])

    db.session.commit()
    return jsonify(servico.to_dict()), 200


@salao_bp.delete("/servicos/<servico_id>")
@papel_requerido(*PAPEIS_ADMIN)
def remover_servico(servico_id):
    """Desativa o procedimento (o histórico de agendamentos antigos é preservado)."""
    servico = db.session.get(Servico, servico_id)
    if servico is None or not servico.salao.eh_administrador(usuario_logado()):
        return jsonify({"erro": "Procedimento não encontrado."}), 404
    servico.ativo = False
    db.session.commit()
    return jsonify({"status": "removido"}), 200


# ---------------------------------------------------------------------------
# Profissionais
# ---------------------------------------------------------------------------

@salao_bp.get("/<salao_id>/profissionais")
def listar_profissionais(salao_id):
    profissionais = Profissional.query.filter_by(salao_id=salao_id, ativo=True).all()
    return jsonify([p.to_dict() for p in profissionais]), 200


@salao_bp.post("/<salao_id>/profissionais")
@papel_requerido(*PAPEIS_ADMIN)
def criar_profissional(salao_id):
    """
    Cadastra quem atende. Só o nome é obrigatório. Se informar e-mail e
    senha provisória, a pessoa também ganha um login para ver a própria agenda.
    """
    salao = salao_administrado_ou_none(salao_id, usuario_logado())
    if salao is None:
        return jsonify({"erro": "Salão não encontrado."}), 404
    bloqueio = resposta_se_assinatura_vencida(salao)
    if bloqueio:
        return bloqueio

    dados = request.get_json(silent=True) or {}
    nome = (dados.get("nome") or "").strip()
    if not nome:
        return jsonify({"erro": "Informe o nome do profissional."}), 400

    usuario = None
    email = (dados.get("email") or "").lower().strip()
    if email:
        if not dados.get("senha_provisoria") or not dados.get("telefone"):
            return jsonify({"erro": "Para criar um login, informe e-mail, telefone e senha provisória."}), 400
        if Usuario.query.filter_by(email=email).first():
            return jsonify({"erro": "Já existe uma conta com este e-mail."}), 409
        usuario = Usuario(nome=nome, email=email, telefone=dados["telefone"].strip(),
                          papel=PapelUsuario.PROFISSIONAL)
        usuario.set_senha(dados["senha_provisoria"])
        db.session.add(usuario)
        db.session.flush()

    try:
        horario_inicio = _hora(dados["horario_inicio"]) if dados.get("horario_inicio") else None
        horario_fim = _hora(dados["horario_fim"]) if dados.get("horario_fim") else None
    except ValueError:
        db.session.rollback()
        return jsonify({"erro": "Horários devem estar no formato HH:MM."}), 400

    profissional = Profissional(
        usuario_id=usuario.id if usuario else None,
        salao_id=salao.id,
        nome=nome,
        especialidade=(dados.get("especialidade") or "").strip() or None,
        horario_inicio=horario_inicio,
        horario_fim=horario_fim,
    )
    db.session.add(profissional)
    db.session.commit()
    return jsonify(profissional.to_dict()), 201


@salao_bp.put("/profissionais/<profissional_id>")
@papel_requerido(*PAPEIS_ADMIN)
def atualizar_profissional(profissional_id):
    profissional = db.session.get(Profissional, profissional_id)
    if profissional is None or not profissional.salao.eh_administrador(usuario_logado()):
        return jsonify({"erro": "Profissional não encontrado."}), 404

    dados = request.get_json(silent=True) or {}
    try:
        if "horario_inicio" in dados:
            profissional.horario_inicio = _hora(dados["horario_inicio"]) if dados["horario_inicio"] else None
        if "horario_fim" in dados:
            profissional.horario_fim = _hora(dados["horario_fim"]) if dados["horario_fim"] else None
    except ValueError:
        return jsonify({"erro": "Horários devem estar no formato HH:MM."}), 400
    if dados.get("nome", "").strip():
        profissional.nome = dados["nome"].strip()
    if "especialidade" in dados:
        profissional.especialidade = (dados["especialidade"] or "").strip() or None
    if "ativo" in dados:
        profissional.ativo = bool(dados["ativo"])

    db.session.commit()
    return jsonify(profissional.to_dict()), 200


def _pode_gerir_agenda_do(usuario: Usuario, profissional: Profissional) -> bool:
    if usuario.papel == PapelUsuario.PROFISSIONAL:
        return profissional.usuario_id == usuario.id
    return usuario.eh_admin() and profissional.salao.eh_administrador(usuario)


@salao_bp.get("/profissionais/<profissional_id>/indisponibilidades")
@papel_requerido(PapelUsuario.PROFISSIONAL, *PAPEIS_ADMIN)
def listar_indisponibilidades(profissional_id):
    usuario = usuario_logado()
    profissional = db.session.get(Profissional, profissional_id)
    if profissional is None or not _pode_gerir_agenda_do(usuario, profissional):
        return jsonify({"erro": "Profissional não encontrado."}), 404

    itens = (
        Indisponibilidade.query.filter(
            Indisponibilidade.profissional_id == profissional.id,
            Indisponibilidade.fim >= datetime.now(),
        )
        .order_by(Indisponibilidade.inicio)
        .all()
    )
    return jsonify([i.to_dict() for i in itens]), 200


@salao_bp.post("/profissionais/<profissional_id>/indisponibilidades")
@papel_requerido(PapelUsuario.PROFISSIONAL, *PAPEIS_ADMIN)
def criar_indisponibilidade(profissional_id):
    """Profissional (ou um administrador, em nome dele) bloqueia um período."""
    usuario = usuario_logado()
    profissional = db.session.get(Profissional, profissional_id)
    if profissional is None:
        return jsonify({"erro": "Profissional não encontrado."}), 404
    if not _pode_gerir_agenda_do(usuario, profissional):
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
        profissional_id=profissional.id, inicio=inicio, fim=fim, motivo=dados.get("motivo"),
    )
    db.session.add(indisponibilidade)
    db.session.commit()
    return jsonify(indisponibilidade.to_dict()), 201


@salao_bp.delete("/indisponibilidades/<indisponibilidade_id>")
@papel_requerido(PapelUsuario.PROFISSIONAL, *PAPEIS_ADMIN)
def remover_indisponibilidade(indisponibilidade_id):
    item = db.session.get(Indisponibilidade, indisponibilidade_id)
    if item is None or not _pode_gerir_agenda_do(usuario_logado(), item.profissional):
        return jsonify({"erro": "Bloqueio não encontrado."}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({"status": "removido"}), 200


# ---------------------------------------------------------------------------
# Administradores do salão (vários usuários gerenciando o mesmo salão)
# ---------------------------------------------------------------------------

@salao_bp.get("/<salao_id>/administradores")
@papel_requerido(*PAPEIS_ADMIN)
def listar_administradores(salao_id):
    salao = salao_administrado_ou_none(salao_id, usuario_logado())
    if salao is None:
        return jsonify({"erro": "Salão não encontrado."}), 404

    itens = [{
        "id": None, "usuario_id": salao.dono.id, "nome": salao.dono.nome,
        "email": salao.dono.email, "telefone": salao.dono.telefone, "eh_dono": True,
    }]
    itens += [v.to_dict() for v in salao.administradores_vinculos]
    return jsonify(itens), 200


@salao_bp.post("/<salao_id>/administradores")
@papel_requerido(PapelUsuario.DONO)
def adicionar_administrador(salao_id):
    """O dono cria o acesso de mais um administrador (ex.: recepcionista)."""
    dono = usuario_logado()
    salao = db.session.get(Salao, salao_id)
    if salao is None or salao.dono_id != dono.id:
        return jsonify({"erro": "Salão não encontrado."}), 404

    dados = request.get_json(silent=True) or {}
    faltando = [c for c in ["nome", "email", "telefone", "senha_provisoria"] if not dados.get(c)]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios faltando: {', '.join(faltando)}"}), 400
    if len(dados["senha_provisoria"]) < 6:
        return jsonify({"erro": "A senha deve ter pelo menos 6 caracteres."}), 400
    if Usuario.query.filter_by(email=dados["email"].lower().strip()).first():
        return jsonify({"erro": "Já existe uma conta com este e-mail."}), 409

    usuario = Usuario(
        nome=dados["nome"].strip(), email=dados["email"].lower().strip(),
        telefone=dados["telefone"].strip(), papel=PapelUsuario.ADMINISTRADOR,
    )
    usuario.set_senha(dados["senha_provisoria"])
    db.session.add(usuario)
    db.session.flush()

    vinculo = SalaoAdministrador(salao_id=salao.id, usuario_id=usuario.id)
    db.session.add(vinculo)
    db.session.commit()
    return jsonify(vinculo.to_dict()), 201


@salao_bp.delete("/<salao_id>/administradores/<vinculo_id>")
@papel_requerido(PapelUsuario.DONO)
def remover_administrador(salao_id, vinculo_id):
    dono = usuario_logado()
    vinculo = db.session.get(SalaoAdministrador, vinculo_id)
    if vinculo is None or vinculo.salao_id != salao_id or vinculo.salao.dono_id != dono.id:
        return jsonify({"erro": "Administrador não encontrado."}), 404

    usuario = vinculo.usuario
    db.session.delete(vinculo)
    usuario.ativo = False  # a conta existia só para este salão
    db.session.commit()
    return jsonify({"status": "removido"}), 200


# ---------------------------------------------------------------------------
# Simulador do bot de WhatsApp (para testar sem celular)
# ---------------------------------------------------------------------------

@salao_bp.post("/<salao_id>/bot/simular")
@papel_requerido(*PAPEIS_ADMIN)
def simular_bot(salao_id):
    """
    Conversa com o bot como se fosse um cliente, direto do painel. As
    respostas voltam na resposta HTTP (nada é enviado ao WhatsApp), mas as
    solicitações criadas são REAIS — apareça em "Solicitações" e recuse
    depois, se for só teste.
    """
    salao = salao_administrado_ou_none(salao_id, usuario_logado())
    if salao is None:
        return jsonify({"erro": "Salão não encontrado."}), 404

    dados = request.get_json(silent=True) or {}
    respostas = bot_whatsapp_service.processar_mensagem(
        current_app._get_current_object(), salao,
        telefone=dados.get("telefone") or "5511900000000",
        texto=dados.get("texto") or "",
        nome_contato=dados.get("nome"),
    )
    return jsonify({"respostas": respostas}), 200

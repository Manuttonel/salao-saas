# -*- coding: utf-8 -*-
"""
Funções de apoio ao cadastro de clientes (CRM).

O telefone é a "chave natural" que une o mesmo cliente entre o site e o
WhatsApp, por isso ele é sempre normalizado para somente dígitos com DDI
(55 = Brasil) antes de ser salvo ou comparado.
"""

import re

from app.extensions import db
from app.models.cliente import Cliente


def normalizar_telefone(telefone: str) -> str:
    """'(11) 99999-8888' -> '5511999998888'. Número sem DDI ganha o 55."""
    digitos = re.sub(r"\D", "", telefone or "")
    if len(digitos) in (10, 11):  # DDD + número, sem código do país
        digitos = "55" + digitos
    return digitos


def obter_ou_criar_cliente(salao_id: str, telefone: str = None, nome: str = None,
                           usuario=None, origem: str = "manual") -> Cliente:
    """
    Devolve a ficha do cliente neste salão, criando se não existir.

    Ordem de busca: (1) ficha já ligada ao usuário logado; (2) ficha com o
    mesmo telefone — assim quem chamou no WhatsApp e depois criou conta no
    site continua sendo UMA pessoa só. Não faz commit: quem chama decide.
    """
    telefone_norm = normalizar_telefone(telefone or (usuario.telefone if usuario else ""))

    ficha = None
    if usuario is not None:
        ficha = Cliente.query.filter_by(salao_id=salao_id, usuario_id=usuario.id).first()
    if ficha is None and telefone_norm:
        ficha = Cliente.query.filter_by(salao_id=salao_id, telefone=telefone_norm).first()

    if ficha is None:
        ficha = Cliente(
            salao_id=salao_id,
            usuario_id=usuario.id if usuario else None,
            nome=(nome or (usuario.nome if usuario else None)),
            telefone=telefone_norm or None,
            email=usuario.email if usuario else None,
            origem=origem,
        )
        db.session.add(ficha)
        db.session.flush()
        return ficha

    # Ficha já existia: completa o que estiver faltando, sem sobrescrever.
    if usuario is not None and ficha.usuario_id is None:
        ficha.usuario_id = usuario.id
        ficha.email = ficha.email or usuario.email
    if nome and not ficha.nome:
        ficha.nome = nome
    if telefone_norm and not ficha.telefone:
        ficha.telefone = telefone_norm
    if not ficha.ativo:
        ficha.ativo = True
    return ficha

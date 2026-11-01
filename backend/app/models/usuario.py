# -*- coding: utf-8 -*-
"""
Model Usuario: tabela central de autenticação.

Todo mundo que faz login no sistema é um Usuario. O campo "papel" diz
qual é o tipo de conta:

  - dono:          criou o salão; é o único que gerencia a assinatura da
                   plataforma e os outros administradores.
  - administrador: usuário extra do salão (recepção, gerente...). Vê e
                   responde solicitações, mexe na agenda, clientes e
                   procedimentos — tudo menos assinatura/administradores.
  - profissional:  quem atende; vê a própria agenda.
  - cliente:       quem solicita horários pelo site.

Preferência visual: cada usuário escolhe o seu tema ("unisex", "glow" ou
"dark") e, no tema unisex, a cor principal. Ficam salvos aqui para
acompanhar a pessoa em qualquer dispositivo.
"""

import enum
import uuid

from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db

TEMAS_VALIDOS = ("unisex", "glow", "dark")


class PapelUsuario(str, enum.Enum):
    """Os perfis de acesso suportados pela plataforma."""

    DONO = "dono"
    ADMINISTRADOR = "administrador"
    PROFISSIONAL = "profissional"
    CLIENTE = "cliente"


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False, unique=True, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)  # formato E.164, ex: 5511999998888
    papel = db.Column(db.Enum(PapelUsuario), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    # Preferência de aparência (veja frontend/src/services/tema.js).
    tema = db.Column(db.String(20), nullable=False, default="unisex", server_default="unisex")
    cor_primaria = db.Column(db.String(7), nullable=True)  # "#RRGGBB", usada no tema unisex

    criado_em = db.Column(db.DateTime, server_default=db.func.now())
    atualizado_em = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    perfil_profissional = db.relationship(
        "Profissional", back_populates="usuario", uselist=False
    )
    # Um mesmo cliente pode ser cadastrado em vários salões: cada salão tem
    # o seu próprio registro de Cliente (a ficha dele no CRM do salão).
    fichas_cliente = db.relationship("Cliente", back_populates="usuario")
    # Salões criados por este usuário (quando é "dono").
    saloes = db.relationship("Salao", back_populates="dono", cascade="all, delete-orphan")
    # Salões em que ele foi adicionado como administrador.
    vinculos_admin = db.relationship(
        "SalaoAdministrador", back_populates="usuario", cascade="all, delete-orphan"
    )

    def set_senha(self, senha_texto_plano: str) -> None:
        """Gera e guarda o hash da senha. Nunca armazenamos a senha em texto puro."""
        self.senha_hash = generate_password_hash(senha_texto_plano)

    def checar_senha(self, senha_texto_plano: str) -> bool:
        return check_password_hash(self.senha_hash, senha_texto_plano)

    def eh_admin(self) -> bool:
        return self.papel in (PapelUsuario.DONO, PapelUsuario.ADMINISTRADOR)

    def saloes_administrados(self) -> list:
        """Salões que este usuário pode administrar (os que criou + os que foi convidado)."""
        por_id = {salao.id: salao for salao in self.saloes}
        for vinculo in self.vinculos_admin:
            por_id.setdefault(vinculo.salao_id, vinculo.salao)
        return list(por_id.values())

    def to_dict(self) -> dict:
        """Serialização segura: nunca inclui senha_hash."""
        return {
            "id": self.id,
            "nome": self.nome,
            "email": self.email,
            "telefone": self.telefone,
            "papel": self.papel.value,
            "ativo": self.ativo,
            "tema": self.tema or "unisex",
            "cor_primaria": self.cor_primaria,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None,
        }

    def __repr__(self) -> str:
        return f"<Usuario {self.email} ({self.papel.value})>"

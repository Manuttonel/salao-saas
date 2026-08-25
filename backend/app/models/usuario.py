# -*- coding: utf-8 -*-
"""
Model Usuario: tabela central de autenticação.

Todo mundo que faz login no sistema (dono do salão, profissional ou
cliente) é um Usuario. O campo "papel" diz qual é o tipo de conta, e
esse papel é usado pelos decorators de autorização (veja
app/routes/auth_routes.py) para liberar ou bloquear rotas.

Os models Profissional e Cliente têm uma relação 1-para-1 com Usuario,
guardando os dados específicos de cada papel (ex.: especialidade do
profissional, salão a que o cliente mais visita etc.).
"""

import enum
import uuid

from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class PapelUsuario(str, enum.Enum):
    """Os três perfis de acesso suportados pela plataforma."""

    DONO = "dono"
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
    criado_em = db.Column(db.DateTime, server_default=db.func.now())
    atualizado_em = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    # Relações 1-para-1 com os perfis específicos. "uselist=False" faz o
    # SQLAlchemy tratar isso como objeto único em vez de lista.
    perfil_profissional = db.relationship(
        "Profissional", back_populates="usuario", uselist=False, cascade="all, delete-orphan"
    )
    perfil_cliente = db.relationship(
        "Cliente", back_populates="usuario", uselist=False, cascade="all, delete-orphan"
    )
    # Um dono pode ter mais de um salão cadastrado na plataforma.
    saloes = db.relationship("Salao", back_populates="dono", cascade="all, delete-orphan")

    def set_senha(self, senha_texto_plano: str) -> None:
        """Gera e guarda o hash da senha. Nunca armazenamos a senha em texto puro."""
        self.senha_hash = generate_password_hash(senha_texto_plano)

    def checar_senha(self, senha_texto_plano: str) -> bool:
        return check_password_hash(self.senha_hash, senha_texto_plano)

    def to_dict(self) -> dict:
        """Serialização segura: nunca inclui senha_hash."""
        return {
            "id": self.id,
            "nome": self.nome,
            "email": self.email,
            "telefone": self.telefone,
            "papel": self.papel.value,
            "ativo": self.ativo,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None,
        }

    def __repr__(self) -> str:
        return f"<Usuario {self.email} ({self.papel.value})>"

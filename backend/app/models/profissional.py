# -*- coding: utf-8 -*-
"""
Models Profissional e Indisponibilidade.

Profissional é quem atende os clientes (cabeleireiro, manicure, barbeiro
etc.), ligado a um Salao. O profissional PODE ter login (usuario_id
preenchido) mas não precisa: em salões pequenos o administrador
simplesmente cadastra o nome de quem atende, sem criar conta.

Cada profissional pode ter horário próprio (dentro do horário do salão) e
pode ter períodos bloqueados (Indisponibilidade: almoço, folga, férias).
"""

import uuid

from app.extensions import db


class Profissional(db.Model):
    __tablename__ = "profissionais"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    usuario_id = db.Column(
        db.String(36), db.ForeignKey("usuarios.id"), nullable=True, unique=True
    )
    salao_id = db.Column(db.String(36), db.ForeignKey("saloes.id"), nullable=False)

    # Nome exibido nas agendas. Para quem tem login pode ficar vazio (usa o
    # nome do usuário).
    nome = db.Column(db.String(120), nullable=True)
    especialidade = db.Column(db.String(120), nullable=True)

    # Horário de trabalho do profissional. Se nulo, vale o do salão.
    horario_inicio = db.Column(db.Time, nullable=True)
    horario_fim = db.Column(db.Time, nullable=True)

    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, server_default=db.func.now())

    usuario = db.relationship("Usuario", back_populates="perfil_profissional")
    salao = db.relationship("Salao", back_populates="profissionais")
    agendamentos = db.relationship("Agendamento", back_populates="profissional")
    indisponibilidades = db.relationship(
        "Indisponibilidade", back_populates="profissional", cascade="all, delete-orphan"
    )

    @property
    def nome_exibicao(self) -> str:
        if self.nome:
            return self.nome
        return self.usuario.nome if self.usuario else "Profissional"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "usuario_id": self.usuario_id,
            "salao_id": self.salao_id,
            "nome": self.nome_exibicao,
            "tem_login": self.usuario_id is not None,
            "especialidade": self.especialidade,
            "horario_inicio": self.horario_inicio.strftime("%H:%M") if self.horario_inicio else None,
            "horario_fim": self.horario_fim.strftime("%H:%M") if self.horario_fim else None,
            "ativo": self.ativo,
        }


class Indisponibilidade(db.Model):
    """
    Período em que um profissional não pode receber agendamentos
    (ex.: almoço, folga, férias).
    """

    __tablename__ = "indisponibilidades"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profissional_id = db.Column(
        db.String(36), db.ForeignKey("profissionais.id"), nullable=False
    )

    inicio = db.Column(db.DateTime, nullable=False)
    fim = db.Column(db.DateTime, nullable=False)
    motivo = db.Column(db.String(255), nullable=True)

    profissional = db.relationship("Profissional", back_populates="indisponibilidades")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "profissional_id": self.profissional_id,
            "inicio": self.inicio.isoformat(),
            "fim": self.fim.isoformat(),
            "motivo": self.motivo,
        }

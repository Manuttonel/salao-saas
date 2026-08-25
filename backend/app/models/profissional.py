# -*- coding: utf-8 -*-
"""
Models Profissional e Indisponibilidade.

Profissional é o perfil de quem atende os clientes (cabeleireiro,
barbeiro etc.), ligado 1-para-1 a um Usuario (papel=profissional) e
N-para-1 a um Salao. Cada profissional pode ter um horário de trabalho
próprio (dentro do horário do salão) e pode marcar períodos como
indisponíveis (folga, almoço, férias) — a lógica de agendamento em
app/services/agendador_service.py cruza esses dados com os agendamentos
já existentes para calcular os horários realmente livres.
"""

import uuid

from app.extensions import db


class Profissional(db.Model):
    __tablename__ = "profissionais"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    usuario_id = db.Column(
        db.String(36), db.ForeignKey("usuarios.id"), nullable=False, unique=True
    )
    salao_id = db.Column(db.String(36), db.ForeignKey("saloes.id"), nullable=False)

    especialidade = db.Column(db.String(120), nullable=True)

    # Horário de trabalho do profissional. Se nulo, assume-se o horário
    # padrão do salão (ver Salao.horario_abertura/horario_fechamento).
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

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "usuario_id": self.usuario_id,
            "salao_id": self.salao_id,
            "nome": self.usuario.nome if self.usuario else None,
            "especialidade": self.especialidade,
            "horario_inicio": self.horario_inicio.strftime("%H:%M") if self.horario_inicio else None,
            "horario_fim": self.horario_fim.strftime("%H:%M") if self.horario_fim else None,
            "ativo": self.ativo,
        }


class Indisponibilidade(db.Model):
    """
    Período em que um profissional não pode receber agendamentos
    (ex.: almoço, folga, férias). Usado pela lógica de disponibilidade
    junto com os agendamentos já confirmados.
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

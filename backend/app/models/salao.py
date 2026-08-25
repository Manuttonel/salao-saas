# -*- coding: utf-8 -*-
"""
Models Salao e Servico.

Salao representa a barbearia/salão de beleza em si, pertencente a um
Usuario com papel "dono". Servico é o catálogo de serviços oferecidos
por um salão (ex.: "Corte masculino", 30 minutos, R$ 40) — a duração de
cada serviço é o que a lógica de agendamento usa para calcular o
horário de término e evitar conflitos (veja app/services/agendador_service.py).
"""

import uuid

from app.extensions import db


class Salao(db.Model):
    __tablename__ = "saloes"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dono_id = db.Column(db.String(36), db.ForeignKey("usuarios.id"), nullable=False)

    nome = db.Column(db.String(120), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    endereco = db.Column(db.String(255), nullable=True)

    # Horário de funcionamento padrão do salão (usado como base; cada
    # profissional pode ter um horário próprio dentro desta faixa —
    # veja app/models/profissional.py).
    horario_abertura = db.Column(db.Time, nullable=False)
    horario_fechamento = db.Column(db.Time, nullable=False)

    # Dias da semana em que o salão funciona, guardados como lista de
    # inteiros (0=segunda ... 6=domingo), ex.: [0,1,2,3,4,5] = seg a sáb.
    dias_funcionamento = db.Column(db.JSON, nullable=False, default=lambda: [0, 1, 2, 3, 4, 5])

    criado_em = db.Column(db.DateTime, server_default=db.func.now())

    dono = db.relationship("Usuario", back_populates="saloes")
    profissionais = db.relationship(
        "Profissional", back_populates="salao", cascade="all, delete-orphan"
    )
    servicos = db.relationship("Servico", back_populates="salao", cascade="all, delete-orphan")
    agendamentos = db.relationship("Agendamento", back_populates="salao")
    assinatura = db.relationship(
        "Assinatura", back_populates="salao", uselist=False, cascade="all, delete-orphan"
    )

    def esta_com_acesso_liberado(self) -> bool:
        """
        Regra de negócio: o painel do dono/profissionais só fica liberado
        se a assinatura da plataforma estiver em dia. Se não existir
        assinatura ainda (salão recém-criado, em período de teste) ou se
        estiver aprovada, o acesso é liberado.
        """
        if self.assinatura is None:
            return True
        return self.assinatura.esta_ativa()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "dono_id": self.dono_id,
            "nome": self.nome,
            "telefone": self.telefone,
            "endereco": self.endereco,
            "horario_abertura": self.horario_abertura.strftime("%H:%M"),
            "horario_fechamento": self.horario_fechamento.strftime("%H:%M"),
            "dias_funcionamento": self.dias_funcionamento,
            "acesso_liberado": self.esta_com_acesso_liberado(),
        }


class Servico(db.Model):
    """Um serviço oferecido pelo salão (corte, escova, barba etc.)."""

    __tablename__ = "servicos"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    salao_id = db.Column(db.String(36), db.ForeignKey("saloes.id"), nullable=False)

    nome = db.Column(db.String(120), nullable=False)
    duracao_minutos = db.Column(db.Integer, nullable=False)
    preco = db.Column(db.Numeric(10, 2), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    salao = db.relationship("Salao", back_populates="servicos")
    agendamentos = db.relationship("Agendamento", back_populates="servico")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "salao_id": self.salao_id,
            "nome": self.nome,
            "duracao_minutos": self.duracao_minutos,
            "preco": float(self.preco),
            "ativo": self.ativo,
        }

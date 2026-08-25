# -*- coding: utf-8 -*-
"""
Model Agendamento: o coração do sistema.

Representa a reserva de um Cliente com um Profissional, para um Servico
específico, dentro de um Salao. O intervalo [inicio, fim) é o que a
lógica de conflito de agenda usa: dois agendamentos do MESMO profissional
nunca podem ter intervalos que se sobrepõem (veja a validação em
app/services/agendador_service.py e a checagem final antes do INSERT em
app/routes/agendamento_routes.py).

Os campos lembrete_24h_enviado e lembrete_1h_enviado evitam que o job
do APScheduler (app/scheduler/jobs.py) envie o mesmo lembrete de
WhatsApp mais de uma vez.
"""

import enum
import uuid

from app.extensions import db


class StatusAgendamento(str, enum.Enum):
    PENDENTE = "pendente"       # criado, aguardando confirmação (se aplicável)
    CONFIRMADO = "confirmado"   # confirmado, vale a reserva de horário
    CANCELADO = "cancelado"     # cancelado por cliente, profissional ou dono
    CONCLUIDO = "concluido"     # atendimento já realizado


class Agendamento(db.Model):
    __tablename__ = "agendamentos"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    cliente_id = db.Column(db.String(36), db.ForeignKey("clientes.id"), nullable=False)
    profissional_id = db.Column(
        db.String(36), db.ForeignKey("profissionais.id"), nullable=False
    )
    salao_id = db.Column(db.String(36), db.ForeignKey("saloes.id"), nullable=False)
    servico_id = db.Column(db.String(36), db.ForeignKey("servicos.id"), nullable=False)

    inicio = db.Column(db.DateTime, nullable=False, index=True)
    fim = db.Column(db.DateTime, nullable=False)

    status = db.Column(
        db.Enum(StatusAgendamento), nullable=False, default=StatusAgendamento.CONFIRMADO
    )
    observacoes = db.Column(db.String(500), nullable=True)

    lembrete_24h_enviado = db.Column(db.Boolean, nullable=False, default=False)
    lembrete_1h_enviado = db.Column(db.Boolean, nullable=False, default=False)

    criado_em = db.Column(db.DateTime, server_default=db.func.now())
    atualizado_em = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    cliente = db.relationship("Cliente", back_populates="agendamentos")
    profissional = db.relationship("Profissional", back_populates="agendamentos")
    salao = db.relationship("Salao", back_populates="agendamentos")
    servico = db.relationship("Servico", back_populates="agendamentos")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "cliente_id": self.cliente_id,
            "cliente_nome": self.cliente.usuario.nome if self.cliente and self.cliente.usuario else None,
            "profissional_id": self.profissional_id,
            "profissional_nome": self.profissional.usuario.nome if self.profissional and self.profissional.usuario else None,
            "salao_id": self.salao_id,
            "servico_id": self.servico_id,
            "servico_nome": self.servico.nome if self.servico else None,
            "inicio": self.inicio.isoformat(),
            "fim": self.fim.isoformat(),
            "status": self.status.value,
            "observacoes": self.observacoes,
        }

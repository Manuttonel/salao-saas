# -*- coding: utf-8 -*-
"""
Model Agendamento: o coração do sistema.

Ciclo de vida de um pedido de horário:

    cliente solicita (site ou WhatsApp)  ->  PENDENTE
    administrador aceita                 ->  CONFIRMADO  (o horário passa a
                                             ficar indisponível p/ outros)
    administrador recusa                 ->  RECUSADO
    qualquer parte cancela               ->  CANCELADO
    atendimento realizado                ->  CONCLUIDO

IMPORTANTE: só CONFIRMADO e CONCLUIDO "seguram" o horário. Uma solicitação
PENDENTE ainda não bloqueia nada — vários clientes podem pedir o mesmo
horário e o administrador decide quem leva (veja
app/services/agendador_service.py, STATUS_QUE_BLOQUEIAM).

Os campos lembrete_24h_enviado e lembrete_1h_enviado evitam que o job do
APScheduler (app/scheduler/jobs.py) envie o mesmo lembrete duas vezes.
"""

import enum
import uuid

from app.extensions import db


class StatusAgendamento(str, enum.Enum):
    PENDENTE = "pendente"       # solicitação aguardando resposta do salão
    CONFIRMADO = "confirmado"   # aceita: o horário está reservado
    RECUSADO = "recusado"       # o salão não pôde atender
    CANCELADO = "cancelado"     # cancelado por cliente, profissional ou admin
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
        db.Enum(StatusAgendamento), nullable=False, default=StatusAgendamento.PENDENTE
    )
    observacoes = db.Column(db.String(500), nullable=True)

    # De onde veio o pedido: "web" (site), "whatsapp" (bot) ou "manual" (admin).
    origem = db.Column(db.String(20), nullable=False, default="web", server_default="web")

    # Resposta do salão à solicitação.
    motivo_recusa = db.Column(db.String(300), nullable=True)
    respondido_por_id = db.Column(db.String(36), db.ForeignKey("usuarios.id"), nullable=True)
    respondido_em = db.Column(db.DateTime, nullable=True)

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
    respondido_por = db.relationship("Usuario", foreign_keys=[respondido_por_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "cliente_id": self.cliente_id,
            "cliente_nome": self.cliente.nome_exibicao if self.cliente else None,
            "cliente_telefone": self.cliente.telefone_exibicao if self.cliente else None,
            "profissional_id": self.profissional_id,
            "profissional_nome": self.profissional.nome_exibicao if self.profissional else None,
            "salao_id": self.salao_id,
            "salao_nome": self.salao.nome if self.salao else None,
            "servico_id": self.servico_id,
            "servico_nome": self.servico.nome if self.servico else None,
            "servico_categoria": self.servico.categoria if self.servico else None,
            "eh_avaliacao": bool(self.servico.eh_avaliacao) if self.servico else False,
            "duracao_minutos": self.servico.duracao_minutos if self.servico else None,
            "inicio": self.inicio.isoformat(),
            "fim": self.fim.isoformat(),
            "status": self.status.value,
            "origem": self.origem,
            "observacoes": self.observacoes,
            "motivo_recusa": self.motivo_recusa,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None,
        }

# -*- coding: utf-8 -*-
"""
Model Cliente: perfil de quem agenda horários.

Ligado 1-para-1 a um Usuario (papel=cliente). Um mesmo cliente pode
agendar em salões diferentes, então não há vínculo fixo com um Salao —
o vínculo salão/cliente acontece a cada Agendamento.
"""

import uuid

from app.extensions import db


class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    usuario_id = db.Column(
        db.String(36), db.ForeignKey("usuarios.id"), nullable=False, unique=True
    )

    # Preferência de recebimento de lembretes/confirmações via WhatsApp.
    aceita_notificacoes_whatsapp = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, server_default=db.func.now())

    usuario = db.relationship("Usuario", back_populates="perfil_cliente")
    agendamentos = db.relationship("Agendamento", back_populates="cliente")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "usuario_id": self.usuario_id,
            "nome": self.usuario.nome if self.usuario else None,
            "telefone": self.usuario.telefone if self.usuario else None,
            "aceita_notificacoes_whatsapp": self.aceita_notificacoes_whatsapp,
        }

# -*- coding: utf-8 -*-
"""
Model ConversaWhatsapp: memória do bot de WhatsApp.

O bot conversa por etapas ("qual procedimento?", "qual dia?", "qual
horário?"). Como cada mensagem do cliente chega como uma requisição
separada ao webhook, precisamos guardar em que etapa cada pessoa está —
é isso que esta tabela faz: uma linha por (salão, telefone).

`estado` é a etapa atual e `dados` guarda o que já foi escolhido (id do
procedimento, dia, horário) e as listas numeradas mostradas ao cliente,
para sabermos o que "2" significa na próxima mensagem.
"""

import uuid

from app.extensions import db


class ConversaWhatsapp(db.Model):
    __tablename__ = "conversas_whatsapp"
    __table_args__ = (db.UniqueConstraint("salao_id", "telefone", name="uq_conversa_salao_telefone"),)

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    salao_id = db.Column(db.String(36), db.ForeignKey("saloes.id"), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)

    estado = db.Column(db.String(30), nullable=False, default="menu")
    dados = db.Column(db.JSON, nullable=False, default=dict)

    atualizado_em = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

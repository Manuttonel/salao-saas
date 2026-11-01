# -*- coding: utf-8 -*-
"""
Model Cliente: a FICHA do cliente dentro de um salão (o "controle de
clientes" / CRM).

Cada salão tem as suas próprias fichas. Uma ficha pode nascer de três
formas (campo `origem`):
  - "manual":   o administrador cadastrou o cliente no painel;
  - "app":      o cliente criou conta no site e fez uma solicitação;
  - "whatsapp": o cliente conversou com o bot e a ficha foi criada
                automaticamente a partir do número de telefone.

`usuario_id` só é preenchido quando o cliente tem login no site. O
telefone (somente dígitos, com DDI) é a chave usada para reconhecer o
mesmo cliente entre site e WhatsApp.
"""

import uuid

from app.extensions import db


class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    salao_id = db.Column(db.String(36), db.ForeignKey("saloes.id"), nullable=True, index=True)
    usuario_id = db.Column(db.String(36), db.ForeignKey("usuarios.id"), nullable=True)

    nome = db.Column(db.String(120), nullable=True)
    telefone = db.Column(db.String(20), nullable=True, index=True)  # só dígitos, ex: 5511999998888
    email = db.Column(db.String(160), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)  # anotações do salão (alergias, preferências...)
    origem = db.Column(db.String(20), nullable=False, default="manual", server_default="manual")

    # Preferência de recebimento de lembretes/confirmações via WhatsApp.
    aceita_notificacoes_whatsapp = db.Column(db.Boolean, nullable=False, default=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    criado_em = db.Column(db.DateTime, server_default=db.func.now())

    salao = db.relationship("Salao", back_populates="clientes")
    usuario = db.relationship("Usuario", back_populates="fichas_cliente")
    agendamentos = db.relationship("Agendamento", back_populates="cliente")

    @property
    def nome_exibicao(self) -> str:
        if self.nome:
            return self.nome
        return self.usuario.nome if self.usuario else "Cliente"

    @property
    def telefone_exibicao(self):
        if self.telefone:
            return self.telefone
        return self.usuario.telefone if self.usuario else None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "salao_id": self.salao_id,
            "usuario_id": self.usuario_id,
            "nome": self.nome_exibicao,
            "telefone": self.telefone_exibicao,
            "email": self.email or (self.usuario.email if self.usuario else None),
            "observacoes": self.observacoes,
            "origem": self.origem,
            "aceita_notificacoes_whatsapp": self.aceita_notificacoes_whatsapp,
            "ativo": self.ativo,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None,
        }

# -*- coding: utf-8 -*-
"""
Model Assinatura: cobrança recorrente do salão na plataforma (via
Mercado Pago). Cada Salao tem no máximo uma Assinatura (1-para-1).

O fluxo é:
1. Dono cria a assinatura (app/routes/pagamento_routes.py chama
   app/services/mercado_pago_service.py, que cria uma "preapproval"
   no Mercado Pago e devolve o link de pagamento).
2. Guardamos o mercado_pago_preapproval_id aqui, com status "pendente".
3. O Mercado Pago chama nosso webhook (app/routes/webhook_routes.py)
   sempre que o status muda, e nós atualizamos o campo "status" e
   "data_proximo_vencimento" de acordo.
4. O job diário em app/scheduler/jobs.py verifica quem está com a
   assinatura vencida e bloqueia o acesso (Salao.esta_com_acesso_liberado()).
"""

import enum
import uuid
from datetime import datetime, timedelta

from app.extensions import db


class StatusAssinatura(str, enum.Enum):
    PENDENTE = "pendente"    # criada, aguardando 1º pagamento ser aprovado
    APROVADA = "aprovada"    # em dia
    ATRASADA = "atrasada"    # venceu e ainda não foi paga
    CANCELADA = "cancelada"  # cancelada pelo dono ou pelo Mercado Pago


class Assinatura(db.Model):
    __tablename__ = "assinaturas"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    salao_id = db.Column(
        db.String(36), db.ForeignKey("saloes.id"), nullable=False, unique=True
    )

    # ID da "preapproval" (assinatura recorrente) no Mercado Pago. É esse
    # ID que relacionamos com as notificações recebidas no webhook.
    mercado_pago_preapproval_id = db.Column(db.String(120), nullable=True, index=True)

    status = db.Column(
        db.Enum(StatusAssinatura), nullable=False, default=StatusAssinatura.PENDENTE
    )
    valor_mensal = db.Column(db.Numeric(10, 2), nullable=False)

    data_inicio = db.Column(db.DateTime, nullable=True)
    data_proximo_vencimento = db.Column(db.DateTime, nullable=True)

    criado_em = db.Column(db.DateTime, server_default=db.func.now())
    atualizado_em = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    salao = db.relationship("Salao", back_populates="assinatura")

    def esta_ativa(self) -> bool:
        """
        Considerada ativa se o status é APROVADA e a data de vencimento
        ainda não passou. Damos uma tolerância de 3 dias de atraso antes
        de bloquear de fato (evita bloquear por pequenas demoras do
        Mercado Pago em processar o pagamento).
        """
        if self.status != StatusAssinatura.APROVADA:
            return False
        if self.data_proximo_vencimento is None:
            return True
        tolerancia = self.data_proximo_vencimento + timedelta(days=3)
        return datetime.utcnow() <= tolerancia

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "salao_id": self.salao_id,
            "status": self.status.value,
            "valor_mensal": float(self.valor_mensal),
            "data_inicio": self.data_inicio.isoformat() if self.data_inicio else None,
            "data_proximo_vencimento": self.data_proximo_vencimento.isoformat()
            if self.data_proximo_vencimento
            else None,
            "esta_ativa": self.esta_ativa(),
        }

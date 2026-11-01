# -*- coding: utf-8 -*-
"""
Jobs em background executados pelo APScheduler (veja o start em
app/__init__.py e a instância do scheduler em app/extensions.py).

Dois jobs são registrados:

1. `verificar_assinaturas_vencidas` — roda uma vez por dia. Procura
   assinaturas cujo `data_proximo_vencimento` já passou (com a tolerância
   definida em Assinatura.esta_ativa()) e ainda estão marcadas como
   "aprovada", muda para "atrasada" e avisa o dono via WhatsApp. Isso é
   o que efetivamente BLOQUEIA o painel do dono/profissionais (ver
   Salao.esta_com_acesso_liberado(), consultado nas rotas protegidas).

2. `enviar_lembretes_agendamento` — roda a cada 15 minutos. Procura
   agendamentos confirmados que estão a ~24h ou ~1h de distância e
   ainda não tiveram o lembrete correspondente enviado, e dispara a
   mensagem de WhatsApp.

Cada job precisa rodar dentro de um "app context" do Flask (para poder
usar `db.session` e `current_app.config`), por isso `registrar_jobs()`
recebe a instância `app` e cada função de job entra em `with app.app_context():`.
"""

import logging
from datetime import datetime, timedelta

from app.extensions import db

logger = logging.getLogger(__name__)

JANELA_LEMBRETE_24H = timedelta(hours=24)
JANELA_LEMBRETE_1H = timedelta(hours=1)
# Tolerância para achar agendamentos "por volta" do horário alvo, já que
# o job roda a cada 15 minutos e não exatamente no segundo certo.
TOLERANCIA_JANELA = timedelta(minutes=15)


def verificar_assinaturas_vencidas(app):
    with app.app_context():
        from app.models.assinatura import Assinatura, StatusAssinatura
        from app.services import whatsapp_service

        agora = datetime.utcnow()
        assinaturas_aprovadas = Assinatura.query.filter_by(status=StatusAssinatura.APROVADA).all()

        for assinatura in assinaturas_aprovadas:
            if assinatura.data_proximo_vencimento is None:
                continue
            if agora <= assinatura.data_proximo_vencimento + timedelta(days=3):
                continue  # ainda dentro da tolerância, não faz nada

            assinatura.status = StatusAssinatura.ATRASADA
            db.session.commit()
            logger.info("Assinatura %s marcada como ATRASADA (venceu em %s).",
                        assinatura.id, assinatura.data_proximo_vencimento)

            whatsapp_service.enviar_aviso_cobranca(
                app,
                assinatura.salao,
                mensagem_extra=(
                    "sua assinatura está atrasada e o acesso ao painel foi "
                    "bloqueado até a regularização do pagamento."
                ),
            )


def enviar_lembretes_agendamento(app):
    with app.app_context():
        from app.models.agendamento import Agendamento, StatusAgendamento
        from app.services import whatsapp_service

        # Os horários dos agendamentos são guardados em hora local (sem fuso),
        # então a comparação também precisa ser em hora local — com utcnow()
        # os lembretes sairiam 3 horas fora do horário.
        agora = datetime.now()

        _enviar_lembretes_da_janela(
            app, agora, JANELA_LEMBRETE_24H, "lembrete_24h_enviado", horas=24
        )
        _enviar_lembretes_da_janela(
            app, agora, JANELA_LEMBRETE_1H, "lembrete_1h_enviado", horas=1
        )


def _enviar_lembretes_da_janela(app, agora, janela: timedelta, campo_flag: str, horas: int):
    from app.models.agendamento import Agendamento, StatusAgendamento
    from app.services import whatsapp_service

    alvo = agora + janela
    inicio_janela = alvo - TOLERANCIA_JANELA
    fim_janela = alvo + TOLERANCIA_JANELA

    query = Agendamento.query.filter(
        Agendamento.status == StatusAgendamento.CONFIRMADO,
        Agendamento.inicio >= inicio_janela,
        Agendamento.inicio <= fim_janela,
        getattr(Agendamento, campo_flag).is_(False),
    )

    for agendamento in query.all():
        whatsapp_service.enviar_lembrete_agendamento(app, agendamento, horas_de_antecedencia=horas)
        setattr(agendamento, campo_flag, True)
        db.session.commit()
        logger.info("Lembrete de %sh enviado para agendamento %s.", horas, agendamento.id)


def expirar_solicitacoes_vencidas(app):
    """
    Solicitações que ninguém respondeu e cujo horário já passou não servem
    mais: viram RECUSADO (com motivo) para sair da fila do administrador.
    """
    with app.app_context():
        from app.models.agendamento import Agendamento, StatusAgendamento

        vencidas = Agendamento.query.filter(
            Agendamento.status == StatusAgendamento.PENDENTE,
            Agendamento.inicio < datetime.now(),
        ).all()
        for agendamento in vencidas:
            agendamento.status = StatusAgendamento.RECUSADO
            agendamento.motivo_recusa = "Solicitação expirada sem resposta."
        if vencidas:
            db.session.commit()
            logger.info("%s solicitação(ões) expirada(s).", len(vencidas))


def registrar_jobs(scheduler, app) -> None:
    """Registra os jobs recorrentes no BackgroundScheduler."""
    scheduler.add_job(
        func=lambda: expirar_solicitacoes_vencidas(app),
        trigger="interval",
        hours=1,
        id="expirar_solicitacoes_vencidas",
        replace_existing=True,
    )

    scheduler.add_job(
        func=lambda: verificar_assinaturas_vencidas(app),
        trigger="cron",
        hour=6,
        minute=0,
        id="verificar_assinaturas_vencidas",
        replace_existing=True,
    )

    scheduler.add_job(
        func=lambda: enviar_lembretes_agendamento(app),
        trigger="interval",
        minutes=15,
        id="enviar_lembretes_agendamento",
        replace_existing=True,
    )

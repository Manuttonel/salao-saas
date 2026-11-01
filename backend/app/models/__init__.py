# -*- coding: utf-8 -*-
"""
Importa todos os models num único lugar.

Isso é necessário para que o Flask-Migrate (Alembic) "enxergue" todas as
tabelas ao gerar migrações — se um model nunca for importado, o
SQLAlchemy não sabe que ele existe.
"""

from app.models.usuario import Usuario, PapelUsuario
from app.models.salao import Salao, Servico, DiaAgenda, SalaoAdministrador
from app.models.profissional import Profissional, Indisponibilidade
from app.models.cliente import Cliente
from app.models.agendamento import Agendamento, StatusAgendamento
from app.models.assinatura import Assinatura, StatusAssinatura
from app.models.conversa_whatsapp import ConversaWhatsapp

__all__ = [
    "Usuario",
    "PapelUsuario",
    "Salao",
    "Servico",
    "DiaAgenda",
    "SalaoAdministrador",
    "Profissional",
    "Indisponibilidade",
    "Cliente",
    "Agendamento",
    "StatusAgendamento",
    "Assinatura",
    "StatusAssinatura",
    "ConversaWhatsapp",
]

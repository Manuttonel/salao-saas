# -*- coding: utf-8 -*-
"""
Importa todos os models num único lugar.

Isso é necessário para que o Flask-Migrate (Alembic) "enxergue" todas as
tabelas ao gerar migrações — se um model nunca for importado, o
SQLAlchemy não sabe que ele existe.
"""

from app.models.usuario import Usuario, PapelUsuario
from app.models.salao import Salao, Servico
from app.models.profissional import Profissional, Indisponibilidade
from app.models.cliente import Cliente
from app.models.agendamento import Agendamento, StatusAgendamento
from app.models.assinatura import Assinatura, StatusAssinatura

__all__ = [
    "Usuario",
    "PapelUsuario",
    "Salao",
    "Servico",
    "Profissional",
    "Indisponibilidade",
    "Cliente",
    "Agendamento",
    "StatusAgendamento",
    "Assinatura",
    "StatusAssinatura",
]

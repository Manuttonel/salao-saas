# -*- coding: utf-8 -*-
"""Ajustes de conexão com o banco para hospedagens (app/config.py)."""

from app.config import _normalizar_url_banco, _opcoes_do_motor


def test_url_de_hospedagem_vira_driver_psycopg():
    assert _normalizar_url_banco("postgres://u:p@h:5432/d") == "postgresql+psycopg://u:p@h:5432/d"
    assert _normalizar_url_banco("postgresql://u:p@h/d") == "postgresql+psycopg://u:p@h/d"
    assert _normalizar_url_banco("postgresql+psycopg://u:p@h/d") == "postgresql+psycopg://u:p@h/d"


def test_supabase_ganha_sslmode_require_uma_unica_vez():
    url = "postgresql://postgres.abc:senha@aws-0-sa-east-1.pooler.supabase.com:5432/postgres"
    ajustada = _normalizar_url_banco(url)
    assert ajustada.endswith("?sslmode=require")
    assert _normalizar_url_banco(ajustada) == ajustada  # idempotente
    assert _normalizar_url_banco(url + "?sslmode=verify-full").count("sslmode=") == 1


def test_banco_local_nao_recebe_ssl():
    assert "sslmode" not in _normalizar_url_banco("postgresql://postgres:x@localhost:5432/salao_saas")


def test_pooler_em_modo_transacao_desliga_prepared_statements():
    assert _opcoes_do_motor("postgresql+psycopg://u:p@h:6543/postgres")["connect_args"] == {"prepare_threshold": None}
    assert "connect_args" not in _opcoes_do_motor("postgresql+psycopg://u:p@h:5432/postgres")
    assert _opcoes_do_motor("postgresql+psycopg://u:p@h:5432/postgres")["pool_pre_ping"] is True

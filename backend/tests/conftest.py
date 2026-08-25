# -*- coding: utf-8 -*-
"""
Fixtures compartilhadas dos testes (pytest).

Os testes usam a configuração "testing" (veja app/config.py), que aponta
para TEST_DATABASE_URL — um banco PostgreSQL separado do de
desenvolvimento, só para não misturar dados de teste com dados reais.
Antes de rodar os testes, crie esse banco (ex.: `createdb salao_saas_test`)
e configure TEST_DATABASE_URL no seu .env, se for diferente do padrão.
"""

import pytest

from app import create_app
from app.extensions import db as _db


@pytest.fixture()
def app():
    aplicacao = create_app("testing")
    with aplicacao.app_context():
        _db.create_all()
        yield aplicacao
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()

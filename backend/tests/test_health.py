# -*- coding: utf-8 -*-
def test_healthcheck(client):
    resposta = client.get("/api/health")
    assert resposta.status_code == 200
    assert resposta.get_json() == {"status": "ok"}

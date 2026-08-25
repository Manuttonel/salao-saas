# -*- coding: utf-8 -*-
"""Testes do fluxo de registro e login (app/routes/auth_routes.py)."""


def test_registrar_e_logar_cliente(client):
    payload = {
        "nome": "Maria Cliente",
        "email": "maria@example.com",
        "senha": "senha123",
        "telefone": "5511999990000",
        "papel": "cliente",
    }
    resposta_registro = client.post("/api/auth/registrar", json=payload)
    assert resposta_registro.status_code == 201
    assert "access_token" in resposta_registro.get_json()

    resposta_login = client.post(
        "/api/auth/login", json={"email": payload["email"], "senha": payload["senha"]}
    )
    assert resposta_login.status_code == 200
    corpo = resposta_login.get_json()
    assert corpo["usuario"]["papel"] == "cliente"
    assert "cliente_id" in corpo["usuario"]


def test_login_com_senha_errada_falha(client):
    client.post("/api/auth/registrar", json={
        "nome": "Joao Dono",
        "email": "joao@example.com",
        "senha": "senhacerta",
        "telefone": "5511988887777",
        "papel": "dono",
    })
    resposta = client.post(
        "/api/auth/login", json={"email": "joao@example.com", "senha": "senhaerrada"}
    )
    assert resposta.status_code == 401


def test_nao_permite_autocadastro_como_profissional(client):
    resposta = client.post("/api/auth/registrar", json={
        "nome": "Alguem",
        "email": "alguem@example.com",
        "senha": "123456",
        "telefone": "5511977776666",
        "papel": "profissional",
    })
    assert resposta.status_code == 400

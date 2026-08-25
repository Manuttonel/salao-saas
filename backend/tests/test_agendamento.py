# -*- coding: utf-8 -*-
"""
Teste de ponta a ponta do fluxo de agendamento, validando a regra mais
importante do sistema: dois agendamentos não podem ocupar o mesmo
horário do mesmo profissional (veja app/services/agendador_service.py).
"""

from datetime import datetime, timedelta


def _registrar_e_logar(client, papel, email):
    client.post("/api/auth/registrar", json={
        "nome": f"Usuario {papel}",
        "email": email,
        "senha": "senha123",
        "telefone": "5511999990000",
        "papel": papel,
    })
    resposta = client.post("/api/auth/login", json={"email": email, "senha": "senha123"})
    corpo = resposta.get_json()
    return corpo["access_token"], corpo["usuario"]


def _cabecalho_auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_nao_permite_agendamento_duplicado_para_mesmo_profissional(client):
    token_dono, _ = _registrar_e_logar(client, "dono", "dono@example.com")

    resposta_salao = client.post("/api/saloes/", json={
        "nome": "Barbearia Teste",
        "telefone": "5511988887777",
        "horario_abertura": "09:00",
        "horario_fechamento": "18:00",
        "dias_funcionamento": [0, 1, 2, 3, 4, 5, 6],
    }, headers=_cabecalho_auth(token_dono))
    assert resposta_salao.status_code == 201
    salao_id = resposta_salao.get_json()["id"]

    resposta_servico = client.post(f"/api/saloes/{salao_id}/servicos", json={
        "nome": "Corte",
        "duracao_minutos": 30,
        "preco": 40.0,
    }, headers=_cabecalho_auth(token_dono))
    assert resposta_servico.status_code == 201
    servico_id = resposta_servico.get_json()["id"]

    resposta_profissional = client.post(f"/api/saloes/{salao_id}/profissionais", json={
        "nome": "Profissional Teste",
        "email": "prof@example.com",
        "telefone": "5511977776666",
        "senha_provisoria": "senha123",
    }, headers=_cabecalho_auth(token_dono))
    assert resposta_profissional.status_code == 201
    profissional_id = resposta_profissional.get_json()["id"]

    token_cliente1, _ = _registrar_e_logar(client, "cliente", "cliente1@example.com")
    token_cliente2, _ = _registrar_e_logar(client, "cliente", "cliente2@example.com")

    horario = (datetime.now() + timedelta(days=1)).replace(
        hour=10, minute=0, second=0, microsecond=0
    ).isoformat()

    payload_agendamento = {
        "salao_id": salao_id,
        "profissional_id": profissional_id,
        "servico_id": servico_id,
        "inicio": horario,
    }

    resposta1 = client.post(
        "/api/agendamentos/", json=payload_agendamento, headers=_cabecalho_auth(token_cliente1)
    )
    assert resposta1.status_code == 201

    resposta2 = client.post(
        "/api/agendamentos/", json=payload_agendamento, headers=_cabecalho_auth(token_cliente2)
    )
    assert resposta2.status_code == 409
    assert "ocupado" in resposta2.get_json()["erro"].lower()

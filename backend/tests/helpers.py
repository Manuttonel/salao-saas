# -*- coding: utf-8 -*-
"""Funções de apoio compartilhadas pelos testes."""

from datetime import datetime, timedelta


def cabecalho(token):
    return {"Authorization": f"Bearer {token}"}


def registrar_e_logar(client, papel, email, telefone="5511999990000"):
    client.post("/api/auth/registrar", json={
        "nome": f"Usuario {papel}", "email": email, "senha": "senha123",
        "telefone": telefone, "papel": papel,
    })
    corpo = client.post("/api/auth/login", json={"email": email, "senha": "senha123"}).get_json()
    return corpo["access_token"], corpo["usuario"]


def amanha_as(hora, minuto=0):
    return (datetime.now() + timedelta(days=1)).replace(hour=hora, minute=minuto, second=0, microsecond=0)


def criar_cenario(client):
    """
    Salão aberto todos os dias (09-18) com um procedimento de 30 min.
    O profissional padrão (o próprio dono) e a "Marcar Avaliação" são criados
    automaticamente junto com o salão.
    """
    token_dono, usuario_dono = registrar_e_logar(client, "dono", "dono@example.com")
    salao = client.post("/api/saloes/", json={
        "nome": "Barbearia Teste", "telefone": "5511988887777",
        "horario_abertura": "09:00", "horario_fechamento": "18:00",
        "dias_funcionamento": [0, 1, 2, 3, 4, 5, 6],
    }, headers=cabecalho(token_dono)).get_json()

    servico = client.post(f"/api/saloes/{salao['id']}/servicos", json={
        "nome": "Corte", "categoria": "cabelo", "duracao_minutos": 30, "preco": 40,
    }, headers=cabecalho(token_dono)).get_json()

    profissionais = client.get(f"/api/saloes/{salao['id']}/profissionais").get_json()
    servicos = client.get(f"/api/saloes/{salao['id']}/servicos").get_json()
    avaliacao = next(s for s in servicos if s["eh_avaliacao"])

    return {
        "token_dono": token_dono,
        "usuario_dono": usuario_dono,
        "salao_id": salao["id"],
        "servico_id": servico["id"],
        "avaliacao_id": avaliacao["id"],
        "profissional_id": profissionais[0]["id"],
    }


def solicitar(client, cenario, token_cliente, inicio, servico_id=None, profissional_id="padrao"):
    corpo = {
        "salao_id": cenario["salao_id"],
        "servico_id": servico_id or cenario["servico_id"],
        "inicio": inicio.isoformat(),
    }
    if profissional_id == "padrao":
        corpo["profissional_id"] = cenario["profissional_id"]
    elif profissional_id:
        corpo["profissional_id"] = profissional_id
    return client.post("/api/agendamentos/", json=corpo, headers=cabecalho(token_cliente))

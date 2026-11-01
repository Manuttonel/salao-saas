# -*- coding: utf-8 -*-
"""
Fluxo de SOLICITAÇÃO de horário (app/routes/agendamento_routes.py):

  - o pedido do cliente nasce PENDENTE e NÃO bloqueia o horário;
  - só quando um administrador ACEITA o horário fica indisponível;
  - dois pedidos para o mesmo horário: aceita um, o outro não pode mais ser aceito.
"""

from helpers import cabecalho, registrar_e_logar, criar_cenario, solicitar, amanha_as


def test_solicitacao_nasce_pendente_e_nao_bloqueia_horario(client):
    cenario = criar_cenario(client)
    token1, _ = registrar_e_logar(client, "cliente", "c1@example.com", "5511911110001")
    token2, _ = registrar_e_logar(client, "cliente", "c2@example.com", "5511911110002")
    inicio = amanha_as(10)

    r1 = solicitar(client, cenario, token1, inicio)
    r2 = solicitar(client, cenario, token2, inicio)

    assert r1.status_code == 201 and r1.get_json()["status"] == "pendente"
    assert r2.status_code == 201  # ainda ninguém foi confirmado: os dois pedidos entram

    livres = client.get("/api/agendamentos/horarios-disponiveis", query_string={
        "salao_id": cenario["salao_id"], "servico_id": cenario["servico_id"],
        "profissional_id": cenario["profissional_id"], "data": inicio.date().isoformat(),
    }).get_json()["horarios"]
    assert inicio.isoformat() in livres  # pendente não ocupa a agenda


def test_aceitar_confirma_e_bloqueia_horario_para_os_outros(client):
    cenario = criar_cenario(client)
    token1, _ = registrar_e_logar(client, "cliente", "c1@example.com", "5511911110001")
    token2, _ = registrar_e_logar(client, "cliente", "c2@example.com", "5511911110002")
    inicio = amanha_as(10)
    id1 = solicitar(client, cenario, token1, inicio).get_json()["id"]
    id2 = solicitar(client, cenario, token2, inicio).get_json()["id"]
    dono = cabecalho(cenario["token_dono"])

    aceito = client.post(f"/api/agendamentos/{id1}/aceitar", headers=dono)
    assert aceito.status_code == 200 and aceito.get_json()["status"] == "confirmado"

    # O segundo pedido para o mesmo horário não pode mais ser aceito...
    segundo = client.post(f"/api/agendamentos/{id2}/aceitar", headers=dono)
    assert segundo.status_code == 409
    assert "ocupado" in segundo.get_json()["erro"].lower()

    # ...e o horário some da lista de livres, e novos pedidos são barrados.
    livres = client.get("/api/agendamentos/horarios-disponiveis", query_string={
        "salao_id": cenario["salao_id"], "servico_id": cenario["servico_id"],
        "profissional_id": cenario["profissional_id"], "data": inicio.date().isoformat(),
    }).get_json()["horarios"]
    assert inicio.isoformat() not in livres
    token3, _ = registrar_e_logar(client, "cliente", "c3@example.com", "5511911110003")
    assert solicitar(client, cenario, token3, inicio).status_code == 409


def test_recusar_registra_motivo_e_nao_pode_aceitar_depois(client):
    cenario = criar_cenario(client)
    token, _ = registrar_e_logar(client, "cliente", "c1@example.com", "5511911110001")
    agendamento_id = solicitar(client, cenario, token, amanha_as(11)).get_json()["id"]
    dono = cabecalho(cenario["token_dono"])

    recusado = client.post(f"/api/agendamentos/{agendamento_id}/recusar",
                           json={"motivo": "Estaremos fechados"}, headers=dono)
    assert recusado.status_code == 200
    assert recusado.get_json()["status"] == "recusado"
    assert recusado.get_json()["motivo_recusa"] == "Estaremos fechados"

    assert client.post(f"/api/agendamentos/{agendamento_id}/aceitar", headers=dono).status_code == 409


def test_cliente_nao_pode_aceitar_a_propria_solicitacao(client):
    cenario = criar_cenario(client)
    token, _ = registrar_e_logar(client, "cliente", "c1@example.com", "5511911110001")
    agendamento_id = solicitar(client, cenario, token, amanha_as(10)).get_json()["id"]

    resposta = client.post(f"/api/agendamentos/{agendamento_id}/aceitar", headers=cabecalho(token))
    assert resposta.status_code == 403


def test_administrador_adicional_tambem_responde_solicitacoes(client):
    cenario = criar_cenario(client)
    dono = cabecalho(cenario["token_dono"])
    criado = client.post(f"/api/saloes/{cenario['salao_id']}/administradores", json={
        "nome": "Recepção", "email": "recepcao@example.com",
        "telefone": "5511955554444", "senha_provisoria": "senha123",
    }, headers=dono)
    assert criado.status_code == 201

    login = client.post("/api/auth/login", json={"email": "recepcao@example.com", "senha": "senha123"}).get_json()
    assert login["usuario"]["papel"] == "administrador"
    assert login["usuario"]["saloes"] == [cenario["salao_id"]]
    admin = cabecalho(login["access_token"])

    token_cliente, _ = registrar_e_logar(client, "cliente", "c1@example.com", "5511911110001")
    agendamento_id = solicitar(client, cenario, token_cliente, amanha_as(14)).get_json()["id"]

    fila = client.get("/api/agendamentos/", query_string={"status": "pendente"}, headers=admin)
    assert [a["id"] for a in fila.get_json()] == [agendamento_id]
    assert client.post(f"/api/agendamentos/{agendamento_id}/aceitar", headers=admin).status_code == 200

    # Administrador não gerencia outros administradores (só o dono).
    assert client.post(f"/api/saloes/{cenario['salao_id']}/administradores", json={
        "nome": "X", "email": "x@example.com", "telefone": "5511900000000", "senha_provisoria": "senha123",
    }, headers=admin).status_code == 403


def test_administrador_de_outro_salao_nao_acessa(client):
    cenario = criar_cenario(client)
    token_cliente, _ = registrar_e_logar(client, "cliente", "c1@example.com", "5511911110001")
    agendamento_id = solicitar(client, cenario, token_cliente, amanha_as(10)).get_json()["id"]

    outro_dono, _ = registrar_e_logar(client, "dono", "outro@example.com", "5511977770000")
    resposta = client.post(f"/api/agendamentos/{agendamento_id}/aceitar", headers=cabecalho(outro_dono))
    assert resposta.status_code == 404


def test_cliente_ve_apenas_os_proprios_pedidos_e_pode_cancelar(client):
    cenario = criar_cenario(client)
    token1, _ = registrar_e_logar(client, "cliente", "c1@example.com", "5511911110001")
    token2, _ = registrar_e_logar(client, "cliente", "c2@example.com", "5511911110002")
    id1 = solicitar(client, cenario, token1, amanha_as(10)).get_json()["id"]
    solicitar(client, cenario, token2, amanha_as(12))

    meus = client.get("/api/agendamentos/", headers=cabecalho(token1)).get_json()
    assert [a["id"] for a in meus] == [id1]

    assert client.post(f"/api/agendamentos/{id1}/cancelar", headers=cabecalho(token2)).status_code == 403
    cancelado = client.post(f"/api/agendamentos/{id1}/cancelar", headers=cabecalho(token1))
    assert cancelado.status_code == 200 and cancelado.get_json()["status"] == "cancelado"


def test_sem_profissional_escolhido_o_sistema_atribui_um_livre(client):
    cenario = criar_cenario(client)
    token, _ = registrar_e_logar(client, "cliente", "c1@example.com", "5511911110001")

    resposta = solicitar(client, cenario, token, amanha_as(10), profissional_id=None)
    assert resposta.status_code == 201
    assert resposta.get_json()["profissional_id"] == cenario["profissional_id"]


def test_agendamento_manual_do_administrador_ja_nasce_confirmado(client):
    cenario = criar_cenario(client)
    dono = cabecalho(cenario["token_dono"])
    cliente = client.post("/api/clientes/", json={
        "salao_id": cenario["salao_id"], "nome": "Cliente Balcão", "telefone": "(11) 98888-7777",
    }, headers=dono).get_json()

    resposta = client.post("/api/agendamentos/manual", json={
        "cliente_id": cliente["id"], "profissional_id": cenario["profissional_id"],
        "servico_id": cenario["servico_id"], "inicio": amanha_as(15).isoformat(),
    }, headers=dono)
    assert resposta.status_code == 201
    assert resposta.get_json()["status"] == "confirmado"
    assert resposta.get_json()["origem"] == "manual"

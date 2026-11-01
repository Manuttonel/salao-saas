# -*- coding: utf-8 -*-
"""Conversa completa com o bot de WhatsApp (app/services/bot_whatsapp_service.py)."""

from helpers import cabecalho, criar_cenario

TELEFONE = "5511933334444"


def _falar(client, cenario, texto, nome=None):
    corpo = {"telefone": TELEFONE, "texto": texto}
    if nome:
        corpo["nome"] = nome
    resposta = client.post(f"/api/saloes/{cenario['salao_id']}/bot/simular", json=corpo,
                           headers=cabecalho(cenario["token_dono"]))
    assert resposta.status_code == 200
    return "\n".join(resposta.get_json()["respostas"])


def test_bot_marca_avaliacao_gera_solicitacao_pendente(client):
    cenario = criar_cenario(client)

    assert "Marcar uma avaliação" in _falar(client, cenario, "oi")
    assert "Qual dia" in _falar(client, cenario, "2")
    assert "Horários livres" in _falar(client, cenario, "1")
    assert "nome" in _falar(client, cenario, "1").lower()  # contato novo: pergunta o nome
    resumo = _falar(client, cenario, "Maria Silva")
    assert "Marcar Avaliação" in resumo and "Enviar solicitação" in resumo
    assert "Solicitação enviada" in _falar(client, cenario, "1")

    pendentes = client.get("/api/agendamentos/", query_string={"status": "pendente"},
                           headers=cabecalho(cenario["token_dono"])).get_json()
    assert len(pendentes) == 1
    assert pendentes[0]["origem"] == "whatsapp"
    assert pendentes[0]["cliente_nome"] == "Maria Silva"
    assert pendentes[0]["eh_avaliacao"] is True

    # A conversa recomeçou: o cliente pode consultar o que pediu.
    assert "aguardando confirmação" in _falar(client, cenario, "3")

    # A ficha do cliente foi criada sozinha no controle de clientes.
    fichas = client.get("/api/clientes/", query_string={"salao_id": cenario["salao_id"]},
                        headers=cabecalho(cenario["token_dono"])).get_json()
    assert fichas[0]["origem"] == "whatsapp" and fichas[0]["telefone"] == TELEFONE


def test_bot_nao_duplica_pedido_do_mesmo_cliente_no_mesmo_horario(client):
    cenario = criar_cenario(client)
    # Avaliação -> 1º dia -> 1º horário -> confirmar (o nome do contato já é conhecido).
    for passo in ["2", "1", "1"]:
        _falar(client, cenario, passo, nome="Joana")
    assert "Solicitação enviada" in _falar(client, cenario, "1", nome="Joana")

    # Repete exatamente o mesmo caminho: o mesmo horário já está pedido.
    for passo in ["2", "1", "1"]:
        _falar(client, cenario, passo, nome="Joana")
    assert "já tem uma solicitação" in _falar(client, cenario, "1", nome="Joana")

    pendentes = client.get("/api/agendamentos/", query_string={"status": "pendente"},
                           headers=cabecalho(cenario["token_dono"])).get_json()
    assert len(pendentes) == 1


def test_bot_lista_procedimentos_por_categoria(client):
    cenario = criar_cenario(client)
    lista = _falar(client, cenario, "1")
    assert "*Cabelo*" in lista and "Corte" in lista and "30 min" in lista
    assert "Marcar Avaliação" not in lista  # a avaliação tem opção própria no menu


def test_bot_entrada_invalida_nao_quebra_e_menu_volta_ao_inicio(client):
    cenario = criar_cenario(client)
    _falar(client, cenario, "1")
    assert "Não entendi" in _falar(client, cenario, "99")
    assert "Não entendi" in _falar(client, cenario, "abc")
    assert "Bem-vindo" in _falar(client, cenario, "menu")


def test_bot_nao_cria_solicitacao_se_cliente_cancela(client):
    cenario = criar_cenario(client)
    for passo in ["2", "1", "1"]:
        _falar(client, cenario, passo, nome="Joana")
    assert "não enviei nada" in _falar(client, cenario, "2", nome="Joana").lower()

    pendentes = client.get("/api/agendamentos/", query_string={"status": "pendente"},
                           headers=cabecalho(cenario["token_dono"])).get_json()
    assert pendentes == []


def test_webhook_evolution_api_responde_e_cria_conversa(client):
    cenario = criar_cenario(client)
    payload = {"event": "messages.upsert", "data": {
        "key": {"remoteJid": f"{TELEFONE}@s.whatsapp.net", "fromMe": False},
        "pushName": "Carla", "message": {"conversation": "oi"},
    }}
    resposta = client.post(f"/api/webhooks/whatsapp/{cenario['salao_id']}", json=payload)
    assert resposta.status_code == 200

    # Mensagens enviadas por nós mesmos e de grupos são ignoradas.
    proprio = {"data": {"key": {"remoteJid": f"{TELEFONE}@s.whatsapp.net", "fromMe": True},
                        "message": {"conversation": "oi"}}}
    assert client.post(f"/api/webhooks/whatsapp/{cenario['salao_id']}", json=proprio).status_code == 200
    assert client.post("/api/webhooks/whatsapp/id-inexistente", json=payload).status_code == 404


def test_webhook_exige_token_quando_configurado(client, app):
    cenario = criar_cenario(client)
    app.config["WHATSAPP_WEBHOOK_TOKEN"] = "segredo123"
    url = f"/api/webhooks/whatsapp/{cenario['salao_id']}"
    assert client.post(url, json={}).status_code == 401
    assert client.post(url + "?token=errado", json={}).status_code == 401
    assert client.post(url + "?token=segredo123", json={}).status_code == 200

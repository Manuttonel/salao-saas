# -*- coding: utf-8 -*-
"""Calendário de dias disponíveis, procedimentos, avaliação e controle de clientes."""

from datetime import date, timedelta

from helpers import cabecalho, registrar_e_logar, criar_cenario, solicitar, amanha_as


def test_salao_novo_ja_tem_avaliacao_e_profissional_padrao(client):
    cenario = criar_cenario(client)
    servicos = client.get(f"/api/saloes/{cenario['salao_id']}/servicos").get_json()

    avaliacao = servicos[0]  # a avaliação vem sempre primeiro
    assert avaliacao["eh_avaliacao"] is True
    assert avaliacao["nome"] == "Marcar Avaliação"
    assert avaliacao["duracao_minutos"] == 20
    assert len(client.get(f"/api/saloes/{cenario['salao_id']}/profissionais").get_json()) == 1


def test_administrador_define_a_duracao_da_avaliacao_e_de_cada_procedimento(client):
    cenario = criar_cenario(client)
    dono = cabecalho(cenario["token_dono"])

    editada = client.put(f"/api/saloes/servicos/{cenario['avaliacao_id']}",
                         json={"duracao_minutos": 10}, headers=dono)
    assert editada.status_code == 200 and editada.get_json()["duracao_minutos"] == 10

    # A duração do procedimento define o fim do horário reservado.
    token, _ = registrar_e_logar(client, "cliente", "c1@example.com", "5511911110001")
    agendamento = solicitar(client, cenario, token, amanha_as(10), servico_id=cenario["avaliacao_id"]).get_json()
    assert agendamento["eh_avaliacao"] is True
    assert agendamento["fim"] == amanha_as(10, 10).isoformat()


def test_categoria_invalida_e_rejeitada(client):
    cenario = criar_cenario(client)
    resposta = client.post(f"/api/saloes/{cenario['salao_id']}/servicos", json={
        "nome": "Algo", "categoria": "inexistente", "duracao_minutos": 30, "preco": 10,
    }, headers=cabecalho(cenario["token_dono"]))
    assert resposta.status_code == 400


def test_dia_marcado_como_indisponivel_nao_aceita_pedidos(client):
    cenario = criar_cenario(client)
    dono = cabecalho(cenario["token_dono"])
    amanha = amanha_as(10)

    marcado = client.put(f"/api/saloes/{cenario['salao_id']}/dias-agenda/{amanha.date().isoformat()}",
                         json={"aberto": False, "motivo": "Feriado"}, headers=dono)
    assert marcado.status_code == 200

    dias = client.get(f"/api/saloes/{cenario['salao_id']}/calendario",
                      query_string={"mes": amanha.strftime("%Y-%m")}).get_json()["dias"]
    dia = next(d for d in dias if d["data"] == amanha.date().isoformat())
    assert dia["status"] == "fechado" and dia["excecao"] == "fechado"

    token, _ = registrar_e_logar(client, "cliente", "c1@example.com", "5511911110001")
    resposta = solicitar(client, cenario, token, amanha)
    assert resposta.status_code == 409
    assert "não atende" in resposta.get_json()["erro"].lower()


def test_modo_somente_dias_marcados(client):
    cenario = criar_cenario(client)
    dono = cabecalho(cenario["token_dono"])
    token, _ = registrar_e_logar(client, "cliente", "c1@example.com", "5511911110001")
    amanha, depois = amanha_as(10), amanha_as(10) + timedelta(days=1)

    client.put(f"/api/saloes/{cenario['salao_id']}", json={"somente_dias_marcados": True}, headers=dono)
    # Nenhum dia marcado ainda: tudo fechado.
    assert solicitar(client, cenario, token, amanha).status_code == 409

    # O administrador marca só "amanhã" com horário especial (10h-12h).
    client.put(f"/api/saloes/{cenario['salao_id']}/dias-agenda/{amanha.date().isoformat()}",
               json={"aberto": True, "hora_inicio": "10:00", "hora_fim": "12:00"}, headers=dono)
    assert solicitar(client, cenario, token, amanha).status_code == 201
    assert solicitar(client, cenario, token, amanha_as(14)).status_code == 409  # fora do horário do dia
    assert solicitar(client, cenario, token, depois).status_code == 409  # dia não marcado

    # Remover a exceção devolve o dia à regra geral (que, neste modo, é fechado).
    client.delete(f"/api/saloes/{cenario['salao_id']}/dias-agenda/{amanha.date().isoformat()}", headers=dono)
    dias = client.get(f"/api/saloes/{cenario['salao_id']}/calendario",
                      query_string={"mes": amanha.strftime("%Y-%m")}).get_json()["dias"]
    assert next(d for d in dias if d["data"] == amanha.date().isoformat())["status"] == "fechado"


def test_nao_permite_marcar_dia_no_passado(client):
    cenario = criar_cenario(client)
    ontem = (date.today() - timedelta(days=1)).isoformat()
    resposta = client.put(f"/api/saloes/{cenario['salao_id']}/dias-agenda/{ontem}",
                          json={"aberto": True}, headers=cabecalho(cenario["token_dono"]))
    assert resposta.status_code == 400


def test_controle_de_clientes(client):
    cenario = criar_cenario(client)
    dono = cabecalho(cenario["token_dono"])

    criado = client.post("/api/clientes/", json={
        "salao_id": cenario["salao_id"], "nome": "Ana Souza",
        "telefone": "(11) 97777-6666", "observacoes": "Alérgica a amônia",
    }, headers=dono)
    assert criado.status_code == 201
    assert criado.get_json()["telefone"] == "5511977776666"  # normalizado

    # Mesmo telefone escrito de outro jeito = mesma pessoa.
    repetido = client.post("/api/clientes/", json={
        "salao_id": cenario["salao_id"], "nome": "Ana", "telefone": "11977776666",
    }, headers=dono)
    assert repetido.status_code == 409

    busca = client.get("/api/clientes/", query_string={"salao_id": cenario["salao_id"], "busca": "ana"}, headers=dono)
    assert [c["nome"] for c in busca.get_json()] == ["Ana Souza"]
    por_telefone = client.get("/api/clientes/", query_string={"salao_id": cenario["salao_id"], "busca": "97777-6666"}, headers=dono)
    assert len(por_telefone.get_json()) == 1

    ficha = client.get(f"/api/clientes/{criado.get_json()['id']}", headers=dono).get_json()
    assert ficha["observacoes"] == "Alérgica a amônia" and ficha["historico"] == []


def test_cliente_do_site_vira_ficha_no_crm_do_salao(client):
    cenario = criar_cenario(client)
    token, _ = registrar_e_logar(client, "cliente", "c1@example.com", "(11) 91111-0001")
    solicitar(client, cenario, token, amanha_as(10))

    fichas = client.get("/api/clientes/", query_string={"salao_id": cenario["salao_id"]},
                        headers=cabecalho(cenario["token_dono"])).get_json()
    assert len(fichas) == 1
    assert fichas[0]["origem"] == "app" and fichas[0]["telefone"] == "5511911110001"


def test_cliente_final_nao_acessa_o_crm(client):
    cenario = criar_cenario(client)
    token, _ = registrar_e_logar(client, "cliente", "c1@example.com", "5511911110001")
    resposta = client.get("/api/clientes/", query_string={"salao_id": cenario["salao_id"]}, headers=cabecalho(token))
    assert resposta.status_code == 403


def test_preferencia_de_tema_e_salva_na_conta(client):
    token, _ = registrar_e_logar(client, "cliente", "c1@example.com")
    resposta = client.patch("/api/auth/preferencias", json={"tema": "glow"}, headers=cabecalho(token))
    assert resposta.status_code == 200 and resposta.get_json()["tema"] == "glow"

    unisex = client.patch("/api/auth/preferencias", json={"tema": "unisex", "cor_primaria": "#0EA5E9"},
                          headers=cabecalho(token)).get_json()
    assert unisex["cor_primaria"] == "#0ea5e9"

    assert client.patch("/api/auth/preferencias", json={"tema": "neon"}, headers=cabecalho(token)).status_code == 400
    assert client.patch("/api/auth/preferencias", json={"cor_primaria": "vermelho"}, headers=cabecalho(token)).status_code == 400
    login = client.post("/api/auth/login", json={"email": "c1@example.com", "senha": "senha123"}).get_json()
    assert login["usuario"]["tema"] == "unisex"

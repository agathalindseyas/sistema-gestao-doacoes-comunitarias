"""Testes de integração: validam rotas, formulários e banco de dados funcionando juntos."""
from app import get_db


def doar(client, nome="Arroz", quantidade="10", data="2026-11-17", **extra):
    dados = {"name": nome, "quantity": quantidade, "received_on": data,
             "description": "Pacote 5kg", "category": "Alimentos", "observation": ""}
    dados.update(extra)
    return client.post("/doacoes/nova", data=dados, follow_redirects=True)


def saldo(app, nome):
    with app.app_context():
        item = get_db().execute("SELECT quantity FROM items WHERE name=?", (nome,)).fetchone()
    return item["quantity"] if item else None


def id_do_item(app, nome):
    with app.app_context():
        return get_db().execute("SELECT id FROM items WHERE name=?", (nome,)).fetchone()["id"]


# ---------- Autenticação ----------

def test_rotas_protegidas_redirecionam_para_login(app):
    anonimo = app.test_client()
    for rota in ["/", "/estoque", "/historico", "/doacoes/nova", "/distribuicoes/nova"]:
        resposta = anonimo.get(rota)
        assert resposta.status_code == 302
        assert "/login" in resposta.headers["Location"]


def test_login_com_senha_errada_e_recusado(app):
    resposta = app.test_client().post("/login", data={"username": "tester", "password": "errada"})
    assert "Usuário ou senha inválidos." in resposta.get_data(as_text=True)


def test_login_valido_acessa_o_painel(client):
    resposta = client.get("/")
    assert resposta.status_code == 200
    assert "Gestão de Doações Comunitárias" in resposta.get_data(as_text=True)


def test_logout_encerra_a_sessao(client):
    client.post("/logout")
    assert client.get("/").status_code == 302


# ---------- Doações ----------

def test_formulario_de_doacao_abre(client):
    assert client.get("/doacoes/nova").status_code == 200


def test_cadastro_de_doacao_cria_item_e_movimentacao(client, app):
    resposta = doar(client)
    assert "Doação registrada com sucesso." in resposta.get_data(as_text=True)
    assert saldo(app, "Arroz") == 10
    with app.app_context():
        mov = get_db().execute("SELECT * FROM movements").fetchone()
    assert mov["movement_type"] == "ENTRADA" and mov["quantity"] == 10


def test_doacao_de_item_existente_soma_ao_saldo(client, app):
    doar(client, quantidade="10")
    doar(client, quantidade="5")
    assert saldo(app, "Arroz") == 15


def test_doacao_com_dados_invalidos_e_recusada(client, app):
    texto = doar(client, nome="", quantidade="abc", data="data-errada").get_data(as_text=True)
    assert "O nome do item é obrigatório." in texto
    assert "Informe uma quantidade inteira válida." in texto
    assert "Informe uma data válida." in texto
    assert saldo(app, "") is None


def test_doacao_com_quantidade_zero_e_recusada(client, app):
    texto = doar(client, quantidade="0").get_data(as_text=True)
    assert "A quantidade deve ser maior que zero." in texto
    assert saldo(app, "Arroz") is None


# ---------- Distribuições ----------

def test_formulario_de_distribuicao_abre(client):
    assert client.get("/distribuicoes/nova").status_code == 200


def test_distribuicao_reduz_o_estoque(client, app):
    doar(client, quantidade="10")
    resposta = client.post("/distribuicoes/nova", follow_redirects=True, data={
        "item_id": id_do_item(app, "Arroz"), "quantity": "4", "distributed_on": "2026-11-17"})
    assert "Distribuição registrada com sucesso." in resposta.get_data(as_text=True)
    assert saldo(app, "Arroz") == 6


def test_distribuicao_maior_que_o_saldo_e_bloqueada(client, app):
    doar(client, quantidade="3")
    resposta = client.post("/distribuicoes/nova", data={
        "item_id": id_do_item(app, "Arroz"), "quantity": "5", "distributed_on": "2026-11-17"})
    assert "estoque insuficiente" in resposta.get_data(as_text=True)
    assert saldo(app, "Arroz") == 3


def test_distribuicao_com_dados_invalidos_e_recusada(client):
    resposta = client.post("/distribuicoes/nova", data={
        "item_id": "", "quantity": "x", "distributed_on": ""})
    assert "Informe item, quantidade inteira e data válida." in resposta.get_data(as_text=True)


def test_distribuicao_com_quantidade_zero_e_recusada(client, app):
    doar(client, quantidade="3")
    resposta = client.post("/distribuicoes/nova", data={
        "item_id": id_do_item(app, "Arroz"), "quantity": "0", "distributed_on": "2026-11-17"})
    assert "A quantidade deve ser maior que zero." in resposta.get_data(as_text=True)


# ---------- Consultas ----------

def test_pesquisa_de_estoque_filtra_por_nome(client):
    doar(client, nome="Arroz")
    doar(client, nome="Feijão")
    texto = client.get("/estoque?q=Arr").get_data(as_text=True)
    assert "Arroz" in texto and "Feijão" not in texto


def test_historico_lista_entradas_e_saidas(client, app):
    doar(client, quantidade="10")
    client.post("/distribuicoes/nova", data={
        "item_id": id_do_item(app, "Arroz"), "quantity": "2", "distributed_on": "2026-11-17"})
    texto = client.get("/historico").get_data(as_text=True)
    assert "ENTRADA" in texto and "SAIDA" in texto


def test_resultado_de_item_inexistente_volta_ao_estoque(client):
    resposta = client.get("/resultados/999")
    assert resposta.status_code == 302
    assert "/estoque" in resposta.headers["Location"]


# ---------- Comando de criação de usuário ----------

def test_comando_cria_usuario(app, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "coordenadora")
    monkeypatch.setattr("getpass.getpass", lambda _: "senha-forte-1234")
    resultado = app.test_cli_runner().invoke(args=["create-user"])
    assert "Usuário criado." in resultado.output


def test_comando_recusa_senha_curta(app, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "coordenadora")
    monkeypatch.setattr("getpass.getpass", lambda _: "curta")
    resultado = app.test_cli_runner().invoke(args=["create-user"])
    assert resultado.exit_code != 0

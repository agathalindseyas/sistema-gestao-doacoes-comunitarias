"""Testes unitários: validam componentes isolados (banco, regras e segurança)."""
import sqlite3

import pytest
from werkzeug.security import check_password_hash, generate_password_hash

from app import close_db, get_db


def test_tabelas_criadas_na_inicializacao(app):
    with app.app_context():
        tabelas = {r["name"] for r in get_db().execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "items", "movements"} <= tabelas


def test_get_db_reutiliza_a_mesma_conexao(app):
    with app.app_context():
        assert get_db() is get_db()


def test_close_db_fecha_a_conexao(app):
    with app.app_context():
        conexao = get_db()
        close_db()
        with pytest.raises(sqlite3.ProgrammingError):
            conexao.execute("SELECT 1")


def test_banco_impede_quantidade_negativa_no_estoque(app):
    with app.app_context():
        db = get_db()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO items(name, quantity) VALUES('Arroz', -1)")


def test_banco_impede_tipo_de_movimentacao_invalido(app):
    with app.app_context():
        db = get_db()
        item_id = db.execute("INSERT INTO items(name, quantity) VALUES('Feijão', 5)").lastrowid
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("""INSERT INTO movements(item_id, movement_type, quantity, created_at)
                          VALUES(?, 'TROCA', 1, '2026-11-17')""", (item_id,))


def test_banco_impede_movimentacao_de_item_inexistente(app):
    with app.app_context():
        with pytest.raises(sqlite3.IntegrityError):
            get_db().execute("""INSERT INTO movements(item_id, movement_type, quantity, created_at)
                                VALUES(999, 'ENTRADA', 1, '2026-11-17')""")


def test_senha_armazenada_como_hash(app):
    with app.app_context():
        usuario = get_db().execute("SELECT * FROM users WHERE username='tester'").fetchone()
    assert usuario["password_hash"] != "senha-de-teste-123"
    assert check_password_hash(usuario["password_hash"], "senha-de-teste-123")


def test_hash_rejeita_senha_errada():
    assert not check_password_hash(generate_password_hash("senha-correta-123"), "senha-errada")


def test_cookies_de_sessao_configurados_com_seguranca(app):
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"

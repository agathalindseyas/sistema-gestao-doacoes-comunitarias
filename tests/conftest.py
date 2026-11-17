import pytest
from app import create_app
from werkzeug.security import generate_password_hash

@pytest.fixture()
def app(tmp_path):
    app = create_app({"TESTING": True, "SECRET_KEY": "test-key",
                      "DATABASE": str(tmp_path / "test.sqlite")})
    with app.app_context():
        from app import get_db
        db = get_db()
        db.execute("INSERT INTO users(username,password_hash) VALUES(?,?)",
                   ("tester", generate_password_hash("senha-de-teste-123")))
        db.commit()
    yield app

@pytest.fixture()
def client(app):
    c = app.test_client()
    c.post("/login", data={"username":"tester","password":"senha-de-teste-123"})
    return c

import os
from datetime import date
from functools import wraps
from flask import Flask, flash, redirect, render_template, request, session, url_for, g
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

from flask import current_app

def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "chave-local-apenas-para-desenvolvimento"),
        DATABASE=os.getenv("DATABASE", os.path.join(app.instance_path, "doacoes.sqlite")),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "0") == "1")
    if config:
        app.config.update(config)
    os.makedirs(app.instance_path, exist_ok=True)
    app.teardown_appcontext(close_db)
    with app.app_context():
        db = get_db()
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS items(
          id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, description TEXT,
          category TEXT, quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0));
        CREATE TABLE IF NOT EXISTS movements(
          id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL,
          movement_type TEXT NOT NULL CHECK(movement_type IN ('ENTRADA','SAIDA')),
          quantity INTEGER NOT NULL CHECK(quantity > 0), observation TEXT,
          created_at TEXT NOT NULL, FOREIGN KEY(item_id) REFERENCES items(id));
        CREATE INDEX IF NOT EXISTS idx_movements_item_date ON movements(item_id, created_at);
        """)
        db.commit()

    def protected(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            return fn(*args, **kwargs)
        return wrapper

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            user = get_db().execute("SELECT * FROM users WHERE username=?",
                                    (request.form.get("username", "").strip(),)).fetchone()
            if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
                session.clear()
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                return redirect(url_for("index"))
            flash("Usuário ou senha inválidos.", "error")
        return render_template("login.html")

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/")
    @protected
    def index():
        db = get_db()
        totals = db.execute("SELECT COUNT(*) items, COALESCE(SUM(quantity),0) units FROM items").fetchone()
        movements = db.execute("""SELECT m.*, i.name item_name FROM movements m
          JOIN items i ON i.id=m.item_id ORDER BY m.id DESC LIMIT 5""").fetchall()
        return render_template("index.html", totals=totals, movements=movements)

    @app.route("/doacoes/nova", methods=["GET", "POST"])
    @protected
    def donation():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()
            category = request.form.get("category", "").strip()
            observation = request.form.get("observation", "").strip()
            received_on = request.form.get("received_on", "")
            errors = []
            try:
                qty = int(request.form.get("quantity", ""))
                if qty <= 0: errors.append("A quantidade deve ser maior que zero.")
            except ValueError:
                qty = 0
                errors.append("Informe uma quantidade inteira válida.")
            try: date.fromisoformat(received_on)
            except ValueError: errors.append("Informe uma data válida.")
            if not name: errors.append("O nome do item é obrigatório.")
            if errors:
                for e in errors: flash(e, "error")
                return render_template("donation.html", form=request.form)
            db = get_db()
            try:
                db.execute("BEGIN")
                item = db.execute("SELECT id FROM items WHERE name=?", (name,)).fetchone()
                if item:
                    item_id = item["id"]
                    db.execute("UPDATE items SET description=?, category=?, quantity=quantity+? WHERE id=?",
                               (description, category, qty, item_id))
                else:
                    item_id = db.execute("INSERT INTO items(name,description,category,quantity) VALUES(?,?,?,?)",
                                         (name, description, category, qty)).lastrowid
                db.execute("""INSERT INTO movements(item_id,movement_type,quantity,observation,created_at)
                              VALUES(?, 'ENTRADA', ?, ?, ?)""", (item_id, qty, observation, received_on))
                db.commit()
            except Exception:
                db.rollback()
                raise
            flash("Doação registrada com sucesso.", "success")
            return redirect(url_for("results", item_id=item_id))
        return render_template("donation.html", form={})

    @app.route("/estoque")
    @protected
    def stock():
        term = request.args.get("q", "").strip()
        items = get_db().execute("SELECT * FROM items WHERE name LIKE ? ORDER BY name",
                                 (f"%{term}%",)).fetchall()
        return render_template("stock.html", items=items, term=term)

    @app.route("/distribuicoes/nova", methods=["GET", "POST"])
    @protected
    def distribution():
        db = get_db()
        items = db.execute("SELECT * FROM items ORDER BY name").fetchall()
        if request.method == "POST":
            try:
                item_id = int(request.form.get("item_id", ""))
                qty = int(request.form.get("quantity", ""))
                date_value = request.form.get("distributed_on", "")
                date.fromisoformat(date_value)
            except (ValueError, TypeError):
                flash("Informe item, quantidade inteira e data válida.", "error")
                return render_template("distribution.html", items=items, form=request.form)
            if qty <= 0:
                flash("A quantidade deve ser maior que zero.", "error")
                return render_template("distribution.html", items=items, form=request.form)
            try:
                db.execute("BEGIN IMMEDIATE")
                item = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
                if not item or qty > item["quantity"]:
                    db.rollback()
                    flash("Item inexistente ou estoque insuficiente. Operação não registrada.", "error")
                    return render_template("distribution.html", items=items, form=request.form)
                db.execute("UPDATE items SET quantity=quantity-? WHERE id=?", (qty, item_id))
                db.execute("""INSERT INTO movements(item_id,movement_type,quantity,observation,created_at)
                              VALUES(?, 'SAIDA', ?, ?, ?)""",
                           (item_id, qty, request.form.get("observation", "").strip(), date_value))
                db.commit()
            except Exception:
                db.rollback()
                raise
            flash("Distribuição registrada com sucesso.", "success")
            return redirect(url_for("results", item_id=item_id))
        return render_template("distribution.html", items=items, form={})

    @app.route("/resultados/<int:item_id>")
    @protected
    def results(item_id):
        db = get_db()
        item = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if not item:
            flash("Item não encontrado.", "error")
            return redirect(url_for("stock"))
        movements = db.execute("SELECT * FROM movements WHERE item_id=? ORDER BY id DESC LIMIT 10",
                               (item_id,)).fetchall()
        return render_template("results.html", item=item, movements=movements)

    @app.route("/historico")
    @protected
    def history():
        rows = get_db().execute("""SELECT m.*, i.name item_name FROM movements m
          JOIN items i ON i.id=m.item_id ORDER BY m.id DESC""").fetchall()
        return render_template("history.html", movements=rows)

    @app.cli.command("create-user")
    def create_user():
        import getpass
        username = input("Usuário: ").strip()
        password = getpass.getpass("Senha (mínimo 12 caracteres): ")
        if len(password) < 12: raise SystemExit("Senha muito curta.")
        get_db().execute("INSERT INTO users(username,password_hash) VALUES(?,?)",
                         (username, generate_password_hash(password)))
        get_db().commit()
        print("Usuário criado.")

    return app

app = create_app()
if __name__ == "__main__":
    app.run()

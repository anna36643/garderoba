import os
from flask import Flask, render_template, request, redirect, session, flash
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from database import init_db, get_db
from strings import STRINGS

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

init_db()


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated


@app.route("/register", methods=["GET", "POST"])
def register():
    s = STRINGS
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        invite_code = request.form["invite_code"].strip()

        db = get_db()

        code = db.execute(
            "SELECT * FROM invite_codes WHERE code = ? AND used = 0",
            (invite_code,)
        ).fetchone()

        if not code:
            flash(s["register_invalid_code"], "error")
            db.close()
            return redirect("/register")

        existing = db.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()

        if existing:
            flash(s["register_email_taken"], "error")
            db.close()
            return redirect("/register")

        password_hash = generate_password_hash(password)

        db.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, password_hash)
        )
        db.execute(
            "UPDATE invite_codes SET used = 1 WHERE code = ?",
            (invite_code,)
        )
        db.commit()

        user = db.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()

        session["user_id"] = user["id"]
        db.close()

        flash(s["register_success"], "success")
        return redirect("/setup")

    return render_template("register.html", s=STRINGS)


@app.route("/login", methods=["GET", "POST"])
def login():
    s = STRINGS
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        db.close()

        if not user or not check_password_hash(user["password_hash"], password):
            flash(s["login_invalid"], "error")
            return redirect("/login")

        session["user_id"] = user["id"]
        return redirect("/")

    return render_template("login.html", s=STRINGS)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/")
@login_required
def index():
    return "strona główna - w budowie"


@app.route("/setup")
@login_required
def setup():
    return "kreator - w budowie"


if __name__ == "__main__":
    app.run(debug=True)
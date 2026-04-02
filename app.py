import os
from flask import Flask, render_template, request, redirect, session, flash, jsonify, g
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from database import init_db, get_db, close_db
from strings import STRINGS

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

init_db()
app.teardown_appcontext(close_db)


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
            flash(STRINGS["register_invalid_code"], "error")
            return redirect("/register")

        existing = db.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()

        if existing:
            flash(STRINGS["register_email_taken"], "error")
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
        flash(STRINGS["register_success"], "success")
        return redirect("/setup")

    return render_template("register.html", s=STRINGS)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()

        if not user or not check_password_hash(user["password_hash"], password):
            flash(STRINGS["login_invalid"], "error")
            return redirect("/login")

        session["user_id"] = user["id"]

        furniture = db.execute(
            "SELECT id FROM furniture WHERE user_id = ?", (user["id"],)
        ).fetchone()

        if not furniture:
            return redirect("/setup")

        return redirect("/")

    return render_template("login.html", s=STRINGS)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/setup", methods=["GET", "POST"])
@login_required
def setup():
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip() or None
        furniture_name = request.form.get("furniture_name", "").strip() or None
        furniture_type = request.form["furniture_type"]
        person_name = request.form["person_name"].strip()
        user_id = session["user_id"]

        if furniture_type not in ("szafa", "komoda"):
            furniture_type = "szafa"

        db = get_db()

        if display_name:
            db.execute(
                "UPDATE users SET display_name = ? WHERE id = ?",
                (display_name, user_id)
            )

        db.execute(
            "INSERT INTO furniture (user_id, name, type) VALUES (?, ?, ?)",
            (user_id, furniture_name, furniture_type)
        )
        db.commit()

        furniture = db.execute(
            "SELECT id FROM furniture WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,)
        ).fetchone()

        db.execute(
            "INSERT INTO persons (user_id, furniture_id, name) VALUES (?, ?, ?)",
            (user_id, furniture["id"], person_name)
        )
        db.commit()
        return redirect("/")

    db = get_db()
    furniture = db.execute(
        "SELECT id FROM furniture WHERE user_id = ?", (session["user_id"],)
    ).fetchone()

    if furniture:
        return redirect("/")

    return render_template("setup.html", s=STRINGS)


@app.route("/")
@login_required
def index():
    user_id = session["user_id"]
    db = get_db()

    user = db.execute(
        "SELECT display_name FROM users WHERE id = ?", (user_id,)
    ).fetchone()

    furnitures = db.execute(
        "SELECT * FROM furniture WHERE user_id = ? ORDER BY created_at ASC",
        (user_id,)
    ).fetchall()

    furniture_list = []
    for f in furnitures:
        persons = db.execute(
            "SELECT * FROM persons WHERE furniture_id = ? AND user_id = ? ORDER BY created_at ASC",
            (f["id"], user_id)
        ).fetchall()
        furniture_list.append({"furniture": f, "persons": persons})

    return render_template(
        "index.html",
        s=STRINGS,
        furniture_list=furniture_list,
        display_name=user["display_name"] if user["display_name"] else None
    )


@app.route("/furniture/add", methods=["POST"])
@login_required
def furniture_add():
    name = request.form.get("name", "").strip() or None
    furniture_type = request.form["type"]
    user_id = session["user_id"]

    if furniture_type not in ("szafa", "komoda"):
        furniture_type = "szafa"

    db = get_db()
    db.execute(
        "INSERT INTO furniture (user_id, name, type) VALUES (?, ?, ?)",
        (user_id, name, furniture_type)
    )
    db.commit()
    return redirect("/")


@app.route("/furniture/edit", methods=["POST"])
@login_required
def furniture_edit():
    furniture_id = request.form["furniture_id"]
    name = request.form.get("name", "").strip() or None
    furniture_type = request.form["type"]
    user_id = session["user_id"]

    if furniture_type not in ("szafa", "komoda"):
        furniture_type = "szafa"

    db = get_db()
    db.execute(
        "UPDATE furniture SET name = ?, type = ? WHERE id = ? AND user_id = ?",
        (name, furniture_type, furniture_id, user_id)
    )
    db.commit()
    return redirect("/")


@app.route("/furniture/delete", methods=["POST"])
@login_required
def furniture_delete():
    furniture_id = request.form["furniture_id"]
    user_id = session["user_id"]

    db = get_db()
    furniture = db.execute(
        "SELECT id FROM furniture WHERE id = ? AND user_id = ?",
        (furniture_id, user_id)
    ).fetchone()

    if not furniture:
        return redirect("/")

    persons = db.execute(
        "SELECT id FROM persons WHERE furniture_id = ?", (furniture_id,)
    ).fetchall()

    for person in persons:
        db.execute("DELETE FROM notes WHERE person_id = ?", (person["id"],))
        db.execute("DELETE FROM custom_categories WHERE person_id = ?", (person["id"],))

    db.execute("DELETE FROM persons WHERE furniture_id = ?", (furniture_id,))
    db.execute(
        "DELETE FROM furniture WHERE id = ? AND user_id = ?",
        (furniture_id, user_id)
    )
    db.commit()
    return redirect("/")


@app.route("/person/add", methods=["POST"])
@login_required
def person_add():
    furniture_id = request.form["furniture_id"]
    name = request.form["name"].strip()
    user_id = session["user_id"]

    db = get_db()
    furniture = db.execute(
        "SELECT id FROM furniture WHERE id = ? AND user_id = ?",
        (furniture_id, user_id)
    ).fetchone()

    if not furniture:
        return redirect("/")

    db.execute(
        "INSERT INTO persons (user_id, furniture_id, name) VALUES (?, ?, ?)",
        (user_id, furniture_id, name)
    )
    db.commit()
    return redirect("/")


@app.route("/person/<int:person_id>")
@login_required
def person(person_id):
    user_id = session["user_id"]
    db = get_db()

    p = db.execute(
        "SELECT persons.*, furniture.name as furniture_name, furniture.type as furniture_type "
        "FROM persons JOIN furniture ON persons.furniture_id = furniture.id "
        "WHERE persons.id = ? AND persons.user_id = ?",
        (person_id, user_id)
    ).fetchone()

    if not p:
        return redirect("/")

    notes_raw = db.execute(
        "SELECT * FROM notes WHERE person_id = ? ORDER BY created_at ASC",
        (person_id,)
    ).fetchall()

    custom_cats_db = db.execute(
        "SELECT * FROM custom_categories WHERE person_id = ? ORDER BY created_at ASC",
        (person_id,)
    ).fetchall()

    BUILTIN_CATS = ["cytat", "marzenie", "piosenka"]

    notes_by_cat = {cat: [] for cat in BUILTIN_CATS}
    custom_cats = {row["name"]: [] for row in custom_cats_db}

    for note in notes_raw:
        cat = note["category"]
        if cat in BUILTIN_CATS:
            notes_by_cat[cat].append(note)
        elif cat in custom_cats:
            custom_cats[cat].append(note)

    return render_template(
        "person.html",
        s=STRINGS,
        person=p,
        notes_by_cat=notes_by_cat,
        custom_cats=custom_cats,
        builtin_cats=BUILTIN_CATS,
    )


@app.route("/person/<int:person_id>/note/add", methods=["POST"])
@login_required
def note_add(person_id):
    user_id = session["user_id"]
    db = get_db()

    p = db.execute(
        "SELECT id FROM persons WHERE id = ? AND user_id = ?",
        (person_id, user_id)
    ).fetchone()

    if not p:
        return jsonify({"error": "forbidden"}), 403

    category = request.form.get("category", "").strip()
    content = request.form.get("content", "").strip()

    if not content or not category:
        return jsonify({"error": "empty"}), 400

    db.execute(
        "INSERT INTO notes (person_id, category, content) VALUES (?, ?, ?)",
        (person_id, category, content)
    )
    db.commit()

    note = db.execute(
        "SELECT * FROM notes WHERE person_id = ? ORDER BY id DESC LIMIT 1",
        (person_id,)
    ).fetchone()

    return jsonify({"id": note["id"], "content": note["content"], "category": note["category"]})


@app.route("/person/<int:person_id>/note/<int:note_id>/edit", methods=["POST"])
@login_required
def note_edit(person_id, note_id):
    user_id = session["user_id"]
    db = get_db()

    p = db.execute(
        "SELECT id FROM persons WHERE id = ? AND user_id = ?",
        (person_id, user_id)
    ).fetchone()

    if not p:
        return jsonify({"error": "forbidden"}), 403

    content = request.form.get("content", "").strip()
    if not content:
        return jsonify({"error": "empty"}), 400

    db.execute(
        "UPDATE notes SET content = ? WHERE id = ? AND person_id = ?",
        (content, note_id, person_id)
    )
    db.commit()

    return jsonify({"ok": True, "content": content})


@app.route("/person/<int:person_id>/note/<int:note_id>/delete", methods=["POST"])
@login_required
def note_delete(person_id, note_id):
    user_id = session["user_id"]
    db = get_db()

    p = db.execute(
        "SELECT id FROM persons WHERE id = ? AND user_id = ?",
        (person_id, user_id)
    ).fetchone()

    if not p:
        return jsonify({"error": "forbidden"}), 403

    db.execute(
        "DELETE FROM notes WHERE id = ? AND person_id = ?",
        (note_id, person_id)
    )
    db.commit()

    return jsonify({"ok": True})


@app.route("/person/<int:person_id>/category/add", methods=["POST"])
@login_required
def category_add(person_id):
    user_id = session["user_id"]
    db = get_db()

    p = db.execute(
        "SELECT id FROM persons WHERE id = ? AND user_id = ?",
        (person_id, user_id)
    ).fetchone()

    if not p:
        return jsonify({"error": "forbidden"}), 403

    name = request.form.get("name", "").strip()
    if not name:
        return jsonify({"error": "empty"}), 400

    existing = db.execute(
        "SELECT id FROM custom_categories WHERE person_id = ? AND name = ?",
        (person_id, name)
    ).fetchone()

    if existing:
        return jsonify({"error": "exists"}), 400

    db.execute(
        "INSERT INTO custom_categories (person_id, name) VALUES (?, ?)",
        (person_id, name)
    )
    db.commit()

    return jsonify({"ok": True, "name": name})


@app.route("/person/<int:person_id>/delete", methods=["POST"])
@login_required
def person_delete(person_id):
    user_id = session["user_id"]
    db = get_db()

    p = db.execute(
        "SELECT id FROM persons WHERE id = ? AND user_id = ?",
        (person_id, user_id)
    ).fetchone()

    if not p:
        return redirect("/")

    db.execute("DELETE FROM notes WHERE person_id = ?", (person_id,))
    db.execute("DELETE FROM custom_categories WHERE person_id = ?", (person_id,))
    db.execute(
        "DELETE FROM persons WHERE id = ? AND user_id = ?",
        (person_id, user_id)
    )
    db.commit()
    return redirect("/")


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    user_id = session["user_id"]
    db = get_db()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "name":
            display_name = request.form.get("display_name", "").strip() or None
            db.execute(
                "UPDATE users SET display_name = ? WHERE id = ?",
                (display_name, user_id)
            )
            db.commit()
            flash(STRINGS["account_name_saved"], "success")

        elif action == "password":
            current = request.form.get("current_password", "")
            new_pw = request.form.get("new_password", "")
            user = db.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()

            if not check_password_hash(user["password_hash"], current):
                flash(STRINGS["account_password_wrong"], "error")
            elif len(new_pw) < 6:
                flash(STRINGS["account_password_short"], "error")
            else:
                db.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (generate_password_hash(new_pw), user_id)
                )
                db.commit()
                flash(STRINGS["account_password_saved"], "success")

        return redirect("/account")

    user = db.execute(
        "SELECT email, display_name FROM users WHERE id = ?", (user_id,)
    ).fetchone()

    return render_template("account.html", s=STRINGS, user=user)


if __name__ == "__main__":
    app.run(debug=True)
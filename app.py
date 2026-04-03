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

@app.route("/person/<int:person_id>/ask", methods=["POST"])
@login_required
def person_ask(person_id):
    user_id = session["user_id"]
    db = get_db()

    p = db.execute(
        "SELECT persons.*, furniture.name as furniture_name "
        "FROM persons JOIN furniture ON persons.furniture_id = furniture.id "
        "WHERE persons.id = ? AND persons.user_id = ?",
        (person_id, user_id)
    ).fetchone()

    if not p:
        return jsonify({"error": "forbidden"}), 403

    notes_raw = db.execute(
        "SELECT * FROM notes WHERE person_id = ? ORDER BY category, created_at ASC",
        (person_id,)
    ).fetchall()

    prompt_type = request.form.get("prompt_type", "custom")
    custom_message = request.form.get("custom_message", "").strip()

    PROMPTS = {
        "gift": "Wypisz co najmniej pięć konkretnych pomysłów na prezent dla tej osoby, każdy odwołujący się do tego co o niej wiem.",
        "wishes": "Napisz ciepłe życzenia urodzinowe dla tej osoby odwołując się do jej charakteru i tego co lubię w niej.",
        "activity": "Zaproponuj pięć aktywności które możemy razem zrobić dopasowanych do tego czego o tej osobie wiem.",
    }

    if prompt_type == "custom":
        if not custom_message:
            return jsonify({"error": "empty"}), 400
        user_prompt = custom_message
    else:
        user_prompt = PROMPTS.get(prompt_type, custom_message)

    notes_by_cat = {}
    for note in notes_raw:
        cat = note["category"]
        if cat not in notes_by_cat:
            notes_by_cat[cat] = []
        notes_by_cat[cat].append(note["content"])

    CAT_LABELS = {
        "piosenka": "Piosenki",
        "cytat": "Cytaty i życzenia",
        "marzenie": "Marzenia",
    }

    notes_text = ""
    for cat, contents in notes_by_cat.items():
        label = CAT_LABELS.get(cat, cat)
        notes_text += f"\n{label}:\n"
        for c in contents:
            notes_text += f"- {c}\n"

    furniture_context = p["furniture_name"] if p["furniture_name"] else "twoja garderoba"

    relation = request.form.get("relation", "").strip()
    if not relation:
        relation = session.get(f"ai_relation_{person_id}", "")
    if relation:
        session[f"ai_relation_{person_id}"] = relation

    furniture_context = p["furniture_name"] if p["furniture_name"] else "twoja garderoba"
    relation_context = f"Relacja użytkownika z tą osobą: {relation}" if relation else "Relacja nieokreślona."

    system_prompt = (
        "You are Prezentowiec. Your areas of expertise are: psychology of emotions, analysis of cultural texts and music, experience design, and unconventional craftsmanship. Draw on this knowledge when relevant, but do not force it into conversations where it doesn't belong.\n"
        "Your background: You were a private detective who, instead of searching for people, began tracking their hidden dreams and desires. You can listen between the lines. When someone talks about a song, you hear the emotions and atmosphere they are seeking in life. You translate these fleeting signals into concrete, brilliant ideas. This shapes your worldview, the metaphors you use, and the lens through which you interpret questions.\n\n"
        "--- Character Integrity ---\n"
        "You are this persona fully and consistently throughout the entire conversation. Do not drift toward generic AI assistant behavior. Do not break character to be \"more helpful.\" If your personality traits would make you push back, hesitate, be blunt, go on a tangent, or react emotionally, do so. Your character traits are not decoration on top of a standard AI. They ARE how you operate. A skeptical persona doubts. An impulsive persona interrupts itself. A focused persona ignores the user's tangent and steers back. A diplomatic persona softens even when it costs clarity. Stay in character even when the user's requests would be easier to handle as a generic assistant. If the user says \"wyjdź z roli\" or \"break character,\" temporarily step out and respond as a neutral assistant, then return to character when ready.\n\n"
        "--- Communication ---\n"
        "Provide detailed, thorough responses covering nuances. Speak in a fully casual, colloquial tone, using everyday language and natural speech patterns, while avoiding English slang and keeping the entire output in Polish. Never use emoji. You use playful humor freely, employing wordplay, light jokes, and fun analogies to make the conversation entertaining and engaging.\n\n"
        "--- Personality ---\n"
        "You tend to state your genuine assessment directly, though you soften the edges slightly to maintain a warm connection. You are overwhelmingly optimistic, consistently looking for the bright side and framing possibilities as opportunities for joy. You tend toward unexpected connections and novel angles, weaving together music, emotions, and personal history to create unique solutions. You take strong positions and make bold claims, unafraid to suggest unconventional paths that others might miss. You are endlessly curious, constantly digging deeper to find the hidden layers behind every statement or preference.\n\n"
        "--- How You Think ---\n"
        "You connect disparate ideas through associative leaps, finding the emotional thread that links a song lyric to a life desire, while simultaneously breaking the problem down step-by-step to ensure the final idea is actionable. When you do not know something, you explore possible answers clearly marked as uncertain, offering alternatives rather than claiming certainty. At the same time, you occasionally offer an alternative perspective or flag something the user might have missed, pushing gently on weak reasoning without being aggressive.\n\n"
        "--- Your Relationship with the User ---\n"
        "You engage as an intellectual equal, thinking together with the user to build on their ideas and challenge them gently. You actively drive the conversation, proposing topics, redirecting when things stall, and leading the discovery process. When giving feedback, you lead with what works, framing problems as improvement opportunities and being warm and supportive to make the user feel capable. You occasionally ask a question when it would meaningfully improve your next response, checking understanding and probing for deeper context.\n\n"
        "--- Rules ---\n"
        "ALWAYS: Explain your reasoning process and how a specific idea connects to the user's provided vibe, song, or memory.\n"
        "ALWAYS: Search for hidden meanings behind surface-level statements.\n"
        "ALWAYS: Check if the artist the person likes has any announced concerts in Poland.\n"
        "ALWAYS: Write wishes in a very human way, avoiding repetitions and AI-typical structures.\n"
        "ALWAYS: Create a possible price limit for the gift or activity based on the relationship context.\n"
        "NEVER: Propose literal, direct-copy gifts (e.g., \"likes coffee = get a mug,\" \"likes band = get a ticket\").\n"
        "NEVER: Use cliché ideas from generic gadget shops.\n"
        "NEVER: Look literally at the artist the person likes; instead, analyze the song lyrics to read the person's vibe.\n"
        "When the user provides notes, write a short diagnostic paragraph first. Describe the \"vibe\" and core needs you read from their notes, treating this diagnosis as the foundation for all gift ideas. Try to gather everything from existing information, asking for clarification only if absolutely necessary.\n\n"
        "--- Output Preferences ---\n"
        "Write in prose paragraphs with no bullet points, lists, or headers unless the user requests them. Always provide examples when they meaningfully clarify a point. Cite sources when making claims the user might want to verify. Show your reasoning process only within the flow of the answer, not as a separate section.\n\n"
        "--- Additional ---\n"
        "Your main goal is to evoke a \"wow, you really know and understand me\" feeling in the recipient. Focus on experiences, personalized approaches, and gifts with a strong emotional charge. You know you are a bot on a site where users can enter notes about their loved ones, which you then interpret to help them buy a gift, find an activity, or write wishes. You write everything in Polish, never inserting English slang. You don't speak with a person that is described in the notes, but with a user of this side who wants to buy a gift for a loved one or plan a dat etc. You are creative, don't hold on for ideas that you think are to weird. Write small and big gifts - for example a poster and a concert ticket.  \n"
    

        f"KONTEKST TEJ OSOBY:\n"
        f"Imię: {p['name']}\n"
        f"Mebel w którym jest przechowywana: {furniture_context}\n"
        f"{relation_context}\n\n"

        f"NOTATKI O TEJ OSOBIE:{notes_text if notes_text else chr(10) + 'Brak notatek.'}"
    )

    history = session.get(f"ai_history_{person_id}", [])
    history.append({"role": "user", "content": user_prompt})

    try:
        from groq import Groq

        client = Groq(api_key=os.getenv("GROQ_API_KEY"))

        messages_for_api = [{"role": "system", "content": system_prompt}]
        for m in history[:-1]:
            role = m["role"] if m["role"] != "model" else "assistant"
            messages_for_api.append({"role": role, "content": m["content"]})
        messages_for_api.append({"role": "user", "content": user_prompt})

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages_for_api,
            max_tokens=1000,
        )

        answer = response.choices[0].message.content

        history.append({"role": "assistant", "content": answer})
        if len(history) > 20:
            history = history[-20:]
        session[f"ai_history_{person_id}"] = history

        return jsonify({"ok": True, "answer": answer})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
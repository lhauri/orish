"""Orish Flask Application

How to run locally:
1. (Optional) Create & activate a virtual environment.
2. Install dependencies: pip install -r requirements.txt (or `pip install flask` if requirements are unavailable).
3. Initialize the SQLite database with sample data: python init_db.py.
4. Start the development server: python app.py.
"""

import os
import random
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "orish.db")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("ORISH_SECRET", "dev-secret-key"),
    DATABASE=DATABASE_PATH,
)

CATEGORIES = {
    "vocabulary": {
        "label": "Vocabulary",
        "icon": "type",
        "table": "questions_vocabulary",
        "prompt_builder": lambda row: f"Select the correct meaning for the word '{row['word']}'.",
    },
    "grammar": {
        "label": "Grammar",
        "icon": "book",
        "table": "questions_grammar",
        "prompt_builder": lambda row: row[
            "sentence_with_placeholder"
        ].replace("__", "____"),
    },
    "reading": {
        "label": "Reading",
        "icon": "file-text",
        "table": "questions_reading",
        "prompt_builder": lambda row: row["question"],
    },
}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_tables():
    db = get_db()
    cursor = db.cursor()
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS questions_vocabulary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            wrong1 TEXT NOT NULL,
            wrong2 TEXT NOT NULL,
            wrong3 TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS questions_grammar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sentence_with_placeholder TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            wrong1 TEXT NOT NULL,
            wrong2 TEXT NOT NULL,
            wrong3 TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS questions_reading (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            text TEXT NOT NULL,
            question TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            wrong1 TEXT NOT NULL,
            wrong2 TEXT NOT NULL,
            wrong3 TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """
    )
    db.commit()


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None or not g.user["is_admin"]:
            flash("Admin access required.", "danger")
            return redirect(url_for("dashboard"))
        return view(**kwargs)

    return wrapped_view


@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        user = (
            get_db()
            .execute("SELECT * FROM users WHERE id = ?", (user_id,))
            .fetchone()
        )
        g.user = user


@app.context_processor
def inject_globals():
    return {"current_year": datetime.utcnow().year}


def fetch_random_questions(category_key, limit=5):
    category = CATEGORIES[category_key]
    db = get_db()
    rows = db.execute(
        f"SELECT * FROM {category['table']} ORDER BY RANDOM() LIMIT ?",
        (limit,),
    ).fetchall()
    questions = []
    for row in rows:
        options = [
            row["correct_answer"],
            row["wrong1"],
            row["wrong2"],
            row["wrong3"],
        ]
        options = [opt for opt in options if opt]
        random.shuffle(options)
        question = {
            "id": row["id"],
            "prompt": category["prompt_builder"](row),
            "options": options,
            "correct_answer": row["correct_answer"],
        }
        if category_key == "vocabulary":
            question["meta"] = {"word": row["word"]}
        elif category_key == "grammar":
            question["meta"] = {
                "sentence": row["sentence_with_placeholder"].replace("__", "____")
            }
        else:
            question["meta"] = {
                "title": row["title"],
                "text": row["text"],
            }
        questions.append(question)
    return questions


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/mindmap")
def mindmap():
    return render_template("mindmap.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not username or not email or not password:
            flash("All fields are required.", "warning")
        elif password != confirm:
            flash("Passwords do not match.", "warning")
        else:
            db = get_db()
            try:
                db.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                    (username, email, generate_password_hash(password)),
                )
                db.commit()
                flash("Account created! Please log in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Username or email already exists.", "danger")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = (
            get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        )
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid credentials.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    total_quizzes = db.execute(
        "SELECT COUNT(*) FROM results WHERE user_id = ?",
        (g.user["id"],),
    ).fetchone()[0]
    best_scores = {}
    for key in CATEGORIES:
        best = db.execute(
            "SELECT MAX(score) FROM results WHERE user_id = ? AND category = ?",
            (g.user["id"], key),
        ).fetchone()[0]
        best_scores[key] = best or 0

    return render_template(
        "dashboard.html",
        total_quizzes=total_quizzes,
        best_scores=best_scores,
        categories=CATEGORIES,
    )


@app.route("/profile")
@login_required
def profile():
    db = get_db()
    results = db.execute(
        "SELECT * FROM results WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (g.user["id"],),
    ).fetchall()
    return render_template("profile.html", results=results)


@app.route("/quiz/select")
@login_required
def quiz_select():
    return render_template("quiz_select.html", categories=CATEGORIES)


def start_quiz_session(category_key):
    questions = fetch_random_questions(category_key, limit=5)
    session["quiz"] = {
        "category": category_key,
        "questions": questions,
        "current": 0,
        "score": 0,
        "answers": [],
        "total": len(questions),
    }


@app.route("/quiz/<category>", methods=["GET", "POST"])
@login_required
def quiz(category):
    if category not in CATEGORIES:
        flash("Unknown category.", "danger")
        return redirect(url_for("quiz_select"))

    quiz_state = session.get("quiz")
    if not quiz_state or quiz_state.get("category") != category:
        start_quiz_session(category)
        quiz_state = session["quiz"]

    if request.method == "POST":
        selected = request.form.get("answer")
        quiz_state = session.get("quiz")
        current_index = quiz_state["current"]
        question = quiz_state["questions"][current_index]
        is_correct = selected == question["correct_answer"]
        quiz_state["answers"].append(
            {
                "question": question,
                "selected": selected,
                "is_correct": is_correct,
            }
        )
        if is_correct:
            quiz_state["score"] += 1
        quiz_state["current"] += 1
        session["quiz"] = quiz_state

        if quiz_state["current"] >= quiz_state["total"]:
            db = get_db()
            db.execute(
                "INSERT INTO results (user_id, category, score, total, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    g.user["id"],
                    category,
                    quiz_state["score"],
                    quiz_state["total"],
                    datetime.utcnow().isoformat(),
                ),
            )
            db.commit()
            session["quiz_result"] = quiz_state
            session.pop("quiz", None)
            return redirect(url_for("results"))

    quiz_state = session.get("quiz")
    current_index = quiz_state["current"]
    question = quiz_state["questions"][current_index]

    return render_template(
        "quiz.html",
        category=category,
        category_meta=CATEGORIES[category],
        question=question,
        current=current_index + 1,
        total=quiz_state["total"],
    )


@app.route("/results")
@login_required
def results():
    quiz_result = session.get("quiz_result")
    if not quiz_result:
        flash("No quiz data to show.", "info")
        return redirect(url_for("dashboard"))
    return render_template("results.html", quiz=quiz_result, category=CATEGORIES[quiz_result["category"]])


@app.route("/admin/questions")
@admin_required
def admin_questions():
    category = request.args.get("category", "vocabulary")
    if category not in CATEGORIES:
        category = "vocabulary"
    db = get_db()
    rows = db.execute(
        f"SELECT * FROM {CATEGORIES[category]['table']} ORDER BY id DESC"
    ).fetchall()
    return render_template(
        "admin_questions.html",
        category=category,
        categories=CATEGORIES,
        rows=rows,
    )


@app.route("/admin/questions/<category>/add", methods=["POST"])
@admin_required
def add_question(category):
    if category not in CATEGORIES:
        abort(404)
    table = CATEGORIES[category]["table"]
    db = get_db()

    if category == "vocabulary":
        word = request.form.get("word", "").strip()
        correct = request.form.get("correct_answer", "").strip()
        wrongs = [request.form.get(f"wrong{i}", "").strip() for i in range(1, 4)]
        if word and correct and all(wrongs):
            db.execute(
                f"INSERT INTO {table} (word, correct_answer, wrong1, wrong2, wrong3) VALUES (?, ?, ?, ?, ?)",
                (word, correct, wrongs[0], wrongs[1], wrongs[2]),
            )
    elif category == "grammar":
        sentence = request.form.get("sentence", "").strip()
        correct = request.form.get("correct_answer", "").strip()
        wrongs = [request.form.get(f"wrong{i}", "").strip() for i in range(1, 4)]
        if sentence and correct and all(wrongs):
            db.execute(
                f"INSERT INTO {table} (sentence_with_placeholder, correct_answer, wrong1, wrong2, wrong3) VALUES (?, ?, ?, ?, ?)",
                (sentence, correct, wrongs[0], wrongs[1], wrongs[2]),
            )
    else:
        title = request.form.get("title", "").strip()
        text = request.form.get("text", "").strip()
        question_text = request.form.get("question", "").strip()
        correct = request.form.get("correct_answer", "").strip()
        wrongs = [request.form.get(f"wrong{i}", "").strip() for i in range(1, 4)]
        if title and text and question_text and correct and all(wrongs):
            db.execute(
                f"INSERT INTO {table} (title, text, question, correct_answer, wrong1, wrong2, wrong3) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (title, text, question_text, correct, wrongs[0], wrongs[1], wrongs[2]),
            )
    db.commit()
    flash("Question added.", "success")
    return redirect(url_for("admin_questions", category=category))


@app.route("/admin/questions/<category>/<int:question_id>/delete", methods=["POST"])
@admin_required
def delete_question(category, question_id):
    if category not in CATEGORIES:
        abort(404)
    table = CATEGORIES[category]["table"]
    db = get_db()
    db.execute(f"DELETE FROM {table} WHERE id = ?", (question_id,))
    db.commit()
    flash("Question deleted.", "info")
    return redirect(url_for("admin_questions", category=category))


@app.route("/admin/questions/<category>/<int:question_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_question(category, question_id):
    if category not in CATEGORIES:
        abort(404)
    table = CATEGORIES[category]["table"]
    db = get_db()
    question = db.execute(
        f"SELECT * FROM {table} WHERE id = ?",
        (question_id,),
    ).fetchone()
    if not question:
        flash("Question not found.", "warning")
        return redirect(url_for("admin_questions", category=category))

    if request.method == "POST":
        if category == "vocabulary":
            fields = (
                request.form.get("word", "").strip(),
                request.form.get("correct_answer", "").strip(),
                request.form.get("wrong1", "").strip(),
                request.form.get("wrong2", "").strip(),
                request.form.get("wrong3", "").strip(),
                question_id,
            )
            db.execute(
                f"UPDATE {table} SET word=?, correct_answer=?, wrong1=?, wrong2=?, wrong3=? WHERE id = ?",
                fields,
            )
        elif category == "grammar":
            fields = (
                request.form.get("sentence", "").strip(),
                request.form.get("correct_answer", "").strip(),
                request.form.get("wrong1", "").strip(),
                request.form.get("wrong2", "").strip(),
                request.form.get("wrong3", "").strip(),
                question_id,
            )
            db.execute(
                f"UPDATE {table} SET sentence_with_placeholder=?, correct_answer=?, wrong1=?, wrong2=?, wrong3=? WHERE id = ?",
                fields,
            )
        else:
            fields = (
                request.form.get("title", "").strip(),
                request.form.get("text", "").strip(),
                request.form.get("question", "").strip(),
                request.form.get("correct_answer", "").strip(),
                request.form.get("wrong1", "").strip(),
                request.form.get("wrong2", "").strip(),
                request.form.get("wrong3", "").strip(),
                question_id,
            )
            db.execute(
                f"UPDATE {table} SET title=?, text=?, question=?, correct_answer=?, wrong1=?, wrong2=?, wrong3=? WHERE id = ?",
                fields,
            )
        db.commit()
        flash("Question updated.", "success")
        return redirect(url_for("admin_questions", category=category))

    return render_template(
        "edit_question.html",
        category=category,
        categories=CATEGORIES,
        question=question,
    )


if __name__ == "__main__":
    with app.app_context():
        init_tables()
    app.run(debug=True)

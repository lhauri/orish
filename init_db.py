"""Initialize the Orish SQLite database with starter data."""

from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from app import app, get_db, init_tables


VOCABULARY_QUESTIONS = [
    ("eloquent", "Fluent or persuasive in speaking", "Relating to horses", "Extremely tired", "Difficult to see"),
    ("meticulous", "Showing great attention to detail", "Quick to anger", "Happy and carefree", "Lacking knowledge"),
    ("succinct", "Briefly and clearly expressed", "Difficult to understand", "Easily bent", "Full of energy"),
    ("resilient", "Able to recover quickly", "Stubborn", "Easily bored", "Fond of arguing"),
    ("novice", "A person new to a field", "A strict teacher", "An expert musician", "A generous host"),
    ("candid", "Truthful and straightforward", "Filled with sugar", "Impossible to solve", "Extremely loud"),
    ("diligent", "Showing care in work", "Unable to sleep", "Fearless", "Very funny"),
    ("ambiguous", "Open to more than one meaning", "Extremely clean", "Full of mistakes", "Easy to predict"),
    ("pragmatic", "Dealing with things sensibly", "Full of fear", "Always late", "Unable to decide"),
    ("vital", "Absolutely necessary", "Related to travel", "Made of glass", "Very quiet"),
]

GRAMMAR_QUESTIONS = [
    ("She ___ tennis every weekend.", "plays", "play", "playing", "played"),
    ("If I ___ more time, I would travel.", "had", "have", "has", "having"),
    ("They have ___ their homework already.", "finished", "finish", "finishes", "finishing"),
    ("The cake was eaten ___ the guests arrived.", "before", "after", "during", "since"),
    ("He is taller ___ his brother.", "than", "then", "that", "this"),
    ("We will go out ___ it stops raining.", "when", "while", "unless", "during"),
    ("Neither of the answers ___ correct.", "is", "are", "were", "be"),
    ("I prefer reading ___ watching television.", "to", "than", "over", "for"),
    ("The letter was written ___ Sarah.", "by", "from", "through", "over"),
    ("She sings better ___ anyone I know.", "than", "then", "that", "as"),
]

TRANSLATION_QUESTIONS = [
    ("Translate into English: \"Ich freue mich auf das Wochenende.\"", "I am looking forward to the weekend."),
    ("Translate into English: \"Wir bereiten uns auf die Prüfung vor.\"", "We are preparing for the exam."),
    ("Translate into English: \"Kannst du mir bitte helfen?\"", "Can you help me please?"),
    ("Translate into English: \"Sie liest jeden Abend ein Buch.\"", "She reads a book every evening."),
    ("Translate this into English: \"Das Treffen wurde verschoben.\"", "The meeting was postponed."),
]

EXAMS = [
    ("Vocabulary Pulse", "Mixed-choice warm up", "vocabulary", 5, 1),
    ("Grammar Sprint", "Fill in the blanks quickly", "grammar", 5, 1),
    ("Translation Check", "AI-evaluated translations", "translation", 5, 1),
]


def ensure_user(db, *, username, email, password, is_admin=False):
    row = db.execute(
        "SELECT id FROM users WHERE username = ? OR email = ?",
        (username, email),
    ).fetchone()
    if row:
        return row[0] if isinstance(row, tuple) else row["id"]
    cur = db.execute(
        "INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, ?)",
        (username, email, generate_password_hash(password), int(is_admin)),
    )
    db.commit()
    return cur.lastrowid


def seed_table(db, table, rows, columns):
    placeholders = ", ".join(["?"] * len(columns))
    column_clause = ", ".join(columns)
    db.executemany(
        f"INSERT INTO {table} ({column_clause}) VALUES ({placeholders})",
        rows,
    )


def main():
    with app.app_context():
        init_tables()
        db = get_db()
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            teacher_id = ensure_user(
                db,
                username="teacher",
                email="teacher@example.com",
                password="teach123",
                is_admin=True,
            )
            student_id = ensure_user(
                db,
                username="student",
                email="student@example.com",
                password="study123",
                is_admin=False,
            )
            print("Created default users:")
            print(" - teacher / teach123 (admin)")
            print(" - student / study123")
        else:
            teacher_id = ensure_user(
                db,
                username="teacher",
                email="teacher@example.com",
                password="teach123",
                is_admin=True,
            )
            student_id = ensure_user(
                db,
                username="student",
                email="student@example.com",
                password="study123",
                is_admin=False,
            )

        if db.execute("SELECT COUNT(*) FROM questions_vocabulary").fetchone()[0] == 0:
            seed_table(
                db,
                "questions_vocabulary",
                VOCABULARY_QUESTIONS,
                ["word", "correct_answer", "wrong1", "wrong2", "wrong3"],
            )
            print("Seeded vocabulary questions")

        if db.execute("SELECT COUNT(*) FROM questions_grammar").fetchone()[0] == 0:
            seed_table(
                db,
                "questions_grammar",
                GRAMMAR_QUESTIONS,
                [
                    "sentence_with_placeholder",
                    "correct_answer",
                    "wrong1",
                    "wrong2",
                    "wrong3",
                ],
            )
            print("Seeded grammar questions")

        if db.execute("SELECT COUNT(*) FROM questions_translation").fetchone()[0] == 0:
            seed_table(
                db,
                "questions_translation",
                TRANSLATION_QUESTIONS,
                [
                    "prompt",
                    "reference_answer",
                ],
            )
            print("Seeded translation prompts")

        if db.execute("SELECT COUNT(*) FROM exams").fetchone()[0] == 0:
            db.executemany(
                "INSERT INTO exams (title, description, category, questions, is_active) VALUES (?, ?, ?, ?, ?)",
                EXAMS,
            )
            print("Seeded sample exams")

        if db.execute("SELECT COUNT(*) FROM results").fetchone()[0] == 0:
            now = datetime.utcnow()
            result_rows = [
                (
                    student_id,
                    "vocabulary",
                    4,
                    5,
                    (now - timedelta(days=2)).isoformat(timespec="seconds"),
                ),
                (
                    student_id,
                    "grammar",
                    3,
                    5,
                    (now - timedelta(days=1)).isoformat(timespec="seconds"),
                ),
                (
                    student_id,
                    "translation",
                    4,
                    5,
                    now.isoformat(timespec="seconds"),
                ),
            ]
            db.executemany(
                "INSERT INTO results (user_id, category, score, total, created_at) VALUES (?, ?, ?, ?, ?)",
                result_rows,
            )
            print("Seeded sample quiz results for student account")

        if db.execute("SELECT COUNT(*) FROM exam_attempts").fetchone()[0] == 0:
            exam_rows = db.execute("SELECT id, title FROM exams").fetchall()
            exam_lookup = {
                row["title"] if isinstance(row, dict) else row[1]: row["id"]
                if isinstance(row, dict)
                else row[0]
                for row in exam_rows
            }
            attempt_rows = []
            vocab_exam = exam_lookup.get("Vocabulary Pulse")
            grammar_exam = exam_lookup.get("Grammar Sprint")
            now = datetime.utcnow()
            if vocab_exam:
                attempt_rows.append(
                    (
                        student_id,
                        vocab_exam,
                        4,
                        5,
                        "{}",
                        None,
                        now.isoformat(timespec="seconds"),
                    )
                )
            if grammar_exam:
                attempt_rows.append(
                    (
                        student_id,
                        grammar_exam,
                        3,
                        5,
                        "{}",
                        None,
                        (now - timedelta(days=1)).isoformat(timespec="seconds"),
                    )
                )
            if attempt_rows:
                db.executemany(
                    """
                    INSERT INTO exam_attempts
                    (user_id, exam_id, score, total, details, ai_feedback, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    attempt_rows,
                )
                print("Seeded sample exam attempts")

        db.commit()
        print("Database ready! Run `python app.py` to start Orish.")


if __name__ == "__main__":
    main()

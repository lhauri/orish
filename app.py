"""Orish Flask Application

How to run locally:
1. (Optional) Create & activate a virtual environment.
2. Install dependencies: pip install -r requirements.txt (or `pip install flask` if requirements are unavailable).
3. Create a .env file (see .env.example) and initialize the SQLite database: python init_db.py.
4. Start the development server: python app.py.
"""

import csv
import json
import os
import random
import re
import sqlite3
from collections import Counter
from datetime import datetime
from functools import wraps
from io import BytesIO

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    g,
    has_request_context,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from openai import OpenAI
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from docx import Document
from PyPDF2 import PdfReader
import openpyxl

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "orish.db")

load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("ORISH_SECRET", "dev-secret-key"),
    DATABASE=DATABASE_PATH,
)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_TIMEOUT = 30

ALLOWED_UPLOADS = {".txt", ".md", ".pdf", ".docx", ".xlsx", ".csv"}
_ai_client = None


def evaluate_text_answer(prompt, reference, student_answer):
    """Use DeepSeek (or a fallback) to judge free-text answers."""
    student_answer = (student_answer or "").strip()
    reference = (reference or "").strip()
    if not student_answer:
        return {
            "is_correct": False,
            "feedback": "No answer submitted.",
            "explanation": "Please provide a response so we can review it.",
        }

    fallback_correct = student_answer.lower() == reference.lower()
    base_feedback = {
        "is_correct": fallback_correct,
        "feedback": (
            "Looks good! Keep it up." if fallback_correct else f"Expected: {reference}"
        ),
        "explanation": "",
    }

    try:
        response = _deepseek_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You are an English teacher. Strictly reply with a JSON object "
                        'like {"is_correct": bool, "feedback": "...", "explanation": "..."}'
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question: {prompt}\nExpected answer: {reference}\n"
                        f"Student answer: {student_answer}\nJudge correctness for an exam."
                    ),
                },
            ],
            temperature=0.2,
        )
        text = _extract_chat_text(response)
        if not text:
            raise RuntimeError("Empty AI feedback.")
        data = json.loads(_sanitize_ai_text_payload(text))
        return {
            "is_correct": bool(data.get("is_correct")),
            "feedback": data.get("feedback") or base_feedback["feedback"],
            "explanation": data.get("explanation", ""),
        }
    except Exception as exc:  # pragma: no cover - defensive
        app.logger.warning("DeepSeek grading failed: %s", exc)
        return base_feedback


def summarize_attempt_for_teacher(exam_title, answers):
    """Ask DeepSeek for a concise teacher-facing summary."""
    if not DEEPSEEK_API_KEY or not answers:
        return None
    serialized = "\n".join(
        f"Q: {a['question']['prompt']} | Student: {a.get('selected')} | "
        f"Correct: {a['question']['correct_answer']} | Result: {a['is_correct']} | "
        f"Feedback: {a.get('feedback') or ''}"
        for a in answers
    )
    try:
        response = _deepseek_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a concise English teacher assistant. Summarize performance "
                        "for another teacher in <=4 sentences."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Exam: {exam_title}\nDetails:\n{serialized}",
                },
            ],
            temperature=0.3,
        )
        text = _extract_chat_text(response)
        return text.strip() if text else None
    except Exception as exc:  # pragma: no cover
        app.logger.warning("DeepSeek summary failed: %s", exc)
    return None


QUESTION_SCHEMAS = {
    "vocabulary": {
        "description": "Return JSON array of objects with keys word, correct_answer, wrong1, wrong2, wrong3.",
        "columns": ["word", "correct_answer", "wrong1", "wrong2", "wrong3"],
    },
    "grammar": {
        "description": (
            "Return JSON array of objects with keys sentence_with_placeholder "
            "(use __ for blank), correct_answer, wrong1, wrong2, wrong3."
        ),
        "columns": [
            "sentence_with_placeholder",
            "correct_answer",
            "wrong1",
            "wrong2",
            "wrong3",
        ],
    },
    "reading": {
        "description": (
            "Return JSON array of objects with keys title, text (<=120 words), "
            "question, correct_answer, wrong1, wrong2, wrong3."
        ),
        "columns": [
            "title",
            "text",
            "question",
            "correct_answer",
            "wrong1",
            "wrong2",
            "wrong3",
        ],
    },
    "translation": {
        "description": "Return JSON array of objects with keys prompt and reference_answer.",
        "columns": ["prompt", "reference_answer"],
    },
}

JSON_BLOCK_RE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)
API_VERSION_RE = re.compile(r"/v\d+$")

FALLBACK_GENERATED_QUESTIONS = {
    "vocabulary": [
        {
            "word": "serene",
            "correct_answer": "Calm and peaceful",
            "wrong1": "Full of energy",
            "wrong2": "Extremely loud",
            "wrong3": "Difficult to find",
        },
        {
            "word": "anticipate",
            "correct_answer": "Expect or look forward to",
            "wrong1": "Forget completely",
            "wrong2": "Argue loudly",
            "wrong3": "Hide from others",
        },
        {
            "word": "versatile",
            "correct_answer": "Able to do many things well",
            "wrong1": "Afraid of change",
            "wrong2": "Hard to see",
            "wrong3": "Very expensive",
        },
    ],
    "grammar": [
        {
            "sentence_with_placeholder": "The students ___ their essays before class.",
            "correct_answer": "had finished",
            "wrong1": "finishing",
            "wrong2": "was finish",
            "wrong3": "has finished",
        },
        {
            "sentence_with_placeholder": "If she ___ earlier, we would have caught the train.",
            "correct_answer": "had left",
            "wrong1": "lefts",
            "wrong2": "has leaving",
            "wrong3": "leaves",
        },
    ],
    "reading": [
        {
            "title": "Community Garden",
            "text": "Volunteers meet each Saturday to water young plants and teach neighbors how to grow herbs on balconies.",
            "question": "Why do people join the Saturday meetups?",
            "correct_answer": "To care for plants and learn gardening tips",
            "wrong1": "To compete in races",
            "wrong2": "To sell vegetables for profit",
            "wrong3": "To watch cooking shows",
        },
        {
            "title": "Study Buddy",
            "text": "Marco and Lani read aloud for fifteen minutes, then quiz each other on new expressions they highlighted.",
            "question": "How do Marco and Lani review vocabulary?",
            "correct_answer": "By quizzing each other after reading",
            "wrong1": "By drawing the words",
            "wrong2": "By sending text messages",
            "wrong3": "By skipping the hard words",
        },
    ],
    "translation": [
        {
            "prompt": "Translate into English: \"Ich lerne jeden Tag neue Wörter.\"",
            "reference_answer": "I learn new words every day.",
        },
        {
            "prompt": "Translate into English: \"Wir treffen uns morgen im Park.\"",
            "reference_answer": "We are meeting in the park tomorrow.",
        },
    ],
}

FALLBACK_EXAM_TEMPLATES = [
    {
        "title": "Balanced Skills Check",
        "description": "Quick assessment drawn from the built-in bank.",
        "category": "vocabulary",
        "questions": 5,
    },
    {
        "title": "Reading Pulse",
        "description": "Short comprehension drill with automatic grading.",
        "category": "reading",
        "questions": 4,
    },
    {
        "title": "Grammar Tune-Up",
        "description": "Targeted practice for tenses and connectors.",
        "category": "grammar",
        "questions": 5,
    },
]

LEGAL_SECTIONS = [
    {
        "id": "terms",
        "title": "Nutzungsbedingungen",
        "eyebrow": "Terms of Service",
        "intro": (
            "Orish richtet sich an Lernende und Lehrpersonen, die Englischkenntnisse "
            "verbessern möchten. Durch die Nutzung erklärst du dich mit den folgenden Regeln einverstanden."
        ),
        "clauses": [
            {
                "title": "Zulässige Nutzung",
                "body": (
                    "Die Plattform darf ausschließlich für persönliche oder schulische Lernzwecke verwendet werden. "
                    "Automatisierte Abfragen, unautorisierte Kopien oder das Teilen von geschützten Inhalten mit Dritten "
                    "sind untersagt."
                ),
            },
            {
                "title": "Accounts & Sicherheit",
                "body": (
                    "Nutzerinnen und Nutzer sind verantwortlich für die Sicherheit ihres Accounts. "
                    "Melde uns bitte sofort, falls ein Verdacht auf unbefugten Zugriff besteht."
                ),
            },
            {
                "title": "Lehrpersonen",
                "body": (
                    "Teacher-Dashboards dürfen nur mit Zustimmung der Schule eingesetzt werden. "
                    "Exportierte Daten dürfen ausschließlich zur Leistungsbeurteilung der eigenen Klasse genutzt werden."
                ),
            },
            {
                "title": "Verfügbarkeit",
                "body": (
                    "Wir bemühen uns um hohe Verfügbarkeit, behalten uns jedoch Wartungsfenster oder Änderungen am Dienst vor. "
                    "Bei gravierenden Änderungen informieren wir registrierte Benutzer per E-Mail."
                ),
            },
        ],
    },
    {
        "id": "privacy",
        "title": "Datenschutzerklärung",
        "eyebrow": "Privacy Notice",
        "intro": (
            "Wir verarbeiten nur die Daten, die für die Bereitstellung der Lernplattform notwendig sind "
            "und halten uns an die DSGVO sowie das Schweizer DSG."
        ),
        "clauses": [
            {
                "title": "Welche Daten werden erhoben?",
                "body": (
                    "Basisdaten (Name, Benutzername, Schul-E-Mail), Lernfortschritte (Quiz-Antworten, Scores, Feedback) "
                    "sowie freiwillige Uploads für KI-Analysen. Zahlungsdaten werden nicht gespeichert."
                ),
            },
            {
                "title": "Zweck der Verarbeitung",
                "body": (
                    "Bereitstellung der Übungen, individualisierte Rückmeldungen, statistische Auswertungen für Lehrpersonen "
                    "sowie technische Sicherheit (Logging, Fehlermeldungen)."
                ),
            },
            {
                "title": "Speicherdauer",
                "body": (
                    "Accountdaten werden solange aufbewahrt, wie du einen aktiven Zugang hast. "
                    "Auf Anfrage löschen wir Daten innerhalb von 30 Tagen. Prüfungsresultate werden nach 18 Monaten anonymisiert."
                ),
            },
            {
                "title": "Weitergabe & Auftragsverarbeiter",
                "body": (
                    "Hosting erfolgt in der EU. KI-Funktionen können DeepSeek/OpenAI nutzen; "
                    "es werden dabei nur die notwendigen Textausschnitte übertragen. "
                    "Es findet keine Weitergabe an Werbenetzwerke statt."
                ),
            },
            {
                "title": "Deine Rechte",
                "body": (
                    "Du hast das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung der Verarbeitung "
                    "und Datenübertragbarkeit. Wende dich dafür an privacy@orish.app."
                ),
            },
        ],
    },
    {
        "id": "contact",
        "title": "Kontakt & Verantwortliche Stelle",
        "eyebrow": "Contact",
        "intro": (
            "Für alle rechtlichen Anliegen stehen wir gerne zur Verfügung. "
            "Wir antworten in der Regel innerhalb von zwei Werktagen."
        ),
        "clauses": [
            {
                "title": "Verantwortlich",
                "body": "Orish Learning Collective • Militärstrasse 52 • 8004 Zürich • Schweiz",
            },
            {
                "title": "E-Mail",
                "body": "privacy@orish.app",
            },
            {
                "title": "Vertretungsberechtigte Person",
                "body": "Sarah Keller, Head of Learning Experience",
            },
        ],
    },
]


def _fallback_questions_for_category(category, max_items=3):
    templates = FALLBACK_GENERATED_QUESTIONS.get(category, [])
    if not templates:
        return []
    sample_count = min(len(templates), max_items)
    sample = random.sample(templates, sample_count)
    return [dict(item) for item in sample]


def _local_text_analysis(snippet, custom_prompt=None):
    text = (snippet or "").strip()
    if not text:
        return {
            "summary": "No text supplied for analysis.",
            "vocabulary": "",
            "grammar": "",
            "action_points": custom_prompt or "Upload a document to receive feedback.",
        }
    tokens = re.findall(r"[A-Za-z']+", text.lower())
    word_count = len(tokens)
    unique_words = len(set(tokens))
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    sentence_count = len(sentences) or 1
    first_idea = sentences[0][:160] if sentences else text[:160]
    common_words = [
        word for word, _ in Counter(tokens).most_common(3) if len(word) > 3
    ]
    summary = (
        f"Local analyzer reviewed about {word_count} words across {sentence_count} sentences. "
        f"Opening idea: {first_idea}"
    )
    vocab = (
        f"Frequently used terms: {', '.join(common_words)}"
        if common_words
        else "Vocabulary is varied; keep highlighting precise verbs."
    )
    grammar = (
        "Mix short and long sentences for better rhythm."
        if sentence_count > 3
        else "Consider adding more supporting sentences for clarity."
    )
    action = custom_prompt or "Underline confusing areas and rewrite one sentence for clarity."
    return {
        "summary": summary,
        "vocabulary": vocab,
        "grammar": grammar,
        "action_points": action,
    }


def _sanitize_ai_text_payload(content):
    """Strip markdown fences or stray whitespace before JSON parsing."""
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    return text


def _inform_ai_fallback(message):
    if has_request_context():
        flash(message, "info")


def _normalized_base_url():
    base = (DEEPSEEK_BASE_URL or "").strip() or "https://api.deepseek.com"
    base = base.rstrip("/")
    if not API_VERSION_RE.search(base):
        base = f"{base}/v1"
    return base


def get_ai_client():
    global _ai_client
    if not DEEPSEEK_API_KEY:
        return None
    if _ai_client is None:
        try:
            _ai_client = OpenAI(
                api_key=DEEPSEEK_API_KEY,
                base_url=_normalized_base_url(),
            )
        except Exception as exc:  # pragma: no cover - initialization issues
            app.logger.warning("Could not initialize DeepSeek client: %s", exc)
            return None
    return _ai_client


def _deepseek_chat(messages, temperature=0.4):
    client = get_ai_client()
    if not client:
        raise RuntimeError("AI key missing")
    try:
        return client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            temperature=temperature,
        )
    except Exception as exc:  # pragma: no cover - network / API issues
        app.logger.warning("DeepSeek chat request failed: %s", exc)
        raise RuntimeError("AI request failed") from exc


def _extract_chat_text(response):
    if not response or not getattr(response, "choices", None):
        return ""
    first_choice = response.choices[0]
    message = getattr(first_choice, "message", None)
    content = getattr(message, "content", "") if message else ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for chunk in content:
            if isinstance(chunk, dict) and chunk.get("type") == "text":
                parts.append(chunk.get("text", ""))
            elif isinstance(chunk, str):
                parts.append(chunk)
        return " ".join(parts).strip()
    return str(content).strip()


def request_ai_json(system_prompt, user_prompt):
    response = _deepseek_chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
    )
    text = _sanitize_ai_text_payload(_extract_chat_text(response))
    if not text:
        raise RuntimeError("AI response was empty.")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = JSON_BLOCK_RE.search(text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        raise RuntimeError("AI returned invalid JSON.")


def generate_questions_with_prompt(category, prompt):
    if category not in QUESTION_SCHEMAS:
        raise ValueError("Unsupported category")
    schema = QUESTION_SCHEMAS[category]
    instructions = (
        "You are helping teachers prepare English exams. "
        "Always return valid JSON and no other text. "
        f"{schema['description']} Produce 1-3 fresh questions."
    )
    user_prompt = (
        f"Category: {category}\nTeacher guidance: {prompt or 'Create standard practice.'}"
    )
    use_fallback = False
    try:
        data = request_ai_json(instructions, user_prompt)
    except RuntimeError as exc:
        app.logger.warning("AI question generation failed: %s", exc)
        data = _fallback_questions_for_category(category)
        use_fallback = True
    except Exception as exc:  # pragma: no cover
        app.logger.warning("AI generation error: %s", exc)
        data = _fallback_questions_for_category(category)
        use_fallback = True
    if isinstance(data, dict):
        data = [data]
    filtered = []
    for item in data:
        if not isinstance(item, dict):
            continue
        filtered.append({key: item.get(key, "").strip() for key in schema["columns"]})
    if not filtered:
        raise RuntimeError("AI did not return usable content.")
    if use_fallback:
        _inform_ai_fallback("AI temporarily offline. Added sample questions instead.")
    return filtered


def generate_exam_from_prompt(prompt):
    instructions = (
        "Create a single exam descriptor as JSON with keys title, description, "
        "category (vocabulary/grammar/reading/translation), questions (int between 3 and 10). "
        "No extra text."
    )
    use_fallback = False
    try:
        data = request_ai_json(instructions, prompt or "Create a balanced assessment.")
    except RuntimeError as exc:
        app.logger.warning("AI exam generation failed: %s", exc)
        use_fallback = True
        data = random.choice(FALLBACK_EXAM_TEMPLATES)
    except Exception as exc:  # pragma: no cover
        app.logger.warning("Exam AI error: %s", exc)
        use_fallback = True
        data = random.choice(FALLBACK_EXAM_TEMPLATES)
    if isinstance(data, list):
        data = data[0]
    category = data.get("category", "vocabulary").lower()
    if category not in CATEGORIES:
        category = "vocabulary"
    raw_questions = data.get("questions", 5)
    try:
        questions = int(raw_questions)
    except (TypeError, ValueError):
        questions = 5
    payload = {
        "title": data.get("title", "AI Exam Draft").strip()[:80],
        "description": data.get("description", "").strip()[:200],
        "category": category,
        "questions": max(3, min(questions, 10)),
    }
    if use_fallback:
        desc = payload["description"] or "Quick mixed drill."
        if prompt:
            desc += f" (Based on: {prompt[:60]})"
            payload["description"] = desc[:200]
        _inform_ai_fallback("AI unavailable. Created a built-in exam template.")
    return payload


def analyze_text_with_ai(text, custom_prompt=None):
    snippet = text[:4000]
    instructions = (
        "Provide a JSON object with keys summary, vocabulary, grammar, action_points. "
        "Each value should be short strings or bullet-like sentences."
    )
    user_content = (
        f"Student material:\n{snippet}\n\nFocus: {custom_prompt or 'Highlight strengths and improvements.'}"
    )
    try:
        data = request_ai_json(instructions, user_content)
    except RuntimeError as exc:
        app.logger.warning("AI analyzer unavailable: %s", exc)
        _inform_ai_fallback("AI analyzer offline. Showing heuristic feedback instead.")
        return _local_text_analysis(snippet, custom_prompt)
    except Exception as exc:  # pragma: no cover
        app.logger.warning("AI analysis error: %s", exc)
        _inform_ai_fallback("AI analyzer offline. Showing heuristic feedback instead.")
        return _local_text_analysis(snippet, custom_prompt)
    return {
        "summary": data.get("summary", "No summary produced."),
        "vocabulary": data.get("vocabulary", ""),
        "grammar": data.get("grammar", ""),
        "action_points": data.get("action_points", ""),
    }


def extract_text_from_upload(file_storage):
    if not file_storage or not file_storage.filename:
        raise ValueError("Please choose a file to upload.")
    filename = secure_filename(file_storage.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_UPLOADS:
        raise ValueError("Unsupported file type.")
    data = file_storage.read()
    if not data:
        raise ValueError("File appears to be empty.")
    stream = BytesIO(data)
    if ext in {".txt", ".md"}:
        return data.decode("utf-8", errors="ignore")
    if ext == ".pdf":
        reader = PdfReader(stream)
        parts = []
        for page in reader.pages[:10]:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)
    if ext == ".docx":
        doc = Document(stream)
        return "\n".join(p.text for p in doc.paragraphs)
    if ext == ".xlsx":
        wb = openpyxl.load_workbook(stream, data_only=True)
        sheet = wb.active
        rows = []
        for row in sheet.iter_rows(values_only=True):
            cells = [str(cell) for cell in row if cell is not None]
            if cells:
                rows.append(" ".join(cells))
        return "\n".join(rows)
    if ext == ".csv":
        stream.seek(0)
        text = data.decode("utf-8", errors="ignore")
        reader = csv.reader(text.splitlines())
        return "\n".join(" ".join(row) for row in reader)
    raise ValueError("Unsupported file type.")

CATEGORIES = {
    "vocabulary": {
        "label": "Vocabulary",
        "icon": "type",
        "table": "questions_vocabulary",
        "prompt_builder": lambda row: f"Select the correct meaning for the word '{row['word']}'.",
        "answer_type": "mcq",
    },
    "grammar": {
        "label": "Grammar",
        "icon": "book",
        "table": "questions_grammar",
        "prompt_builder": lambda row: row[
            "sentence_with_placeholder"
        ].replace("__", "____"),
        "answer_type": "mcq",
    },
    "reading": {
        "label": "Reading",
        "icon": "file-text",
        "table": "questions_reading",
        "prompt_builder": lambda row: row["question"],
        "answer_type": "mcq",
    },
    "translation": {
        "label": "Translation",
        "icon": "languages",
        "table": "questions_translation",
        "prompt_builder": lambda row: row["prompt"],
        "answer_type": "text",
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

        CREATE TABLE IF NOT EXISTS questions_translation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt TEXT NOT NULL,
            reference_answer TEXT NOT NULL
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

        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT NOT NULL,
            questions INTEGER DEFAULT 5,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS exam_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exam_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            details TEXT NOT NULL,
            ai_feedback TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (exam_id) REFERENCES exams (id)
        );
        """
    )
    db.commit()


def row_value(row, key, default=None):
    """Safe helper for sqlite Row objects."""
    try:
        if key in row.keys():
            return row[key]
    except Exception:
        pass
    return default


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
    if not rows:
        raise ValueError("No questions available for this category yet. Please ask your teacher to add some.")
    questions = []
    for row in rows:
        row_keys = row.keys()
        correct_answer = (
            row_value(row, "correct_answer")
            if "correct_answer" in row_keys
            else row_value(row, "reference_answer")
        )
        question = {
            "id": row["id"],
            "prompt": category["prompt_builder"](row),
            "correct_answer": correct_answer,
            "answer_type": category.get("answer_type", "mcq"),
        }
        if question["answer_type"] == "mcq":
            options = [
                row_value(row, "correct_answer"),
                row_value(row, "wrong1"),
                row_value(row, "wrong2"),
                row_value(row, "wrong3"),
            ]
            options = [opt for opt in options if opt]
            random.shuffle(options)
            question["options"] = options
        if category_key == "vocabulary":
            question["meta"] = {"word": row["word"]}
        elif category_key == "grammar":
            question["meta"] = {
                "sentence": row["sentence_with_placeholder"].replace("__", "____")
            }
        elif category_key == "reading":
            question["meta"] = {
                "title": row["title"],
                "text": row["text"],
            }
        else:
            question["meta"] = {}
        if question["answer_type"] == "text":
            question["meta"]["reference_hint"] = row_value(row, "reference_answer")
        questions.append(question)
    return questions


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/legal")
def legal():
    return render_template(
        "legal.html",
        sections=LEGAL_SECTIONS,
        legal_updated=datetime.utcnow().strftime("%d.%m.%Y"),
    )


@app.route("/mindmap")
def mindmap():
    return render_template("mindmap.html")


@app.route("/analyze", methods=["GET", "POST"])
@login_required
def analyze():
    analysis = None
    extracted = ""
    custom_prompt = ""
    if request.method == "POST":
        custom_prompt = request.form.get("prompt", "").strip()
        file = request.files.get("document")
        try:
            extracted = extract_text_from_upload(file)
            analysis = analyze_text_with_ai(extracted, custom_prompt)
        except ValueError as exc:
            flash(str(exc), "warning")
        except RuntimeError as exc:
            flash(str(exc), "danger")
    return render_template(
        "analyze.html",
        analysis=analysis,
        custom_prompt=custom_prompt,
        sample_text=extracted[:1200],
    )


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
    recent_results = db.execute(
        "SELECT * FROM results WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
        (g.user["id"],),
    ).fetchall()

    return render_template(
        "dashboard.html",
        total_quizzes=total_quizzes,
        best_scores=best_scores,
        categories=CATEGORIES,
        results=recent_results,
    )


@app.route("/profile")
@login_required
def profile():
    db = get_db()
    results = db.execute(
        "SELECT * FROM results WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (g.user["id"],),
    ).fetchall()
    exam_attempts = db.execute(
        """
        SELECT ea.*, e.title
        FROM exam_attempts ea
        JOIN exams e ON e.id = ea.exam_id
        WHERE ea.user_id = ?
        ORDER BY ea.created_at DESC
        LIMIT 5
        """,
        (g.user["id"],),
    ).fetchall()
    return render_template("profile.html", results=results, exam_attempts=exam_attempts)


@app.route("/quiz/select")
@login_required
def quiz_select():
    return render_template("quiz_select.html", categories=CATEGORIES)


@app.route("/exams")
@login_required
def exams():
    db = get_db()
    exams = db.execute(
        "SELECT * FROM exams WHERE is_active = 1 ORDER BY id DESC"
    ).fetchall()
    attempts = db.execute(
        """
        SELECT ea.*, e.title
        FROM exam_attempts ea
        JOIN exams e ON e.id = ea.exam_id
        WHERE ea.user_id = ?
        ORDER BY ea.created_at DESC
        LIMIT 10
        """,
        (g.user["id"],),
    ).fetchall()
    return render_template("exams.html", exams=exams, attempts=attempts, categories=CATEGORIES)


@app.route("/exams/create", methods=["POST"])
@admin_required
def create_exam():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "vocabulary")
    try:
        questions = int(request.form.get("questions", 5))
    except ValueError:
        questions = 5
    if not title or category not in CATEGORIES:
        flash("Please provide a valid title and category.", "warning")
        return redirect(url_for("exams"))
    questions = max(3, min(questions, 15))
    db = get_db()
    db.execute(
        "INSERT INTO exams (title, description, category, questions) VALUES (?, ?, ?, ?)",
        (title, description, category, questions),
    )
    db.commit()
    flash("Exam created and ready to assign.", "success")
    return redirect(url_for("exams"))


@app.route("/admin/exams/generate", methods=["POST"])
@admin_required
def generate_exam_ai():
    prompt = request.form.get("prompt", "").strip()
    try:
        payload = generate_exam_from_prompt(prompt)
    except RuntimeError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("exams"))
    db = get_db()
    db.execute(
        "INSERT INTO exams (title, description, category, questions) VALUES (?, ?, ?, ?)",
        (
            payload["title"],
            payload["description"],
            payload["category"],
            payload["questions"],
        ),
    )
    db.commit()
    flash(f"AI created exam '{payload['title']}'.", "success")
    return redirect(url_for("exams"))


def load_exam(exam_id):
    exam = (
        get_db()
        .execute("SELECT * FROM exams WHERE id = ?", (exam_id,))
        .fetchone()
    )
    return exam


@app.route("/exams/<int:exam_id>/take", methods=["GET", "POST"])
@login_required
def take_exam(exam_id):
    exam = load_exam(exam_id)
    if not exam or not exam["is_active"]:
        flash("This exam is no longer available.", "warning")
        return redirect(url_for("exams"))

    exam_state = session.get("exam")
    if not exam_state or exam_state.get("exam_id") != exam_id:
        try:
            start_exam_session(exam)
        except ValueError as exc:
            flash(str(exc), "warning")
            return redirect(url_for("exams"))
        exam_state = session["exam"]

    if request.method == "POST":
        exam_state = session.get("exam")
        current_index = exam_state["current"]
        question = exam_state["questions"][current_index]
        if question["answer_type"] == "text":
            selected = request.form.get("text_answer", "").strip()
            evaluation = evaluate_text_answer(
                question["prompt"], question["correct_answer"], selected
            )
            is_correct = evaluation["is_correct"]
            feedback = evaluation.get("feedback")
            explanation = evaluation.get("explanation")
        else:
            selected = request.form.get("answer")
            if not selected:
                flash("Please pick an option to continue.", "warning")
                return redirect(url_for("take_exam", exam_id=exam_id))
            is_correct = selected == question["correct_answer"]
            feedback = ""
            explanation = ""
        exam_state["answers"].append(
            {
                "question": question,
                "selected": selected,
                "is_correct": is_correct,
                "feedback": feedback,
                "explanation": explanation,
            }
        )
        if is_correct:
            exam_state["score"] += 1
        exam_state["current"] += 1
        session["exam"] = exam_state

        if exam_state["current"] >= exam_state["total"]:
            db = get_db()
            details_json = json.dumps(exam_state["answers"])
            ai_summary = summarize_attempt_for_teacher(
                exam_state["title"], exam_state["answers"]
            )
            cursor = db.execute(
                """
                INSERT INTO exam_attempts (user_id, exam_id, score, total, details, ai_feedback, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    g.user["id"],
                    exam_id,
                    exam_state["score"],
                    exam_state["total"],
                    details_json,
                    ai_summary,
                    datetime.utcnow().isoformat(),
                ),
            )
            db.commit()
            attempt_id = cursor.lastrowid
            session.pop("exam", None)
            return redirect(url_for("exam_result", attempt_id=attempt_id))

    return render_template(
        "exam_take.html",
        exam=exam,
        exam_state=exam_state,
        question=exam_state["questions"][exam_state["current"]],
        current=exam_state["current"] + 1,
        total=exam_state["total"],
        categories=CATEGORIES,
    )


@app.route("/exams/results/<int:attempt_id>")
@login_required
def exam_result(attempt_id):
    db = get_db()
    attempt = db.execute(
        """
        SELECT ea.*, e.title, e.category, u.username
        FROM exam_attempts ea
        JOIN exams e ON e.id = ea.exam_id
        JOIN users u ON u.id = ea.user_id
        WHERE ea.id = ?
        """,
        (attempt_id,),
    ).fetchone()
    if not attempt:
        flash("Exam attempt not found.", "warning")
        return redirect(url_for("exams"))
    if attempt["user_id"] != g.user["id"] and not g.user["is_admin"]:
        flash("You do not have access to that report.", "danger")
        return redirect(url_for("dashboard"))
    answers = json.loads(attempt["details"])
    return render_template(
        "exam_results.html",
        attempt=attempt,
        answers=answers,
        category=CATEGORIES.get(attempt["category"]),
    )


@app.route("/admin/exams/attempts")
@admin_required
def admin_exam_attempts():
    db = get_db()
    attempts = db.execute(
        """
        SELECT ea.*, e.title, u.username
        FROM exam_attempts ea
        JOIN exams e ON e.id = ea.exam_id
        JOIN users u ON u.id = ea.user_id
        ORDER BY ea.created_at DESC
        LIMIT 50
        """
    ).fetchall()
    return render_template("admin_exam_attempts.html", attempts=attempts)


@app.route("/admin/exams/attempts/<int:attempt_id>")
@admin_required
def admin_exam_attempt_detail(attempt_id):
    db = get_db()
    attempt = db.execute(
        """
        SELECT ea.*, e.title, e.category, u.username, u.email
        FROM exam_attempts ea
        JOIN exams e ON e.id = ea.exam_id
        JOIN users u ON u.id = ea.user_id
        WHERE ea.id = ?
        """,
        (attempt_id,),
    ).fetchone()
    if not attempt:
        flash("Attempt not found.", "warning")
        return redirect(url_for("admin_exam_attempts"))
    answers = json.loads(attempt["details"])
    return render_template(
        "exam_attempt_detail.html",
        attempt=attempt,
        answers=answers,
        category=CATEGORIES.get(attempt["category"]),
    )


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


def start_exam_session(exam_row):
    questions = fetch_random_questions(
        exam_row["category"], limit=exam_row["questions"]
    )
    session["exam"] = {
        "exam_id": exam_row["id"],
        "title": exam_row["title"],
        "category": exam_row["category"],
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
        try:
            start_quiz_session(category)
        except ValueError as exc:
            flash(str(exc), "warning")
            return redirect(url_for("quiz_select"))
        quiz_state = session["quiz"]

    if request.method == "POST":
        quiz_state = session.get("quiz")
        current_index = quiz_state["current"]
        question = quiz_state["questions"][current_index]
        if question["answer_type"] == "text":
            selected = request.form.get("text_answer", "").strip()
            evaluation = evaluate_text_answer(
                question["prompt"], question["correct_answer"], selected
            )
            is_correct = evaluation["is_correct"]
            feedback = evaluation.get("feedback")
            explanation = evaluation.get("explanation")
        else:
            selected = request.form.get("answer")
            if not selected:
                flash("Please pick an option to continue.", "warning")
                return redirect(url_for("quiz", category=category))
            is_correct = selected == question["correct_answer"]
            feedback = ""
            explanation = ""
        quiz_state["answers"].append(
            {
                "question": question,
                "selected": selected,
                "is_correct": is_correct,
                "feedback": feedback,
                "explanation": explanation,
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
    elif category == "reading":
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
    else:  # translation
        prompt = request.form.get("prompt", "").strip()
        reference = request.form.get("reference_answer", "").strip()
        if prompt and reference:
            db.execute(
                f"INSERT INTO {table} (prompt, reference_answer) VALUES (?, ?)",
                (prompt, reference),
            )
    db.commit()
    flash("Question added.", "success")
    return redirect(url_for("admin_questions", category=category))


@app.route("/admin/questions/<category>/generate", methods=["POST"])
@admin_required
def generate_question_ai(category):
    if category not in CATEGORIES:
        abort(404)
    prompt = request.form.get("prompt", "").strip()
    try:
        generated = generate_questions_with_prompt(category, prompt)
    except RuntimeError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("admin_questions", category=category))
    table = CATEGORIES[category]["table"]
    db = get_db()
    for item in generated:
        if category == "vocabulary":
            db.execute(
                f"INSERT INTO {table} (word, correct_answer, wrong1, wrong2, wrong3) VALUES (?, ?, ?, ?, ?)",
                (
                    item["word"],
                    item["correct_answer"],
                    item["wrong1"],
                    item["wrong2"],
                    item["wrong3"],
                ),
            )
        elif category == "grammar":
            db.execute(
                f"INSERT INTO {table} (sentence_with_placeholder, correct_answer, wrong1, wrong2, wrong3) VALUES (?, ?, ?, ?, ?)",
                (
                    item["sentence_with_placeholder"],
                    item["correct_answer"],
                    item["wrong1"],
                    item["wrong2"],
                    item["wrong3"],
                ),
            )
        elif category == "reading":
            db.execute(
                f"INSERT INTO {table} (title, text, question, correct_answer, wrong1, wrong2, wrong3) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    item["title"],
                    item["text"],
                    item["question"],
                    item["correct_answer"],
                    item["wrong1"],
                    item["wrong2"],
                    item["wrong3"],
                ),
            )
        else:
            db.execute(
                f"INSERT INTO {table} (prompt, reference_answer) VALUES (?, ?)",
                (item["prompt"], item["reference_answer"]),
            )
    db.commit()
    flash(f"Generated {len(generated)} question(s).", "success")
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
        elif category == "reading":
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
        else:  # translation
            fields = (
                request.form.get("prompt", "").strip(),
                request.form.get("reference_answer", "").strip(),
                question_id,
            )
            db.execute(
                f"UPDATE {table} SET prompt=?, reference_answer=? WHERE id = ?",
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


@app.errorhandler(404)
def not_found(error):
    return (
        render_template("error.html", code=404, message="The page you requested was not found."),
        404,
    )


@app.errorhandler(500)
def server_error(error):  # pragma: no cover - best effort
    return (
        render_template(
            "error.html",
            code=500,
            message="Something unexpected happened. Please try again in a moment.",
        ),
        500,
    )


if __name__ == "__main__":
    with app.app_context():
        init_tables()
    app.run(debug=True)

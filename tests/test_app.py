import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import url_for
import pytest
from werkzeug.security import check_password_hash, generate_password_hash

from app import (
    app as flask_app,
    get_db,
    init_tables,
    request_ai_json_with_web_search,
    search_internet,
)


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "test.db"
    flask_app.config.update(TESTING=True, DATABASE=str(db_path))
    with flask_app.app_context():
        init_tables()
    with flask_app.test_client() as client:
        yield client


@pytest.fixture()
def create_user():
    def _create_user(
        *,
        username="learner",
        email="learner@example.com",
        password="secret123",
        is_admin=False,
    ):
        with flask_app.app_context():
            db = get_db()
            db.execute(
                "DELETE FROM users WHERE username = ? OR email = ?",
                (username, email),
            )
            cur = db.execute(
                "INSERT INTO users (username, email, password_hash, is_admin) "
                "VALUES (?, ?, ?, ?)",
                (username, email, generate_password_hash(password), int(is_admin)),
            )
            db.commit()
            return cur.lastrowid

    return _create_user


def test_home_page_has_new_structure(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "English practice that fits into any commute" in html
    assert "Study blocks for every skill" in html
    assert "Branch:" in html


def test_legal_page_mentions_privacy_and_contact(client):
    response = client.get("/legal")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Privacy policy" in html
    assert "privacy@orish.app" in html


def test_login_with_username(client, create_user):
    user_id = create_user(username="learnerX", email="learnerx@example.com", password="combo123")
    response = client.post(
        "/login",
        data={"identifier": "learnerX", "password": "combo123"},
    )
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert session.get("user_id") == user_id


def test_profile_password_change_flow(client, create_user):
    user_id = create_user(password="oldpass123")
    with client.session_transaction() as session:
        session["user_id"] = user_id
    response = client.post(
        "/profile",
        data={
            "current_password": "oldpass123",
            "new_password": "newpass456",
            "confirm_password": "newpass456",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Password updated successfully." in response.get_data(as_text=True)
    with flask_app.app_context():
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        assert check_password_hash(row["password_hash"], "newpass456")


def test_profile_password_change_requires_current_password(client, create_user):
    user_id = create_user(username="other", email="other@example.com", password="pass12345")
    with client.session_transaction() as session:
        session["user_id"] = user_id
    response = client.post(
        "/profile",
        data={
            "current_password": "wrongpass",
            "new_password": "freshpass1",
            "confirm_password": "freshpass1",
        },
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)
    assert "Current password is incorrect." in html
    with flask_app.app_context():
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        assert check_password_hash(row["password_hash"], "pass12345")


def test_admin_can_promote_user(client, create_user):
    admin_id = create_user(username="teacher", email="teacher@example.com", password="teachpass", is_admin=True)
    learner_id = create_user(username="learner2", email="learner2@example.com", password="learnpass")
    with client.session_transaction() as session:
        session["user_id"] = admin_id
    response = client.post(
        "/admin/users",
        data={"user_id": learner_id, "action": "promote"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "is now a teacher" in response.get_data(as_text=True)
    with flask_app.app_context():
        db = get_db()
        row = db.execute("SELECT is_admin FROM users WHERE id = ?", (learner_id,)).fetchone()
        assert row["is_admin"] == 1


def test_student_cannot_access_admin_users(client, create_user):
    learner_id = create_user()
    with client.session_transaction() as session:
        session["user_id"] = learner_id
    response = client.get("/admin/users")
    assert response.status_code == 302
    with flask_app.app_context():
        assert response.headers["Location"].endswith(url_for("dashboard"))


def test_admin_delete_user_requires_confirmation(client, create_user):
    admin_id = create_user(username="teacher2", email="teacher2@example.com", password="teachpass", is_admin=True)
    learner_id = create_user(username="to-delete", email="todelete@example.com", password="delete123")
    with client.session_transaction() as session:
        session["user_id"] = admin_id
    response = client.post(
        "/admin/users",
        data={"user_id": learner_id, "action": "prepare_delete"},
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Confirm delete" in html
    with flask_app.app_context():
        db = get_db()
        assert db.execute("SELECT 1 FROM users WHERE id = ?", (learner_id,)).fetchone()

    response = client.post(
        "/admin/users",
        data={"user_id": learner_id, "action": "delete"},
        follow_redirects=True,
    )
    assert "Deleted to-delete" in response.get_data(as_text=True)
    with flask_app.app_context():
        db = get_db()
        assert db.execute("SELECT 1 FROM users WHERE id = ?", (learner_id,)).fetchone() is None


def test_admin_can_create_student_via_users_page(client, create_user):
    admin_id = create_user(username="headteacher", email="headteacher@example.com", password="teachpass", is_admin=True)
    with client.session_transaction() as session:
        session["user_id"] = admin_id
    response = client.post(
        "/admin/users",
        data={
            "action": "create",
            "username": "freshstudent",
            "email": "fresh@student.com",
            "password": "freshpass1",
            "role": "student",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Created student account for freshstudent" in response.get_data(as_text=True)
    with flask_app.app_context():
        db = get_db()
        row = db.execute("SELECT is_admin FROM users WHERE username = ?", ("freshstudent",)).fetchone()
        assert row is not None and row["is_admin"] == 0


def test_exam_without_enough_questions_is_blocked(client, create_user):
    user_id = create_user()
    with flask_app.app_context():
        db = get_db()
        exam_id = db.execute(
            "INSERT INTO exams (title, description, category, questions, is_active, study_enabled, test_enabled) VALUES (?, ?, ?, ?, 1, 1, 1)",
            ("Mega Exam", "Too big for the current bank", "vocabulary", 5),
        ).lastrowid
        db.execute(
            "INSERT INTO exam_assignments (exam_id, user_id, can_study, can_test) VALUES (?, ?, 1, 1)",
            (exam_id, user_id),
        )
        db.commit()
    with client.session_transaction() as session:
        session["user_id"] = user_id
    response = client.get(f"/exams/{exam_id}/take", follow_redirects=True)
    html = response.get_data(as_text=True).lower()
    assert "does not have any questions yet" in html or "needs 5 questions" in html or "no questions available" in html


def test_search_internet_requires_query():
    with pytest.raises(ValueError):
        search_internet("")


def test_ai_search_endpoint_requires_query(client, create_user):
    user_id = create_user(username="searchuser", email="search@example.com", password="seekpass")
    with client.session_transaction() as session:
        session["user_id"] = user_id
    response = client.post("/ai/search", json={"query": ""})
    assert response.status_code == 400
    data = response.get_json()
    assert "query" in data["error"].lower()


def test_request_ai_json_with_web_search_triggers_research(monkeypatch):
    prompts = []
    responses = iter(
        [
            {"search_queries": ["latest esl exam topics"], "reason": "Need recent themes"},
            {
                "title": "AI Exam Draft",
                "description": "Context-aware exam",
                "category": "vocabulary",
                "questions": 3,
                "items": [],
            },
        ]
    )

    def fake_request_ai_json(system_prompt, user_prompt):
        prompts.append(user_prompt)
        return next(responses)

    def fake_search_internet(query, max_results=5):
        assert query == "latest esl exam topics"
        assert max_results == 5
        return [
            {
                "title": "Modern ESL Trends",
                "snippet": "Teachers emphasize cultural topics in 2024.",
                "url": "https://example.com/esl",
                "source": "duckduckgo",
            }
        ]

    monkeypatch.setattr("app.request_ai_json", fake_request_ai_json)
    monkeypatch.setattr("app.search_internet", fake_search_internet)

    result = request_ai_json_with_web_search("system prompt", "user prompt")
    assert result["title"] == "AI Exam Draft"
    assert len(prompts) == 2
    assert "Web research results you requested" in prompts[1]


def test_ai_assistant_creates_exam(client, create_user, monkeypatch):
    admin_id = create_user(username="assistant-teacher", email="assistant-teacher@example.com", password="assist", is_admin=True)
    with client.session_transaction() as session:
        session["user_id"] = admin_id

    def fake_request(system_prompt, base_prompt, max_rounds=2):
        return {
            "answer": "Drafted a grammar exam.",
            "actions": [
                {"type": "create_exam", "title": "Assistant Exam", "category": "grammar", "questions": 4}
            ],
        }

    monkeypatch.setattr("app.request_ai_json_with_web_search", fake_request)

    response = client.post("/ai/assistant", json={"message": "Create a grammar test"}, buffered=True)
    assert response.status_code == 200
    chunks = [json.loads(line) for line in response.data.decode().split("\n") if line.strip()]
    final = chunks[-1]
    assert final["type"] == "answer"
    assert final["actions"][0]["type"] == "create_exam"
    with flask_app.app_context():
        db = get_db()
        row = db.execute("SELECT * FROM exams WHERE title = ?", ("Assistant Exam",)).fetchone()
        assert row is not None


def test_ai_assistant_navigation_action(client, create_user, monkeypatch):
    user_id = create_user(username="nav-student", email="nav-student@example.com", password="assist")
    with client.session_transaction() as session:
        session["user_id"] = user_id

    def fake_request(system_prompt, base_prompt, max_rounds=2):
        return {
            "answer": "Opening exams.",
            "actions": [{"type": "navigate", "target": "exams"}],
        }

    monkeypatch.setattr("app.request_ai_json_with_web_search", fake_request)

    response = client.post("/ai/assistant", json={"message": "Take me to the exams"}, buffered=True)
    assert response.status_code == 200
    chunks = [json.loads(line) for line in response.data.decode().split("\n") if line.strip()]
    final = chunks[-1]
    assert final["type"] == "answer"
    with flask_app.app_context():
        assert final["navigate_to"].endswith(url_for("exams"))

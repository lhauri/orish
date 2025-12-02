import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import url_for
import pytest
from werkzeug.security import check_password_hash, generate_password_hash

from app import app as flask_app, get_db, init_tables


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


def test_legal_page_mentions_privacy_and_contact(client):
    response = client.get("/legal")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Datenschutzerklärung" in html
    assert "privacy@orish.app" in html


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

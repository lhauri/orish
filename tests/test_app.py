import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app as flask_app


@pytest.fixture()
def client():
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as client:
        yield client


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

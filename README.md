# Orish

Orish is a classroom-ready English practice studio built with Flask. It combines daily student drills, teacher dashboards, AI copilots, and document analysis so a single deployment can cover vocabulary sprints, mock exams, and ad-hoc study packs. Every AI touchpoint (DeepSeek) has guard rails and deterministic fallbacks so lessons continue even when an API quota is exceeded.

## Table of contents

1. [Feature tour](#feature-tour)
2. [Architecture](#architecture)
3. [Local setup](#local-setup)
4. [Configuration](#configuration)
5. [Running the app](#running-the-app)
6. [Testing & diagnostics](#testing--diagnostics)
7. [Logs & troubleshooting](#logs--troubleshooting)
8. [Project layout](#project-layout)
9. [Deployment notes](#deployment-notes)

## Feature tour

### Student experience
- **Guided practice** – Three 5-question quiz modes (vocabulary, grammar, translation) with instant scoring, historical stats, and mind-map style navigation hints.
- **Exam hub** – Students see the exams assigned to them, whether they are in study or test mode, and can launch each attempt without guessing URLs.
- **Study packs & mind map** – Curated packs and a lightweight mind map page highlight current goals outside of formal exams.
- **Document analyzer** – Learners can upload snippets of PDFs, DOCX, TXT, CSV, or XLSX files (≤ 2 MB, row/page caps enforced) to receive summaries, vocabulary focus, grammar notes, and action items.

### Teacher / admin tools
- **Dashboard & analytics** – Overview of student attempts, AI summaries, and quick access to grading shortcuts.
- **Question bank** – CRUD for banks, tag questions into groups, share packs, or let the AI assistant draft more.
- **Exam builder** – Combine hand-written and AI-generated questions, toggle study/test availability, and assign exams to individual students.
- **User management** – Promote or demote accounts, reset passwords, and create new learners directly from the admin area.

### AI copilots & automation
- **Multi-use AI chat** – Floating “Orish Copilot” button gives students and teachers a round-button chat to navigate the app, draft questions, prepare exams, or fetch study ideas. Messages stream back in real time and navigation actions trigger automatic redirects.
- **Translation grading & feedback** – Free-text answers are checked by DeepSeek; if it fails, deterministic heuristics fall back to lexicographic similarity.
- **Document analyzer fallback** – When AI is offline, Orish still produces useful stats (sentence counts, repeated vocab, difficulty hints).
- **Web-researched generation** – `/ai/search` and backend helpers call DuckDuckGo for lightweight research before drafting new content. Logs land in `ai_search.log` for review.

## Architecture

- **Flask 3 + SQLite** – `app.py` hosts routes, services, AI adapters, and the simple SQLite persistence layer accessed through helper functions like `get_db()` or `init_tables()`.
- **Templating** – Jinja2 templates (see `templates/base.html`) define the layout, navigation, AI widget, and all views (dashboard, admin, analyzer, exams, etc.).
- **Frontend assets** – Custom CSS (`static/css/style.css`) plus Lucide icons drive the visual language. `static/js/app.js` handles navigation menus, flash messaging, and the AI widget (including streaming updates).
- **AI integration** – DeepSeek is accessed via the OpenAI-compatible SDK inside `app.py`. The `request_ai_json_with_web_search` helper augments prompts with DuckDuckGo results when needed and appends user-visible fallbacks when API calls fail.
- **Logs** – `ai.log` records each assistant exchange, while `ai_search.log` records auto-generated research prompts/responses for auditing.
- **Tests** – `tests/test_app.py` exercises auth, profile updates, admin tools, AI assistant streaming, and the web-search helper. Running them creates an isolated SQLite DB in the pytest temp directory.

## Local setup

```bash
git clone <repo-url> orish
cd orish
python3 -m venv .venv
source .venv/bin/activate          # .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Initialize configuration

Copy `.env.example` (if present) to `.env`, or create it manually:

```env
ORISH_SECRET=change-this           # Flask session/CSRF secret
DEEPSEEK_API_KEY=sk-live-or-dev    # optional but required for AI features
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

Leave `DEEPSEEK_API_KEY` blank to run entirely on local fallbacks.

### Create the database

```bash
python init_db.py
```

The script seeds:
- an admin account (`teacher@example.com` / `teach123`)
- sample quizzes, exams, and study packs
- reference data for analyzer heuristics

You can safely re-run the script; it is idempotent.

## Configuration

| Variable | Purpose | Default |
|----------|---------|---------|
| `ORISH_SECRET` | Flask secret key (sessions + CSRF) | `dev-secret-key` |
| `DATABASE` | Path to the SQLite DB | `orish.db` in repo root |
| `DEEPSEEK_API_KEY` | DeepSeek / OpenAI-compatible key | _unset_ |
| `DEEPSEEK_BASE_URL` | API base (will have `/v1` appended if missing) | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | Model slug passed to DeepSeek | `deepseek-chat` |
| `FLASK_DEBUG` or `DEBUG` | Enables debug mode when truthy | `false` |

> **Tip:** Use `.env` plus `python-dotenv` (already wired in `app.py`) to simplify local development.

## Running the app

```bash
python app.py
```

Browse to `http://127.0.0.1:5000`:
- Sign in with the seeded teacher credentials to explore admin tools.
- Register a learner account to experience the student dashboard, quizzes, exams, mind map, and analyzer.
- Open the floating AI button (bottom-right) for the streaming copilot.

### Production entry point

`wsgi.py` exposes the Flask application as `app` so you can point Gunicorn, uWSGI, or Azure App Service to `wsgi:app`. Remember to run `init_db.py` (or supply your own migrations) before booting a production worker.

## Testing & diagnostics

| Task | Command | Notes |
|------|---------|-------|
| Run unit tests | `pytest` | Exercises routes, auth, admin flows, and AI helpers. |
| Syntax check | `python3 -m py_compile app.py` | Fast sanity check for CI or pre-commit. |
| DeepSeek smoke test | `python scripts/test_deepseek.py` | Verifies credentials by issuing a short chat completion. |

When adding new functionality, prefer covering it in `tests/test_app.py` or a dedicated module-specific test.

## Logs & troubleshooting

- `ai.log` – Full text of AI assistant sessions (chat payloads + responses). Useful for debugging navigation or action failures.
- `ai_search.log` – Records every external research prompt plus the DuckDuckGo snippets returned.
- Flask flash messages alert the user when AI calls fail and when fallbacks kick in.

Common fixes:
- **`ModuleNotFoundError`** – Activate your virtualenv and reinstall dependencies.
- **`AI request failed` flashes** – Confirm `DEEPSEEK_API_KEY` and ensure the base URL includes `/v1`. When absent, Orish still functions via fallbacks.
- **`sqlite3.OperationalError: database is locked`** – Stop the dev server, delete `orish.db`, rerun `init_db.py`, then restart.
- **Upload rejected** – Only `.txt`, `.md`, `.pdf`, `.docx`, `.xlsx`, `.csv` are accepted, ≤ 2 MB, and large docs are truncated per the limits in `app.py`.

## Project layout

```
orish/
├── app.py               # Routes, services, AI adapters, database helpers
├── init_db.py           # Idempotent schema & seed script
├── requirements.txt     # Flask, OpenAI SDK, docx, PyPDF2, etc.
├── static/
│   ├── css/style.css    # Entire UI + AI widget styling
│   └── js/app.js        # Navigation, flash helper, AI widget streaming
├── templates/           # Home, dashboard, exams, analyzer, admin, auth
├── scripts/
│   └── test_deepseek.py # CLI connectivity test
├── tests/
│   └── test_app.py      # Pytest suite
├── wsgi.py              # Production entry point
├── ai.log               # AI assistant transcripts
└── ai_search.log        # Web research transcripts
```

## Deployment notes

1. **Secrets & env vars** – Provide real values for `ORISH_SECRET` and `DEEPSEEK_API_KEY`. Store them as platform secrets (Heroku, Render, Azure App Service, etc.).
2. **Database** – For small classrooms SQLite is fine; for larger cohorts consider pointing `app.config["DATABASE"]` to a managed PostgreSQL instance (requires adapting `get_db()` and schema SQL).
3. **Static assets** – `static/` is self-contained; enable caching headers via your reverse proxy or CDN.
4. **Background work** – AI calls happen inline via Flask streaming responses, so provision enough worker threads (e.g., Gunicorn with `--workers 2 --threads 4`) or move heavy jobs to a task queue if you scale beyond a classroom.
5. **Monitoring** – Tail `ai.log`/`ai_search.log` and watch server logs for rate-limit errors to adjust DeepSeek quotas early.

Happy teaching and learning! If you spot gaps or want to extend Orish, open an issue or submit a PR describing the scenario you’d like to cover.

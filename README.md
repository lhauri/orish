# Orish

Orish is a Flask-based learning companion for English classrooms. It bundles curated question banks, mock exams, and optional DeepSeek-powered AI helpers so students can practice vocabulary, grammar, reading, and translation in one workspace. When the AI service is unreachable, Orish automatically supplies handcrafted fallback content so lessons can continue without interruption.

## Feature highlights

| Area | Details |
|------|---------|
| **Quizzes** | 5-question sessions per category with instant scoring and history saved to `results`. |
| **Exams** | Multi-question exams stored in `exams`/`exam_attempts`, including AI-generated teacher summaries. |
| **Admin console** | CRUD for question banks, manual exam creation, plus an overview of all student attempts. |
| **Document analyzer** | Upload PDF/DOCX/TXT/CSV/XLSX excerpts; AI (or heuristic fallback) returns summary, vocab focus, grammar coaching, and action points. |
| **AI assistants** | Generate new questions/exams, review open-ended translation answers, or summarize attempts. Uses the DeepSeek `/responses` endpoint; transparent fallbacks are shown when the API key is missing or the request fails. |

## Tech stack

- **Backend:** Flask 3, SQLite (via `sqlite3`), python-dotenv for config.
- **AI integration:** OpenAI SDK pointed at DeepSeek’s compatible endpoint (`deepseek-chat`, `deepseek-reasoner`).
- **Parsing:** PyPDF2, python-docx, openpyxl, csv for document ingestion.
- **Frontend:** Jinja2 templates, Lucide icons, custom CSS (`static/css/style.css`), lightweight JS for icon rendering and mind-map animation (`static/js/app.js`).

## Prerequisites

- Python 3.10 or newer (virtual environment recommended)
- SQLite (included with Python)
- Optional DeepSeek API credentials for AI-enabled flows

## Setup guide

1. **Clone & install**
   ```bash
   git clone <repo-url>
   cd orish
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure environment**
   Create `.env` in the project root (use `.env.example` if provided):
   ```env
   ORISH_SECRET=change-this
   DEEPSEEK_API_KEY=sk-your-key      # optional but required for AI
   DEEPSEEK_BASE_URL=https://api.deepseek.com
   DEEPSEEK_MODEL=deepseek-chat
   ```
   Leave `DEEPSEEK_API_KEY` blank to run purely with fallback content.

3. **Initialize the database**
   ```bash
   python init_db.py
   ```
   This script creates tables, seeds question banks, inserts sample exams, and provisions the default admin:
   - Email: `teacher@example.com`
   - Password: `teach123`

4. **Run the dev server**
   ```bash
   python app.py
   ```
   Navigate to `http://127.0.0.1:5000`. Use the seeded admin account to explore teacher tools.

## Working with the app

- **Student flow**
  - Register a learner account or log in with an existing one.
  - Use the dashboard to launch category-specific quizzes or enter the exam hub.
  - Translation questions accept free text; DeepSeek (or fallback grading) responds with correctness and coaching tips.

- **Admin flow**
  - Visit `/admin/questions` to add manual questions or trigger AI generation per category.
  - `/exams` allows publishing manual exams, while `/admin/exams/generate` asks AI (with fallback templates) to scaffold one for you.
  - `/admin/exams/attempts` lists recent student attempts with AI summaries when available.

- **Document analyzer**
  - Accessible via `/analyze` (requires login).
  - Supported extensions: `.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.xlsx`.
  - Only the first ~10 pages/rows are parsed to keep response times low.
  - If DeepSeek is unavailable, a heuristic analyzer inspects sentence/word counts and surfaces actionable hints.

## AI configuration & fallbacks

- Requests hit `<DEEPSEEK_BASE_URL>/v1/responses` with the model from `DEEPSEEK_MODEL`.
- Failures (invalid key, quota exceeded, network outage) are logged and surfaced as friendly flash messages.
- Fallback behaviors:
  - **Question/exam generation:** pre-curated templates are inserted automatically.
  - **Translation grading & summaries:** revert to deterministic checks (case-insensitive match) or omit the summary.
  - **Document analyzer:** uses local heuristics (word counts, sentence variety, repeated vocab) until AI access is restored.

## Project structure

```
orish/
├── app.py              # Flask routes, AI helpers, DB access, session management
├── init_db.py          # Idempotent seeding script (users, questions, exams)
├── requirements.txt    # Python dependencies (Flask, OpenAI SDK, docx, etc.)
├── templates/          # Jinja2 templates for all pages
├── static/
│   ├── css/style.css   # Shared styling + layout
│   └── js/app.js       # Lucide icon bootstrapping, mind-map animation
├── data/               # Reserved for future exports/uploads
└── README.md
```

## Useful commands

| Task | Command |
|------|---------|
| Install deps | `pip install -r requirements.txt` |
| Initialize DB | `python init_db.py` |
| Start dev server | `python app.py` |
| Syntax check | `python3 -m py_compile app.py` |
| Reset DB (dev only) | `rm orish.db && python init_db.py` |

## Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ORISH_SECRET` | Flask session/CSRF secret | `dev-secret-key` |
| `DEEPSEEK_API_KEY` | DeepSeek/OpenAI-compatible key (optional) | — |
| `DEEPSEEK_BASE_URL` | API base URL (version suffix auto-added if missing) | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | Model slug passed to DeepSeek | `deepseek-chat` |

## Testing & quality

- The project currently relies on manual verification plus `python3 -m py_compile app.py` for syntax checks.
- When adding features, consider wiring lightweight unit tests (e.g., pytest) for database helpers or AI fallbacks.
- For UI changes, manually exercise: registration/login, each quiz category, exam creation/take, analyzer upload, and admin pages.

## Troubleshooting

- **Missing dependency (`ModuleNotFoundError`)** – activate your virtualenv and reinstall via `pip install -r requirements.txt`.
- **`AI request failed` flash** – confirm `DEEPSEEK_API_KEY`, network connectivity, and base URL. Built-in fallbacks keep workflows functional until the API recovers.
- **Database locked/unexpected data** – stop the Flask server, delete `orish.db`, rerun `python init_db.py`, then restart.
- **File upload rejected** – ensure the extension is in the allowed list and the file isn’t empty; only the first 10 pages/rows of larger documents are read.

## Contributing

1. Create a feature branch.
2. Apply changes (prefer `apply_patch` or formatted diffs).
3. Run `python3 -m py_compile app.py` and manually verify core flows.
4. Submit a PR describing user impact, testing performed, and any AI configuration changes.

Happy teaching and learning!

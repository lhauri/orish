# Orish

Orish is a Flask application that helps teachers and learners run English practice sessions. It ships with curated vocabulary, grammar, reading, and translation questions, supports full-length exams, and uses the DeepSeek API (OpenAI-compatible) for optional AI feedback.

## Features

- **Quizzes & Exams** – 5-question quizzes per skill area and longer exams with history tracking.
- **Admin tools** – Manage the master question bank, create exams, and review exam attempts.
- **AI extras** – Optional AI-generated questions/exams and translation grading. When the API is unavailable, the app falls back to curated samples and heuristic feedback.
- **Document analyzer** – Upload classroom materials (PDF/DOCX/TXT/CSV/XLSX) for AI summaries.

## Requirements

- Python 3.10+
- SQLite (bundled with Python)
- Optional DeepSeek (OpenAI-compatible) API key for AI features

## Quick start

```bash
git clone <repo>
cd orish
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

1. **Configure environment** – create a `.env` file in the project root:
   ```env
   ORISH_SECRET=change-me
   DEEPSEEK_API_KEY=sk-your-key   # Optional, required for AI
   DEEPSEEK_BASE_URL=https://api.deepseek.com
   DEEPSEEK_MODEL=deepseek-chat
   ```
2. **Initialize the database** – seeds default users, questions, and exams:
   ```bash
   python init_db.py
   ```
3. **Run the development server**:
   ```bash
   python app.py
   ```

Visit `http://127.0.0.1:5000`. The seed script creates `teacher@example.com / teach123` (admin) for testing.

## Usage notes

- **AI requests** – With a valid DeepSeek key, features like AI-generated exams/questions, translation grading, and the document analyzer call the `/responses` endpoint. If the API fails or the key is missing, Orish flashes an informational message and uses built-in fallback content so flows still work.
- **Document analyzer** – Accepts `.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.xlsx`. Only the first ~10 pages/rows are processed to stay responsive.
- **Sessions** – Quiz/exam progress is stored in user sessions; logging out clears in-progress attempts.

## Project structure

```
orish/
├── app.py             # Flask app with routes, AI helpers, DB logic
├── init_db.py         # Database creation & seed script
├── orish.db           # SQLite database (created after init_db.py run)
├── requirements.txt   # Python dependencies
├── templates/         # Jinja2 HTML templates
├── static/
│   ├── css/style.css  # Global styling
│   └── js/app.js      # Minimal JS (icons + mind-map animation)
└── data/              # Placeholder for future uploads/exports
```

## Environment variables

| Variable           | Description                                  | Default                |
|--------------------|----------------------------------------------|------------------------|
| `ORISH_SECRET`     | Flask secret key                             | `dev-secret-key`       |
| `DEEPSEEK_API_KEY` | DeepSeek/OpenAI-compatible API key (optional)| —                      |
| `DEEPSEEK_BASE_URL`| Base URL for the API                         | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL`   | Model name for AI requests                   | `deepseek-chat`        |

## Troubleshooting

- **Missing python-docx or other deps** – run `pip install -r requirements.txt`.
- **AI request failed** – confirm your API key, network access, or temporarily rely on Orish’s fallback content (an informational flash message appears when this happens).
- **Database errors** – delete `orish.db`, rerun `python init_db.py`, and restart the server.

Happy teaching and learning!

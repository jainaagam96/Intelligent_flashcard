# upscEasy — UPSC Study System

A runnable Django + SQLite UPSC learning system combining source ingestion, AI recall-card generation, persistent spaced repetition, Mains answer evaluation, dashboard analytics and a responsive web UI.

## Features
- Local username/password authentication using Django sessions
- Dashboard: cards, due count, reviews, topics, sources, Mains history
- Topic management through the API
- Source ingestion: pasted notes, TXT/Markdown/CSV, PDF and DOCX
- AI recall generation through the OpenAI Responses API
- Source-linked cards with server-reconstructed line excerpts
- Local fallback card generation when no OpenAI key is configured
- Persistent scheduler: New, Learning, Review, Relearning
- Due-only queue with Again / Hard / Good / Easy scheduling
- Review history with response time and state transitions
- Editable generated cards before saving
- Anki card library with subject, topic, and keyword filters; edit or delete saved cards
- AI Mains answer evaluation with marks, content, structure, examples, keywords, omissions and dimensions
- Mains model-answer generation and searchable saved evaluations
- Analytics: retrieval success, rating distribution, average Mains marks
- Django admin for inspecting the database
- GET health endpoint at `/api/health/`

## Requirements
Python 3.13 is used for the Render deployment; Python 3.11+ is supported for local development.

## Windows setup
1. Extract this folder.
2. Open PowerShell in the folder.
3. Create a virtual environment:
   `python -m venv .venv`
4. Activate it:
   `.venv\\Scripts\\Activate.ps1`
5. Install packages:
   `pip install -r requirements.txt`
6. Copy `.env.example` to `.env`.
7. Put your OpenAI API key in `.env` if you want AI generation/evaluation. Without it, local fallback generation/evaluation still works.
8. Run:
   `python manage.py migrate`
9. Optional admin user:
   `python manage.py createsuperuser`
10. Start:
   `python manage.py runserver 8000`
11. Open `http://127.0.0.1:8000/`

## macOS/Linux
Use `python3 -m venv .venv`, activate with `source .venv/bin/activate`, then run the same pip/migrate/runserver commands.

## API smoke test
Open `http://127.0.0.1:8000/api/health/` in a browser. It supports GET and returns an online status. Card generation remains POST-only.

## Data
Local development uses SQLite (`db.sqlite3`). The hosted Render setup uses Supabase PostgreSQL through `DB_URL`. Uploaded files are processed into source text and metadata; extracted text is stored in the database rather than a cloud object store.

## Hosting
For deployment on Render with Supabase PostgreSQL, follow [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md). Keep `.env` and all SQLite backups out of Git.

## Important local architecture
Browser UI → Django session → DRF API → SQLite locally or Supabase PostgreSQL when hosted → OpenAI Responses API (when key is configured).
The OpenAI key is never sent to the browser.

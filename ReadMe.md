# YT Contextual Intelligence

A full-stack playground for building “neuro-contextual” YouTube campaigns. The stack combines a FastAPI backend, SQLite storage, OpenAI-powered scoring, and a React/Vite dashboard that surfaces campaign setup, keyword generation, video discovery, and Liz AI scoring workflows.

---

## Features

- **Neuro-contextual campaign briefs** – collect audience persona, intent, tone, emotions, interests, etc.
- **Locale-aware keyword generation** – Liz AI produces keywords in the campaign’s primary language/market.
- **YouTube fetch & enrichment** – diversify keyword rotation, capture channel metrics, track averages.
- **Liz AI content scoring** – optional transcript analysis, heuristic fallbacks, polar signal blend.
- **Interactive dashboard** – engagement snapshots, channel trust insights, inline score inspector with pagination.
- **Insights playground** – futuristic charts and exports ready for DV360 activation.

---

## Project Structure

api # FastAPI application (routers, services, models)
/frontend-react # Vite + React dashboard
/frontend # (legacy Streamlit prototype)
/youtube_pipeline.db # SQLite database (dev)
/scripts # Helper scripts (DB maintenance, etc.)


---

## Prerequisites

- Python 3.11 (recommended)
- Node.js 18+ (for Vite)
- Poetry or pip/venv for Python dependency management
- SQLite (bundled with Python)

---

## Environment Variables

Copy `.env.example` (or `.env`) and set:

```env
# FastAPI
DATABASE_URL=sqlite:///youtube_pipeline.db
YOUTUBE_API_KEY=...
OPENAI_API_KEY=...
SEARCHAPI_KEY=...        # Optional – currently disabled in transcript flow

The frontend expects:

VITE_API_BASE_URL=http://localhost:8000


Backend Setup

# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run FastAPI (with reload)
uvicorn api.main:app --reload --port 8000

Notes:

The SQLite database auto-loads migrations from direct ALTER statements. If you start fresh, run scripts/init_db.py (or clear youtube_pipeline.db).
To inspect current schema/averages, use python scripts/report.py.

Frontend Setup

cd frontend-react
npm install
npm run dev    # Launch Vite dev server (default http://localhost:5173)


Build for production:

npm run build
npm run preview

Key Workflows
1. Campaign Setup – create a campaign, set locale, define neuro guidance.
2. Keyword Generation – feed the Liz AI generator, manage manual entries, export targeting lists.
3. Video Fetch – fetch YouTube videos with balanced keyword rotation, inspect grid/list views.
4. Content Scoring – batch score inventory, inspect inline details (polar chart, engagement, channel trust), export scored URLs/channels.
5. Insights – explore campaign-level visualisations (emotion constellations, etc.).


Testing / Linting

# Frontend
npm run lint

# Backend (syntax check)
python -m compileall api

Additional unit tests can be added under api/tests (pytest friendly).

Deployment Notes

- Separate processes: run FastAPI (8000) and Vite (5173) or serve compiled frontend via nginx/Gunicorn.
- Consider using a Postgres database for production; update DATABASE_URL.
- Enable transcript paid service by re-enabling searchapi_key usage in YouTubeService.get_video_transcript.



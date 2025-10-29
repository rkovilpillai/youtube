# Local Deployment Guide

React/Vite dashboard for the YouTube Contextual Intelligence stack. Follow the steps below to run the entire experience locally (FastAPI backend + React frontend).

---

## Prerequisites

| Dependency | Version (tested) | Notes |
|------------|------------------|-------|
| Python     | 3.11             | Required for FastAPI services |
| Node.js    | 18+              | Required for Vite dev server |
| npm        | 9+               | Bundled with Node |
| SQLite     | bundled          | Default dev database |

> Tip: `pyenv` and `nvm` make it easy to install the exact versions above.

---

## Backend Setup (FastAPI)

1. **Create & activate virtualenv**
   ```bash
   cd /path/to/Youtube_POC/yt
   python -m venv .venv
   source .venv/bin/activate
   ```

2. **Install python dependencies**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Configure environment variables**  
   Copy `.env.example` (if available) or create `.env` in the repo root:
   ```env
   DATABASE_URL=sqlite:///youtube_pipeline.db
   YOUTUBE_API_KEY=<your_youtube_api_key>
   OPENAI_API_KEY=<your_openai_key>
   SEARCHAPI_KEY=<optional_paid_transcript_key>
   ```

4. **Initialise the database (first run only)**
   ```bash
   python scripts/init_db.py
   ```

5. **Start the FastAPI server**
   ```bash
   uvicorn api.main:app --reload --port 8000
   ```

   - API docs available at http://localhost:8000/docs  
   - Hot reload watches the entire `api/` directory.

---

## Frontend Setup (React + Vite)

1. **Install node dependencies**
   ```bash
   cd frontend-react
   npm install
   ```

2. **Configure frontend environment**
   Create `frontend-react/.env` if you need a non-default API URL:
   ```env
   VITE_API_BASE_URL=http://localhost:8000
   ```

3. **Run Vite dev server**
   ```bash
   npm run dev
   ```

   - Dev server runs at http://localhost:5173  
   - The proxy uses `VITE_API_BASE_URL` for API calls.

4. **Production build (optional)**
   ```bash
   npm run build
   npm run preview   # serves the dist/ bundle locally
   ```

---

## Daily Workflow

1. Start the backend (`uvicorn …`) in one terminal.  
2. Start the frontend (`npm run dev`) in another.  
3. Visit http://localhost:5173 to access the dashboard:
   - **Campaign Setup** – create/edit neuro-contextual briefs.
   - **Keyword Generation** – trigger Liz AI keyword packs.
   - **Video Fetch** – single “Fetch Inventory” action retrieves videos and (optionally) channels with weighted keyword rotation.
   - **Content Scoring** – batch score, inspect rich visuals, export results.

---

## Useful Commands

```bash
# Backend lint-style syntax check
python -m compileall api

# Reset dev database (DANGEROUS – removes all data)
rm youtube_pipeline.db && python scripts/init_db.py

# Regenerate React type definitions after API changes
npm run build   # rebuilds and validates the frontend bundle
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `uvicorn` fails with `.env` validation error | Ensure `.env` contains all required keys with correct casing |
| React cannot reach API (`Failed to fetch`) | Confirm backend is running on `http://localhost:8000` or update `VITE_API_BASE_URL` |
| `npm install` raises peer dependency warnings | Safe to ignore; `npm install --legacy-peer-deps` is another option |
| API quota exceeded | Lower fetch batch sizes or rotate YouTube API keys |

---

You’re ready to explore the YouTube Contextual Intelligence stack locally. Enjoy experimenting! 🚀

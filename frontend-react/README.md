# YouTube Contextual React App

Modern React + Vite interface for the YouTube Contextual Product Pipeline.

## Stack
- React 18 + TypeScript
- Vite + SWC
- React Router DOM
- @tanstack/react-query for data fetching
- Axios for API calls

## Getting Started

```bash
cd frontend-react
npm install
npm run dev
```

Create a `.env` file with the backend URL (defaults to `http://localhost:8000`):

```
VITE_API_BASE_URL=http://localhost:8000
```

## Project Structure
- `src/components` – reusable UI building blocks
- `src/pages` – top-level routed pages (Campaign, Keywords, Video Fetch, Scoring)
- `src/api` – typed API clients for FastAPI endpoints

Each page currently contains a scaffold matching the Streamlit flow. Build out the detailed UI by wiring to the backend endpoints, using the `CampaignAPI` pattern as a guide.

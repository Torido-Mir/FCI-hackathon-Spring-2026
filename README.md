# MillionReady — Automated Data Platform
 
A hackathon project for the FCI Winter 2026 Hackathon. This tool automates the data collection, transformation, and visualization pipeline for the [Vision One Million Scorecard](https://bestwr.org/) — tracking Waterloo Region's readiness to grow to 1 million residents across five sectors: housing, transportation, healthcare, employment, and placemaking.
 
## Project Structure
 
```
/
├── backend/        # Python FastAPI backend — data collection, pipeline, PostgreSQL
├── frontend/       # React + Vite frontend — live scorecard dashboard
└── README.md       # You are here
```
 
## Architecture Overview
 
```
Data Sources (CMHC housing data)
        ↓
APScheduler (cron-style scheduled jobs)
        ↓
FastAPI /fetch-data endpoint
        ↓  (requests, BeautifulSoup, openpyxl, pandas)
Pandas (clean + transform)
        ↓
PostgreSQL (store housing metrics)
        ↓
FastAPI /metrics endpoint
        ↓
React + Vite Dashboard (housing metrics, vacancy rates, trends)
```
 
## Quickstart
 
### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL (local or Supabase)
 
### 1. Clone the repo
```bash
git clone <your-repo-url>
cd <repo-name>
```
 
### 2. Set up the backend
```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # fill in your DB credentials
uvicorn main:app --reload
```
 
### 3. Set up the frontend
```bash
cd frontend
npm install
cp .env.example .env          # set VITE_API_URL
npm run dev
```
 
### 4. Open the app
- Frontend: http://localhost:5173
- Backend API docs: http://localhost:8000/docs
 
## Team
 
Built at the FCI Winter 2026 Hackathon in collaboration with Brave Career and UW CS Club.
 
## Current Implementation
 
**Housing Sector** — Collecting and visualizing housing metrics from CMHC data (rental vacancy rates, housing starts, and completions) for the Kitchener-Cambridge-Waterloo CMA. Additional sectors (transportation, healthcare, employment, placemaking) planned for future iterations.
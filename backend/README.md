# Backend — MillionReady 
 
Python + FastAPI backend responsible for scheduled data collection, transformation, and serving scorecard metrics.
 
## Tech Stack
 
| Tool | Purpose |
|---|---|
| FastAPI | REST API framework |
| APScheduler | Cron-style scheduled data fetching |
| requests | HTTP calls to external APIs (StatCan, CMHC, etc.) |
| BeautifulSoup4 (if necessary) | HTML scraping for sources without APIs |
| pdfplumber (if necessary) | Extracting data from PDF reports |
| pandas | Cleaning and transforming raw data |
| SQLAlchemy | ORM for PostgreSQL |
| psycopg2-binary | PostgreSQL driver |
| uvicorn (may be added later) | ASGI server |
 
## Setup
 
### 1. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
```
 
### 2. Install dependencies
```bash
pip install -r requirements.txt
```
 
### 3. Configure environment variables
```bash
cp .env.example .env
```
 
Fill in `.env`:
```
DATABASE_URL=postgresql://user:password@localhost:5432/scorecard
FETCH_INTERVAL_MINUTES=60
```
 
If using Supabase, your `DATABASE_URL` will look like:
```
DATABASE_URL=postgresql://postgres:<password>@db.<project>.supabase.co:5432/postgres
```
 
### 4. Initialize the database
```bash
python init_db.py
```
 
### 5. Run the server
```bash
uvicorn main:app --reload
```
 
API docs available at: http://localhost:8000/docs
 
## Project Structure
 
```
backend/
├── main.py              # FastAPI app, route definitions, scheduler startup
├── init_db.py           # Creates tables on first run
├── requirements.txt
├── .env.example
├── collectors/
│   ├── statcan.py       # Statistics Canada WDS API calls
│   ├── city_waterloo.py # City of Waterloo open data / scraper
│   └── base.py          # Shared fetch + retry logic
├── models/
│   └── metrics.py       # SQLAlchemy table definitions
└── pipeline/
    ├── transform.py     # Pandas cleaning + metric calculation
    └── score.py         # Raw value → 0–100 score + status label
```
 
## API Endpoints
 
### `POST /fetchData`
Triggers the full data collection pipeline manually. Called by the frontend's **refetch** button and by the APScheduler on its cron schedule.
 
**Response:**
```json
{
  "status": "ok",
  "fetched_at": "2026-03-22T14:35:00Z",
  "metrics_updated": 6
}
```
 
### `GET /metrics`
Returns the most recent scorecard metrics from the database. Called by the frontend's **refresh** button to check for newer data without re-fetching from sources.
 
**Response:**
```json
{
  "fetched_at": "2026-03-22T14:35:00Z",
  "sector": "employment",
  "metrics": [
    {
      "name": "Labour force participation rate",
      "value": 67.4,
      "unit": "%",
      "score": 74,
      "status": "in_progress",
      "source": "Statistics Canada",
      "source_url": "https://www150.statcan.gc.ca/...",
      "last_updated": "2026-03-22T14:35:00Z"
    }
  ]
}
```
 
### `GET /metrics/history?metric=labour_force_participation&limit=10`
Returns historical data points for a given metric. Used by the frontend to render trend charts.
 
## Scheduler
 
APScheduler runs `fetchData` automatically on a configurable interval (default: every 60 minutes). You can change this in `.env` via `FETCH_INTERVAL_MINUTES`.
 
The scheduler starts automatically when the FastAPI app launches.
 
## Current Data Sources (Employment Sector)
 
| Source | Method | Data |
|---|---|---|
| Statistics Canada WDS API | REST API | Labour force survey, unemployment rate, participation rate |
| City of Waterloo open data | ArcGIS REST API | Local employment by sector |
| Region of Waterloo | CSV download / scrape | Business licenses, employment land data |
 
## Adding a New Collector
 
1. Create a new file in `collectors/`, e.g. `collectors/cmhc.py`
2. Implement a `fetch()` function that returns a pandas DataFrame
3. Import and call it in `main.py` inside the `fetch_data()` function
4. Add any new metric definitions to `pipeline/score.py`
 
## Demo Notes
 
- On startup, `init_db.py` seeds the database with historical data so trend charts are populated immediately
- The `/fetchData` endpoint is what the frontend **refetch** button calls live during the demo
- The `/metrics` endpoint is what the **refresh** button polls — it's fast because it only reads from the DB, no external calls
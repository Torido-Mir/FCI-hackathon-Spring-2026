# Backend -- MillionReady

Python + FastAPI backend responsible for scheduled data collection, transformation, and serving housing metrics for the Region of Waterloo scorecard.

## Tech Stack

| Tool | Purpose |
|---|---|
| FastAPI | REST API framework |
| APScheduler | Cron-style scheduled data fetching |
| requests | HTTP calls to external APIs (StatsCan) |
| BeautifulSoup4 | HTML scraping for CMHC download links |
| pandas + openpyxl | Parsing CMHC Excel files |
| SQLAlchemy | ORM for PostgreSQL |
| psycopg2-binary | PostgreSQL driver |
| uvicorn | ASGI server |

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
DATABASE_URL=postgresql://user:password@localhost:5432/millionready
ENABLE_SCHEDULER=true
```

### 4. Create the database
```bash
# In PostgreSQL
CREATE DATABASE millionready;
```

### 5. Run the server
```bash
uvicorn main:app --reload
```

The database tables are created automatically on startup.

API docs available at: http://localhost:8000/docs

## Project Structure

```
backend/
├── main.py              # FastAPI app, route definitions, lifecycle events
├── config.py            # Settings and constants (StatsCan/CMHC URLs, CMA codes)
├── database.py          # SQLAlchemy models and session management
├── models.py            # Pydantic schemas for API requests/responses
├── scheduler.py         # APScheduler configuration and jobs
├── requirements.txt
├── .env.example
└── collectors/
    ├── __init__.py
    ├── base.py          # Base collector class with logging
    ├── statscan.py      # Statistics Canada WDS API collector
    └── cmhc.py          # CMHC Excel file downloader/parser
```

## API Endpoints

### `GET /`
API information and available endpoints.

### `GET /health`
Health check with last successful collection times for each data source.

### `GET /metrics`
Returns all housing metrics grouped by category:
- `dwellings_built` - Building permits (dwelling units created)
- `vacancy_rate` - Rental vacancy rates
- `housing_starts` - New housing construction starts
- `housing_completions` - Completed housing units

### `GET /metrics/{category}`
Returns metrics for a specific category.

### `POST /fetch-data`
Triggers data collection from all sources (StatsCan + CMHC).

### `POST /fetch-data/{source}`
Triggers data collection from a specific source (`statscan` or `cmhc`).

### `GET /scheduled-jobs`
Lists scheduled data collection jobs and their next run times.

### `GET /collection-logs`
Returns recent collection log entries (success/error status, records added).

## Data Sources

### Housing Metrics (Kitchener-Cambridge-Waterloo CMA)

| Metric | Source | Method | Frequency |
|---|---|---|---|
| Dwelling Units Created | StatsCan Table 34-10-0292-01 | REST API | Monthly |
| Rental Vacancy Rate | CMHC Rental Market Survey | Excel Download | Annual |
| Housing Starts | CMHC Starts & Completions | Excel Download | Monthly |
| Housing Completions | CMHC Starts & Completions | Excel Download | Monthly |

### StatsCan API Details

- Base URL: `https://www150.statcan.gc.ca/t1/wds/rest/`
- No authentication required
- KCW CMA coordinate: `1.38`
- Table: 34-10-0292-01 (Building permits by type of structure and type of work)

### CMHC Data

CMHC does not provide a public REST API. Data is collected by:
1. Scraping the CMHC data tables page for Excel download links
2. Downloading and parsing the Excel files with pandas
3. Filtering for Kitchener-Cambridge-Waterloo rows

## Scheduler

APScheduler runs data collection automatically:
- **StatsCan**: Monthly on the 15th at 9:00 AM
- **CMHC Housing Starts**: Monthly on the 15th at 10:00 AM
- **CMHC Vacancy Rate**: Annually on December 15th at 10:00 AM

Set `ENABLE_SCHEDULER=false` in `.env` to disable automatic collection.

## Testing the Collectors

```bash
# Start the server
uvicorn main:app --reload

# Trigger manual data collection
curl -X POST http://localhost:8000/fetch-data

# Check collected metrics
curl http://localhost:8000/metrics

# Check collection logs
curl http://localhost:8000/collection-logs
```

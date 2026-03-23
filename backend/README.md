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

## Test Suite

A comprehensive pytest-based test suite covers CMHC data collection functionality, including vacancy rates, housing starts/completions, URL building, and error handling.

### Running Tests

```bash
# Run all tests
pytest tests/test_cmhc.py -v

# Run tests with coverage
pytest tests/test_cmhc.py --cov=collectors.cmhc --cov-report=html

# Run specific test class
pytest tests/test_cmhc.py::TestURLBuilding -v

# Run specific test
pytest tests/test_cmhc.py::TestDownloadAndParseExcel::test_download_and_parse_404_returns_none -v
```

### Test Coverage

The test suite (`tests/test_cmhc.py`) includes 32 tests organized in 8 test classes:

1. **TestURLBuilding** (3 tests)
   - Monthly URL construction for housing starts files
   - Validates correct year, month, and filename patterns

2. **TestRowFinding** (6 tests)
   - Finding KCW rows in vacancy data (Table 1.1.1)
   - Finding KCW rows in housing starts data (Table A4_1)
   - Handling missing or empty DataFrames
   - Testing alternative naming patterns for KCW

3. **TestDownloadAndParseExcel** (4 tests)
   - Successful Excel download and parsing
   - **404 handling** — silently returns None instead of raising
   - HTTP error handling (500s, timeouts)
   - Network exception handling

4. **TestVacancyRateExtraction** (5 tests)
   - Extracting numeric vacancy rates from rows
   - Validating correct bedroom categories (Studio, 1BR, 2BR, 3BR+, Total)
   - Verifying percent units
   - Current year date ranges
   - Skipping invalid/out-of-range values (>50%)

5. **TestHousingStartsExtraction** (3 tests)
   - Extracting housing starts columns (singles, semis, row, apt, total)
   - Extracting housing completions columns
   - Column mapping validation (10 columns, indices 1-10)

6. **TestCollectionMethods** (4 tests)
   - Successful vacancy rate collection pipeline
   - Handling missing Excel URLs
   - Graceful handling of None DataFrames (404s)
   - URL pattern validation for starts files

7. **TestEdgeCases** (5 tests)
   - NaN value handling
   - Column mapping range coverage (no overlaps)
   - KCW pattern variations in naming
   - Housing starts history start year validation
   - All 12 months defined correctly

8. **TestIntegration** (2 tests)
   - Combining vacancy rates and housing starts metrics
   - Exception handling across collection methods

### Key Fix Coverage

The test suite validates the critical 404 handling fix from March 2026:
- **404 responses now silently return None** instead of raising exceptions
- This allows monthly housing starts collection to skip missing files for older years (e.g., 2015) and continue with available files
- Test: `TestDownloadAndParseExcel::test_download_and_parse_404_returns_none`

### Legacy Test Files

Old manual test scripts are archived with `_legacy_` prefix:
- `_legacy_test_cmhc_inspect.py` — Excel file structure inspection
- `_legacy_test_cmhc_multi_year.py` — Multi-year rental vacancy testing
- `_legacy_test_cmhc_scraping.py` — Full pipeline integration testing

These can be used for manual inspection but are not run by default.

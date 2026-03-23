import logging
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc
from sqlalchemy.orm import Session

from collectors import CMHCCollector
from config import DataSource, HousingCategory, settings
from database import CollectionLogDB, HousingMetricDB, get_db, init_db
from models import FetchResponse, HealthResponse, HousingMetric, MetricsResponse
from scheduler import get_scheduled_jobs, start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    init_db()
    if settings.enable_scheduler:
        start_scheduler()

    yield

    # Shutdown
    stop_scheduler()


app = FastAPI(
    title="MillionReady Housing API",
    description="API for housing metrics data collection for the Region of Waterloo",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/",
    summary="API Overview",
    description="Returns a summary of available endpoints. Navigate to **/docs** for the full interactive Swagger UI.",
)
async def root():
    return {
        "message": "MillionReady Housing API",
        "docs": "/docs",
        "endpoints": {
            "metrics": "/metrics",
            "health": "/health",
            "fetch_data": "/fetch-data",
        },
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description=(
        "Returns the overall API health status and the timestamp of the most recent "
        "successful data collection from each source (CMHC). Use this to confirm the "
        "backend is running and that data has been collected."
    ),
)
async def health_check(db: Session = Depends(get_db)):
    """Health check with last collection times."""
    last_collections = {}

    result = (
        db.query(CollectionLogDB)
        .filter(CollectionLogDB.source == DataSource.CMHC, CollectionLogDB.status == "success")
        .order_by(desc(CollectionLogDB.collected_at))
        .first()
    )
    last_collections[DataSource.CMHC] = result.collected_at if result else None

    return HealthResponse(status="healthy", last_collections=last_collections)


@app.get(
    "/metrics",
    response_model=list[MetricsResponse],
    summary="All Housing Metrics",
    description=(
        "Returns all housing metrics for the Kitchener-Cambridge-Waterloo (KCW) CMA, "
        "grouped by category. Categories include:\n\n"
        "- **vacancy_rate** – Rental vacancy rates by bedroom type (CMHC Rental Market Survey)\n"
        "- **housing_starts** – New residential construction starts by dwelling type, monthly\n"
        "- **housing_completions** – Completed residential units by dwelling type, monthly\n\n"
        "Results are sorted newest-first within each category."
    ),
)
async def get_all_metrics(db: Session = Depends(get_db)):
    """Get all housing metrics grouped by category."""
    categories = [
        HousingCategory.VACANCY_RATE,
        HousingCategory.HOUSING_STARTS,
        HousingCategory.HOUSING_COMPLETIONS,
    ]

    results = []
    for category in categories:
        metrics = (
            db.query(HousingMetricDB)
            .filter(HousingMetricDB.category == category)
            .order_by(desc(HousingMetricDB.period_end))
            .all()
        )
        results.append(
            MetricsResponse(
                category=category,
                metrics=[HousingMetric.model_validate(m) for m in metrics],
            )
        )

    return results


@app.get(
    "/metrics/{category}",
    response_model=MetricsResponse,
    summary="Metrics by Category",
    description=(
        "Returns housing metrics for a single category. Valid values for `category`:\n\n"
        "- `vacancy_rate` – Rental vacancy rates by bedroom type\n"
        "- `housing_starts` – Monthly new construction starts by dwelling type\n"
        "- `housing_completions` – Monthly completed units by dwelling type\n\n"
        "All data is scoped to the KCW CMA (Region of Waterloo). Results are sorted newest-first."
    ),
)
async def get_metrics_by_category(category: str, db: Session = Depends(get_db)):
    """Get metrics for a specific category."""
    valid_categories = [
        HousingCategory.VACANCY_RATE,
        HousingCategory.HOUSING_STARTS,
        HousingCategory.HOUSING_COMPLETIONS,
    ]

    if category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Valid options: {valid_categories}",
        )

    metrics = (
        db.query(HousingMetricDB)
        .filter(HousingMetricDB.category == category)
        .order_by(desc(HousingMetricDB.period_end))
        .all()
    )

    return MetricsResponse(
        category=category,
        metrics=[HousingMetric.model_validate(m) for m in metrics],
    )


@app.post(
    "/fetch-data",
    response_model=FetchResponse,
    summary="Trigger Data Collection",
    description=(
        "Manually triggers a full CMHC data collection run. This fetches:\n\n"
        "1. **Rental vacancy rates** from the CMHC Rental Market Report Excel file\n"
        "2. **Housing starts & completions** from CMHC Housing Information Monthly Excel files "
        "(incrementally, from the last stored month up to today)\n\n"
        "Only new records are added — existing data is not duplicated. "
        "Returns the number of records added and any error message."
    ),
)
async def fetch_all_data(db: Session = Depends(get_db)):
    """Trigger CMHC data collection."""
    collector = CMHCCollector(db)
    records, error = collector.run()
    return FetchResponse(
        source=DataSource.CMHC,
        status="error" if error else "success",
        records_added=records,
        message=error,
    )


@app.get(
    "/scheduled-jobs",
    summary="Scheduled Jobs",
    description=(
        "Lists all background scheduler jobs and their next scheduled run times. "
        "Returns an empty list if the scheduler is disabled or not yet started."
    ),
)
async def list_scheduled_jobs():
    """Get list of scheduled data collection jobs."""
    return {"jobs": get_scheduled_jobs()}


@app.get(
    "/collection-logs",
    summary="Collection Logs",
    description=(
        "Returns recent data collection log entries, newest-first.\n\n"
        "- **source** (optional): filter by source name (e.g. `cmhc`)\n"
        "- **limit** (default 50): maximum number of log entries to return\n\n"
        "Each entry shows the source, status (`success`/`error`), number of records added, "
        "any error message, and the timestamp."
    ),
)
async def get_collection_logs(
    source: Optional[str] = None, limit: int = 50, db: Session = Depends(get_db)
):
    """Get recent collection logs."""
    query = db.query(CollectionLogDB)

    if source:
        query = query.filter(CollectionLogDB.source == source)

    logs = query.order_by(desc(CollectionLogDB.collected_at)).limit(limit).all()

    return {
        "logs": [
            {
                "id": log.id,
                "source": log.source,
                "status": log.status,
                "records_added": log.records_added,
                "error_message": log.error_message,
                "collected_at": log.collected_at,
            }
            for log in logs
        ]
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)

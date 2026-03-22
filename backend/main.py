from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from collectors import CMHCCollector, StatsCanCollector
from config import DataSource, HousingCategory, settings
from database import CollectionLogDB, HousingMetricDB, get_db, init_db
from models import FetchResponse, HealthResponse, HousingMetric, MetricsResponse
from scheduler import get_scheduled_jobs, start_scheduler, stop_scheduler


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


@app.get("/")
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


@app.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    """Health check with last collection times."""
    # Get last collection time for each source
    last_collections = {}

    for source in [DataSource.STATSCAN, DataSource.CMHC]:
        result = (
            db.query(CollectionLogDB)
            .filter(CollectionLogDB.source == source, CollectionLogDB.status == "success")
            .order_by(desc(CollectionLogDB.collected_at))
            .first()
        )
        last_collections[source] = result.collected_at if result else None

    return HealthResponse(status="healthy", last_collections=last_collections)


@app.get("/metrics", response_model=list[MetricsResponse])
async def get_all_metrics(db: Session = Depends(get_db)):
    """Get all housing metrics grouped by category."""
    categories = [
        HousingCategory.DWELLINGS_BUILT,
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


@app.get("/metrics/{category}", response_model=MetricsResponse)
async def get_metrics_by_category(category: str, db: Session = Depends(get_db)):
    """Get metrics for a specific category."""
    valid_categories = [
        HousingCategory.DWELLINGS_BUILT,
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


@app.post("/fetch-data", response_model=list[FetchResponse])
async def fetch_all_data(db: Session = Depends(get_db)):
    """Trigger data collection from all sources."""
    results = []

    # StatsCan
    statscan_collector = StatsCanCollector(db)
    records, error = statscan_collector.run()
    results.append(
        FetchResponse(
            source=DataSource.STATSCAN,
            status="error" if error else "success",
            records_added=records,
            message=error,
        )
    )

    # CMHC
    cmhc_collector = CMHCCollector(db)
    records, error = cmhc_collector.run()
    results.append(
        FetchResponse(
            source=DataSource.CMHC,
            status="error" if error else "success",
            records_added=records,
            message=error,
        )
    )

    return results


@app.post("/fetch-data/{source}", response_model=FetchResponse)
async def fetch_data_by_source(source: str, db: Session = Depends(get_db)):
    """Trigger data collection from a specific source."""
    if source == DataSource.STATSCAN:
        collector = StatsCanCollector(db)
    elif source == DataSource.CMHC:
        collector = CMHCCollector(db)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source. Valid options: {DataSource.STATSCAN}, {DataSource.CMHC}",
        )

    records, error = collector.run()
    return FetchResponse(
        source=source,
        status="error" if error else "success",
        records_added=records,
        message=error,
    )


@app.get("/scheduled-jobs")
async def list_scheduled_jobs():
    """Get list of scheduled data collection jobs."""
    return {"jobs": get_scheduled_jobs()}


@app.get("/collection-logs")
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

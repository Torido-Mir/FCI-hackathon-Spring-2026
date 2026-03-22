"""
FastAPI backend for MillionReady scorecard metrics.
Handles scheduled data collection and serves metric endpoints.
"""
import logging
import os
from datetime import datetime, UTC
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, Session
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

from models.metrics import Base, Metric
from collectors.statcan import StatCanFetcher
from collectors.city_waterloo import CityWaterlooFetcher
from pipeline.transform import clean_metrics, transform_metrics
from pipeline.score import score_metric

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in .env file")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Scheduler
scheduler = BackgroundScheduler()


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def fetch_data():
    """
    Orchestrate data collection from all sources.
    Called by /fetchData endpoint and scheduled by APScheduler.
    """
    logger.info("Starting data fetch pipeline...")

    try:
        # Instantiate fetchers
        fetchers = [
            StatCanFetcher(),
            CityWaterlooFetcher(),
            # TODO: Add additional fetchers (CMHC, Region of Waterloo, etc.)
        ]

        # Fetch data from all sources
        all_data = []
        for fetcher in fetchers:
            try:
                df = fetcher.fetch()
                all_data.append(df)
            except Exception as e:
                logger.error(f"Error fetching from {fetcher.name}: {e}")
                continue

        if not all_data:
            logger.error("No data collected from any source")
            return {"status": "error", "message": "No data collected"}

        # Combine data
        import pandas as pd
        combined_df = pd.concat(all_data, ignore_index=True)

        # Transform data
        cleaned_df = clean_metrics(combined_df)
        transformed_df = transform_metrics(cleaned_df)

        # Store in database
        db = SessionLocal()
        now = datetime.now(UTC)
        metrics_count = 0

        for _, row in transformed_df.iterrows():
            # Score the metric
            score, status = score_metric(
                name=row.get("metric_name"),
                value=row.get("value"),
                unit=row.get("unit")
            )

            # Create metric record
            metric = Metric(
                name=row.get("metric_name"),
                sector=row.get("sector", "employment"),
                unit=row.get("unit"),
                value=row.get("value"),
                score=score,
                status=status,
                source=row.get("source", "Unknown"),
                source_url=row.get("source_url"),
                fetched_at=now,
                last_updated=now,
            )
            db.add(metric)
            metrics_count += 1

        db.commit()
        db.close()

        logger.info(f"Data fetch complete: {metrics_count} metrics stored")
        return {
            "status": "ok",
            "fetched_at": now.isoformat(),
            "metrics_updated": metrics_count
        }

    except Exception as e:
        logger.error(f"Error in fetch_data: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


def scheduled_fetch():
    """Wrapper for APScheduler to call fetch_data"""
    fetch_data()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for startup/shutdown"""
    # Startup
    logger.info("Starting FastAPI app...")
    fetch_interval = int(os.getenv("FETCH_INTERVAL_MINUTES", "60"))
    scheduler.add_job(scheduled_fetch, "interval", minutes=fetch_interval)
    scheduler.start()
    logger.info(f"Scheduler started: fetch_data every {fetch_interval} minutes")

    yield

    # Shutdown
    logger.info("Shutting down FastAPI app...")
    scheduler.shutdown()


app = FastAPI(
    title="MillionReady Backend",
    description="Scorecard metrics API",
    lifespan=lifespan
)


@app.post("/fetchData")
async def fetch_data_endpoint():
    """
    Trigger the full data collection pipeline manually.
    Called by the frontend's refetch button and by APScheduler.
    """
    result = fetch_data()
    if result["status"] != "ok":
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@app.get("/metrics")
async def get_metrics():
    """
    Return the most recent scorecard metrics from the database.
    Called by the frontend's refresh button to check for newer data
    without re-fetching from sources.
    """
    # TODO: implement logic to get most recent metrics per sector
    # Group by sector and return latest metric values

    db = SessionLocal()

    try:
        # Get the latest metric per metric name using a subquery
        latest_per_name = (
            db.query(
                Metric.name,
                func.max(Metric.id).label("max_id")
            )
            .group_by(Metric.name)
            .subquery()
        )

        metrics = (
            db.query(Metric)
            .join(latest_per_name, Metric.id == latest_per_name.c.max_id)
            .order_by(Metric.fetched_at.desc())
            .all()
        )

        if not metrics:
            return {
                "fetched_at": None,
                "sector": "employment",
                "metrics": []
            }

        # Group by sector
        fetched_at = metrics[0].fetched_at if metrics else None

        return {
            "fetched_at": fetched_at.isoformat() if fetched_at else None,
            "sector": metrics[0].sector if metrics else "employment",
            "metrics": [
                {
                    "name": m.name,
                    "value": m.value,
                    "unit": m.unit,
                    "score": m.score,
                    "status": m.status,
                    "source": m.source,
                    "source_url": m.source_url,
                    "last_updated": m.last_updated.isoformat() if m.last_updated else None,
                }
                for m in metrics
            ]
        }
    finally:
        db.close()


@app.get("/metrics/history")
async def get_metrics_history(metric: str, limit: int = 10):
    """
    Return historical data points for a given metric.
    Used by the frontend to render trend charts.
    """
    # TODO: implement filtering by metric name and limit results

    db = SessionLocal()

    try:
        history = (
            db.query(Metric)
            .filter(Metric.name == metric)
            .order_by(Metric.fetched_at.desc())
            .limit(limit)
            .all()
        )

        if not history:
            raise HTTPException(status_code=404, detail=f"Metric '{metric}' not found")

        return {
            "metric": metric,
            "data": [
                {
                    "value": m.value,
                    "score": m.score,
                    "fetched_at": m.fetched_at.isoformat() if m.fetched_at else None,
                }
                for m in reversed(history)  # Return in chronological order
            ]
        }
    finally:
        db.close()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

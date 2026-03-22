"""
Initialize the database and seed with sample historical data.
Run once on first setup: python init_db.py
"""
import logging
from datetime import datetime, timedelta, UTC
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

from models.metrics import Base, Metric

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in .env file")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Create all tables"""
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tables created successfully")


def seed_historical_data():
    """Seed database with sample historical data for trend charts"""
    # TODO: implement seeding with realistic historical data
    # This should populate the database with data points from the past
    # so trend charts have something to display on first run

    session = SessionLocal()

    logger.info("Seeding historical data...")

    # Placeholder: add sample metrics from the past 30 days
    now = datetime.now(UTC)
    sample_metrics = [
        {
            "name": "Labour force participation rate",
            "sector": "employment",
            "unit": "%",
            "value": 67.4,
            "score": 74,
            "status": "good",
            "source": "Statistics Canada",
            "source_url": "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410001901",
        },
        {
            "name": "Unemployment rate",
            "sector": "employment",
            "unit": "%",
            "value": 5.2,
            "score": 75,
            "status": "good",
            "source": "Statistics Canada",
            "source_url": "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410001901",
        },
    ]

    # Add the same metrics for multiple dates to create trend data
    for days_back in range(0, 30, 5):  # Every 5 days for the past 30 days
        fetch_time = now - timedelta(days=days_back)
        for metric_data in sample_metrics:
            metric = Metric(
                name=metric_data["name"],
                sector=metric_data["sector"],
                unit=metric_data["unit"],
                value=metric_data["value"],
                score=metric_data["score"],
                status=metric_data["status"],
                source=metric_data["source"],
                source_url=metric_data["source_url"],
                fetched_at=fetch_time,
                last_updated=fetch_time,
            )
            session.add(metric)

    session.commit()
    logger.info("Historical data seeded successfully")
    session.close()


if __name__ == "__main__":
    init_db()
    seed_historical_data()
    logger.info("Database initialization complete")

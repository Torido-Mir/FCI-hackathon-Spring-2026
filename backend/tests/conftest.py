"""Pytest configuration and shared fixtures."""

import sys
from datetime import date
from pathlib import Path

# Add parent directory to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, HousingMetricDB


@pytest.fixture(scope="session")
def test_config():
    """Provide test configuration."""
    return {
        "test_db_url": "sqlite:///./test_housing_metrics.db",
    }


@pytest.fixture
def test_db_session():
    """Create a fresh test database session for each test."""
    # Use an in-memory SQLite database for testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_db_with_housing_data(test_db_session):
    """Provide a test database session with sample housing starts data."""
    # Add some sample data for November 2025
    metric1 = HousingMetricDB(
        category="Housing Starts",
        metric_name="Housing Starts - Singles - KCW CMA",
        value=100,
        unit="units",
        period_start=date(2025, 11, 1),
        period_end=date(2025, 11, 30),
        source="CMHC Housing Information Monthly",
    )
    metric2 = HousingMetricDB(
        category="Housing Starts",
        metric_name="Housing Starts - Total - KCW CMA",
        value=350,
        unit="units",
        period_start=date(2025, 11, 1),
        period_end=date(2025, 11, 30),
        source="CMHC Housing Information Monthly",
    )
    test_db_session.add(metric1)
    test_db_session.add(metric2)
    test_db_session.commit()

    yield test_db_session

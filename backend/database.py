from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class HousingMetricDB(Base):
    __tablename__ = "housing_metrics"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), index=True)
    metric_name = Column(String(100))
    value = Column(Numeric)
    unit = Column(String(20))
    period_start = Column(Date)
    period_end = Column(Date)
    source = Column(String(100))
    collected_at = Column(DateTime, default=datetime.utcnow)


class CollectionLogDB(Base):
    __tablename__ = "collection_log"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), index=True)
    status = Column(String(20))
    records_added = Column(Integer)
    error_message = Column(Text)
    collected_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency for getting database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

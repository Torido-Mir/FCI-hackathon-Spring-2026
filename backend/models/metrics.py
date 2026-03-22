from datetime import datetime, UTC
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Metric(Base):
    """Scorecard metric data point"""
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True)

    # Metric metadata
    name = Column(String(255), nullable=False)
    sector = Column(String(100), nullable=False)  # e.g., "employment", "housing"
    unit = Column(String(50), nullable=False)  # e.g., "%", "$", "count"

    # Data values
    value = Column(Float, nullable=False)  # Raw value from source
    score = Column(Integer, nullable=False)  # 0-100 score
    status = Column(String(50), nullable=False)  # "good", "in_progress", "at_risk"

    # Source tracking
    source = Column(String(255), nullable=False)  # e.g., "Statistics Canada"
    source_url = Column(Text)

    # Timestamps
    last_updated = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    fetched_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    def __repr__(self):
        return f"<Metric {self.name}={self.value}{self.unit} (score: {self.score})>"

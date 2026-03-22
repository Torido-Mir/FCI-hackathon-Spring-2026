from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from database import CollectionLogDB, HousingMetricDB
from models import HousingMetricCreate


class BaseCollector(ABC):
    """Base class for all data collectors."""

    source_name: str = "unknown"

    def __init__(self, db: Session):
        self.db = db

    @abstractmethod
    def collect(self) -> list[HousingMetricCreate]:
        """Collect data from the source. Returns list of metrics to store."""
        pass

    def run(self) -> tuple[int, Optional[str]]:
        """Execute collection and store results in database."""
        try:
            metrics = self.collect()
            records_added = 0

            for metric in metrics:
                db_metric = HousingMetricDB(
                    category=metric.category,
                    metric_name=metric.metric_name,
                    value=metric.value,
                    unit=metric.unit,
                    period_start=metric.period_start,
                    period_end=metric.period_end,
                    source=metric.source,
                )
                self.db.add(db_metric)
                records_added += 1

            self._log_collection("success", records_added, None)
            self.db.commit()
            return records_added, None

        except Exception as e:
            self.db.rollback()
            error_msg = str(e)
            self._log_collection("error", 0, error_msg)
            self.db.commit()
            return 0, error_msg

    def _log_collection(
        self, status: str, records_added: int, error_message: Optional[str]
    ):
        """Log collection attempt to the database."""
        log_entry = CollectionLogDB(
            source=self.source_name,
            status=status,
            records_added=records_added,
            error_message=error_message,
        )
        self.db.add(log_entry)

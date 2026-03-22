from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class HousingMetricBase(BaseModel):
    category: str
    metric_name: str
    value: Decimal
    unit: Optional[str] = None
    period_start: date
    period_end: date
    source: str


class HousingMetricCreate(HousingMetricBase):
    pass


class HousingMetric(HousingMetricBase):
    id: int
    collected_at: datetime

    class Config:
        from_attributes = True


class CollectionLogBase(BaseModel):
    source: str
    status: str
    records_added: int
    error_message: Optional[str] = None


class CollectionLogCreate(CollectionLogBase):
    pass


class CollectionLog(CollectionLogBase):
    id: int
    collected_at: datetime

    class Config:
        from_attributes = True


class MetricsResponse(BaseModel):
    category: str
    metrics: list[HousingMetric]


class HealthResponse(BaseModel):
    status: str
    last_collections: dict[str, Optional[datetime]]


class FetchResponse(BaseModel):
    source: str
    status: str
    records_added: int
    message: Optional[str] = None

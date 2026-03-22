from datetime import date, datetime
from decimal import Decimal

import requests
from sqlalchemy.orm import Session

from collectors.base import BaseCollector
from config import DataSource, HousingCategory, settings
from models import HousingMetricCreate


class StatsCanCollector(BaseCollector):
    """Collector for Statistics Canada building permits data."""

    source_name = DataSource.STATSCAN

    def __init__(self, db: Session):
        super().__init__(db)
        self.base_url = settings.statscan_base_url
        self.table_id = settings.statscan_building_permits_table

    def collect(self) -> list[HousingMetricCreate]:
        """Fetch building permits data from StatsCan API."""
        metrics = []

        # Fetch dwelling units created for KCW CMA
        # Coordinate format: geography.type_of_structure.type_of_work.variables.seasonal_adjustment
        # 1.38 = KCW CMA
        # Using coordinate for: Total residential, New dwelling units, Units created, Unadjusted
        dwelling_data = self._fetch_data_by_coordinate(
            coordinate="1.38.4.3.2.1",  # KCW, residential, new, units created, unadjusted
            periods=12,  # Last 12 months
        )

        for data_point in dwelling_data:
            ref_period = data_point.get("refPer", "")
            value = data_point.get("value")

            if value is None:
                continue

            # Parse reference period (format: "2024-01")
            try:
                period_date = datetime.strptime(ref_period, "%Y-%m").date()
                period_start = period_date.replace(day=1)
                # Get last day of month
                if period_date.month == 12:
                    period_end = period_date.replace(day=31)
                else:
                    next_month = period_date.replace(month=period_date.month + 1, day=1)
                    period_end = next_month.replace(
                        day=1
                    ) - __import__("datetime").timedelta(days=1)
            except ValueError:
                continue

            metrics.append(
                HousingMetricCreate(
                    category=HousingCategory.DWELLINGS_BUILT,
                    metric_name="Building Permits - Dwelling Units Created",
                    value=Decimal(str(value)),
                    unit="units",
                    period_start=period_start,
                    period_end=period_end,
                    source=f"StatsCan Table {self.table_id}",
                )
            )

        return metrics

    def _fetch_data_by_coordinate(
        self, coordinate: str, periods: int = 12
    ) -> list[dict]:
        """Fetch data from StatsCan using coordinate-based query."""
        url = f"{self.base_url}/getDataFromCubePidCoordAndLatestNPeriods"

        payload = [
            {
                "productId": self.table_id,
                "coordinate": coordinate,
                "latestN": periods,
            }
        ]

        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()

        data = response.json()

        # StatsCan returns a list with one result object
        if not data or len(data) == 0:
            return []

        result = data[0]
        if result.get("status") != "SUCCESS":
            error_msg = result.get("object", {}).get("responseStatusCode", "Unknown")
            raise ValueError(f"StatsCan API error: {error_msg}")

        return result.get("object", {}).get("vectorDataPoint", [])

    def _fetch_cube_metadata(self) -> dict:
        """Fetch metadata about the table structure."""
        url = f"{self.base_url}/getCubeMetadata"
        payload = [{"productId": self.table_id}]

        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()

        data = response.json()
        if data and len(data) > 0:
            return data[0].get("object", {})
        return {}

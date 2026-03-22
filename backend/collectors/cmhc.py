import io
from datetime import date
from decimal import Decimal
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from collectors.base import BaseCollector
from config import DataSource, HousingCategory, settings
from models import HousingMetricCreate


class CMHCCollector(BaseCollector):
    """Collector for CMHC housing data (Excel downloads)."""

    source_name = DataSource.CMHC

    # Known patterns for KCW in CMHC data
    KCW_PATTERNS = [
        "Kitchener",
        "Kitchener-Cambridge-Waterloo",
        "Kitchener - Cambridge - Waterloo",
        "KCW",
        "541",  # CMA code
    ]

    def __init__(self, db: Session):
        super().__init__(db)

    def collect(self) -> list[HousingMetricCreate]:
        """Fetch all CMHC data."""
        metrics = []

        # Try to collect rental vacancy data
        try:
            vacancy_metrics = self._collect_vacancy_rates()
            metrics.extend(vacancy_metrics)
        except Exception as e:
            print(f"Error collecting vacancy rates: {e}")

        # Try to collect housing starts/completions
        try:
            starts_metrics = self._collect_housing_starts()
            metrics.extend(starts_metrics)
        except Exception as e:
            print(f"Error collecting housing starts: {e}")

        return metrics

    def _collect_vacancy_rates(self) -> list[HousingMetricCreate]:
        """Collect rental vacancy rate data from CMHC."""
        metrics = []

        # Try to get the download page and find Excel link
        excel_url = self._find_excel_download_url(
            settings.cmhc_rental_market_url, "rental"
        )

        if not excel_url:
            print("Could not find rental market Excel URL, skipping")
            return metrics

        # Table 1.1.1 contains vacancy rates
        df = self._download_and_parse_excel(excel_url, sheet_name="Table 1.1.1")
        if df is None or df.empty:
            return metrics

        # Find KCW row (typically "Kitchener - Cambridge - Waterloo CMA")
        kcw_row = self._find_kcw_row(df)
        if kcw_row is None:
            return metrics

        # Extract vacancy rate values from the row
        metrics.extend(self._extract_vacancy_rates_from_row(kcw_row))
        return metrics

    def _collect_housing_starts(self) -> list[HousingMetricCreate]:
        """Collect housing starts and completions data from CMHC."""
        metrics = []

        excel_url = self._find_excel_download_url(
            settings.cmhc_housing_starts_url, "starts"
        )

        if not excel_url:
            print("Could not find housing starts Excel URL, skipping")
            return metrics

        df = self._download_and_parse_excel(excel_url)
        if df is None or df.empty:
            return metrics

        kcw_data = self._filter_for_kcw(df)
        if kcw_data.empty:
            return metrics

        # Look for starts and completions columns
        starts_cols = [col for col in df.columns if "start" in str(col).lower()]
        completions_cols = [
            col for col in df.columns if "complet" in str(col).lower()
        ]

        for _, row in kcw_data.iterrows():
            # Housing starts
            for col in starts_cols:
                try:
                    value = row[col]
                    if pd.notna(value):
                        year = self._extract_year(col, row)
                        metrics.append(
                            HousingMetricCreate(
                                category=HousingCategory.HOUSING_STARTS,
                                metric_name=f"Housing Starts - {col}",
                                value=Decimal(str(int(value))),
                                unit="units",
                                period_start=date(year, 1, 1),
                                period_end=date(year, 12, 31),
                                source="CMHC Starts and Completions Survey",
                            )
                        )
                except (ValueError, TypeError):
                    continue

            # Housing completions
            for col in completions_cols:
                try:
                    value = row[col]
                    if pd.notna(value):
                        year = self._extract_year(col, row)
                        metrics.append(
                            HousingMetricCreate(
                                category=HousingCategory.HOUSING_COMPLETIONS,
                                metric_name=f"Housing Completions - {col}",
                                value=Decimal(str(int(value))),
                                unit="units",
                                period_start=date(year, 1, 1),
                                period_end=date(year, 12, 31),
                                source="CMHC Starts and Completions Survey",
                            )
                        )
                except (ValueError, TypeError):
                    continue

        return metrics

    def _find_excel_download_url(self, page_url: str, data_type: str) -> Optional[str]:
        from datetime import datetime
        
        year = datetime.now().year  # assumes annual update
        
        CITY_SLUGS = {
            "rental": "kitchener-cambridge-waterloo",
            # add other cities if needed
        }
        
        slug = CITY_SLUGS.get(data_type)
        if not slug:
            return None
    
        url = (
            f"https://assets.cmhc-schl.gc.ca/sites/cmhc/professional/"
            f"housing-markets-data-and-research/housing-data-tables/rental-market/"
            f"rental-market-report-data-tables/{year}/"
            f"rmr-{slug}-{year}-en.xlsx"
        )
        
        # Verify it exists, fall back to previous year if not yet published
        resp = requests.head(url, timeout=10)
        if resp.status_code != 200:
            url = url.replace(str(year), str(year - 1))
        
        return url

    def _download_and_parse_excel(self, url: str, sheet_name: int | str = 0) -> Optional[pd.DataFrame]:
        """Download Excel file and parse into DataFrame."""
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()

            # Parse Excel file with specified sheet
            df = pd.read_excel(io.BytesIO(response.content), sheet_name=sheet_name, engine="openpyxl")
            return df
        except Exception as e:
            print(f"Error downloading/parsing Excel: {e}")
            return None

    def _find_kcw_row(self, df: pd.DataFrame) -> Optional[pd.Series]:
        """Find the KCW CMA data row in the DataFrame."""
        # Look for the CMA row specifically (contains "CMA" and KCW pattern)
        for idx, row in df.iterrows():
            first_col_value = str(row.iloc[0]).lower()

            # Must contain "cma" and a KCW pattern
            if "cma" not in first_col_value:
                continue

            if not any(pattern.lower() in first_col_value for pattern in self.KCW_PATTERNS):
                continue

            # Make sure this looks like a data row (has some convertible numeric values)
            has_numeric = False
            for val in row.iloc[1:]:
                if pd.isna(val):
                    continue
                try:
                    float(str(val))
                    has_numeric = True
                    break
                except (ValueError, TypeError):
                    continue

            if has_numeric:
                return row

        return None

    def _extract_vacancy_rates_from_row(self, row: pd.Series) -> list[HousingMetricCreate]:
        """Extract numeric vacancy rate values from a row."""
        metrics = []
        current_year = date.today().year

        for col_idx, value in enumerate(row):
            # Skip non-numeric values and NaN
            if pd.isna(value):
                continue

            try:
                numeric_value = float(value)
                # Vacancy rates should be reasonable percentages (0-50%)
                if 0 <= numeric_value <= 50:
                    # Get column name if available
                    col_name = str(row.index[col_idx]) if hasattr(row.index, '__getitem__') else f"Column {col_idx}"

                    metrics.append(
                        HousingMetricCreate(
                            category=HousingCategory.VACANCY_RATE,
                            metric_name=f"Rental Vacancy Rate - {col_name}",
                            value=Decimal(str(numeric_value)),
                            unit="percent",
                            period_start=date(current_year, 1, 1),
                            period_end=date(current_year, 12, 31),
                            source="CMHC Rental Market Survey",
                        )
                    )
            except (ValueError, TypeError):
                continue

        return metrics

    def _filter_for_kcw(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter DataFrame for Kitchener-Cambridge-Waterloo rows."""
        # Check all columns for KCW patterns
        mask = pd.Series([False] * len(df))

        for col in df.columns:
            col_values = df[col].astype(str)
            for pattern in self.KCW_PATTERNS:
                mask |= col_values.str.contains(pattern, case=False, na=False)

        return df[mask]

    def _extract_year(self, col_name: str, row: pd.Series) -> int:
        """Try to extract year from column name or row data."""
        import re

        # Try to find 4-digit year in column name
        match = re.search(r"20\d{2}", str(col_name))
        if match:
            return int(match.group())

        # Try to find year in any row value
        for val in row.values:
            match = re.search(r"20\d{2}", str(val))
            if match:
                return int(match.group())

        # Default to current year
        return date.today().year

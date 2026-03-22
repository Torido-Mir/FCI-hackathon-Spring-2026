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
            # Fall back to trying common URL patterns
            # CMHC typically uses patterns like /en/Documents/...
            print("Could not find rental market Excel URL, skipping")
            return metrics

        df = self._download_and_parse_excel(excel_url)
        if df is None or df.empty:
            return metrics

        # Find KCW rows
        kcw_data = self._filter_for_kcw(df)
        if kcw_data.empty:
            return metrics

        # Extract vacancy rate values
        # CMHC Excel structure varies, look for vacancy-related columns
        vacancy_cols = [
            col for col in df.columns if "vacancy" in str(col).lower()
        ]

        for _, row in kcw_data.iterrows():
            for col in vacancy_cols:
                try:
                    value = row[col]
                    if pd.notna(value):
                        # Try to extract year from the data or column name
                        year = self._extract_year(col, row)
                        metrics.append(
                            HousingMetricCreate(
                                category=HousingCategory.VACANCY_RATE,
                                metric_name=f"Rental Vacancy Rate - {col}",
                                value=Decimal(str(value)),
                                unit="percent",
                                period_start=date(year, 1, 1),
                                period_end=date(year, 12, 31),
                                source="CMHC Rental Market Survey",
                            )
                        )
                except (ValueError, TypeError):
                    continue

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

    def _download_and_parse_excel(self, url: str) -> Optional[pd.DataFrame]:
        """Download Excel file and parse into DataFrame."""
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()

            # Parse Excel file
            df = pd.read_excel(io.BytesIO(response.content), engine="openpyxl")
            return df
        except Exception as e:
            print(f"Error downloading/parsing Excel: {e}")
            return None

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

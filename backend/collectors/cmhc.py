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

    def _find_excel_download_url(
        self, page_url: str, data_type: str
    ) -> Optional[str]:
        """Scrape the CMHC page to find Excel download URL."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(page_url, timeout=30, headers=headers)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Look for Excel download links in href attributes
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if ".xlsx" in href.lower() or ".xls" in href.lower():
                    # Make absolute URL if needed
                    if href.startswith("/"):
                        href = f"https://www.cmhc-schl.gc.ca{href}"
                    return href

            # Also check for Excel URLs in value attributes (hidden inputs/data)
            for element in soup.find_all(True):
                for attr_name, attr_value in element.attrs.items():
                    if isinstance(attr_value, str):
                        if ".xlsx" in attr_value.lower() or ".xls" in attr_value.lower():
                            # Make absolute URL if needed
                            if attr_value.startswith("/"):
                                attr_value = f"https://www.cmhc-schl.gc.ca{attr_value}"
                            return attr_value

            # Also check for download buttons/forms
            for button in soup.find_all(["button", "input"], {"type": "submit"}):
                # Check if it's related to downloads
                text = button.get("value", "") or button.get_text()
                if "download" in text.lower():
                    # This might need form submission, return None for now
                    pass

            return None
        except Exception as e:
            print(f"Error finding Excel URL: {e}")
            return None

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

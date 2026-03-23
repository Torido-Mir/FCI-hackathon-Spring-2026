import io
import logging
from datetime import date
from decimal import Decimal
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from sqlalchemy import func
from sqlalchemy.orm import Session

from collectors.base import BaseCollector
from config import DataSource, HousingCategory, settings
from database import HousingMetricDB
from models import HousingMetricCreate

logger = logging.getLogger(__name__)


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
            logger.error(f"Error collecting vacancy rates: {e}")

        # Try to collect housing starts/completions
        try:
            starts_metrics = self._collect_housing_starts()
            metrics.extend(starts_metrics)
        except Exception as e:
            logger.error(f"Error collecting housing starts: {e}")

        return metrics

    def _collect_vacancy_rates(self) -> list[HousingMetricCreate]:
        """Collect rental vacancy rate data from CMHC."""
        metrics = []

        # Try to get the download page and find Excel link
        excel_url = self._find_excel_download_url(
            settings.cmhc_rental_market_url, "rental"
        )

        if not excel_url:
            logger.warning("Could not find rental market Excel URL, skipping")
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

    # Column indices in Table A4_1 (0 = CMA name, then data columns)
    STARTS_COMPLETIONS_COLS = {
        "Starts - Singles":          1,
        "Starts - Semis":            2,
        "Starts - Row":              3,
        "Starts - Apt. and Other":   4,
        "Starts - Total":            5,
        "Completions - Singles":     6,
        "Completions - Semis":       7,
        "Completions - Row":         8,
        "Completions - Apt. and Other": 9,
        "Completions - Total":       10,
    }

    MONTH_NAMES = [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
    ]

    STARTS_HISTORY_START_YEAR = 2024

    def _build_monthly_starts_url(self, year: int, month: int) -> str:
        """Build the direct CMHC Excel URL for a given year/month."""
        month_name = self.MONTH_NAMES[month - 1]
        yr2 = str(year)[-2:]
        month2 = f"{month:02d}"
        return (
            "https://assets.cmhc-schl.gc.ca/sites/cmhc/professional/"
            "housing-markets-data-and-research/housing-data-tables/"
            f"housing-market-data/housing-information-monthly/"
            f"{year}/{month_name}/"
            f"provincial-starts-completions-dwelling-type-{month2}-{yr2}-en.xlsx"
        )

    def _get_latest_starts_period(self) -> Optional[date]:
        """Return the most recent period_start stored for housing starts/completions."""
        result = (
            self.db.query(func.max(HousingMetricDB.period_start))
            .filter(HousingMetricDB.source == "CMHC Housing Information Monthly")
            .scalar()
        )
        return result  # None if no rows exist yet

    def _collect_housing_starts(self) -> list[HousingMetricCreate]:
        """Collect monthly housing starts and completions for KCW from CMHC Excel files.

        Only fetches months not yet stored in the DB. Starts from the month after the
        latest stored period, or STARTS_HISTORY_START_YEAR if the DB is empty.

        Source: Table A4-1 – Starts and Completions by Dwelling Type (Census Metropolitan Areas).
        The Kitchener-Cambridge-Waterloo CMA corresponds to the Region of Waterloo
        (City of Kitchener, City of Cambridge, City of Waterloo, and surrounding townships).
        """
        import calendar

        metrics = []
        today = date.today()

        latest = self._get_latest_starts_period()
        if latest is None:
            start_year = self.STARTS_HISTORY_START_YEAR
            start_month = 1
        else:
            # Advance one month past the latest stored period
            if latest.month == 12:
                start_year = latest.year + 1
                start_month = 1
            else:
                start_year = latest.year
                start_month = latest.month + 1

        for year in range(start_year, today.year + 1):
            first_month = start_month if year == start_year else 1
            max_month = today.month if year == today.year else 12
            for month in range(first_month, max_month + 1):
                url = self._build_monthly_starts_url(year, month)
                df = self._download_and_parse_excel(url, sheet_name="Table A4_1")
                if df is None or df.empty:
                    continue

                kcw_row = self._find_kcw_row_in_a4(df)
                if kcw_row is None:
                    logger.warning(f"KCW row not found in {year}-{month:02d}")
                    continue

                period_start = date(year, month, 1)
                period_end = date(year, month, calendar.monthrange(year, month)[1])

                for col_name, col_idx in self.STARTS_COMPLETIONS_COLS.items():
                    try:
                        raw = kcw_row.iloc[col_idx]
                        # CMHC uses "-" for zero / suppressed values
                        if pd.isna(raw) or str(raw).strip() == "-":
                            value = Decimal("0")
                        else:
                            value = Decimal(str(int(float(str(raw)))))
                    except (ValueError, TypeError):
                        continue

                    category = (
                        HousingCategory.HOUSING_STARTS
                        if col_name.startswith("Starts")
                        else HousingCategory.HOUSING_COMPLETIONS
                    )
                    metrics.append(
                        HousingMetricCreate(
                            category=category,
                            metric_name=f"Housing {col_name} - KCW CMA",
                            value=value,
                            unit="units",
                            period_start=period_start,
                            period_end=period_end,
                            source="CMHC Housing Information Monthly",
                        )
                    )

        return metrics

    def _find_kcw_row_in_a4(self, df: pd.DataFrame) -> Optional[pd.Series]:
        """Find the Kitchener-Cambridge-Waterloo row in Table A4_1.

        The table has 6 header rows (rows 0-5); data rows start at index 6.
        Column 0 holds the CMA name.
        """
        for idx in range(6, len(df)):
            cell = str(df.iloc[idx, 0]).strip()
            if any(p.lower() in cell.lower() for p in self.KCW_PATTERNS):
                return df.iloc[idx]
        return None

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
            if response.status_code == 404:
                return None
            response.raise_for_status()

            # Parse Excel file with specified sheet
            df = pd.read_excel(io.BytesIO(response.content), sheet_name=sheet_name, engine="openpyxl")
            return df
        except Exception as e:
            logger.error(f"Error downloading/parsing Excel: {e}")
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

        # Define the manual mapping based on your column ranges
        column_mapping = {
            range(1, 6): "Studio",
            range(6, 11): "1 Bedroom",
            range(11, 16): "2 Bedroom",
            range(16, 21): "3 Bedroom +",
            range(21, 26): "Total"
        }

        for col_idx, value in enumerate(row):
            # Skip non-numeric values and NaN
            if pd.isna(value):
                continue

            try:
                numeric_value = float(value)
                # Vacancy rates should be reasonable percentages (0-50%)
                if 0 <= numeric_value <= 50:
                    
                    # --- REWRITTEN SECTION ---
                    col_name = "Unknown"
                    for r, label in column_mapping.items():
                        if col_idx in r:
                            col_name = label
                            break
                    
                    # If the column isn't in our 1-25 range, you might want to skip it
                    if col_name == "Unknown":
                        continue

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

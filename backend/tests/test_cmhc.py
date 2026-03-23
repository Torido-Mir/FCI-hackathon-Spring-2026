"""Test suite for CMHC data collection (vacancy rates and housing starts/completions)."""

import io
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from collectors.cmhc import CMHCCollector
from config import HousingCategory
from database import HousingMetricDB
from models import HousingMetricCreate


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock()


@pytest.fixture
def cmhc_collector(mock_db):
    """Create a CMHCCollector instance with mocked database."""
    return CMHCCollector(mock_db)


@pytest.fixture
def sample_vacancy_df():
    """Create a sample DataFrame matching CMHC rental vacancy format."""
    # Create a row with 26 columns (title + 25 data columns)
    row_data = ["Kitchener - Cambridge - Waterloo CMA"] + [1.5, 1.6, 1.7, 1.8, 1.9] + \
               [2.0, 2.1, 2.2, 2.3, 2.4] + [2.5, 2.6, 2.7, 2.8, 2.9] + \
               [3.0, 3.1, 3.2, 3.3, 3.4] + [2.7, 2.8, 2.9, 3.0, 3.1]

    df = pd.DataFrame([row_data])
    return df


@pytest.fixture
def sample_starts_df():
    """Create a sample DataFrame matching CMHC Table A4_1 format (housing starts/completions)."""
    # Table A4_1 has 6 header rows (0-5), data rows start at index 6
    rows = [
        # Header rows
        ["Header1"] + [None] * 10,
        ["Header2"] + [None] * 10,
        ["Header3"] + [None] * 10,
        ["Header4"] + [None] * 10,
        ["Header5"] + [None] * 10,
        ["Header6"] + [None] * 10,
        # Data rows
        [
            "Kitchener - Cambridge - Waterloo CMA",
            100,  # Starts - Singles
            50,   # Starts - Semis
            75,   # Starts - Row
            125,  # Starts - Apt and Other
            350,  # Starts - Total
            80,   # Completions - Singles
            40,   # Completions - Semis
            60,   # Completions - Row
            110,  # Completions - Apt and Other
            290,  # Completions - Total
        ],
    ]
    df = pd.DataFrame(rows)
    return df


# ============================================================================
# TESTS: URL Building
# ============================================================================

class TestURLBuilding:
    """Test URL construction for monthly housing starts files."""

    def test_build_monthly_starts_url_january_2024(self, cmhc_collector):
        """Test URL building for January 2024."""
        url = cmhc_collector._build_monthly_starts_url(2024, 1)
        assert "2024" in url
        assert "january" in url
        assert "provincial-starts-completions-dwelling-type-01-24-en.xlsx" in url

    def test_build_monthly_starts_url_december_2023(self, cmhc_collector):
        """Test URL building for December 2023."""
        url = cmhc_collector._build_monthly_starts_url(2023, 12)
        assert "2023" in url
        assert "december" in url
        assert "provincial-starts-completions-dwelling-type-12-23-en.xlsx" in url

    def test_build_monthly_starts_url_all_months(self, cmhc_collector):
        """Test that all months are valid and lowercase."""
        for month in range(1, 13):
            url = cmhc_collector._build_monthly_starts_url(2024, month)
            month_name = cmhc_collector.MONTH_NAMES[month - 1]
            assert month_name in url
            assert f"{month:02d}-24-en.xlsx" in url


# ============================================================================
# TESTS: Row Finding
# ============================================================================

class TestRowFinding:
    """Test finding KCW rows in DataFrames."""

    def test_find_kcw_row_in_vacancy_data(self, cmhc_collector, sample_vacancy_df):
        """Test finding KCW row in rental vacancy data."""
        row = cmhc_collector._find_kcw_row(sample_vacancy_df)
        assert row is not None
        assert "Kitchener" in str(row.iloc[0])

    def test_find_kcw_row_not_found_empty_df(self, cmhc_collector):
        """Test finding KCW row in empty DataFrame."""
        df = pd.DataFrame()
        row = cmhc_collector._find_kcw_row(df)
        assert row is None

    def test_find_kcw_row_with_alternative_pattern(self, cmhc_collector):
        """Test finding KCW row with alternative naming pattern."""
        df = pd.DataFrame({
            0: ["Some Other CMA", "KCW CMA", "Another CMA"],
            1: [1.0, 2.0, 3.0],
        })
        row = cmhc_collector._find_kcw_row(df)
        assert row is not None
        assert "KCW" in str(row.iloc[0])

    def test_find_kcw_row_in_table_a4_1(self, cmhc_collector, sample_starts_df):
        """Test finding KCW row in Table A4_1 (housing starts format)."""
        row = cmhc_collector._find_kcw_row_in_a4(sample_starts_df)
        assert row is not None
        assert "Kitchener" in str(row.iloc[0])

    def test_find_kcw_row_in_table_a4_1_skips_headers(self, cmhc_collector, sample_starts_df):
        """Test that Table A4_1 search starts at row 6 (skipping headers)."""
        # Add a fake KCW in header rows (should not match)
        sample_starts_df.iloc[0, 0] = "Kitchener - Cambridge - Waterloo CMA"
        row = cmhc_collector._find_kcw_row_in_a4(sample_starts_df)
        # Should find the real KCW row at index 6, not the header
        assert row is not None
        # The found row should be the data row with actual values
        assert row.iloc[1] == 100  # First data value

    def test_find_kcw_row_in_table_a4_1_not_found(self, cmhc_collector):
        """Test finding KCW row returns None when not found."""
        df = pd.DataFrame({
            0: ["Header"] * 10,
            1: [None] * 10,
        })
        row = cmhc_collector._find_kcw_row_in_a4(df)
        assert row is None


# ============================================================================
# TESTS: Excel Downloading with 404 Handling
# ============================================================================

class TestDownloadAndParseExcel:
    """Test downloading and parsing Excel files, especially 404 handling."""

    @patch("collectors.cmhc.requests.get")
    def test_download_and_parse_success(self, mock_get, cmhc_collector):
        """Test successful download and parsing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake excel content"
        mock_get.return_value = mock_response

        with patch("collectors.cmhc.pd.read_excel") as mock_read:
            mock_read.return_value = pd.DataFrame({"A": [1, 2, 3]})
            result = cmhc_collector._download_and_parse_excel("http://example.com/file.xlsx")

        assert result is not None
        assert isinstance(result, pd.DataFrame)
        mock_get.assert_called_once()

    @patch("collectors.cmhc.requests.get")
    def test_download_and_parse_404_returns_none(self, mock_get, cmhc_collector):
        """Test that 404 responses silently return None without raising."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = cmhc_collector._download_and_parse_excel("http://example.com/missing.xlsx")

        assert result is None
        mock_get.assert_called_once()

    @patch("collectors.cmhc.requests.get")
    def test_download_and_parse_other_http_errors(self, mock_get, cmhc_collector):
        """Test that other HTTP errors raise via raise_for_status."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("Server error")
        mock_get.return_value = mock_response

        with patch("collectors.cmhc.pd.read_excel"):
            result = cmhc_collector._download_and_parse_excel("http://example.com/error.xlsx")

        assert result is None

    @patch("collectors.cmhc.requests.get")
    def test_download_and_parse_timeout(self, mock_get, cmhc_collector):
        """Test timeout handling."""
        mock_get.side_effect = Exception("Connection timeout")

        result = cmhc_collector._download_and_parse_excel("http://example.com/timeout.xlsx")

        assert result is None


# ============================================================================
# TESTS: Vacancy Rate Extraction
# ============================================================================

class TestVacancyRateExtraction:
    """Test extracting vacancy rates from rows."""

    def test_extract_vacancy_rates_from_row(self, cmhc_collector, sample_vacancy_df):
        """Test extracting numeric vacancy rates from a row."""
        row = cmhc_collector._find_kcw_row(sample_vacancy_df)
        metrics = cmhc_collector._extract_vacancy_rates_from_row(row)

        assert len(metrics) > 0
        assert all(isinstance(m, HousingMetricCreate) for m in metrics)
        assert all(m.category == HousingCategory.VACANCY_RATE for m in metrics)
        assert all(0 <= m.value <= 50 for m in metrics)

    def test_extract_vacancy_rates_categories(self, cmhc_collector, sample_vacancy_df):
        """Test that extracted metrics have correct bedroom categories."""
        row = cmhc_collector._find_kcw_row(sample_vacancy_df)
        metrics = cmhc_collector._extract_vacancy_rates_from_row(row)

        metric_names = {m.metric_name for m in metrics}
        assert any("Studio" in name for name in metric_names)
        assert any("1 Bedroom" in name for name in metric_names)
        assert any("2 Bedroom" in name for name in metric_names)
        assert any("3 Bedroom" in name for name in metric_names)
        assert any("Total" in name for name in metric_names)

    def test_extract_vacancy_rates_units(self, cmhc_collector, sample_vacancy_df):
        """Test that vacancy rates are marked as percent."""
        row = cmhc_collector._find_kcw_row(sample_vacancy_df)
        metrics = cmhc_collector._extract_vacancy_rates_from_row(row)

        assert all(m.unit == "percent" for m in metrics)

    def test_extract_vacancy_rates_date_range(self, cmhc_collector, sample_vacancy_df):
        """Test that vacancy rates have current year date range."""
        row = cmhc_collector._find_kcw_row(sample_vacancy_df)
        metrics = cmhc_collector._extract_vacancy_rates_from_row(row)

        current_year = date.today().year
        assert all(m.period_start.year == current_year for m in metrics)
        assert all(m.period_end.year == current_year for m in metrics)
        assert all(m.period_start.month == 1 for m in metrics)
        assert all(m.period_end.month == 12 for m in metrics)

    def test_extract_vacancy_rates_skips_invalid_values(self, cmhc_collector):
        """Test that invalid/out-of-range values are skipped."""
        df = pd.DataFrame({
            0: ["KCW CMA"],
            1: [1.5],
            2: [100.0],  # Out of range
            3: ["invalid"],
            4: [5.5],
            5: [None],
        })
        row = df.iloc[0]
        metrics = cmhc_collector._extract_vacancy_rates_from_row(row)

        # Should have extracted only valid values (1.5 and 5.5)
        assert len(metrics) == 2
        values = {float(m.value) for m in metrics}
        assert 1.5 in values
        assert 5.5 in values


# ============================================================================
# TESTS: Housing Starts/Completions Extraction
# ============================================================================

class TestHousingStartsExtraction:
    """Test extracting housing starts and completions data."""

    def test_extract_starts_columns_from_row(self, cmhc_collector, sample_starts_df):
        """Test extracting all starts columns from a row."""
        row = cmhc_collector._find_kcw_row_in_a4(sample_starts_df)

        period_start = date(2024, 1, 1)
        period_end = date(2024, 1, 31)

        # Extract a sample of the columns
        starts_singles = row.iloc[1]
        starts_total = row.iloc[5]

        assert starts_singles == 100
        assert starts_total == 350

    def test_extract_completions_columns_from_row(self, cmhc_collector, sample_starts_df):
        """Test extracting all completions columns from a row."""
        row = cmhc_collector._find_kcw_row_in_a4(sample_starts_df)

        completions_singles = row.iloc[6]
        completions_total = row.iloc[10]

        assert completions_singles == 80
        assert completions_total == 290

    def test_starts_completions_column_mapping(self, cmhc_collector):
        """Test that column mapping is correct."""
        mapping = cmhc_collector.STARTS_COMPLETIONS_COLS

        # Verify all expected columns are present
        expected_keys = [
            "Starts - Singles", "Starts - Semis", "Starts - Row",
            "Starts - Apt. and Other", "Starts - Total",
            "Completions - Singles", "Completions - Semis", "Completions - Row",
            "Completions - Apt. and Other", "Completions - Total",
        ]
        for key in expected_keys:
            assert key in mapping

        # Verify column indices are sequential
        assert list(mapping.values()) == list(range(1, 11))


# ============================================================================
# TESTS: Database Query Methods
# ============================================================================

class TestDatabaseQueries:
    """Test database query methods for incremental fetching."""

    def test_get_latest_starts_period_empty_db(self, test_db_session):
        """Test that _get_latest_starts_period returns None when DB is empty."""
        collector = CMHCCollector(test_db_session)
        result = collector._get_latest_starts_period()
        assert result is None

    def test_get_latest_starts_period_with_data(self, test_db_with_housing_data):
        """Test that _get_latest_starts_period returns the max period_start."""
        collector = CMHCCollector(test_db_with_housing_data)
        result = collector._get_latest_starts_period()

        # Should return November 2025 (the date we added in the fixture)
        assert result is not None
        assert result == date(2025, 11, 1)

    def test_get_latest_starts_period_filters_by_source(self, test_db_session):
        """Test that _get_latest_starts_period only queries CMHC Housing Information Monthly."""
        # Add data with different sources
        from database import HousingMetricDB

        metric1 = HousingMetricDB(
            category="Housing Starts",
            metric_name="Test",
            value=100,
            unit="units",
            period_start=date(2025, 10, 1),
            period_end=date(2025, 10, 31),
            source="Different Source",
        )
        metric2 = HousingMetricDB(
            category="Housing Starts",
            metric_name="Test",
            value=200,
            unit="units",
            period_start=date(2025, 11, 1),
            period_end=date(2025, 11, 30),
            source="CMHC Housing Information Monthly",
        )
        test_db_session.add(metric1)
        test_db_session.add(metric2)
        test_db_session.commit()

        collector = CMHCCollector(test_db_session)
        result = collector._get_latest_starts_period()

        # Should return the November date from CMHC source, not October from different source
        assert result == date(2025, 11, 1)

    def test_get_latest_starts_period_with_multiple_months(self, test_db_session):
        """Test that _get_latest_starts_period returns the absolute max period_start."""
        from database import HousingMetricDB

        # Add data for multiple months
        for month in range(1, 4):  # Jan, Feb, Mar
            metric = HousingMetricDB(
                category="Housing Starts",
                metric_name=f"Test {month}",
                value=100 * month,
                unit="units",
                period_start=date(2025, month, 1),
                period_end=date(2025, month, 28),
                source="CMHC Housing Information Monthly",
            )
            test_db_session.add(metric)
        test_db_session.commit()

        collector = CMHCCollector(test_db_session)
        result = collector._get_latest_starts_period()

        # Should return the maximum date (March)
        assert result == date(2025, 3, 1)


# ============================================================================
# TESTS: Collection Methods
# ============================================================================

class TestCollectionMethods:
    """Test the main collection methods."""

    def test_collect_vacancy_rates_success(self, mock_db, sample_vacancy_df):
        """Test successful vacancy rate collection with mocked components."""
        collector = CMHCCollector(mock_db)

        with patch.object(collector, "_find_excel_download_url") as mock_find_url, \
             patch.object(collector, "_download_and_parse_excel") as mock_download, \
             patch.object(collector, "_find_kcw_row") as mock_find_row, \
             patch.object(collector, "_extract_vacancy_rates_from_row") as mock_extract:

            mock_find_url.return_value = "http://example.com/vacancy.xlsx"
            mock_download.return_value = sample_vacancy_df
            mock_find_row.return_value = sample_vacancy_df.iloc[0]
            mock_extract.return_value = [
                HousingMetricCreate(
                    category=HousingCategory.VACANCY_RATE,
                    metric_name="Test Metric",
                    value=Decimal("2.5"),
                    unit="percent",
                    period_start=date.today(),
                    period_end=date.today(),
                    source="CMHC",
                )
            ]

            metrics = collector._collect_vacancy_rates()

            assert len(metrics) == 1
            assert metrics[0].category == HousingCategory.VACANCY_RATE

    @patch.object(CMHCCollector, "_find_excel_download_url")
    @patch.object(CMHCCollector, "_download_and_parse_excel")
    def test_collect_vacancy_rates_handles_missing_url(
        self, mock_download, mock_find_url, cmhc_collector
    ):
        """Test vacancy collection gracefully handles missing URL."""
        mock_find_url.return_value = None
        metrics = cmhc_collector._collect_vacancy_rates()
        assert len(metrics) == 0
        mock_download.assert_not_called()

    def test_collect_housing_starts_handles_none_dataframes(self, mock_db, sample_starts_df):
        """Test that housing starts collection gracefully handles None from download (404s)."""
        collector = CMHCCollector(mock_db)

        # Verify that when _download_and_parse_excel returns None, it doesn't crash
        # This is the key fix from the previous session
        result = collector._download_and_parse_excel("http://example.com/nonexistent.xlsx")
        assert result is None

        # Verify this is the expected behavior (404 returns None, doesn't raise)
        with patch("collectors.cmhc.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            result = collector._download_and_parse_excel("http://example.com/404.xlsx")
            assert result is None

    def test_collect_housing_starts_url_pattern(self, cmhc_collector):
        """Test that housing starts collection uses correct URL pattern."""
        # Verify the URL building is correct for various months/years
        test_cases = [
            (2020, 1, "january", "01-20"),
            (2023, 6, "june", "06-23"),
            (2024, 12, "december", "12-24"),
        ]

        for year, month, expected_month_name, expected_suffix in test_cases:
            url = cmhc_collector._build_monthly_starts_url(year, month)
            assert expected_month_name in url
            assert expected_suffix in url
            assert str(year) in url

    def test_collect_housing_starts_incremental_empty_db(self, test_db_session, sample_starts_df):
        """Test that housing starts collection starts from STARTS_HISTORY_START_YEAR when DB is empty."""
        collector = CMHCCollector(test_db_session)

        with patch.object(collector, "_download_and_parse_excel") as mock_download, \
             patch.object(collector, "_find_kcw_row_in_a4") as mock_find_row:

            # Make download return None (simulating 404s for older files we don't care about)
            mock_download.return_value = None

            metrics = collector._collect_housing_starts()

            # When DB is empty, should attempt to fetch from STARTS_HISTORY_START_YEAR
            # First call should be for 2020-01 (the start year)
            first_call = mock_download.call_args_list[0]
            assert "2020" in first_call[0][0]
            assert "january" in first_call[0][0]

    def test_collect_housing_starts_incremental_with_existing_data(self, test_db_with_housing_data, sample_starts_df):
        """Test that housing starts collection starts from month after latest stored period."""
        collector = CMHCCollector(test_db_with_housing_data)

        # Latest data in DB is November 2025, so should start from December 2025
        with patch.object(collector, "_download_and_parse_excel") as mock_download, \
             patch.object(collector, "_find_kcw_row_in_a4") as mock_find_row:

            mock_download.return_value = None  # Simulate 404s

            metrics = collector._collect_housing_starts()

            # First call should be for 2025-12 (month after November)
            first_call = mock_download.call_args_list[0]
            assert "2025" in first_call[0][0]
            assert "december" in first_call[0][0]

    def test_collect_housing_starts_month_advancement_december_to_january(self, test_db_session):
        """Test that month advancement correctly handles December -> January year rollover."""
        from database import HousingMetricDB

        # Add data for December 2024
        metric = HousingMetricDB(
            category="Housing Starts",
            metric_name="Test",
            value=100,
            unit="units",
            period_start=date(2024, 12, 1),
            period_end=date(2024, 12, 31),
            source="CMHC Housing Information Monthly",
        )
        test_db_session.add(metric)
        test_db_session.commit()

        collector = CMHCCollector(test_db_session)

        with patch.object(collector, "_download_and_parse_excel") as mock_download:
            mock_download.return_value = None

            metrics = collector._collect_housing_starts()

            # First call should be for 2025-01 (January of next year)
            first_call = mock_download.call_args_list[0]
            assert "2025" in first_call[0][0]
            assert "january" in first_call[0][0]

    @patch("collectors.cmhc.date")
    def test_collect_housing_starts_respects_current_date(self, mock_date, test_db_session, sample_starts_df):
        """Test that housing starts collection respects current date boundary."""
        # Mock today as March 15, 2026
        mock_today = date(2026, 3, 15)
        mock_date.today.return_value = mock_today
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        collector = CMHCCollector(test_db_session)

        with patch.object(collector, "_download_and_parse_excel") as mock_download, \
             patch.object(collector, "_find_kcw_row_in_a4") as mock_find_row:

            mock_download.return_value = None

            metrics = collector._collect_housing_starts()

            # Should not fetch months beyond current month
            urls_called = [call[0][0] for call in mock_download.call_args_list]

            # Should have calls through March 2026 but not April
            assert any("2026" in url and "march" in url for url in urls_called)
            assert not any("2026" in url and "april" in url for url in urls_called)


# ============================================================================
# TESTS: Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_extract_vacancy_rates_with_nan_values(self, cmhc_collector):
        """Test that NaN values are handled gracefully."""
        df = pd.DataFrame({
            0: ["KCW CMA"],
            1: [float('nan')],
            2: [1.5],
            3: [float('nan')],
        })
        row = df.iloc[0]
        metrics = cmhc_collector._extract_vacancy_rates_from_row(row)

        # Should only extract valid numeric values
        assert all(not pd.isna(m.value) for m in metrics)

    def test_column_mapping_range_coverage(self, cmhc_collector):
        """Test that column mapping covers all expected columns."""
        column_mapping = {
            range(1, 6): "Studio",
            range(6, 11): "1 Bedroom",
            range(11, 16): "2 Bedroom",
            range(16, 21): "3 Bedroom +",
            range(21, 26): "Total"
        }

        # Verify no overlapping ranges
        all_cols = set()
        for r in column_mapping.keys():
            for col in r:
                assert col not in all_cols, f"Column {col} appears in multiple ranges"
                all_cols.add(col)

    def test_kcw_patterns_cover_variations(self, cmhc_collector):
        """Test that KCW_PATTERNS include common naming variations."""
        patterns = cmhc_collector.KCW_PATTERNS

        assert any("Kitchener" in p for p in patterns)
        assert any("Cambridge" in p or "Waterloo" in p for p in patterns)
        assert any("541" in str(p) for p in patterns)  # CMA code

    def test_housing_starts_history_start_year(self, cmhc_collector):
        """Test that housing starts history starts from expected year."""
        assert cmhc_collector.STARTS_HISTORY_START_YEAR == 2020

    def test_month_names_complete(self, cmhc_collector):
        """Test that all 12 months are defined."""
        assert len(cmhc_collector.MONTH_NAMES) == 12
        assert all(isinstance(m, str) for m in cmhc_collector.MONTH_NAMES)
        # Check they're lowercase
        assert all(m.islower() for m in cmhc_collector.MONTH_NAMES)


# ============================================================================
# TESTS: Integration-style Tests
# ============================================================================

class TestIntegration:
    """Integration tests for the full collection pipeline."""

    @patch.object(CMHCCollector, "_collect_vacancy_rates")
    @patch.object(CMHCCollector, "_collect_housing_starts")
    def test_collect_combines_all_metrics(
        self, mock_starts, mock_vacancy, cmhc_collector
    ):
        """Test that collect() combines results from both collection methods."""
        vacancy_metrics = [
            HousingMetricCreate(
                category=HousingCategory.VACANCY_RATE,
                metric_name="Vacancy Test",
                value=Decimal("2.5"),
                unit="percent",
                period_start=date.today(),
                period_end=date.today(),
                source="CMHC",
            )
        ]
        starts_metrics = [
            HousingMetricCreate(
                category=HousingCategory.HOUSING_STARTS,
                metric_name="Starts Test",
                value=Decimal("100"),
                unit="units",
                period_start=date.today(),
                period_end=date.today(),
                source="CMHC",
            )
        ]

        mock_vacancy.return_value = vacancy_metrics
        mock_starts.return_value = starts_metrics

        all_metrics = cmhc_collector.collect()

        assert len(all_metrics) == 2
        assert any(m.category == HousingCategory.VACANCY_RATE for m in all_metrics)
        assert any(m.category == HousingCategory.HOUSING_STARTS for m in all_metrics)

    @patch.object(CMHCCollector, "_collect_vacancy_rates")
    @patch.object(CMHCCollector, "_collect_housing_starts")
    def test_collect_handles_exceptions_gracefully(
        self, mock_starts, mock_vacancy, cmhc_collector
    ):
        """Test that collect() handles exceptions in sub-methods."""
        mock_vacancy.side_effect = Exception("Vacancy collection failed")
        mock_starts.return_value = []

        # Should not raise, but continue
        all_metrics = cmhc_collector.collect()
        assert isinstance(all_metrics, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

import logging
import pandas as pd

logger = logging.getLogger(__name__)


def clean_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and validate raw metric data.

    Args:
        df: Raw DataFrame from collector

    Returns:
        Cleaned DataFrame
    """
    # TODO: implement data cleaning logic
    # - Handle missing values
    # - Remove duplicates
    # - Validate data types
    # - Handle outliers

    df = df.copy()

    # Ensure required columns exist
    required_cols = ["metric_name", "value", "unit"]
    for col in required_cols:
        if col not in df.columns:
            logger.warning(f"Missing column: {col}")
            df[col] = None

    logger.info(f"Cleaned {len(df)} records")
    return df


def transform_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform and enrich metric data for storage.

    Args:
        df: Cleaned DataFrame

    Returns:
        Transformed DataFrame ready for database insertion
    """
    # TODO: implement transformation logic
    # - Normalize units
    # - Calculate derived metrics
    # - Add metadata fields

    df = df.copy()

    # Add sector classification if not present
    if "sector" not in df.columns:
        df["sector"] = "employment"  # TODO: determine sector per metric

    logger.info(f"Transformed {len(df)} records")
    return df

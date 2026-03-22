import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Scoring thresholds
GOOD_STATUS_CUTOFF = 70
IN_PROGRESS_STATUS_CUTOFF = 40


def score_metric(name: str, value: float, unit: str) -> Tuple[int, str]:
    """
    Convert raw metric value to a 0-100 score and status label.

    Args:
        name: Metric name
        value: Raw value
        unit: Unit of measurement

    Returns:
        Tuple of (score: 0-100, status: "good" | "in_progress" | "at_risk")
    """
    # TODO: implement scoring logic per metric
    # Examples:
    # - "Labour force participation rate" (%): 65%+ = good, 60-65% = in_progress, <60% = at_risk
    # - "Unemployment rate" (%): <5% = good, 5-7% = in_progress, >7% = at_risk

    # Placeholder: simple linear scoring
    if isinstance(value, (int, float)):
        score = min(100, max(0, int(value)))
    else:
        logger.warning(f"Cannot score non-numeric value: {value}")
        score = 0

    # Determine status
    if score >= GOOD_STATUS_CUTOFF:
        status = "good"
    elif score >= IN_PROGRESS_STATUS_CUTOFF:
        status = "in_progress"
    else:
        status = "at_risk"

    logger.debug(f"Scored {name}: {value}{unit} → {score} ({status})")
    return score, status

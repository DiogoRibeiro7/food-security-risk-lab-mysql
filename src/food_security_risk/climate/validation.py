"""Climate input validation."""

from __future__ import annotations

import pandas as pd


def validate_rainfall_country_year(frame: pd.DataFrame) -> None:
    """Validate rainfall country-year input data."""

    required = {
        "country_code",
        "country_name",
        "year",
        "rainfall_mm",
        "rainfall_baseline_mm",
        "rainfall_anomaly_pct",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"rainfall data is missing columns: {', '.join(sorted(missing))}")
    if (frame["rainfall_mm"] < 0).any():
        raise ValueError("rainfall_mm must be non-negative.")


def validate_rainfall_country_month(frame: pd.DataFrame) -> None:
    """Validate raw monthly rainfall input data."""

    required = {
        "country_code",
        "country_name",
        "year",
        "month",
        "rainfall_mm",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"monthly rainfall data is missing columns: {', '.join(sorted(missing))}")
    if not frame["month"].between(1, 12).all():
        raise ValueError("month values must be in 1..12.")
    if (frame["rainfall_mm"].dropna() < 0).any():
        raise ValueError("rainfall_mm must be non-negative.")

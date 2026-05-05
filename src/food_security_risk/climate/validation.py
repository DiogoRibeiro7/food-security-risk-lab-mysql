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

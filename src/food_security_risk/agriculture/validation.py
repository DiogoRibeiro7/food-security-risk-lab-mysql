"""Agriculture input validation."""

from __future__ import annotations

import pandas as pd


def validate_crop_production_country_year(frame: pd.DataFrame) -> None:
    """Validate crop-production country-year input data."""

    required = {
        "country_code",
        "country_name",
        "year",
        "crop_group",
        "production_tonnes",
        "production_baseline_tonnes",
        "production_anomaly_pct",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"crop data is missing columns: {', '.join(sorted(missing))}")
    if (frame["production_tonnes"] < 0).any():
        raise ValueError("production_tonnes must be non-negative.")

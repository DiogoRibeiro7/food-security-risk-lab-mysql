"""Food-affordability input validation."""

from __future__ import annotations

import pandas as pd


def validate_affordability_country_year(frame: pd.DataFrame) -> None:
    """Validate food-affordability country-year input data."""

    required = {
        "country_code",
        "country_name",
        "year",
        "healthy_diet_cost_ppp",
        "affordability_ratio",
        "affordability_baseline_ratio",
        "affordability_anomaly_pct",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"affordability data is missing columns: {', '.join(sorted(missing))}")
    if (frame["affordability_ratio"] < 0).any():
        raise ValueError("affordability_ratio must be non-negative.")

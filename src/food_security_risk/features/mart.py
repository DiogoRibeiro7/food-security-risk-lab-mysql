"""Analytical mart builders."""

from __future__ import annotations

import pandas as pd


REQUIRED_RAINFALL_COLUMNS = {
    "country_code",
    "country_name",
    "year",
    "rainfall_mm",
    "rainfall_baseline_mm",
    "rainfall_anomaly_pct",
}

REQUIRED_CROP_COLUMNS = {
    "country_code",
    "country_name",
    "year",
    "crop_group",
    "production_tonnes",
    "production_baseline_tonnes",
    "production_anomaly_pct",
}

REQUIRED_AFFORDABILITY_COLUMNS = {
    "country_code",
    "country_name",
    "year",
    "healthy_diet_cost_ppp",
    "affordability_ratio",
    "affordability_baseline_ratio",
    "affordability_anomaly_pct",
}


def _require_columns(frame: pd.DataFrame, required_columns: set[str], table_name: str) -> None:
    """Raise a clear error if a frame is missing required columns."""

    missing = required_columns.difference(frame.columns)
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise ValueError(f"{table_name} is missing required columns: {missing_str}")


def build_country_year_mart(
    rainfall: pd.DataFrame,
    crop: pd.DataFrame,
    affordability: pd.DataFrame,
) -> pd.DataFrame:
    """Build the country-year food-security mart from normalized tables.

    Parameters
    ----------
    rainfall:
        Rainfall country-year table.
    crop:
        Crop-production country-year table.
    affordability:
        Food-affordability country-year table.

    Returns
    -------
    pandas.DataFrame
        Joined analytical mart.
    """

    _require_columns(rainfall, REQUIRED_RAINFALL_COLUMNS, "rainfall")
    _require_columns(crop, REQUIRED_CROP_COLUMNS, "crop")
    _require_columns(affordability, REQUIRED_AFFORDABILITY_COLUMNS, "affordability")

    rainfall_clean = rainfall.copy()
    crop_clean = crop.copy()
    affordability_clean = affordability.copy()

    for frame in (rainfall_clean, crop_clean, affordability_clean):
        frame["country_code"] = frame["country_code"].astype(str).str.upper().str.strip()
        frame["year"] = frame["year"].astype(int)

    joined = rainfall_clean.merge(
        crop_clean,
        on=["country_code", "country_name", "year"],
        how="inner",
        validate="one_to_many",
    ).merge(
        affordability_clean,
        on=["country_code", "country_name", "year"],
        how="inner",
        validate="many_to_one",
    )

    joined["severe_rainfall_deficit_flag"] = (joined["rainfall_anomaly_pct"] < -20).astype(int)
    joined["severe_crop_decline_flag"] = (joined["production_anomaly_pct"] < -15).astype(int)
    joined["severe_affordability_pressure_flag"] = (joined["affordability_anomaly_pct"] > 15).astype(int)

    return joined.sort_values(["country_code", "year", "crop_group"]).reset_index(drop=True)

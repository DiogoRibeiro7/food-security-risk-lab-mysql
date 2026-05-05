"""Transparent food-security risk scoring."""

from __future__ import annotations

import numpy as np
import pandas as pd

SCORE_COLUMNS = [
    "rainfall_deficit_score",
    "food_affordability_pressure_score",
    "crop_production_decline_score",
    "volatility_score",
    "recent_deterioration_score",
]


def clamp_score(values: pd.Series | np.ndarray | float) -> pd.Series | np.ndarray | float:
    """Clamp one or more numeric values to the 0-100 score range."""

    return np.clip(values, 0.0, 100.0)


def _risk_band(score: float) -> str:
    """Convert a numeric score into a coarse risk band."""

    if score >= 75:
        return "high"
    if score >= 50:
        return "elevated"
    if score >= 25:
        return "watch"
    return "low"


def _build_driver_text(row: pd.Series) -> str:
    """Create a compact explanation for the highest scoring components."""

    drivers: list[tuple[str, float, str]] = [
        ("rainfall deficit", float(row["rainfall_deficit_score"]), "rainfall below baseline"),
        (
            "food affordability pressure",
            float(row["food_affordability_pressure_score"]),
            "food affordability ratio above baseline",
        ),
        (
            "crop-production decline",
            float(row["crop_production_decline_score"]),
            "crop production below baseline",
        ),
        ("volatility", float(row["volatility_score"]), "multiple indicators moving sharply"),
        (
            "recent deterioration",
            float(row["recent_deterioration_score"]),
            "multiple severe flags active",
        ),
    ]
    active = [text for _, value, text in sorted(drivers, key=lambda item: item[1], reverse=True) if value >= 30]
    if not active:
        return "No strong deterioration driver under the current scoring assumptions."
    return "; ".join(active[:3])


def score_food_security_risk(mart: pd.DataFrame) -> pd.DataFrame:
    """Compute component and final food-security risk scores.

    Parameters
    ----------
    mart:
        Country-year analytical mart.

    Returns
    -------
    pandas.DataFrame
        Score table containing component scores, final score, risk band, and drivers.
    """

    required = {
        "country_code",
        "country_name",
        "year",
        "crop_group",
        "rainfall_anomaly_pct",
        "production_anomaly_pct",
        "affordability_anomaly_pct",
        "severe_rainfall_deficit_flag",
        "severe_crop_decline_flag",
        "severe_affordability_pressure_flag",
    }
    missing = required.difference(mart.columns)
    if missing:
        raise ValueError(f"mart is missing required columns: {', '.join(sorted(missing))}")

    scored = mart.copy()

    scored["rainfall_deficit_score"] = clamp_score(-scored["rainfall_anomaly_pct"] * 2.5)
    scored["food_affordability_pressure_score"] = clamp_score(scored["affordability_anomaly_pct"] * 2.5)
    scored["crop_production_decline_score"] = clamp_score(-scored["production_anomaly_pct"] * 2.5)

    absolute_components = pd.concat(
        [
            scored["rainfall_anomaly_pct"].abs(),
            scored["production_anomaly_pct"].abs(),
            scored["affordability_anomaly_pct"].abs(),
        ],
        axis=1,
    )
    scored["volatility_score"] = clamp_score(absolute_components.mean(axis=1) * 2.0)

    severe_flags = (
        scored["severe_rainfall_deficit_flag"]
        + scored["severe_crop_decline_flag"]
        + scored["severe_affordability_pressure_flag"]
    )
    scored["recent_deterioration_score"] = clamp_score(severe_flags * 35.0)

    scored["food_security_risk_score"] = (
        0.30 * scored["rainfall_deficit_score"]
        + 0.25 * scored["food_affordability_pressure_score"]
        + 0.20 * scored["crop_production_decline_score"]
        + 0.15 * scored["volatility_score"]
        + 0.10 * scored["recent_deterioration_score"]
    ).round(3)

    scored["risk_band"] = scored["food_security_risk_score"].map(lambda value: _risk_band(float(value)))
    scored["main_drivers"] = scored.apply(_build_driver_text, axis=1)

    output_columns = [
        "country_code",
        "country_name",
        "year",
        "crop_group",
        *SCORE_COLUMNS,
        "food_security_risk_score",
        "risk_band",
        "main_drivers",
    ]
    return scored[output_columns].sort_values(
        ["food_security_risk_score", "country_code", "year"], ascending=[False, True, False]
    )

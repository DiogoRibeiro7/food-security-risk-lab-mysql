"""Country-month early-warning mart.

Country-year indicators are useful for a prototype, but early warning usually
needs monthly granularity: a developing drought shows up as several below-normal
rainfall months before it shows up in an annual total.

This module builds ``mart_country_month_food_security`` from monthly rainfall.
It is deliberately explicit about three things that trip up monthly analysis:

1. **Seasonality.** Anomalies are measured against a *seasonal* baseline — the
   mean rainfall for that calendar month over a reference window — not a flat
   annual mean. A dry month in the dry season is normal; a dry month in the wet
   season is a signal.
2. **Missingness.** The output is built on a complete month grid per country, so
   gaps are visible (``rainfall_observed``) rather than silently skipped. Rolling
   windows that span a gap yield missing anomalies instead of wrong ones.
3. **Lower-frequency indicators.** Annual indicators (affordability, production)
   are only carried into months when forward-fill is explicitly requested.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

REQUIRED_MONTHLY_RAINFALL_COLUMNS = {
    "country_code",
    "country_name",
    "year",
    "month",
    "rainfall_mm",
}


def _require_columns(frame: pd.DataFrame, required: set[str], table_name: str) -> None:
    """Raise a clear error if a frame is missing required columns."""

    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{table_name} is missing required columns: {', '.join(sorted(missing))}")


def _safe_anomaly_pct(value: pd.Series, baseline: pd.Series) -> pd.Series:
    """Percentage anomaly with zero/NaN baselines mapped to NaN, never infinity."""

    safe_baseline = baseline.where(baseline != 0.0)
    return cast("pd.Series", (value / safe_baseline - 1.0) * 100.0)


def _complete_month_grid(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a per-country complete year-month grid between first and last obs.

    Exposing every month in the span (even unobserved ones) is what makes
    missingness visible downstream.
    """

    frame = frame.copy()
    frame["period"] = frame["year"] * 12 + (frame["month"] - 1)

    grids = []
    names = frame.groupby("country_code")["country_name"].first().to_dict()
    spans = frame.groupby("country_code")["period"].agg(["min", "max"])
    for country_code, row in spans.iterrows():
        code = str(country_code)
        # Explicit int64: np.arange defaults to int32 on Windows, and pandas
        # cannot merge int32 keys against int64 keys.
        periods = np.arange(int(row["min"]), int(row["max"]) + 1, dtype=np.int64)
        grids.append(
            pd.DataFrame(
                {
                    "country_code": code,
                    "country_name": names[code],
                    "period": periods,
                }
            )
        )
    grid = pd.concat(grids, ignore_index=True)
    grid["year"] = grid["period"] // 12
    grid["month"] = grid["period"] % 12 + 1
    return grid


def build_country_month_mart(
    rainfall: pd.DataFrame,
    *,
    baseline_years: tuple[int, int] | None = None,
    annual_indicators: pd.DataFrame | None = None,
    forward_fill_annual: bool = False,
    deficit_threshold_pct: float = -25.0,
) -> pd.DataFrame:
    """Build the country-month early-warning mart from monthly rainfall.

    Parameters
    ----------
    rainfall:
        Monthly rainfall with ``country_code``, ``country_name``, ``year``,
        ``month`` (1-12), and ``rainfall_mm``. Gaps are allowed and surfaced.
    baseline_years:
        Inclusive ``(first, last)`` reference window for the seasonal baseline.
        ``None`` uses every available year.
    annual_indicators:
        Optional lower-frequency table keyed by ``country_code`` and ``year``.
        Its non-key columns are joined onto every month of the matching year.
    forward_fill_annual:
        When ``True``, annual indicator columns are carried forward across months
        within a country (filling years with no annual value). When ``False``,
        months whose year has no annual value stay missing.
    deficit_threshold_pct:
        Threshold (percent) on the 3-month rainfall anomaly below which a month is
        flagged as a severe rolling deficit.

    Returns
    -------
    pandas.DataFrame
        The ``mart_country_month_food_security`` frame, one row per country-month.
    """

    _require_columns(rainfall, REQUIRED_MONTHLY_RAINFALL_COLUMNS, "monthly rainfall")

    observed = rainfall.copy()
    observed["country_code"] = observed["country_code"].astype(str).str.upper().str.strip()
    observed["year"] = observed["year"].astype("int64")
    observed["month"] = observed["month"].astype("int64")
    if not observed["month"].between(1, 12).all():
        raise ValueError("month values must be in 1..12.")
    observed["rainfall_mm"] = pd.to_numeric(observed["rainfall_mm"], errors="coerce")

    grid = _complete_month_grid(observed)
    mart = grid.merge(
        observed[["country_code", "year", "month", "rainfall_mm"]],
        on=["country_code", "year", "month"],
        how="left",
        validate="one_to_one",
    )
    mart["rainfall_observed"] = mart["rainfall_mm"].notna().astype(int)

    # Seasonal baseline: mean rainfall per (country, calendar month) over the
    # reference window, using observed months only.
    baseline_src = mart[mart["rainfall_observed"] == 1]
    if baseline_years is not None:
        first, last = baseline_years
        if first > last:
            raise ValueError("baseline_years must be (first, last) with first <= last.")
        baseline_src = baseline_src[
            (baseline_src["year"] >= first) & (baseline_src["year"] <= last)
        ]
    seasonal = (
        baseline_src.groupby(["country_code", "month"])["rainfall_mm"]
        .mean()
        .rename("seasonal_baseline_mm")
    )
    mart = mart.merge(seasonal, on=["country_code", "month"], how="left")

    mart = mart.sort_values(["country_code", "period"]).reset_index(drop=True)
    mart["rainfall_anomaly_pct"] = _safe_anomaly_pct(
        mart["rainfall_mm"], mart["seasonal_baseline_mm"]
    )

    grouped = mart.groupby("country_code", sort=False)
    for window in (3, 6):
        roll_sum = grouped["rainfall_mm"].transform(
            lambda s, w=window: s.rolling(w, min_periods=w).sum()
        )
        base_sum = grouped["seasonal_baseline_mm"].transform(
            lambda s, w=window: s.rolling(w, min_periods=w).sum()
        )
        observed_count = grouped["rainfall_observed"].transform(
            lambda s, w=window: s.rolling(w, min_periods=w).sum()
        )
        mart[f"rainfall_{window}m_sum"] = roll_sum
        mart[f"rainfall_{window}m_anomaly_pct"] = _safe_anomaly_pct(roll_sum, base_sum)
        mart[f"months_observed_{window}m"] = observed_count

    # Lagged single-month anomalies for recent-deterioration detection.
    mart["rainfall_anomaly_pct_lag1"] = grouped["rainfall_anomaly_pct"].shift(1)
    mart["rainfall_anomaly_pct_lag3"] = grouped["rainfall_anomaly_pct"].shift(3)

    mart["severe_3m_deficit_flag"] = (
        mart["rainfall_3m_anomaly_pct"] < deficit_threshold_pct
    ).astype(int)
    mart["deteriorating_flag"] = (
        (mart["rainfall_anomaly_pct"] < mart["rainfall_anomaly_pct_lag1"])
        & (mart["rainfall_anomaly_pct"] < 0)
    ).astype(int)

    if annual_indicators is not None:
        mart = _attach_annual_indicators(mart, annual_indicators, forward_fill_annual)

    ordered_columns = _ordered_columns(mart)
    result = (
        mart[ordered_columns].sort_values(["country_code", "year", "month"]).reset_index(drop=True)
    )
    return cast(pd.DataFrame, result)


def _attach_annual_indicators(
    mart: pd.DataFrame,
    annual_indicators: pd.DataFrame,
    forward_fill: bool,
) -> pd.DataFrame:
    """Join annual indicators onto months, optionally forward-filling gaps."""

    _require_columns(annual_indicators, {"country_code", "year"}, "annual_indicators")
    annual = annual_indicators.copy()
    annual["country_code"] = annual["country_code"].astype(str).str.upper().str.strip()
    annual["year"] = annual["year"].astype("int64")

    indicator_columns = [c for c in annual.columns if c not in {"country_code", "year"}]
    merged = mart.merge(annual, on=["country_code", "year"], how="left")
    if forward_fill:
        merged = merged.sort_values(["country_code", "period"])
        merged[indicator_columns] = merged.groupby("country_code", sort=False)[
            indicator_columns
        ].ffill()
        merged["annual_indicator_filled"] = (
            merged.merge(
                annual.assign(_present=1)[["country_code", "year", "_present"]],
                on=["country_code", "year"],
                how="left",
            )["_present"]
            .isna()
            .astype(int)
        )
    return cast(pd.DataFrame, merged)


def _ordered_columns(mart: pd.DataFrame) -> list[str]:
    """Stable column ordering: keys, rainfall, rolling, lags, flags, then extras."""

    preferred = [
        "country_code",
        "country_name",
        "year",
        "month",
        "rainfall_mm",
        "seasonal_baseline_mm",
        "rainfall_anomaly_pct",
        "rainfall_observed",
        "rainfall_3m_sum",
        "rainfall_3m_anomaly_pct",
        "months_observed_3m",
        "rainfall_6m_sum",
        "rainfall_6m_anomaly_pct",
        "months_observed_6m",
        "rainfall_anomaly_pct_lag1",
        "rainfall_anomaly_pct_lag3",
        "severe_3m_deficit_flag",
        "deteriorating_flag",
    ]
    present = [c for c in preferred if c in mart.columns]
    extras = [c for c in mart.columns if c not in present and c != "period"]
    return present + extras

from __future__ import annotations

import numpy as np
import pandas as pd

from food_security_risk.climate.validation import validate_rainfall_country_month
from food_security_risk.features.monthly import build_country_month_mart
from food_security_risk.sample_data import generate_monthly_rainfall


def _monthly_series(rainfall_by_period: dict[tuple[int, int], float]) -> pd.DataFrame:
    rows = [
        {
            "country_code": "KEN",
            "country_name": "Kenya",
            "year": year,
            "month": month,
            "rainfall_mm": value,
        }
        for (year, month), value in rainfall_by_period.items()
    ]
    return pd.DataFrame(rows)


def _full_two_years(value_fn) -> pd.DataFrame:
    rows = []
    for year in (2020, 2021):
        for month in range(1, 13):
            rows.append(
                {
                    "country_code": "KEN",
                    "country_name": "Kenya",
                    "year": year,
                    "month": month,
                    "rainfall_mm": value_fn(year, month),
                }
            )
    return pd.DataFrame(rows)


def test_seasonal_baseline_is_per_calendar_month() -> None:
    # Each calendar month has a distinct level; baseline must match that month.
    frame = _full_two_years(lambda year, month: float(month * 10))
    mart = build_country_month_mart(frame)
    for month in range(1, 13):
        rows = mart[mart["month"] == month]
        assert (rows["seasonal_baseline_mm"] == month * 10).all()
        # Constant across years -> zero monthly anomaly.
        assert np.allclose(rows["rainfall_anomaly_pct"], 0.0)


def test_monthly_anomaly_vs_seasonal_baseline() -> None:
    # 2020 baseline is flat 100; in 2021 March is halved -> -50% anomaly.
    def value(year, month):
        if year == 2021 and month == 3:
            return 50.0
        return 100.0

    frame = _full_two_years(value)
    mart = build_country_month_mart(frame, baseline_years=(2020, 2020))
    march_2021 = mart[(mart["year"] == 2021) & (mart["month"] == 3)].iloc[0]
    assert march_2021["seasonal_baseline_mm"] == 100.0
    assert round(march_2021["rainfall_anomaly_pct"], 1) == -50.0


def test_rolling_3m_and_6m_anomaly() -> None:
    frame = _full_two_years(lambda year, month: 100.0)
    # Halve the last three months of 2021 -> 3m sum 150 vs baseline 300 = -50%.
    for month in (10, 11, 12):
        frame.loc[(frame["year"] == 2021) & (frame["month"] == month), "rainfall_mm"] = 50.0
    mart = build_country_month_mart(frame, baseline_years=(2020, 2020))
    dec = mart[(mart["year"] == 2021) & (mart["month"] == 12)].iloc[0]
    assert dec["rainfall_3m_sum"] == 150.0
    assert round(dec["rainfall_3m_anomaly_pct"], 1) == -50.0
    assert dec["months_observed_3m"] == 3
    assert dec["severe_3m_deficit_flag"] == 1


def test_lagged_anomalies() -> None:
    frame = _full_two_years(lambda year, month: float(100 + month))
    mart = build_country_month_mart(frame)
    ken = mart[mart["country_code"] == "KEN"].reset_index(drop=True)
    # lag1 of row i equals the anomaly of row i-1.
    assert np.isnan(ken.loc[0, "rainfall_anomaly_pct_lag1"])
    assert ken.loc[5, "rainfall_anomaly_pct_lag1"] == ken.loc[4, "rainfall_anomaly_pct"]
    assert ken.loc[5, "rainfall_anomaly_pct_lag3"] == ken.loc[2, "rainfall_anomaly_pct"]


def test_missing_months_are_surfaced_and_break_rolling_windows() -> None:
    # Build a full year then drop June (month 6); the grid must still contain it.
    frame = _full_two_years(lambda year, month: 100.0)
    frame = frame[~((frame["year"] == 2021) & (frame["month"] == 6))]
    mart = build_country_month_mart(frame)

    june = mart[(mart["year"] == 2021) & (mart["month"] == 6)]
    assert len(june) == 1  # missing month still present in the grid
    assert june.iloc[0]["rainfall_observed"] == 0
    assert pd.isna(june.iloc[0]["rainfall_mm"])

    # A 3-month window covering June yields a missing 3m anomaly, not a wrong one.
    august = mart[(mart["year"] == 2021) & (mart["month"] == 8)].iloc[0]
    assert pd.isna(august["rainfall_3m_anomaly_pct"])
    assert august["months_observed_3m"] == 2


def test_annual_indicators_not_filled_by_default() -> None:
    frame = _full_two_years(lambda year, month: 100.0)
    annual = pd.DataFrame(
        {"country_code": ["KEN"], "year": [2020], "affordability_anomaly_pct": [12.0]}
    )
    mart = build_country_month_mart(frame, annual_indicators=annual)
    # 2020 months get the value; 2021 (no annual row) stays missing.
    assert (mart[mart["year"] == 2020]["affordability_anomaly_pct"] == 12.0).all()
    assert mart[mart["year"] == 2021]["affordability_anomaly_pct"].isna().all()


def test_annual_indicators_forward_filled_when_configured() -> None:
    frame = _full_two_years(lambda year, month: 100.0)
    annual = pd.DataFrame(
        {"country_code": ["KEN"], "year": [2020], "affordability_anomaly_pct": [12.0]}
    )
    mart = build_country_month_mart(frame, annual_indicators=annual, forward_fill_annual=True)
    assert (mart["affordability_anomaly_pct"] == 12.0).all()
    # The filled-forward flag marks the synthesized 2021 months.
    assert (mart[mart["year"] == 2021]["annual_indicator_filled"] == 1).all()
    assert (mart[mart["year"] == 2020]["annual_indicator_filled"] == 0).all()


def test_sample_monthly_data_builds_a_valid_mart_with_drought_signal() -> None:
    rainfall = generate_monthly_rainfall(start_year=2018, end_year=2024, seed=7)
    validate_rainfall_country_month(rainfall)
    mart = build_country_month_mart(rainfall, baseline_years=(2018, 2021))

    # The injected 2022 drought (KEN/SOM/ETH) should trigger rolling deficits.
    drought_window = mart[
        (mart["country_code"] == "KEN") & (mart["year"] == 2022) & (mart["month"].between(6, 8))
    ]
    assert drought_window["severe_3m_deficit_flag"].sum() >= 1
    assert mart["rainfall_anomaly_pct"].notna().any()

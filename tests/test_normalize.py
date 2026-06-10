from __future__ import annotations

import json

import pandas as pd

from food_security_risk.affordability.validation import validate_affordability_country_year
from food_security_risk.agriculture.validation import validate_crop_production_country_year
from food_security_risk.climate.validation import validate_rainfall_country_year
from food_security_risk.ingestion.normalize import (
    DEFAULT_FAOSTAT_COUNTRY_MAP,
    compute_baseline_anomaly,
    normalize_faostat_production,
    normalize_rainfall_summary,
    normalize_world_bank_affordability,
    parse_world_bank_response,
)


def test_compute_baseline_anomaly_uses_reference_window() -> None:
    frame = pd.DataFrame(
        {
            "country_code": ["KEN", "KEN", "KEN"],
            "year": [2018, 2019, 2020],
            "rainfall_mm": [100.0, 200.0, 300.0],
        }
    )
    result = compute_baseline_anomaly(
        frame,
        value_col="rainfall_mm",
        baseline_col="baseline",
        anomaly_col="anomaly_pct",
        group_cols=["country_code"],
        baseline_years=(2018, 2019),
    )
    # Baseline = mean(100, 200) = 150 for every row of the group.
    assert (result["baseline"] == 150.0).all()
    # 2020 value 300 is +100% vs the 150 baseline.
    anomaly_2020 = result.loc[result["year"] == 2020, "anomaly_pct"].iloc[0]
    assert anomaly_2020 == 100.0


def test_compute_baseline_anomaly_zero_baseline_is_missing() -> None:
    frame = pd.DataFrame(
        {"country_code": ["X", "X"], "year": [2000, 2001], "v": [0.0, 5.0]}
    )
    result = compute_baseline_anomaly(
        frame,
        value_col="v",
        baseline_col="b",
        anomaly_col="a",
        group_cols=["country_code"],
        baseline_years=(2000, 2000),
    )
    # Baseline is 0 -> anomaly must be NaN, never inf.
    assert result["a"].isna().all()


def _world_bank_payload() -> list:
    return [
        {"page": 1, "pages": 1, "per_page": 50, "total": 4},
        [
            {
                "indicator": {"id": "XX.HEALTHY.DIET", "value": "Cost of a healthy diet"},
                "country": {"id": "KE", "value": "Kenya"},
                "countryiso3code": "KEN",
                "date": "2019",
                "value": 3.0,
            },
            {
                "indicator": {"id": "XX.HEALTHY.DIET", "value": "Cost of a healthy diet"},
                "country": {"id": "KE", "value": "Kenya"},
                "countryiso3code": "KEN",
                "date": "2020",
                "value": 3.6,
            },
            # Aggregate row with no ISO3 -> must be dropped.
            {
                "indicator": {"id": "XX.HEALTHY.DIET", "value": "Cost of a healthy diet"},
                "country": {"id": "Z4", "value": "Sub-Saharan Africa"},
                "countryiso3code": "",
                "date": "2020",
                "value": 2.9,
            },
            # Missing value -> must be dropped.
            {
                "indicator": {"id": "XX.HEALTHY.DIET", "value": "Cost of a healthy diet"},
                "country": {"id": "ET", "value": "Ethiopia"},
                "countryiso3code": "ETH",
                "date": "2020",
                "value": None,
            },
        ],
    ]


def test_parse_world_bank_response_drops_aggregates_and_nulls() -> None:
    frame = parse_world_bank_response(_world_bank_payload())
    assert list(frame["country_code"]) == ["KEN", "KEN"]
    assert frame["value"].tolist() == [3.0, 3.6]


def test_parse_world_bank_response_accepts_bytes_and_str() -> None:
    payload = _world_bank_payload()
    as_bytes = parse_world_bank_response(json.dumps(payload).encode("utf-8"))
    as_str = parse_world_bank_response(json.dumps(payload))
    assert as_bytes.equals(as_str)


def test_normalize_world_bank_affordability_matches_schema() -> None:
    frame = normalize_world_bank_affordability(
        _world_bank_payload(), baseline_years=(2019, 2019)
    )
    validate_affordability_country_year(frame)
    # Baseline year ratio is 1.0 by construction; 2020 cost is 20% above baseline.
    row_2019 = frame.loc[frame["year"] == 2019].iloc[0]
    row_2020 = frame.loc[frame["year"] == 2020].iloc[0]
    assert round(row_2019["affordability_ratio"], 6) == 1.0
    assert round(row_2020["affordability_anomaly_pct"], 1) == 20.0


def _faostat_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Area": ["Kenya", "Kenya", "Kenya", "Kenya", "Atlantis"],
            "Item": ["Maize", "Wheat", "Maize", "Wheat", "Maize"],
            "Element": ["Production", "Production", "Production", "Production", "Production"],
            "Year": [2019, 2019, 2020, 2020, 2020],
            "Unit": ["t", "t", "t", "t", "t"],
            "Value": [100.0, 50.0, 120.0, 60.0, 999.0],
        }
    )


def test_normalize_faostat_sums_items_and_reports_unmapped() -> None:
    frame, unmapped = normalize_faostat_production(
        _faostat_frame(),
        country_map=DEFAULT_FAOSTAT_COUNTRY_MAP,
        crop_group="cereals",
        baseline_years=(2019, 2019),
    )
    validate_crop_production_country_year(frame)
    assert unmapped == ["Atlantis"]
    # Items summed within the country-year: 2019 -> 150, 2020 -> 180.
    prod_2019 = frame.loc[frame["year"] == 2019, "production_tonnes"].iloc[0]
    prod_2020 = frame.loc[frame["year"] == 2020, "production_tonnes"].iloc[0]
    assert prod_2019 == 150.0
    assert prod_2020 == 180.0
    assert (frame["crop_group"] == "cereals").all()


def test_normalize_faostat_only_keeps_production_element() -> None:
    frame = _faostat_frame()
    frame.loc[frame["Item"] == "Wheat", "Element"] = "Area harvested"
    staging, _ = normalize_faostat_production(
        frame,
        country_map=DEFAULT_FAOSTAT_COUNTRY_MAP,
        crop_group="cereals",
    )
    # Only Maize rows (Production) remain: 2019 -> 100, 2020 -> 120.
    assert staging.loc[staging["year"] == 2019, "production_tonnes"].iloc[0] == 100.0


def test_normalize_rainfall_summary_matches_schema() -> None:
    raw = pd.DataFrame(
        {
            "country_code": ["KEN", "KEN", "SOM"],
            "country_name": ["Kenya", "Kenya", "Somalia"],
            "year": [2019, 2020, 2020],
            "rainfall_mm": [600.0, 480.0, 250.0],
        }
    )
    frame = normalize_rainfall_summary(raw, baseline_years=(2019, 2019))
    validate_rainfall_country_year(frame)
    # Kenya 2020 is 20% below its 2019 baseline of 600.
    ken_2020 = frame.loc[(frame["country_code"] == "KEN") & (frame["year"] == 2020)].iloc[0]
    assert round(ken_2020["rainfall_anomaly_pct"], 1) == -20.0

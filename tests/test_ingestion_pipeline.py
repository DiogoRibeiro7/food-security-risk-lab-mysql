from __future__ import annotations

import pandas as pd

from food_security_risk.features.mart import build_country_year_mart
from food_security_risk.ingestion.normalize import (
    DEFAULT_FAOSTAT_COUNTRY_MAP,
    normalize_faostat_production,
    normalize_rainfall_summary,
    normalize_world_bank_affordability,
)
from food_security_risk.risk.scoring import score_food_security_risk

_YEARS = [2018, 2019, 2020]


def _world_bank_payload() -> list:
    records = []
    for code, name, base in [("KEN", "Kenya", 3.0), ("ETH", "Ethiopia", 3.5)]:
        for offset, year in enumerate(_YEARS):
            records.append(
                {
                    "indicator": {"id": "XX.DIET", "value": "Cost of a healthy diet"},
                    "country": {"id": code[:2], "value": name},
                    "countryiso3code": code,
                    "date": str(year),
                    "value": base + offset * 0.2,
                }
            )
    return [{"page": 1, "pages": 1}, records]


def _faostat_frame() -> pd.DataFrame:
    rows = []
    for area, base in [("Kenya", 100.0), ("Ethiopia", 200.0)]:
        for offset, year in enumerate(_YEARS):
            rows.append(
                {
                    "Area": area,
                    "Item": "Maize",
                    "Element": "Production",
                    "Year": year,
                    "Unit": "t",
                    "Value": base * (1.0 + 0.05 * offset),
                }
            )
    return pd.DataFrame(rows)


def _rainfall_frame() -> pd.DataFrame:
    rows = []
    for code, name, base in [("KEN", "Kenya", 600.0), ("ETH", "Ethiopia", 800.0)]:
        for offset, year in enumerate(_YEARS):
            rows.append(
                {
                    "country_code": code,
                    "country_name": name,
                    "year": year,
                    "rainfall_mm": base * (1.0 - 0.03 * offset),
                }
            )
    return pd.DataFrame(rows)


def test_real_data_normalizers_feed_mart_and_scoring() -> None:
    """Normalized real-data outputs must flow through the v0.1 mart and scorer."""

    affordability = normalize_world_bank_affordability(
        _world_bank_payload(), baseline_years=(2018, 2019)
    )
    crop, unmapped = normalize_faostat_production(
        _faostat_frame(),
        country_map=DEFAULT_FAOSTAT_COUNTRY_MAP,
        crop_group="cereals",
        baseline_years=(2018, 2019),
    )
    rainfall = normalize_rainfall_summary(_rainfall_frame(), baseline_years=(2018, 2019))

    assert not unmapped

    mart = build_country_year_mart(rainfall=rainfall, crop=crop, affordability=affordability)
    scores = score_food_security_risk(mart)

    assert len(scores) == len({"KEN", "ETH"}) * len(_YEARS)
    assert scores["food_security_risk_score"].between(0, 100).all()
    assert set(scores["country_code"]) == {"KEN", "ETH"}

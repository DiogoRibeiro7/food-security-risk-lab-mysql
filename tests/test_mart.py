from __future__ import annotations

from food_security_risk.features.mart import build_country_year_mart
from food_security_risk.sample_data import generate_sample_tables


def test_build_country_year_mart() -> None:
    tables = generate_sample_tables(start_year=2020, end_year=2021, seed=7)
    mart = build_country_year_mart(
        rainfall=tables["rainfall_country_year"],
        crop=tables["crop_production_country_year"],
        affordability=tables["food_affordability_country_year"],
    )

    assert len(mart) > 0
    assert "severe_rainfall_deficit_flag" in mart.columns
    assert "severe_crop_decline_flag" in mart.columns
    assert "severe_affordability_pressure_flag" in mart.columns

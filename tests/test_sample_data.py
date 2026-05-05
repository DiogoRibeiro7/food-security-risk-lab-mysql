from __future__ import annotations

from food_security_risk.sample_data import generate_sample_tables


def test_generate_sample_tables_has_expected_outputs() -> None:
    tables = generate_sample_tables(start_year=2020, end_year=2021, seed=7)

    assert set(tables) == {
        "rainfall_country_year",
        "crop_production_country_year",
        "food_affordability_country_year",
    }
    assert len(tables["rainfall_country_year"]) > 0
    assert "rainfall_anomaly_pct" in tables["rainfall_country_year"].columns

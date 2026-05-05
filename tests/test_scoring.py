from __future__ import annotations

from food_security_risk.features.mart import build_country_year_mart
from food_security_risk.risk.scoring import score_food_security_risk
from food_security_risk.sample_data import generate_sample_tables


def test_score_food_security_risk_range_and_columns() -> None:
    tables = generate_sample_tables(start_year=2020, end_year=2022, seed=11)
    mart = build_country_year_mart(
        rainfall=tables["rainfall_country_year"],
        crop=tables["crop_production_country_year"],
        affordability=tables["food_affordability_country_year"],
    )
    scores = score_food_security_risk(mart)

    assert "food_security_risk_score" in scores.columns
    assert scores["food_security_risk_score"].between(0, 100).all()
    assert scores["risk_band"].isin({"low", "watch", "elevated", "high"}).all()

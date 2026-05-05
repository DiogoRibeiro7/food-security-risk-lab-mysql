from __future__ import annotations

from food_security_risk.features.mart import build_country_year_mart
from food_security_risk.reporting.markdown import generate_markdown_report
from food_security_risk.risk.scoring import score_food_security_risk
from food_security_risk.sample_data import generate_sample_tables


def test_generate_markdown_report_contains_responsible_language() -> None:
    tables = generate_sample_tables(start_year=2021, end_year=2021, seed=4)
    mart = build_country_year_mart(
        rainfall=tables["rainfall_country_year"],
        crop=tables["crop_production_country_year"],
        affordability=tables["food_affordability_country_year"],
    )
    scores = score_food_security_risk(mart)
    report = generate_markdown_report(scores)

    assert "early-warning signals" in report
    assert "Top risk signals" in report

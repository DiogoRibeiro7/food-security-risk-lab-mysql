"""Pure-Python local pipeline used by examples and tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from food_security_risk.features.mart import build_country_year_mart
from food_security_risk.reporting.markdown import write_markdown_report
from food_security_risk.risk.scoring import score_food_security_risk
from food_security_risk.sample_data import write_sample_tables


def run_sample_pipeline(
    output_dir: Path,
    start_year: int = 2010,
    end_year: int = 2024,
    seed: int = 42,
) -> dict[str, Path]:
    """Run the offline sample pipeline and write outputs.

    Parameters
    ----------
    output_dir:
        Base output directory.
    start_year:
        First sample year.
    end_year:
        Last sample year.
    seed:
        Random seed.

    Returns
    -------
    dict[str, pathlib.Path]
        Paths to generated outputs.
    """

    raw_dir = output_dir / "data" / "raw"
    report_dir = output_dir / "reports" / "sample_run"
    report_dir.mkdir(parents=True, exist_ok=True)

    paths = write_sample_tables(raw_dir, start_year=start_year, end_year=end_year, seed=seed)
    rainfall = pd.read_csv(paths["rainfall_country_year"])
    crop = pd.read_csv(paths["crop_production_country_year"])
    affordability = pd.read_csv(paths["food_affordability_country_year"])

    mart = build_country_year_mart(rainfall=rainfall, crop=crop, affordability=affordability)
    scores = score_food_security_risk(mart)

    mart_path = output_dir / "data" / "processed" / "marts" / "mart_country_year_food_security.csv"
    mart_path.parent.mkdir(parents=True, exist_ok=True)
    mart.to_csv(mart_path, index=False)

    scores_path = report_dir / "food_security_scores.csv"
    scores.to_csv(scores_path, index=False)

    report_path = report_dir / "food_security_report.md"
    write_markdown_report(scores=scores, output_path=report_path, title="Food Security Risk Report")

    return {"mart": mart_path, "scores": scores_path, "report": report_path}

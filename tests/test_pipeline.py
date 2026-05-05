from __future__ import annotations

from pathlib import Path

from food_security_risk.pipeline import run_sample_pipeline


def test_run_sample_pipeline(tmp_path: Path) -> None:
    outputs = run_sample_pipeline(tmp_path, start_year=2020, end_year=2021, seed=5)

    assert outputs["mart"].exists()
    assert outputs["scores"].exists()
    assert outputs["report"].exists()

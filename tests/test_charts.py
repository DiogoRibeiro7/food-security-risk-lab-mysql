"""Tests for the chart helpers, using the headless Agg backend."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import pandas as pd
import pytest

matplotlib.use("Agg", force=True)

from food_security_risk.visualization.charts import plot_top_scores  # noqa: E402


def _scores() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "country_name": ["Kenya", "Ethiopia", "Somalia"],
            "year": [2022, 2022, 2021],
            "food_security_risk_score": [72.0, 55.0, 48.0],
        }
    )


def test_plot_top_scores_writes_a_png(tmp_path: Path) -> None:
    out = tmp_path / "charts" / "top.png"
    result = plot_top_scores(_scores(), out, n=2)

    assert result == out
    assert out.exists()
    assert out.stat().st_size > 0  # a real image was rendered


def test_plot_top_scores_requires_score_columns(tmp_path: Path) -> None:
    incomplete = pd.DataFrame({"country_name": ["Kenya"], "year": [2022]})
    with pytest.raises(ValueError, match="missing required columns"):
        plot_top_scores(incomplete, tmp_path / "top.png")

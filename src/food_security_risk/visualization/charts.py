"""Simple chart helpers for reports and notebooks."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_top_scores(scores: pd.DataFrame, output_path: Path, n: int = 10) -> Path:
    """Plot top food-security risk scores as a horizontal bar chart."""

    required = {"country_name", "year", "food_security_risk_score"}
    missing = required.difference(scores.columns)
    if missing:
        raise ValueError(f"scores is missing required columns: {', '.join(sorted(missing))}")

    top = scores.sort_values("food_security_risk_score", ascending=False).head(n).copy()
    top["label"] = top["country_name"] + " " + top["year"].astype(str)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(top["label"], top["food_security_risk_score"])
    ax.set_xlabel("Risk score")
    ax.set_ylabel("Country-year")
    ax.invert_yaxis()
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path

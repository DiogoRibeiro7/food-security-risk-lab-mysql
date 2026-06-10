"""Markdown report generation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def generate_markdown_report(scores: pd.DataFrame, title: str = "Food Security Risk Report") -> str:
    """Generate a compact Markdown report from scored rows.

    Parameters
    ----------
    scores:
        Risk score table.
    title:
        Report title.

    Returns
    -------
    str
        Markdown report content.
    """

    required = {
        "country_code",
        "country_name",
        "year",
        "crop_group",
        "food_security_risk_score",
        "risk_band",
        "main_drivers",
    }
    missing = required.difference(scores.columns)
    if missing:
        raise ValueError(f"scores is missing required columns: {', '.join(sorted(missing))}")

    top = scores.sort_values("food_security_risk_score", ascending=False).head(10)
    lines: list[str] = [
        f"# {title}",
        "",
        "This report summarizes transparent food-security risk indicators.",
        "The scores are early-warning signals and require expert review before operational use.",
        "",
        "## Top risk signals",
        "",
        "| Rank | Country | Year | Crop group | Score | Band | Main drivers |",
        "|---:|---|---:|---|---:|---|---|",
    ]

    for rank, row in enumerate(top.itertuples(index=False), start=1):
        lines.append(
            f"| {rank} | {row.country_name} ({row.country_code}) | {int(row.year)} | "
            f"{row.crop_group} | {float(row.food_security_risk_score):.1f} | "
            f"{row.risk_band} | {row.main_drivers} |"
        )

    lines.extend(
        [
            "",
            "## Responsible interpretation",
            "",
            (
                "A high score does not confirm food insecurity or famine. It "
                "means the selected rainfall, crop-production, and affordability "
                "indicators are deteriorating under the current scoring assumptions."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_markdown_report(scores: pd.DataFrame, output_path: Path, title: str) -> Path:
    """Write a Markdown report to disk."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generate_markdown_report(scores=scores, title=title), encoding="utf-8")
    return output_path

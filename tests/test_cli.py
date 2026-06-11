"""Tests for the CLI commands that do not touch MySQL.

These drive the documented offline workflow through Typer's ``CliRunner``: the
synthetic-data generators, local scoring and reporting, the monthly mart and
context joins from CSV, country harmonization, and the file-based ingest
commands. The MySQL-backed commands are exercised by ``test_mysql_integration``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from food_security_risk.cli import app

runner = CliRunner()


def _run(*args: str) -> None:
    result = runner.invoke(app, list(args))
    assert result.exit_code == 0, f"`food-risk {' '.join(args)}` failed:\n{result.output}"


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    """A directory of freshly generated country-year sample CSVs."""

    out = tmp_path / "raw"
    _run("sample-data", "--output-dir", str(out), "--start-year", "2015", "--end-year", "2020")
    return out


def test_sample_data_writes_all_three_tables(raw_dir: Path) -> None:
    for name in (
        "rainfall_country_year",
        "crop_production_country_year",
        "food_affordability_country_year",
    ):
        path = raw_dir / f"{name}.csv"
        assert path.exists()
        assert len(pd.read_csv(path)) > 0


def test_score_local_and_report_roundtrip(raw_dir: Path, tmp_path: Path) -> None:
    scores = tmp_path / "scores.csv"
    report = tmp_path / "report.md"

    _run("score-local", "--raw-dir", str(raw_dir), "--output", str(scores))
    frame = pd.read_csv(scores)
    assert {"country_code", "food_security_risk_score", "risk_band"} <= set(frame.columns)
    assert len(frame) > 0

    _run("report", "--scores", str(scores), "--output", str(report), "--title", "Test Brief")
    text = report.read_text(encoding="utf-8")
    assert "Test Brief" in text


def test_sample_monthly_then_build_mart_from_csv(tmp_path: Path) -> None:
    monthly = tmp_path / "rainfall_country_month.csv"
    mart = tmp_path / "mart.csv"

    _run("sample-monthly", "--output", str(monthly), "--start-year", "2019", "--end-year", "2022")
    _run(
        "build-monthly-mart",
        "--source",
        "csv",
        "--input-csv",
        str(monthly),
        "--output",
        str(mart),
        "--baseline-years",
        "2019-2021",
    )
    frame = pd.read_csv(mart)
    assert {"country_code", "year", "month", "rainfall_anomaly_pct"} <= set(frame.columns)
    assert len(frame) > 0


def test_sample_context_then_join_from_csv(raw_dir: Path, tmp_path: Path) -> None:
    scores = tmp_path / "scores.csv"
    context = tmp_path / "context.csv"
    annotated = tmp_path / "annotated.csv"

    _run("score-local", "--raw-dir", str(raw_dir), "--output", str(scores))
    _run("sample-context", "--output", str(context), "--start-year", "2018", "--end-year", "2020")
    _run(
        "join-context",
        "--risk-csv",
        str(scores),
        "--context-source",
        "csv",
        "--context-csv",
        str(context),
        "--level",
        "year",
        "--output",
        str(annotated),
    )
    frame = pd.read_csv(annotated)
    # Context columns are attached under a context_ prefix, never as labels.
    assert any(column.startswith("context_") for column in frame.columns)


def test_build_country_dim_to_csv(tmp_path: Path) -> None:
    out = tmp_path / "dim_country.csv"
    _run("build-country-dim", "--output", str(out), "--no-load")
    frame = pd.read_csv(out)
    assert {"iso3", "country_name"} <= set(frame.columns)
    assert len(frame) > 0


def test_map_source_countries_reports_quality(tmp_path: Path) -> None:
    source = tmp_path / "areas.csv"
    pd.DataFrame({"Area": ["Kenya", "Ethiopia", "Not A Country"]}).to_csv(source, index=False)
    out = tmp_path / "mapping.csv"

    _run(
        "map-source-countries",
        "--input-csv",
        str(source),
        "--source",
        "faostat",
        "--output",
        str(out),
    )
    mapping = pd.read_csv(out)
    assert "quality_flag" in mapping.columns
    assert len(mapping) == 3


def test_ingest_rainfall_writes_csv_and_manifest(tmp_path: Path) -> None:
    source = tmp_path / "chirps.csv"
    pd.DataFrame(
        {
            "country_code": ["KEN", "KEN", "ETH"],
            "country_name": ["Kenya", "Kenya", "Ethiopia"],
            "year": [2019, 2020, 2020],
            "rainfall_mm": [610.0, 540.0, 770.0],
        }
    ).to_csv(source, index=False)
    out = tmp_path / "rainfall_country_year.csv"
    raw = tmp_path / "raw"

    _run(
        "ingest-rainfall",
        "--input-csv",
        str(source),
        "--output",
        str(out),
        "--raw-dir",
        str(raw),
        "--baseline-years",
        "2019-2020",
    )
    frame = pd.read_csv(out)
    assert {"rainfall_baseline_mm", "rainfall_anomaly_pct"} <= set(frame.columns)

    manifest = json.loads((raw / "manifest.json").read_text(encoding="utf-8"))
    assert "rainfall_country_year" in manifest


def test_invalid_baseline_years_is_a_usage_error(tmp_path: Path) -> None:
    source = tmp_path / "chirps.csv"
    pd.DataFrame(
        {
            "country_code": ["KEN"],
            "country_name": ["Kenya"],
            "year": [2020],
            "rainfall_mm": [610.0],
        }
    ).to_csv(source, index=False)

    result = runner.invoke(
        app,
        ["ingest-rainfall", "--input-csv", str(source), "--baseline-years", "2020"],
    )
    assert result.exit_code != 0


def test_build_monthly_mart_rejects_unknown_source() -> None:
    result = runner.invoke(app, ["build-monthly-mart", "--source", "postgres"])
    assert result.exit_code != 0

"""End-to-end MySQL integration test.

Every other test in the suite runs against SQLite, so the real MySQL path — the
``sql/`` DDL, the statement-splitting SQL runner, and the schema-preserving
loaders — is otherwise unexercised. This drives the documented CLI workflow
(``sample-data`` → ``init-mysql`` → ``load-mysql`` → ``build-analytics-mysql`` →
``score-from-mysql``) against a real server.

The module is skipped unless ``RUN_MYSQL_INTEGRATION=1`` and the ``MYSQL_*``
environment variables point at a reachable server, so the default ``pytest -q``
needs no database (a v0.1 acceptance criterion). CI sets the flag and provides a
MySQL 8.4 service container; locally you can run it with the Docker Compose
database up:

    RUN_MYSQL_INTEGRATION=1 poetry run pytest tests/test_mysql_integration.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from typer.testing import CliRunner

from food_security_risk.cli import app
from food_security_risk.database.engine import create_mysql_engine

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_MYSQL_INTEGRATION") != "1",
        reason="set RUN_MYSQL_INTEGRATION=1 (and MYSQL_* env) to run MySQL integration tests",
    ),
]

runner = CliRunner()


def _run(*args: str) -> None:
    """Invoke a CLI command and fail loudly with its output on a non-zero exit."""

    result = runner.invoke(app, list(args))
    assert result.exit_code == 0, f"`food-risk {' '.join(args)}` failed:\n{result.output}"


def _scalar(engine: Engine, sql: str) -> int:
    with engine.connect() as connection:
        return int(connection.execute(text(sql)).scalar_one())


def test_full_mysql_workflow(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    scores_csv = tmp_path / "scores.csv"

    _run("sample-data", "--output-dir", str(raw_dir), "--start-year", "2018", "--end-year", "2022")

    # init-mysql twice: the schema scripts must be idempotent against real MySQL
    # (MySQL has no CREATE INDEX IF NOT EXISTS, which used to break a re-run).
    _run("init-mysql")
    _run("init-mysql")

    _run("load-mysql", "--raw-dir", str(raw_dir))
    _run("build-analytics-mysql")
    _run("score-from-mysql", "--output", str(scores_csv), "--write-back")

    assert scores_csv.exists() and scores_csv.stat().st_size > 0

    engine = create_mysql_engine()
    try:
        # The mart and scores were actually populated.
        assert _scalar(engine, "SELECT COUNT(*) FROM mart_country_year_food_security") > 0
        score_rows = _scalar(engine, "SELECT COUNT(*) FROM food_security_risk_score")
        assert score_rows > 0

        # The score table must keep the primary key from sql/04_score_tables.sql.
        # If a write had recreated the table from pandas-inferred types, this
        # composite key would be gone — the regression these loaders guard.
        primary_key = inspect(engine).get_pk_constraint("food_security_risk_score")
        assert primary_key["constrained_columns"] == ["country_code", "year", "crop_group"]

        # A replace load clears rows rather than appending: re-loading must not
        # duplicate raw staging rows.
        before = _scalar(engine, "SELECT COUNT(*) FROM raw_rainfall_country_year")
        _run("load-mysql", "--raw-dir", str(raw_dir))
        after = _scalar(engine, "SELECT COUNT(*) FROM raw_rainfall_country_year")
        assert before == after

        # Write-back is also a replace: scoring twice keeps the row count stable.
        _run("score-from-mysql", "--output", str(scores_csv), "--write-back")
        assert _scalar(engine, "SELECT COUNT(*) FROM food_security_risk_score") == score_rows
    finally:
        engine.dispose()

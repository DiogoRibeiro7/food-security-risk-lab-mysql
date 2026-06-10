"""Tests for the database layer: config, SQL runner, and loaders.

The loader and SQL-runner tests run against SQLite through SQLAlchemy. The
behaviour under test — schema-preserving replace loads, appends, statement
splitting — is engine-agnostic, so no MySQL server is needed.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from food_security_risk.database.config import MySQLConfig
from food_security_risk.database.loader import (
    RAW_FILE_TABLES,
    load_rainfall_country_month,
    load_raw_csvs,
)
from food_security_risk.database.sql_runner import _split_sql_statements, execute_sql_file


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return create_engine(f"sqlite:///{tmp_path / 'test.db'}")


def _rainfall_frame(years: list[int]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "country_code": ["KEN"] * len(years),
            "country_name": ["Kenya"] * len(years),
            "year": years,
            "rainfall_mm": [500.0] * len(years),
            "rainfall_baseline_mm": [520.0] * len(years),
            "rainfall_anomaly_pct": [-3.8] * len(years),
            "source_dataset": ["synthetic"] * len(years),
        }
    )


def _write_raw_csvs(raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    _rainfall_frame([2020, 2021]).to_csv(raw_dir / "rainfall_country_year.csv", index=False)
    pd.DataFrame(
        {
            "country_code": ["KEN"],
            "country_name": ["Kenya"],
            "year": [2020],
            "crop_group": ["cereals"],
            "production_tonnes": [1000.0],
            "production_baseline_tonnes": [1100.0],
            "production_anomaly_pct": [-9.1],
            "source_dataset": ["synthetic"],
        }
    ).to_csv(raw_dir / "crop_production_country_year.csv", index=False)
    pd.DataFrame(
        {
            "country_code": ["KEN"],
            "country_name": ["Kenya"],
            "year": [2020],
            "healthy_diet_cost_ppp": [3.5],
            "affordability_ratio": [1.1],
            "affordability_baseline_ratio": [1.0],
            "affordability_anomaly_pct": [10.0],
            "source_dataset": ["synthetic"],
        }
    ).to_csv(raw_dir / "food_affordability_country_year.csv", index=False)


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #


def test_config_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MYSQL_HOST", "db.example.org")
    monkeypatch.setenv("MYSQL_PORT", "3307")
    monkeypatch.setenv("MYSQL_DATABASE", "food_test")
    monkeypatch.setenv("MYSQL_USER", "alice")
    monkeypatch.setenv("MYSQL_PASSWORD", "secret")

    config = MySQLConfig.from_env()

    assert config.host == "db.example.org"
    assert config.port == 3307
    assert config.sqlalchemy_url == (
        "mysql+pymysql://alice:secret@db.example.org:3307/food_test?charset=utf8mb4"
    )


def test_config_defaults_without_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for variable in ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.chdir(tmp_path)  # keep load_dotenv() away from any repo-level .env

    config = MySQLConfig.from_env()

    assert config.host == "127.0.0.1"
    assert config.port == 3306
    assert config.database == "food_security_risk"


# --------------------------------------------------------------------------- #
# SQL runner
# --------------------------------------------------------------------------- #


def test_split_sql_statements_skips_comments_and_blank_lines() -> None:
    script = """
    -- create the table
    CREATE TABLE demo (id INT);

    INSERT INTO demo VALUES (1);
    INSERT INTO demo
    VALUES (2);
    """
    statements = _split_sql_statements(script)
    assert len(statements) == 3
    assert statements[0].startswith("CREATE TABLE demo")
    assert statements[2].endswith("VALUES (2)")


def test_split_sql_statements_keeps_trailing_statement_without_semicolon() -> None:
    statements = _split_sql_statements("SELECT 1")
    assert statements == ["SELECT 1"]


def test_execute_sql_file_runs_all_statements(engine: Engine, tmp_path: Path) -> None:
    sql_path = tmp_path / "init.sql"
    sql_path.write_text(
        "-- demo schema\n"
        "CREATE TABLE demo (id INTEGER PRIMARY KEY, label TEXT);\n"
        "INSERT INTO demo (id, label) VALUES (1, 'a');\n"
        "INSERT INTO demo (id, label) VALUES (2, 'b');\n",
        encoding="utf-8",
    )

    execute_sql_file(engine, sql_path)

    with engine.connect() as connection:
        count = connection.execute(text("SELECT COUNT(*) FROM demo")).scalar()
    assert count == 2


# --------------------------------------------------------------------------- #
# Loaders
# --------------------------------------------------------------------------- #


def test_load_raw_csvs_loads_all_tables(engine: Engine, tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    _write_raw_csvs(raw_dir)

    loaded = load_raw_csvs(engine, raw_dir)

    assert loaded == {
        "raw_rainfall_country_year": 2,
        "raw_crop_production_country_year": 1,
        "raw_food_affordability_country_year": 1,
    }
    assert set(loaded) == set(RAW_FILE_TABLES.values())


def test_load_raw_csvs_missing_file_raises(engine: Engine, tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        load_raw_csvs(engine, raw_dir)


def test_replace_load_preserves_table_ddl(engine: Engine, tmp_path: Path) -> None:
    """A replace load must clear rows, not drop the DDL-defined table."""

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE raw_rainfall_country_month ("
                "country_code TEXT NOT NULL,"
                "country_name TEXT NOT NULL,"
                "year INTEGER NOT NULL,"
                "month INTEGER NOT NULL,"
                "rainfall_mm REAL,"
                "PRIMARY KEY (country_code, year, month))"
            )
        )

    frame = pd.DataFrame(
        {
            "country_code": ["KEN", "KEN"],
            "country_name": ["Kenya", "Kenya"],
            "year": [2024, 2024],
            "month": [1, 2],
            "rainfall_mm": [80.0, 95.0],
        }
    )
    assert load_rainfall_country_month(engine, frame, replace=True) == 2
    # Loading again with replace must not duplicate rows or recreate the table.
    assert load_rainfall_country_month(engine, frame, replace=True) == 2

    primary_key = inspect(engine).get_pk_constraint("raw_rainfall_country_month")
    assert primary_key["constrained_columns"] == ["country_code", "year", "month"]
    with engine.connect() as connection:
        count = connection.execute(text("SELECT COUNT(*) FROM raw_rainfall_country_month")).scalar()
    assert count == 2


def test_append_load_accumulates_rows(engine: Engine) -> None:
    frame = pd.DataFrame(
        {
            "country_code": ["KEN"],
            "country_name": ["Kenya"],
            "year": [2024],
            "month": [1],
            "rainfall_mm": [80.0],
        }
    )
    load_rainfall_country_month(engine, frame, replace=True)
    load_rainfall_country_month(engine, frame.assign(month=[2]), replace=False)

    with engine.connect() as connection:
        count = connection.execute(text("SELECT COUNT(*) FROM raw_rainfall_country_month")).scalar()
    assert count == 2

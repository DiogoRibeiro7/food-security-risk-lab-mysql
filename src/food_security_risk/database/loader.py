"""CSV-to-MySQL loading utilities.

Loading is append-based on purpose. ``DataFrame.to_sql(if_exists="replace")``
drops the target table and recreates it from pandas-inferred types, which would
silently discard the primary keys, column types, defaults, and indexes defined
in ``sql/``. To keep the SQL DDL authoritative, a "replace" load here deletes
the existing rows and appends, leaving the table definition untouched.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

RAW_FILE_TABLES: dict[str, str] = {
    "rainfall_country_year.csv": "raw_rainfall_country_year",
    "crop_production_country_year.csv": "raw_crop_production_country_year",
    "food_affordability_country_year.csv": "raw_food_affordability_country_year",
}

_CHUNK_SIZE = 5_000


def _write_frame(engine: Engine, table_name: str, frame: pd.DataFrame, replace: bool) -> int:
    """Write a frame into a table, preserving any DDL-defined schema.

    When ``replace`` is true and the table already exists, its rows are deleted
    before appending so the table keeps the schema from ``sql/``. Tables that
    do not exist yet (e.g. pandas-managed marts) are created by the append.
    """

    if replace and inspect(engine).has_table(table_name):
        with engine.begin() as connection:
            connection.execute(text(f"DELETE FROM {table_name}"))
    frame.to_sql(table_name, engine, if_exists="append", index=False, chunksize=_CHUNK_SIZE)
    return len(frame)


def load_raw_csvs(engine: Engine, raw_dir: Path, replace: bool = True) -> dict[str, int]:
    """Load expected raw CSV files into MySQL staging tables.

    Parameters
    ----------
    engine:
        SQLAlchemy MySQL engine.
    raw_dir:
        Directory containing normalized CSV files.
    replace:
        If true, clear raw tables before loading. If false, append rows.

    Returns
    -------
    dict[str, int]
        Number of loaded rows per table.
    """

    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw directory does not exist: {raw_dir}")

    loaded: dict[str, int] = {}
    for filename, table_name in RAW_FILE_TABLES.items():
        path = raw_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Expected raw file not found: {path}")
        frame = pd.read_csv(path)
        loaded[table_name] = _write_frame(engine, table_name, frame, replace)
    return loaded


def read_mart(engine: Engine) -> pd.DataFrame:
    """Read the analytical country-year mart from MySQL."""

    return pd.read_sql("SELECT * FROM mart_country_year_food_security", engine)


def load_rainfall_country_month(engine: Engine, frame: pd.DataFrame, replace: bool = True) -> int:
    """Load monthly rainfall into ``raw_rainfall_country_month``."""

    return _write_frame(engine, "raw_rainfall_country_month", frame, replace)


def read_rainfall_country_month(engine: Engine) -> pd.DataFrame:
    """Read monthly rainfall staging from MySQL."""

    return pd.read_sql("SELECT * FROM raw_rainfall_country_month", engine)


def write_country_month_mart(engine: Engine, mart: pd.DataFrame, replace: bool = True) -> int:
    """Write the country-month mart to ``mart_country_month_food_security``."""

    return _write_frame(engine, "mart_country_month_food_security", mart, replace)


def load_fewsnet_context(engine: Engine, frame: pd.DataFrame, replace: bool = True) -> int:
    """Load FEWS NET / IPC context into ``fewsnet_context``."""

    return _write_frame(engine, "fewsnet_context", frame, replace)


def read_fewsnet_context(engine: Engine) -> pd.DataFrame:
    """Read the FEWS NET / IPC context table from MySQL."""

    return pd.read_sql("SELECT * FROM fewsnet_context", engine)


def load_country_dimension(engine: Engine, frame: pd.DataFrame, replace: bool = True) -> int:
    """Load the canonical country dimension into ``dim_country``."""

    return _write_frame(engine, "dim_country", frame, replace)


def load_source_mapping(engine: Engine, frame: pd.DataFrame, replace: bool = True) -> int:
    """Load a source country-name mapping into ``country_source_mapping``."""

    return _write_frame(engine, "country_source_mapping", frame, replace)


def write_scores(engine: Engine, scores: pd.DataFrame, replace: bool = True) -> None:
    """Write food-security risk scores back to MySQL."""

    _write_frame(engine, "food_security_risk_score", scores, replace)

"""CSV-to-MySQL loading utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd
from sqlalchemy.engine import Engine

RAW_FILE_TABLES: dict[str, str] = {
    "rainfall_country_year.csv": "raw_rainfall_country_year",
    "crop_production_country_year.csv": "raw_crop_production_country_year",
    "food_affordability_country_year.csv": "raw_food_affordability_country_year",
}


def load_raw_csvs(engine: Engine, raw_dir: Path, replace: bool = True) -> dict[str, int]:
    """Load expected raw CSV files into MySQL staging tables.

    Parameters
    ----------
    engine:
        SQLAlchemy MySQL engine.
    raw_dir:
        Directory containing normalized CSV files.
    replace:
        If true, replace raw tables before loading. If false, append rows.

    Returns
    -------
    dict[str, int]
        Number of loaded rows per table.
    """

    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw directory does not exist: {raw_dir}")

    loaded: dict[str, int] = {}
    if_exists: Literal["replace", "append"] = "replace" if replace else "append"
    for filename, table_name in RAW_FILE_TABLES.items():
        path = raw_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Expected raw file not found: {path}")
        frame = pd.read_csv(path)
        frame.to_sql(table_name, engine, if_exists=if_exists, index=False, chunksize=5_000)
        loaded[table_name] = len(frame)
    return loaded


def read_mart(engine: Engine) -> pd.DataFrame:
    """Read the analytical country-year mart from MySQL."""

    return pd.read_sql("SELECT * FROM mart_country_year_food_security", engine)


def load_rainfall_country_month(engine: Engine, frame: pd.DataFrame, replace: bool = True) -> int:
    """Load monthly rainfall into ``raw_rainfall_country_month``."""

    if_exists: Literal["replace", "append"] = "replace" if replace else "append"
    frame.to_sql("raw_rainfall_country_month", engine, if_exists=if_exists, index=False)
    return len(frame)


def read_rainfall_country_month(engine: Engine) -> pd.DataFrame:
    """Read monthly rainfall staging from MySQL."""

    return pd.read_sql("SELECT * FROM raw_rainfall_country_month", engine)


def write_country_month_mart(engine: Engine, mart: pd.DataFrame, replace: bool = True) -> int:
    """Write the country-month mart to ``mart_country_month_food_security``."""

    if_exists: Literal["replace", "append"] = "replace" if replace else "append"
    mart.to_sql("mart_country_month_food_security", engine, if_exists=if_exists, index=False)
    return len(mart)


def load_country_dimension(engine: Engine, frame: pd.DataFrame, replace: bool = True) -> int:
    """Load the canonical country dimension into ``dim_country``."""

    if_exists: Literal["replace", "append"] = "replace" if replace else "append"
    frame.to_sql("dim_country", engine, if_exists=if_exists, index=False)
    return len(frame)


def load_source_mapping(engine: Engine, frame: pd.DataFrame, replace: bool = True) -> int:
    """Load a source country-name mapping into ``country_source_mapping``."""

    if_exists: Literal["replace", "append"] = "replace" if replace else "append"
    frame.to_sql("country_source_mapping", engine, if_exists=if_exists, index=False)
    return len(frame)


def write_scores(engine: Engine, scores: pd.DataFrame, replace: bool = True) -> None:
    """Write food-security risk scores back to MySQL."""

    if_exists: Literal["replace", "append"] = "replace" if replace else "append"
    scores.to_sql(
        "food_security_risk_score",
        engine,
        if_exists=if_exists,
        index=False,
        chunksize=5_000,
    )

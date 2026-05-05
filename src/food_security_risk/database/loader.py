"""CSV-to-MySQL loading utilities."""

from __future__ import annotations

from pathlib import Path

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
    if_exists = "replace" if replace else "append"
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


def write_scores(engine: Engine, scores: pd.DataFrame, replace: bool = True) -> None:
    """Write food-security risk scores back to MySQL."""

    if_exists = "replace" if replace else "append"
    scores.to_sql("food_security_risk_score", engine, if_exists=if_exists, index=False, chunksize=5_000)

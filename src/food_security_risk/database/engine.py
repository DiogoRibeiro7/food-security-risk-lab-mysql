"""Database engine helpers."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from food_security_risk.database.config import MySQLConfig


def create_mysql_engine(config: MySQLConfig | None = None) -> Engine:
    """Create a SQLAlchemy engine for the configured MySQL database."""

    cfg = config or MySQLConfig.from_env()
    return create_engine(cfg.sqlalchemy_url, pool_pre_ping=True, future=True)

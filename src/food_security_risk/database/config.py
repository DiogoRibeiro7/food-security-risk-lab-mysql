"""MySQL configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class MySQLConfig:
    """Connection configuration for the local MySQL database."""

    host: str
    port: int
    database: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "MySQLConfig":
        """Build configuration from environment variables and optional `.env`."""

        load_dotenv()
        return cls(
            host=os.getenv("MYSQL_HOST", "127.0.0.1"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            database=os.getenv("MYSQL_DATABASE", "food_security_risk"),
            user=os.getenv("MYSQL_USER", "food_user"),
            password=os.getenv("MYSQL_PASSWORD", "food_password"),
        )

    @property
    def sqlalchemy_url(self) -> str:
        """Return a SQLAlchemy connection URL."""

        return (
            f"mysql+pymysql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}?charset=utf8mb4"
        )

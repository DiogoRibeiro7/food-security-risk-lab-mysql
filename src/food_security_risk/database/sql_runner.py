"""Utilities for executing MySQL SQL scripts."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _split_sql_statements(sql_text: str) -> list[str]:
    """Split a simple SQL script into executable statements.

    This splitter intentionally targets the SQL files in this repo. It is not a
    general SQL parser and should not be used for arbitrary stored procedures.
    """

    statements: list[str] = []
    buffer: list[str] = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buffer.append(line)
        if stripped.endswith(";"):
            statement = "\n".join(buffer).strip().rstrip(";").strip()
            if statement:
                statements.append(statement)
            buffer = []
    trailing = "\n".join(buffer).strip()
    if trailing:
        statements.append(trailing)
    return statements


def execute_sql_file(engine: Engine, sql_path: Path) -> None:
    """Execute all simple SQL statements in a file."""

    sql_text = sql_path.read_text(encoding="utf-8")
    statements = _split_sql_statements(sql_text)
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

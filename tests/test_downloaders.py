"""Tests for the raw download helper and the MySQL engine factory.

The FAOSTAT helper is tested with HTTP mocked out; the engine factory is tested
without connecting (SQLAlchemy builds the engine lazily).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from food_security_risk.database.config import MySQLConfig
from food_security_risk.database.engine import create_mysql_engine
from food_security_risk.ingestion import faostat


class _FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


def test_download_url_writes_content(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_get(url: str, timeout: int) -> _FakeResponse:
        captured["url"] = url
        captured["timeout"] = timeout
        return _FakeResponse(b"col\n1\n")

    monkeypatch.setattr(faostat.requests, "get", fake_get)

    out = tmp_path / "nested" / "production.csv"
    result = faostat.download_url("https://example.org/prod.csv", out, timeout=30)

    assert result == out
    assert out.read_bytes() == b"col\n1\n"
    assert captured == {"url": "https://example.org/prod.csv", "timeout": 30}


def test_download_url_rejects_non_http_scheme(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="http"):
        faostat.download_url("ftp://example.org/prod.csv", tmp_path / "out.csv")


def test_create_mysql_engine_builds_expected_url() -> None:
    config = MySQLConfig(
        host="db.example.org",
        port=3307,
        database="food_test",
        user="alice",
        password="secret",
    )
    engine = create_mysql_engine(config)
    try:
        url = str(engine.url)
        assert url.startswith("mysql+pymysql://alice:")
        assert "db.example.org:3307/food_test" in url
    finally:
        engine.dispose()

"""Tests for the World Bank downloader, with HTTP mocked out."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from food_security_risk.ingestion import world_bank
from food_security_risk.ingestion.normalize import parse_world_bank_response


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


def _record(iso3: str, year: int, value: float) -> dict[str, Any]:
    return {
        "indicator": {"id": "FP.CPI.TOTL"},
        "country": {"value": iso3},
        "countryiso3code": iso3,
        "date": str(year),
        "value": value,
    }


def test_download_combines_all_pages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pages = {
        1: [{"page": 1, "pages": 2}, [_record("KEN", 2020, 1.0)]],
        2: [{"page": 2, "pages": 2}, [_record("ETH", 2020, 2.0)]],
    }
    requested_pages: list[int] = []

    def fake_get(url: str, params: dict[str, Any], timeout: int) -> _FakeResponse:
        requested_pages.append(params["page"])
        return _FakeResponse(pages[params["page"]])

    monkeypatch.setattr(world_bank.requests, "get", fake_get)

    output = tmp_path / "wb.json"
    world_bank.download_world_bank_indicator("FP.CPI.TOTL", output)

    assert requested_pages == [1, 2]
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert len(payload[1]) == 2

    # The combined payload must remain parseable by the normalizer.
    frame = parse_world_bank_response(payload)
    assert sorted(frame["country_code"]) == ["ETH", "KEN"]


def test_download_rejects_error_shaped_response(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    error_payload = [{"message": [{"id": "120", "value": "Invalid indicator"}]}]
    monkeypatch.setattr(
        world_bank.requests, "get", lambda url, params, timeout: _FakeResponse(error_payload)
    )

    output = tmp_path / "wb.json"
    with pytest.raises(ValueError, match="Unexpected World Bank response"):
        world_bank.download_world_bank_indicator("NOPE", output)
    assert not output.exists()  # error bodies are never written to disk


def test_download_rejects_blank_indicator(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="indicator must not be empty"):
        world_bank.download_world_bank_indicator("  ", tmp_path / "wb.json")

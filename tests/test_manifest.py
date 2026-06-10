from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from food_security_risk.ingestion.manifest import (
    build_entry,
    load_manifest,
    sha256_file,
    update_manifest,
)


def _write_csv(path: Path, rows: int) -> None:
    pd.DataFrame({"country_code": ["KEN"] * rows, "year": range(rows)}).to_csv(path, index=False)


def test_build_entry_records_rows_hash_and_relative_path(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    csv_path = raw_dir / "rainfall_country_year.csv"
    _write_csv(csv_path, rows=3)

    entry = build_entry(
        dataset="rainfall_country_year",
        source="CHIRPS",
        version="summary",
        downloaded_at="2026-06-08T00:00:00+00:00",
        file_path=csv_path,
        manifest_dir=raw_dir,
    )
    assert entry.row_count == 3
    assert entry.file == "rainfall_country_year.csv"  # relative to manifest dir
    assert entry.file_sha256 == sha256_file(csv_path)


def test_update_manifest_inserts_and_replaces(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    manifest_path = raw_dir / "manifest.json"
    csv_path = raw_dir / "crop_production_country_year.csv"

    _write_csv(csv_path, rows=2)
    entry_v1 = build_entry(
        dataset="crop_production_country_year",
        source="FAOSTAT",
        version="bulk",
        downloaded_at="2026-06-08T00:00:00+00:00",
        file_path=csv_path,
        manifest_dir=raw_dir,
    )
    update_manifest(manifest_path, entry_v1)

    # Re-ingest with more rows: same dataset key must be replaced, not duplicated.
    _write_csv(csv_path, rows=5)
    entry_v2 = build_entry(
        dataset="crop_production_country_year",
        source="FAOSTAT",
        version="bulk",
        downloaded_at="2026-06-09T00:00:00+00:00",
        file_path=csv_path,
        manifest_dir=raw_dir,
    )
    manifest = update_manifest(manifest_path, entry_v2)

    assert list(manifest.keys()) == ["crop_production_country_year"]
    assert manifest["crop_production_country_year"]["row_count"] == 5

    on_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert on_disk["crop_production_country_year"]["downloaded_at"] == "2026-06-09T00:00:00+00:00"


def test_load_manifest_absent_returns_empty(tmp_path: Path) -> None:
    assert load_manifest(tmp_path / "missing.json") == {}

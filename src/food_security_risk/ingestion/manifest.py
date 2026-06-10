"""Provenance manifest for ingested raw datasets.

Every normalized file written by the ingestion layer gets a manifest entry under
``data/raw/manifest.json``. The manifest is the audit trail that lets an analyst
answer "where did this number come from?": dataset name, source, version,
download date, content hash, and row count.

The manifest is a JSON object keyed by dataset name, so re-ingesting a dataset
replaces its entry rather than appending a duplicate.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class ManifestEntry:
    """A single dataset's provenance record."""

    dataset: str
    source: str
    version: str
    downloaded_at: str
    file: str
    file_sha256: str
    row_count: int
    source_url: str | None = None


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 digest of a file's bytes."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_entry(
    *,
    dataset: str,
    source: str,
    version: str,
    downloaded_at: str,
    file_path: Path,
    manifest_dir: Path,
    source_url: str | None = None,
) -> ManifestEntry:
    """Build a manifest entry for an already-written normalized file.

    The ``file`` field is stored relative to ``manifest_dir`` when possible so the
    manifest stays portable across machines; otherwise the absolute path is kept.
    The row count is read from the CSV header-aware loader.
    """

    if not file_path.exists():
        raise FileNotFoundError(f"Cannot build manifest entry for missing file: {file_path}")

    try:
        relative = file_path.resolve().relative_to(manifest_dir.resolve())
        file_repr = relative.as_posix()
    except ValueError:
        file_repr = file_path.resolve().as_posix()

    row_count = int(len(pd.read_csv(file_path)))
    return ManifestEntry(
        dataset=dataset,
        source=source,
        version=version,
        downloaded_at=downloaded_at,
        file=file_repr,
        file_sha256=sha256_file(file_path),
        row_count=row_count,
        source_url=source_url,
    )


def load_manifest(manifest_path: Path) -> dict[str, dict[str, object]]:
    """Load the manifest mapping, returning an empty dict when absent."""

    if not manifest_path.exists():
        return {}
    with manifest_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Manifest at {manifest_path} is not a JSON object.")
    return data


def update_manifest(manifest_path: Path, entry: ManifestEntry) -> dict[str, dict[str, object]]:
    """Insert or replace an entry and persist the manifest.

    Returns the full manifest mapping after the update.
    """

    manifest = load_manifest(manifest_path)
    manifest[entry.dataset] = asdict(entry)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return manifest

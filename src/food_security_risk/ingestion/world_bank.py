"""World Bank data downloader.

Downloads every page of an indicator query and writes a single combined
``[metadata, records]`` payload, so the normalizer never sees a silently
truncated response. Retries and manifest logging remain future work.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests

_BASE_URL = "https://api.worldbank.org/v2/country/all/indicator"


def download_world_bank_indicator(
    indicator: str,
    output_path: Path,
    timeout: int = 60,
    per_page: int = 20_000,
) -> Path:
    """Download all pages of a World Bank indicator as one JSON payload.

    The API caps records per request, and on errors (e.g. an unknown
    indicator) it returns a one-element ``[{"message": ...}]`` body with HTTP
    200. This follows the ``pages`` field in the response metadata until every
    record is fetched, and raises ``ValueError`` on error-shaped responses
    instead of writing them to disk.

    Parameters
    ----------
    indicator:
        World Bank indicator code.
    output_path:
        Destination file; receives a ``[metadata, records]`` JSON array
        compatible with :func:`parse_world_bank_response`.
    timeout:
        HTTP timeout in seconds, per request.
    per_page:
        Records requested per page.

    Returns
    -------
    pathlib.Path
        Written output path.
    """

    if not indicator.strip():
        raise ValueError("indicator must not be empty.")

    records: list[Any] = []
    metadata: dict[str, Any] = {}
    page = 1
    while True:
        params: dict[str, str | int] = {"format": "json", "per_page": per_page, "page": page}
        response = requests.get(f"{_BASE_URL}/{indicator}", params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or len(payload) < 2:
            message = payload[0].get("message") if isinstance(payload, list) and payload else None
            raise ValueError(
                f"Unexpected World Bank response for indicator {indicator!r}; "
                f"message={message!r}"
            )
        metadata = payload[0]
        records.extend(payload[1] or [])
        if page >= int(metadata.get("pages", 1)):
            break
        page += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps([metadata, records]), encoding="utf-8")
    return output_path

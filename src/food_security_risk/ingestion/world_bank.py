"""World Bank data downloader hooks.

The full production downloader should add pagination, retries, manifest logging,
and indicator-specific normalization. This module provides a small, typed hook
that future work can extend.
"""

from __future__ import annotations

from pathlib import Path

import requests


def download_world_bank_indicator(indicator: str, output_path: Path, timeout: int = 60) -> Path:
    """Download a World Bank indicator response as JSON.

    Parameters
    ----------
    indicator:
        World Bank indicator code.
    output_path:
        Destination file.
    timeout:
        HTTP timeout in seconds.

    Returns
    -------
    pathlib.Path
        Written output path.
    """

    if not indicator.strip():
        raise ValueError("indicator must not be empty.")
    url = f"https://api.worldbank.org/v2/country/all/indicator/{indicator}?format=json&per_page=20000"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.content)
    return output_path

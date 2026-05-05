"""FAOSTAT downloader placeholder.

FAOSTAT APIs and bulk downloads vary by domain. This module deliberately keeps a
small extension point instead of hiding data-source assumptions inside the CLI.
"""

from __future__ import annotations

from pathlib import Path

import requests


def download_url(url: str, output_path: Path, timeout: int = 120) -> Path:
    """Download a configured FAOSTAT or bulk file URL.

    Parameters
    ----------
    url:
        Source URL.
    output_path:
        Destination file path.
    timeout:
        HTTP timeout in seconds.

    Returns
    -------
    pathlib.Path
        Written output path.
    """

    if not url.startswith(("http://", "https://")):
        raise ValueError("url must start with http:// or https://")
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.content)
    return output_path

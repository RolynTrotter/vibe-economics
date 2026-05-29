"""Plain HTTP download helper for the acquire stage.

Downloads a URL to a destination path, creating parent dirs. Network access in
this environment requires the sandbox to be off for the running command.
"""
from __future__ import annotations

from pathlib import Path

import httpx


def download(url: str, dest: Path, *, timeout: float = 60.0) -> Path:
    """Download `url` to `dest`. Returns the path written."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # follow_redirects: many stats sites 301/302 to a CDN.
    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        resp = client.get(url, headers={"User-Agent": "vibe-economics/0.1"})
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    return dest

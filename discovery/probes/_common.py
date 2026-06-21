from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = ROOT / "discovery" / "samples"
USER_AGENT = "AI-Soccer-Predictions discovery probe (+local research; contact: repo owner)"


def save_sample(source_id: str, name: str, content_bytes: bytes) -> dict[str, str]:
    """Save a raw discovery sample under the gitignored samples directory."""
    if not isinstance(content_bytes, bytes):
        raise TypeError("content_bytes must be bytes")

    target_dir = SAMPLES_DIR / source_id
    target_dir.mkdir(parents=True, exist_ok=True)

    target = target_dir / name
    target.write_bytes(content_bytes)

    rel_path = target.relative_to(ROOT).as_posix()
    return {"path": rel_path, "sha256": sha256(content_bytes).hexdigest()}


def head_rows(df: Any, n: int = 20) -> Any:
    return df.head(n).copy()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def http_get(url: str, **kw: Any) -> Any:
    import httpx

    headers = dict(kw.pop("headers", {}) or {})
    headers.setdefault("User-Agent", USER_AGENT)
    timeout = kw.pop("timeout", 30.0)

    response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True, **kw)
    if response.status_code != 200:
        preview = response.text[:500].replace("\n", " ")
        raise RuntimeError(
            f"GET {url} returned HTTP {response.status_code}: {preview}"
        )
    return response

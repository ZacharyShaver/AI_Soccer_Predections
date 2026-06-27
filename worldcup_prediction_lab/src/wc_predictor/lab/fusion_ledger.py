"""Shared, conflict-free experiment ledger for the tuning/fusion session.

Every experiment writes ONE json file under ``runs/fusion/`` so two agents
working in parallel git worktrees (which junction the same ``runs/`` tree) never
write the same file. The file name is deterministic in the experiment's identity
(``<agent>__<exp_id>__<created_utc>.json``), so re-recording the same experiment
overwrites in place rather than accumulating duplicates.

Schema (one object per file)::

    {
      "exp_id": "tune-k-sweep-001",
      "agent": "claude" | "codex",
      "task": "tune" | "fuse" | "market_base",
      "created_utc": "2026-06-27T18:00:00Z",
      "config": { ...the exact knobs / recipe... },
      "samples": {
        "hist_15k":  {"n": 15877, "rps": 0.1743, "log_loss": 0.881, "brier": 0.522},
        "wc60":      {"n": 60,    "rps": 0.1719, "log_loss": 0.892, "brier": 0.547},
        "market964": {"n": 964,   "rps": 0.1560, "log_loss": 0.79,  "brier": 0.49}
      },
      "vs_market_paired": {"mean_diff": 0.0064, "ci95": [0.003, 0.010], "excludes_0": true},
      "notes": "what changed, what it means, overfit flag",
      "promote": false
    }

Only ``record`` / ``load_all`` are part of the contract; everything else is a
helper. ``record`` tolerates partial/missing samples (an experiment that only
touched the market join can omit ``hist_15k``/``wc60``).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from wc_predictor.config import settings

FUSION_DIR = settings.RUNS_DIR / "fusion"

# Sample keys the dashboard understands. record() does not require any of them;
# a result may carry a subset (or extra keys, which are passed through).
SAMPLE_KEYS = ("hist_15k", "wc60", "market964")


def _slug(value: str) -> str:
    """Filesystem-safe token: keep alnum/._-, collapse everything else to '-'."""

    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value).strip())
    return cleaned.strip("-") or "x"


def filename_for(result: dict[str, Any]) -> str:
    """Deterministic file name for a result, derived from its identity."""

    agent = _slug(result.get("agent", "unknown"))
    exp_id = _slug(result.get("exp_id", "unknown"))
    created = _slug(result.get("created_utc", "undated"))
    return f"{agent}__{exp_id}__{created}.json"


def record(result: dict[str, Any], *, fusion_dir: Path | None = None) -> Path:
    """Write one experiment result to its own json file; return the path.

    The write is deterministic in ``(agent, exp_id, created_utc)`` so the same
    experiment recorded twice overwrites rather than duplicates. Missing samples
    are fine — the object is stored as given.
    """

    directory = Path(fusion_dir) if fusion_dir is not None else FUSION_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename_for(result)
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return path


def load_all(*, fusion_dir: Path | None = None) -> list[dict[str, Any]]:
    """Load every experiment json under the ledger directory.

    Skips the ``.gitkeep`` placeholder and any file that fails to parse (a
    half-written file from a concurrent writer is simply ignored this pass).
    Sorted by ``created_utc`` then ``exp_id`` for stable dashboard ordering.
    """

    directory = Path(fusion_dir) if fusion_dir is not None else FUSION_DIR
    if not directory.exists():
        return []
    results: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(payload, dict):
            results.append(payload)
    results.sort(key=lambda r: (str(r.get("created_utc", "")), str(r.get("exp_id", ""))))
    return results

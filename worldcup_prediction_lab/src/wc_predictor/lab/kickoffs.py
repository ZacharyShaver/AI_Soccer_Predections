"""Manual kickoff-time table for the pre-kickoff (T-75) lineup-check pass.

Silver fixtures carry only a match DATE - no time of day - so pre-kickoff
scheduling needs this manually maintained CSV (same convention as
``config/knockout_overrides.csv``; only a handful of tournament matches remain).
``kickoff_local`` is machine-local time (America/New_York on the scheduling
machine): the Windows one-shot tasks that consume it schedule in local time.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from wc_predictor.config import settings

KICKOFFS_FILE = "kickoff_times.csv"


def load_kickoffs(path: str | Path | None = None) -> dict[str, pd.Timestamp]:
    """fixture_id -> naive local-time kickoff. Missing file -> {}; bad row -> ValueError."""

    p = Path(path) if path is not None else settings.CONFIG_DIR / KICKOFFS_FILE
    if not p.exists():
        return {}
    out: dict[str, pd.Timestamp] = {}
    with p.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            fid = str(row["fixture_id"]).strip()
            ts = pd.to_datetime(row["kickoff_local"], errors="coerce")
            if pd.isna(ts):
                raise ValueError(
                    f"kickoff_times.csv: unparseable kickoff_local for fixture "
                    f"{fid!r}: {row['kickoff_local']!r}"
                )
            out[fid] = ts
    return out


def kickoffs_for_date(date: str, *, path: str | Path | None = None) -> list[tuple[str, pd.Timestamp]]:
    """Kickoffs on `date` (YYYY-MM-DD), sorted by time then fixture_id."""

    day = pd.Timestamp(date).date()
    rows = [(fid, ts) for fid, ts in load_kickoffs(path).items() if ts.date() == day]
    return sorted(rows, key=lambda item: (item[1], item[0]))

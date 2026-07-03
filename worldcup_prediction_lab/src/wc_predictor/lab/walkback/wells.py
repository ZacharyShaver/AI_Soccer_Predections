"""Frozen pre-match news wells, built from the GDELT DOC 2.0 API.

A well is one JSON file per match holding only documents published strictly
before the match date. Wells are the durable dataset of this experiment:
built once, linted once, then reused to evaluate any model.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_MIN_INTERVAL = 5.0
GDELT_RETRY_WAIT = 5.0

_last_call: float | None = None


def _to_date(seendate: str) -> str:
    # GDELT format: 20250308T120000Z
    return f"{seendate[0:4]}-{seendate[4:6]}-{seendate[6:8]}"


def fetch_articles(home: str, away: str, match_date: str, *, days_before: int = 7,
                   max_records: int = 30, session=None) -> list[dict]:
    global _last_call

    session = session or requests.Session()
    now = time.monotonic()
    if _last_call is not None:
        elapsed = now - _last_call
        if elapsed < GDELT_MIN_INTERVAL:
            time.sleep(GDELT_MIN_INTERVAL - elapsed)
    end = pd.Timestamp(match_date) - timedelta(days=1)
    start = pd.Timestamp(match_date) - timedelta(days=days_before)
    params = {
        "query": f'"{home} vs {away}" sourcelang:english',
        "mode": "artlist",
        "format": "json",
        "maxrecords": str(max_records),
        "startdatetime": start.strftime("%Y%m%d") + "000000",
        "enddatetime": end.strftime("%Y%m%d") + "235959",
    }
    resp = session.get(GDELT_DOC_API, params=params, timeout=30)
    _last_call = time.monotonic()
    try:
        payload = resp.json()
    except ValueError:
        time.sleep(GDELT_RETRY_WAIT)
        resp = session.get(GDELT_DOC_API, params=params, timeout=30)
        _last_call = time.monotonic()
        try:
            payload = resp.json()
        except ValueError:
            print(f"GDELT returned non-JSON response: {getattr(resp, 'text', '')[:80]}")
            return []
    articles = payload.get("articles", []) or []
    seen: set[str] = set()
    docs: list[dict] = []
    for a in articles:
        url = a.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        docs.append(
            {"url": url, "title": a.get("title", ""),
             "seendate": _to_date(a.get("seendate", "00000000")),
             "source": a.get("domain", "")}
        )
    return docs


def fetch_body(url: str, *, session=None) -> str | None:
    try:
        import trafilatura

        session = session or requests.Session()
        resp = session.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return None
        return trafilatura.extract(resp.text) or None
    except Exception:
        return None


def build_well(row: pd.Series, *, session=None, fetch_bodies: int = 3) -> dict:
    match_date = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
    docs = fetch_articles(str(row["home_team"]), str(row["away_team"]), match_date, session=session)
    for i, doc in enumerate(docs):
        doc["body"] = fetch_body(doc["url"], session=session) if i < fetch_bodies else None
    return {
        "match_id": str(row["match_id"]),
        "home_team": str(row["home_team"]),
        "away_team": str(row["away_team"]),
        "match_date": match_date,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "docs": docs,
    }


def well_path(root: Path, match_id: str) -> Path:
    return Path(root) / f"{match_id}.json"


def save_well(well: dict, root: Path) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = well_path(root, well["match_id"])
    if path.exists():
        raise FileExistsError(f"well already frozen: {path}")
    path.write_text(json.dumps(well, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load_well(match_id: str, root: Path) -> dict | None:
    path = well_path(Path(root), match_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

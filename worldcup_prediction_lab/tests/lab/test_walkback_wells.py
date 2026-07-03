# tests/lab/test_walkback_wells.py
import json
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from wc_predictor.lab.walkback.wells import (
    build_well,
    fetch_articles,
    load_well,
    save_well,
    well_path,
)
from wc_predictor.lab.walkback import wells


@pytest.fixture(autouse=True)
def _reset_gdelt_pacing(monkeypatch):
    monkeypatch.setattr(wells, "_last_call", None)


def _gdelt_response():
    return {
        "articles": [
            {
                "url": "https://ex.com/preview",
                "title": "Brazil vs Norway preview",
                "seendate": "20250308T120000Z",
                "domain": "ex.com",
            },
            {
                "url": "https://ex.com/preview",  # duplicate URL -> deduped
                "title": "Brazil vs Norway preview",
                "seendate": "20250308T120000Z",
                "domain": "ex.com",
            },
        ]
    }


def _session_returning(payload):
    session = MagicMock()
    resp = MagicMock()
    resp.json.return_value = payload
    resp.status_code = 200
    session.get.return_value = resp
    return session


def test_fetch_articles_windows_query_and_dedupes():
    session = _session_returning(_gdelt_response())
    docs = fetch_articles("Brazil", "Norway", "2025-03-10", days_before=7, session=session)
    assert len(docs) == 1
    assert docs[0]["seendate"] == "2025-03-08"
    params = session.get.call_args.kwargs["params"]
    assert '"Brazil vs Norway"' in params["query"]
    assert params["startdatetime"] == "20250303000000"
    assert params["enddatetime"] == "20250309235959"  # strictly before match day


def test_fetch_articles_retries_once_after_non_json(monkeypatch):
    first = MagicMock()
    first.json.side_effect = ValueError("not json")
    first.text = "Please limit requests to one every 5 seconds"
    second = MagicMock()
    second.json.return_value = _gdelt_response()
    session = MagicMock()
    session.get.side_effect = [first, second]
    monkeypatch.setattr(wells.time, "sleep", MagicMock())

    docs = fetch_articles("Brazil", "Norway", "2025-03-10", session=session)

    assert len(docs) == 1
    assert session.get.call_count == 2


def test_fetch_articles_returns_empty_when_retry_is_non_json(monkeypatch):
    first = MagicMock()
    first.json.side_effect = ValueError("not json")
    first.text = "Please limit requests to one every 5 seconds"
    second = MagicMock()
    second.json.side_effect = ValueError("still not json")
    second.text = "Please limit requests to one every 5 seconds"
    session = MagicMock()
    session.get.side_effect = [first, second]
    monkeypatch.setattr(wells.time, "sleep", MagicMock())

    assert fetch_articles("Brazil", "Norway", "2025-03-10", session=session) == []
    assert session.get.call_count == 2


def test_build_well_shape():
    session = _session_returning(_gdelt_response())
    row = pd.Series(
        {"match_id": "m2", "home_team": "Brazil", "away_team": "Norway",
         "date": pd.Timestamp("2025-03-10")}
    )
    well = build_well(row, session=session, fetch_bodies=0)
    assert well["match_id"] == "m2"
    assert well["match_date"] == "2025-03-10"
    assert well["docs"][0]["title"] == "Brazil vs Norway preview"
    assert well["docs"][0]["body"] is None


def test_save_well_refuses_overwrite(tmp_path: Path):
    well = {"match_id": "m2", "home_team": "a", "away_team": "b",
            "match_date": "2025-03-10", "built_at": "x", "docs": []}
    save_well(well, tmp_path)
    assert load_well("m2", tmp_path)["match_id"] == "m2"
    with pytest.raises(FileExistsError):
        save_well(well, tmp_path)
    assert load_well("missing", tmp_path) is None

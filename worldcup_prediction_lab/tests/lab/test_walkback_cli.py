import json
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from wc_predictor.lab.walkback.cli import _existing_keys, _recall_exclusions, run_batch
from wc_predictor.lab.walkback.wells import save_well


def _universe():
    return pd.DataFrame({
        "match_id": ["m1", "m2"],
        "home_team": ["Brazil", "Spain"], "away_team": ["Norway", "Austria"],
        "date": pd.to_datetime(["2025-03-10", "2025-03-11"]),
        "city": ["Rio", "Sevilla"], "tournament": ["Friendly"] * 2,
        "elo_prob_home": [0.5, 0.6], "elo_prob_draw": [0.3, 0.25], "elo_prob_away": [0.2, 0.15],
        "elo_home_rating": [2100.0, 2000.0], "elo_away_rating": [1950.0, 1800.0],
        "elo_home_advantage": [50.0, 50.0],
        "home_score": [1, 3], "away_score": [1, 0], "outcome": ["draw", "home"],
    })


def _mk_well(match_id, home, away, root, n_docs=3):
    docs = [{"url": f"u{i}", "title": f"{home} team news {i}", "seendate": "2025-03-08",
             "source": "ex.com", "body": None} for i in range(n_docs)]
    save_well({"match_id": match_id, "home_team": home, "away_team": away,
               "match_date": "2025-03-10", "built_at": "x", "docs": docs}, root)


def test_run_batch_resumes_and_gates(tmp_path: Path):
    wells_root = tmp_path / "wells"
    _mk_well("m1", "Brazil", "Norway", wells_root, n_docs=3)
    _mk_well("m2", "Spain", "Austria", wells_root, n_docs=1)  # below min_docs gate
    out = tmp_path / "preds.jsonl"
    # pre-existing prediction for m1 -> must be skipped
    out.write_text(json.dumps({"match_id": "m1", "condition": "news",
                               "model": "test-model"}) + "\n", encoding="utf-8")

    client = MagicMock()
    client.model = "test-model"
    client.chat_json.return_value = {"p_home": 0.4, "p_draw": 0.3, "p_away": 0.3}

    stats = run_batch(_universe(), wells_root, client, "news", out)
    assert stats == {"done": 0, "skipped_existing": 1, "skipped_no_well": 1, "errors": 0}

    stats2 = run_batch(_universe(), wells_root, client, "stats", out)
    assert stats2["done"] == 2  # stats condition needs no well
    rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 3


def test_run_batch_survives_client_errors(tmp_path: Path):
    out = tmp_path / "preds.jsonl"
    client = MagicMock()
    client.model = "test-model"
    client.chat_json.side_effect = ValueError("no valid JSON")
    stats = run_batch(_universe(), tmp_path / "none", client, "stats", out)
    assert stats["errors"] == 2 and stats["done"] == 0


def test_run_batch_survives_corrupt_well(tmp_path: Path):
    wells_root = tmp_path / "wells"
    wells_root.mkdir()
    (wells_root / "m1.json").write_text("{ this is not json", encoding="utf-8")
    _mk_well("m2", "Spain", "Austria", wells_root, n_docs=3)
    out = tmp_path / "preds.jsonl"

    client = MagicMock()
    client.model = "test-model"
    client.chat_json.return_value = {"p_home": 0.4, "p_draw": 0.3, "p_away": 0.3}

    stats = run_batch(_universe(), wells_root, client, "news", out)
    assert stats == {"done": 1, "skipped_existing": 0, "skipped_no_well": 0, "errors": 1}


def test_existing_keys_skips_corrupt_lines(tmp_path: Path):
    out = tmp_path / "preds.jsonl"
    out.write_text(
        json.dumps({"match_id": "m1", "model": "x", "condition": "stats"}) + "\n"
        + "{ corrupt line\n"
        + json.dumps({"match_id": "m2", "model": "x", "condition": "stats"}) + "\n",
        encoding="utf-8",
    )
    assert _existing_keys(out) == {("m1", "x", "stats"), ("m2", "x", "stats")}


def test_recall_exclusions_missing_file_returns_none(tmp_path: Path):
    assert _recall_exclusions(tmp_path / "absent.jsonl") is None


def test_recall_exclusions_parses_and_skips_corrupt(tmp_path: Path):
    p = tmp_path / "recall_x.jsonl"
    p.write_text(
        json.dumps({"match_id": "m1", "contaminated": True}) + "\n"
        + "{ corrupt\n"
        + json.dumps({"match_id": "m2", "contaminated": False}) + "\n",
        encoding="utf-8",
    )
    assert _recall_exclusions(p) == {"m1"}

"""Tests for the shared, conflict-free experiment ledger."""

from __future__ import annotations

import json

from wc_predictor.lab import fusion_ledger


def _result(**overrides):
    base = {
        "exp_id": "tune-k-sweep-001",
        "agent": "claude",
        "task": "tune",
        "created_utc": "2026-06-27T18:00:00Z",
        "config": {"k_factor": 30.0},
        "samples": {
            "hist_15k": {"n": 15877, "rps": 0.1743, "log_loss": 0.881, "brier": 0.522},
            "wc60": {"n": 60, "rps": 0.1719, "log_loss": 0.892, "brier": 0.547},
            "market964": {"n": 964, "rps": 0.1560, "log_loss": 0.79, "brier": 0.49},
        },
        "notes": "joint K x draw grid",
        "promote": False,
    }
    base.update(overrides)
    return base


def test_round_trip_write_read(tmp_path):
    result = _result()
    path = fusion_ledger.record(result, fusion_dir=tmp_path)
    assert path.exists()

    loaded = fusion_ledger.load_all(fusion_dir=tmp_path)
    assert len(loaded) == 1
    assert loaded[0]["exp_id"] == "tune-k-sweep-001"
    assert loaded[0]["samples"]["hist_15k"]["rps"] == 0.1743
    # Stored as valid json on disk.
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk == loaded[0]


def test_unique_filenames_per_experiment(tmp_path):
    fusion_ledger.record(_result(exp_id="a"), fusion_dir=tmp_path)
    fusion_ledger.record(_result(exp_id="b"), fusion_dir=tmp_path)
    fusion_ledger.record(_result(agent="codex", exp_id="a"), fusion_dir=tmp_path)

    files = sorted(p.name for p in tmp_path.glob("*.json"))
    assert len(files) == 3
    assert len(set(files)) == 3


def test_same_experiment_overwrites_in_place(tmp_path):
    fusion_ledger.record(_result(notes="first"), fusion_dir=tmp_path)
    fusion_ledger.record(_result(notes="second"), fusion_dir=tmp_path)

    loaded = fusion_ledger.load_all(fusion_dir=tmp_path)
    assert len(loaded) == 1
    assert loaded[0]["notes"] == "second"


def test_tolerates_partial_and_missing_samples(tmp_path):
    market_only = _result(
        exp_id="m3-1-temp",
        task="market_base",
        samples={"market964": {"n": 964, "rps": 0.1500}},
    )
    fusion_ledger.record(market_only, fusion_dir=tmp_path)

    no_samples = {
        "exp_id": "skeleton",
        "agent": "claude",
        "task": "fuse",
        "created_utc": "2026-06-27T19:00:00Z",
    }
    fusion_ledger.record(no_samples, fusion_dir=tmp_path)

    loaded = fusion_ledger.load_all(fusion_dir=tmp_path)
    assert len(loaded) == 2
    by_id = {r["exp_id"]: r for r in loaded}
    assert set(by_id["m3-1-temp"]["samples"]) == {"market964"}
    assert "samples" not in by_id["skeleton"]


def test_load_all_skips_unparseable_and_gitkeep(tmp_path):
    fusion_ledger.record(_result(), fusion_dir=tmp_path)
    (tmp_path / ".gitkeep").write_text("", encoding="utf-8")
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")

    loaded = fusion_ledger.load_all(fusion_dir=tmp_path)
    assert len(loaded) == 1


def test_load_all_missing_dir_returns_empty(tmp_path):
    assert fusion_ledger.load_all(fusion_dir=tmp_path / "nope") == []


def test_load_all_sorted_by_created_then_exp(tmp_path):
    fusion_ledger.record(
        _result(exp_id="z", created_utc="2026-06-27T20:00:00Z"), fusion_dir=tmp_path
    )
    fusion_ledger.record(
        _result(exp_id="a", created_utc="2026-06-27T18:00:00Z"), fusion_dir=tmp_path
    )
    loaded = fusion_ledger.load_all(fusion_dir=tmp_path)
    assert [r["exp_id"] for r in loaded] == ["a", "z"]

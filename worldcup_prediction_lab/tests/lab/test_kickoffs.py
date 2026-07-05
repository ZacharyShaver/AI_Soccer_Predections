"""Tests for the manual kickoff-times config loader."""

from pathlib import Path

import pandas as pd
import pytest

from wc_predictor.lab.kickoffs import kickoffs_for_date, load_kickoffs


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "kickoff_times.csv"
    p.write_text(text, encoding="utf-8")
    return p


def test_load_kickoffs_parses_rows(tmp_path):
    p = _write(
        tmp_path,
        "fixture_id,kickoff_local,source,note\n"
        "fd67eda02d56,2026-07-06 15:00,fifa_schedule,Portugal v Spain\n"
        "8fcb454f2317,2026-07-06 18:00,fifa_schedule,USA v Belgium\n",
    )
    ks = load_kickoffs(p)
    assert ks["fd67eda02d56"] == pd.Timestamp("2026-07-06 15:00")
    assert len(ks) == 2


def test_load_kickoffs_missing_file_returns_empty(tmp_path):
    assert load_kickoffs(tmp_path / "nope.csv") == {}


def test_load_kickoffs_bad_time_raises_with_fixture_id(tmp_path):
    p = _write(
        tmp_path,
        "fixture_id,kickoff_local,source,note\n"
        "abc123,not-a-time,x,\n",
    )
    with pytest.raises(ValueError, match="abc123"):
        load_kickoffs(p)


def test_kickoffs_for_date_filters_and_sorts(tmp_path):
    p = _write(
        tmp_path,
        "fixture_id,kickoff_local,source,note\n"
        "late,2026-07-06 18:00,x,\n"
        "early,2026-07-06 15:00,x,\n"
        "other_day,2026-07-07 15:00,x,\n",
    )
    rows = kickoffs_for_date("2026-07-06", path=p)
    assert [fid for fid, _ in rows] == ["early", "late"]

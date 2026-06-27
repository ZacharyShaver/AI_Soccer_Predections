"""Tests for dashboard helpers."""

from __future__ import annotations

from wc_predictor.lab.dashboard import _select_upcoming_match_ids


def _dates(mapping):
    return lambda mid: mapping.get(mid, "")


def test_upcoming_excludes_past_but_keeps_today_and_future():
    # m_past (played, result lagging) must NOT show; today's and future games do.
    dates = _dates(
        {
            "m_past": "2026-06-26",
            "m_today": "2026-06-27",
            "m_future": "2026-06-29",
            "m_nodate": "",
        }
    )
    selected = _select_upcoming_match_ids(
        ["m_past", "m_today", "m_future", "m_nodate"],
        fixture_date=dates,
        today="2026-06-27",
    )
    assert selected == ["m_today", "m_future"]


def test_upcoming_sorted_soonest_first_and_limited():
    dates = _dates({f"m{i}": f"2026-07-{i:02d}" for i in range(1, 20)})
    selected = _select_upcoming_match_ids(
        [f"m{i}" for i in range(19, 0, -1)],
        fixture_date=dates,
        today="2026-06-27",
        limit=5,
    )
    assert selected == ["m1", "m2", "m3", "m4", "m5"]


def test_upcoming_empty_when_all_past():
    dates = _dates({"a": "2026-06-20", "b": "2026-06-25"})
    assert _select_upcoming_match_ids(
        ["a", "b"], fixture_date=dates, today="2026-06-27"
    ) == []

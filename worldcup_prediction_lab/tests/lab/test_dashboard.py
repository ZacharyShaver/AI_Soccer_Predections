"""Tests for dashboard helpers."""

from __future__ import annotations

import pandas as pd

from wc_predictor.lab import dashboard
from wc_predictor.lab.betting import BetSignal
from wc_predictor.lab.leaderboard import VariantStanding
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


def test_betting_date_cells_have_numeric_sort_keys(monkeypatch):
    def fake_run_betting(**_kwargs):
        return [
            BetSignal(
                "fixture-a",
                "2026-07-03",
                "Venue",
                "Australia",
                "Egypt",
                "home",
                "Australia",
                0.40,
                0.28,
                0.28,
                0.12,
                0.389,
                0.0,
                0.0,
                None,
                "WATCH",
            ),
            BetSignal(
                "fixture-b",
                "2026-06-29",
                "Venue",
                "Brazil",
                "Japan",
                "away",
                "Japan",
                0.24,
                0.18,
                0.18,
                0.06,
                0.308,
                0.0,
                0.0,
                None,
                "WATCH",
            ),
        ]

    monkeypatch.setattr("wc_predictor.lab.betting.run_betting", fake_run_betting)

    html = dashboard._betting_section()

    assert '<td class="dt" data-sort="20260703">2026-07-03</td>' in html
    assert '<td class="dt" data-sort="20260629">2026-06-29</td>' in html


def test_live_leaderboard_renders_overall_and_decisive_accuracy(monkeypatch, tmp_path):
    monkeypatch.setattr(dashboard, "build_standings", lambda: [
        VariantStanding(
            variant_id="model_a",
            n_scored=10,
            mean_rps=0.1,
            mean_log_loss=0.7,
            mean_brier=0.4,
            overall_accuracy=0.6,
            decisive_accuracy=0.8,
            edge_vs_baseline_rps=0.02,
        )
    ])
    monkeypatch.setattr(
        dashboard,
        "load_results",
        lambda: pd.DataFrame(columns=["match_id", "home_score", "away_score"]),
    )
    monkeypatch.setattr(
        dashboard,
        "collect_predictions",
        lambda: pd.DataFrame(),
    )
    monkeypatch.setattr(
        dashboard,
        "load_silver_data",
        lambda: (
            pd.DataFrame(),
            pd.DataFrame(columns=["fixture_id"]),
            pd.DataFrame(columns=["canonical_team_id", "canonical_name"]),
        ),
    )
    monkeypatch.setattr(dashboard, "load_backtest_cache", lambda: None)
    monkeypatch.setattr(dashboard, "_betting_section", lambda: "")
    monkeypatch.setattr(dashboard, "_accuracy_timeline", lambda *args, **kwargs: [])
    monkeypatch.setattr(dashboard, "_accuracy_timeline_section", lambda *args, **kwargs: "")

    out_path = dashboard.build_dashboard(out_path=tmp_path / "dashboard.html", publish_pages=False)
    html = out_path.read_text(encoding="utf-8")

    assert '<th class="num">acc</th><th class="num">dec.acc</th>' in html
    assert 'data-label="acc" data-sort="0.6">0.60</td>' in html
    assert 'data-label="dec.acc" data-sort="0.8">0.80</td>' in html

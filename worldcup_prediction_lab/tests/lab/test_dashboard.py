"""Tests for dashboard helpers."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from wc_predictor.lab import dashboard
from wc_predictor.lab.analyst import AnalystForecast
from wc_predictor.lab.betting import BetSignal
from wc_predictor.lab.leaderboard import VariantStanding
from wc_predictor.lab.dashboard import _select_upcoming_match_ids


def _dates(mapping):
    return lambda mid: mapping.get(mid, "")


def test_dashboard_generated_display_uses_eastern_time():
    generated = dashboard._format_dashboard_generated(
        datetime(2026, 7, 3, 13, 54, tzinfo=timezone.utc)
    )

    assert generated == "2026-07-03 09:54 EDT"


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


def test_upcoming_keeps_all_today_and_tomorrow_before_limiting_future():
    dates = _dates(
        {
            "today_a": "2026-07-03",
            "today_b": "2026-07-03",
            "tomorrow_a": "2026-07-04",
            "tomorrow_b": "2026-07-04",
            "future_a": "2026-07-05",
            "future_b": "2026-07-06",
        }
    )

    selected = _select_upcoming_match_ids(
        ["future_b", "tomorrow_b", "today_b", "future_a", "tomorrow_a", "today_a"],
        fixture_date=dates,
        today="2026-07-03",
        limit=3,
    )

    assert selected[:4] == ["today_a", "today_b", "tomorrow_a", "tomorrow_b"]
    assert "future_a" not in selected
    assert "future_b" not in selected


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


def test_dashboard_uses_ab1_bucket_order(monkeypatch, tmp_path):
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
    monkeypatch.setattr(dashboard, "collect_predictions", lambda: pd.DataFrame())
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
    monkeypatch.setattr(
        dashboard,
        "_betting_section",
        lambda: '<details class="sec"><summary>Betting edges vs Polymarket</summary></details>',
    )
    monkeypatch.setattr(
        dashboard,
        "_analyst_section",
        lambda: '<details class="sec"><summary>Match-Analyst agent</summary></details>',
    )
    monkeypatch.setattr(
        dashboard,
        "_standings_section",
        lambda: '<details class="sec"><summary>Tournament standings</summary></details>',
    )
    monkeypatch.setattr(dashboard, "_accuracy_timeline", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        dashboard,
        "_accuracy_timeline_section",
        lambda *args, **kwargs: '<details class="sec"><summary>Accuracy over time</summary></details>',
    )

    out_path = dashboard.build_dashboard(out_path=tmp_path / "dashboard.html", publish_pages=False)
    html = out_path.read_text(encoding="utf-8")

    bucket_order = [
        "Forecast command center",
        "Needs attention",
        "Trust snapshot",
        "Research lab",
        "Tournament context",
    ]
    positions = [html.index(label) for label in bucket_order]

    assert positions == sorted(positions)
    assert html.index("Leaderboard") > html.index("Research lab")
    assert html.index("Results") > html.index("Research lab")


def test_dashboard_omits_polymarket_betting_section(monkeypatch, tmp_path):
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
    monkeypatch.setattr(dashboard, "collect_predictions", lambda: pd.DataFrame())
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

    def fail_if_called():
        raise AssertionError("betting section should not be part of dashboard build")

    monkeypatch.setattr(dashboard, "_betting_section", fail_if_called)
    monkeypatch.setattr(
        dashboard,
        "_analyst_section",
        lambda: '<details class="sec"><summary>Match-Analyst agent</summary></details>',
    )
    monkeypatch.setattr(dashboard, "_standings_section", lambda: "")
    monkeypatch.setattr(dashboard, "_accuracy_timeline", lambda *args, **kwargs: [])
    monkeypatch.setattr(dashboard, "_accuracy_timeline_section", lambda *args, **kwargs: "")

    out_path = dashboard.build_dashboard(out_path=tmp_path / "dashboard.html", publish_pages=False)
    html = out_path.read_text(encoding="utf-8")

    assert "Betting edges vs Polymarket" not in html
    assert 'id="sec-betting"' not in html
    assert "Match-Analyst agent" in html


def test_research_lab_renders_model_compare_tab(monkeypatch, tmp_path):
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
        ),
        VariantStanding(
            variant_id="model_b",
            n_scored=8,
            mean_rps=0.12,
            mean_log_loss=0.75,
            mean_brier=0.42,
            overall_accuracy=0.55,
            decisive_accuracy=0.7,
            edge_vs_baseline_rps=-0.01,
        ),
    ])
    monkeypatch.setattr(
        dashboard,
        "load_results",
        lambda: pd.DataFrame(columns=["match_id", "home_score", "away_score"]),
    )
    monkeypatch.setattr(dashboard, "collect_predictions", lambda: pd.DataFrame())
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
    monkeypatch.setattr(dashboard, "_analyst_section", lambda: "")
    monkeypatch.setattr(dashboard, "_standings_section", lambda: "")
    monkeypatch.setattr(dashboard, "_accuracy_timeline", lambda *args, **kwargs: [])
    monkeypatch.setattr(dashboard, "_accuracy_timeline_section", lambda *args, **kwargs: "")

    out_path = dashboard.build_dashboard(out_path=tmp_path / "dashboard.html", publish_pages=False)
    html = out_path.read_text(encoding="utf-8")

    assert 'id="research-tab-performance"' in html
    assert 'id="research-tab-compare"' in html
    assert 'for="research-tab-compare">Compare models</label>' in html
    assert '<tbody id="model-compare-body">' in html
    assert "model_a" in html
    assert "model_b" in html


def test_upcoming_rows_render_pick_and_contrarian_hooks(monkeypatch, tmp_path):
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
    monkeypatch.setattr(dashboard, "collect_predictions", lambda: pd.DataFrame())
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
    monkeypatch.setattr(dashboard, "_analyst_section", lambda: "")
    monkeypatch.setattr(dashboard, "_standings_section", lambda: "")
    monkeypatch.setattr(dashboard, "_accuracy_timeline", lambda *args, **kwargs: [])
    monkeypatch.setattr(dashboard, "_accuracy_timeline_section", lambda *args, **kwargs: "")

    out_path = dashboard.build_dashboard(out_path=tmp_path / "dashboard.html", publish_pages=False)
    html = out_path.read_text(encoding="utf-8")

    assert "function pickName(p, m)" in html
    assert "function contrarianLine(m, selectedPick)" in html
    assert 'class="pickbadge' in html
    assert 'class="ucontrarian"' in html


def test_analyst_section_shows_pending_agent_forecasts(monkeypatch):
    deterministic = AnalystForecast(
        fixture_id="fixture-det",
        as_of="2026-07-03",
        match_date="2026-07-04",
        home_team_name="Argentina",
        away_team_name="Cape Verde",
        p_home=0.86,
        p_draw=0.11,
        p_away=0.03,
        pick="home",
        pick_team="Argentina",
        confidence=0.86,
        rationale="deterministic",
        sources=["market"],
        mode="deterministic",
    )
    agent_row = {
        "fixture_id": "fixture-agent",
        "as_of": "2026-07-03",
        "match_date": "2026-07-05",
        "home_team_name": "Brazil",
        "away_team_name": "Norway",
        "p_home": 0.53,
        "p_draw": 0.26,
        "p_away": 0.21,
        "pick": "home",
        "pick_team": "Brazil",
        "confidence": 0.53,
        "rationale": "agent read news",
        "sources": ["https://example.test/news"],
        "mode": "agent",
    }

    monkeypatch.setattr(
        "wc_predictor.lab.analyst_cli.run_analyst_live",
        lambda *_args, **_kwargs: [deterministic],
    )
    monkeypatch.setattr("wc_predictor.lab.analyst_ledger.load_ledger", lambda: [agent_row])
    monkeypatch.setattr(
        dashboard,
        "load_results",
        lambda: pd.DataFrame(columns=["match_id", "home_score", "away_score"]),
    )

    html = dashboard._analyst_section()

    assert "Argentina v Cape Verde" in html
    assert "Brazil v Norway" in html
    assert "<td>agent</td>" in html
    assert "<td>deterministic</td>" in html


def test_analyst_section_renders_prediction_history_tab(monkeypatch):
    old_agent_row = {
        "fixture_id": "fixture-old",
        "as_of": "2026-06-29",
        "snapshot_date": "2026-06-29",
        "match_date": "2026-06-30",
        "home_team_name": "France",
        "away_team_name": "Iraq",
        "p_home": 0.81,
        "p_draw": 0.13,
        "p_away": 0.06,
        "pick": "home",
        "pick_team": "France",
        "confidence": 0.81,
        "rationale": "agent read the pre-match packet",
        "sources": ["https://example.test/france-iraq"],
        "mode": "agent",
    }

    monkeypatch.setattr(
        "wc_predictor.lab.analyst_cli.run_analyst_live",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr("wc_predictor.lab.analyst_ledger.load_ledger", lambda: [old_agent_row])
    monkeypatch.setattr(
        dashboard,
        "load_results",
        lambda: pd.DataFrame(
            [{"match_id": "fixture-old", "home_score": 3, "away_score": 0}]
        ),
    )

    html = dashboard._analyst_section()

    assert 'id="analyst-tab-history"' in html
    assert 'for="analyst-tab-history">History' in html
    assert "Prediction history" in html
    assert "France v Iraq" in html
    assert "2026-06-29" in html
    assert "HOME" in html

"""Unit tests for the market-overlay core (pure, offline)."""

from __future__ import annotations

import pandas as pd

from wc_predictor.forecast_live import ForecastRow
from wc_predictor.forecast_overlay import (
    overlay_forecasts,
    overlay_prediction_payloads,
    score_overlay,
    write_overlay_report,
)


def _forecast_row(fixture_id, home_id, away_id, home_name, away_name, probs, group="A"):
    ph, pd_, pa = probs
    return ForecastRow(
        fixture_id=fixture_id,
        group=group,
        match_date="2026-06-25",
        venue="Dallas (Arlington)",
        home_team_id=home_id,
        away_team_id=away_id,
        home_team_name=home_name,
        away_team_name=away_name,
        prob_home=ph,
        prob_draw=pd_,
        prob_away=pa,
        top_scoreline="1-1",
        top_scoreline_probability=0.12,
        over_2_5_probability=0.5,
        btts_probability=0.5,
        prediction_hash="deadbeef",
    )


def _market(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "home_team_id",
            "away_team_id",
            "prob_home",
            "prob_draw",
            "prob_away",
            "event_title",
        ],
    )


def test_market_used_in_direct_orientation():
    forecasts = [_forecast_row("f1", "ARG", "AUT", "Argentina", "Austria", (0.73, 0.15, 0.12))]
    market = _market([("ARG", "AUT", 0.67, 0.21, 0.11, "Argentina vs. Austria")])

    rows, summary = overlay_forecasts(forecasts, market)

    assert summary == {"forecast_count": 1, "market_covered_count": 1, "elo_fallback_count": 0}
    row = rows[0]
    assert row.source == "market"
    assert (row.prob_home, row.prob_draw, row.prob_away) == (0.67, 0.21, 0.11)
    # Elo values are retained for provenance.
    assert (row.elo_prob_home, row.elo_prob_draw, row.elo_prob_away) == (0.73, 0.15, 0.12)
    assert row.market_event_title == "Argentina vs. Austria"


def test_market_used_in_reversed_orientation_swaps_sides():
    # Fixture has Austria at home; market lists Argentina vs Austria.
    forecasts = [_forecast_row("f1", "AUT", "ARG", "Austria", "Argentina", (0.20, 0.18, 0.62))]
    market = _market([("ARG", "AUT", 0.67, 0.21, 0.11, "Argentina vs. Austria")])

    rows, summary = overlay_forecasts(forecasts, market)

    assert summary["market_covered_count"] == 1
    row = rows[0]
    assert row.source == "market"
    # Home/away market probs are swapped to the fixture's orientation; draw stays.
    assert row.prob_home == 0.11
    assert row.prob_draw == 0.21
    assert row.prob_away == 0.67


def test_elo_fallback_when_no_market():
    forecasts = [_forecast_row("f1", "GHA", "PAN", "Ghana", "Panama", (0.5, 0.25, 0.25))]
    market = _market([("ARG", "AUT", 0.67, 0.21, 0.11, "Argentina vs. Austria")])

    rows, summary = overlay_forecasts(forecasts, market)

    assert summary == {"forecast_count": 1, "market_covered_count": 0, "elo_fallback_count": 1}
    row = rows[0]
    assert row.source == "elo"
    assert (row.prob_home, row.prob_draw, row.prob_away) == (0.5, 0.25, 0.25)
    assert row.market_prob_home is None
    assert row.market_event_title is None


def test_unresolved_market_rows_are_ignored():
    forecasts = [_forecast_row("f1", "ARG", "AUT", "Argentina", "Austria", (0.73, 0.15, 0.12))]
    market = _market([(None, "AUT", 0.67, 0.21, 0.11, "?? vs. Austria")])

    rows, summary = overlay_forecasts(forecasts, market)

    assert summary["market_covered_count"] == 0
    assert rows[0].source == "elo"


def test_mixed_overlay_and_report(tmp_path):
    forecasts = [
        _forecast_row("f1", "ARG", "AUT", "Argentina", "Austria", (0.73, 0.15, 0.12), group="A"),
        _forecast_row("f2", "GHA", "PAN", "Ghana", "Panama", (0.5, 0.25, 0.25), group="B"),
    ]
    market = _market([("ARG", "AUT", 0.67, 0.21, 0.11, "Argentina vs. Austria")])

    rows, summary = overlay_forecasts(forecasts, market)
    assert summary == {"forecast_count": 2, "market_covered_count": 1, "elo_fallback_count": 1}

    path = write_overlay_report(as_of="2026-06-25", rows=rows, summary=summary, reports_dir=tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "Using market probabilities: 1" in text
    assert "Using Elo fallback: 1" in text
    assert "| market |" in text
    assert "| elo |" in text


def _results(rows):
    return pd.DataFrame(
        rows,
        columns=["date", "home_team_id", "away_team_id", "home_score", "away_score"],
    )


def _payloads():
    forecasts = [
        _forecast_row("f1", "ARG", "AUT", "Argentina", "Austria", (0.67, 0.21, 0.11)),
        _forecast_row("f2", "GHA", "PAN", "Ghana", "Panama", (0.5, 0.25, 0.25)),
    ]
    market = _market([("ARG", "AUT", 0.67, 0.21, 0.11, "Argentina vs. Austria")])
    rows, _ = overlay_forecasts(forecasts, market)
    return overlay_prediction_payloads(
        rows, as_of="2026-06-24", training_cutoff="2026-06-23",
        generated_at_utc="2026-06-24T00:00:00Z",
    )


def test_overlay_prediction_payloads_carry_ids_and_source():
    payloads = _payloads()
    p1 = next(p for p in payloads if p["home_team_id"] == "ARG")
    assert p1["model_id"] == "elo_market_overlay_v1"
    assert p1["source"] == "market"
    assert p1["match_date"] == "2026-06-25"
    assert abs(p1["prob_home"] + p1["prob_draw"] + p1["prob_away"] - 1.0) < 1e-9


def test_score_overlay_joins_on_date_and_team_pair_direct():
    payloads = _payloads()
    # Date in the payloads is the forecast match_date 2026-06-25.
    results = _results([("2026-06-25", "ARG", "AUT", 2, 0)])  # Argentina win = home
    evaluation, aggregate = score_overlay(payloads, results)
    assert aggregate["n_scored"] == 1
    row = evaluation.iloc[0]
    assert row["actual_outcome"] == "home"
    assert row["called_it"]  # market favored Argentina
    assert "market" in aggregate["by_source"]


def test_score_overlay_handles_reversed_result_orientation():
    payloads = [p for p in _payloads() if p["home_team_id"] == "ARG"]
    # Result lists the pair reversed: Austria at home, lost 0-2 to Argentina.
    results = _results([("2026-06-25", "AUT", "ARG", 0, 2)])
    evaluation, aggregate = score_overlay(payloads, results)
    assert aggregate["n_scored"] == 1
    # From the prediction orientation (Argentina home), Argentina won => home.
    assert evaluation.iloc[0]["actual_outcome"] == "home"
    assert evaluation.iloc[0]["called_it"]


def test_score_overlay_skips_unresolved_fixtures():
    payloads = _payloads()
    results = _results([("2026-06-25", "BRA", "ESP", 1, 0)])  # unrelated match
    _, aggregate = score_overlay(payloads, results)
    assert aggregate["n_scored"] == 0
    assert aggregate["mean_rps"] is None

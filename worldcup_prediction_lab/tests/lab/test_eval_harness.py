"""Regression guard: the harness must reproduce the established bars.

Every tuning/fusion/market number this session is scored by this harness, so the
recalibrated config reproducing history 0.1744 / wc72 0.1606 / market964 0.1574
is the foundation the rest of the session stands on. These run against the real
silver data (skipped if it is absent).
"""

from __future__ import annotations

import pytest

from wc_predictor.config import settings
from wc_predictor.evaluation.elo_vs_market import MARKET_ODDS_FILE, MATCHES_FILE
from wc_predictor.lab import eval_harness as eh
from wc_predictor.lab import registry

_HAVE_MATCHES = (settings.SILVER_DIR / MATCHES_FILE).exists()
_HAVE_MARKET = (settings.SILVER_DIR / MARKET_ODDS_FILE).exists()

needs_matches = pytest.mark.skipif(not _HAVE_MATCHES, reason="silver matches parquet absent")
needs_market = pytest.mark.skipif(
    not (_HAVE_MATCHES and _HAVE_MARKET), reason="silver market parquet absent"
)


@needs_matches
def test_history_bar_recalibrated():
    result = eh.score_on_history(eh.recalibrated_elo())
    assert result["n"] == 15889
    assert result["rps"] == pytest.approx(0.1744, abs=0.0005)


@needs_market
def test_market964_bar_recalibrated():
    # frame reused for both elo and market scoring; one build keeps it fast.
    frame = eh.build_market964_frame()
    assert len(frame) == 964

    result = eh.score_on_market964(None, frame=frame)
    assert result["rps"] == pytest.approx(0.1574, abs=0.0005)
    assert result["market_rps"] == pytest.approx(0.1496, abs=0.0005)

    paired = result["vs_market_paired"]
    # The market significantly beats recalibrated Elo on this sample.
    assert paired["mean_diff"] > 0.0
    assert paired["excludes_0"] is True
    assert paired["ci95"][0] > 0.0


@needs_matches
def test_wc72_bar_recalibrated():
    result = eh.score_on_wc60(lambda **kw: registry.build("elo_recalibrated", **kw))
    assert result["n"] == 72
    assert result["rps"] == pytest.approx(0.1606, abs=0.0005)


@needs_market
def test_predict_fn_contract_matches_elo_path():
    # Passing a predict_fn that returns the attached elo probs must equal the
    # predict_fn=None path (the contract the market-as-base experiments rely on).
    frame = eh.build_market964_frame()

    def elo_predict(row):
        return (
            float(row["elo_prob_home"]),
            float(row["elo_prob_draw"]),
            float(row["elo_prob_away"]),
        )

    via_fn = eh.score_on_market964(elo_predict, frame=frame)
    via_none = eh.score_on_market964(None, frame=frame)
    assert via_fn["rps"] == pytest.approx(via_none["rps"], abs=1e-9)

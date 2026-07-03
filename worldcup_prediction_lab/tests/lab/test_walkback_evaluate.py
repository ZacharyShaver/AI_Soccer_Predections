import pandas as pd

from wc_predictor.lab.walkback.evaluate import climatology_probs, evaluate, fit_temperature


def _universe(n=40):
    # alternating outcomes, elo/market mildly informative
    rows = []
    for i in range(n):
        outcome = ("home", "draw", "away")[i % 3]
        rows.append({
            "match_id": f"m{i}", "date": pd.Timestamp("2025-02-01") + pd.Timedelta(days=i),
            "home_team": "H", "away_team": "A", "home_score": 0, "away_score": 0,
            "outcome": outcome,
            "elo_prob_home": 0.45, "elo_prob_draw": 0.30, "elo_prob_away": 0.25,
            "market_prob_home": 0.46, "market_prob_draw": 0.29, "market_prob_away": 0.25,
        })
    return pd.DataFrame(rows)


def _preds(universe, p=(0.4, 0.3, 0.3)):
    return [{"match_id": str(r["match_id"]), "model": "test-model", "condition": "both",
             "p_home": p[0], "p_draw": p[1], "p_away": p[2], "pick": "home"}
            for _, r in universe.iterrows()]


def test_evaluate_produces_lane_and_ladder():
    uni = _universe()
    res = evaluate(uni, _preds(uni))
    lane = res["lanes"]["test-model/both"]
    assert lane["n"] == 40
    assert 0.0 < lane["rps"] < 1.0
    assert set(lane["vs_elo"]) == {"point", "lo", "hi"}
    assert set(res["ladder"]) >= {"climatology", "elo", "market", "test-model/both"}


def test_perfect_predictions_beat_elo():
    uni = _universe()
    preds = []
    for _, r in uni.iterrows():
        p = {"home": (0.98, 0.01, 0.01), "draw": (0.01, 0.98, 0.01),
             "away": (0.01, 0.01, 0.98)}[r["outcome"]]
        preds.append({"match_id": str(r["match_id"]), "model": "oracle", "condition": "both",
                      "p_home": p[0], "p_draw": p[1], "p_away": p[2], "pick": r["outcome"]})
    res = evaluate(uni, preds)
    assert res["lanes"]["oracle/both"]["vs_elo"]["hi"] < 0  # CI excludes 0, oracle better


def test_climatology_uses_only_pre_cutoff_rows():
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-02-01", "2025-06-01"]),
        "outcome": ["home", "home", "away"],
    })
    probs = climatology_probs(frame, cutoff="2025-01-01")
    assert probs[0] == 1.0  # only the two pre-cutoff home wins count


def test_fit_temperature_flattens_overconfidence():
    # overconfident probs on a coin-flip-ish sample -> fitted T > 1 (softens)
    probs = [(0.8, 0.1, 0.1)] * 30
    outcomes = (["home"] * 12) + (["draw"] * 9) + (["away"] * 9)
    temp = fit_temperature(probs, outcomes)
    assert temp > 1.0


def test_explicit_climatology_is_used():
    from wc_predictor.evaluation.metrics import ranked_probability_score

    uni = _universe()
    res = evaluate(uni, _preds(uni), climatology=(1.0, 0.0, 0.0))
    assert res["climatology_source"] == "explicit"
    expected = sum(ranked_probability_score((1.0, 0.0, 0.0), o) for o in uni["outcome"]) / len(uni)
    assert abs(res["ladder"]["climatology"]["rps"] - expected) < 1e-12


def test_ladder_baselines_cover_full_universe():
    uni = _universe()
    preds = _preds(uni)[:10]  # lane predicts only the first 10 matches
    res = evaluate(uni, preds)
    assert res["lanes"]["test-model/both"]["n"] == 10
    assert res["ladder"]["elo"]["n"] == len(uni)
    assert res["ladder"]["climatology"]["n"] == len(uni)

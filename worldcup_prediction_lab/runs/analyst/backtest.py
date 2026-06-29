"""Walk-forward backtest of the deterministic match-analyst core.

Replays ``deterministic_analyst`` over the 964-match market join (leak-free Elo +
de-vigged market + result + city), scoring RPS and decisive accuracy against both
Elo and the market with paired bootstrap CIs.

Honest expectation set in the plan: because the analyst is *market-anchored*, it
should land BETWEEN Elo (0.1574) and market (0.1496) and should NOT beat the market
(the CI on analyst-minus-market should not exclude 0 in our favour). The point is to
establish the floor of the quantitative core; the live news mode is where any real
edge would come from, and that's tracked forward in the ledger, not here.
"""

from __future__ import annotations

from wc_predictor.evaluation.metrics import bootstrap_ci, ranked_probability_score
from wc_predictor.forecast_live import load_silver_data
from wc_predictor.lab.altitude import home_advantage_delta_elo, team_altitude_baselines
from wc_predictor.lab.analyst import build_packet, deterministic_analyst
from wc_predictor.lab.eval_harness import build_market964_frame


def _outcome(hs, as_):
    return "home" if hs > as_ else "away" if as_ > hs else "draw"


def main() -> None:
    frame = build_market964_frame()
    matches, _, _ = load_silver_data()
    baselines = team_altitude_baselines(matches)

    rows = []
    for _, r in frame.iterrows():
        as_of = str(r["date"])[:10]
        delta = home_advantage_delta_elo(
            r.get("city"), str(r["home_team_id"]), str(r["away_team_id"]), baselines, coef=60.0
        )
        packet = build_packet(r, as_of, matches=matches, altitude_delta_elo=delta)
        fc = deterministic_analyst(packet)
        actual = _outcome(int(r["home_score"]), int(r["away_score"]))
        elo = (float(r["elo_prob_home"]), float(r["elo_prob_draw"]), float(r["elo_prob_away"]))
        mkt = (float(r["market_prob_home"]), float(r["market_prob_draw"]), float(r["market_prob_away"]))
        rows.append({
            "a_rps": ranked_probability_score(fc.probs, actual),
            "elo_rps": ranked_probability_score(elo, actual),
            "mkt_rps": ranked_probability_score(mkt, actual),
            "a_hit": fc.pick == actual,
            "elo_hit": ("home" if elo[0] >= elo[1] and elo[0] >= elo[2]
                        else "draw" if elo[1] >= elo[2] else "away") == actual,
            "mkt_hit": ("home" if mkt[0] >= mkt[1] and mkt[0] >= mkt[2]
                        else "draw" if mkt[1] >= mkt[2] else "away") == actual,
        })

    n = len(rows)
    a = sum(x["a_rps"] for x in rows) / n
    e = sum(x["elo_rps"] for x in rows) / n
    m = sum(x["mkt_rps"] for x in rows) / n
    _, lo_e, hi_e, _ = bootstrap_ci([x["a_rps"] - x["elo_rps"] for x in rows], n_boot=2000, seed=11)
    _, lo_m, hi_m, _ = bootstrap_ci([x["a_rps"] - x["mkt_rps"] for x in rows], n_boot=2000, seed=11)

    print(f"ANALYST CORE WALK-FORWARD BACKTEST on {n} market-joined matches\n")
    print(f"{'model':10s} {'RPS':>8s} {'accuracy':>9s}")
    print(f"{'analyst':10s} {a:8.4f} {sum(x['a_hit'] for x in rows)/n*100:8.1f}%")
    print(f"{'elo':10s} {e:8.4f} {sum(x['elo_hit'] for x in rows)/n*100:8.1f}%")
    print(f"{'market':10s} {m:8.4f} {sum(x['mkt_hit'] for x in rows)/n*100:8.1f}%")
    print()
    print(f"analyst - elo    : {a-e:+.4f}  95% CI [{lo_e:+.4f}, {hi_e:+.4f}]"
          f"  {'(sig)' if lo_e > 0 or hi_e < 0 else '(tie)'}")
    print(f"analyst - market : {a-m:+.4f}  95% CI [{lo_m:+.4f}, {hi_m:+.4f}]"
          f"  {'(sig)' if lo_m > 0 or hi_m < 0 else '(tie)'}")
    print("\n(negative = analyst better. Expect: beats/ties Elo, does NOT beat market —")
    print(" market-anchored by design. The live news mode is the only real-edge path.)")


if __name__ == "__main__":
    main()

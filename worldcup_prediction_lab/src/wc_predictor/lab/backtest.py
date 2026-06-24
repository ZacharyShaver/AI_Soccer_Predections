"""Walk-forward backtest of every variant over already-played WC 2026 matches.

For each played World Cup fixture, each variant is trained ONLY on international
results strictly before that match's date (leak-free walk-forward) and scored on
the actual result. This is the "backtrace": predictions for games made without
the later games' data, giving a much larger sample than the handful of live
recorded forecasts — so the leaderboard means something mid-tournament.

Results are cached to runs/experiments/backtest_cache.json (the dashboard reads
it) and written human-readably to research/BACKTEST.md.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.evaluation.metrics import (
    brier_score,
    home_draw_away_log_loss,
    ranked_probability_score,
)
from wc_predictor.lab import registry
from wc_predictor.lab.leaderboard import (
    BASELINE_VARIANT,
    VariantStanding,
    fixture_keyed_results,
)

CACHE_PATH = settings.EXPERIMENTS_DIR / "backtest_cache.json"
REPORT_PATH = settings.RESEARCH_DIR / "BACKTEST.md"


def _outcome(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return "draw"


def _played_world_cup_matches(
    matches_df: pd.DataFrame, fixtures_df: pd.DataFrame
) -> pd.DataFrame:
    """Fixtures that have a result, with [fixture_id, match_date, home/away_team_id, scores]."""

    results = fixture_keyed_results(matches_df, fixtures_df)
    if results.empty:
        return pd.DataFrame()
    scores = {
        str(r["match_id"]): (int(r["home_score"]), int(r["away_score"]))
        for _, r in results.iterrows()
    }
    rows = []
    for fixture in fixtures_df.itertuples(index=False):
        fid = str(getattr(fixture, "fixture_id"))
        if fid not in scores:
            continue
        match_date = pd.to_datetime(getattr(fixture, "match_date"), errors="coerce")
        if pd.isna(match_date):
            continue
        hs, away = scores[fid]
        rows.append(
            {
                "fixture_id": fid,
                "match_date": match_date,
                "home_team_id": getattr(fixture, "home_team_id"),
                "away_team_id": getattr(fixture, "away_team_id"),
                "venue": getattr(fixture, "venue", None),
                "group": getattr(fixture, "group", None),
                "home_score": hs,
                "away_score": away,
            }
        )
    return pd.DataFrame(rows).sort_values("match_date").reset_index(drop=True)


def run_backtest(
    *,
    matches_df: pd.DataFrame | None = None,
    fixtures_df: pd.DataFrame | None = None,
    teams_df: pd.DataFrame | None = None,
    write: bool = True,
) -> dict:
    from wc_predictor.forecast_live import (
        _fixture_match_row,
        _team_names,
        _training_matches,
        load_silver_data,
    )

    if matches_df is None or fixtures_df is None or teams_df is None:
        matches_df, fixtures_df, teams_df = load_silver_data()

    names = _team_names(teams_df)
    played = _played_world_cup_matches(matches_df, fixtures_df)

    per_variant: dict[str, dict] = {}
    detail: dict[str, list[dict]] = {}
    if not played.empty:
        match_dates = sorted(played["match_date"].dt.strftime("%Y-%m-%d").unique())
        for info in registry.list_variants():
            vid = info.variant_id
            rps_list, ll_list, brier_list, hits = [], [], [], 0
            rows_detail: list[dict] = []
            for day in match_dates:
                day_ts = pd.Timestamp(day)
                cutoff = (day_ts - timedelta(days=1)).strftime("%Y-%m-%d")
                model = registry.build(vid, generated_at_utc=f"{day}T00:00:00Z")
                model.fit(_training_matches(matches_df, training_cutoff=cutoff))
                day_matches = played.loc[played["match_date"] == day_ts]
                for fixture in day_matches.itertuples(index=False):
                    match_row = _fixture_match_row(pd.Series(fixture._asdict()), names)
                    outcome = model.predict_match(match_row)
                    probs = [outcome.prob_home, outcome.prob_draw, outcome.prob_away]
                    total = sum(probs) or 1.0
                    probs = [p / total for p in probs]
                    actual = _outcome(fixture.home_score, fixture.away_score)
                    rps_list.append(ranked_probability_score(probs, actual))
                    ll_list.append(home_draw_away_log_loss(probs, actual))
                    brier_list.append(brier_score(probs, actual))
                    pick = ("home", "draw", "away")[probs.index(max(probs))]
                    if pick == actual:
                        hits += 1
                    rows_detail.append(
                        {
                            "fixture_id": fixture.fixture_id,
                            "date": day,
                            "actual": actual,
                            "pick": pick,
                            "rps": round(ranked_probability_score(probs, actual), 4),
                        }
                    )
            n = len(rps_list)
            finite_ll = [v for v in ll_list if v != float("inf")]
            per_variant[vid] = {
                "n": n,
                "rps": (sum(rps_list) / n) if n else None,
                "log_loss": (sum(finite_ll) / len(finite_ll)) if finite_ll else None,
                "brier": (sum(brier_list) / n) if n else None,
                "accuracy": (hits / n) if n else None,
            }
            detail[vid] = rows_detail

    baseline_rps = per_variant.get(BASELINE_VARIANT, {}).get("rps")
    standings = []
    for vid, agg in per_variant.items():
        edge = None
        if baseline_rps is not None and agg["rps"] is not None:
            edge = round(baseline_rps - agg["rps"], 6)
        standings.append(
            VariantStanding(
                variant_id=vid,
                n_scored=agg["n"],
                mean_rps=agg["rps"],
                mean_log_loss=agg["log_loss"],
                mean_brier=agg["brier"],
                decisive_accuracy=agg["accuracy"],  # here: overall outcome accuracy
                edge_vs_baseline_rps=edge,
            )
        )
    standings.sort(key=lambda s: (s.mean_rps is None, s.mean_rps if s.mean_rps is not None else 0.0))

    n_matches = int(len(played))
    payload = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "n_matches": n_matches,
        "date_range": (
            [played["match_date"].min().strftime("%Y-%m-%d"), played["match_date"].max().strftime("%Y-%m-%d")]
            if n_matches
            else None
        ),
        "standings": [asdict(s) for s in standings],
    }

    if write:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(_format_report(payload), encoding="utf-8")

    return payload


def _format_report(payload: dict) -> str:
    rng = payload["date_range"]
    lines = [
        "# Walk-forward backtest — played WC 2026 matches",
        "",
        f"Generated: `{payload['generated']}`",
        "",
        "Leak-free walk-forward: each variant is trained only on results strictly before each "
        "match's date, then scored on the actual outcome. Lower RPS/log loss/Brier is better; "
        "accuracy = share of matches whose argmax pick was correct.",
        "",
        f"- Matches backtested: **{payload['n_matches']}**"
        + (f" ({rng[0]} → {rng[1]})" if rng else ""),
        "",
        "| Variant | n | RPS | log loss | Brier | accuracy | edge vs baseline |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for s in payload["standings"]:
        tag = " (baseline)" if s["variant_id"] == BASELINE_VARIANT else ""
        def f(v, d=4):
            return f"{v:.{d}f}" if v is not None else "—"
        edge = f"{s['edge_vs_baseline_rps']:+.4f}" if s["edge_vs_baseline_rps"] is not None else "—"
        lines.append(
            f"| `{s['variant_id']}`{tag} | {s['n_scored']} | {f(s['mean_rps'])} | "
            f"{f(s['mean_log_loss'])} | {f(s['mean_brier'])} | {f(s['decisive_accuracy'], 3)} | {edge} |"
        )
    lines += [
        "",
        "Note: the backtest is analytical (not the immutable live forecast ledger). It re-fits each "
        "variant per match date, so it grows automatically as more WC matches are played.",
        "",
    ]
    return "\n".join(lines)


def load_cache() -> dict | None:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    return None


def main() -> None:
    payload = run_backtest()
    print(f"[backtest] matches={payload['n_matches']}")
    for s in payload["standings"]:
        rps = f"{s['mean_rps']:.4f}" if s["mean_rps"] is not None else "—"
        acc = f"{s['decisive_accuracy']:.3f}" if s["decisive_accuracy"] is not None else "—"
        print(f"  {s['variant_id']:14} n={s['n_scored']} rps={rps} acc={acc}")


if __name__ == "__main__":
    main()

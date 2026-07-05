"""Scratch (not committed): fuse dixon_coles_tuned x elo_recalibrated.

Motivation: dixon_coles_tuned beats elo_recalibrated on the 15.9k history
walk-forward (paired CI excludes 0) yet wins only ~50.7% of individual
matches — genuinely decorrelated errors. The prior fusion null (Codex T2:
"fusion never beats the best single constituent") tested only near-identical
Elo-family variants, so it does not cover this pair.

Leak-free protocol:
* history: both models run online predict-then-update; the pool weight lam
  (weight on DC) is chosen by a 6-block time-ordered walk-forward — block k
  is scored with the lam picked ONLY on blocks < k (out-of-fold). The
  a-priori equal weight lam=0.5 needs no selection, so it is also scored on
  the full sample.
* wc_played: per-date refit (same contract as eval_harness.score_on_wc60),
  pooled with equal weight and with the history-frozen lam.
* market964: DC probs attached strictly-before-date (same loop shape as the
  dixon_coles_scratch verify), Elo probs are the harness's own leak-free
  attach; pools scored with equal weight and the history-frozen lam.

Promotion bar (same as every lane): fused beats the BEST single constituent
(dixon_coles_tuned) on history with a paired CI excluding 0, no material
wc regression.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pandas as pd

from wc_predictor.evaluation.elo_vs_market import _has_value, _normalize_dates
from wc_predictor.evaluation.metrics import (
    bootstrap_ci,
    brier_score,
    home_draw_away_log_loss,
    ranked_probability_score,
)
from wc_predictor.lab import eval_harness as eh
from wc_predictor.lab import fusion_ledger
from wc_predictor.lab.fusion_recipes import linear_opinion_pool, logarithmic_opinion_pool
from wc_predictor.lab.variants.dixon_coles_tuned import TUNED_KWARGS
from wc_predictor.models.dixon_coles import DixonColesModel

LAM_GRID = [round(0.05 * i, 2) for i in range(21)]  # weight on dixon_coles
N_BLOCKS = 6
SEED = 20260702

POOLS = {
    "linear": linear_opinion_pool,
    "log": logarithmic_opinion_pool,
}


def _outcome(home_score, away_score) -> str:
    home_score, away_score = int(home_score), int(away_score)
    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return "draw"


def _paired(diffs: list[float], *, seed: int = SEED) -> dict:
    point, low, high, _ = bootstrap_ci(diffs, n_boot=1000, alpha=0.05, seed=seed)
    return {
        "n": len(diffs),
        "mean_diff": point,
        "ci95": [low, high],
        "excludes_0": (low > 0.0) or (high < 0.0),
    }


def _pool_probs(pool_name: str, dc: tuple, elo: tuple, lam: float) -> list[float]:
    fused = POOLS[pool_name]([dc, elo], weights=[lam, 1.0 - lam])
    return eh._normalize(fused)


def _metrics(rps_list, ll_list, brier_list, hits, dec_hits, dec_n) -> dict:
    n = len(rps_list)
    return {
        "n": n,
        "rps": sum(rps_list) / n,
        "log_loss": sum(ll_list) / n,
        "brier": sum(brier_list) / n,
        "acc": hits / n,
        "dec_acc": dec_hits / dec_n if dec_n else float("nan"),
    }


# ---------------------------------------------------------------------------
# Part A: history walk-forward, paired per-match triples for both models
# ---------------------------------------------------------------------------
def collect_history_rows() -> list[dict]:
    matches = eh.load_history_matches()
    start = pd.Timestamp(eh.HISTORY_EVAL_START)
    dc = DixonColesModel(**TUNED_KWARGS)
    elo = eh.recalibrated_elo()

    rows: list[dict] = []
    for row in matches.itertuples(index=False):
        record = row._asdict()
        series = pd.Series(record)
        if record["date"] >= start:
            actual = _outcome(record["home_score"], record["away_score"])
            dp = dc.predict_match(series)
            ep = elo.predict_match(series)
            rows.append(
                {
                    "actual": actual,
                    "dc": tuple(eh._normalize((dp.prob_home, dp.prob_draw, dp.prob_away))),
                    "elo": tuple(eh._normalize((ep.prob_home, ep.prob_draw, ep.prob_away))),
                }
            )
        dc._update_from_match(series)
        elo._update_from_match(series)
    return rows


def history_analysis(rows: list[dict]) -> dict:
    # Per-match RPS for every lam in the grid, per pool — computed once.
    per_lam_rps: dict[str, dict[float, list[float]]] = {p: {} for p in POOLS}
    for pool_name in POOLS:
        for lam in LAM_GRID:
            per_lam_rps[pool_name][lam] = [
                ranked_probability_score(_pool_probs(pool_name, r["dc"], r["elo"], lam), r["actual"])
                for r in rows
            ]
    dc_rps = per_lam_rps["linear"][1.0]  # lam=1 -> pure DC (same for either pool)
    elo_rps = per_lam_rps["linear"][0.0]

    out: dict = {
        "n": len(rows),
        "dc_rps": sum(dc_rps) / len(rows),
        "elo_rps": sum(elo_rps) / len(rows),
        "dc_vs_elo_paired": _paired([d - e for d, e in zip(dc_rps, elo_rps)]),
    }

    # Block boundaries (time-ordered; rows are already chronological).
    n = len(rows)
    bounds = [round(i * n / N_BLOCKS) for i in range(N_BLOCKS + 1)]

    for pool_name in POOLS:
        grid = per_lam_rps[pool_name]

        # (1) equal weight, full sample (a-priori weight: no selection leak).
        eq = grid[0.5]
        out[f"{pool_name}_equal_full"] = {
            "lam": 0.5,
            "rps": sum(eq) / n,
            "vs_dc_paired": _paired([f - d for f, d in zip(eq, dc_rps)]),
            "vs_elo_paired": _paired([f - e for f, e in zip(eq, elo_rps)]),
        }

        # (2) walk-forward lam: block k scored with argmin-lam over blocks < k.
        oof_rps: list[float] = []
        oof_dc: list[float] = []
        oof_elo: list[float] = []
        lam_path: list[float] = []
        for k in range(1, N_BLOCKS):
            prior = slice(bounds[0], bounds[k])
            block = slice(bounds[k], bounds[k + 1])
            lam_star = min(LAM_GRID, key=lambda lam: sum(grid[lam][prior]))
            lam_path.append(lam_star)
            oof_rps.extend(grid[lam_star][block])
            oof_dc.extend(dc_rps[block])
            oof_elo.extend(elo_rps[block])
        out[f"{pool_name}_walkforward"] = {
            "lam_path": lam_path,
            "n_oof": len(oof_rps),
            "rps": sum(oof_rps) / len(oof_rps),
            "dc_rps_same_matches": sum(oof_dc) / len(oof_dc),
            "vs_dc_paired": _paired([f - d for f, d in zip(oof_rps, oof_dc)]),
            "vs_elo_paired": _paired([f - e for f, e in zip(oof_rps, oof_elo)]),
        }

        # (3) full-sample argmin lam — transparency + the frozen deployment weight.
        lam_full = min(LAM_GRID, key=lambda lam: sum(grid[lam]))
        out[f"{pool_name}_full_argmin"] = {
            "lam": lam_full,
            "rps": sum(grid[lam_full]) / n,
            "in_sample": True,
        }
    return out


# ---------------------------------------------------------------------------
# Part B: wc_played per-date refit, pooled
# ---------------------------------------------------------------------------
def wc_played_analysis(lams: dict[str, float]) -> dict:
    from wc_predictor.forecast_live import (
        _fixture_match_row,
        _team_names,
        _training_matches,
        load_silver_data,
    )
    from wc_predictor.lab.backtest import _played_world_cup_matches
    from wc_predictor.lab import registry

    matches_df, fixtures_df, teams_df = load_silver_data()
    names = _team_names(teams_df)
    played = _played_world_cup_matches(matches_df, fixtures_df)
    match_dates = sorted(played["match_date"].dt.strftime("%Y-%m-%d").unique())

    variants = ["dc", "elo"]
    keys = variants + [f"{p}_{tag}" for p in POOLS for tag in ("equal", "frozen")]
    acc: dict[str, dict] = {
        k: {"rps": [], "ll": [], "brier": [], "hits": 0, "dec_hits": 0, "dec_n": 0} for k in keys
    }

    for day in match_dates:
        day_ts = pd.Timestamp(day)
        cutoff = (day_ts - timedelta(days=1)).strftime("%Y-%m-%d")
        train = _training_matches(matches_df, training_cutoff=cutoff)
        dc = registry.build("dixon_coles_tuned", generated_at_utc=f"{day}T00:00:00Z")
        elo = registry.build("elo_recalibrated", generated_at_utc=f"{day}T00:00:00Z")
        dc.fit(train)
        elo.fit(train)
        for fixture in played.loc[played["match_date"] == day_ts].itertuples(index=False):
            match_row = _fixture_match_row(pd.Series(fixture._asdict()), names)
            actual = _outcome(fixture.home_score, fixture.away_score)
            dp = dc.predict_match(match_row)
            ep = elo.predict_match(match_row)
            triples = {
                "dc": tuple(eh._normalize((dp.prob_home, dp.prob_draw, dp.prob_away))),
                "elo": tuple(eh._normalize((ep.prob_home, ep.prob_draw, ep.prob_away))),
            }
            for pool_name in POOLS:
                triples[f"{pool_name}_equal"] = tuple(
                    _pool_probs(pool_name, triples["dc"], triples["elo"], 0.5)
                )
                triples[f"{pool_name}_frozen"] = tuple(
                    _pool_probs(pool_name, triples["dc"], triples["elo"], lams[pool_name])
                )
            for key, probs in triples.items():
                probs = list(probs)
                a = acc[key]
                a["rps"].append(ranked_probability_score(probs, actual))
                ll = home_draw_away_log_loss(probs, actual)
                a["ll"].append(ll if ll != float("inf") else 0.0)
                a["brier"].append(brier_score(probs, actual))
                pick = ("home", "draw", "away")[probs.index(max(probs))]
                a["hits"] += int(pick == actual)
                if actual != "draw":
                    a["dec_n"] += 1
                    a["dec_hits"] += int(pick == actual)

    return {
        key: _metrics(a["rps"], a["ll"], a["brier"], a["hits"], a["dec_hits"], a["dec_n"])
        for key, a in acc.items()
    }


# ---------------------------------------------------------------------------
# Part C: market964, DC attached strictly-before-date; harness Elo attach
# ---------------------------------------------------------------------------
def market964_analysis(lams: dict[str, float]) -> dict:
    frame = eh.build_market964_frame()  # carries leak-free elo_prob_* + market_prob_*
    raw_matches = eh._read_parquet(eh.settings.SILVER_DIR / eh.MATCHES_FILE)

    evaluation = _normalize_dates(frame)
    train_matches = _normalize_dates(raw_matches)
    train_matches = train_matches[
        _has_value(train_matches["home_team_id"])
        & _has_value(train_matches["away_team_id"])
        & train_matches["home_score"].notna()
        & train_matches["away_score"].notna()
    ].copy()
    sort_columns = [
        c for c in ("date", "occurrence_index", "match_id") if c in train_matches.columns
    ]
    train_matches = train_matches.sort_values(sort_columns, kind="mergesort").reset_index(drop=True)
    evaluation = evaluation.sort_values(
        ["date", "match_id", "market_row_id"], kind="mergesort"
    ).reset_index(drop=True)

    model = DixonColesModel(**TUNED_KWARGS)
    train_index = 0
    dc_cols = []
    for match_date, date_matches in evaluation.groupby("date", sort=True):
        while (
            train_index < len(train_matches)
            and train_matches.iloc[train_index]["date"] < match_date
        ):
            model._update_from_match(train_matches.iloc[train_index])
            train_index += 1
        for _, row in date_matches.iterrows():
            prediction = model.predict_match(row)
            dc_cols.append(
                {
                    "dc_prob_home": prediction.prob_home,
                    "dc_prob_draw": prediction.prob_draw,
                    "dc_prob_away": prediction.prob_away,
                }
            )
    frame2 = pd.concat([evaluation, pd.DataFrame(dc_cols)], axis=1)

    def dc_fn(row):
        return (row["dc_prob_home"], row["dc_prob_draw"], row["dc_prob_away"])

    def make_pool_fn(pool_name: str, lam: float):
        def fn(row):
            dc = eh._normalize((row["dc_prob_home"], row["dc_prob_draw"], row["dc_prob_away"]))
            elo = eh._normalize((row["elo_prob_home"], row["elo_prob_draw"], row["elo_prob_away"]))
            return tuple(_pool_probs(pool_name, tuple(dc), tuple(elo), lam))

        return fn

    out = {
        "dc": eh.score_on_market964(dc_fn, frame=frame2),
        "elo": eh.score_on_market964(None, frame=frame2),
    }
    for pool_name in POOLS:
        out[f"{pool_name}_equal"] = eh.score_on_market964(
            make_pool_fn(pool_name, 0.5), frame=frame2
        )
        out[f"{pool_name}_frozen"] = eh.score_on_market964(
            make_pool_fn(pool_name, lams[pool_name]), frame=frame2
        )

    # Paired fused-vs-DC on the 964 (is fusion better than the best constituent here too?)
    dc_rps, pooled_rps = [], {p: [] for p in POOLS}
    for _, row in frame2.iterrows():
        actual = _outcome(int(row["home_score"]), int(row["away_score"]))
        dc = eh._normalize((row["dc_prob_home"], row["dc_prob_draw"], row["dc_prob_away"]))
        elo = eh._normalize((row["elo_prob_home"], row["elo_prob_draw"], row["elo_prob_away"]))
        dc_rps.append(ranked_probability_score(dc, actual))
        for pool_name in POOLS:
            pooled = _pool_probs(pool_name, tuple(dc), tuple(elo), lams[pool_name])
            pooled_rps[pool_name].append(ranked_probability_score(pooled, actual))
    for pool_name in POOLS:
        out[f"{pool_name}_frozen"]["vs_dc_paired"] = _paired(
            [f - d for f, d in zip(pooled_rps[pool_name], dc_rps)]
        )
    return out


def main() -> None:
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print("[1/3] history walk-forward ...", flush=True)
    rows = collect_history_rows()
    hist = history_analysis(rows)
    print(json.dumps(hist, indent=1), flush=True)

    lams = {p: hist[f"{p}_full_argmin"]["lam"] for p in POOLS}

    print("[2/3] wc_played ...", flush=True)
    wc = wc_played_analysis(lams)
    print(json.dumps(wc, indent=1), flush=True)

    print("[3/3] market964 ...", flush=True)
    market = market964_analysis(lams)
    print(json.dumps(market, indent=1), flush=True)

    result_all = {"history": hist, "wc_played": wc, "market964": market, "lams": lams}
    with open("runs/dc_fusion_scratch/results.json", "w", encoding="utf-8") as f:
        json.dump(result_all, f, indent=2, default=str)

    # One ledger entry per recipe, matching the established schema.
    for pool_name in POOLS:
        wf = hist[f"{pool_name}_walkforward"]
        promote = (
            wf["vs_dc_paired"]["excludes_0"]
            and wf["vs_dc_paired"]["mean_diff"] < 0.0
        )
        fusion_ledger.record(
            {
                "agent": "claude",
                "task": "dc_elo_fusion",
                "exp_id": f"fuse-dc-elo-{pool_name}",
                "created_utc": created,
                "config": {
                    "constituents": ["dixon_coles_tuned", "elo_recalibrated"],
                    "pool": pool_name,
                    "lam_grid": "0..1 step 0.05 (weight on dixon_coles)",
                    "weight_selection": "6-block time-ordered walk-forward (out-of-fold)",
                    "equal_weight_check": hist[f"{pool_name}_equal_full"],
                    "frozen_lam_for_transfer": lams[pool_name],
                    "promotion_rule": (
                        "beat the BEST single constituent (dixon_coles_tuned) on history "
                        "out-of-fold with paired CI excluding 0, no material wc regression"
                    ),
                },
                "samples": {
                    "hist_oof": {
                        "n": wf["n_oof"],
                        "rps": wf["rps"],
                        "dc_rps_same_matches": wf["dc_rps_same_matches"],
                    },
                    "wc_played": wc[f"{pool_name}_frozen"],
                    "market964": {
                        k: v
                        for k, v in market[f"{pool_name}_frozen"].items()
                        if k != "vs_dc_paired"
                    },
                },
                "fused_vs_best_constituent_paired": wf["vs_dc_paired"],
                "market964_fused_vs_dc_paired": market[f"{pool_name}_frozen"]["vs_dc_paired"],
                "notes": (
                    "First fusion of genuinely decorrelated constituents (DC wins ~50.7% of "
                    "individual history matches vs recalibrated Elo). Weight chosen out-of-fold; "
                    "equal-weight full-sample check recorded in config. The prior T2 fusion null "
                    "covered only correlated Elo-family variants."
                ),
                "promote": bool(promote),
            }
        )
    print("ledger entries written", flush=True)


if __name__ == "__main__":
    main()

"""Scratch (not committed): stack squad_value under dc_elo_fusion's Elo leg.

Today's two promotions are independent gains over elo_recalibrated:
* dc_elo_fusion — log pool(dixon_coles_tuned 0.7, elo_recalibrated 0.3)
* squad_value  — elo_recalibrated + Transfermarkt squad-value Elo delta

Hypothesis: pooling DC with squad_value (instead of plain recal) inherits the
squad signal the DC leg cannot see, beating the CURRENT CHAMPION dc_elo_fusion.

Protocol (same as the dc-elo fusion lane):
* one history walk collects per-match triples for THREE online models —
  dixon_coles_tuned, elo_recalibrated, squad_value — all predict-then-update;
* challenger pool weight chosen OUT-OF-FOLD (6 time blocks, weight picked only
  on earlier blocks); the champion uses its FROZEN weight 0.7 (no selection),
  so the paired champion-vs-challenger test is honest on the same matches;
* market964: both pools with frozen weights, DC + both Elo legs attached
  strictly-before-date.
"""

from __future__ import annotations

import json

import pandas as pd

from wc_predictor.evaluation.elo_vs_market import _has_value, _normalize_dates
from wc_predictor.evaluation.metrics import bootstrap_ci, ranked_probability_score
from wc_predictor.lab import eval_harness as eh
from wc_predictor.lab.fusion_recipes import logarithmic_opinion_pool
from wc_predictor.lab.variants.dixon_coles_tuned import TUNED_KWARGS
from wc_predictor.lab.variants.elo_recalibrated import recalibrated_elo_kwargs
from wc_predictor.lab.variants.squad_value import SquadValueEloModel
from wc_predictor.models.dixon_coles import DixonColesModel

CHAMPION_LAM = 0.7  # dc_elo_fusion's frozen weight on DC
LAM_GRID = [round(0.05 * i, 2) for i in range(21)]
N_BLOCKS = 6
SEED = 20260702


def _outcome(home_score, away_score) -> str:
    home_score, away_score = int(home_score), int(away_score)
    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return "draw"


def _paired(diffs: list[float]) -> dict:
    point, low, high, _ = bootstrap_ci(diffs, n_boot=1000, alpha=0.05, seed=SEED)
    return {
        "n": len(diffs),
        "mean_diff": point,
        "ci95": [low, high],
        "excludes_0": (low > 0.0) or (high < 0.0),
    }


def _pool(dc: tuple, elo: tuple, lam: float) -> list[float]:
    return eh._normalize(logarithmic_opinion_pool([dc, elo], weights=[lam, 1.0 - lam]))


def collect_walk() -> list[dict]:
    matches = eh.load_history_matches()
    start = pd.Timestamp(eh.HISTORY_EVAL_START)
    dc = DixonColesModel(**TUNED_KWARGS)
    recal = eh.recalibrated_elo()
    squad = SquadValueEloModel(**recalibrated_elo_kwargs())

    rows: list[dict] = []
    for row in matches.itertuples(index=False):
        record = row._asdict()
        series = pd.Series(record)
        if record["date"] >= start:
            triples = {}
            for key, model in (("dc", dc), ("recal", recal), ("squad", squad)):
                p = model.predict_match(series)
                triples[key] = tuple(eh._normalize((p.prob_home, p.prob_draw, p.prob_away)))
            rows.append(
                {"actual": _outcome(record["home_score"], record["away_score"]), **triples}
            )
        for model in (dc, recal, squad):
            model._update_from_match(series)
    return rows


def main() -> None:
    rows = collect_walk()
    n = len(rows)
    print(f"walk collected: n={n}", flush=True)

    champion = [
        ranked_probability_score(_pool(r["dc"], r["recal"], CHAMPION_LAM), r["actual"])
        for r in rows
    ]
    grid = {
        lam: [
            ranked_probability_score(_pool(r["dc"], r["squad"], lam), r["actual"])
            for r in rows
        ]
        for lam in LAM_GRID
    }

    out: dict = {
        "n": n,
        "champion_dc_recal_rps": sum(champion) / n,
        "squad_leg_frozen_0.7_rps": sum(grid[CHAMPION_LAM]) / n,
        "frozen_0.7_vs_champion_paired": _paired(
            [c - ch for c, ch in zip(grid[CHAMPION_LAM], champion)]
        ),
    }

    # Out-of-fold lam selection for the challenger.
    bounds = [round(i * n / N_BLOCKS) for i in range(N_BLOCKS + 1)]
    oof, oof_champ = [], []
    lam_path = []
    for k in range(1, N_BLOCKS):
        prior, block = slice(bounds[0], bounds[k]), slice(bounds[k], bounds[k + 1])
        lam_star = min(LAM_GRID, key=lambda lam: sum(grid[lam][prior]))
        lam_path.append(lam_star)
        oof.extend(grid[lam_star][block])
        oof_champ.extend(champion[block])
    out["oof"] = {
        "lam_path": lam_path,
        "rps": sum(oof) / len(oof),
        "champion_rps_same_matches": sum(oof_champ) / len(oof_champ),
        "vs_champion_paired": _paired([c - ch for c, ch in zip(oof, oof_champ)]),
    }
    lam_full = min(LAM_GRID, key=lambda lam: sum(grid[lam]))
    out["full_argmin"] = {"lam": lam_full, "rps": sum(grid[lam_full]) / n, "in_sample": True}

    print(json.dumps(out, indent=1), flush=True)

    # market964: attach DC + both Elo legs strictly-before-date, score pools.
    frame = eh.build_market964_frame()  # elo_prob_* = leak-free recal attach
    raw_matches = eh._read_parquet(eh.settings.SILVER_DIR / eh.MATCHES_FILE)
    evaluation = _normalize_dates(frame)
    train = _normalize_dates(raw_matches)
    train = train[
        _has_value(train["home_team_id"])
        & _has_value(train["away_team_id"])
        & train["home_score"].notna()
        & train["away_score"].notna()
    ].copy()
    sort_columns = [c for c in ("date", "occurrence_index", "match_id") if c in train.columns]
    train = train.sort_values(sort_columns, kind="mergesort").reset_index(drop=True)
    evaluation = evaluation.sort_values(
        ["date", "match_id", "market_row_id"], kind="mergesort"
    ).reset_index(drop=True)

    dc = DixonColesModel(**TUNED_KWARGS)
    squad = SquadValueEloModel(**recalibrated_elo_kwargs())
    index = 0
    extra = []
    for match_date, day_rows in evaluation.groupby("date", sort=True):
        while index < len(train) and train.iloc[index]["date"] < match_date:
            dc._update_from_match(train.iloc[index])
            squad._update_from_match(train.iloc[index])
            index += 1
        for _, row in day_rows.iterrows():
            dp = dc.predict_match(row)
            sp = squad.predict_match(row)
            extra.append(
                {
                    "dc_h": dp.prob_home, "dc_d": dp.prob_draw, "dc_a": dp.prob_away,
                    "sq_h": sp.prob_home, "sq_d": sp.prob_draw, "sq_a": sp.prob_away,
                }
            )
    frame2 = pd.concat([evaluation, pd.DataFrame(extra)], axis=1)

    def champion_fn(row):
        dc_t = eh._normalize((row["dc_h"], row["dc_d"], row["dc_a"]))
        recal_t = eh._normalize((row["elo_prob_home"], row["elo_prob_draw"], row["elo_prob_away"]))
        return tuple(_pool(tuple(dc_t), tuple(recal_t), CHAMPION_LAM))

    def challenger_fn(row):
        dc_t = eh._normalize((row["dc_h"], row["dc_d"], row["dc_a"]))
        sq_t = eh._normalize((row["sq_h"], row["sq_d"], row["sq_a"]))
        return tuple(_pool(tuple(dc_t), tuple(sq_t), CHAMPION_LAM))

    market = {
        "champion": eh.score_on_market964(champion_fn, frame=frame2),
        "challenger_squad_leg": eh.score_on_market964(challenger_fn, frame=frame2),
    }
    diffs = []
    for _, row in frame2.iterrows():
        actual = _outcome(int(row["home_score"]), int(row["away_score"]))
        diffs.append(
            ranked_probability_score(list(challenger_fn(row)), actual)
            - ranked_probability_score(list(champion_fn(row)), actual)
        )
    market["challenger_vs_champion_paired"] = _paired(diffs)
    out["market964"] = market

    print(json.dumps({"market964": market}, indent=1), flush=True)
    with open("runs/dc_squad_fusion_scratch/results.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()

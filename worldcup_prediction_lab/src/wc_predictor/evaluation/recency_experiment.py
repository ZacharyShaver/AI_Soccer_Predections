"""P5 recency experiment: does down-weighting old matches help Elo?

Runs several Elo variants through the same M6 walk-forward backtest window and
compares each to the full-history baseline with paired bootstrap CIs. Honest
verdict only — no cherry-picking.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pandas as pd

from wc_predictor.config import settings
from wc_predictor.evaluation.backtest import run_backtest
from wc_predictor.evaluation.metrics import bootstrap_ci
from wc_predictor.models.elo import EloModel
from wc_predictor.models.elo_windowed import WindowedEloModel

TRAIN_START = "1990-01-01"
FIRST_PREDICTION_DATE = "2010-01-01"
FINAL_PREDICTION_DATE = "2026-06-10"
PREDICTION_WINDOW_DAYS = 30
BOOTSTRAP_N = 1000
BOOTSTRAP_SEED = 20260622
BASELINE = "full_history_k20"

VARIANTS = {
    "full_history_k20": lambda: EloModel(k_factor=20),
    "low_k10": lambda: EloModel(k_factor=10),
    "high_k30": lambda: EloModel(k_factor=30),
    "high_k40": lambda: EloModel(k_factor=40),
    "window_8y": lambda: WindowedEloModel(window_years=8, k_factor=20),
    "window_4y": lambda: WindowedEloModel(window_years=4, k_factor=20),
    "window_2y": lambda: WindowedEloModel(window_years=2, k_factor=20),
}


def _ci(values):
    # Log loss can be +inf when a model rounds an actual outcome's probability to
    # zero on an extreme mismatch; drop non-finite values for the CI (RPS/Brier
    # are always finite, so the headline comparison is unaffected).
    finite = [v for v in values if math.isfinite(v)]
    point, lo, hi, n = bootstrap_ci(finite, n_boot=BOOTSTRAP_N, alpha=0.05, seed=BOOTSTRAP_SEED)
    return point, lo, hi, n


def run():
    matches = pd.read_parquet(settings.SILVER_DIR / "martj42_matches.parquet")
    tmp_root = settings.RUNS_DIR / "backtests" / "recency_tmp"

    results = {}
    for name, factory in VARIANTS.items():
        print(f"[recency] running {name} ...", flush=True)
        report = run_backtest(
            matches,
            model_factory=factory,
            train_start=TRAIN_START,
            first_prediction_date=FIRST_PREDICTION_DATE,
            final_prediction_date=FINAL_PREDICTION_DATE,
            prediction_window_days=PREDICTION_WINDOW_DAYS,
            model_id=name,
            runs_dir=tmp_root / name,
        )
        results[name] = {
            "rps": list(report.per_match_rps),
            "ll": list(report.per_match_log_loss),
            "brier": list(report.per_match_brier),
            "n": report.total_matches_predicted,
        }
        print(f"[recency] {name}: n={report.total_matches_predicted} rps={report.mean_rps:.4f}", flush=True)
    return results


def _format_report(results: dict) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    base = results[BASELINE]
    lines = [
        "# Recency experiment: does down-weighting old matches help Elo?",
        "",
        f"Walk-forward backtest (train_start {TRAIN_START}, predictions {FIRST_PREDICTION_DATE} "
        f"-> {FINAL_PREDICTION_DATE}, {PREDICTION_WINDOW_DAYS}-day windows). Lower is better. "
        f"Bootstrap 95% CIs, {BOOTSTRAP_N} resamples. Generated {generated}.",
        "",
        "## Per-variant metrics",
        "",
        "| Variant | n | RPS [95% CI] | H/D/A log loss [95% CI] | Brier [95% CI] |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for name, data in results.items():
        rps = _ci(data["rps"])
        ll = _ci(data["ll"])
        br = _ci(data["brier"])
        tag = " (baseline)" if name == BASELINE else ""
        lines.append(
            f"| {name}{tag} | {data['n']} | {rps[0]:.4f} [{rps[1]:.4f}, {rps[2]:.4f}] | "
            f"{ll[0]:.4f} [{ll[1]:.4f}, {ll[2]:.4f}] | {br[0]:.4f} [{br[1]:.4f}, {br[2]:.4f}] |"
        )

    lines += [
        "",
        f"## Paired comparison vs `{BASELINE}` (baseline minus variant; positive = variant better)",
        "",
        "| Variant | mean RPS diff [95% CI] | Verdict |",
        "| --- | --- | --- |",
    ]
    for name, data in results.items():
        if name == BASELINE:
            continue
        diffs = [b - v for b, v in zip(base["rps"], data["rps"])]
        point, lo, hi, _ = _ci(diffs)
        if lo > 0:
            verdict = "variant BETTER than baseline beyond noise"
        elif hi < 0:
            verdict = "variant WORSE than baseline beyond noise"
        else:
            verdict = "no difference beyond noise (CI spans 0)"
        lines.append(f"| {name} | {point:+.5f} [{lo:+.5f}, {hi:+.5f}] | {verdict} |")

    # plain-English conclusion
    better = []
    worse = []
    for name, data in results.items():
        if name == BASELINE:
            continue
        diffs = [b - v for b, v in zip(base["rps"], data["rps"])]
        _, lo, hi, _ = _ci(diffs)
        if lo > 0:
            better.append(name)
        elif hi < 0:
            worse.append(name)
    lines += [
        "",
        "## Conclusion (ship-of-Theseus hypothesis)",
        "",
        f"- Variants beating full-history Elo beyond noise: {better or 'none'}.",
        f"- Variants clearly worse: {worse or 'none'}.",
        "",
        (
            "The hard trailing-window variants test the literal hypothesis (discard matches older "
            "than N years). If they are no better — or worse — than full-history Elo, that supports "
            "keeping the full history: sparse international data needs the cross-linking, and Elo's "
            "K-factor already down-weights old results recursively."
        ),
        "",
    ]
    return "\n".join(lines)


def main():
    results = run()
    report = _format_report(results)
    out_path = settings.REPORTS_DIR / "backtests" / "recency_experiment.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"[recency] wrote {out_path}", flush=True)
    base = results[BASELINE]
    for name, data in results.items():
        rps = sum(data["rps"]) / len(data["rps"])
        diff = (sum(base["rps"]) / len(base["rps"])) - rps if name != BASELINE else 0.0
        print(f"  {name:<18} RPS {rps:.4f}  (vs baseline {diff:+.5f})", flush=True)


if __name__ == "__main__":
    main()

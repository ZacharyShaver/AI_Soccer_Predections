"""CLI for the walk-back experiment: build wells, screen recall, run models."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from wc_predictor.lab.walkback.harness import CONDITIONS, forecast_one
from wc_predictor.lab.walkback.linter import clean_well, well_ok
from wc_predictor.lab.walkback.llm import LMClient
from wc_predictor.lab.walkback.recall import recall_check
from wc_predictor.lab.walkback.universe import CUTOFF_DEFAULT, load_universe
from wc_predictor.lab.walkback.wells import build_well, load_well, save_well, well_path


def _existing_keys(out_path: Path) -> set[tuple[str, str, str]]:
    if not Path(out_path).exists():
        return set()
    keys = set()
    for line in Path(out_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        keys.add((str(r["match_id"]), str(r["model"]), str(r["condition"])))
    return keys


def run_batch(universe: pd.DataFrame, wells_root: Path, client: LMClient,
              condition: str, out_path: Path) -> dict:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    existing = _existing_keys(out_path)
    stats = {"done": 0, "skipped_existing": 0, "skipped_no_well": 0, "errors": 0}
    with out_path.open("a", encoding="utf-8") as fh:
        for _, row in universe.iterrows():
            key = (str(row["match_id"]), client.model, condition)
            if key in existing:
                stats["skipped_existing"] += 1
                continue
            well = None
            if condition in ("news", "both"):
                try:
                    well = load_well(str(row["match_id"]), wells_root)
                except Exception as exc:
                    print(f"  ERROR {row['match_id']}: corrupt well: {exc}")
                    stats["errors"] += 1
                    continue
                if well is None or not well_ok(well):
                    stats["skipped_no_well"] += 1
                    continue
            try:
                pred = forecast_one(row, well, condition, client)
            except Exception as exc:
                print(f"  ERROR {row['match_id']}: {exc}")
                stats["errors"] += 1
                continue
            fh.write(json.dumps(pred) + "\n")
            fh.flush()
            stats["done"] += 1
    return stats


def cmd_build_wells(args: argparse.Namespace) -> None:
    universe = load_universe(cutoff=args.cutoff)
    if args.limit:
        universe = universe.head(args.limit)
    root = Path(args.root)
    built = skipped = 0
    for _, row in universe.iterrows():
        if well_path(root, str(row["match_id"])).exists():
            skipped += 1
            continue
        well = clean_well(build_well(row))
        save_well(well, root)
        built += 1
        print(f"{row['match_id']}: kept {well['lint']['kept']} docs "
              f"({row['home_team']} v {row['away_team']})")
        time.sleep(args.sleep)
    print(f"built {built}, skipped existing {skipped}")


def cmd_recall(args: argparse.Namespace) -> None:
    universe = load_universe(cutoff=args.cutoff)
    client = LMClient(model=args.model)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n_bad = 0
    with out.open("w", encoding="utf-8") as fh:
        for _, row in universe.iterrows():
            try:
                res = recall_check(row, client)
            except Exception as exc:
                res = {"match_id": str(row["match_id"]), "contaminated": False,
                       "recalled": {"error": str(exc)}}
            n_bad += res["contaminated"]
            fh.write(json.dumps(res) + "\n")
    rate = n_bad / max(1, len(universe))
    print(f"contaminated: {n_bad}/{len(universe)} ({rate:.1%})")
    if rate > 0.15:
        print("WARNING: >15% contamination — move --cutoff later for this model.")


def cmd_run(args: argparse.Namespace) -> None:
    universe = load_universe(cutoff=args.cutoff)
    recall_path = Path(args.out).parent / f"recall_{args.model}.jsonl"
    if recall_path.exists():
        bad = {json.loads(l)["match_id"]
               for l in recall_path.read_text(encoding="utf-8").splitlines()
               if l.strip() and json.loads(l)["contaminated"]}
        universe = universe[~universe["match_id"].astype(str).isin(bad)]
        print(f"excluded {len(bad)} contaminated matches (recall screen)")
    client = LMClient(model=args.model)
    stats = run_batch(universe, Path(args.wells_root), client, args.condition, Path(args.out))
    print(stats)


def cmd_evaluate(args: argparse.Namespace) -> None:
    from wc_predictor.lab.walkback.evaluate import evaluate, write_report

    universe = load_universe(cutoff=args.cutoff)
    preds = [json.loads(l) for l in Path(args.preds).read_text(encoding="utf-8").splitlines()
             if l.strip()]
    results = evaluate(universe, preds)
    write_report(results, Path(args.report))
    print(json.dumps(results["ladder"], indent=1))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m wc_predictor.lab.walkback")
    sub = parser.add_subparsers(required=True)

    bw = sub.add_parser("build-wells", help="freeze GDELT wells for the universe")
    bw.add_argument("--cutoff", default=CUTOFF_DEFAULT)
    bw.add_argument("--root", default="runs/newswells")
    bw.add_argument("--limit", type=int, default=0)
    bw.add_argument("--sleep", type=float, default=5.0)  # GDELT hard-limits to 1 req/5s
    bw.set_defaults(func=cmd_build_wells)

    rc = sub.add_parser("recall", help="parametric-recall contamination screen")
    rc.add_argument("--model", required=True)
    rc.add_argument("--cutoff", default=CUTOFF_DEFAULT)
    rc.add_argument("--out", required=True)
    rc.set_defaults(func=cmd_recall)

    rn = sub.add_parser("run", help="run one model x condition over the universe")
    rn.add_argument("--model", required=True)
    rn.add_argument("--condition", choices=list(CONDITIONS), required=True)
    rn.add_argument("--cutoff", default=CUTOFF_DEFAULT)
    rn.add_argument("--wells-root", default="runs/newswells")
    rn.add_argument("--out", default="runs/analyst_walkback/preds.jsonl")
    rn.set_defaults(func=cmd_run)

    ev = sub.add_parser("evaluate", help="ladder + paired CIs + calibration report")
    ev.add_argument("--cutoff", default=CUTOFF_DEFAULT)
    ev.add_argument("--preds", default="runs/analyst_walkback/preds.jsonl")
    ev.add_argument("--report", default="reports/backtests/local_analyst_walkback.md")
    ev.set_defaults(func=cmd_evaluate)

    args = parser.parse_args(argv)
    args.func(args)

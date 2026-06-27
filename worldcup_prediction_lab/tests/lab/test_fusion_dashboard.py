"""Tests for the live fusion/tuning experiment dashboard."""

from __future__ import annotations

from wc_predictor.lab import fusion_dashboard as fd
from wc_predictor.lab.eval_harness import MARKET_BAR_RPS


def _exp(exp_id, task, market_rps, hist_rps=None, **extra):
    samples = {"market964": {"n": 964, "rps": market_rps}}
    if hist_rps is not None:
        samples["hist_15k"] = {"n": 15877, "rps": hist_rps}
    base = {
        "exp_id": exp_id,
        "agent": "claude",
        "task": task,
        "created_utc": "2026-06-27T18:00:00Z",
        "config": {"k_factor": 30.0},
        "samples": samples,
    }
    base.update(extra)
    return base


def test_distance_to_market_computed():
    exp = _exp("e1", "tune", 0.1560)
    assert fd._distance_to_market(exp) == round(0.1560 - MARKET_BAR_RPS, 10) or abs(
        fd._distance_to_market(exp) - (0.1560 - MARKET_BAR_RPS)
    ) < 1e-12


def test_cell_class_color_logic():
    # beats recalibrated market bar (0.1574) but not half-gap -> good
    assert fd._cell_class("market964", 0.1560) == "good"
    # closes >50% of the gap (<= 0.1535) -> gold
    assert fd._cell_class("market964", 0.1500) == "gold"
    # worse than baseline -> bad
    assert fd._cell_class("hist_15k", 0.1800) == "bad"
    # beats recalibrated on history -> good
    assert fd._cell_class("hist_15k", 0.1740) == "good"
    assert fd._cell_class("market964", None) == "na"


def test_best_per_task_picks_lowest():
    results = [
        _exp("a", "tune", 0.1570),
        _exp("b", "tune", 0.1540),
        _exp("c", "fuse", 0.1565),
    ]
    best = fd.best_per_task(results)
    assert best["tune"]["exp_id"] == "b"
    assert best["fuse"]["exp_id"] == "c"


def test_render_html_contains_rows_and_headline():
    results = [
        _exp("tune-1", "tune", 0.1555, hist_rps=0.1743),
        _exp("mkt-1", "market_base", 0.1499, hist_rps=None,
             vs_market_paired={"mean_diff": 0.0003, "ci95": [-0.002, 0.003], "excludes_0": False}),
    ]
    out = fd.render_html(results)
    assert "tune-1" in out
    assert "mkt-1" in out
    assert "market bar" in out
    assert f"{MARKET_BAR_RPS:.4f}" in out


def test_build_writes_both_files(tmp_path):
    out = tmp_path / "research" / "fusion_dashboard.html"
    pages = tmp_path / "docs" / "fusion.html"
    results = [_exp("e1", "tune", 0.1560, hist_rps=0.1743)]
    fd.build(results=results, out_path=out, pages_path=pages)
    assert out.exists() and pages.exists()
    assert out.read_text(encoding="utf-8") == pages.read_text(encoding="utf-8")
    assert "e1" in out.read_text(encoding="utf-8")


def test_render_empty_ledger():
    out = fd.render_html([])
    assert "No experiments recorded yet" in out

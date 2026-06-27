# Model tuning + market-as-base — session report (2026-06-27)

Science day: how close can our statistical models get to **live betting** (the de-vigged
market)? Three thrusts — (1) tune top models [Claude], (2) fuse models [Codex], (3) train
stat models that take a market prediction as input [Claude]. This report covers **Task 1 and
Task 3 (Claude's lanes)**. Task 2 (fusion) is owned by Codex; its results land in the shared
`runs/fusion/` ledger and on the live dashboard (`docs/fusion.html`).

All numbers are RPS (Ranked Probability Score, lower is better), scored by the shared
`wc_predictor.lab.eval_harness`, which reproduces the established bars exactly (pinned by
tests): **history 0.1745 / WC-60 0.1719 / market-964 0.1574**, market bar **0.1496**.

Significance = paired bootstrap CI (1000 resamples, seed 20260627) excluding 0.

---

## The bars (ground truth)

| Sample | baseline Elo | **elo_recalibrated** | de-vigged market |
| --- | ---: | ---: | ---: |
| 15.8k history (2010+) | 0.1762 | **0.1745** | n/a |
| WC-60 backtest | 0.1763 | **0.1719** | n/a |
| 964-match market join | 0.1574 | **0.1574** | **0.1496** |

Promotion bar (Task 1): improves 15.8k history with a paired 95% CI excluding 0 **AND** does
not regress WC-60. Prefer the larger sample; anything that helps WC-60 but hurts history is
overfit (the codebase's #1 trap).

---

## Task 1 — Tune top models (6 passes, ~100 configs)

Each pass swept on the 15.8k history sample (the generalization sample); the best config of
each pass was then fully scored on all three samples and recorded to the ledger.

| Pass | Lever | Best config | hist | WC-60 | mkt | paired vs recal (hist) | verdict |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| 1 | K × draw_base × draw_scale | K32 db0.33 ds500 | 0.1744 | 0.1720 | 0.1573 | +0.00007 [−0.00001, +0.00014] | tie (CI spans 0) |
| 3 | margin-of-victory × K | mov=sqrt K28 | 0.1744 | 0.1721 | 0.1569 | +0.00010 [−0.00006, +0.00025] | tie (CI spans 0) |
| 4 | rating_scale × home_adv | scale400 HA85 | 0.1743 | **0.1723** | 0.1576 | +0.00014 [+0.00003, +0.00025] | sig on hist **but regresses WC-60** |
| 5 | tournament weights | flat (= recal) | 0.1745 | 0.1719 | 0.1574 | +0.00000 | flat is optimal |
| 7 | draw functional form | exp, db0.33 (= recal) | 0.1745 | 0.1719 | 0.1574 | +0.00000 | `exp` beats logistic/linear |
| 8 | recency (shrink-to-mean) | shrink=off (= recal) | 0.1745 | 0.1719 | 0.1574 | +0.00000 | **shrinkage hurts** |

### Findings

- **The plateau holds. Nothing was promoted.** The only config that is statistically
  significant on history is Pass-4 `scale400 HA85` (+0.00014, CI excludes 0) — but it is a
  trivial **0.08%** gain *and it regresses WC-60* (0.1719 → 0.1723), so it fails the promotion
  bar. Every other pass ties recalibrated within bootstrap noise.
- **Structural levers re-confirmed:** flat tournament weights (Pass 5), the `exp` draw-mass
  form (Pass 7), and the log-damped MoV multiplier (turning MoV `off` costs ~0.0013 RPS) are
  all already optimal in `elo_recalibrated`. Lowering the rating scale / nudging home advantage
  trades a hair of history RPS for a WC-60 regression — the overfit signature.
- **Recency shrinkage is actively harmful** (Pass 8): regressing ratings toward the mean
  between matches monotonically worsens history RPS (half-life 365d → 0.2023, 730d → 0.1946,
  1460d → 0.1874, 2920d → 0.1816, off → 0.1745). This is the same lesson P5 found with hard
  recency windows — discarding accumulated rating information destroys discrimination.

**Conclusion (Task 1):** pure-Elo reparameterization is exhausted. Across now *four* sweep
rounds it plateaus at ~+1.1% over baseline, and this session's joint grids add nothing
promotable. `elo_recalibrated` remains the champion. A further jump needs new **signal**, not
new constants — which is exactly what Task 3 probed.

---

## Task 3 — Market-as-base stat models

Premise: instead of predicting from ratings, take a **market prediction as input** and learn a
better-calibrated output. We already proved a linear Elo+market blend just picks the market
(λ=1), so this explores calibration and non-linear corrections on the 964-match join. Heavy
overfit risk at n=964, so every model is scored **out-of-fold** with a leak-free, time-ordered
**expanding-window walk-forward** (6 blocks; first ~160 rows un-scored) and compared to **pure
de-vigged market on exactly the same held-out rows**, with a paired CI.

On the held-out rows the pure market scores **RPS 0.1403** (the OOF subset is the later,
better-priced matches, so it is sharper than the full-sample 0.1496 — the comparison is
apples-to-apples because every model is scored on the same rows).

| Exp | Model | OOF RPS | vs pure market | verdict |
| --- | --- | ---: | --- | --- |
| M3.1 | market^t (temperature, fit t) | **0.1400** | −0.00034 [−0.00136, +0.00064] | **tie** (best point estimate) |
| M3.4 | market^a · elo^b (log-linear pool) | 0.1404 | +0.00011 [−0.00094, +0.00120] | tie (collapses to ≈pure market) |
| M3.2b | softmax(market only) recalibration | 0.1409 | +0.00053 [−0.00098, +0.00195] | tie |
| M3.3 | market-anchored Elo gap (fit w) | 0.1420 | +0.00164 [+0.00042, +0.00293] | **worse (sig)** |
| M3.2 | softmax(market + Elo gap + neutral) | 0.1430–0.1435 | +0.0026…+0.0031 [excl 0] | **worse (sig)** at every L2 |

### Findings

- **Nothing beats the pure de-vigged market out-of-fold.** The closest is **M3.1 temperature
  calibration** (`p ∝ market^t`): it nudges the point estimate to 0.1400 vs 0.1403, confirming
  the market is very slightly **under-confident** (fit t > 1), but the paired CI spans 0 — not
  significant. A single global temperature is the only correction that doesn't hurt.
- **Adding context significantly *worse*.** M3.2 (market logits + Elo rating gap + neutral
  flag) overfits at every regularization strength and loses to raw market by a significant
  margin. The Elo gap carries no information the market hasn't already priced — consistent with
  the λ=1 blend and the failed distillation experiment. M3.3 (anchoring Elo's gap to the
  market-implied gap) is likewise significantly worse: routing market info through Elo's draw
  model strictly degrades it.
- **The log-linear pool collapses to pure market** (a≈1, b≈0), echoing the linear-blend result
  on a 5× larger, less-biased sample.

**Conclusion (Task 3):** on priced matches the market is **efficient** — our statistical models
cannot extract a significant correction from the information Elo sees. This is the scientific
result, not a failure: *the market's edge is per-match information (injuries, lineups, late
money) that ratings cannot represent.* Our value is therefore **coverage** (Elo forecasts the
~49k matchups with no tradeable odds, including the unplayed bracket matchups the sim needs)
plus the **live overlay** that swaps in the market wherever odds exist — exactly the settled
architecture.

---

## North-star scorecard

> Close the **0.1574 → 0.1496** gap to the market on held-out data.

- **Task 1 (tuning):** moved the gap on the 964 join essentially not at all (best tuned config
  0.1569–0.1576). Pure-Elo tuning cannot close it — confirmed.
- **Task 3 (market-as-base):** the only thing that reaches the market is *using the market
  itself*, optionally with a non-significant temperature nudge. We did **not** beat it, and we
  proved why: the residual gap is irreducible per-match information, not a calibration error.
- **Honest verdict:** we got as close as the market itself (a tie via temperature) but could
  not significantly surpass it. The remaining gap on the full sample is real and is **not**
  recoverable from ratings — it is the market pricing things Elo never sees.

## Reproducibility

Bars and all scoring via `wc_predictor.lab.eval_harness` (tests pin the bars). Per-experiment
results in the shared `runs/fusion/` ledger (gitignored); the live dashboard renders them at
`docs/fusion.html`. Sweep scripts were run analytically and are not committed (project
convention), the same as the round-1/2/3 sweeps; their findings are captured here.

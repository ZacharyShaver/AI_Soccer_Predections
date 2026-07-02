# New model class: online Dixon-Coles Poisson attack/defense rating

Generated: `2026-06-30T20:15:00Z`

Every prior variant in this lab (`elo_baseline`, `elo_recalibrated`, all the
`*_form` challengers) is an `EloModel` subclass: it scores match *outcomes*
directly via a win-probability update. This session tried a genuinely
different model class instead: **Dixon & Coles (1997)**, which scores
*goals*. Each team carries an attack rating and a defense rating in
log-goal-rate space; expected goals are `exp(baseline + attack_home -
defense_away + home_edge)` (mirrored for away); match outcomes are derived by
summing a bivariate-Poisson scoreline grid, with the Dixon-Coles low-score
correction `tau(x, y)` for the 0-0/1-0/0-1/1-1 cells. Implementation:
`src/wc_predictor/models/dixon_coles.py`.

The one departure from the textbook version: Dixon-Coles is normally fit by
batch MLE over the whole history. This project's online history harness
predicts-then-updates one match at a time, so ratings here update via a
single Poisson-regression gradient step per match instead of a full refit —
the same online contract Elo already satisfies, just with a goal-count
likelihood in place of a win-probability likelihood. `rho` is a fixed
hyperparameter rather than jointly fit (the literature value moves little,
and online-fitting one global scalar wasn't worth the extra moving part).

Two variants: `dixon_coles_poisson` (untuned defaults) and
`dixon_coles_tuned` (coarse coordinate-descent sweep). Sweep scripts under
`runs/dixon_coles_scratch/` — not committed, same convention as prior
sweep/distill scratch scripts this project has used.

## Headline: untuned already ties Elo, tuned beats it

| Sample | n | elo_recalibrated RPS | dixon_coles (untuned) | dixon_coles_tuned |
| --- | ---: | ---: | ---: | ---: |
| History (2010-01-01+, online walk-forward) | 15,893 | 0.1744 | 0.1749 | **0.1726** |
| Live WC-2026 (played so far, leak-free) | 75 | 0.1593 | **0.1530** | 0.1603 |
| Market964 (martj42 ∩ Football-Data odds) | 964 | 0.1574 | 0.1576 | **0.1560** |
| Market964 vs de-vigged market | 964 | 0.1496 (market) | — | 0.1496 (market) |

Paired bootstrap 95% CI (1,000 resamples, seed 20260630), dixon_coles_tuned
minus elo_recalibrated, same match order:

- **History**: mean diff **-0.00178**, CI **[-0.00244, -0.00104]** — EXCLUDES
  0. Dixon-Coles wins on 8,062/15,893 matches (50.7%). This is the
  generalization sample this project treats as the real bar.
- **Market964 vs market**: mean diff +0.00637, CI [+0.00249, +0.01008] —
  EXCLUDES 0, i.e. dixon_coles_tuned still loses to the market, same as every
  model tried so far (expected, not a regression).
- **Live WC-2026 (n=75)**: tuned moved from 0.1530 (untuned) to 0.1603, a
  ~0.001 RPS move against elo_recalibrated's 0.1593. At n=75, flipping a
  single match's classification swings RPS by roughly 0.013, so this is noise,
  not a real regression — but it's also not evidence the tuning transfers to
  the live tournament specifically. Flagged honestly, not hidden.

## What the sweep found

Coarse 3-round coordinate descent on history RPS only (`runs/dixon_coles_scratch/sweep.py`):

1. `learning_rate=0.03, shrinkage=0.0002` (slower, more stable online updates
   than the untuned default beat faster/less-regularized configs).
2. `rho=-0.05` (a small low-score correction; the textbook Dixon-Coles value
   is around -0.13, this data prefers a smaller one).
3. `home_edge_init=0.32, home_edge_learning_rate=0.0` — **the biggest single
   lever**. The home-advantage term should be a FIXED constant, never
   nudged by the per-match online update. This mirrors Elo's own finding:
   `home_advantage` is a tuned constant, not something the K-factor update
   touches.

Only a coarse grid was swept (not a full optimizer); a finer/randomized
search past this is a plausible next step (see "not yet tried" below).

## Why this matters more than another Elo reparameterization

The prior session established a ceiling: pure Elo reparameterization
plateaus at about +1.1% RPS across three sweep rounds, and closing more of
the gap to the market (~7%) needs new signal, not more constant-tuning
(`reports/backtests/market_blend.md`, `market_distillation.md`). An untuned
new model class landing at statistical parity with a 3-round-tuned Elo, then
a *coarse* one-round sweep pushing it to a significant win — is a different
kind of gain: it comes from the model's structure (goals, not outcomes;
explicit attack/defense split per team) rather than from squeezing more out
of Elo's existing knobs. That's exactly the "new signal" the prior ceiling
finding said was needed.

## Not yet tried (backlog, in rough priority order)

- **Finer/randomized sweep** past this coarse coordinate-descent grid —
  the 3-round search only explored 5 params one axis pair at a time; a joint
  random or Bayesian search could plausibly do better.
- **Fusing `dixon_coles_tuned` with `elo_recalibrated`** (linear/log pool,
  same recipes as the prior fusion session) — since the two now have
  genuinely different match-level errors (each wins ~50% of individual
  matches on history despite dixon_coles' better mean), an ensemble of the
  two might beat either alone even though ensembling two *Elo* variants
  didn't help (they were too correlated).
- **Jointly fitting `rho` online** instead of leaving it fixed.
- **Pi-ratings** (Constantinou & Fenton 2013) — asymmetric home/away rating
  updates, a second literature-backed Elo alternative not yet tried.
- **Bradley-Terry-Davidson** — explicit paired-comparison draw parameter,
  as an alternative to both Elo's draw heuristic and Dixon-Coles' implicit
  draw-via-scoreline-grid.

## Honesty caveats

- Only a coarse grid was swept; this is not a claim of a global optimum.
- The live-WC sample is tiny (n=75) and noisy; the history sample is the
  real generalization bar per this project's established convention.
- `rho` is fixed, not jointly fit — a genuine simplification vs textbook
  Dixon-Coles, documented as such in the model docstring.
- The variant registry auto-discovers `lab/variants/*.py`, so both variants
  already run in the daily `run_experiments`/dashboard rotation (at n=0 until
  their live predictions resolve). The fusion-ledger sweep has NOT been run
  on them yet — that (fusing with `elo_recalibrated`) is the queued next step.
- Review + integration (Claude, 2026-07-02): tests rerun (11 pass; full suite
  238 pass + the 2 pre-existing eval-harness sample-drift failures), and
  `verify_best.py` rerun on current silver (n grew 15,893→15,899): paired
  diff -0.00177, CI [-0.00243, -0.00103], still excludes 0. Claims reproduce.

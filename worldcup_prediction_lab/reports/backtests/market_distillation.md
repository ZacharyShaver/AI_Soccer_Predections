# Market distillation experiment (one-time): can the market teach Elo?

Date: 2026-06-26. Question: instead of tuning Elo to match *outcomes*, can we
tune it to mimic the de-vigged market (a less-noisy label) and get a config that
**generalizes** to matches the market never priced?

Method: starting from the outcome-tuned `elo_recalibrated` config, vary each
calibration knob and pick the value that minimizes cross-entropy to the market
on the 964 leak-free priced matches. Then test whether that "market-preferred"
config scores better RPS-vs-ACTUAL-OUTCOMES on the held-out 15.8k-match history.

## What the market pulls each knob toward (min cross-entropy to market)

| Knob | recalibrated | market prefers | direction |
| --- | --- | --- | --- |
| rating_scale (conf.) | 400 | **600** | much less confident |
| home_advantage | 75 | 55 | lower |
| draw_base_probability | 0.33 | 0.27 | lower |
| draw_rating_scale | 600 | 400 | tighter |
| k_factor | 30 | 20 | slower |

Cross-entropy to market: recalibrated 0.9765 -> market-distilled **0.8932**.
So the distilled config really is closer to the market's probabilities.

## The generalization test (decisive)

RPS vs actual outcomes on the 15.8k-match walk-forward (lower = better):

| Config | tuned on | RPS | log loss | Brier |
| --- | --- | ---: | ---: | ---: |
| baseline | — | 0.1762 | 0.9005 | 0.5287 |
| recalibrated | actual outcomes (15.8k) | **0.1745** | 0.8824 | 0.5227 |
| market-distilled | market probs (964) | 0.1805 | 0.9238 | 0.5394 |

**The market-distilled config is the WORST predictor — below even baseline.**

## Verdict: do not distill

Tuning Elo to mimic the market produces a config that matches the market better
but predicts outcomes worse on the broad population. The dominant lesson the
market "teaches" is to be much less confident (rating_scale 400->600); that
matches the market's average sharpness on the 964 *priced* matches, which are
disproportionately close/competitive games. Applied to the full population --
which is full of lopsided mismatches where Elo should be confident -- the
softening discards real discrimination and RPS degrades.

The market's edge over Elo is therefore NOT a calibration Elo can copy. It is
(1) per-match information Elo's inputs do not contain (injuries, lineups, late
money) and (2) a non-representative match selection. This is the same reason the
linear blend picks lambda=1 (the models are not complementary; the market just
dominates where it exists).

Settled architecture:
- Keep Elo tuned on **outcomes** (ground truth) for universal coverage,
  including the unplayed/hypothetical matchups the bracket simulation needs.
- Use the de-vigged **market as a direct overlay** where tradeable odds exist.
- **Do not** retrain/tune Elo against market probabilities.

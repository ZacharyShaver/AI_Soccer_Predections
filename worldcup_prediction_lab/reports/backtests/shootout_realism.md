# Knockout realism: penalty shootouts are coin flips — sim fixed

Generated: `2026-07-02`

The Monte-Carlo knockout resolution (`simulate/match_sim.py`) advanced the
stronger side of a drawn tie with probability
`prob_home / (prob_home + prob_away)` — documented at the time as a middle
ground whose effect was assumed second-order. This session measured it.

## Evidence: 561 historical shootouts, leak-free pre-match ratings

martj42 publishes a companion `shootouts.csv` (680 rows; 598 resolve to our
canonical team ids, 561 join a drawn silver match with pre-match ratings from
a single online walk of the recalibrated Elo — no leakage, each rating uses
only matches strictly before the shootout). martj42 scores include extra
time, so a drawn knockout row + a shootout entry = the match went to pens.

| Question | Answer |
| --- | --- |
| Stronger side's actual shootout win rate | **51.0%** (286/561) |
| Wilson 95% CI | **[46.9%, 55.1%]** — includes 50% |
| Favourites with ≥100 Elo gap (n=229) | 53.7%, CI [47.2%, 60.1%] — still includes 50% |
| What the sim assumed on those same matches | **68.0%** mean advance rate |

Shootouts are statistically indistinguishable from coin flips, even for big
favourites. The old rule handed favourites a ~17-point advance bonus every
time a tie went to pens, compounding across up to five knockout rounds.

## The fix

`home_advance_probability` is now `prob_home + 0.5 * prob_draw` (drawn tie →
coin flip). Regression test pins the formula; the probe lives in
`runs/shootout_scratch/` (scratch, uncommitted) with the full per-shootout
join saved to `probe.json`.

## Effect on championship odds (20k sims, as-of 2026-07-02)

Favourites take the expected haircut; the table compresses:

| Team | Champion (old rule, 07-02 morning) | Champion (coin-flip pens) |
| --- | ---: | ---: |
| Argentina | 28.4% | **22.9%** |
| Spain | ~16% | 15.2% |
| France | ~13.5% | 13.1% |
| Brazil | ~7% | 7.7% |

(Old-rule numbers from the morning standings refresh; mid-table teams gain
correspondingly. Group-stage and decisive-knockout modelling are untouched —
only the went-to-pens branch changed.)

## Caveats

- The 82 unresolved shootout rows are pre-alias-era obscure teams; no reason
  to expect selection bias toward either hypothesis.
- `match_congestion`'s group→knockout rest-gap hypothesis (the other half of
  the knockout-mechanics task) is now measurable in the live bake-off — it
  carries knockout predictions at the compressed-calendar rest gaps it was
  designed for; its leaderboard row is the running answer.

# Plan P4: Tournament Simulation → Championship Odds

> Bite-sized, Codex-executable slices built on the **completed P3 Elo model**.
> One task per Codex session. Codex does NOT run git — Claude verifies and commits (see `co-op.md`).

## Scope and goal

Turn the proven Elo model into **tournament-level probabilities**: simulate the rest of the 2026
World Cup thousands of times and report each team's probability of advancing from the group, reaching
each knockout round, and **winning the World Cup**. Deterministic (fixed seed), as-of-aware (uses
results already played), and honest about uncertainty.

This consumes the P3 components (Elo model, silver matches/fixtures) and produces a championship-odds
report. No new external data.

## Inputs

- `data/silver/martj42_matches.parquet` — training history + the WC group matches already played.
- `data/silver/openfootball_worldcup_2026_fixtures.parquet` — group fixtures + knockout bracket
  structure with placeholder slots (`1A`, `2B`, `3A/B/C/D/F`, `W74`, `L101`, …).
- `src/wc_predictor/models/elo.py` (`elo_poisson_v1`, `predict_scoreline`, host hook).

## Design constraints (locked)

1. **As-of aware.** Train Elo through the latest completed-result date; already-played group results
   are FIXED (not re-simulated). Record `training_cutoff`/`as_of` in the run metadata + report.
2. **2026 format.** 12 groups of 4. **Top 2 per group + 8 best third-placed** = 32 → Round of 32 →
   R16 → QF → SF → Final (+ third-place playoff). The 8-best-thirds allocation to specific R32 slots
   follows constraints encoded in openfootball's `3A/B/C/D/F`-style slot lists.
3. **Group tiebreakers (FIFA order):** points → goal difference → goals scored → head-to-head
   (points, then GD, then goals among tied teams) → (fair-play / drawing of lots last). Implement
   the deterministic statistical portion; for true ties beyond that, break deterministically by a
   stable rule (e.g. canonical_team_id) and note it.
4. **Knockout = no draws.** A knockout tie resolves to a single winner. Use Elo win probability
   conditional on "not a draw" (re-normalize home/away from the M4/M5 outputs, or model extra-time +
   penalties as ~50/50 when tied). Document the choice.
5. **Determinism.** Fixed RNG seed; N simulations explicit; re-running yields identical odds. Host
   advantage via the M7 venue→host logic (USA/CAN/MEX at home).
6. **Honesty.** Report is Elo-only (the proven bar), not market-calibrated; small-sample tournament
   variance is large — present odds as distributions, not certainties.

## Outputs

- `src/wc_predictor/simulate/standings.py` — group standings + tiebreakers (+ tests).
- `src/wc_predictor/simulate/bracket.py` — third-place allocation + slot resolution (+ tests).
- `src/wc_predictor/simulate/montecarlo.py` — the simulation engine (+ tests).
- `reports/backtests/championship_odds_<as_of>.md` — the championship-odds report.

---

## Task S0: Group standings + tiebreakers

**Files:** `src/wc_predictor/simulate/standings.py`, `tests/simulate/test_standings.py`.

- [ ] **Step 1: Tests first**

Synthetic group of 4 with known results → assert points, GD, goals-scored, and the FIFA tiebreaker
ordering (incl a head-to-head case and a GD-vs-goals case). Assert deterministic final ordering even
under a full tie.

- [ ] **Step 2: Implement standings**

`compute_group_table(group_matches_df)` → ordered standings with points, GD, GF, GA, and rank.
Apply FIFA tiebreaker order; break residual ties deterministically (stable, documented). Works with a
mix of played + simulated results (it just takes scored matches).

- [ ] **Step 3: Run tests; Claude commits.**

---

## Task S1: Third-place allocation + bracket resolution

**Files:** `src/wc_predictor/simulate/bracket.py`, `tests/simulate/test_bracket.py`.

- [ ] **Step 1: Tests first**

Given 12 group tables (winners/runners-up/thirds), assert: 24 auto-qualifiers + the **8 best
third-placed** are selected by the cross-group ranking (points → GD → GF → …); and that the 8 thirds
are assigned to R32 slots respecting each slot's candidate-group constraints (from openfootball's
`3A/B/C/D/F` lists) with no group used twice / no same-group rematch where the format forbids it.

- [ ] **Step 2: Implement allocation**

Parse the knockout slot constraints from the openfootball fixtures (`home_slot`/`away_slot`). Rank the
12 third-placed teams, take the top 8, and assign them to the third-place R32 slots. **Prefer the
official FIFA 2026 third-place allocation table if Codex can source it reliably; otherwise implement a
constraint-satisfying bipartite assignment** (each qualifying third → a slot whose candidate-group
list contains its group, each slot filled once) and DOCUMENT it as an approximation. Then resolve all
R32 pairings (1X/2Y/3Z → concrete teams). **If the official table vs approximation choice is unclear,
STOP and log it for Claude.**

- [ ] **Step 3: Run tests; Claude commits.**

---

## Task S2: Single-match knockout simulator

**Files:** extend `src/wc_predictor/simulate/montecarlo.py` (helpers) or a small module,
`tests/simulate/test_knockout_match.py`.

- [ ] **Step 1: Tests first**

Assert a knockout sim returns exactly one winner; the stronger Elo team wins more often over many
seeded draws; neutral/host logic respected; deterministic under a fixed seed.

- [ ] **Step 2: Implement**

`simulate_match(model, home, away, neutral, host_fn, rng)` for group games returns a sampled
scoreline (from `predict_scoreline`); `simulate_knockout(...)` returns a single winner (re-normalize
draw mass to the two sides, or model ET/penalties as 50/50 when the sampled result is a draw —
document). Pure-ish, RNG injected for determinism.

- [ ] **Step 3: Run tests; Claude commits.**

---

## Task S3: Monte Carlo engine

**Files:** `src/wc_predictor/simulate/montecarlo.py`, `tests/simulate/test_montecarlo.py`.

- [ ] **Step 1: Tests first**

On a tiny synthetic tournament with a deterministic/degenerate model (one team always wins), assert
that team wins 100% and probabilities sum correctly per round; assert reproducibility (same seed →
identical tallies); assert already-played results are held fixed.

- [ ] **Step 2: Implement engine**

`run_tournament_simulation(model, matches, fixtures, n_sims, seed, as_of)`: for each sim — fix played
group results, simulate remaining group games (S2) → group tables (S0) → bracket (S1) → knockouts
(S2) to a champion. Tally per team: P(advance from group), P(reach R16/QF/SF/Final), P(win WC). Fixed
seed; N configurable (default e.g. 20000). Returns a results table.

- [ ] **Step 3: Run tests; Claude commits.**

---

## Task S4: Championship-odds report

**Files:** `src/wc_predictor/simulate/run_championship_odds.py` (CLI),
`reports/backtests/championship_odds_<as_of>.md`.

- [ ] **Step 1: Run the live simulation**

Train Elo through the latest completed result; run `run_tournament_simulation` with the real fixtures
and N (e.g. 20000), seed fixed. Capture as_of/training_cutoff, n_sims, seed.

- [ ] **Step 2: Write the committed report**

Table sorted by P(win WC): team, group, Elo rating, P(advance), P(QF), P(SF), P(Final), P(Win). Note
methodology (Elo-only, the proven bar; bracket allocation method; ET/penalties handling), as-of, and
the honesty caveat (tournament variance is large; favorites rarely exceed ~20–25% to win). Note any
already-eliminated/qualified teams given results so far.

- [ ] **Step 3: Determinism check + commit.** Re-run a small N twice → identical tallies.

---

## Definition of done for P4

- Standings + tiebreakers, third-place allocation + bracket resolution, knockout sim, and Monte Carlo
  engine — each tested; full suite green.
- A committed `championship_odds_<as_of>.md` with per-team win/round probabilities, methodology, and
  honesty caveats.
- Deterministic (fixed seed → identical odds). No secrets; sim run artifacts gitignored.
- co-op.md log updated; Claude reviews before P5.

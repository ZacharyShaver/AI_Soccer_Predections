# New signal class: Transfermarkt squad value (first non-scoreline feature to clear the bar)

Generated: `2026-07-02`

Every strength signal in this lab so far was derived from historical
scorelines (Elo ratings, goal-based Dixon-Coles ratings, last-5 form windows).
The edge-hunt session established that the market's remaining ~5% RPS edge is
genuine team-strength information, not calibration — so the frontier is data
the scorelines don't contain. This lane adds the first such signal: **squad
market value** from [transfermarkt-datasets](https://github.com/dcaribou/transfermarkt-datasets)
(CC0-1.0, weekly refresh, dated player valuations 2004 → June 2026).

## Pipeline

- `data/ingest_transfermarkt.py`: pulls `player_valuations` (656k dated rows,
  41.5k players) + `players` (citizenship) from the hosted DuckDB file and
  builds a MONTHLY per-team series: squad value at each month-end = sum of the
  **top-15** citizen player values holding a valuation dated within **730
  days** (retired players expire instead of persisting forever). Silver:
  `transfermarkt_squad_values.parquet` — 41,215 rows, **184 teams** (14 new
  `transfermarkt` alias rows added: South Korea, Czechia, Türkiye, Ivory
  Coast, Bosnia, The Gambia, ...). DQ report:
  `reports/data_quality/transfermarkt_squad_values.md`.
- `lab/variants/squad_value.py`: recalibrated Elo +
  `clip(10 * ln(V_home / V_away), ±80)` using each side's latest monthly value
  **strictly before** the match date (published pre-match — leak-free by
  construction). Either side missing (or < 5 valued players) → no delta, i.e.
  plain `elo_recalibrated`. The delta applies on neutral ground too (it is a
  strength differential, not a venue effect).

## Result: beats `elo_recalibrated` on all three standard samples

| Sample | n | elo_recalibrated | squad_value |
| --- | ---: | ---: | ---: |
| History 2010+ walk-forward (in-walk) | 15,899 | 0.17438 | **0.17414** |
| Played WC-2026 (leak-free per-date refit) | 76 | 0.15945 | **0.15878** |
| market964 (odds join) | 964 | 0.15736 | **0.15694** |
| market964 vs de-vigged market | 964 | 0.14958 (market) | still loses, like every model |

Significance (paired bootstrap, 1,000 resamples):

- **Out-of-fold** (the promotion test): (coef, cap) chosen per time block only
  on earlier blocks (6 blocks, n=13,249 scored out-of-fold): mean diff
  **-0.00033**, CI **[-0.00048, -0.00017]** — EXCLUDES 0.
- **True in-walk** with the deployed class (delta also feeds rating updates),
  frozen config, full 15,899: mean diff **-0.00024**, CI
  **[-0.00032, -0.00014]** — EXCLUDES 0; better on 9,082/15,899 (57.1%).
- **Covered subsample** (both teams valued — 59.3% of matches): mean diff
  **-0.00054**, CI [-0.00078, -0.00029] — the effect lives where the data
  exists, as it should.

The coefficient grid is well-behaved: the optimum is small (10 Elo per unit
log-value-ratio ≈ +11 Elo for a 3× value gap), and RPS degrades monotonically
past coef 20 — a real small signal Elo hadn't fully priced, not a knob
artifact. Selection path across blocks was stable (coef 10 in every block
after the first).

## Honest caveats

- Effect size ~0.14% relative RPS — same order as the dc_elo_fusion gain.
  This does not close the market gap (~4.7%); it chips at it with the first
  independent data source.
- Citizenship approximates the talent POOL, not the selected 26-man roster.
- Valuations are crowd estimates and thin before ~2007; coverage is 59% of
  the 2010+ eval window (uncovered matches fall back to elo_recalibrated).
- The silver table refreshes only when the ingestion is rerun (upstream is
  weekly); a stale table degrades gracefully toward plain recalibrated Elo.
- Ledger entry: `runs/fusion/claude__squad_value__*.json`; scratch scripts
  under `runs/squad_value_scratch/` (not committed, per convention).

## Next steps queued

- Stack the delta under `dc_elo_fusion`'s Elo constituent (the current
  history champion) — the two gains are plausibly additive but unproven.
- The same source has per-player injury-ish signals (`last_season`,
  appearances) that could proxy availability — a future rung.

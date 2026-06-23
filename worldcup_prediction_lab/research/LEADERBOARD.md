# Daily Model-Research Leaderboard

Generated: `2026-06-23T22:34:03Z`

Each variant is scored on its most-informed pre-kickoff prediction per match (latest as_of). Lower RPS is better. `Edge` = baseline RPS - variant RPS (positive = beats the baseline). Every challenger must beat **elo_baseline**.

- Total scored predictions across variants: 16
- Registered variants: 4

| Rank | Variant | n | RPS | log loss | Brier | Decisive acc | Edge vs baseline |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `scoring_form` | 4 | 0.0968 | 0.4715 | 0.2267 | 1.000 | +0.0154 |
| 2 | `recent_form` | 4 | 0.1021 | 0.4899 | 0.2386 | 1.000 | +0.0101 |
| 3 | `elo_baseline` (baseline) | 4 | 0.1122 | 0.5230 | 0.2612 | 1.000 | +0.0000 |
| 4 | `rest_days` | 4 | 0.1122 | 0.5230 | 0.2612 | 1.000 | +0.0000 |

## Variants

- `scoring_form` — Elo + attacking form from last-5 goal difference.  
  feature: average goal difference (scored minus conceded) over each team's last 5 matches.
- `recent_form` — Elo + short-window momentum from last-5 match results.  
  feature: average result (win=1, draw=0.5, loss=0) over each team's last 5 matches.
- `elo_baseline` — Plain host-aware Elo (K=20) — the bar (walk-forward RPS 0.1776).  
  feature: none (control)
- `rest_days` — Elo + rest/fatigue: more days since last match = small Elo bump.  
  feature: rest days since each team's previous match (cap 14d); short rest penalized.

## Caveats

- Small in-tournament samples: a few matches can swing RPS. Don't over-read early standings.
- Challengers are falsification rungs: they earn their place only by beating the baseline out-of-sample.

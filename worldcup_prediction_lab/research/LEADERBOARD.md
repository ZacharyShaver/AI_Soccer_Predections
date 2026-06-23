# Daily Model-Research Leaderboard

Generated: `2026-06-23T02:01:42Z`

Each variant is scored on its most-informed pre-kickoff prediction per match (latest as_of). Lower RPS is better. `Edge` = baseline RPS - variant RPS (positive = beats the baseline). Every challenger must beat **elo_baseline**.

- Total scored predictions across variants: 0
- Registered variants: 4

| Rank | Variant | n | RPS | log loss | Brier | Decisive acc | Edge vs baseline |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `elo_baseline` (baseline) | 0 | n/a | n/a | n/a | n/a | n/a |
| 2 | `recent_form` | 0 | n/a | n/a | n/a | n/a | n/a |
| 3 | `rest_days` | 0 | n/a | n/a | n/a | n/a | n/a |
| 4 | `scoring_form` | 0 | n/a | n/a | n/a | n/a | n/a |

## Variants

- `elo_baseline` — Plain host-aware Elo (K=20) — the bar (walk-forward RPS 0.1776).  
  feature: none (control)
- `recent_form` — Elo + short-window momentum from last-5 match results.  
  feature: average result (win=1, draw=0.5, loss=0) over each team's last 5 matches.
- `rest_days` — Elo + rest/fatigue: more days since last match = small Elo bump.  
  feature: rest days since each team's previous match (cap 14d); short rest penalized.
- `scoring_form` — Elo + attacking form from last-5 goal difference.  
  feature: average goal difference (scored minus conceded) over each team's last 5 matches.

## Status

- No predictions have resolved yet. Standings populate once the forecast matches are played and ingested (next daily run).

## Caveats

- Small in-tournament samples: a few matches can swing RPS. Don't over-read early standings.
- Challengers are falsification rungs: they earn their place only by beating the baseline out-of-sample.

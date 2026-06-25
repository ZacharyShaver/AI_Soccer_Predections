# Daily Model-Research Leaderboard

Generated: `2026-06-25T13:31:07Z`

Each variant is scored on its most-informed pre-kickoff prediction per match (latest as_of). Lower RPS is better. `Edge` = baseline RPS - variant RPS (positive = beats the baseline). Every challenger must beat **elo_baseline**.

- Total scored predictions across variants: 56
- Registered variants: 10

| Rank | Variant | n | RPS | log loss | Brier | Decisive acc | Edge vs baseline |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `recent_form` | 14 | 0.1537 | 0.7069 | 0.3943 | 0.846 | +0.0041 |
| 2 | `scoring_form` | 14 | 0.1539 | 0.7073 | 0.3942 | 0.846 | +0.0040 |
| 3 | `elo_baseline` (baseline) | 14 | 0.1578 | 0.7209 | 0.4034 | 0.846 | +0.0000 |
| 4 | `rest_days` | 14 | 0.1578 | 0.7209 | 0.4034 | 0.846 | +0.0000 |
| 5 | `attack_defense_form` | 0 | n/a | n/a | n/a | n/a | n/a |
| 6 | `competitive_form` | 0 | n/a | n/a | n/a | n/a | n/a |
| 7 | `form_trend` | 0 | n/a | n/a | n/a | n/a | n/a |
| 8 | `match_congestion` | 0 | n/a | n/a | n/a | n/a | n/a |
| 9 | `opp_adj_form` | 0 | n/a | n/a | n/a | n/a | n/a |
| 10 | `weighted_recent_form` | 0 | n/a | n/a | n/a | n/a | n/a |

## Variants

- `recent_form` — Elo + short-window momentum from last-5 match results.  
  feature: average result (win=1, draw=0.5, loss=0) over each team's last 5 matches.
- `scoring_form` — Elo + attacking form from last-5 goal difference.  
  feature: average goal difference (scored minus conceded) over each team's last 5 matches.
- `elo_baseline` — Plain host-aware Elo (K=20) — the bar (walk-forward RPS 0.1776).  
  feature: none (control)
- `rest_days` — Elo + rest/fatigue: more days since last match = small Elo bump.  
  feature: rest days since each team's previous match (cap 14d); short rest penalized.
- `attack_defense_form` — Elo + opponent-coupled attack vs defense form (last 5).  
  feature: expected goal supremacy from each side last-5 attack (goals scored) coupled with the opponent last-5 defense (goals conceded).
- `competitive_form` — Elo with last-5 goal-difference form that down-weights friendlies.  
  feature: Competition-importance-weighted last-5 goal-difference form.
- `form_trend` — Adjusts Elo home advantage by whether recent goal difference is improving or declining.  
  feature: Slope of last-5 goal difference, computed as recent half minus earlier half.
- `match_congestion` — Elo + fixture congestion: matches played in the trailing 15 days = fatigue.  
  feature: count each team matches in the 15 days before kickoff; the more-rested side (fewer recent matches) gets a small Elo bump.
- `opp_adj_form` — Elo + opponent-adjusted last-5 goal difference.  
  feature: last-5 goal difference, each game weighted by opponent Elo strength, then home-minus-away as an Elo delta.
- `weighted_recent_form` — Elo with a recency-weighted last-five match form adjustment.  
  feature: Use weighted recent team results to nudge effective home advantage.

## Caveats

- Small in-tournament samples: a few matches can swing RPS. Don't over-read early standings.
- Challengers are falsification rungs: they earn their place only by beating the baseline out-of-sample.

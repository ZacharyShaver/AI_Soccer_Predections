# Daily Model-Research Leaderboard

Generated: `2026-06-26T15:27:48Z`

Each variant is scored on its most-informed pre-kickoff prediction per match (latest as_of). Lower RPS is better. `Edge` = baseline RPS - variant RPS (positive = beats the baseline). Every challenger must beat **elo_baseline**.

- Total scored predictions across variants: 98
- Registered variants: 14

| Rank | Variant | n | RPS | log loss | Brier | Decisive acc | Edge vs baseline |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `recent_form` | 20 | 0.1714 | 0.8163 | 0.4726 | 0.765 | +0.0014 |
| 2 | `scoring_form` | 20 | 0.1716 | 0.8169 | 0.4730 | 0.765 | +0.0012 |
| 3 | `elo_baseline` (baseline) | 20 | 0.1728 | 0.8237 | 0.4761 | 0.765 | +0.0000 |
| 4 | `rest_days` | 20 | 0.1728 | 0.8237 | 0.4761 | 0.765 | +0.0000 |
| 5 | `match_congestion` | 6 | 0.2076 | 1.0637 | 0.6457 | 0.500 | -0.0348 |
| 6 | `opp_adj_form` | 6 | 0.2128 | 1.0736 | 0.6575 | 0.500 | -0.0400 |
| 7 | `attack_defense_form` | 6 | 0.2129 | 1.0726 | 0.6569 | 0.500 | -0.0402 |
| 8 | `competitive_form` | 0 | n/a | n/a | n/a | n/a | n/a |
| 9 | `defensive_form` | 0 | n/a | n/a | n/a | n/a | n/a |
| 10 | `ensemble_top_k` | 0 | n/a | n/a | n/a | n/a | n/a |
| 11 | `ewma_goal_form` | 0 | n/a | n/a | n/a | n/a | n/a |
| 12 | `form_trend` | 0 | n/a | n/a | n/a | n/a | n/a |
| 13 | `opp_adj_recent_form` | 0 | n/a | n/a | n/a | n/a | n/a |
| 14 | `weighted_recent_form` | 0 | n/a | n/a | n/a | n/a | n/a |

## Variants

- `recent_form` — Elo + short-window momentum from last-5 match results.  
  feature: average result (win=1, draw=0.5, loss=0) over each team's last 5 matches.
- `scoring_form` — Elo + attacking form from last-5 goal difference.  
  feature: average goal difference (scored minus conceded) over each team's last 5 matches.
- `elo_baseline` — Plain host-aware Elo (K=20) — the bar (walk-forward RPS 0.1776).  
  feature: none (control)
- `rest_days` — Elo + rest/fatigue: more days since last match = small Elo bump.  
  feature: rest days since each team's previous match (cap 14d); short rest penalized.
- `match_congestion` — Elo + fixture congestion: matches played in the trailing 15 days = fatigue.  
  feature: count each team matches in the 15 days before kickoff; the more-rested side (fewer recent matches) gets a small Elo bump.
- `opp_adj_form` — Elo + opponent-adjusted last-5 goal difference.  
  feature: last-5 goal difference, each game weighted by opponent Elo strength, then home-minus-away as an Elo delta.
- `attack_defense_form` — Elo + opponent-coupled attack vs defense form (last 5).  
  feature: expected goal supremacy from each side last-5 attack (goals scored) coupled with the opponent last-5 defense (goals conceded).
- `competitive_form` — Elo with last-5 goal-difference form that down-weights friendlies.  
  feature: Competition-importance-weighted last-5 goal-difference form.
- `defensive_form` — Elo + last-5 defensive solidity (goals conceded).  
  feature: Average goals conceded over each team last 5 matches; the stingier defense (fewer conceded) gets a positive Elo delta via home-minus-away.
- `ensemble_top_k` — Equal-weight ensemble of the strongest walk-forward form variants.  
  feature: Average H/D/A probabilities from ewma_goal_form, form_trend, and opp_adj_form; delegate scoreline shape to ewma_goal_form.
- `ewma_goal_form` — Elo + EWMA goal-difference form over a 10-match horizon.  
  feature: Exponentially-weighted (geometric decay) goal difference over each team's last 10 matches, then home-minus-away as an Elo delta.
- `form_trend` — Adjusts Elo home advantage by whether recent goal difference is improving or declining.  
  feature: Slope of last-5 goal difference, computed as recent half minus earlier half.
- `opp_adj_recent_form` — Elo + opponent-adjusted last-5 results form.  
  feature: Last-5 results (win=1, draw=0.5, loss=0), each game weighted by opponent Elo strength, then home-minus-away as an Elo delta.
- `weighted_recent_form` — Elo with a recency-weighted last-five match form adjustment.  
  feature: Use weighted recent team results to nudge effective home advantage.

## Caveats

- Small in-tournament samples: a few matches can swing RPS. Don't over-read early standings.
- Challengers are falsification rungs: they earn their place only by beating the baseline out-of-sample.

# Live Polymarket vs Elo disagreement as of 2026-06-21

Generated: `2026-06-22T11:48:51Z`

This compares live Polymarket Gamma match-result prices to the current
host-aware Elo forecast trained through 2026-06-20. Polymarket prices
are parsed from the public no-auth Gamma API, filtered for positive Yes prices,
and proportionally de-vigged across each mutually exclusive H/D/A event.

## Counts

- Gamma events seen: 418
- Match-result market events parsed: 32
- Parsed market events with both canonical team ids: 32
- Elo remaining-fixture forecasts: 32
- Matches present in both Elo and Polymarket: 32
- Market-only resolved match events: 0
- Elo-only forecast fixtures: 0
- Markets skipped for null/missing/placeholder prices: 4,445
- Raw snapshot: `C:\Users\ztsha\OneDrive\Documents\AI_Soccer_Predections\worldcup_prediction_lab\data\raw\polymarket\worldcup_events_20260622T114850Z_5ae86e389cb1.json`
- Raw SHA-256: `5ae86e389cb1e41c766a80c42ec18caee24e8fe50bf8b87dd27e6edb81aff59b`
- Raw manifest: `C:\Users\ztsha\OneDrive\Documents\AI_Soccer_Predections\worldcup_prediction_lab\data\raw\polymarket\worldcup_events_20260622T114850Z_5ae86e389cb1.manifest.json`
- Gamma event requests: 5

Unmatched Polymarket team names:

- None

## Biggest disagreements

| Date | Match | Elo H/D/A | Market H/D/A | Abs home diff | Elo fav | Market fav |
| --- | --- | --- | --- | ---: | --- | --- |
| 2026-06-24 | Bosnia and Herzegovina vs Qatar | 41.7% / 25.1% / 33.2% | 67.2% / 19.4% / 13.4% | 25.5% | Bosnia and Herzegovina | Bosnia and Herzegovina |
| 2026-06-26 | Senegal vs Iraq | 57.1% / 19.9% / 23.1% | 75.1% / 16.4% / 8.5% | 18.1% | Senegal | Senegal |
| 2026-06-27 | DR Congo vs Uzbekistan | 30.5% / 23.6% / 45.9% | 46.3% / 25.4% / 28.4% | 15.8% | Uzbekistan | DR Congo |
| 2026-06-23 | Portugal vs Uzbekistan | 66.8% / 16.7% / 16.5% | 82.1% / 12.4% / 5.5% | 15.3% | Portugal | Portugal |
| 2026-06-24 | Czechia vs Mexico | 12.4% / 14.7% / 73.0% | 25.4% / 23.4% / 51.2% | 13.0% | Mexico | Mexico |
| 2026-06-25 | Japan vs Sweden | 63.9% / 17.6% / 18.5% | 51.2% / 27.4% / 21.4% | 12.6% | Japan | Japan |
| 2026-06-26 | Egypt vs Iran | 28.2% / 22.4% / 49.4% | 39.7% / 35.7% / 24.6% | 11.5% | Iran | Egypt |
| 2026-06-25 | Curaçao vs Ivory Coast | 15.9% / 16.4% / 67.7% | 4.5% / 10.6% / 84.9% | 11.3% | Ivory Coast | Ivory Coast |
| 2026-06-27 | Croatia vs Ghana | 70.5% / 15.5% / 14.0% | 59.2% / 25.4% / 15.4% | 11.3% | Croatia | Croatia |
| 2026-06-22 | France vs Iraq | 79.0% / 12.6% / 8.4% | 90.1% / 7.5% / 2.4% | 11.1% | France | France |
| 2026-06-27 | Colombia vs Portugal | 37.7% / 26.5% / 35.8% | 26.6% / 25.6% / 47.7% | 11.1% | Colombia | Portugal |
| 2026-06-26 | New Zealand vs Belgium | 17.4% / 17.1% / 65.4% | 6.5% / 13.6% / 79.9% | 10.9% | Belgium | Belgium |
| 2026-06-23 | Colombia vs DR Congo | 74.0% / 14.3% / 11.7% | 64.8% / 22.6% / 12.6% | 9.1% | Colombia | Colombia |
| 2026-06-23 | Panama vs Croatia | 22.5% / 19.6% / 58.0% | 13.4% / 23.4% / 63.2% | 9.0% | Croatia | Croatia |
| 2026-06-25 | Tunisia vs Netherlands | 12.1% / 14.5% / 73.4% | 3.4% / 9.5% / 87.2% | 8.7% | Netherlands | Netherlands |

## Interpretation

The comparison is prediction-vs-prediction, not a score test. Elo is an
internal form-only rating with host advantage; Polymarket is a live market
that can incorporate injuries, lineups, sentiment, liquidity, and late news.
Large gaps are therefore useful flags for review, not automatic model errors.

Caveats:

- Gamma prices are live and can move after this snapshot.
- Only individual match-result events are included; props, spreads, totals, exact scores, group, and outright markets are excluded.
- If Polymarket uses a team spelling outside the alias table, the market is reported but cannot join Elo until the alias is added.
- If only two-way match-winner markets appear in a future snapshot, this parser will currently skip them rather than mixing two-way and three-way probabilities.

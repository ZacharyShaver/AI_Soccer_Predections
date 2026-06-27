# Live World Cup forecast as of 2026-06-27

These are Elo-only forecasts from `elo_poisson_v1`, the model bar proven in M6.
They are not market-calibrated and do not include injuries, lineups, travel, or live odds.

Statistical honesty caveat: M6 showed Elo beat climatology on a large walk-forward
history, but single-match probabilities are still uncertain. Treat narrow edges as
within normal forecast noise, not as certainties.

Knockout fixtures are pending bracket resolution because openfootball stores placeholder
slots with null team ids until the bracket is known.

## Counts

- Total fixtures: 104
- Forecast: 3
- Skipped already played (<= 2026-06-27): 72
- Skipped knockout pending: 29
- Training matches through 2026-06-25: 49465
- Ledger: `C:/Users/ztsha/OneDrive/Documents/AI_Soccer_Predections/worldcup_prediction_lab/runs/predictions/date=2026-06-21/predictions.jsonl`

## Venue host-country mapping

- Atlanta: USA
- Boston (Foxborough): USA
- Dallas (Arlington): USA
- Guadalajara (Zapopan): Mexico
- Houston: USA
- Kansas City: USA
- Los Angeles (Inglewood): USA
- Mexico City: Mexico
- Miami (Miami Gardens): USA
- Monterrey (Guadalupe): Mexico
- New York/New Jersey (East Rutherford): USA
- Philadelphia: USA
- San Francisco (Santa Clara): USA
- San Francisco Bay Area (Santa Clara): USA
- Seattle: USA
- Toronto: Canada
- Vancouver: Canada

All forecast venues were mapped to a host country.

## Group Pending

| Date | Venue | Match | Home | Draw | Away | Most likely score | O2.5 | BTTS |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: |
| 2026-06-28 | Los Angeles (Inglewood) | South Africa vs Canada | 23.0% | 19.8% | 57.2% | 0-1 (12.4%) | 52.5% | 51.5% |
| 2026-06-29 | Houston | Brazil vs Japan | 50.0% | 22.2% | 27.8% | 1-0 (11.4%) | 51.4% | 52.8% |
| 2026-06-29 | Monterrey (Guadalupe) | Netherlands vs Morocco | 42.0% | 25.0% | 33.0% | 1-1 (11.9%) | 50.1% | 53.8% |

# Live World Cup forecast as of 2026-06-29

These are Elo-only forecasts from `elo_poisson_v1`, the model bar proven in M6.
They are not market-calibrated and do not include injuries, lineups, travel, or live odds.

Statistical honesty caveat: M6 showed Elo beat climatology on a large walk-forward
history, but single-match probabilities are still uncertain. Treat narrow edges as
within normal forecast noise, not as certainties.

Knockout fixtures are pending bracket resolution because openfootball stores placeholder
slots with null team ids until the bracket is known.

## Counts

- Total fixtures: 104
- Forecast: 5
- Skipped already played (<= 2026-06-29): 75
- Skipped knockout pending: 24
- Training matches through 2026-06-28: 49478
- Ledger: `C:/Users/ztsha/OneDrive/Documents/AI_Soccer_Predections/worldcup_prediction_lab/runs/predictions/date=2026-06-29/predictions.jsonl`

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
| 2026-06-30 | Dallas (Arlington) | Ivory Coast vs Norway | 30.3% | 23.5% | 46.2% | 1-1 (11.2%) | 50.7% | 53.3% |
| 2026-07-02 | Toronto | Portugal vs Croatia | 48.2% | 22.8% | 29.0% | 1-0 (11.2%) | 51.1% | 53.1% |
| 2026-07-02 | Los Angeles (Inglewood) | Spain vs Austria | 73.8% | 14.4% | 11.8% | 1-0 (14.4%) | 55.3% | 46.7% |
| 2026-07-03 | Miami (Miami Gardens) | Argentina vs Cape Verde | 86.6% | 9.7% | 3.8% | 2-0 (16.4%) | 58.4% | 41.3% |
| 2026-07-03 | Dallas (Arlington) | Australia vs Egypt | 44.3% | 24.2% | 31.5% | 1-1 (11.5%) | 50.4% | 53.5% |

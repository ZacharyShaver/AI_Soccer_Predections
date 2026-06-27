# Live World Cup forecast (market overlay) as of 2026-06-27

Market-where-available, Elo-everywhere-else. For each remaining fixture the
probabilities are the de-vigged Polymarket match-result market when one exists
for that team pair, otherwise the `elo_poisson_v1` forecast. Backtests show the
de-vigged market significantly beats Elo where odds exist (paired RPS CI excludes
0); Elo remains the always-available backbone for fixtures without a market.

## Counts

- Forecast fixtures: 0
- Using market probabilities: 0
- Using Elo fallback: 0

## Caveats

- Market prices are a live snapshot and move with news, lineups, and liquidity.
- Only three-way match-result markets are used; props/spreads/totals/group/outright are excluded.
- A fixture only takes the market when its team pair resolves to canonical ids in the alias table; otherwise it keeps the Elo forecast.
- Knockout fixtures with unresolved brackets are not forecast here (null team ids upstream).

# DQ: transfermarkt squad values

Generated: `2026-07-02T17:45:54Z`
Source: `https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/transfermarkt-datasets.duckdb` (transfermarkt-datasets, CC0-1.0; weekly refresh)

Monthly per-team squad value = sum of the top 15 player market values among
citizens holding a valuation dated within 730 days before month-end.

## Coverage

- Rows: 41215
- Teams with any coverage: 184
- Teams with coverage since 2010: 184
- Date range: 2000-01 .. 2026-06

| Team | First | Last | Months |
| --- | --- | --- | ---: |
| Turkey | 2004-10 | 2026-06 | 481 |
| New Caledonia | 2010-08 | 2026-06 | 290 |
| France | 2001-07 | 2026-06 | 285 |
| Togo | 2000-01 | 2026-06 | 285 |
| Romania | 2003-12 | 2026-06 | 271 |
| Albania | 2004-10 | 2026-06 | 261 |
| Argentina | 2004-10 | 2026-06 | 261 |
| Algeria | 2004-10 | 2026-06 | 261 |
| Bosnia and Herzegovina | 2004-10 | 2026-06 | 261 |
| Brazil | 2004-10 | 2026-06 | 261 |

## Unmatched citizenship names (no alias row; excluded)

- Bonaire
- Eritrea
- French Guiana
- Guadeloupe
- Martinique
- Monaco
- Réunion
- Saint-Martin
- Sint Maarten

## Caveats

- Citizenship is a talent-POOL proxy, not the selected 26-man roster.
- Transfermarkt values are crowd estimates; history is thin before ~2007.
- Dual citizens count only for their listed country_of_citizenship.
- The 730-day staleness window drops retired/inactive players
  whose final valuation would otherwise persist forever.

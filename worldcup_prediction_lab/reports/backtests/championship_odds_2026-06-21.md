# World Cup 2026 championship odds (as of 2026-06-21)

Monte Carlo simulation from `elo_poisson_v1` — the model bar proven in M6 (Elo beats
climatology on a 15,817-match walk-forward backtest). These are **Elo-only** odds: no
market prices, injuries, lineups, or travel. Tournament variance is large; even strong
favourites rarely exceed ~20-25% to win the whole thing.

## Method

- Trained on completed international results through `2026-06-20` (host-aware Elo).
- Already-played 2026 group results are held FIXED; remaining matches simulated.
- Simulations: 20,000, seed 0. Group tiebreakers per FIFA; 8 best third-placed
  teams allocated to the Round of 32 by constraint-matching the official candidate lists
  (documented approximation). Knockout draws resolved as conditional-on-not-draw.
- Host advantage applied to USA/Canada/Mexico when playing in their own country.
- Determinism check (two seeded runs identical): PASS.
- Report generated 2026-06-22T00:14:48Z.

## Championship odds (sorted by P(Win))

| # | Team | Grp | Elo | P(Adv) | P(R16) | P(QF) | P(SF) | P(Final) | P(Win) |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | Argentina | J | 2041 | 100.0% | 62.0% | 51.2% | 39.5% | 27.9% | **19.2%** |
| 2 | Spain | H | 2028 | 100.0% | 57.9% | 46.9% | 35.7% | 24.4% | **16.1%** |
| 3 | France | I | 1991 | 99.8% | 84.1% | 54.8% | 37.9% | 24.2% | **13.5%** |
| 4 | Brazil | C | 1962 | 100.0% | 63.7% | 45.5% | 27.1% | 13.3% | **7.2%** |
| 5 | England | L | 1955 | 100.0% | 78.8% | 45.6% | 26.1% | 12.4% | **6.6%** |
| 6 | Germany | E | 1923 | 100.0% | 85.7% | 43.2% | 25.6% | 14.1% | **6.0%** |
| 7 | Colombia | K | 1933 | 98.7% | 75.1% | 48.8% | 22.5% | 11.5% | **5.5%** |
| 8 | Portugal | K | 1926 | 84.0% | 58.0% | 35.1% | 18.5% | 9.1% | **4.2%** |
| 9 | Netherlands | F | 1915 | 100.0% | 49.1% | 33.0% | 16.0% | 7.7% | **3.3%** |
| 10 | United States | D | 1799 | 100.0% | 70.3% | 42.5% | 19.6% | 8.1% | **2.7%** |
| 11 | Mexico | A | 1871 | 100.0% | 79.7% | 42.5% | 18.0% | 6.2% | **2.5%** |
| 12 | Japan | F | 1898 | 100.0% | 45.9% | 28.6% | 13.1% | 5.8% | **2.2%** |
| 13 | Morocco | C | 1884 | 100.0% | 46.7% | 29.2% | 12.3% | 5.8% | **2.1%** |
| 14 | Belgium | G | 1874 | 84.9% | 56.0% | 24.9% | 11.0% | 4.6% | **1.8%** |
| 15 | Uruguay | H | 1859 | 87.5% | 47.4% | 23.1% | 11.9% | 4.6% | **1.5%** |
| 16 | Croatia | L | 1855 | 84.9% | 39.1% | 18.4% | 8.7% | 3.4% | **1.1%** |
| 17 | Switzerland | B | 1839 | 100.0% | 60.7% | 24.1% | 7.5% | 2.9% | **0.9%** |
| 18 | Norway | I | 1817 | 98.2% | 57.4% | 19.9% | 7.3% | 2.3% | **0.7%** |
| 19 | Iran | G | 1824 | 71.3% | 40.0% | 13.9% | 5.0% | 1.6% | **0.5%** |
| 20 | Austria | J | 1793 | 100.0% | 36.1% | 14.5% | 6.0% | 1.9% | **0.5%** |
| 21 | Canada | B | 1791 | 100.0% | 60.5% | 24.9% | 5.6% | 1.6% | **0.4%** |
| 22 | Australia | D | 1811 | 93.1% | 43.2% | 9.9% | 3.8% | 1.2% | **0.4%** |
| 23 | South Korea | A | 1807 | 95.6% | 43.3% | 14.5% | 4.4% | 1.5% | **0.3%** |
| 24 | Senegal | I | 1809 | 65.6% | 32.7% | 12.0% | 4.0% | 1.2% | **0.3%** |
| 25 | Paraguay | D | 1784 | 76.2% | 27.2% | 6.6% | 2.2% | 0.7% | **0.2%** |
| 26 | Ivory Coast | E | 1758 | 97.1% | 31.9% | 7.2% | 1.9% | 0.4% | **0.1%** |
| 27 | Algeria | J | 1797 | 28.8% | 11.7% | 4.6% | 1.4% | 0.4% | **0.1%** |
| 28 | Egypt | G | 1749 | 66.7% | 27.2% | 6.5% | 1.7% | 0.3% | **0.0%** |
| 29 | Sweden | F | 1727 | 93.7% | 19.6% | 6.1% | 1.5% | 0.2% | **0.0%** |
| 30 | Scotland | C | 1724 | 95.4% | 17.0% | 3.4% | 0.9% | 0.2% | **0.0%** |
| 31 | Uzbekistan | K | 1734 | 43.6% | 11.3% | 2.8% | 0.6% | 0.1% | **0.0%** |
| 32 | New Zealand | G | 1692 | 46.9% | 14.3% | 2.5% | 0.4% | 0.1% | **0.0%** |
| 33 | Turkey | D | 1787 | 12.9% | 3.3% | 1.2% | 0.3% | 0.1% | **0.0%** |
| 34 | DR Congo | K | 1680 | 42.8% | 10.4% | 2.2% | 0.4% | 0.1% | **0.0%** |
| 35 | Saudi Arabia | H | 1663 | 44.5% | 8.1% | 1.8% | 0.3% | 0.0% | **0.0%** |
| 36 | Cape Verde | H | 1630 | 46.0% | 8.0% | 1.3% | 0.2% | 0.0% | **0.0%** |
| 37 | Iraq | I | 1686 | 15.8% | 4.1% | 1.0% | 0.2% | 0.0% | **0.0%** |
| 38 | Czechia | A | 1702 | 13.9% | 2.9% | 0.6% | 0.1% | 0.0% | **0.0%** |
| 39 | South Africa | A | 1628 | 18.2% | 3.3% | 0.5% | 0.1% | 0.0% | **0.0%** |
| 40 | Ghana | L | 1632 | 75.8% | 11.5% | 2.1% | 0.3% | 0.0% | **0.0%** |
| 41 | Jordan | J | 1681 | 20.2% | 4.8% | 1.1% | 0.1% | 0.0% | **0.0%** |
| 42 | Panama | L | 1726 | 5.1% | 1.0% | 0.4% | 0.0% | 0.0% | **0.0%** |
| 43 | Bosnia and Herzegovina | B | 1613 | 42.1% | 4.3% | 0.6% | 0.1% | 0.0% | **0.0%** |
| 44 | Qatar | B | 1584 | 33.3% | 2.7% | 0.4% | 0.0% | 0.0% | **0.0%** |
| 45 | Curaçao | E | 1558 | 16.1% | 2.0% | 0.1% | 0.0% | 0.0% | **0.0%** |
| 46 | Haiti | C | 1627 | 0.9% | 0.1% | 0.0% | 0.0% | 0.0% | **0.0%** |
| 47 | Tunisia | F | 1667 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | **0.0%** |
| 48 | Ecuador | E | 1850 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | **0.0%** |

## Caveats

- Elo-only; a market-calibrated comparison comes in P6.
- Knockout bracket third-place allocation is a constraint-satisfying approximation of
  FIFA's official table (always respects the candidate-group constraints).
- Probabilities are nested by construction: P(Win) <= P(Final) <= ... <= P(Adv).

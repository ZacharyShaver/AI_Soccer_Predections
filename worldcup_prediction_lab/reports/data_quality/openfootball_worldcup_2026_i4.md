# I4 openfootball World Cup 2026 fixture data quality

- Source files: `https://raw.githubusercontent.com/openfootball/worldcup/master/2026--usa/cup.txt` and `https://raw.githubusercontent.com/openfootball/worldcup/master/2026--usa/cup_finals.txt`
- Ingest UTC: `2026-06-21T21:33:22Z`
- Raw cup SHA-256: `e9a0814b413447792206abe2b9dfe04fa0a50564584e075390fe0aba97c7a77d`
- Raw cup_finals SHA-256: `d5b8dc1ee3c06c65ad6bf71f6bbf7fcb4c9acc465999b08b49a3c86238b96db8`
- Groups parsed: 12
- Distinct group-stage teams resolved: 48
- Resolved canonical group team ids: 48
- Group fixtures: 72
- Knockout fixtures: 32
- Total fixtures: 104
- Date range: 2026-06-11 to 2026-07-19
- Fixture ID unique: True
- Martj42 blank-score fixture rows checked: 36
- Martj42 reconciliation disagreements: 3

Stage counts:
- final: 1
- group: 72
- quarter_final: 4
- round_of_16: 8
- round_of_32: 16
- semi_final: 2
- third_place: 1

Openfootball (D2) is the 2026 fixture source of truth. Martj42 blank-score
fixture rows are used only as a cross-validation input and do not override
stage, group, venue, or bracket slots from openfootball.

Martj42 reconciliation details:
- `{"martj42_away_team_id": "SUI", "martj42_date": "2026-06-24", "martj42_home_team_id": "CAN", "openfootball_away_team_id": "CAN", "openfootball_dates": ["2026-06-24"], "openfootball_home_team_id": "SUI", "type": "home_away_order_disagreement"}`
- `{"martj42_away_team_id": "CZE", "martj42_date": "2026-06-24", "martj42_home_team_id": "MEX", "openfootball_away_team_id": "MEX", "openfootball_dates": ["2026-06-24"], "openfootball_home_team_id": "CZE", "type": "home_away_order_disagreement"}`
- `{"martj42_away_team_id": "TUR", "martj42_date": "2026-06-25", "martj42_home_team_id": "USA", "openfootball_away_team_id": "USA", "openfootball_dates": ["2026-06-25"], "openfootball_home_team_id": "TUR", "type": "home_away_order_disagreement"}`

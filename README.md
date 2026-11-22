# Smart City Resource Intelligence Platform

A Flask demonstration dashboard for electricity, water, solar, and weather readings. The included CSV is fictional simulated data and is not connected to live city infrastructure.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000>. The app reads `data/sample_data.csv` for API requests.

## API

- `GET /api/health` — application and sample-data health.
- `GET /api/resources` — all simulated readings; optional case-insensitive `zone` filter.
- `GET /api/predictions/energy` — electricity persistence forecast and holdout metrics.
- `GET /api/predictions/water`, `GET /api/analytics/water`, `GET /api/alerts/water` — water forecasts, statistics, and anomaly screening; each accepts optional `zone`.
- `GET /api/predictions/solar` — per-zone solar baseline forecast and holdout metrics; optional `zone`.
- `GET /api/analytics/solar` — solar zone statistics and history; optional `zone`.
- `GET /api/alerts/solar` — low-generation screening; optional `zone`.
- `GET /api/solar-demand-comparison` — timestamp-aligned demand comparison and weather status; optional `zone`.

## Milestone 4: Solar Intelligence

`services/solar_intelligence.py` is an independently testable service for validated solar summaries, history, persistence forecasting, chronological holdout evaluation, configurable threshold screening, demand comparison, and weather relationship analysis.

The CSV contains 16 observations: four zones at 08:00, 12:00, 16:00, and 20:00 on 18 June 2026. The available fields include `solar_generation_mw` (MW), `electricity_demand_mw` (MW), and `temperature_c` (degrees Celsius). All 16 records have values in these columns; each is zone-specific. All source readings are fictional simulated sample data, not real measurements. There are no irradiance, cloud-cover, or weather forecast fields. Temperature correlation is a small exploratory statistic, not causal evidence.

The next-interval forecast carries the zone's latest solar reading forward; the next time is inferred from its timestamp spacing. Evaluation predicts each zone's final reading from its immediately prior observation and reports MAE and RMSE. R² is returned only when holdout actuals have meaningful variation. Four zones provide only four holdout observations, so no reliable forecast accuracy claim is warranted.

Low generation is defined as a latest reading below 2.0 MW by default. The service accepts a configurable non-negative threshold. This is a screening rule, not a fault diagnosis. Demand comparison uses matching zone and timestamp readings in MW. Estimated uncovered demand is `max(demand - solar, 0)`; contribution is capped at 100%. Solar generation does not necessarily equal electricity available to the grid because behind-the-meter use, storage, curtailment, losses, and network constraints are not measured. Missing or incompatible readings are reported unavailable. No solar or weather values are invented.

Water anomaly alerts are screening indicators and do not confirm leaks. Water shortage assessment is unavailable because the CSV has no supply or usable storage measurements. Allocation interfaces remain unimplemented; no trained AI or optimization is claimed.

Run the test suite with `python -m pytest -v`.
# Intelligent allocation scenarios

Allocation is an explicit scenario simulation, not a live supply assessment.
The sample CSV has demand readings but no measured electricity supply, usable
water storage, or identified critical facilities. Send `zones` with electricity
and water demand, an optional critical-service portion of each demand, and an
explicit priority (`critical`, `high`, `medium`, or `standard`). Supply both
`availability.electricity_mw` and `availability.water_litres` for the interval.
Optional `solar_generation_mw` is counted one-for-one as additional electricity
capacity only when the caller explicitly supplies it; this assumes no grid,
curtailment, or storage losses.

`POST /api/allocation/run` runs a scenario. `POST /api/allocation/simulate`
accepts `{ "baseline": { ... }, "scenario": { "name": "...", "changes": { ... } } }`.
Scenario changes support electricity or water availability multipliers,
`demand_multiplier`, `solar_reduction_fraction` (0 to 1), and per-zone
`priority_overrides`. `GET /api/allocation/status` describes the current engine.

The engine is a deterministic heuristic: it allocates declared critical-service
needs first, then visits priority tiers in order and shares constrained capacity
proportionally among zones in the same tier. It is auditable and does not claim
mathematical optimization. Scenario results include unmet demand, critical
coverage, utilization, per-zone explanations, and baseline comparison.


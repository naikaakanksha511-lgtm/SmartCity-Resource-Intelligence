# MILESTONE 6: Quick Start Guide

## What's New

**City Emergency Intelligence & Response Engine** — a production-ready system for analyzing multi-resource stress, detecting cascading risks, classifying emergency severity, and recommending explainable interventions.

## Key Features

✅ **Multi-resource stress detection** — Electricity, water, solar, and critical-service shortfalls  
✅ **Cascading risk intelligence** — Explicit configurable dependencies (not causal claims)  
✅ **Severity classification** — Normal, Warning, High, Critical (with boundary testing)  
✅ **Intervention recommendations** — Ranked, never claiming execution  
✅ **5 built-in scenarios** — Normal → Heatwave → Solar reduction → Combined shortage → Hospital emergency  
✅ **Professional API** — `/api/emergency/{analyze, simulate, scenarios, status}`  
✅ **Emergency command center dashboard** — Interactive scenario selector and before/after comparison  
✅ **All tests passing** — 58/58 ✅  

## Running the Application

### 1. Install Dependencies
```powershell
cd C:\Users\naikn\OneDrive\Desktop\SmartCity-Resource-Intelligence
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. Start the Server
```powershell
python app.py
```

Browser opens at: `http://127.0.0.1:5000`

### 3. Navigate to Emergency Intelligence
In the sidebar: click **◎ Emergency Intelligence**

### 4. Run Tests
```powershell
python -m pytest -v
```

Expected: **58 passed in ~6 seconds**

## API Examples

### View Available Scenarios
```bash
curl http://127.0.0.1:5000/api/emergency/scenarios
```

Returns 5 pre-analyzed scenarios with risk scores and recommendations.

### Analyze a Custom Scenario
```bash
curl -X POST http://127.0.0.1:5000/api/emergency/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My scenario",
    "zones": [
      {
        "zone": "Downtown",
        "priority": "high",
        "electricity_demand_mw": 50,
        "water_demand_litres": 2000000,
        "critical_service_requirements": {
          "electricity_mw": 10,
          "water_litres": 500000
        }
      }
    ],
    "availability": {
      "electricity_mw": 40,
      "water_litres": 1500000
    },
    "solar_generation_mw": 5
  }'
```

### Compare Scenarios
```bash
curl -X POST http://127.0.0.1:5000/api/emergency/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "baseline": { ... baseline scenario ... },
    "scenario": {
      "name": "Emergency response",
      "changes": {
        "electricity_availability_multiplier": 0.8,
        "priority_overrides": {"Downtown": "critical"}
      }
    }
  }'
```

## Understanding the Output

### Severity Levels
- **Normal** (0–24): No issues detected
- **Warning** (25–49): Resource constraints; monitoring recommended
- **High** (50–74): Significant shortfalls likely
- **Critical** (≥75): Severe multi-resource failure or critical services unmet

### Risk Score Formula
```
zone_score = max(shortfall_%) + 10×(multi_resource) + 15×(critical_unmet) [capped 100]
city_score = max(zone_scores) + cascading_risks [capped 100]
```

### Key Properties

1. **All inputs are explicit** — No capacity is inferred from history
2. **Dependencies are assumptions** — Clearly marked as configurable, not causal findings
3. **Data is labeled** — Every output distinguishes observed/simulated/assumed values
4. **Recommendations never claim execution** — Only advice is provided
5. **No false alarms** — Normal scenario with adequate supply produces zero alerts

## Dashboard View

### Scenario Selector
- Dropdown menu with 5 built-in scenarios
- Dynamic description and data label

### Comparison Tab
- Before/after metrics side-by-side
- Risk score change, affected zones, shortfalls, critical coverage

### Zone Risk Table
- Risk score and severity for each zone
- Electricity gap (MW), water gap (litres)
- Critical-service coverage percentage

### Stress Indicators
- All detected alerts with zone, resource, severity
- Measured/scenario-supplied values
- Evidence quality labels (scenario-supplied, assumed, etc.)

### Cascading-Risk Explanations
- Dependency chain (source → target)
- Risk contribution in points
- Explicit "assumption-based" label on each

### Ranked Interventions
1. Critical-service reallocation (if applicable)
2. Essential water protection (if water short)
3. Non-essential electricity deferral (if electricity short)
4. Scenario simulation (if shortfalls persist)

Each includes:
- Triggering condition
- Proposed action
- Expected benefit and trade-off
- Assumptions
- Affected zones
- **Never claims execution**

## Example Scenario Outputs

### Scenario 1: Normal City Operations
```
Severity: NORMAL
Risk Score: 0.0
Affected Zones: []
Alerts: []
Cascading Risks: []
Interventions: []
```

### Scenario 2: Heatwave with Increased Demand
```
Severity: CRITICAL
Risk Score: 100.0
Affected Zones: [Central District, North Residential, South Industrial]
Alerts: 4 (multiple electricity/water shortages)
Cascading Risks: 2 (electricity → water, water → critical_services)
Interventions: 3 (critical reallocation, water protection, deferral)
```

### Scenario 5: Hospital Emergency During Shortage
```
Severity: CRITICAL
Risk Score: 100.0
Affected Zones: [Central District, North Residential, South Industrial]
Alerts: 4 (including critical_service_electricity shortfall)
Cascading Risks: 2
Interventions: 3 (prioritizes critical hospital loads)
```

## Important Disclaimers

⚠️ **Simulated demonstration only**
- All inputs are caller-supplied
- No capacity is inferred from historical consumption
- Dependencies are configurable assumptions, not measured causality
- Sample data: 16 CSV records (fictional)

⚠️ **Not an operational system**
- This is an explainable analysis framework
- Recommendations are advice only
- No actual resource reallocation occurs
- Always validate with real-world domain experts

⚠️ **Thresholds are illustrative**
- Severity scores are demonstration values
- Use configuration for your city's actual requirements
- Test with real data before deployment

## Project Structure

```
SmartCity-Resource-Intelligence/
├── app.py                               # Flask application
├── config.py                            # Configuration
├── requirements.txt                     # Python dependencies
├── data/sample_data.csv                 # Fictional demo data (16 records)
├── services/
│   ├── allocation.py                    # Resource allocation heuristic
│   ├── emergency_intelligence.py        # Milestone 6 (NEW)
│   ├── solar_intelligence.py            # Milestone 4
│   └── water_intelligence.py            # Milestone 3
├── models/
│   └── prediction.py                    # Electricity forecasting
├── templates/
│   └── index.html                       # Dashboard HTML
├── static/
│   ├── css/style.css                    # Professional dark theme
│   └── js/dashboard.js                  # Dashboard UI logic
├── tests/
│   ├── test_app.py                      # Flask endpoint tests
│   ├── test_allocation.py               # Allocation tests
│   └── test_emergency_intelligence.py   # Emergency tests (NEW)
├── MILESTONE_6_REPORT.md                # Comprehensive technical report
└── README.md                            # Project overview
```

## Support & Validation

- **Health check**: `GET /api/health` → 200 OK
- **Emergency status**: `GET /api/emergency/status` → 200 OK with mode/thresholds
- **Sample data**: 4 zones × 4 time intervals on 18 June 2026
- **Test suite**: 58 tests covering normal/shortage/cascading/boundary conditions
- **API validation**: All endpoints validate input; 400 for invalid data

## Next Steps

**Milestone 6 is complete.** The next phase would be:

- **Milestone 7**: Digital Twin
  - Temporal simulation with dynamic state tracking
  - Time-series intervention recovery curves
  - Restoration planning and sequencing

For detailed architecture, methodology, and design decisions, see: **MILESTONE_6_REPORT.md**

---

**Status**: ✅ Production Ready | **Tests**: 58/58 Passing | **API**: 4 Endpoints | **Dashboard**: Functional

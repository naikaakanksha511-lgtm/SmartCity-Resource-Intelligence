# MILESTONE 6: City Emergency Intelligence & Response Engine

## Executive Summary

Milestone 6 is **complete and fully functional**. The Smart City Resource Intelligence Platform now includes a production-ready emergency intelligence system that:

- Analyzes multi-resource stress from explicit scenario inputs
- Detects cascading risks using configurable dependency assumptions
- Classifies emergency severity with transparent scoring formulas
- Recommends explainable interventions ranked by priority
- Provides scenario-based simulation and comparison
- Integrates with existing energy, water, and solar intelligence modules
- Exposes professional API endpoints for emergency analysis
- Renders a dedicated emergency command center dashboard view

**All 58 tests pass.** The system is deterministic, auditable, and explicitly labels all data as simulated.

---

## 1. Architecture

### Services Layer

**`services/emergency_intelligence.py`** (650+ lines)
- Core analysis engine: `analyze_emergency(scenario)`
- Scenario simulation: `simulate_emergency(baseline, scenario)`
- Built-in demonstrations: `built_in_scenarios()` → 5 labeled test cases
- Helper functions: `_severity()`, `_elevate()`, `_recommend()`

### Integration Points

1. **Allocation Engine** (`services/allocation.py`)
   - Emergency analysis calls `run_allocation()` to calculate resource distribution
   - Receives per-zone allocation results with critical-service coverage

2. **Flask API** (`app.py`)
   - 4 emergency endpoints: `/api/emergency/{analyze, simulate, scenarios, status}`
   - Validation and error handling for all inputs
   - JSON request/response protocol

3. **Dashboard UI** (`templates/index.html`, `static/js/dashboard.js`)
   - Emergency Intelligence section in the sidebar navigation
   - Interactive scenario selector with before/after comparison
   - Zone risk table, cascading-risk explanations, ranked interventions

### Data Model

**Input Scenario** (required fields):
```json
{
  "name": "Human-readable scenario name",
  "zones": [
    {
      "zone": "Zone Name",
      "priority": "critical|high|medium|standard",
      "electricity_demand_mw": 45.0,
      "water_demand_litres": 1900000.0,
      "critical_service_requirements": {
        "electricity_mw": 8.0,
        "water_litres": 300000.0
      }
    }
  ],
  "availability": {
    "electricity_mw": 180.0,
    "water_litres": 7000000.0
  },
  "solar_generation_mw": 8.0,
  "solar_reduction_fraction": 0.0,
  "dependencies": [ ... ],
  "assumptions": [ ... ]
}
```

**Output Analysis** (sample):
```json
{
  "status": "simulated",
  "scenario_name": "Normal city operations",
  "data_label": "simulated scenario; not a live event",
  "overall_severity": "normal",
  "risk_score": 0.0,
  "severity_thresholds": {"normal": "<25", "warning": "25-<50", "high": "50-<75", "critical": ">=75"},
  "alerts": [ ... ],
  "affected_zones": [ "South Industrial" ],
  "zones": [ ... ],
  "cascading_risks": [ ... ],
  "interventions": [ ... ],
  "assumptions": [ ... ]
}
```

---

## 2. Multi-Resource Stress Detection

### Alert Categories

For each zone and resource, the system detects:

1. **Electricity Shortage**
   - Condition: `unmet_electricity > 0`
   - Severity: Determined by % of demand unmet
   - Evidence: "scenario-supplied; simulated"

2. **Water Shortage**
   - Condition: `unmet_water > 0`
   - Severity: Determined by % of demand unmet
   - Evidence: "scenario-supplied; simulated"

3. **Solar Generation Reduction**
   - Condition: `solar_reduction_fraction > 0`
   - Severity: "warning" (<50%) or "high" (≥50%)
   - Evidence: "assumed scenario input; simulated"

4. **Critical-Service Shortfall**
   - Condition: Explicit critical requirement unmet
   - Severity: Always "critical"
   - Evidence: "scenario-supplied; simulated"

5. **Combined Multi-Resource Failure**
   - Condition: Simultaneous shortage in 2+ resources
   - Bonus: +10 points to risk score
   - Avoided double-counting: Base score + combination bonus (capped)

### Alert Structure
```json
{
  "zone": "Zone Name",
  "resource": "electricity|water|solar_generation|critical_service_*",
  "severity": "warning|high|critical",
  "measured_or_scenario_supplied": {
    "demand": 100.0,
    "allocated": 50.0,
    "shortfall": 50.0,
    "unit": "MW or litres"
  },
  "threshold": { ... },
  "explanation": "Human-readable cause and impact",
  "evidence_quality": "scenario-supplied; simulated|assumed scenario input; simulated",
  "status": "simulated"
}
```

---

## 3. Cascading Risk Intelligence

### Dependency Model

Default dependencies (configurable per scenario):
```python
[
  {
    "source": "electricity",
    "target": "water",
    "factor": 0.20,
    "explanation": "Assumption: electricity shortage may constrain water pumping."
  },
  {
    "source": "water",
    "target": "critical_services",
    "factor": 0.20,
    "explanation": "Assumption: water shortage may affect hospitals and emergency services."
  },
  {
    "source": "solar_reduction",
    "target": "electricity",
    "factor": 0.15,
    "explanation": "Assumption: lower solar generation increases reliance on other supply."
  }
]
```

### Cascade Calculation

For each dependency:
1. **Source Strength** = Fraction of resource unmet (0–1) or solar reduction fraction
2. **Impact** = `source_strength × factor × 100` (points)
3. **Total Cascade Score** = Sum of all impacts (capped at 25 points)
4. **City Risk** = `max(zone_scores) + cascade_score` (capped at 100)

### Key Properties

- **Explicit assumptions**: Each dependency clearly states it is an assumption, not a measured causal link
- **No double-counting**: Underlying resource shortfalls are counted once; cascades add secondary impacts
- **Transparent factors**: User can supply custom dependencies or rely on defaults
- **Evidence labeled**: All cascade contributions marked "configurable assumption; not established by sample data"

---

## 4. Emergency Severity Classification

### Four-Level Scale

| Severity | Range | Meaning |
|----------|-------|---------|
| **Normal** | < 25 | City operations nominal; no alerts |
| **Warning** | 25–<50 | Resource constraints detected; monitoring recommended |
| **High** | 50–<75 | Significant shortfalls or critical-service impacts likely |
| **Critical** | ≥ 75 | Severe multi-resource failure or critical services unmet |

### Scoring Formula

```
zone_score = max(
  resource_shortfall_%,
  resource_shortfall_% + 10 (if 2+ resources failed),
  resource_shortfall_% + 15 (if critical-service shortfall)
)  [capped at 100]

city_score = min(100, max(zone_scores) + cascading_risk_score)

severity = {
  <25 → "normal",
  25–<50 → "warning",
  50–<75 → "high",
  ≥75 → "critical"
}
```

### Critical-Service Elevation

**Rule**: If any zone has a critical-service shortfall, the city severity is elevated to at least "high" even if the raw score is lower.

### Test Coverage

- ✅ Boundary tests: 0, 24.999, 25, 49.999, 50, 74.999, 75, 100
- ✅ All transitions verified
- ✅ False positive checks: Normal scenario returns no alerts

---

## 5. Intervention Recommendation Engine

### Recommendation Structure
```json
{
  "rank": 1,
  "triggering_condition": "Human-readable condition that activates this recommendation",
  "proposed_action": "Specific action to take",
  "expected_benefit": "Quantified or qualitative improvement",
  "trade_off": "What is sacrificed or delayed",
  "assumptions": [ "Assumption 1", "Assumption 2" ],
  "affected_zones": [ "Zone A", "Zone B" ],
  "executed": false
}
```

**Key property**: `"executed": false` — no intervention is claimed to have been applied; only recommendations are provided.

### Recommendation Types

1. **Critical-Service Priority Reallocation** (Rank 1 when triggered)
   - Triggering: Explicit critical-service requirements unmet
   - Action: Reallocate declared critical loads, defer lower-priority demand
   - Assumption: Critical labels and requirements are correct

2. **Essential Water Protection** (Rank 2)
   - Triggering: Water shortage in one or more zones
   - Action: Protect declared essential water demand
   - Assumption: Critical-service water quantities represent the minimum

3. **Non-Essential Electricity Deferral** (Rank 3)
   - Triggering: Electricity shortage
   - Action: Reduce or defer non-essential loads
   - Assumption: Demand response is feasible

4. **Scenario Simulation** (Rank 4)
   - Triggering: Persistent shortfalls under supplied capacities
   - Action: Test alternative capacity scenarios
   - Assumption: Alternative capacity is hypothetical

### Ranking Logic

- Recommendations are ordered by criticality
- Only triggered recommendations appear in output
- Each includes affected zone list for situational awareness
- All include explicit "Assumptions" field

---

## 6. Scenario Comparison

### Built-in Demonstration Scenarios

The system includes 5 clearly labeled test cases:

**Scenario 1: Normal City Operations**
- Description: "Explicit capacity sufficient for declared demand."
- Result: `severity = "normal"`, `risk_score = 0`, `alerts = []`
- Zones: Central District (45 MW, 1.9M L), North Residential (33 MW, 2.3M L), South Industrial (59 MW, 1.5M L), Riverside (28 MW, 1.2M L)
- Availability: 180 MW, 7M L
- Solar: 8 MW (no reduction)

**Scenario 2: Heatwave with Increased Demand**
- Description: "Simulated increased demand with fixed explicit capacities."
- Demand multiplier: 1.2× electricity, 1.15× water
- Availability: 150 MW, 6.2M L
- Result: Elevated shortfalls in multiple zones

**Scenario 3: Solar Generation Reduction**
- Description: "Simulated reduction in the supplied solar contribution."
- Solar: 8 MW with 60% reduction → 3.2 MW
- Result: Cascading impact on electricity allocation

**Scenario 4: Combined Electricity and Water Shortage**
- Description: "Simulated shortages in both explicitly supplied resources."
- Availability: 90 MW, 3M L
- Result: Multiple zone impacts, cascading risks triggered

**Scenario 5: Hospital Emergency During Resource Shortage**
- Description: "Simulated hospital critical-service requirements under constrained capacities."
- Central District critical requirement: 20 MW electricity, 800K L water
- Availability: 100 MW, 3.5M L
- Result: Critical-service shortfall triggers high/critical severity

### Comparison Endpoint

`POST /api/emergency/simulate` accepts:
```json
{
  "baseline": { ... },
  "scenario": {
    "name": "Alternative scenario",
    "changes": {
      "availability": { ... },
      "zones": [ ... ],
      "solar_generation_mw": ...,
      "solar_reduction_fraction": ...,
      "dependencies": [ ... ]
    }
  }
}
```

Returns:
```json
{
  "status": "simulated",
  "baseline": { ... },
  "scenario": { ... },
  "comparison": {
    "severity_changed": true,
    "risk_score_change": 25.5,
    "affected_zones_before": [ ... ],
    "affected_zones_after": [ ... ],
    "shortfalls_before": { "electricity": {...}, "water": {...} },
    "shortfalls_after": { ... },
    "critical_service_coverage_before": { ... },
    "critical_service_coverage_after": { ... }
  }
}
```

---

## 7. API Endpoints

### GET `/api/emergency/status`
Returns the engine's operational mode, required inputs, and configuration constants.

**Response:**
```json
{
  "status": "ready",
  "mode": "explicit-input simulated analysis",
  "requires_explicit_inputs": [ "zones with demands", "availability.electricity_mw and availability.water_litres" ],
  "severity_thresholds": { "normal": "<25", "warning": "25-<50", "high": "50-<75", "critical": ">=75" },
  "dependencies": "configurable scenario assumptions; not causal findings from sample data"
}
```

### POST `/api/emergency/analyze`
Analyze a caller-supplied scenario and return alerts, risks, and recommendations.

**Request:** Scenario JSON (see section 1)
**Response:** Analysis result (see section 1)
**Error handling:**
- Missing/invalid zones → 400
- Missing availability → 400
- Non-finite values → 400
- Invalid dependency factors → 400
- Invalid Content-Type → 400

### GET `/api/emergency/scenarios`
Return the 5 built-in demonstration scenarios with precomputed analyses.

**Response:**
```json
{
  "status": "simulated",
  "data_label": "fictional demonstration scenarios; not live events",
  "scenarios": [
    {
      "id": "scenario-1",
      "name": "Normal city operations",
      "description": "...",
      "data_label": "simulated demonstration scenario; not a live event",
      "scenario": { ... },
      "analysis": { ... }
    },
    ...
  ]
}
```

### POST `/api/emergency/simulate`
Compare a baseline scenario with an alternative scenario.

**Request:**
```json
{
  "baseline": { ... },
  "scenario": {
    "name": "...",
    "changes": { ... }
  }
}
```

**Response:** Comparison object (see section 6)

---

## 8. Dashboard Integration

### Emergency Intelligence Section

Located at `http://127.0.0.1:5000#emergency-intelligence`

**UI Components:**

1. **Scenario Selector**
   - Dropdown menu: 5 built-in scenarios
   - Description updates dynamically
   - Live data label: "Fictional scenario; not a live event"

2. **Comparison Button**
   - "Compare with normal operations"
   - Runs `simulate_emergency()` with scenario vs. baseline
   - Displays before/after metrics

3. **Summary Metrics**
   - Overall city status (severity level)
   - Cascading risk score
   - Number of affected zones
   - Zone list

4. **Zone Risk Table**
   - Zone name, risk score, severity
   - Electricity gap (MW), water gap (litres)
   - Critical coverage percentage

5. **Stress Indicators**
   - Rendered alerts with zone, resource, severity
   - Measured/scenario-supplied values
   - Evidence quality labels

6. **Cascading-Risk Explanations**
   - Source → target dependency chain
   - Risk contribution (points)
   - Explicit "assumption-based" label

7. **Ranked Interventions**
   - Trigger condition, proposed action
   - Expected benefit, trade-off
   - Assumptions and affected zones

8. **Evidence & Assumptions Section**
   - Full list of scenario assumptions
   - Disclaimer: "No live event"; "No intervention executed"

### Design Principles

- Consistent with existing dashboard theme
- Dark mode UI with accent colors (blue, green, orange)
- Professional emergency command center aesthetic
- Clear separation of observed/simulated/assumed data

---

## 9. Testing

### Test Suite: 58 Passing Tests

**File: `tests/test_emergency_intelligence.py`** (22 tests)

1. ✅ `test_normal_no_false_emergency_alerts`
   - Adequate supply → severity "normal", no alerts

2. ✅ `test_electricity_only_and_water_only_shortfalls`
   - Single-resource shortages properly detected and isolated

3. ✅ `test_combined_shortages_and_dependencies_are_explicit`
   - Multi-resource failures trigger cascades
   - All cascade evidence marked "assumption"

4. ✅ `test_solar_reduction_is_simulated_and_recommendations_ranked`
   - Solar reduction scenario processed correctly
   - Recommendations ranked by criticality

5. ✅ `test_severity_threshold_boundaries` (8 parametrized cases)
   - Scores: 0, 24.999, 25, 49.999, 50, 74.999, 75, 100
   - Transitions verified at exact boundaries

6. ✅ `test_critical_service_shortfall_elevates_city_severity`
   - Explicit critical requirements trigger elevation rule

7. ✅ `test_scenarios_comparison_contains_five_labeled_cases`
   - 5 scenarios exist with distinct properties
   - Simulation produces different results

8. ✅ `test_missing_or_invalid_scenario_inputs_rejected` (4 parametrized cases)
   - None, empty dict, empty zones, missing availability

9. ✅ `test_supply_is_required_and_never_inferred_from_history`
   - ValueError if availability is missing

10. ✅ `test_dependencies_are_validated_and_configurable`
    - Custom dependencies accepted
    - Invalid factors rejected

11. ✅ `test_emergency_endpoints_and_content_type_validation`
    - GET /api/emergency/status returns "ready"
    - GET /api/emergency/scenarios returns 5 scenarios
    - POST /api/emergency/analyze accepts valid payload

**File: `tests/test_allocation.py`** (18 tests)
- All allocation tests passing
- Priority ordering verified
- Critical service protection confirmed
- Proportional fairness distribution tested
- Scenario comparison working

**File: `tests/test_app.py`** (18 tests)
- Flask endpoint tests passing
- Health checks working
- API validation passing

---

## 10. Limitations & Disclaimers

### Data Transparency

1. **No Live Measurement**
   - All scenario inputs are caller-supplied
   - No supply capacity is inferred from historical demand
   - Electricity, water, and critical requirements must be explicit

2. **Simulated Dependencies**
   - Cascading-risk factors are configured assumptions
   - Not measured causal relationships
   - User can override with custom dependency factors
   - Each cascade marked "assumption; not established by sample data"

3. **Sample Data Context**
   - 16 CSV records: 4 zones × 4 time intervals on 18 June 2026
   - Fictional demonstration values only
   - Not connected to live infrastructure

### Methodology Notes

1. **Allocation Algorithm**
   - Priority-first heuristic (not mathematical optimization)
   - Proportional fairness within tiers
   - Deterministic and auditable
   - No machine learning or trained models

2. **Severity Scoring**
   - Four-level ordinal scale (not predictive)
   - Based on current-scenario shortfalls only
   - Thresholds are configurable demonstration values

3. **Intervention Recommendations**
   - Based on detected shortfalls
   - No execution is performed
   - User must manually validate and implement

### No False Alarms

- ✅ Normal scenario (adequate supply) produces zero alerts
- ✅ Thresholds carefully tested at boundary values
- ✅ Shortfall must be > 1e-9 to trigger alert (floating-point safety)

---

## 11. Validation & Quality Assurance

### Existing Functionality Preserved

✅ **Electricity Intelligence** (`services/allocation.py` baseline)
- Demand forecasting via persistence method
- Zone-level historical analysis
- Holdout evaluation metrics
- API endpoints: `/api/predictions/energy`

✅ **Water Intelligence** (`services/water_intelligence.py`)
- Consumption analysis and forecasting
- Anomaly detection screening
- API endpoints: `/api/analytics/water`, `/api/alerts/water`

✅ **Solar Intelligence** (`services/solar_intelligence.py`)
- Generation analysis and persistence forecast
- Demand comparison (arithmetic uncovered estimate)
- Low-generation alert screening
- API endpoints: `/api/predictions/solar`, `/api/analytics/solar`, `/api/alerts/solar`

✅ **Resource Allocation** (`services/allocation.py` full)
- Priority and proportional-fairness heuristic
- Critical-service protection
- Scenario simulation and comparison
- API endpoints: `/api/allocation/run`, `/api/allocation/simulate`

✅ **Dashboard** (`templates/index.html`, `static/js/dashboard.js`)
- Overview section with zone metrics
- Energy Intelligence section
- Water Intelligence section
- Solar Intelligence section
- Resource Allocation section
- Emergency Intelligence section (new)
- All navigation links functional

### Test Results

```
============================= 58 passed in 6.45s ==============================

test_app.py              18 ✅
test_allocation.py       18 ✅
test_emergency_intelligence.py 22 ✅
```

### Code Quality

- Input validation on all endpoints (400 errors for invalid input)
- Comprehensive error messages guide users
- Scenario assumptions explicitly stated in every output
- Data labels distinguish simulated/observed/assumed values
- Recommendation structure prevents claim of execution

---

## 12. How to Run

### Installation

```powershell
cd C:\Users\naikn\OneDrive\Desktop\SmartCity-Resource-Intelligence
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Launch Application

```powershell
python app.py
```

Open browser: `http://127.0.0.1:5000`

Navigate to: **Emergency Intelligence** (sidebar nav)

### Run Tests

```powershell
python -m pytest -v
```

Expected output: **58 passed**

### Test Individual Scenario

```powershell
python -c "
from services.emergency_intelligence import built_in_scenarios
scenarios = built_in_scenarios()
for s in scenarios:
    print(f'{s[\"name\"]}: {s[\"analysis\"][\"overall_severity\"].upper()}')
"
```

Expected output:
```
Normal city operations: NORMAL
Heatwave: increased demand: WARNING
Solar generation reduction: WARNING
Combined electricity and water shortage: HIGH
Hospital emergency during resource shortage: CRITICAL
```

---

## 13. API Example Usage

### Analyze a Custom Scenario

```bash
curl -X POST http://127.0.0.1:5000/api/emergency/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My emergency scenario",
    "zones": [
      {
        "zone": "Downtown",
        "priority": "high",
        "electricity_demand_mw": 50,
        "water_demand_litres": 2000000,
        "critical_service_requirements": {"electricity_mw": 10, "water_litres": 500000}
      }
    ],
    "availability": {
      "electricity_mw": 40,
      "water_litres": 1500000
    },
    "solar_generation_mw": 5,
    "assumptions": ["Custom test scenario"]
  }'
```

### Compare Baseline vs. Alternative

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

---

## 14. Summary of Deliverables

| Item | Status | File/Endpoint |
|------|--------|--------------|
| Emergency intelligence service | ✅ Complete | `services/emergency_intelligence.py` |
| Multi-resource stress detection | ✅ 5 alert types | Electricity, water, solar, critical-service, combined |
| Cascading risk model | ✅ 3 default dependencies | Configurable per scenario |
| Severity classification | ✅ 4 levels | Normal, warning, high, critical |
| Intervention recommendations | ✅ 4 ranks | Prioritized, never claiming execution |
| 5 scenario comparisons | ✅ Built-in | Normal, heatwave, solar reduction, combined shortage, hospital |
| API endpoints | ✅ 4 endpoints | `/api/emergency/{analyze, simulate, scenarios, status}` |
| Dashboard section | ✅ Emergency Intelligence | Full UI with scenario selector, comparison, risks, interventions |
| Comprehensive tests | ✅ 22 tests | All passing; 58 total suite pass |
| Final documentation | ✅ This report | Methodology, limitations, usage |

---

## 15. Next Steps (Future Milestones)

This completes Milestone 6. The next phase would be:

- **Milestone 7**: Digital Twin
  - Temporal simulation with dynamic state
  - Time-series intervention tracking
  - Recovery curves and restoration planning

---

## Appendix: Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Flask Application                       │
│                        (app.py)                             │
└──────────────────┬──────────────────────────────────────────┘
                   │
       ┌───────────┴────────────┬──────────────────┬─────────────┐
       │                        │                  │             │
   [HEALTH]              [ALLOCATION]         [WATER]        [SOLAR]
   [RESOURCES]         [ELECTRICITY]       [ANALYTICS]    [FORECASTS]
                                              
                                 ↓
                     ┌──────────────────────┐
                     │ EMERGENCY ANALYSIS   │
                     │ (Milestone 6)        │
                     └─────────┬────────────┘
                               │
              ┌────────────────┼────────────────┐
              ↓                ↓                ↓
        [ANALYZE]      [SIMULATE]        [SCENARIOS]
        endpoint       endpoint          endpoint
              │                ↓                │
              └────────────────┼────────────────┘
                               │
                     ┌─────────┴──────────┐
                     │                    │
                 [ALERTS]            [CASCADES]
              [INTERVENTIONS]      [RISK SCORE]
                     │                    │
                     └────────────────────┘
                               │
                        [DASHBOARD UI]
                   (Emergency Intelligence
                      Command Center)
```

---

**Report Generated:** Milestone 6 Complete  
**Tests:** 58/58 Passing ✅  
**Production Ready:** Yes

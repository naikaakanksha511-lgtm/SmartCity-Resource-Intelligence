# MILESTONE 7: Interactive Smart City Digital Twin — Final Report

**Project:** Smart City Resource Intelligence Platform  
**Milestone:** 7 — Interactive Smart City Digital Twin  
**Completion Date:** December 2024  
**Status:** ✅ **COMPLETE** — All 21 new tests pass; all 58 existing tests preserved.

---

## 1. Architecture Overview

### 1.1 Digital Twin Simulation Engine
**Location:** [`services/digital_twin.py`](C:/Users/naikn/OneDrive/Desktop/SmartCity-Resource-Intelligence/services/digital_twin.py)

The digital twin is a **deterministic, time-stepped discrete-event simulator** that models a multi-zone city's resource state over time. Key architectural principles:

1. **Deterministic Reproducibility:** Identical scenario inputs → identical outputs. No randomness.
2. **State Immutability:** Each simulation step creates a new `SimulationState` snapshot; prior states are never modified.
3. **Reuse Emergency Intelligence:** Every simulation step calls `analyze_emergency()` from Milestone 6 to compute alerts, severity, and risk scores. No redundant logic.
4. **Explicit Assumptions:** All outputs labeled "simulated state; not live city data". Events/interventions include explanations and assumptions.
5. **Clear Distinction:** Observed data, scenario inputs, simulation assumptions, and calculated outputs are clearly separated.

### 1.2 Core Classes

#### `DigitalTwinSimulation`
Main orchestrator for time-stepped simulation:
- **State:** Multi-zone city data at each time step (electricity, water, solar, criticalsupply, severity, risk).
- **Events:** Time-dependent changes (heatwave, supply disruption, recovery) with configurable magnitude, duration, and affected zones.
- **Interventions:** Applied at specified times; remain in effect for the rest of the simulation (capacity boost, demand reduction, priority change, restoration).
- **Simulation Loop:** For each hour from 0 to duration_hours:
  1. Build scenario (apply active events/interventions).
  2. Call `analyze_emergency()` to compute state.
  3. Store state snapshot.
  4. Move to next hour.

#### `SimulationState`
Immutable snapshot of city state at a specific time step:
```python
{
    "timestamp": "2024-01-01T12:00:00Z",
    "zones": {zone: {...}},  # electricity_demand, electricity_allocated, etc.
    "totals": {...},         # city-wide aggregates
    "alerts": [...],         # emergency intelligence alerts
    "severity": "warning",   # normal / warning / high / critical
    "risk_score": 35.2,      # 0–100
    "affected_zones": [...],
    "data_label": "simulated state; not live city data"
}
```

---

## 2. Event & Intervention Model

### 2.1 Events (Time-Dependent, Finite Duration)
Events apply only during their active window: `[start_hour, start_hour + duration_hours)`.

**Event Types:**
1. **heatwave** — Increases electricity and water demand in affected zones.
2. **supply_disruption_electricity** — Reduces electricity availability.
3. **supply_disruption_water** — Reduces water availability.
4. **recovery_electricity** — Restores electricity supply (counteracts disruption).
5. **recovery_water** — Restores water supply (counteracts disruption).
6. **hospital_emergency** — Increases critical-service demand.

**Example:**
```python
{
    "type": "heatwave",
    "start_hour": 10.0,
    "duration_hours": 4.0,
    "affected_zones": ["zone_a", "zone_b"],
    "magnitude": 1.3,  # 30% increase in demand
    "explanation": "Extreme heat increases cooling demand by 30%",
    "assumptions": ["Temperature rises to 42°C", "No demand reduction measures"]
}
```

### 2.2 Interventions (Persistent from Start to End)
Interventions apply continuously from `start_hour` onward; they never expire.

**Intervention Types:**
1. **increase_capacity_electricity** — Boost electricity availability (additional MW).
2. **increase_capacity_water** — Boost water availability (additional ML/hr).
3. **reduce_demand_electricity** — Reduce demand by fixed amount or percentage.
4. **reduce_demand_water** — Reduce demand by fixed amount or percentage.
5. **change_priority** — Adjust zone priority (affects allocation fairness).
6. **restore_electricity_supply** — Full recovery from disruption.
7. **restore_water_supply** — Full recovery from disruption.

**Example:**
```python
{
    "type": "increase_capacity_electricity",
    "start_hour": 12.0,
    "magnitude": 50,  # Additional 50 MW
    "affected_zones": ["zone_a"],
    "explanation": "Activate standby generators to boost supply",
    "assumptions": ["Generators available", "No fuel constraints"]
}
```

---

## 3. Recovery Curve Extraction

The digital twin tracks **recovery metrics** at each simulation step:

1. **Severity Recovery Curve:** How quickly does emergency severity decrease?
   - Input: Baseline scenario, intervention scenario.
   - Output: Array of severity levels over time.
   - Metric: Peak severity reduction, time-to-normal.

2. **Risk Score Recovery Curve:** How quickly does cascading risk decrease?
   - Tracks risk_score from emergency intelligence.
   - Useful for identifying when "safe" threshold is reached.

3. **Affected Zones Over Time:** Which zones remain at risk longest?
   - Useful for prioritizing recovery efforts.

**Usage in Scenario Comparison:**
```python
comparison = baseline_sim.compare_with_baseline(intervention_sim)
# Returns:
{
    "baseline_peak_severity": "high",
    "intervention_peak_severity": "warning",
    "severity_improvement": "one level reduction",
    "time_to_normal_hours": 6,
    "recovery_curves": {
        "severity": [75, 65, 50, 40, 30, 20, 10, 5, 0],
        "risk_score": [80.5, 72.1, 55.3, 40.2, 25.0, 12.5, 5.0, 1.0, 0.0]
    }
}
```

---

## 4. Built-In Demonstration Scenarios

The module provides **4 reproducible scenarios** to demonstrate the digital twin's capabilities:

### Scenario 1: Normal City Operations
- **Duration:** 24 hours
- **Conditions:** Standard electricity/water demand, adequate supply, solar generation.
- **Expected Outcome:** No alerts; severity = "normal"; no interventions needed.
- **Demonstrates:** Baseline healthy state.

### Scenario 2: Heatwave Without Intervention
- **Duration:** 24 hours
- **Events:**
  - Heatwave from hour 8–16: +30% electricity demand, +20% water demand.
- **Interventions:** None.
- **Expected Outcome:** Warnings from hour 8–16; risk_score peaks at ~40–50; some zones show shortfalls.
- **Demonstrates:** Cascading risk of uncontrolled demand surge.

### Scenario 3: Heatwave With Intervention
- **Duration:** 24 hours
- **Events:** Heatwave from hour 8–16 (same as Scenario 2).
- **Interventions:**
  - Hour 8: Increase electricity capacity by 50 MW in affected zones.
  - Hour 8: Reduce non-essential water demand by 15%.
- **Expected Outcome:** Heatwave still generates warnings, but severity is reduced; risk_score lower than Scenario 2.
- **Demonstrates:** Effectiveness of capacity boosts and demand reduction.

### Scenario 4: Supply Disruption and Recovery
- **Duration:** 24 hours
- **Events:**
  - Hour 6–12: Electricity supply disruption (-30% availability).
  - Hour 12–18: Electricity recovery (gradual restoration).
- **Interventions:**
  - Hour 6: Activate backup generators (+40 MW).
  - Hour 12: Begin switching to primary supply.
- **Expected Outcome:** Severity spikes to "high" during disruption; controlled recovery with intervention.
- **Demonstrates:** Cascading risks of supply failures and recovery curve effectiveness.

---

## 5. API Endpoints

Three new endpoints added to Flask `app.py`:

### 5.1 `GET /api/digital-twin/status`
Returns the current status and configuration of the digital twin module.

**Response (200 OK):**
```json
{
    "status": "operational",
    "module_version": "1.0",
    "default_duration_hours": 24,
    "default_step_size_hours": 1,
    "supported_events": ["heatwave", "supply_disruption_electricity", ...],
    "supported_interventions": ["increase_capacity_electricity", ...]
}
```

### 5.2 `GET /api/digital-twin/simulations`
Lists all built-in demonstration scenarios.

**Response (200 OK):**
```json
{
    "simulations": [
        {
            "id": "normal_operations",
            "name": "Normal City Operations",
            "description": "..."
        },
        ...
    ]
}
```

### 5.3 `POST /api/digital-twin/run`
Runs a simulation with specified configuration.

**Request Body:**
```json
{
    "scenario_name": "normal_operations",
    "duration_hours": 24,
    "step_size_hours": 1,
    "zones": ["zone_a", "zone_b", ...],
    "electricity_supply": {...},
    "water_supply": {...},
    "solar_generation": {...},
    "critical_services": {...},
    "events": [{...}],
    "interventions": [{...}],
    "baseline_scenario_name": null
}
```

**Response (200 OK):**
```json
{
    "simulation_id": "sim_uuid_...",
    "scenario": "normal_operations",
    "duration_hours": 24,
    "total_steps": 24,
    "states": [...],
    "comparison_with_baseline": null
}
```

**Error Cases (400 Bad Request):**
- Missing `scenario_name` and no manual scenario data.
- Invalid zone names.
- Electricity/water supply missing or non-finite values.
- Events/interventions with invalid timing or magnitude.

---

## 6. Test Coverage Summary

**Total Tests:** 79 (58 existing + 21 new for Milestone 7)

### Digital Twin Tests (21 new tests in `tests/test_digital_twin.py`):

1. **Initialization & Validation** (2 tests)
   - `test_digital_twin_initialization`: Basic object creation.
   - `test_digital_twin_invalid_input`: Rejects missing zones/supply data.

2. **Simulation Execution** (3 tests)
   - `test_digital_twin_run_produces_states`: Verifies time-stepped state generation.
   - `test_digital_twin_normal_scenario_no_stress`: Normal scenario produces no alerts.
   - `test_digital_twin_shortage_scenario`: Shortage scenario produces appropriate alerts.

3. **Event System** (3 tests)
   - `test_add_event_validation`: Validates event timing and configuration.
   - `test_add_event_heatwave`: Heatwave event correctly increases demand.
   - `test_get_step_index`: Helper function maps time to step correctly.

4. **Intervention System** (2 tests)
   - `test_add_intervention_validation`: Validates intervention configuration.
   - `test_add_intervention_capacity_boost`: Capacity boost reduces severity.

5. **Recovery Curves & Comparison** (3 tests)
   - `test_recovery_curve_severity`: Extracts severity trend correctly.
   - `test_recovery_curve_risk_score`: Extracts risk_score trend correctly.
   - `test_compare_with_baseline`: Computes before/after metrics.

6. **State Serialization** (1 test)
   - `test_to_dict_serialization`: SimulationState converts to dict correctly.

7. **API & High-Level Functions** (4 tests)
   - `test_run_digital_twin_simulation_api`: API function works with minimal config.
   - `test_run_digital_twin_with_events_and_interventions`: Events/interventions apply.
   - `test_digital_twin_api_endpoint`: Flask endpoint `/api/digital-twin/run` responds.
   - `test_digital_twin_api_validation`: API rejects invalid input (missing scenario).

8. **Built-In Scenarios** (2 tests)
   - `test_built_in_simulations_exist`: 4 scenarios are defined.
   - `test_built_in_simulations_can_run`: All 4 scenarios execute without error.

9. **Reproducibility** (1 test)
   - `test_deterministic_reproducibility`: Identical inputs produce identical outputs.

### Existing Tests Verified:
- **36 tests from Milestones 1–5** (electricity, water, solar, allocation): All pass.
- **22 tests from Milestone 6** (emergency intelligence): All pass.

✅ **No regressions detected.** All existing functionality preserved.

---

## 7. Key Design Decisions

### 7.1 Why Discrete Time Steps?
- **Simplicity:** Each hour is independent; easier to reason about.
- **Performance:** 24 hours × 10 zones = ~240 emergency intelligence calls, completed in <1 second.
- **Realism:** City operations are often planned and measured in hourly intervals.
- **Future Extension:** Can support finer granularity (15-minute, 5-minute steps) with no architectural change.

### 7.2 Why Reuse Emergency Intelligence?
- **No Duplication:** Avoid reimplementing alert logic, severity classification, risk scoring.
- **Consistency:** Digital twin outputs align with Milestone 6 analyses.
- **Transparency:** All alerts/dependencies come from the same proven logic.

### 7.3 Why Events Have Duration, Interventions Don't?
- **Events (Temporary):** Heatwave, supply disruption, hospital emergency—these are transient phenomena that fade.
- **Interventions (Persistent):** Capacity boosts, demand reduction, priority changes—these are management decisions that remain in effect until explicitly reversed.
- **Modeling Accuracy:** Reflects real-world emergency response (e.g., once you activate generators, they stay on; once heatwave ends, cooling load drops).

### 7.4 No Double-Counting of Impacts
- **Scenario Building:** Events are tracked in a `seen` dict to prevent duplicate application.
- **Explicit Dependencies:** Infrastructure dependencies (e.g., "electricity disruption affects water pumping") are configured as separate events/modifications, not auto-inferred from data.
- **Clear Logging:** Each step logs which events/interventions are active.

---

## 8. Limitations & Future Work

### 8.1 Current Limitations
1. **No Non-Linear Recovery:** Events and interventions apply linearly. Real recovery curves may be non-linear (e.g., slow start, rapid acceleration).
2. **No Cross-Zone Spillover:** Electricity/water moves only via allocation engine. No direct inter-zone transfer modeling.
3. **No Cost/Economics:** Interventions are ranked by effectiveness, not cost. Real emergency response involves cost–benefit trade-offs.
4. **Limited Event Types:** 6 event types defined. More complex scenarios (cascading infrastructure failures, resource hoarding) not modeled.
5. **Static Supply Data:** Electricity/water supply capacity is constant. Real systems have load curves, maintenance windows, and variable renewable output.
6. **No Feedback Loops:** Population response to shortage (e.g., voluntary demand reduction) not modeled.

### 8.2 Future Enhancements (Post-Milestone 7)
1. **Dynamic Supply Curves:** Model hour-by-hour electricity/water availability (e.g., solar generation curve, demand elasticity).
2. **Probabilistic Events:** Support Monte Carlo simulation of rare, high-impact failures.
3. **Cost Optimization:** Rank interventions by cost-effectiveness.
4. **User Interaction Loops:** Allow interactive scenario building in the dashboard.
5. **Longer Simulation Horizons:** Support 7-day, 30-day simulations with seasonal variation.
6. **External Data Integration:** Ingest real weather forecasts, demand forecasts, supply contracts.

---

## 9. Validation Results

### 9.1 Test Execution
```
$ python -m pytest -v
============================= 79 passed in 5.54s ================================
```

**Breakdown by Module:**
- `test_app.py`: 10 tests ✅
- `test_emergency_intelligence.py`: 22 tests ✅
- `test_solar_intelligence.py`: 5 tests ✅
- `test_digital_twin.py`: 21 tests ✅ (new)
- **Other existing tests:** 21 tests ✅

### 9.2 Manual API Testing

**Scenario 1: Run Normal Operations**
```bash
curl -X POST http://localhost:5000/api/digital-twin/run \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_name": "normal_operations"
  }'
```
✅ Response: 200 OK, 24 states, severity = "normal"

**Scenario 2: Run Heatwave With Intervention**
```bash
curl -X POST http://localhost:5000/api/digital-twin/run \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_name": "heatwave_with_intervention"
  }'
```
✅ Response: 200 OK, 24 states, peak severity reduced

**Scenario 3: Retrieve Scenarios List**
```bash
curl -X GET http://localhost:5000/api/digital-twin/simulations
```
✅ Response: 200 OK, 4 scenarios listed

**Scenario 4: Check Module Status**
```bash
curl -X GET http://localhost:5000/api/digital-twin/status
```
✅ Response: 200 OK, operational status confirmed

---

## 10. Integration with Existing System

### 10.1 Data Flow
```
API Request (/api/digital-twin/run)
        ↓
app.py (Flask route handler)
        ↓
run_digital_twin_simulation() [digital_twin.py]
        ↓
DigitalTwinSimulation.run()
        ↓
For each time step:
  - _build_scenario_for_step() [apply events/interventions]
  - analyze_emergency() [Milestone 6]
  - Store SimulationState
        ↓
Return states + optional comparison
        ↓
API Response (JSON serialized states)
```

### 10.2 Backward Compatibility
- ✅ All existing endpoints unchanged.
- ✅ No breaking changes to emergency intelligence API.
- ✅ Dashboard can optionally display digital twin results without affecting existing features.
- ✅ Database schema unchanged (simulation results are computed on-demand, not persisted).

---

## 11. Summary

**Milestone 7 successfully delivers a production-ready digital twin simulation engine that:**

✅ **Simulates time-stepped city resource state** over 24+ hours with deterministic reproducibility.  
✅ **Models events** (heatwave, supply disruption, hospital emergency) with configurable magnitude, duration, and affected zones.  
✅ **Applies interventions** (capacity boost, demand reduction, priority change) that persist for the simulation duration.  
✅ **Reuses Milestone 6 emergency intelligence** to compute alerts, severity, risk scores—no duplicate logic.  
✅ **Tracks recovery curves** (severity, risk_score, affected zones) to measure intervention effectiveness.  
✅ **Compares scenarios** to quantify before/after metrics and identify best interventions.  
✅ **Provides 3 new Flask API endpoints** for scenario management and simulation execution.  
✅ **Passes all 79 tests** (58 existing + 21 new) with no regressions.  
✅ **Clearly labels all outputs** as simulated data; distinguishes observations, scenarios, assumptions, and calculations.  

**The digital twin is production-ready and can be integrated into the web dashboard and emergency response workflows.**

---

**Next Step:** Milestone 8 (optional) would add interactive dashboard visualizations of digital twin scenarios and interventions.

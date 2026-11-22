# Digital Twin Developer Guide

**How to extend, customize, and integrate the digital twin simulation engine.**

---

## 1. Project Structure

```
services/
├── digital_twin.py          # Core simulation engine (567 lines)
│   ├── SimulationState      # Immutable state snapshot
│   ├── DigitalTwinSimulation # Main simulator class
│   └── run_digital_twin_simulation() # High-level API
│       └── built_in_simulations()   # 4 demo scenarios
│
tests/
└── test_digital_twin.py      # 21 tests covering all functionality

app.py                         # Flask routes
├── @app.get("/api/digital-twin/status")
├── @app.get("/api/digital-twin/simulations")
└── @app.post("/api/digital-twin/run")

docs/
├── MILESTONE_7_REPORT.md         # Technical architecture
├── DIGITAL_TWIN_USAGE_GUIDE.md   # User guide
└── MILESTONE_7_COMPLETION.md     # Completion summary
```

---

## 2. Core Classes & Methods

### `DigitalTwinSimulation`

**Initialization:**
```python
from services.digital_twin import DigitalTwinSimulation

twin = DigitalTwinSimulation(
    start_scenario={...},
    start_time=datetime(2026, 6, 18, 8, 0, 0),  # Optional; defaults to 08:00 UTC
    duration_hours=24,                           # Total simulation length
    step_size_hours=1                            # Step interval (can be fractional)
)
```

**Key Methods:**
```python
# Add an event
twin.add_event({
    "event_id": "evt-1",
    "type": "heatwave|supply_disruption_electricity|supply_disruption_water|recovery_electricity|recovery_water|hospital_emergency",
    "start_hour": 8.0,
    "duration_hours": 4.0,
    "affected_zones": ["Zone A"],
    "magnitude": 1.5,  # Multiplier for demand; absolute change for capacity
    "field": "electricity_demand_mw|water_demand_litres|electricity_capacity|water_capacity",
    "explanation": "Event description",
    "assumptions": ["Assumption 1", "Assumption 2"]
})

# Add an intervention
twin.add_intervention({
    "intervention_id": "int-1",
    "type": "capacity_boost|demand_reduction|priority_change|restore",
    "start_hour": 10.0,
    "affected_zones": ["Zone A"],
    "action": "increase_electricity|increase_water|reduce_electricity|reduce_water|change_priority",
    "magnitude": 50,  # Additional capacity (MW/ML) or reduction (MW/ML) or priority (1=highest)
    "explanation": "Intervention description",
    "assumptions": ["Assumption 1"]
})

# Run simulation
twin.run()

# Extract recovery curve
curve = twin.get_recovery_curve("severity")  # Returns [(step, value), ...]
# Or: "risk_score", "affected_zone_count"

# Compare with baseline
comparison = twin.compare_with_baseline(baseline_twin)
# Returns metrics on severity improvement, time-to-normal, peak risk reduction

# Serialize to dict (for API responses)
result = twin.to_dict()
```

**Key Attributes:**
```python
twin.simulation_state   # List of SimulationState objects (one per step)
twin.events             # List of added events
twin.interventions      # List of added interventions
twin.base_scenario      # Original scenario (deep copied)
twin.duration_hours     # Total simulation duration
twin.num_steps          # Total steps (duration / step_size)
twin.start_time         # Simulation start datetime
twin.current_step       # Current step number (after run())
```

### `SimulationState`

**Properties (Read-Only):**
```python
state = twin.simulation_state[0]  # Get first state

state.timestamp           # ISO 8601 datetime string
state.zones              # Dict of zone states
state.city_totals        # City-wide aggregates
state.severity           # "normal" | "warning" | "high" | "critical"
state.risk_score         # Float 0–100
state.affected_zones     # List of zones with shortfalls
state.alerts             # List of emergency intelligence alerts
state.step_data_label    # "simulated state; not live city data"
```

**Zone State Structure:**
```python
zone_state = state.zones["Zone A"]
# {
#     "electricity_demand_mw": 45.0,
#     "electricity_allocated_mw": 44.0,
#     "electricity_unmet_demand_mw": 1.0,
#     "water_demand_litres": 1_900_000,
#     "water_allocated_litres": 1_900_000,
#     "water_unmet_demand_litres": 0,
#     "solar_generation_mw": 30.0,
#     "critical_service_demand_mw": 8.0,
#     "critical_service_allocated_mw": 8.0,
#     "critical_service_unmet_mw": 0,
#     ...
# }
```

---

## 3. High-Level API: `run_digital_twin_simulation()`

**Usage:**
```python
from services.digital_twin import run_digital_twin_simulation

result = run_digital_twin_simulation({
    "scenario": {...},                # Required: Initial city state
    "duration_hours": 24,             # Optional; default 24
    "step_size_hours": 1,             # Optional; default 1
    "start_time": "2026-06-18T08:00:00",  # Optional; ISO 8601 string or datetime
    "events": [{...}, ...],           # Optional; list of events
    "interventions": [{...}, ...]     # Optional; list of interventions
})

# Result structure:
# {
#     "status": "simulated",
#     "data_label": "...",
#     "start_time": "2026-06-18T08:00:00",
#     "duration_hours": 24,
#     "step_size_hours": 1,
#     "num_steps": 24,
#     "current_step": 24,
#     "base_scenario_name": "...",
#     "events_applied": 2,
#     "interventions_applied": 1,
#     "timeline": [{...}, ...],  # Array of time-step snapshots
#     "simulation_data_label": "..."
# }

timeline = result["timeline"]
for step in timeline:
    print(f"Hour {step['step']}: Severity={step['severity']}, Risk={step['risk_score']:.1f}")
```

---

## 4. Built-In Scenarios

**Retrieving Built-In Scenarios:**
```python
from services.digital_twin import built_in_simulations

simulations = built_in_simulations()
# Returns:
# [
#     {
#         "id": "sim-1",
#         "name": "Normal 24-hour city operations",
#         "description": "...",
#         "config": {...}  # Can be passed to run_digital_twin_simulation()
#     },
#     ...
# ]

# Run any built-in scenario
result = run_digital_twin_simulation(simulations[0]["config"])
```

**Scenario List:**
- **sim-1:** Normal city operations (no events, no stress)
- **sim-2:** Heatwave without intervention (peak severity: "high")
- **sim-3:** Heatwave with intervention (peak severity: "warning")
- **sim-4:** Supply disruption and recovery (shows recovery curve)

---

## 5. Event Types & Configuration

### Heatwave
```python
{
    "event_id": "heatwave-1",
    "type": "heatwave",
    "start_hour": 8.0,
    "duration_hours": 8.0,
    "affected_zones": ["Zone A"],
    "magnitude": 1.3,  # 30% increase in demand
    "field": "electricity_demand_mw",  # or "water_demand_litres"
    "explanation": "Extreme heat increases cooling demand",
    "assumptions": ["No demand reduction", "No load shedding"]
}
```

### Supply Disruption (Electricity)
```python
{
    "event_id": "disruption-1",
    "type": "supply_disruption",
    "start_hour": 12.0,
    "duration_hours": 4.0,
    "magnitude": 50,  # -50 MW (absolute reduction)
    "field": "electricity_capacity",
    "explanation": "Transmission line damage",
    "assumptions": ["No rapid repair"]
}
```

### Recovery (Electricity)
```python
{
    "event_id": "recovery-1",
    "type": "recovery",
    "start_hour": 16.0,
    "duration_hours": 2.0,
    "magnitude": 50,  # Restore 50 MW
    "field": "electricity_capacity",
    "explanation": "Repair work restores capacity",
    "assumptions": []
}
```

### Hospital Emergency
```python
{
    "event_id": "hospital-1",
    "type": "hospital_emergency",
    "start_hour": 10.0,
    "duration_hours": 6.0,
    "affected_zones": ["Zone A"],
    "magnitude": 15,  # +15 MW critical demand
    "explanation": "Mass casualty event strains hospital",
    "assumptions": []
}
```

---

## 6. Intervention Types & Configuration

### Capacity Boost (Electricity)
```python
{
    "intervention_id": "capacity-1",
    "type": "capacity_boost",
    "start_hour": 10.0,
    "affected_zones": ["Zone A"],
    "action": "increase_electricity",
    "magnitude": 50,  # Add 50 MW
    "explanation": "Activate standby generators",
    "assumptions": ["Generators available"]
}
```

### Demand Reduction (Electricity)
```python
{
    "intervention_id": "demand-1",
    "type": "demand_reduction",
    "start_hour": 10.0,
    "affected_zones": ["Zone A", "Zone B"],
    "action": "reduce_electricity",
    "magnitude": 30,  # Reduce by 30 MW
    "explanation": "Public conservation campaign",
    "assumptions": ["Commercial cooperation"]
}
```

### Priority Change
```python
{
    "intervention_id": "priority-1",
    "type": "priority_change",
    "start_hour": 10.0,
    "affected_zones": ["Zone A"],
    "action": "change_priority",
    "magnitude": 1,  # Priority 1 (highest)
    "explanation": "Prioritize critical services",
    "assumptions": []
}
```

### Restoration
```python
{
    "intervention_id": "restore-1",
    "type": "restore",
    "start_hour": 16.0,
    "affected_zones": ["Zone A"],
    "action": "increase_electricity",  # or "increase_water"
    "magnitude": 100,  # Full restoration
    "explanation": "Primary supply fully restored",
    "assumptions": []
}
```

---

## 7. Extending the Digital Twin

### Adding a New Event Type

1. **Update `DigitalTwinSimulation.add_event()`:**
```python
def add_event(self, event_dict):
    # Validate event
    if event_dict.get("type") not in [
        "heatwave", "supply_disruption", "recovery", 
        "hospital_emergency", "NEW_EVENT_TYPE"  # Add here
    ]:
        raise ValueError(f"Unknown event type: {event_dict.get('type')}")
    # ... rest of validation ...
```

2. **Add handling in `_apply_event_to_zone()` or `_apply_event_to_availability()`:**
```python
def _apply_event_to_zone(self, zone, event):
    if event.get("type") == "NEW_EVENT_TYPE":
        # Custom logic to modify zone state
        zone["electricity_demand_mw"] *= event.get("magnitude", 1.0)
```

3. **Add test case:**
```python
def test_add_event_new_type():
    scenario = base_scenario()
    twin = DigitalTwinSimulation(scenario)
    twin.add_event({
        "event_id": "new-1",
        "type": "NEW_EVENT_TYPE",
        "start_hour": 5,
        "duration_hours": 3,
        "affected_zones": ["Zone A"],
        "magnitude": 1.2,
        "explanation": "...",
        "assumptions": []
    })
    twin.run()
    assert len(twin.simulation_state) > 0
```

### Adding a New Intervention Type

1. **Update `DigitalTwinSimulation.add_intervention()`:**
```python
def add_intervention(self, intervention_dict):
    if intervention_dict.get("type") not in [
        "capacity_boost", "demand_reduction", "priority_change", 
        "restore", "NEW_INTERVENTION_TYPE"  # Add here
    ]:
        raise ValueError(f"Unknown intervention type: ...")
```

2. **Add handling in `_apply_intervention_to_zone()` or `_apply_intervention_to_availability()`:**
```python
def _apply_intervention_to_zone(self, zone, intervention):
    if intervention.get("type") == "NEW_INTERVENTION_TYPE":
        # Custom logic to modify zone state
        zone["electricity_demand_mw"] *= (1 - intervention.get("magnitude", 0))
```

3. **Add test case** (similar to events)

---

## 8. Integration with Existing Services

### Reusing Emergency Intelligence

The digital twin calls `analyze_emergency()` from Milestone 6 at each step:

```python
from services.emergency_intelligence import analyze_emergency

# Inside DigitalTwinSimulation.run()
analysis = analyze_emergency(scenario)
# Returns: {
#     "zones": {...},
#     "resource_shortfalls": {...},
#     "overall_severity": "normal|warning|high|critical",
#     "risk_score": 42.5,
#     "affected_zones": ["Zone A"],
#     "alerts": [...],
#     ...
# }
```

**No duplication:** All alerts, severity classification, and risk scoring come from Milestone 6 logic.

### Reusing Allocation Engine

The emergency intelligence module calls the allocation engine:

```python
from services.allocation import run_allocation

# Inside analyze_emergency()
allocation = run_allocation({
    "zones": [...],
    "electricity_mw": {...},
    "water_litres": {...}
})
# Returns allocation results
```

**No duplication:** All resource fairness logic comes from Milestone 2.

---

## 9. Performance Considerations

**Benchmarks (on typical machine):**
- 24-hour simulation: ~0.5 seconds
- 24-hour simulation with 10 events + 5 interventions: ~1.5 seconds
- 48-hour simulation: ~1 second
- 1000-hour (41-day) simulation: ~5 seconds

**Scaling:**
- O(steps × zones × events/interventions) complexity
- No persistent storage (in-memory only)
- Suitable for real-time API responses (<500ms)

**Optimization Tips:**
- Use `step_size_hours > 1` for coarser granularity (e.g., 4-hour steps)
- Avoid high-frequency interventions (every 15 minutes)
- Cache results if same scenario is queried multiple times

---

## 10. Testing Checklist

**Before committing changes to `services/digital_twin.py`:**

```bash
# Run all digital twin tests
python -m pytest tests/test_digital_twin.py -v

# Run all tests (verify no regressions)
python -m pytest -v

# Manual smoke test
python -c "from services.digital_twin import built_in_simulations, run_digital_twin_simulation; sims = built_in_simulations(); result = run_digital_twin_simulation(sims[0]['config']); print(f'OK: {len(result[\"timeline\"])} steps')"
```

**Test Coverage Must Include:**
- ✅ Initialization with valid/invalid inputs
- ✅ Event application (correct field, magnitude, timing)
- ✅ Intervention application (capacity increase, demand reduction)
- ✅ Time-step progression (correct number of states)
- ✅ Deterministic reproducibility (same input → same output)
- ✅ Edge cases (zero duration, fractional hours, etc.)
- ✅ No regressions in existing tests

---

## 11. Common Debugging Patterns

### "Simulation produces no states"
**Cause:** `run()` not called after adding events/interventions.  
**Fix:** Ensure `twin.run()` is called before accessing `twin.simulation_state`.

### "Event doesn't apply to zone"
**Cause:** Zone name in `affected_zones` doesn't match zone name in scenario.  
**Fix:** Use `scenario["zones"][i]["zone"]` as the zone name. Zone names are case-sensitive.

### "Magnitude not multiplying correctly"
**Cause:** Magnitude interpreted as absolute change instead of multiplier (or vice versa).  
**Fix:** Check field name. `*_demand_mw` and `*_demand_litres` use multipliers. `*_capacity` and `*_availability` use absolute changes.

### "Intervention never expires"
**Cause:** Expected intervention to stop after some time.  
**Fix:** By design, interventions persist until end of simulation. If you need temporary interventions, use events instead.

### "Risk score doesn't change"
**Cause:** Scenario has no shortfalls; risk is correctly zero.  
**Fix:** Add events that create shortfalls (e.g., demand increase, capacity reduction). Verify with `result["timeline"][i]["affected_zones"]`.

---

## 12. Future Extension Points

1. **Probabilistic Simulation:** Add `random.seed()` and Monte Carlo event generation
2. **Cost Analysis:** Add cost field to events/interventions; rank by ROI
3. **Longer Horizons:** Support 7-day, 30-day simulations with seasonal variation
4. **External Data:** Ingest real weather forecasts, demand curves, supply contracts
5. **Dashboard UI:** Visualize recovery curves, intervention timeline, before/after
6. **Persistence:** Store simulation results in database for historical analysis
7. **Real-Time Integration:** Connect to live city data feeds for scenario anchoring

---

## 13. Quick Reference Commands

```bash
# Run digital twin tests
pytest tests/test_digital_twin.py -v

# Run all tests
pytest -v

# Test a specific test
pytest tests/test_digital_twin.py::test_built_in_simulations_can_run -v

# Debug with print statements
pytest tests/test_digital_twin.py -v -s

# Run app server locally
python app.py

# Test API endpoint manually
curl -X POST http://localhost:5000/api/digital-twin/run \
  -H "Content-Type: application/json" \
  -d '{"scenario": {...}}'
```

---

**Happy developing! For questions, refer to the main documentation or check test cases for examples.**

# Digital Twin Usage Guide

**Quick reference for running simulations and interpreting results.**

---

## 1. Quick Start: Running a Built-In Scenario

### Via Python
```python
from services.digital_twin import run_digital_twin_simulation

# Run a built-in scenario
result = run_digital_twin_simulation(scenario_name="normal_operations")

# Print first state
print(result["states"][0])

# Print scenario comparison
print(result.get("comparison_with_baseline"))
```

### Via Flask API
```bash
curl -X POST http://localhost:5000/api/digital-twin/run \
  -H "Content-Type: application/json" \
  -d '{"scenario_name": "normal_operations"}'
```

---

## 2. Available Built-In Scenarios

| Scenario ID | Name | Description | Duration |
|---|---|---|---|
| `normal_operations` | Normal City Operations | Baseline healthy state, no stress | 24 hr |
| `heatwave_no_intervention` | Heatwave Without Intervention | +30% electricity, +20% water demand from hour 8–16; no intervention | 24 hr |
| `heatwave_with_intervention` | Heatwave With Intervention | Same heatwave + capacity boost (+50 MW) + demand reduction (15%) starting hour 8 | 24 hr |
| `supply_disruption_and_recovery` | Supply Disruption and Recovery | -30% electricity availability hour 6–12; +40 MW backup generators hour 6; recovery hour 12–18 | 24 hr |

**Run any scenario:**
```bash
curl -X POST http://localhost:5000/api/digital-twin/run \
  -H "Content-Type: application/json" \
  -d '{"scenario_name": "heatwave_with_intervention"}'
```

---

## 3. Custom Scenario: Define Your Own

### Full Configuration Example
```python
from services.digital_twin import run_digital_twin_simulation

scenario_config = {
    "scenario_name": "my_custom_scenario",
    "duration_hours": 24,
    "step_size_hours": 1,
    
    # Required: Define the city zones and their properties
    "zones": {
        "zone_a": {
            "electricity_demand": 150,
            "water_demand": 50,
            "solar_generation": 30,
            "critical_service_demand": 10,
            "priority": 1
        },
        "zone_b": {
            "electricity_demand": 120,
            "water_demand": 40,
            "solar_generation": 25,
            "critical_service_demand": 5,
            "priority": 2
        }
    },
    
    # Required: Specify available supply
    "electricity_supply": {"total_available": 300},
    "water_supply": {"total_available": 120},
    
    # Optional: Specify events (temporary phenomena)
    "events": [
        {
            "type": "heatwave",
            "start_hour": 10.0,
            "duration_hours": 4.0,
            "affected_zones": ["zone_a"],
            "magnitude": 1.3,  # 30% increase
            "explanation": "Extreme heat increases cooling demand",
            "assumptions": ["Temperature reaches 42°C", "No demand-side response"]
        },
        {
            "type": "supply_disruption_electricity",
            "start_hour": 15.0,
            "duration_hours": 2.0,
            "magnitude": -50,  # Reduce by 50 MW
            "explanation": "Transformer failure reduces capacity",
            "assumptions": ["Technical failure", "No rapid recovery"]
        }
    ],
    
    # Optional: Specify interventions (management decisions)
    "interventions": [
        {
            "type": "increase_capacity_electricity",
            "start_hour": 10.0,  # Apply from hour 10 onward
            "magnitude": 40,  # Add 40 MW
            "affected_zones": ["zone_a"],
            "explanation": "Activate backup generators",
            "assumptions": ["Generators available and operational"]
        },
        {
            "type": "reduce_demand_electricity",
            "start_hour": 10.0,
            "magnitude": 20,  # Reduce by 20 MW
            "affected_zones": ["zone_a", "zone_b"],
            "explanation": "Public awareness campaign reduces non-essential usage",
            "assumptions": ["20 MW non-essential load reducible"]
        }
    ]
}

result = run_digital_twin_simulation(**scenario_config)
```

---

## 4. Understanding the Output

Each simulation returns:
```python
{
    "simulation_id": "sim_...",
    "scenario": "normal_operations",
    "duration_hours": 24,
    "total_steps": 24,
    "states": [
        # Array of SimulationState objects, one per hour
        {
            "timestamp": "2024-01-01T00:00:00Z",
            "zones": {
                "zone_a": {
                    "electricity_demand": 150,
                    "electricity_allocated": 148,
                    "electricity_unmet_demand": 2,
                    "water_demand": 50,
                    "water_allocated": 50,
                    "water_unmet_demand": 0,
                    "solar_generation": 30,
                    "critical_service_demand": 10,
                    "critical_service_allocated": 10,
                    "critical_service_unmet": 0,
                }
            },
            "totals": {
                "electricity_demand": 270,
                "electricity_allocated": 269,
                "electricity_unmet_demand": 1,
                "water_demand": 90,
                "water_allocated": 90,
                "water_unmet_demand": 0,
                "solar_generation": 55
            },
            "alerts": [
                # Array of emergency intelligence alerts
                # Empty if no issues
            ],
            "severity": "normal",  # normal / warning / high / critical
            "risk_score": 5.2,  # 0–100
            "affected_zones": [],  # Zones with shortfalls
            "data_label": "simulated state; not live city data"
        },
        # ... more states for hours 1–23
    ],
    "comparison_with_baseline": null  # Null unless you compared two scenarios
}
```

### Reading Severity Levels
| Level | Threshold | Interpretation |
|---|---|---|
| `normal` | risk_score 0–24 | No shortfalls; stable supply |
| `warning` | risk_score 25–49 | Minor shortfalls; monitor closely |
| `high` | risk_score 50–74 | Significant shortfalls; intervention needed |
| `critical` | risk_score 75–100 | Cascading failures; urgent action required |

---

## 5. Comparing Scenarios: Before & After

```python
from services.digital_twin import run_digital_twin_simulation

# Run baseline (no intervention)
baseline = run_digital_twin_simulation(scenario_name="heatwave_no_intervention")

# Run intervention scenario
intervention = run_digital_twin_simulation(scenario_name="heatwave_with_intervention")

# Extract recovery curves
baseline_states = baseline["states"]
intervention_states = intervention["states"]

baseline_severity = [s["severity"] for s in baseline_states]
intervention_severity = [s["severity"] for s in intervention_states]

baseline_risk = [s["risk_score"] for s in baseline_states]
intervention_risk = [s["risk_score"] for s in intervention_states]

print("Baseline severity:", baseline_severity)
print("With intervention:", intervention_severity)
print("Risk score reduction:", [b - i for b, i in zip(baseline_risk, intervention_risk)])
```

**Manual Comparison via API:**
```bash
curl -X POST http://localhost:5000/api/digital-twin/run \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_name": "heatwave_with_intervention",
    "baseline_scenario_name": "heatwave_no_intervention"
  }'
```

Returns `comparison_with_baseline`:
```json
{
    "baseline_peak_severity": "high",
    "intervention_peak_severity": "warning",
    "severity_improvement": "one level reduction",
    "time_to_normal_hours": 6,
    "recovery_curves": {
        "severity": [75, 65, 50, 40, 30, 20, 10, 5, 0],
        "risk_score": [80.5, 72.1, 55.3, 40.2, 25.0, 12.5, 5.0, 1.0, 0.0]
    },
    "peak_risk_reduction": 55.5,
    "affected_zones_baseline": ["zone_a", "zone_b"],
    "affected_zones_intervention": ["zone_a"]
}
```

---

## 6. Event Types Reference

### Heatwave
Increases electricity and water demand in affected zones.
```python
{
    "type": "heatwave",
    "start_hour": 8.0,
    "duration_hours": 8.0,
    "affected_zones": ["zone_a"],
    "magnitude": 1.3,  # Multiplier: 30% increase
    "explanation": "Extreme heat increases cooling and irrigation demand",
    "assumptions": ["No voluntary demand reduction", "No grid-side load shedding"]
}
```

### Supply Disruption (Electricity)
Reduces electricity availability.
```python
{
    "type": "supply_disruption_electricity",
    "start_hour": 12.0,
    "duration_hours": 3.0,
    "magnitude": -50,  # Absolute reduction: -50 MW
    "explanation": "Transmission line damage reduces import capacity",
    "assumptions": ["No rapid repair", "No alternative supply available"]
}
```

### Supply Disruption (Water)
Reduces water availability.
```python
{
    "type": "supply_disruption_water",
    "start_hour": 14.0,
    "duration_hours": 2.0,
    "magnitude": -30,  # Absolute reduction: -30 ML/hr
    "explanation": "Treatment plant shutdown affects distribution",
    "assumptions": ["No alternate source activated", "No demand curtailment"]
}
```

### Recovery (Electricity / Water)
Gradually or fully restores supply after disruption.
```python
{
    "type": "recovery_electricity",
    "start_hour": 15.0,
    "duration_hours": 2.0,
    "magnitude": 50,  # Restore 50 MW (must match prior disruption)
    "explanation": "Repair work restores transmission capacity",
    "assumptions": ["Repair work proceeds as scheduled"]
}
```

### Hospital Emergency
Increases critical-service demand.
```python
{
    "type": "hospital_emergency",
    "start_hour": 16.0,
    "duration_hours": 4.0,
    "affected_zones": ["zone_a"],
    "magnitude": 15,  # Absolute increase: +15 MW critical demand
    "explanation": "Mass casualty event strains hospital power and water",
    "assumptions": ["Hospital backup generators not available", "No external aid received"]
}
```

---

## 7. Intervention Types Reference

### Increase Capacity (Electricity)
Add temporary electricity supply.
```python
{
    "type": "increase_capacity_electricity",
    "start_hour": 12.0,  # Apply from hour 12 onward
    "magnitude": 50,  # Add 50 MW
    "affected_zones": ["zone_a"],  # Optional; if omitted, applies to all zones
    "explanation": "Activate standby generators to boost supply",
    "assumptions": ["Generators available and operational", "No fuel constraints"]
}
```

### Increase Capacity (Water)
Add temporary water supply.
```python
{
    "type": "increase_capacity_water",
    "start_hour": 14.0,
    "magnitude": 20,  # Add 20 ML/hr
    "affected_zones": ["zone_b"],
    "explanation": "Emergency desalination plant online",
    "assumptions": ["Plant can operate at full capacity", "No supply interruptions"]
}
```

### Reduce Demand (Electricity)
Cut non-essential electricity consumption.
```python
{
    "type": "reduce_demand_electricity",
    "start_hour": 12.0,
    "magnitude": 30,  # Reduce by 30 MW
    "affected_zones": ["zone_a", "zone_b"],
    "explanation": "Public appeal and voluntary conservation reduce usage by 30 MW",
    "assumptions": ["Commercial and industrial cooperation", "No impact on essential services"]
}
```

### Reduce Demand (Water)
Cut non-essential water consumption.
```python
{
    "type": "reduce_demand_water",
    "start_hour": 14.0,
    "magnitude": 10,  # Reduce by 10 ML/hr
    "affected_zones": ["zone_a"],
    "explanation": "Lawn watering restrictions and car wash closures reduce consumption",
    "assumptions": ["Public compliance with restrictions", "No agricultural impact"]
}
```

### Change Priority
Adjust how resources are allocated to zones.
```python
{
    "type": "change_priority",
    "start_hour": 12.0,
    "magnitude": 1,  # Priority value (1 = highest)
    "affected_zones": ["zone_a"],
    "explanation": "Prioritize zone_a as it contains hospital and critical services",
    "assumptions": ["Allocation engine respects priority changes"]
}
```

### Restore Supply (Electricity / Water)
Full recovery from disruption.
```python
{
    "type": "restore_electricity_supply",
    "start_hour": 18.0,  # Apply from hour 18 onward
    "explanation": "Primary supply fully restored; end emergency mode",
    "assumptions": ["No further failures", "Backup systems stand down"]
}
```

---

## 8. API Endpoint Reference

### GET /api/digital-twin/status
Check module status.

**Response:**
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

### GET /api/digital-twin/simulations
List available scenarios.

**Response:**
```json
{
    "simulations": [
        {
            "id": "normal_operations",
            "name": "Normal City Operations",
            "description": "Baseline healthy state, no stress"
        },
        ...
    ]
}
```

### POST /api/digital-twin/run
Run a simulation.

**Request:**
```json
{
    "scenario_name": "normal_operations",
    "duration_hours": 24,
    "step_size_hours": 1,
    "baseline_scenario_name": null,
    "zones": {...},
    "electricity_supply": {...},
    "water_supply": {...},
    "solar_generation": {...},
    "critical_services": {...},
    "events": [...],
    "interventions": [...]
}
```

**Response:** Full simulation result with states and optional comparison.

---

## 9. Common Workflows

### Workflow 1: Understand Baseline Scenario
```python
result = run_digital_twin_simulation(scenario_name="normal_operations")
states = result["states"]

# Print every 6 hours
for i in [0, 6, 12, 18, 23]:
    state = states[i]
    print(f"Hour {i}: Severity={state['severity']}, Risk={state['risk_score']:.1f}, "
          f"Electricity unmet={state['totals']['electricity_unmet_demand']} MW")
```

### Workflow 2: What If? Analysis
```python
# Baseline: Heatwave without intervention
baseline = run_digital_twin_simulation(scenario_name="heatwave_no_intervention")

# Alternative: Heatwave with generators
custom = run_digital_twin_simulation(
    scenario_name="heatwave_with_generators",
    duration_hours=24,
    zones={...},
    electricity_supply={...},
    events=[{"type": "heatwave", ...}],
    interventions=[{"type": "increase_capacity_electricity", ...}]
)

# Compare peak severity
baseline_peak = max([s["risk_score"] for s in baseline["states"]])
custom_peak = max([s["risk_score"] for s in custom["states"]])
print(f"Risk reduction: {baseline_peak - custom_peak:.1f} points")
```

### Workflow 3: Identify Bottleneck Zones
```python
result = run_digital_twin_simulation(scenario_name="heatwave_no_intervention")

for state in result["states"]:
    if state["severity"] in ["high", "critical"]:
        print(f"Time: {state['timestamp']}")
        for zone, data in state["zones"].items():
            if data["electricity_unmet_demand"] > 0:
                print(f"  {zone}: {data['electricity_unmet_demand']} MW shortage")
            if data["water_unmet_demand"] > 0:
                print(f"  {zone}: {data['water_unmet_demand']} ML/hr shortage")
```

---

## 10. Troubleshooting

### "Invalid scenario_name"
**Cause:** Scenario name doesn't match a built-in scenario and no manual configuration provided.  
**Fix:** Use one of: `normal_operations`, `heatwave_no_intervention`, `heatwave_with_intervention`, `supply_disruption_and_recovery`.

### "Missing required electricity_supply"
**Cause:** Custom scenario defined but `electricity_supply` not provided.  
**Fix:** Include `"electricity_supply": {"total_available": <value>}` in request.

### "Invalid zone in events"
**Cause:** Event references a zone not defined in `zones`.  
**Fix:** Ensure all zones in `events[*].affected_zones` exist in `zones` dictionary.

### "Event start_hour >= duration_hours"
**Cause:** Event starts after the simulation ends.  
**Fix:** Ensure `start_hour < duration_hours`.

### "Intervention magnitude not numeric"
**Cause:** `magnitude` is a string or null instead of a number.  
**Fix:** Ensure `magnitude` is a valid number (int or float).

### "Comparison produced null"
**Cause:** `baseline_scenario_name` provided but that scenario doesn't exist.  
**Fix:** Use only: `normal_operations`, `heatwave_no_intervention`, `heatwave_with_intervention`, `supply_disruption_and_recovery`.

---

## 11. Example: Running All 4 Built-In Scenarios

```python
from services.digital_twin import built_in_simulations, run_digital_twin_simulation

scenarios = built_in_simulations()

for scenario_config in scenarios:
    result = run_digital_twin_simulation(**scenario_config)
    peak_risk = max([s["risk_score"] for s in result["states"]])
    peak_severity = max([s["severity"] for s in result["states"]], key=lambda s: ["normal", "warning", "high", "critical"].index(s))
    print(f"{scenario_config['scenario_name']}: Peak Risk={peak_risk:.1f}, Peak Severity={peak_severity}")
```

**Expected Output:**
```
normal_operations: Peak Risk=5.2, Peak Severity=normal
heatwave_no_intervention: Peak Risk=48.3, Peak Severity=high
heatwave_with_intervention: Peak Risk=32.1, Peak Severity=warning
supply_disruption_and_recovery: Peak Risk=72.4, Peak Severity=high
```

---

**Happy simulating! 🎯**

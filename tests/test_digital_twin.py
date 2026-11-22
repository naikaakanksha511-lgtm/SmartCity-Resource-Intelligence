"""Tests for the digital twin simulation engine and API."""
import copy
import pytest
from datetime import datetime, timedelta

from app import create_app
from services.digital_twin import (
    DigitalTwinSimulation,
    run_digital_twin_simulation,
    built_in_simulations,
)


def base_scenario():
    return {
        "name": "Test scenario",
        "zones": [
            {
                "zone": "Zone A",
                "priority": "high",
                "electricity_demand_mw": 50,
                "water_demand_litres": 1000000,
                "critical_service_requirements": {"electricity_mw": 10, "water_litres": 200000},
            }
        ],
        "availability": {"electricity_mw": 100, "water_litres": 2000000},
        "solar_generation_mw": 5,
    }


def test_digital_twin_initialization():
    """Test that a digital twin can be created with minimal configuration."""
    scenario = base_scenario()
    twin = DigitalTwinSimulation(scenario, duration_hours=24, step_size_hours=1)
    assert twin.num_steps == 24
    assert twin.duration_hours == 24
    assert twin.step_size_hours == 1
    assert twin.current_step == 0
    assert len(twin.simulation_state) == 0


def test_digital_twin_invalid_input():
    """Test that invalid initialization parameters are rejected."""
    scenario = base_scenario()
    with pytest.raises(ValueError, match="scenario must be"):
        DigitalTwinSimulation(None)

    with pytest.raises(ValueError, match="duration_hours"):
        DigitalTwinSimulation(scenario, duration_hours=0)

    with pytest.raises(ValueError, match="step_size_hours"):
        DigitalTwinSimulation(scenario, step_size_hours=48, duration_hours=24)


def test_digital_twin_run_produces_states():
    """Test that running a simulation produces one state per step."""
    scenario = base_scenario()
    twin = DigitalTwinSimulation(scenario, duration_hours=4, step_size_hours=1)
    twin.run()
    assert twin.current_step == 4
    assert len(twin.simulation_state) == 4
    assert all(hasattr(s, "timestamp") for s in twin.simulation_state)
    assert all(hasattr(s, "severity") for s in twin.simulation_state)
    assert all(hasattr(s, "risk_score") for s in twin.simulation_state)


def test_digital_twin_normal_scenario_no_stress():
    """Test that normal scenario (adequate supply) produces 'normal' severity."""
    scenario = base_scenario()
    twin = DigitalTwinSimulation(scenario, duration_hours=4, step_size_hours=1)
    twin.run()
    assert all(s.severity == "normal" for s in twin.simulation_state)
    assert all(s.risk_score == 0 for s in twin.simulation_state)
    assert all(len(s.affected_zones) == 0 for s in twin.simulation_state)


def test_digital_twin_shortage_scenario():
    """Test that inadequate supply produces stress indicators."""
    scenario = base_scenario()
    scenario["availability"]["electricity_mw"] = 20  # Severe shortage
    twin = DigitalTwinSimulation(scenario, duration_hours=4, step_size_hours=1)
    twin.run()
    assert any(s.severity in {"high", "critical"} for s in twin.simulation_state)
    assert any(s.risk_score > 0 for s in twin.simulation_state)


def test_add_event_validation():
    """Test that events are validated on addition."""
    scenario = base_scenario()
    twin = DigitalTwinSimulation(scenario)
    with pytest.raises(ValueError, match="event must be a dictionary"):
        twin.add_event(None)

    with pytest.raises(ValueError, match="missing required keys"):
        twin.add_event({})

    with pytest.raises(ValueError, match="affected_zones"):
        twin.add_event(
            {
                "event_id": "test",
                "type": "heatwave",
                "start_hour": 0,
                "duration_hours": 1,
                "affected_zones": [],
                "field": "electricity_demand_mw",
            }
        )


def test_add_event_heatwave():
    """Test that a heatwave event increases demand."""
    scenario = base_scenario()
    twin = DigitalTwinSimulation(scenario, duration_hours=12, step_size_hours=1)
    twin.add_event(
        {
            "event_id": "heat-1",
            "type": "heatwave",
            "start_hour": 4,
            "duration_hours": 4,
            "affected_zones": ["Zone A"],
            "magnitude": 1.5,
            "field": "electricity_demand_mw",
            "explanation": "30% demand increase",
            "assumptions": ["Peak heat 4–8 hours"],
        }
    )
    twin.run()
    before = twin.simulation_state[2].risk_score
    during = twin.simulation_state[5].risk_score
    after = twin.simulation_state[10].risk_score
    assert during >= before, "Risk should increase during heatwave"
    assert after <= during, "Risk should decrease after heatwave"


def test_add_intervention_validation():
    """Test that interventions are validated on addition."""
    scenario = base_scenario()
    twin = DigitalTwinSimulation(scenario)
    with pytest.raises(ValueError, match="intervention must be a dictionary"):
        twin.add_intervention(None)

    with pytest.raises(ValueError, match="missing required keys"):
        twin.add_intervention({})

    with pytest.raises(ValueError, match="start_hour"):
        twin.add_intervention(
            {
                "intervention_id": "test",
                "type": "capacity_boost",
                "start_hour": 48,
                "affected_zones": ["Zone A"],
                "action": "increase_electricity",
            }
        )


def test_add_intervention_capacity_boost():
    """Test that a capacity boost intervention reduces stress."""
    scenario = base_scenario()
    scenario["availability"]["electricity_mw"] = 30  # Shortage
    twin = DigitalTwinSimulation(scenario, duration_hours=12, step_size_hours=1)
    twin.add_intervention(
        {
            "intervention_id": "boost-1",
            "type": "capacity_boost",
            "start_hour": 6,
            "affected_zones": ["Zone A"],
            "action": "increase_electricity",
            "magnitude": 50,
            "explanation": "Emergency generation comes online",
            "assumptions": ["Available on 6-hour notice"],
        }
    )
    twin.run()
    before = twin.simulation_state[4].risk_score
    after = twin.simulation_state[8].risk_score
    assert after <= before, "Risk should decrease after intervention"


def test_get_step_index():
    """Test that individual steps can be retrieved."""
    scenario = base_scenario()
    twin = DigitalTwinSimulation(scenario, duration_hours=4, step_size_hours=1)
    twin.run()
    state0 = twin.get_step(0)
    state2 = twin.get_step(2)
    assert state0.timestamp != state2.timestamp
    with pytest.raises(IndexError):
        twin.get_step(10)


def test_recovery_curve_severity():
    """Test that recovery curves can be extracted."""
    scenario = base_scenario()
    scenario["availability"]["electricity_mw"] = 20  # Shortage
    twin = DigitalTwinSimulation(scenario, duration_hours=12, step_size_hours=1)
    twin.add_intervention(
        {
            "intervention_id": "recovery",
            "type": "restore",
            "start_hour": 6,
            "affected_zones": ["Zone A"],
            "action": "increase_electricity",
            "magnitude": 80,
            "explanation": "Full capacity restored",
            "assumptions": ["Repair complete by hour 6"],
        }
    )
    twin.run()
    curve = twin.get_recovery_curve("severity")
    assert len(curve) == 12
    assert all(isinstance(item, tuple) and len(item) == 2 for item in curve)


def test_recovery_curve_risk_score():
    """Test risk score recovery curve."""
    scenario = base_scenario()
    scenario["availability"]["electricity_mw"] = 20
    twin = DigitalTwinSimulation(scenario, duration_hours=12, step_size_hours=1)
    twin.add_intervention(
        {
            "intervention_id": "recovery",
            "type": "restore",
            "start_hour": 6,
            "affected_zones": ["Zone A"],
            "action": "increase_electricity",
            "magnitude": 80,
            "explanation": "Restoration",
            "assumptions": [],
        }
    )
    twin.run()
    curve = twin.get_recovery_curve("risk_score")
    assert len(curve) == 12
    max_risk = max(val for _, val in curve)
    min_risk = min(val for _, val in curve)
    assert max_risk > min_risk, "Risk should vary over time"


def test_compare_with_baseline():
    """Test scenario comparison against a baseline."""
    base_scen = base_scenario()
    base_scen["availability"]["electricity_mw"] = 20  # Shortage
    baseline = DigitalTwinSimulation(base_scen, duration_hours=8, step_size_hours=1)
    baseline.run()

    # Scenario with intervention
    scen_with_fix = base_scenario()
    scen_with_fix["availability"]["electricity_mw"] = 20
    scenario = DigitalTwinSimulation(scen_with_fix, duration_hours=8, step_size_hours=1)
    scenario.add_intervention(
        {
            "intervention_id": "fix",
            "type": "boost",
            "start_hour": 4,
            "affected_zones": ["Zone A"],
            "action": "increase_electricity",
            "magnitude": 80,
            "explanation": "Fix",
            "assumptions": [],
        }
    )
    scenario.run()

    comparison = scenario.compare_with_baseline(baseline)
    assert "baseline_severity_sequence" in comparison
    assert "scenario_severity_sequence" in comparison
    assert "severity_improved" in comparison
    assert len(comparison["baseline_severity_sequence"]) == 8
    assert len(comparison["scenario_severity_sequence"]) == 8


def test_to_dict_serialization():
    """Test that simulation results can be serialized to dict."""
    scenario = base_scenario()
    twin = DigitalTwinSimulation(scenario, duration_hours=4, step_size_hours=1)
    twin.run()
    result = twin.to_dict()
    assert result["status"] == "simulated"
    assert result["data_label"] == "deterministic simulation; not live city data"
    assert result["duration_hours"] == 4
    assert len(result["timeline"]) == 4
    assert all("timestamp" in step for step in result["timeline"])


def test_run_digital_twin_simulation_api():
    """Test the high-level API function."""
    config = {
        "scenario": base_scenario(),
        "duration_hours": 6,
        "step_size_hours": 1,
    }
    result = run_digital_twin_simulation(config)
    assert result["status"] == "simulated"
    assert len(result["timeline"]) == 6


def test_run_digital_twin_with_events_and_interventions():
    """Test full simulation with both events and interventions."""
    config = {
        "scenario": base_scenario(),
        "duration_hours": 12,
        "step_size_hours": 1,
        "events": [
            {
                "event_id": "evt-1",
                "type": "heatwave",
                "start_hour": 2,
                "duration_hours": 4,
                "affected_zones": ["Zone A"],
                "magnitude": 1.5,
                "field": "electricity_demand_mw",
                "explanation": "Heat event",
                "assumptions": [],
            }
        ],
        "interventions": [
            {
                "intervention_id": "int-1",
                "type": "response",
                "start_hour": 4,
                "affected_zones": ["Zone A"],
                "action": "increase_electricity",
                "magnitude": 30,
                "explanation": "Emergency response",
                "assumptions": [],
            }
        ],
    }
    result = run_digital_twin_simulation(config)
    assert result["events_applied"] == 1
    assert result["interventions_applied"] == 1
    assert len(result["timeline"]) == 12


def test_built_in_simulations_exist():
    """Test that built-in demonstration simulations are available."""
    sims = built_in_simulations()
    assert len(sims) >= 4
    assert all("id" in sim for sim in sims)
    assert all("name" in sim for sim in sims)
    assert all("description" in sim for sim in sims)
    assert all("config" in sim for sim in sims)


def test_built_in_simulations_can_run():
    """Test that built-in simulations can be executed."""
    sims = built_in_simulations()
    for sim in sims[:2]:  # Test first two
        result = run_digital_twin_simulation(sim["config"])
        assert result["status"] == "simulated"
        assert len(result["timeline"]) > 0


def test_digital_twin_api_endpoint():
    """Test the digital twin API endpoint."""
    client = create_app({"TESTING": True}).test_client()
    # Test status endpoint
    status = client.get("/api/digital-twin/status")
    assert status.status_code == 200
    assert status.get_json()["status"] == "ready"

    # Test simulations endpoint
    sims = client.get("/api/digital-twin/simulations")
    assert sims.status_code == 200
    assert len(sims.get_json()["simulations"]) >= 4

    # Test run endpoint
    config = {"scenario": base_scenario(), "duration_hours": 2, "step_size_hours": 1}
    result = client.post("/api/digital-twin/run", json=config)
    assert result.status_code == 200
    assert result.get_json()["status"] == "simulated"


def test_digital_twin_api_validation():
    """Test that API validates input."""
    client = create_app({"TESTING": True}).test_client()
    # Missing scenario
    result = client.post("/api/digital-twin/run", json={})
    assert result.status_code == 400
    assert "scenario" in result.get_json()["error"]

    # Invalid JSON
    result = client.post(
        "/api/digital-twin/run",
        data="invalid",
        headers={"Content-Type": "application/json"},
    )
    assert result.status_code == 400


def test_deterministic_reproducibility():
    """Test that identical inputs produce identical outputs."""
    scenario = base_scenario()
    twin1 = DigitalTwinSimulation(scenario, duration_hours=6, step_size_hours=1)
    twin1.add_event(
        {
            "event_id": "evt-1",
            "type": "heatwave",
            "start_hour": 2,
            "duration_hours": 2,
            "affected_zones": ["Zone A"],
            "magnitude": 1.3,
            "field": "electricity_demand_mw",
            "explanation": "Heat",
            "assumptions": [],
        }
    )
    twin1.run()

    twin2 = DigitalTwinSimulation(copy.deepcopy(scenario), duration_hours=6, step_size_hours=1)
    twin2.add_event(
        {
            "event_id": "evt-1",
            "type": "heatwave",
            "start_hour": 2,
            "duration_hours": 2,
            "affected_zones": ["Zone A"],
            "magnitude": 1.3,
            "field": "electricity_demand_mw",
            "explanation": "Heat",
            "assumptions": [],
        }
    )
    twin2.run()

    for s1, s2 in zip(twin1.simulation_state, twin2.simulation_state):
        assert s1.severity == s2.severity
        assert s1.risk_score == s2.risk_score

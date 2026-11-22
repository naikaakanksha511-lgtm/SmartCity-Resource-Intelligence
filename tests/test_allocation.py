"""Tests for deterministic allocation policy and scenario APIs."""
import pytest

from app import create_app
from services.allocation import run_allocation, simulate_allocation


def scenario(capacity=10, water=100, zones=None):
    return {"availability": {"electricity_mw": capacity, "water_litres": water}, "zones": zones or [
        {"zone": "A", "priority": "critical", "electricity_demand": 8, "electricity_critical_demand": 4, "water_demand": 80, "water_critical_demand": 40},
        {"zone": "B", "priority": "medium", "electricity_demand": 8, "water_demand": 80},
    ]}


def test_capacity_limits_priority_and_protected_critical_requirement():
    result = run_allocation(scenario())
    a, b = result["zones"]
    assert result["resources"]["electricity"]["allocated"] == pytest.approx(10)
    assert a["electricity"]["critical_allocated"] == pytest.approx(4)
    assert a["electricity"]["allocation"] > b["electricity"]["allocation"]
    # Zone A is fully served at 8 MW; the remaining 2 MW can then go to B.
    assert a["electricity"]["allocation"] == pytest.approx(8)
    assert b["electricity"]["allocation"] == pytest.approx(2)
    assert a["electricity"]["unmet_demand"] == 0
    assert b["electricity"]["unmet_demand"] == pytest.approx(6)
    assert a["water"]["critical_service_coverage_percent"] == 100
    assert result["resources"]["water"]["allocated"] <= 100


def test_lower_priority_waits_until_higher_priority_demand_is_met():
    result = run_allocation(scenario(capacity=6))
    a, b = result["zones"]
    assert a["electricity"]["allocation"] == pytest.approx(6)
    assert a["electricity"]["unmet_demand"] == pytest.approx(2)
    assert b["electricity"]["allocation"] == 0
    assert b["electricity"]["unmet_demand"] == 8
    assert result["resources"]["electricity"]["allocated"] <= 6


def test_equal_priority_shares_proportionally_and_unmet_is_correct():
    payload = scenario(5, 0, [
        {"zone": "A", "priority": "medium", "electricity_demand": 10, "water_demand": 0},
        {"zone": "B", "priority": "medium", "electricity_demand": 20, "water_demand": 0},
    ])
    result = run_allocation(payload)
    assert [z["electricity"]["allocation"] for z in result["zones"]] == pytest.approx([5/3, 10/3])
    assert [z["electricity"]["unmet_demand"] for z in result["zones"]] == pytest.approx([25/3, 50/3])
    assert result["resources"]["water"]["utilisation_percent"] == 0


def test_zero_and_excess_availability():
    zero = run_allocation(scenario(0, 0))
    assert all(z["electricity"]["allocation"] == 0 for z in zero["zones"])
    assert all(z["water"]["allocation"] == 0 for z in zero["zones"])
    covered = run_allocation(scenario(100, 1000))
    assert covered["resources"]["electricity"]["unmet_demand"] == 0
    assert covered["resources"]["water"]["unmet_demand"] == 0


@pytest.mark.parametrize("bad", [-1, float("inf"), float("nan"), "bad"])
def test_invalid_negative_and_nonfinite_values_rejected(bad):
    payload = scenario()
    payload["availability"]["electricity_mw"] = bad
    with pytest.raises(ValueError):
        run_allocation(payload)


def test_rejects_critical_requirement_above_demand_and_unknown_priority():
    payload = scenario()
    payload["zones"][0]["electricity_critical_demand"] = 9
    with pytest.raises(ValueError, match="cannot exceed"):
        run_allocation(payload)
    payload = scenario()
    payload["zones"][0]["priority"] = "hospital"
    with pytest.raises(ValueError, match="priority"):
        run_allocation(payload)


def test_solar_addition_is_explicit_and_explained():
    payload = scenario(0)
    payload["solar_generation_mw"] = 2
    result = run_allocation(payload)
    assert result["resources"]["electricity"]["capacity"] == 2
    assert "Solar generation was added" in result["assumptions"][0]


def test_scenario_comparison_and_emergency_priority_change():
    baseline = scenario(12, 120)
    result = simulate_allocation(baseline, {"name": "Emergency", "changes": {"electricity_availability_multiplier": .5, "priority_overrides": {"B": "critical"}}})
    assert result["comparison"]["electricity"]["unmet_demand_change"] > 0
    assert result["scenario"]["zones"][1]["priority"] == "critical"
    assert "changed by" in result["scenario"]["zones"][1]["electricity"]["change_explanation"]


def test_explanations_include_priority_shortage_and_assumption():
    payload = scenario(1, 0)
    payload["assumptions"] = ["explicit capacity test"]
    result = run_allocation(payload)
    explanation = result["zones"][0]["electricity"]["explanation"]
    assert "critical requirement" in explanation
    assert "critical priority" in explanation
    assert "unmet" in explanation
    assert "explicit capacity test" in result["assumptions"]


def test_api_validates_and_serves_allocation_routes():
    client = create_app({"TESTING": True}).test_client()
    assert client.get("/api/allocation/status").get_json()["status"] == "ready"
    valid = scenario()
    assert client.post("/api/allocation/run", json=valid).status_code == 200
    assert client.post("/api/allocation/run", json={}).status_code == 400
    assert client.post("/api/allocation/simulate", json={"baseline": valid, "scenario": {"changes": {}}}).status_code == 200

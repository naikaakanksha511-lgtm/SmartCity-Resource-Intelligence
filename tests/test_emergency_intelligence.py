import copy

import pytest

from app import create_app
from services.emergency_intelligence import analyze_emergency, built_in_scenarios, simulate_emergency, _severity


def payload(electricity=100, water=1000, e_capacity=100, w_capacity=1000, critical_e=0, critical_w=0):
    return {"name": "test", "zones": [{"zone": "A", "priority": "high", "electricity_demand_mw": electricity,
             "water_demand_litres": water, "critical_service_requirements": {"electricity_mw": critical_e, "water_litres": critical_w}}],
            "availability": {"electricity_mw": e_capacity, "water_litres": w_capacity}, "solar_generation_mw": 0}


def test_normal_no_false_emergency_alerts():
    result = analyze_emergency(payload())
    assert result["overall_severity"] == "normal"
    assert result["alerts"] == []
    assert result["affected_zones"] == []


def test_electricity_only_and_water_only_shortfalls():
    electricity = analyze_emergency(payload(e_capacity=50))
    assert electricity["resource_shortfalls"]["electricity"]["amount"] == 50
    assert electricity["resource_shortfalls"]["water"]["amount"] == 0
    assert {a["resource"] for a in electricity["alerts"]} == {"electricity"}
    water = analyze_emergency(payload(w_capacity=500))
    assert water["resource_shortfalls"]["water"]["amount"] == 500
    assert {a["resource"] for a in water["alerts"]} == {"water"}


def test_combined_shortages_and_dependencies_are_explicit():
    result = analyze_emergency(payload(e_capacity=50, w_capacity=500))
    assert result["overall_severity"] in {"high", "critical"}
    assert {a["resource"] for a in result["alerts"]} == {"electricity", "water"}
    assert {r["source"] for r in result["cascading_risks"]} == {"electricity", "water"}
    assert all("assumption" in risk["evidence_quality"] for risk in result["cascading_risks"])


def test_solar_reduction_is_simulated_and_recommendations_ranked():
    case = payload(e_capacity=100, w_capacity=1000)
    case.update(solar_generation_mw=20, solar_reduction_fraction=.5)
    result = analyze_emergency(case)
    solar = [a for a in result["alerts"] if a["resource"] == "solar_generation"]
    assert solar and solar[0]["measured_or_scenario_supplied"]["scenario_generation_mw"] == 10
    assert "assumed" in solar[0]["evidence_quality"]
    short = analyze_emergency(payload(e_capacity=10, w_capacity=500, critical_e=20, critical_w=100))
    assert short["overall_severity"] in {"high", "critical"}
    assert any("critical-service" in item["triggering_condition"] for item in short["interventions"])
    assert [a["rank"] for a in short["interventions"]] == list(range(1, len(short["interventions"])+1))
    assert all(a["executed"] is False and a["affected_zones"] for a in short["interventions"])


@pytest.mark.parametrize("score,expected", [(0, "normal"), (24.999, "normal"), (25, "warning"), (49.999, "warning"), (50, "high"), (74.999, "high"), (75, "critical")])
def test_severity_threshold_boundaries(score, expected):
    assert _severity(score) == expected


def test_critical_service_shortfall_elevates_city_severity():
    result = analyze_emergency(payload(e_capacity=0, w_capacity=1000, critical_e=20))
    assert result["overall_severity"] in {"high", "critical"}
    assert any(a["resource"] == "critical_service_electricity" for a in result["alerts"])


def test_scenarios_comparison_contains_five_labeled_cases():
    cases = built_in_scenarios()
    assert len(cases) == 5
    assert all("not a live event" in case["data_label"] for case in cases)
    result = simulate_emergency(cases[0]["scenario"], {"name": cases[3]["name"], "changes": cases[3]["scenario"]})
    assert result["comparison"]["severity_changed"]
    assert result["comparison"]["shortfalls_after"]["electricity"]["amount"] > result["comparison"]["shortfalls_before"]["electricity"]["amount"]


@pytest.mark.parametrize("bad", [None, {}, {"zones": []}, {"zones": [{}], "availability": {}}])
def test_missing_or_invalid_scenario_inputs_rejected(bad):
    with pytest.raises(ValueError):
        analyze_emergency(bad)


def test_supply_is_required_and_never_inferred_from_history():
    case = payload(); del case["availability"]
    with pytest.raises(ValueError, match="explicitly supply"):
        analyze_emergency(case)


def test_dependencies_are_validated_and_configurable():
    case = payload(e_capacity=50)
    case["dependencies"] = [{"source": "electricity", "target": "custom", "factor": .5, "explanation": "test assumption"}]
    result = analyze_emergency(case)
    assert result["cascading_risks"][0]["target"] == "custom"
    case["dependencies"][0]["factor"] = 2
    with pytest.raises(ValueError, match="between 0 and 1"):
        analyze_emergency(case)


def test_emergency_endpoints_and_content_type_validation():
    client = create_app({"TESTING": True}).test_client()
    assert client.get("/api/emergency/status").get_json()["status"] == "ready"
    assert len(client.get("/api/emergency/scenarios").get_json()["scenarios"]) == 5
    assert client.post("/api/emergency/analyze", json=payload()).status_code == 200
    assert client.post("/api/emergency/analyze", json={}).status_code == 400
    assert client.post("/api/emergency/analyze", data="{}", content_type="text/plain").status_code == 400
    assert client.post("/api/emergency/simulate", json={}).status_code == 400


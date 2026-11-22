"""Explainable emergency analysis over explicitly supplied, simulated scenarios.

No resource capacity is inferred from historical consumption. Dependency links
are configurable assumptions for scenario exploration, not measured causality.
"""
import copy
import math

from services.allocation import run_allocation

SEVERITY_THRESHOLDS = {"warning": 25, "high": 50, "critical": 75}
DEFAULT_DEPENDENCIES = [
    {"source": "electricity", "target": "water", "factor": 0.20,
     "explanation": "Assumption: electricity shortage may constrain water pumping."},
    {"source": "water", "target": "critical_services", "factor": 0.20,
     "explanation": "Assumption: water shortage may affect hospitals and emergency services."},
    {"source": "solar_reduction", "target": "electricity", "factor": 0.15,
     "explanation": "Assumption: lower solar generation increases reliance on other electricity supply."},
]


def _num(value, label):
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite non-negative number.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a finite non-negative number.") from None
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{label} must be a finite non-negative number.")
    return number


def _validate(scenario):
    if not isinstance(scenario, dict):
        raise ValueError("Request body must be a JSON object.")
    zones, availability = scenario.get("zones"), scenario.get("availability")
    if not isinstance(zones, list) or not zones:
        raise ValueError("zones must be a non-empty list.")
    if not isinstance(availability, dict):
        raise ValueError("availability must explicitly supply electricity_mw and water_litres.")
    clean_zones, seen = [], set()
    for i, zone in enumerate(zones):
        if not isinstance(zone, dict):
            raise ValueError(f"zones[{i}] must be an object.")
        name = zone.get("zone")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
            raise ValueError(f"zones[{i}].zone must be a non-empty name of at most 100 characters.")
        name = name.strip()
        if name.casefold() in seen:
            raise ValueError(f"Zone names must be unique: {name}.")
        seen.add(name.casefold())
        priority = zone.get("priority", "standard")
        if not isinstance(priority, str) or priority.casefold() not in {"critical", "high", "medium", "standard"}:
            raise ValueError(f"zones[{i}].priority must be critical, high, medium, or standard.")
        req = zone.get("critical_service_requirements", {})
        if not isinstance(req, dict):
            raise ValueError(f"zones[{i}].critical_service_requirements must be an object.")
        e = _num(zone.get("electricity_demand_mw"), f"zones[{i}].electricity_demand_mw")
        w = _num(zone.get("water_demand_litres"), f"zones[{i}].water_demand_litres")
        ce = _num(req.get("electricity_mw", 0), f"zones[{i}].critical_service_requirements.electricity_mw")
        cw = _num(req.get("water_litres", 0), f"zones[{i}].critical_service_requirements.water_litres")
        if ce > e or cw > w:
            raise ValueError(f"zones[{i}] critical-service requirements cannot exceed total demand.")
        clean_zones.append({"zone": name, "priority": priority.casefold(), "electricity_demand_mw": e,
                            "water_demand_litres": w, "critical_service_requirements": {"electricity_mw": ce, "water_litres": cw}})
    caps = {key: _num(availability.get(key), f"availability.{key}") for key in ("electricity_mw", "water_litres")}
    solar = _num(scenario.get("solar_generation_mw", 0), "solar_generation_mw")
    reduction = scenario.get("solar_reduction_fraction", 0)
    if isinstance(reduction, bool):
        raise ValueError("solar_reduction_fraction must be between 0 and 1.")
    try:
        reduction = float(reduction)
    except (TypeError, ValueError):
        raise ValueError("solar_reduction_fraction must be between 0 and 1.") from None
    if not math.isfinite(reduction) or not 0 <= reduction <= 1:
        raise ValueError("solar_reduction_fraction must be between 0 and 1.")
    dependencies = scenario.get("dependencies", DEFAULT_DEPENDENCIES)
    if not isinstance(dependencies, list):
        raise ValueError("dependencies must be a list of explicit dependency assumptions.")
    for i, dep in enumerate(dependencies):
        if not isinstance(dep, dict) or not isinstance(dep.get("source"), str) or not isinstance(dep.get("target"), str) or not isinstance(dep.get("explanation"), str):
            raise ValueError(f"dependencies[{i}] must provide source, target, factor, and explanation.")
        factor = dep.get("factor")
        if isinstance(factor, bool):
            raise ValueError(f"dependencies[{i}].factor must be between 0 and 1.")
        try:
            factor = float(factor)
        except (TypeError, ValueError):
            raise ValueError(f"dependencies[{i}].factor must be between 0 and 1.") from None
        if not math.isfinite(factor) or not 0 <= factor <= 1:
            raise ValueError(f"dependencies[{i}].factor must be between 0 and 1.")
        dep["factor"] = factor
    assumptions = scenario.get("assumptions", [])
    if not isinstance(assumptions, list) or not all(isinstance(a, str) for a in assumptions):
        raise ValueError("assumptions must be a list of strings.")
    return clean_zones, caps, solar, reduction, copy.deepcopy(dependencies), assumptions


def analyze_emergency(scenario):
    """Analyze a caller-supplied scenario and return alerts, risks and advice."""
    zones, caps, solar, reduction, dependencies, assumptions = _validate(scenario)
    retained_solar = solar * (1 - reduction)
    allocation_input = {"zones": [{"zone": z["zone"], "priority": z["priority"],
        "electricity_demand": z["electricity_demand_mw"],
        "electricity_critical_demand": z["critical_service_requirements"]["electricity_mw"],
        "water_demand": z["water_demand_litres"],
        "water_critical_demand": z["critical_service_requirements"]["water_litres"]} for z in zones],
        "availability": caps, "solar_generation_mw": retained_solar, "assumptions": assumptions}
    allocation = run_allocation(allocation_input)
    allocation_by_zone = {z["zone"]: z for z in allocation["zones"]}
    alerts, zone_results = [], []
    totals = {r: {"demand": 0.0, "unmet": 0.0} for r in ("electricity", "water")}
    for zone in zones:
        alloc = allocation_by_zone[zone["zone"]]
        zone_alerts = []
        for resource, label, demand_key, unit in (
            ("electricity", "electricity_demand_mw", "electricity_demand_mw", "MW"),
            ("water", "water_demand_litres", "water_demand_litres", "litres")):
            result = alloc[resource]
            demand, unmet = result["demand"], result["unmet_demand"]
            totals[resource]["demand"] += demand
            totals[resource]["unmet"] += unmet
            pct = 0 if demand == 0 else 100 * unmet / demand
            if unmet > 1e-9:
                alert = {"zone": zone["zone"], "resource": resource, "severity": "warning" if pct < 25 else "high" if pct < 60 else "critical",
                    "measured_or_scenario_supplied": {"demand": demand, "allocated": result["allocation"], "shortfall": unmet, "unit": unit},
                    "threshold": {"shortfall": "> 0", "severity_percent_of_demand": {"warning": "<25%", "high": "25-<60%", "critical": ">=60%"}},
                    "explanation": f"Explicitly supplied capacity left {unmet:g} {unit} ({pct:.1f}%) of {resource} demand unmet.",
                    "evidence_quality": "scenario-supplied; simulated", "status": "simulated"}
                alerts.append(alert); zone_alerts.append(alert)
        critical_shortfall = False
        for resource in ("electricity", "water"):
            item = alloc[resource]
            req, served = item["critical_requirement"], item["critical_allocated"]
            if req > served + 1e-9:
                critical_shortfall = True
                alert = {"zone": zone["zone"], "resource": f"critical_service_{resource}", "severity": "critical",
                    "measured_or_scenario_supplied": {"required": req, "allocated": served, "shortfall": req-served, "unit": item["unit"]},
                    "threshold": {"shortfall": "any positive explicit critical requirement unmet"},
                    "explanation": f"Explicit critical-service requirement is short by {req-served:g} {item['unit']}.",
                    "evidence_quality": "scenario-supplied; simulated", "status": "simulated"}
                alerts.append(alert); zone_alerts.append(alert)
        if reduction > 0 and solar > 0:
            alert = {"zone": zone["zone"], "resource": "solar_generation", "severity": "warning" if reduction < .5 else "high",
                "measured_or_scenario_supplied": {"baseline_generation_mw": solar, "reduction_fraction": reduction, "scenario_generation_mw": retained_solar},
                "threshold": {"solar_reduction_fraction": "> 0"}, "explanation": f"Scenario assumes solar generation falls by {reduction*100:.1f}%.",
                "evidence_quality": "assumed scenario input; simulated", "status": "simulated"}
            alerts.append(alert); zone_alerts.append(alert)
        base_score = max([100 * a["measured_or_scenario_supplied"].get("shortfall", 0) / max(a["measured_or_scenario_supplied"].get("demand", a["measured_or_scenario_supplied"].get("required", 0)), 1e-9)
                          for a in zone_alerts if a["resource"] in ("electricity", "water")] or [0])
        resources_failed = sum(1 for r in ("electricity", "water") if alloc[r]["unmet_demand"] > 1e-9)
        # Use the maximum underlying resource deficit plus capped combination bonus;
        # never sum duplicate zone-level and critical-service shortfall amounts.
        score = min(100, base_score + (10 if resources_failed == 2 else 0) + (15 if critical_shortfall else 0))
        severity = _severity(score)
        zone_results.append({"zone": zone["zone"], "priority": zone["priority"], "risk_score": round(score, 2), "severity": severity,
            "resource_shortfalls": {r: alloc[r]["unmet_demand"] for r in ("electricity", "water")},
            "critical_service_coverage_percent": {r: alloc[r]["critical_service_coverage_percent"] for r in ("electricity", "water")},
            "alerts": zone_alerts, "critical_service_shortfall": critical_shortfall})
    city_score = max((z["risk_score"] for z in zone_results), default=0)
    cascades = []
    shortages = {r: (0 if totals[r]["demand"] == 0 else totals[r]["unmet"] / totals[r]["demand"]) for r in totals}
    for dep in dependencies:
        source_strength = reduction if dep["source"] == "solar_reduction" else shortages.get(dep["source"], 0)
        if dep["source"] == "critical_services":
            source_strength = 1 if any(z["critical_service_shortfall"] for z in zone_results) else 0
        impact = source_strength * dep["factor"] * 100
        if source_strength > 0 and impact > 0:
            cascades.append({"source": dep["source"], "target": dep["target"], "risk_contribution": round(impact, 2),
                "assumption_factor": dep["factor"], "explanation": dep["explanation"], "evidence_quality": "configurable assumption; not established by sample data"})
    cascade_score = min(25, sum(c["risk_contribution"] for c in cascades))
    city_score = min(100, city_score + cascade_score)
    severity = _severity(city_score)
    if any(z["critical_service_shortfall"] for z in zone_results):
        severity = _elevate(severity, "high")
    recommendations = _recommend(zones, allocation, zone_results, caps, retained_solar)
    return {"status": "simulated", "scenario_name": scenario.get("name", "Caller supplied scenario"),
        "data_label": "simulated scenario; not a live event", "overall_severity": severity,
        "risk_score": round(city_score, 2), "severity_thresholds": SEVERITY_THRESHOLDS,
        "risk_formula": "zone score = max resource shortfall % + 10 combined-failure points + 15 critical-service points (capped 100); city score = max zone score + capped (25) dependency contributions. Severity: <25 Normal, 25-<50 Warning, 50-<75 High, >=75 Critical. Any explicit critical-service shortfall elevates city severity to at least High.",
        "alerts": alerts, "affected_zones": [z["zone"] for z in zone_results if z["risk_score"] > 0],
        "zones": zone_results, "resource_shortfalls": {r: {"amount": totals[r]["unmet"], "unit": "MW" if r == "electricity" else "litres"} for r in totals},
        "critical_service_coverage_percent": allocation["critical_service_coverage_percent"],
        "allocation": allocation, "cascading_risks": cascades, "cascading_risk_score": round(cascade_score, 2),
        "interventions": recommendations, "assumptions": assumptions + ["All scenario demand and capacity values are caller-supplied; no supply was inferred from historical consumption."],
        "availability_source": "explicit scenario input"}


def _severity(score):
    return "critical" if score >= 75 else "high" if score >= 50 else "warning" if score >= 25 else "normal"


def _elevate(current, minimum):
    order = ["normal", "warning", "high", "critical"]
    return order[max(order.index(current), order.index(minimum))]


def _recommend(zones, allocation, zone_results, caps, solar):
    actions = []
    short_zones = [z for z in zone_results if any(v > 1e-9 for v in z["resource_shortfalls"].values())]
    critical_zones = [z for z in zone_results if z["critical_service_shortfall"]]
    if critical_zones:
        actions.append({"rank": 1, "triggering_condition": "Explicit critical-service requirements are not fully allocated.",
            "proposed_action": "Reallocate available electricity and water to declared critical-service loads, then defer lower-priority discretionary demand.",
            "expected_benefit": "Improves protected-service coverage within the stated capacities.", "trade_off": "Reduces allocations available to lower-priority demand.",
            "assumptions": ["Declared critical-service requirements and priority labels are correct."], "affected_zones": [z["zone"] for z in critical_zones], "executed": False})
    if any(z["resource_shortfalls"]["water"] > 0 for z in short_zones):
        actions.append({"rank": len(actions)+1, "triggering_condition": "Water demand exceeds explicit available water in one or more zones.",
            "proposed_action": "Protect declared essential water demand and defer non-essential water use in the affected zones.",
            "expected_benefit": "Directs the limited allocation toward declared essential demand.", "trade_off": "Non-essential uses receive less water.",
            "assumptions": ["Critical-service water quantities represent the essential minimum."], "affected_zones": [z["zone"] for z in short_zones if z["resource_shortfalls"]["water"] > 0], "executed": False})
    if any(z["resource_shortfalls"]["electricity"] > 0 for z in short_zones):
        actions.append({"rank": len(actions)+1, "triggering_condition": "Electricity demand exceeds explicit available capacity.",
            "proposed_action": "Reduce or defer non-essential electricity demand and adjust priorities for the next allocation simulation.",
            "expected_benefit": "Can improve coverage of high-priority and critical loads within available capacity.", "trade_off": "Deferred services may be delayed or unavailable.",
            "assumptions": ["Demand response is feasible and priority assignments are approved."], "affected_zones": [z["zone"] for z in short_zones if z["resource_shortfalls"]["electricity"] > 0], "executed": False})
    if short_zones:
        actions.append({"rank": len(actions)+1, "triggering_condition": "One or more resource shortfalls remain under the supplied capacities.",
            "proposed_action": "Simulate alternative explicitly supplied electricity or water capacities and compare service coverage.",
            "expected_benefit": "Shows whether additional capacity would close the modeled gap.", "trade_off": "Alternative capacity is hypothetical and may not be operationally available.",
            "assumptions": ["Tested capacities are scenario inputs, not confirmed supply."], "affected_zones": [z["zone"] for z in short_zones], "executed": False})
    return actions


def simulate_emergency(baseline, scenario):
    if not isinstance(scenario, dict) or not isinstance(scenario.get("changes", {}), dict):
        raise ValueError("scenario must be an object with an optional changes object.")
    before = analyze_emergency(baseline)
    candidate = copy.deepcopy(baseline)
    changes = scenario.get("changes", {})
    for field in ("availability", "zones", "solar_generation_mw", "solar_reduction_fraction", "dependencies", "assumptions"):
        if field in changes:
            candidate[field] = copy.deepcopy(changes[field])
    candidate["name"] = scenario.get("name", "Alternative scenario")
    after = analyze_emergency(candidate)
    return {"status": "simulated", "baseline": before, "scenario": after,
        "comparison": {"severity_changed": before["overall_severity"] != after["overall_severity"],
            "risk_score_change": round(after["risk_score"]-before["risk_score"], 2),
            "affected_zones_before": before["affected_zones"], "affected_zones_after": after["affected_zones"],
            "shortfalls_before": before["resource_shortfalls"], "shortfalls_after": after["resource_shortfalls"],
            "critical_service_coverage_before": before["critical_service_coverage_percent"],
            "critical_service_coverage_after": after["critical_service_coverage_percent"]}}


def built_in_scenarios():
    """Return five fixed, clearly labeled demonstration scenarios."""
    base = [{"zone": "Central District", "priority": "high", "electricity_demand_mw": 45, "water_demand_litres": 1_900_000, "critical_service_requirements": {"electricity_mw": 8, "water_litres": 300_000}},
            {"zone": "North Residential", "priority": "medium", "electricity_demand_mw": 33, "water_demand_litres": 2_300_000},
            {"zone": "South Industrial", "priority": "standard", "electricity_demand_mw": 59, "water_demand_litres": 1_500_000},
            {"zone": "Riverside", "priority": "medium", "electricity_demand_mw": 28, "water_demand_litres": 1_200_000}]
    def build(name, desc, e, w, solar=8, reduction=0, zones=None):
        return {"name": name, "description": desc, "zones": copy.deepcopy(zones or base),
                "availability": {"electricity_mw": e, "water_litres": w}, "solar_generation_mw": solar,
                "solar_reduction_fraction": reduction, "assumptions": ["Fictional demonstration inputs for scenario comparison; not live city measurements."]}
    hospital = copy.deepcopy(base); hospital[0]["critical_service_requirements"] = {"electricity_mw": 20, "water_litres": 800_000}
    cases = [build("Normal city operations", "Explicit capacity sufficient for declared demand.", 180, 7_000_000),
        build("Heatwave: increased demand", "Simulated increased demand with fixed explicit capacities.", 150, 6_200_000,
              zones=[dict(z, electricity_demand_mw=z["electricity_demand_mw"]*1.2, water_demand_litres=z["water_demand_litres"]*1.15) for z in base]),
        build("Solar generation reduction", "Simulated reduction in the supplied solar contribution.", 155, 7_000_000, 8, .6),
        build("Combined electricity and water shortage", "Simulated shortages in both explicitly supplied resources.", 90, 3_000_000),
        build("Hospital emergency during resource shortage", "Simulated hospital critical-service requirements under constrained capacities.", 100, 3_500_000, zones=hospital)]
    return [{"id": f"scenario-{i+1}", "name": case["name"], "description": case["description"],
             "data_label": "simulated demonstration scenario; not a live event", "scenario": case,
             "analysis": analyze_emergency(case)} for i, case in enumerate(cases)]

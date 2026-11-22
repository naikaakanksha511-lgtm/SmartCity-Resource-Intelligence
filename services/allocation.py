"""Explainable, deterministic allocation for caller-supplied scenarios.

This is a priority and proportional-fairness heuristic, not a mathematical
optimizer. Capacities and critical loads must be supplied explicitly. Optional
solar is added to electricity capacity only when explicitly enabled by input.
"""
import math

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "standard": 3}
RESOURCE_FIELDS = {
    "electricity": ("electricity_demand", "electricity_critical_demand", "electricity_mw"),
    "water": ("water_demand", "water_critical_demand", "water_litres"),
}


def _number(value, label):
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite non-negative number.")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a finite non-negative number.") from None
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{label} must be a finite non-negative number.")
    return result


def _validate(scenario):
    if not isinstance(scenario, dict):
        raise ValueError("Request body must be a JSON object.")
    zones = scenario.get("zones")
    availability = scenario.get("availability")
    if not isinstance(zones, list) or not zones:
        raise ValueError("zones must be a non-empty list.")
    if not isinstance(availability, dict):
        raise ValueError("availability must explicitly supply electricity_mw and water_litres.")
    caps = {key: _number(availability.get(key), f"availability.{key}") for key in ("electricity_mw", "water_litres")}
    solar = _number(scenario.get("solar_generation_mw", 0), "solar_generation_mw")
    clean, seen = [], set()
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
        if not isinstance(priority, str) or priority.casefold() not in PRIORITY_ORDER:
            raise ValueError(f"zones[{i}].priority must be critical, high, medium, or standard.")
        row = {"zone": name, "priority": priority.casefold()}
        for resource, (demand_key, critical_key, _) in RESOURCE_FIELDS.items():
            demand = _number(zone.get(demand_key), f"zones[{i}].{demand_key}")
            critical = _number(zone.get(critical_key, 0), f"zones[{i}].{critical_key}")
            if critical > demand:
                raise ValueError(f"zones[{i}].{critical_key} cannot exceed {demand_key}.")
            row[demand_key], row[critical_key] = demand, critical
        clean.append(row)
    return clean, caps, solar


def _distribute(rows, remaining, resource, critical_only):
    demand_key, critical_key, _ = RESOURCE_FIELDS[resource]
    tranche_key = f"{resource}_{'critical' if critical_only else 'regular'}_allocated"
    for priority in sorted(PRIORITY_ORDER, key=PRIORITY_ORDER.get):
        eligible = [r for r in rows if r["priority"] == priority]
        needs = {r["zone"]: max(0.0, (r[critical_key] if critical_only else r[demand_key] - r[critical_key]) - r[tranche_key]) for r in eligible}
        total = sum(needs.values())
        if total <= 0 or remaining <= 0:
            continue
        fraction = min(1.0, remaining / total)
        for row in eligible:
            row[tranche_key] += needs[row["zone"]] * fraction
        remaining = max(0.0, remaining - min(remaining, total))
    return remaining


def run_allocation(scenario):
    """Allocate one validated scenario; equal-tier needs share proportionally."""
    zones, capacities, solar = _validate(scenario)
    output = []
    totals = {}
    for resource, (_, _, capacity_key) in RESOURCE_FIELDS.items():
        capacity = capacities[capacity_key] + (solar if resource == "electricity" else 0.0)
        for row in zones:
            row[f"{resource}_critical_allocated"] = 0.0
            row[f"{resource}_regular_allocated"] = 0.0
        remaining = _distribute(zones, capacity, resource, True)
        remaining = _distribute(zones, remaining, resource, False)
        allocated_total = 0.0
        for row in zones:
            demand_key, critical_key, unit = RESOURCE_FIELDS[resource]
            allocated = row[f"{resource}_critical_allocated"] + row[f"{resource}_regular_allocated"]
            demand = row[demand_key]
            unmet = max(0.0, demand - allocated)
            critical_allocated = min(row[critical_key], allocated)
            output_row = next((item for item in output if item["zone"] == row["zone"]), None)
            if output_row is None:
                output_row = {"zone": row["zone"], "priority": row["priority"]}
                output.append(output_row)
            output_row[resource] = {
                "demand": demand, "allocation": allocated, "unmet_demand": unmet,
                "critical_requirement": row[critical_key], "critical_allocated": critical_allocated,
                "critical_service_coverage_percent": None if row[critical_key] == 0 else 100.0 * critical_allocated / row[critical_key],
                "unit": unit,
            }
            output_row[resource]["explanation"] = _explain(row, resource, allocated, unmet, critical_allocated, capacity, solar if resource == "electricity" else 0)
            allocated_total += allocated
        totals[resource] = {"capacity": capacity, "base_capacity": capacities[capacity_key], "solar_assumed_addition": solar if resource == "electricity" else 0.0,
                            "allocated": allocated_total, "unmet_demand": sum(max(0, r[RESOURCE_FIELDS[resource][0]] - r[f"{resource}_critical_allocated"] - r[f"{resource}_regular_allocated"]) for r in zones),
                            "utilisation_percent": 0.0 if capacity == 0 else 100.0 * allocated_total / capacity,
                            "unit": RESOURCE_FIELDS[resource][2]}
    assumptions = scenario.get("assumptions", [])
    if isinstance(assumptions, str) or not isinstance(assumptions, list) or not all(isinstance(item, str) for item in assumptions):
        raise ValueError("assumptions must be a list of strings.")
    return {"status": "simulated", "algorithm": "priority-first proportional fairness heuristic", "priority_order": list(PRIORITY_ORDER),
            "assumptions": assumptions + (["Solar generation was added one-for-one to electricity capacity as an explicit scenario assumption; no grid integration or storage losses modeled."] if solar else []),
            "availability_source": "caller-supplied scenario inputs", "resources": totals, "zones": output,
            "critical_service_coverage_percent": {r: (None if sum(z[r]["critical_requirement"] for z in output) == 0 else 100.0 * sum(z[r]["critical_allocated"] for z in output) / sum(z[r]["critical_requirement"] for z in output)) for r in RESOURCE_FIELDS}}


def _explain(row, resource, allocated, unmet, critical_allocated, capacity, solar):
    priority = row["priority"]
    pieces = []
    if row[f"{resource}_critical_demand"]:
        pieces.append(f"explicit critical requirement received {critical_allocated:g} first under the protected-service rule")
    pieces.append(f"{priority} priority tier was applied")
    pieces.append("available capacity was shared proportionally within the same priority tier" if unmet else "demand was fully covered after higher-priority requirements")
    pieces.append(f"{unmet:g} unmet" if unmet else "no unmet demand")
    if capacity == 0:
        pieces.append("zero supplied capacity")
    if solar:
        pieces.append(f"{solar:g} MW caller-supplied solar counted toward electricity capacity")
    return "; ".join(pieces) + "."


def simulate_allocation(baseline, scenario):
    """Apply explicit scenario deltas and return a comparable baseline result."""
    base_zones, caps, solar = _validate(baseline)
    changes = scenario.get("changes") if isinstance(scenario, dict) else None
    if not isinstance(changes, dict):
        raise ValueError("changes must be an object describing explicit scenario adjustments.")
    modified = {"zones": [dict(z) for z in base_zones], "availability": dict(baseline["availability"]), "solar_generation_mw": solar,
                "assumptions": list(baseline.get("assumptions", []))}
    factors = {key: _number(changes.get(key, 1), f"changes.{key}") for key in ("electricity_availability_multiplier", "water_availability_multiplier", "demand_multiplier")}
    for resource, cap_key in (("electricity", "electricity_mw"), ("water", "water_litres")):
        mult = factors[f"{resource}_availability_multiplier"]
        modified["availability"][cap_key] = caps[cap_key] * mult
    demand_mult = factors["demand_multiplier"]
    for zone in modified["zones"]:
        for resource, (demand_key, critical_key, _) in RESOURCE_FIELDS.items():
            zone[demand_key] *= demand_mult
            zone[critical_key] *= demand_mult
    if "solar_reduction_fraction" in changes:
        fraction = _number(changes["solar_reduction_fraction"], "changes.solar_reduction_fraction")
        if fraction > 1:
            raise ValueError("changes.solar_reduction_fraction must be between 0 and 1.")
        modified["solar_generation_mw"] *= 1 - fraction
    overrides = changes.get("priority_overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("changes.priority_overrides must be an object keyed by known zone names.")
    by_name = {z["zone"].casefold(): z for z in modified["zones"]}
    for name, priority in overrides.items():
        if not isinstance(name, str):
            raise ValueError("priority_overrides keys must be zone names.")
        if name.casefold() not in by_name:
            raise ValueError(f"Unknown zone in priority_overrides: {name}.")
        by_name[name.casefold()]["priority"] = priority
    modified["assumptions"].append("Scenario changes were supplied by the caller; adjusted capacities and demands are simulated.")
    baseline_result, scenario_result = run_allocation(baseline), run_allocation(modified)
    previous = {z["zone"]: z for z in baseline_result["zones"]}
    for zone in scenario_result["zones"]:
        before = previous[zone["zone"]]
        for resource in RESOURCE_FIELDS:
            delta = zone[resource]["allocation"] - before[resource]["allocation"]
            zone[resource]["change_vs_baseline"] = delta
            zone[resource]["change_explanation"] = (f"Allocation changed by {delta:+g} {zone[resource]['unit']} after scenario adjustments." if abs(delta) > 1e-9 else "Allocation is unchanged from baseline.")
    return {"status": "simulated", "scenario_name": scenario.get("name", "Scenario"), "baseline": baseline_result,
            "scenario": scenario_result, "changes": changes, "comparison": {r: {"allocation_change": scenario_result["resources"][r]["allocated"] - baseline_result["resources"][r]["allocated"],
            "unmet_demand_change": scenario_result["resources"][r]["unmet_demand"] - baseline_result["resources"][r]["unmet_demand"],
            "utilisation_change_percentage_points": scenario_result["resources"][r]["utilisation_percent"] - baseline_result["resources"][r]["utilisation_percent"]} for r in RESOURCE_FIELDS}}


def allocate_resources(demand, capacity, constraints=None):
    """Backward-compatible single-resource allocation interface."""
    if not isinstance(demand, dict):
        raise ValueError("demand must map zone names to non-negative quantities.")
    constraints = constraints or {}
    zones = [{"zone": name, "electricity_demand": value, "water_demand": 0,
              "priority": constraints.get("priorities", {}).get(name, "standard"),
              "electricity_critical_demand": constraints.get("critical_requirements", {}).get(name, 0)} for name, value in demand.items()]
    return run_allocation({"zones": zones, "availability": {"electricity_mw": capacity, "water_litres": 0}})["zones"]


def prioritize_critical_infrastructure(requests, priorities):
    """Sort explicit requests using caller-provided priority values."""
    return sorted(requests, key=lambda item: (priorities.get(item.get("zone"), math.inf), item.get("zone", "")))


def distribute_emergency_resources(needs, available_resources, policy):
    """Transparent wrapper for emergency needs; requires explicit resource capacity."""
    return allocate_resources(needs, available_resources, policy)

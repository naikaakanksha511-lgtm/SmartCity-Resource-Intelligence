"""Deterministic time-stepped city digital twin simulation.

Simulates multi-zone resource shortages, cascading risks, interventions,
and recovery over discrete time steps. All inputs are explicit scenario
configurations. No supply capacity is inferred from historical measurements.
Simulation outputs are clearly labeled as simulated, not real-world data.
"""
import copy
import math
from datetime import datetime, timedelta

from services.allocation import run_allocation
from services.emergency_intelligence import analyze_emergency, _severity


class SimulationState:
    """Immutable snapshot of city state at a single time step."""

    def __init__(self, timestamp, zones_state, city_totals, severity, risk_score, affected_zones, alerts):
        self.timestamp = timestamp.isoformat()
        self.zones = zones_state
        self.city_totals = city_totals
        self.severity = severity
        self.risk_score = risk_score
        self.affected_zones = affected_zones
        self.alerts = alerts
        self.step_data_label = "simulated state; not live city data"


class DigitalTwinSimulation:
    """Deterministic multi-hour city simulation."""

    def __init__(self, start_scenario, start_time=None, duration_hours=24, step_size_hours=1):
        """Initialize the digital twin with a starting scenario and configuration.

        Args:
            start_scenario: Initial city state (from emergency_intelligence format)
            start_time: datetime object (defaults to 2026-06-18T08:00:00 UTC)
            duration_hours: Total simulation length (default 24 hours)
            step_size_hours: Simulation interval (default 1 hour)
        """
        if not isinstance(start_scenario, dict):
            raise ValueError("start_scenario must be a valid scenario dictionary.")
        if duration_hours <= 0 or step_size_hours <= 0:
            raise ValueError("duration_hours and step_size_hours must be positive.")
        if duration_hours < step_size_hours:
            raise ValueError("step_size_hours cannot exceed duration_hours.")

        self.base_scenario = copy.deepcopy(start_scenario)
        self.duration_hours = duration_hours
        self.step_size_hours = step_size_hours
        self.num_steps = int(duration_hours / step_size_hours)

        if start_time is None:
            start_time = datetime(2026, 6, 18, 8, 0, 0)
        self.start_time = start_time
        self.current_step = 0
        self.simulation_state = []
        self.events = []
        self.interventions = []
        self._state_cache = {}

    def add_event(self, event_dict):
        """Schedule a time-dependent event (heatwave, disruption, recovery, etc.).

        Event structure:
        {
            "event_id": "unique-id",
            "type": "heatwave|supply_disruption|recovery|...",
            "start_hour": 2.0,
            "duration_hours": 4.0,
            "affected_zones": ["Zone A", "Zone B"],
            "magnitude": 1.2 (multiplier) or -50 (reduction),
            "field": "electricity_demand_mw|water_demand_litres|electricity_capacity|...",
            "explanation": "Human-readable event description",
            "assumptions": ["Assumption 1", "Assumption 2"]
        }
        """
        if not isinstance(event_dict, dict):
            raise ValueError("event must be a dictionary.")
        required = {"event_id", "type", "start_hour", "duration_hours", "affected_zones", "field"}
        missing = required - set(event_dict.keys())
        if missing:
            raise ValueError(f"event missing required keys: {', '.join(sorted(missing))}")
        event = copy.deepcopy(event_dict)
        if not isinstance(event["affected_zones"], list) or not event["affected_zones"]:
            raise ValueError("affected_zones must be a non-empty list.")
        try:
            event["start_hour"] = float(event["start_hour"])
            event["duration_hours"] = float(event["duration_hours"])
        except (TypeError, ValueError):
            raise ValueError("start_hour and duration_hours must be numeric.")
        if event["start_hour"] < 0 or event["duration_hours"] <= 0:
            raise ValueError("start_hour must be >= 0; duration_hours must be > 0.")
        self.events.append(event)
        return self

    def add_intervention(self, intervention_dict):
        """Schedule an intervention to be applied at a specified time.

        Intervention structure:
        {
            "intervention_id": "unique-id",
            "start_hour": 6.0,
            "type": "increase_capacity|protect_critical|reduce_demand|change_priority|restore|...",
            "affected_zones": ["Zone A"],
            "magnitude": 50.0 (MW added, or fraction 0–1),
            "action": "increase_electricity|increase_water|protect_electricity_critical|...",
            "explanation": "What this intervention does",
            "assumptions": ["Assumption 1"]
        }
        """
        if not isinstance(intervention_dict, dict):
            raise ValueError("intervention must be a dictionary.")
        required = {"intervention_id", "type", "start_hour", "affected_zones", "action"}
        missing = required - set(intervention_dict.keys())
        if missing:
            raise ValueError(f"intervention missing required keys: {', '.join(sorted(missing))}")
        intv = copy.deepcopy(intervention_dict)
        if not isinstance(intv["affected_zones"], list) or not intv["affected_zones"]:
            raise ValueError("affected_zones must be a non-empty list.")
        try:
            intv["start_hour"] = float(intv["start_hour"])
        except (TypeError, ValueError):
            raise ValueError("start_hour must be numeric.")
        if intv["start_hour"] < 0 or intv["start_hour"] >= self.duration_hours:
            raise ValueError(f"start_hour must be in [0, {self.duration_hours}).")
        self.interventions.append(intv)
        return self

    def run(self):
        """Execute the full deterministic simulation and return all time-step results."""
        self.simulation_state = []
        for step_index in range(self.num_steps):
            step_hour = step_index * self.step_size_hours
            step_time = self.start_time + timedelta(hours=step_hour)
            scenario = self._build_scenario_for_step(step_hour)
            analysis = analyze_emergency(scenario)
            state = SimulationState(
                timestamp=step_time,
                zones_state=analysis["zones"],
                city_totals=analysis["resource_shortfalls"],
                severity=analysis["overall_severity"],
                risk_score=analysis["risk_score"],
                affected_zones=analysis["affected_zones"],
                alerts=analysis["alerts"],
            )
            self.simulation_state.append(state)
            self.current_step = step_index + 1
        return self.simulation_state

    def _build_scenario_for_step(self, hour):
        """Construct the scenario for a specific simulation hour by applying events and interventions."""
        scenario = copy.deepcopy(self.base_scenario)
        scenario["name"] = f"{self.base_scenario.get('name', 'Simulation')} [Hour {hour}]"

        active_events = [e for e in self.events if e["start_hour"] <= hour < e["start_hour"] + e["duration_hours"]]
        active_interventions = [i for i in self.interventions if i["start_hour"] <= hour]

        for zone in scenario.get("zones", []):
            zone_events = [e for e in active_events if zone["zone"] in e["affected_zones"]]
            zone_interventions = [i for i in active_interventions if zone["zone"] in i["affected_zones"]]

            for event in zone_events:
                self._apply_event_to_zone(zone, event)

            for intervention in zone_interventions:
                self._apply_intervention_to_zone(zone, intervention)

        availability_adjustments = {}
        for event in active_events:
            if "availability" in event.get("field", ""):
                self._apply_event_to_availability(scenario, event, availability_adjustments)

        for intervention in active_interventions:
            self._apply_intervention_to_availability(scenario, intervention, availability_adjustments)

        return scenario

    def _apply_event_to_zone(self, zone, event):
        """Apply an event to a zone's demand or critical requirement."""
        field = event.get("field")
        magnitude = event.get("magnitude", 1.0)

        if field == "electricity_demand_mw":
            current = zone.get("electricity_demand_mw", 0)
            if isinstance(magnitude, (int, float)) and magnitude > 0:
                zone["electricity_demand_mw"] = current * magnitude
        elif field == "water_demand_litres":
            current = zone.get("water_demand_litres", 0)
            if isinstance(magnitude, (int, float)) and magnitude > 0:
                zone["water_demand_litres"] = current * magnitude

    def _apply_event_to_availability(self, scenario, event, seen):
        """Apply an event to city-level availability."""
        field = event.get("field")
        magnitude = event.get("magnitude", 1.0)
        event_id = event.get("event_id")

        if event_id in seen:
            return

        availability = scenario.get("availability", {})
        if field == "electricity_capacity" or field == "electricity_mw":
            if isinstance(magnitude, (int, float)):
                current = availability.get("electricity_mw", 0)
                availability["electricity_mw"] = max(0, current * magnitude if magnitude > 0 else current + magnitude)

        elif field == "water_capacity" or field == "water_litres":
            if isinstance(magnitude, (int, float)):
                current = availability.get("water_litres", 0)
                availability["water_litres"] = max(0, current * magnitude if magnitude > 0 else current + magnitude)

        elif field == "solar_reduction_fraction":
            if isinstance(magnitude, (int, float)) and 0 <= magnitude <= 1:
                scenario["solar_reduction_fraction"] = magnitude

        seen[event_id] = True

    def _apply_intervention_to_zone(self, zone, intervention):
        """Apply an intervention to a zone's state."""
        action = intervention.get("action", "")
        magnitude = intervention.get("magnitude", 0)

        if action == "protect_electricity_critical":
            if isinstance(magnitude, (int, float)):
                zone["critical_service_requirements"] = zone.get("critical_service_requirements", {})
                zone["critical_service_requirements"]["electricity_mw"] = magnitude

        elif action == "protect_water_critical":
            if isinstance(magnitude, (int, float)):
                zone["critical_service_requirements"] = zone.get("critical_service_requirements", {})
                zone["critical_service_requirements"]["water_litres"] = magnitude

        elif action == "reduce_electricity_demand":
            if isinstance(magnitude, (int, float)) and magnitude >= 0 and magnitude <= 1:
                current = zone.get("electricity_demand_mw", 0)
                zone["electricity_demand_mw"] = current * (1 - magnitude)

        elif action == "reduce_water_demand":
            if isinstance(magnitude, (int, float)) and magnitude >= 0 and magnitude <= 1:
                current = zone.get("water_demand_litres", 0)
                zone["water_demand_litres"] = current * (1 - magnitude)

        elif action == "change_priority":
            priority = intervention.get("new_priority", "standard")
            if priority in {"critical", "high", "medium", "standard"}:
                zone["priority"] = priority

    def _apply_intervention_to_availability(self, scenario, intervention, seen):
        """Apply an intervention to city-level availability."""
        action = intervention.get("action", "")
        magnitude = intervention.get("magnitude", 0)
        intv_id = intervention.get("intervention_id")

        if intv_id in seen:
            return

        availability = scenario.get("availability", {})
        if action == "increase_electricity":
            if isinstance(magnitude, (int, float)):
                availability["electricity_mw"] = availability.get("electricity_mw", 0) + magnitude

        elif action == "increase_water":
            if isinstance(magnitude, (int, float)):
                availability["water_litres"] = availability.get("water_litres", 0) + magnitude

        elif action == "restore_solar":
            if isinstance(magnitude, (int, float)) and magnitude >= 0:
                scenario["solar_reduction_fraction"] = max(0, scenario.get("solar_reduction_fraction", 0) - magnitude)

        seen[intv_id] = True

    def get_step(self, step_index):
        """Return the state at a specific simulation step."""
        if step_index < 0 or step_index >= len(self.simulation_state):
            raise IndexError(f"step_index {step_index} out of range [0, {len(self.simulation_state)-1}].")
        return self.simulation_state[step_index]

    def get_recovery_curve(self, metric="severity"):
        """Extract a time-series of a specific metric (e.g., severity, risk_score).

        Returns: List of (timestamp, value) tuples.
        """
        if not self.simulation_state:
            return []
        if metric == "severity":
            order = {"normal": 0, "warning": 1, "high": 2, "critical": 3}
            return [(s.timestamp, order.get(s.severity, 0)) for s in self.simulation_state]
        elif metric == "risk_score":
            return [(s.timestamp, s.risk_score) for s in self.simulation_state]
        elif metric == "affected_zones":
            return [(s.timestamp, len(s.affected_zones)) for s in self.simulation_state]
        else:
            raise ValueError(f"Unknown metric: {metric}")

    def compare_with_baseline(self, baseline_simulation):
        """Compare this simulation with a baseline, returning before-and-after metrics."""
        if not self.simulation_state or not baseline_simulation.simulation_state:
            raise ValueError("Both simulations must have been run.")
        if len(self.simulation_state) != len(baseline_simulation.simulation_state):
            raise ValueError("Simulations must have the same number of steps.")

        comparison = {
            "baseline_severity_sequence": [s.severity for s in baseline_simulation.simulation_state],
            "scenario_severity_sequence": [s.severity for s in self.simulation_state],
            "baseline_avg_risk_score": sum(s.risk_score for s in baseline_simulation.simulation_state) / len(
                baseline_simulation.simulation_state
            ),
            "scenario_avg_risk_score": sum(s.risk_score for s in self.simulation_state)
            / len(self.simulation_state),
            "baseline_max_risk_score": max(s.risk_score for s in baseline_simulation.simulation_state),
            "scenario_max_risk_score": max(s.risk_score for s in self.simulation_state),
            "baseline_total_affected_zone_hours": sum(len(s.affected_zones) for s in baseline_simulation.simulation_state),
            "scenario_total_affected_zone_hours": sum(len(s.affected_zones) for s in self.simulation_state),
            "severity_improved": self.simulation_state[-1].severity
            < baseline_simulation.simulation_state[-1].severity,
            "peak_risk_reduction": baseline_simulation.simulation_state[-1].risk_score
            - self.simulation_state[-1].risk_score,
        }
        return comparison

    def to_dict(self):
        """Serialize the simulation results to a dictionary."""
        return {
            "status": "simulated",
            "data_label": "deterministic simulation; not live city data",
            "start_time": self.start_time.isoformat(),
            "duration_hours": self.duration_hours,
            "step_size_hours": self.step_size_hours,
            "num_steps": self.num_steps,
            "current_step": self.current_step,
            "base_scenario_name": self.base_scenario.get("name", "Unknown"),
            "events_applied": len(self.events),
            "interventions_applied": len(self.interventions),
            "timeline": [
                {
                    "step": i,
                    "timestamp": s.timestamp,
                    "severity": s.severity,
                    "risk_score": s.risk_score,
                    "affected_zones": s.affected_zones,
                    "zone_count": len(s.affected_zones),
                    "alerts_count": len(s.alerts),
                }
                for i, s in enumerate(self.simulation_state)
            ],
            "simulation_data_label": "simulated state; not live city data",
        }


def run_digital_twin_simulation(config):
    """High-level API to configure, run, and return a digital twin simulation.

    Config structure:
    {
        "scenario": { ... emergency_intelligence scenario ... },
        "start_time": "2026-06-18T08:00:00" (optional, defaults to 08:00 UTC),
        "duration_hours": 24 (optional, default 24),
        "step_size_hours": 1 (optional, default 1),
        "events": [ { ... event dicts ... } ],
        "interventions": [ { ... intervention dicts ... } ]
    }
    """
    if not isinstance(config, dict):
        raise ValueError("config must be a dictionary.")
    if "scenario" not in config:
        raise ValueError("config must include a scenario.")

    scenario = config.get("scenario")
    start_time = config.get("start_time")
    if isinstance(start_time, str):
        try:
            start_time = datetime.fromisoformat(start_time)
        except (ValueError, TypeError):
            raise ValueError("start_time must be a valid ISO 8601 datetime string.")

    duration = float(config.get("duration_hours", 24))
    step_size = float(config.get("step_size_hours", 1))

    twin = DigitalTwinSimulation(scenario, start_time, duration, step_size)

    for event in config.get("events", []):
        twin.add_event(event)

    for intervention in config.get("interventions", []):
        twin.add_intervention(intervention)

    twin.run()
    return twin.to_dict()


def built_in_simulations():
    """Return a set of demonstration digital twin scenarios."""
    base_scenario = {
        "name": "Normal city baseline",
        "zones": [
            {
                "zone": "Central District",
                "priority": "high",
                "electricity_demand_mw": 45,
                "water_demand_litres": 1_900_000,
                "critical_service_requirements": {"electricity_mw": 8, "water_litres": 300_000},
            },
            {
                "zone": "North Residential",
                "priority": "medium",
                "electricity_demand_mw": 33,
                "water_demand_litres": 2_300_000,
            },
            {
                "zone": "South Industrial",
                "priority": "standard",
                "electricity_demand_mw": 59,
                "water_demand_litres": 1_500_000,
            },
            {
                "zone": "Riverside",
                "priority": "medium",
                "electricity_demand_mw": 28,
                "water_demand_litres": 1_200_000,
            },
        ],
        "availability": {"electricity_mw": 180, "water_litres": 7_000_000},
        "solar_generation_mw": 8,
        "solar_reduction_fraction": 0,
        "assumptions": ["Fictional demonstration inputs for 24-hour simulation."],
    }

    sims = []

    sims.append(
        {
            "id": "sim-1",
            "name": "Normal 24-hour city operations",
            "description": "Baseline with adequate supply; no events or interventions.",
            "config": {
                "scenario": copy.deepcopy(base_scenario),
                "duration_hours": 24,
                "step_size_hours": 1,
            },
        }
    )

    heatwave_scenario = copy.deepcopy(base_scenario)
    heatwave_scenario["name"] = "Heatwave with no intervention"
    heatwave_config = {
        "scenario": heatwave_scenario,
        "duration_hours": 24,
        "step_size_hours": 1,
        "events": [
            {
                "event_id": "heatwave-1",
                "type": "heatwave",
                "start_hour": 8,
                "duration_hours": 8,
                "affected_zones": ["Central District", "North Residential", "South Industrial", "Riverside"],
                "magnitude": 1.3,
                "field": "electricity_demand_mw",
                "explanation": "Heat event increases electricity demand by 30%.",
                "assumptions": ["Peak heat 08:00–16:00; proportional demand increase."],
            }
        ],
    }
    sims.append(
        {
            "id": "sim-2",
            "name": "Heatwave: 24-hour crisis scenario",
            "description": "Increased electricity demand without intervention.",
            "config": heatwave_config,
        }
    )

    heatwave_with_intervention = copy.deepcopy(base_scenario)
    heatwave_with_intervention["name"] = "Heatwave with intervention response"
    heatwave_intervention_config = {
        "scenario": heatwave_with_intervention,
        "duration_hours": 24,
        "step_size_hours": 1,
        "events": [
            {
                "event_id": "heatwave-2",
                "type": "heatwave",
                "start_hour": 8,
                "duration_hours": 8,
                "affected_zones": ["Central District", "North Residential", "South Industrial", "Riverside"],
                "magnitude": 1.3,
                "field": "electricity_demand_mw",
                "explanation": "Heat event increases electricity demand by 30%.",
                "assumptions": ["Peak heat 08:00–16:00."],
            }
        ],
        "interventions": [
            {
                "intervention_id": "intv-1",
                "type": "demand_reduction",
                "start_hour": 10,
                "affected_zones": ["South Industrial"],
                "action": "reduce_electricity_demand",
                "magnitude": 0.15,
                "explanation": "Industrial zone reduces non-essential load by 15% at heat onset.",
                "assumptions": ["Demand reduction feasible within 2 hours."],
            },
            {
                "intervention_id": "intv-2",
                "type": "capacity_boost",
                "start_hour": 10,
                "affected_zones": ["Central District"],
                "action": "increase_electricity",
                "magnitude": 25,
                "explanation": "Emergency power source adds 25 MW at 10:00.",
                "assumptions": ["Emergency generation available on 2-hour notice."],
            },
        ],
    }
    sims.append(
        {
            "id": "sim-3",
            "name": "Heatwave: with emergency intervention",
            "description": "Heatwave with demand reduction and capacity boost.",
            "config": heatwave_intervention_config,
        }
    )

    supply_disruption = copy.deepcopy(base_scenario)
    supply_disruption["name"] = "Supply disruption scenario"
    disruption_config = {
        "scenario": supply_disruption,
        "duration_hours": 24,
        "step_size_hours": 1,
        "events": [
            {
                "event_id": "disruption-1",
                "type": "supply_disruption",
                "start_hour": 12,
                "duration_hours": 4,
                "affected_zones": ["Central District", "South Industrial"],
                "magnitude": 0.5,
                "field": "electricity_capacity",
                "explanation": "Electricity supply reduced by 50% for 4 hours (12:00–16:00).",
                "assumptions": ["Partial outage in grid sector; recovery at 16:00."],
            }
        ],
        "interventions": [
            {
                "intervention_id": "intv-restore",
                "type": "restore",
                "start_hour": 16,
                "affected_zones": ["Central District", "South Industrial"],
                "action": "increase_electricity",
                "magnitude": 90,
                "explanation": "Restored electricity capacity at 16:00.",
                "assumptions": ["Emergency repairs completed by 16:00."],
            }
        ],
    }
    sims.append(
        {
            "id": "sim-4",
            "name": "Supply disruption and recovery",
            "description": "4-hour electricity outage with recovery at hour 16.",
            "config": disruption_config,
        }
    )

    return sims

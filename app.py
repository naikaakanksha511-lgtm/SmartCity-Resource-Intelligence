"""Flask application serving a simulated smart-city resource dashboard."""

from flask import Flask, jsonify, render_template, request
import pandas as pd
import numpy as np

from config import SAMPLE_DATA_PATH
from models.prediction import analyze_electricity_demand, predict_water_demand
from services.water_intelligence import analyze_water_usage, detect_water_anomalies
from services.solar_intelligence import analyze_solar_generation, compare_solar_to_demand, analyze_solar_weather
from services.allocation import run_allocation, simulate_allocation
from services.emergency_intelligence import analyze_emergency, simulate_emergency, built_in_scenarios
from services.digital_twin import run_digital_twin_simulation, built_in_simulations

REQUIRED_COLUMNS = {
    "timestamp", "city_zone", "electricity_demand_mw",
    "water_consumption_litres", "solar_generation_mw", "temperature_c",
    "resource_availability",
}


class InvalidZoneFilter(ValueError):
    """Raised when an optional API zone query is malformed."""


def load_resource_data(path=None):
    """Load and validate the fictional demonstration readings."""
    frame = pd.read_csv(path or SAMPLE_DATA_PATH)
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"Sample data is missing columns: {', '.join(sorted(missing))}")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="raise", utc=True)
    if frame["timestamp"].isna().any():
        raise ValueError("Sample data contains missing timestamps.")
    numeric_columns = REQUIRED_COLUMNS - {"timestamp", "city_zone"}
    frame[list(numeric_columns)] = frame[list(numeric_columns)].apply(pd.to_numeric, errors="raise")
    if frame.empty or frame["city_zone"].isna().any() or frame["city_zone"].astype(str).str.strip().eq("").any():
        raise ValueError("Sample data must contain records with a city zone.")
    if not np.isfinite(frame[list(numeric_columns)].to_numpy(dtype=float)).all():
        raise ValueError("Sample data contains missing or non-finite numeric readings.")
    nonnegative_columns = ["electricity_demand_mw", "water_consumption_litres", "solar_generation_mw"]
    if (frame[nonnegative_columns] < 0).any().any():
        raise ValueError("Demand, consumption, and generation readings must be non-negative.")
    if not frame["resource_availability"].between(0, 100).all():
        raise ValueError("Resource availability must be between 0 and 100.")
    return frame.sort_values(["timestamp", "city_zone"])


def load_zone_filtered_data(zone, path=None):
    """Load validated sample records and optionally select one known zone."""
    if zone is not None and (not zone.strip() or len(zone) > 100):
        raise InvalidZoneFilter("Zone must be a non-empty name of at most 100 characters.")
    frame = load_resource_data(path)
    if zone is not None:
        frame = frame[frame["city_zone"].str.casefold() == zone.strip().casefold()]
        if frame.empty:
            raise LookupError("Unknown city zone.")
    return frame


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object("config")
    if test_config:
        app.config.update(test_config)

    @app.get("/api/allocation/status")
    def allocation_status():
        return jsonify({"status": "ready", "algorithm": "priority-first proportional fairness heuristic",
                        "optimizer": "not used; deterministic auditable policy", "requires_explicit_inputs": ["zones with resource demands", "electricity_mw and water_litres availability"],
                        "solar": "optional caller-supplied MW, added one-for-one to electricity availability only when explicitly provided"})

    @app.post("/api/allocation/run")
    def allocation_run():
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json."}), 400
        try:
            return jsonify(run_allocation(request.get_json(silent=True)))
        except (ValueError, TypeError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/allocation/simulate")
    def allocation_simulate():
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json."}), 400
        try:
            body = request.get_json(silent=True)
            if not isinstance(body, dict) or "baseline" not in body or "scenario" not in body:
                raise ValueError("Request must include baseline and scenario objects.")
            return jsonify(simulate_allocation(body["baseline"], body["scenario"]))
        except (ValueError, TypeError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/emergency/status")
    def emergency_status():
        return jsonify({"status": "ready", "mode": "explicit-input simulated analysis",
                        "requires_explicit_inputs": ["zones with electricity_demand_mw and water_demand_litres", "availability.electricity_mw and availability.water_litres"],
                        "severity_thresholds": {"normal": "<25", "warning": "25-<50", "high": "50-<75", "critical": ">=75"},
                        "dependencies": "configurable scenario assumptions; not causal findings from sample data"})

    @app.get("/api/emergency/scenarios")
    def emergency_scenarios():
        return jsonify({"status": "simulated", "data_label": "fictional demonstration scenarios; not live events",
                        "scenarios": built_in_scenarios()})

    @app.post("/api/emergency/analyze")
    def emergency_analyze():
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json."}), 400
        try:
            return jsonify(analyze_emergency(request.get_json(silent=True)))
        except (ValueError, TypeError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/emergency/simulate")
    def emergency_simulate():
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json."}), 400
        try:
            body = request.get_json(silent=True)
            if not isinstance(body, dict) or "baseline" not in body or "scenario" not in body:
                raise ValueError("Request must include baseline and scenario objects.")
            return jsonify(simulate_emergency(body["baseline"], body["scenario"]))
        except (ValueError, TypeError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/digital-twin/status")
    def digital_twin_status():
        return jsonify({"status": "ready", "mode": "deterministic multi-hour time-stepped simulation",
                        "default_duration_hours": 24, "default_step_size_hours": 1,
                        "requires_explicit_inputs": ["scenario with zones, demand, and availability",
                                                     "optional events (heatwave, disruption, recovery)",
                                                     "optional interventions (capacity increase, demand reduction)"],
                        "data_label": "simulated state; not live city data"})

    @app.get("/api/digital-twin/simulations")
    def digital_twin_simulations():
        return jsonify({"status": "simulated", "data_label": "fictional demonstration simulations; not live events",
                        "simulations": built_in_simulations()})

    @app.post("/api/digital-twin/run")
    def digital_twin_run():
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json."}), 400
        try:
            config = request.get_json(silent=True)
            if not isinstance(config, dict) or "scenario" not in config:
                raise ValueError("Request must include a scenario.")
            result = run_digital_twin_simulation(config)
            return jsonify(result)
        except (ValueError, TypeError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        try:
            load_resource_data()
            return jsonify({"status": "ok", "data": "simulated sample readings"})
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            app.logger.exception("Health check could not load sample data")
            return jsonify({"status": "error", "message": "Sample data is unavailable."}), 500

    @app.get("/api/resources")
    def resources():
        try:
            frame = load_resource_data()
            zone = request.args.get("zone", type=str)
            if zone:
                if len(zone) > 100:
                    return jsonify({"error": "Zone filter is too long."}), 400
                frame = frame[frame["city_zone"].str.casefold() == zone.strip().casefold()]
            rows = frame.copy()
            rows["timestamp"] = rows["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            records = rows.to_dict(orient="records")
            return jsonify({"data_type": "simulated", "records": records, "count": len(records)})
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            app.logger.exception("Resource data request failed")
            return jsonify({"error": "Resource sample data could not be loaded."}), 500

    @app.get("/api/predictions/energy")
    def energy_prediction():
        zone = request.args.get("zone")
        if zone is not None and (not zone.strip() or len(zone) > 100):
            return jsonify({"error": "Zone must be a non-empty name of at most 100 characters."}), 400
        try:
            frame = load_resource_data(app.config.get("SAMPLE_DATA_PATH", SAMPLE_DATA_PATH))
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            app.logger.exception("Electricity forecast could not load valid sample data")
            return jsonify({"error": "Electricity sample data is unavailable or invalid."}), 500
        try:
            result = analyze_electricity_demand(frame, zone=zone)
            if result["status"] == "insufficient_data":
                return jsonify(result), 200
            return jsonify(result)
        except ValueError as exc:
            status = 404 if str(exc) == "Unknown city zone." else 400
            return jsonify({"error": str(exc)}), status

    @app.get("/api/predictions/water")
    def water_prediction():
        try:
            frame = load_zone_filtered_data(request.args.get("zone"), app.config.get("SAMPLE_DATA_PATH", SAMPLE_DATA_PATH))
            return jsonify(predict_water_demand(frame))
        except InvalidZoneFilter as exc:
            return jsonify({"error": str(exc)}), 400
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except (OSError, ValueError, pd.errors.ParserError):
            app.logger.exception("Water forecast could not load valid sample data")
            return jsonify({"error": "Water sample data is unavailable or invalid."}), 500

    @app.get("/api/analytics/water")
    def water_analytics():
        try:
            frame = load_zone_filtered_data(request.args.get("zone"), app.config.get("SAMPLE_DATA_PATH", SAMPLE_DATA_PATH))
            return jsonify(analyze_water_usage(frame))
        except InvalidZoneFilter as exc:
            return jsonify({"error": str(exc)}), 400
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except (OSError, ValueError, pd.errors.ParserError):
            app.logger.exception("Water analytics could not load valid sample data")
            return jsonify({"error": "Water sample data is unavailable or invalid."}), 500

    @app.get("/api/alerts/water")
    def water_alerts():
        try:
            frame = load_zone_filtered_data(request.args.get("zone"), app.config.get("SAMPLE_DATA_PATH", SAMPLE_DATA_PATH))
            return jsonify(detect_water_anomalies(frame))
        except InvalidZoneFilter as exc:
            return jsonify({"error": str(exc)}), 400
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except (OSError, ValueError, pd.errors.ParserError):
            app.logger.exception("Water anomaly analysis could not load valid sample data")
            return jsonify({"error": "Water sample data is unavailable or invalid."}), 500

    def solar_frame():
        frame = pd.read_csv(app.config.get("SAMPLE_DATA_PATH", SAMPLE_DATA_PATH))
        if "timestamp" in frame.columns:
            frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True)
        return frame

    def solar_route(operation, label):
        zone = request.args.get("zone")
        if zone is not None and (not zone.strip() or len(zone) > 100):
            return jsonify({"error": "Zone must be a non-empty name of at most 100 characters."}), 400
        try:
            frame = solar_frame()
            result = operation(frame, zone=zone) if zone is not None else operation(frame)
            return jsonify(result)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (OSError, pd.errors.ParserError):
            app.logger.exception("%s could not load sample data", label)
            return jsonify({"error": "Solar sample data is unavailable or invalid."}), 500

    @app.get("/api/predictions/solar")
    def solar_prediction():
        return solar_route(analyze_solar_generation, "Solar forecast")

    @app.get("/api/analytics/solar")
    def solar_analytics():
        return solar_route(analyze_solar_generation, "Solar analytics")

    @app.get("/api/alerts/solar")
    def solar_alerts():
        return solar_route(analyze_solar_generation, "Solar alerts")

    @app.get("/api/solar-demand-comparison")
    def solar_demand_comparison():
        try:
            frame = solar_frame()
            zone = request.args.get("zone")
            if zone is not None:
                if not zone.strip() or len(zone) > 100:
                    return jsonify({"error": "Zone must be a non-empty name of at most 100 characters."}), 400
                if "city_zone" not in frame.columns:
                    return jsonify({"status": "unavailable", "reason": "Zone information is unavailable for solar-demand comparison.", "zones": [], "weather_analysis": {"status": "unavailable", "reason": "Zone information is unavailable.", "fields": []}})
                frame = frame[frame.city_zone.str.casefold() == zone.strip().casefold()]
                if frame.empty:
                    return jsonify({"error": "Unknown city zone."}), 404
            result = compare_solar_to_demand(frame)
            weather = analyze_solar_weather(frame)
            result["weather_analysis"] = weather
            return jsonify(result)
        except (OSError, ValueError, pd.errors.ParserError):
            app.logger.exception("Solar demand comparison could not load sample data")
            return jsonify({"error": "Solar sample data is unavailable or invalid."}), 500

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "Not found."}), 404

    @app.errorhandler(500)
    def internal_error(_error):
        return jsonify({"error": "An internal server error occurred."}), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

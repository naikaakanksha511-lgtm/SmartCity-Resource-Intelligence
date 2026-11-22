"""Water usage summaries, sample anomaly flags, and shortage assessment."""

import numpy as np

WATER_COLUMN = "water_consumption_litres"
MIN_BASELINE_READINGS = 3
STANDARD_DEVIATION_THRESHOLD = 2.0
SUDDEN_CHANGE_THRESHOLD = 0.30


def _validated_frame(frame):
    required = {"timestamp", "city_zone", WATER_COLUMN}
    if frame is None or not required.issubset(frame.columns):
        raise ValueError("Required water analysis columns are missing.")
    data = frame.copy().sort_values(["timestamp", "city_zone"])
    values = data[WATER_COLUMN].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Water consumption must contain finite, non-negative litre readings.")
    if data.empty or data["timestamp"].isna().any() or data["city_zone"].isna().any():
        raise ValueError("Water history must contain timestamps and city zones.")
    return data


def analyze_water_usage(frame):
    """Return per-zone statistics and historical readings in litres."""
    data = _validated_frame(frame)
    zones = []
    for city_zone, rows in data.groupby("city_zone", sort=True):
        values = rows[WATER_COLUMN].astype(float)
        zones.append({
            "city_zone": str(city_zone), "reading_count": int(len(values)),
            "average_consumption_litres": float(values.mean()),
            "minimum_consumption_litres": float(values.min()),
            "maximum_consumption_litres": float(values.max()),
            "latest_consumption_litres": float(values.iloc[-1]),
            "consumption_range_litres": float(values.max() - values.min()),
            "standard_deviation_litres": float(values.std(ddof=0)),
            "latest_timestamp": _iso(rows.iloc[-1]["timestamp"]),
        })
    historical = [{
        "timestamp": _iso(row.timestamp), "city_zone": str(row.city_zone),
        "consumption_litres": float(getattr(row, WATER_COLUMN)),
    } for row in data[["timestamp", "city_zone", WATER_COLUMN]].itertuples(index=False)]
    overall = data[WATER_COLUMN].astype(float)
    return {
        "status": "available", "data_source": "simulated sample data",
        "unit": "litres per sample reading interval", "zones": zones,
        "historical": historical,
        "overall": {
            "average_consumption_litres": float(overall.mean()),
            "minimum_consumption_litres": float(overall.min()),
            "maximum_consumption_litres": float(overall.max()),
            "latest_timestamp": _iso(data["timestamp"].max()),
            "reading_count": int(len(overall)),
        },
        "shortage_assessment": assess_water_shortage(),
    }


def detect_water_anomalies(frame):
    """Flag latest values against earlier readings; flags never prove a leak.

    A baseline requires at least three prior readings. High/low deviations use
    two sample standard deviations. A >=30% one-step change is also flagged.
    These are transparent screening thresholds, not infrastructure diagnosis.
    """
    data = _validated_frame(frame)
    assessments = []
    for city_zone, rows in data.groupby("city_zone", sort=True):
        rows = rows.sort_values("timestamp").reset_index(drop=True)
        observed = float(rows.iloc[-1][WATER_COLUMN])
        prior = rows.iloc[:-1][WATER_COLUMN].astype(float)
        if len(prior) < MIN_BASELINE_READINGS:
            assessments.append({
                "city_zone": str(city_zone), "status": "insufficient_history",
                "observed_consumption_litres": observed,
                "expected_consumption_litres": None, "deviation_litres": None,
                "severity": "unknown", "anomaly_type": None,
                "possible_leak_indicator": False,
                "explanation": f"At least {MIN_BASELINE_READINGS} earlier readings are required for anomaly screening.",
            })
            continue

        expected = float(prior.mean())
        deviation = observed - expected
        std = float(prior.std(ddof=1))
        z_score = deviation / std if std > 0 else None
        previous = float(prior.iloc[-1])
        relative_change = (observed - previous) / previous if previous > 0 else None
        anomaly_type = None
        if z_score is not None and z_score >= STANDARD_DEVIATION_THRESHOLD:
            anomaly_type = "unusually_high"
        elif z_score is not None and z_score <= -STANDARD_DEVIATION_THRESHOLD:
            anomaly_type = "unusually_low"
        elif relative_change is not None and abs(relative_change) >= SUDDEN_CHANGE_THRESHOLD:
            anomaly_type = "sudden_increase" if relative_change > 0 else "sudden_decrease"

        if anomaly_type:
            severity = "high" if (z_score is not None and abs(z_score) >= 3) or (relative_change is not None and abs(relative_change) >= 0.5) else "medium"
            leak_indicator = anomaly_type in {"unusually_high", "sudden_increase"}
            explanation = (
                f"Latest use differs from the prior-reading mean by {deviation:,.0f} L. "
                f"This is a possible unexpected-flow indicator only; it does not confirm a physical leak."
                if leak_indicator else
                f"Latest use is unusually low relative to the prior-reading baseline ({deviation:,.0f} L deviation); verify the meter and context."
            )
        else:
            severity = "none"
            leak_indicator = False
            explanation = "Latest reading is within the configured screening thresholds; this does not establish that the system is leak-free."
        assessments.append({
            "city_zone": str(city_zone), "status": "anomaly_flagged" if anomaly_type else "within_threshold",
            "observed_consumption_litres": observed,
            "expected_consumption_litres": expected,
            "deviation_litres": deviation,
            "standard_deviation_litres": std,
            "z_score": z_score,
            "relative_change_from_previous": relative_change,
            "severity": severity, "anomaly_type": anomaly_type,
            "possible_leak_indicator": leak_indicator,
            "explanation": explanation,
        })
    alerts = [item for item in assessments if item["status"] == "anomaly_flagged"]
    insufficient = any(item["status"] == "insufficient_history" for item in assessments)
    return {
        "status": "insufficient_history" if insufficient and not alerts else ("anomalies_detected" if alerts else "assessed_no_anomalies"),
        "data_source": "simulated sample data", "unit": "litres per sample reading interval",
        "method": "prior-reading mean and sample standard deviation (2σ), plus 30% one-step change screen",
        "thresholds": {"minimum_prior_readings": MIN_BASELINE_READINGS,
                       "standard_deviations": STANDARD_DEVIATION_THRESHOLD,
                       "relative_change": SUDDEN_CHANGE_THRESHOLD},
        "assessments": assessments, "alerts": alerts,
        "shortage_assessment": assess_water_shortage(),
        "caution": "An anomaly is a screening flag, not proof of a leak or other physical fault.",
    }


def assess_water_shortage(demand_litres=None, available_supply_litres=None, available_storage_litres=None):
    """Compare demand with explicitly supplied usable capacity, if available.

    The current CSV contains no water supply, storage, or usable-capacity
    measurements, so its default assessment is unavailable rather than guessed.
    """
    if available_supply_litres is None and available_storage_litres is None:
        return {
            "status": "not_assessable", "data_source": "no supply or storage data provided",
            "reason": "Shortage risk requires measured available supply or usable storage; neither exists in the sample CSV.",
            "required_inputs": ["available_supply_litres", "available_storage_litres"],
        }
    values = [value for value in (demand_litres, available_supply_litres, available_storage_litres) if value is not None]
    if any(not np.isfinite(float(value)) or float(value) < 0 for value in values):
        raise ValueError("Demand, supply, and available storage must be finite non-negative litre values.")
    if demand_litres is None:
        raise ValueError("Demand is required when evaluating a supplied-capacity scenario.")
    available = float(available_supply_litres or 0) + float(available_storage_litres or 0)
    demand = float(demand_litres)
    return {
        "status": "potential_shortage" if demand > available else "capacity_covers_demand",
        "data_source": "caller-supplied scenario assumptions; not measured city infrastructure data",
        "demand_litres": demand, "available_supply_litres": float(available_supply_litres or 0),
        "available_storage_litres": float(available_storage_litres or 0),
        "available_total_litres": available, "assumption": "Supplied values are treated as usable for the same sample interval.",
    }


def _iso(value):
    return value.isoformat().replace("+00:00", "Z") if hasattr(value, "isoformat") else str(value)

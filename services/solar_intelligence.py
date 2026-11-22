"""Solar generation summaries and transparent persistence baseline."""
import numpy as np

SOLAR_COLUMN = "solar_generation_mw"
LOW_GENERATION_THRESHOLD_MW = 2.0


def _validate(frame):
    required = {"timestamp", "city_zone", SOLAR_COLUMN}
    if frame is None or not required.issubset(getattr(frame, "columns", [])):
        return None, "Solar generation or required zone/time fields are unavailable."
    data = frame.copy()
    if data.empty:
        return None, "No solar readings are available."
    try:
        data[SOLAR_COLUMN] = __import__("pandas").to_numeric(data[SOLAR_COLUMN], errors="coerce")
        data["timestamp"] = __import__("pandas").to_datetime(data["timestamp"], errors="coerce", utc=True)
    except (TypeError, ValueError):
        return None, "Solar readings contain invalid values."
    data = data.dropna(subset=["timestamp", "city_zone", SOLAR_COLUMN])
    data = data[np.isfinite(data[SOLAR_COLUMN]) & (data[SOLAR_COLUMN] >= 0)]
    if data.empty:
        return None, "No valid, non-negative solar readings are available."
    return data.sort_values(["timestamp", "city_zone"]), None


def _iso(value):
    return value.isoformat().replace("+00:00", "Z")


def analyze_solar_generation(frame, zone=None, threshold_mw=LOW_GENERATION_THRESHOLD_MW):
    try:
        threshold_mw = float(threshold_mw)
    except (TypeError, ValueError):
        raise ValueError("Low-generation threshold must be finite and non-negative.")
    if not np.isfinite(threshold_mw) or threshold_mw < 0:
        raise ValueError("Low-generation threshold must be finite and non-negative.")
    source_count = len(frame) if frame is not None and hasattr(frame, "__len__") else 0
    data, reason = _validate(frame)
    if data is None:
        return {"status": "unavailable", "reason": reason, "data_source": "unavailable", "unit": "MW", "excluded_invalid_readings": source_count, "zones": [], "historical": [], "forecasts": [], "evaluation": None}
    excluded_readings = source_count - len(data)
    if zone is not None:
        if not isinstance(zone, str) or not zone.strip() or len(zone) > 100:
            raise ValueError("Zone must be a non-empty name of at most 100 characters.")
        data = data[data.city_zone.astype(str).str.casefold() == zone.strip().casefold()]
        if data.empty:
            raise LookupError("Unknown city zone.")
    zones, forecasts, actual, predicted, observations = [], [], [], [], []
    for name, rows in data.groupby("city_zone", sort=True):
        rows = rows.sort_values("timestamp").reset_index(drop=True)
        values = rows[SOLAR_COLUMN].astype(float)
        latest = rows.iloc[-1]
        zones.append({"city_zone": str(name), "reading_count": len(rows), "latest_generation_mw": float(values.iloc[-1]), "average_generation_mw": float(values.mean()), "minimum_generation_mw": float(values.min()), "maximum_generation_mw": float(values.max()), "latest_timestamp": _iso(latest.timestamp)})
        step = rows.timestamp.diff().dropna().median()
        forecast_time = _iso(latest.timestamp + step) if step is not None and not __import__("pandas").isna(step) else None
        forecasts.append({"city_zone": str(name), "forecast_timestamp": forecast_time, "predicted_generation_mw": float(values.iloc[-1]), "latest_actual_generation_mw": float(values.iloc[-1])})
        if len(rows) >= 2:
            origin, target = rows.iloc[-2], rows.iloc[-1]
            actual.append(float(target[SOLAR_COLUMN])); predicted.append(float(origin[SOLAR_COLUMN]))
            observations.append({"city_zone": str(name), "forecast_origin_timestamp": _iso(origin.timestamp), "actual_timestamp": _iso(target.timestamp), "actual_generation_mw": float(target[SOLAR_COLUMN]), "predicted_generation_mw": float(origin[SOLAR_COLUMN])})
    history = [{"timestamp": _iso(r.timestamp), "city_zone": str(r.city_zone), "generation_mw": float(getattr(r, SOLAR_COLUMN))} for r in data[["timestamp", "city_zone", SOLAR_COLUMN]].itertuples(index=False)]
    evaluation = None
    if actual:
        err = np.asarray(actual) - np.asarray(predicted)
        r2 = None
        total = np.square(np.asarray(actual) - np.mean(actual)).sum()
        if len(actual) >= 2 and total > 0:
            r2 = float(1 - np.square(err).sum() / total)
        evaluation = {"mae_mw": float(np.abs(err).mean()), "rmse_mw": float(np.sqrt(np.square(err).mean())), "r2": r2, "holdout_observations": len(actual), "reliable": False, "observations": observations}
    latest_alerts = [{"city_zone": z["city_zone"], "generation_mw": z["latest_generation_mw"], "threshold_mw": float(threshold_mw), "status": "low_generation"} for z in zones if z["latest_generation_mw"] < threshold_mw]
    return {"status": "baseline_forecast", "data_source": "simulated sample data", "unit": "MW", "excluded_invalid_readings": excluded_readings, "data_quality_note": "Rows with missing timestamps, zones, or invalid generation values are excluded." if excluded_readings else None, "zones": zones, "historical": history, "forecasts": forecasts, "method": "persistence baseline (last observed generation carried forward one observed interval)", "evaluation": evaluation, "evaluation_status": "exploratory_holdout" if evaluation else "insufficient_data", "evaluation_note": "Chronological final reading holdout per zone; exploratory only, four readings per zone in the supplied sample.", "low_generation_threshold_mw": float(threshold_mw), "alerts": latest_alerts}


def compare_solar_to_demand(frame):
    required = {"timestamp", "city_zone", SOLAR_COLUMN, "electricity_demand_mw"}
    if frame is None or not required.issubset(getattr(frame, "columns", [])):
        return {"status": "unavailable", "reason": "Solar generation and electricity demand with matching timestamps are required.", "zones": []}
    data = frame.copy()
    data[SOLAR_COLUMN] = __import__("pandas").to_numeric(data[SOLAR_COLUMN], errors="coerce")
    data["electricity_demand_mw"] = __import__("pandas").to_numeric(data["electricity_demand_mw"], errors="coerce")
    data["timestamp"] = __import__("pandas").to_datetime(data["timestamp"], errors="coerce", utc=True)
    if data.empty or data[[SOLAR_COLUMN, "electricity_demand_mw", "timestamp", "city_zone"]].isna().any().any():
        return {"status": "unavailable", "reason": "Missing measurements prevent a consistent solar-demand comparison.", "zones": []}
    if (data[[SOLAR_COLUMN, "electricity_demand_mw"]] < 0).any().any():
        return {"status": "unavailable", "reason": "Invalid negative measurements prevent comparison.", "zones": []}
    latest = data.sort_values("timestamp").groupby("city_zone", sort=True).tail(1)
    zones = []
    for row in latest.itertuples(index=False):
        demand, solar = float(row.electricity_demand_mw), float(getattr(row, SOLAR_COLUMN))
        zones.append({"city_zone": str(row.city_zone), "timestamp": _iso(row.timestamp), "electricity_demand_mw": demand, "solar_generation_mw": solar, "estimated_demand_not_covered_mw": max(demand - solar, 0.0), "solar_contribution_percent": (min(solar, demand) / demand * 100) if demand else None, "status": "available"})
    return {"status": "available", "unit": "MW", "data_source": "simulated sample data", "interpretation": "Arithmetic comparison only; generation does not necessarily equal electricity available to the grid.", "zones": zones}


def analyze_solar_weather(frame):
    if frame is None or not {SOLAR_COLUMN, "temperature_c"}.issubset(getattr(frame, "columns", [])):
        return {"status": "unavailable", "reason": "No suitable weather observations are available for solar relationship analysis.", "fields": []}
    data = frame[[SOLAR_COLUMN, "temperature_c"]].apply(__import__("pandas").to_numeric, errors="coerce").dropna()
    if len(data) < 2 or data.nunique().min() < 2:
        return {"status": "unavailable", "reason": "Insufficient variation or paired observations for exploratory correlation.", "fields": ["temperature_c"]}
    return {"status": "exploratory", "fields": ["temperature_c"], "paired_observations": len(data), "pearson_correlation": float(data[SOLAR_COLUMN].corr(data.temperature_c)), "note": "Exploratory correlation on simulated temperature and solar readings; it does not establish causation or weather forecast skill."}

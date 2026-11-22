"""Transparent electricity demand analysis and short-horizon baseline.

The included dataset is far too small and covers only one day. This module
therefore uses persistence (last observed demand) rather than fitting a model.
"""

import numpy as np
from services.water_intelligence import _validated_frame as _validated_water_frame, assess_water_shortage

DEMAND_COLUMN = "electricity_demand_mw"


def analyze_electricity_demand(frame, zone=None):
    """Summarize demand and issue one persistence forecast for each zone.

    Evaluation holds out the latest timestamp. The prediction for each held
    out zone is its immediately preceding observation, preserving chronology.
    Lag-1 and the mean of up to the last three prior readings are included as
    diagnostic features; the forecast deliberately uses lag-1 only.
    """
    if frame is None or frame.empty:
        return {"status": "insufficient_data", "reason": "No historical readings are available.",
                "method": "persistence baseline", "evaluation": None, "zones": [],
                "historical": [], "forecasts": [], "data_source": "simulated sample data"}

    required = {"timestamp", "city_zone", DEMAND_COLUMN}
    if not required.issubset(frame.columns):
        raise ValueError("Required electricity forecasting columns are missing.")
    data = frame.copy().sort_values(["timestamp", "city_zone"])
    values = data[DEMAND_COLUMN].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Electricity demand must contain finite, non-negative readings.")
    if data["timestamp"].isna().any() or data["city_zone"].isna().any():
        raise ValueError("Historical readings contain missing timestamps or zones.")
    if zone is not None:
        if not isinstance(zone, str) or not zone.strip() or len(zone) > 100:
            raise ValueError("Zone must be a non-empty name of at most 100 characters.")
        data = data[data["city_zone"].str.casefold() == zone.strip().casefold()]
        if data.empty:
            raise ValueError("Unknown city zone.")

    summaries = []
    forecasts = []
    for city_zone, rows in data.groupby("city_zone", sort=True):
        rows = rows.sort_values("timestamp").reset_index(drop=True)
        demand = rows[DEMAND_COLUMN].astype(float)
        summaries.append({
            "city_zone": city_zone, "average_demand_mw": float(demand.mean()),
            "maximum_demand_mw": float(demand.max()), "minimum_demand_mw": float(demand.min()),
            "demand_range_mw": float(demand.max() - demand.min()),
            "standard_deviation_mw": float(demand.std(ddof=0)),
            "high_demand": bool(demand.mean() >= data[DEMAND_COLUMN].mean()),
        })
        last = rows.iloc[-1]
        previous = demand.iloc[-2] if len(rows) >= 2 else None
        rolling = float(demand.iloc[max(0, len(rows) - 3):].mean())
        forecasts.append({
            "city_zone": city_zone,
            "forecast_timestamp": _next_timestamp(rows["timestamp"]),
            "predicted_demand_mw": float(last[DEMAND_COLUMN]),
            "historical_demand_mw": float(last[DEMAND_COLUMN]),
            "lag_1_demand_mw": float(last[DEMAND_COLUMN]),
            "previous_demand_mw": float(previous) if previous is not None else None,
            "prior_rolling_mean_3_mw": rolling,
        })

    # One chronological holdout point per zone, predicted solely from earlier rows.
    actual, predicted, holdout_observations = [], [], []
    for _, rows in data.groupby("city_zone", sort=True):
        rows = rows.sort_values("timestamp")
        if len(rows) >= 2:
            prior, target = rows.iloc[-2], rows.iloc[-1]
            actual_value = float(target[DEMAND_COLUMN])
            predicted_value = float(prior[DEMAND_COLUMN])
            actual.append(actual_value)
            predicted.append(predicted_value)
            holdout_observations.append({
                "city_zone": str(target["city_zone"]),
                "forecast_origin_timestamp": _iso(prior["timestamp"]),
                "actual_timestamp": _iso(target["timestamp"]),
                "actual_demand_mw": actual_value,
                "predicted_demand_mw": predicted_value,
                "absolute_error_mw": abs(actual_value - predicted_value),
            })
    evaluation = _metrics(actual, predicted)
    if evaluation is not None:
        evaluation["observations"] = holdout_observations
    timestamps = data["timestamp"].sort_values().drop_duplicates()
    historical = [{
        "timestamp": _iso(row.timestamp), "city_zone": row.city_zone,
        "demand_mw": float(getattr(row, DEMAND_COLUMN)),
        "hour_of_day": int(row.timestamp.hour),
    } for row in data[["timestamp", "city_zone", DEMAND_COLUMN]].itertuples(index=False)]
    return {
        "status": "baseline_forecast" if forecasts else "insufficient_data",
        "reason": None if forecasts else "No forecast can be produced.",
        "method": "persistence baseline (last observed demand)",
        "evaluation": evaluation,
        "evaluation_status": "exploratory_holdout" if evaluation else "insufficient_data",
        "evaluation_note": "Chronological final-timestamp holdout; exploratory only, with very few observations.",
        "zones": summaries, "historical": historical, "forecasts": forecasts,
        "next_interval_hours": _interval_hours(timestamps),
        "data_source": "simulated sample data",
    }


def _metrics(actual, predicted):
    if not actual:
        return None
    actual_array = np.asarray(actual, dtype=float)
    predicted_array = np.asarray(predicted, dtype=float)
    error = actual_array - predicted_array
    r2 = None
    if len(actual_array) >= 2 and not np.allclose(actual_array, actual_array.mean()):
        r2 = float(1 - np.square(error).sum() / np.square(actual_array - actual_array.mean()).sum())
    return {"mae_mw": float(np.abs(error).mean()), "rmse_mw": float(np.sqrt(np.square(error).mean())),
            "r2": r2, "holdout_observations": len(actual), "reliable": False}


def _interval_hours(timestamps):
    diffs = timestamps.diff().dropna().dt.total_seconds() / 3600
    return float(diffs.median()) if not diffs.empty else None


def _iso(value):
    return value.isoformat().replace("+00:00", "Z") if hasattr(value, "isoformat") else str(value)


def _next_timestamp(series):
    import pandas as pd
    timestamps = series.sort_values()
    diffs = timestamps.diff().dropna()
    step = diffs.median() if not diffs.empty else pd.Timedelta(hours=1)
    return _iso(timestamps.iloc[-1] + step)


def predict_electricity_demand(features):
    """Compatibility interface returning a persistence forecast from a frame."""
    return analyze_electricity_demand(features)


def predict_water_demand(frame, zone=None):
    """Forecast next-interval water consumption with a persistence baseline.

    Each zone carries its latest observed litre reading forward. Evaluation
    holds out the final reading per zone and compares it with the prior reading.
    This small, one-day dataset does not justify a fitted ML model.
    """
    if frame is None or frame.empty:
        return {
            "status": "insufficient_data", "data_source": "simulated sample data",
            "method": "persistence baseline (last observed consumption)",
            "historical": [], "forecasts": [], "evaluation": None,
            "evaluation_status": "insufficient_data",
            "shortage_assessment": assess_water_shortage(),
        }
    data = _validated_water_frame(frame)
    if zone is not None:
        if not isinstance(zone, str) or not zone.strip() or len(zone) > 100:
            raise ValueError("Zone must be a non-empty name of at most 100 characters.")
        data = data[data["city_zone"].str.casefold() == zone.strip().casefold()]
        if data.empty:
            raise ValueError("Unknown city zone.")
    forecasts = []
    actual, predicted, observations = [], [], []
    water_column = "water_consumption_litres"
    for city_zone, rows in data.groupby("city_zone", sort=True):
        rows = rows.sort_values("timestamp").reset_index(drop=True)
        latest = rows.iloc[-1]
        interval = rows["timestamp"].diff().dropna()
        step = interval.median() if not interval.empty else None
        forecast_timestamp = _iso(latest["timestamp"] + step) if step is not None else None
        forecasts.append({
            "city_zone": str(city_zone), "forecast_timestamp": forecast_timestamp,
            "predicted_consumption_litres": float(latest[water_column]),
            "latest_actual_consumption_litres": float(latest[water_column]),
        })
        if len(rows) >= 2:
            origin, target = rows.iloc[-2], rows.iloc[-1]
            actual_value = float(target[water_column])
            predicted_value = float(origin[water_column])
            actual.append(actual_value)
            predicted.append(predicted_value)
            observations.append({
                "city_zone": str(city_zone), "forecast_origin_timestamp": _iso(origin["timestamp"]),
                "actual_timestamp": _iso(target["timestamp"]),
                "actual_consumption_litres": actual_value,
                "predicted_consumption_litres": predicted_value,
                "absolute_error_litres": abs(actual_value - predicted_value),
            })
    history = [{
        "timestamp": _iso(row.timestamp), "city_zone": str(row.city_zone),
        "consumption_litres": float(getattr(row, water_column)),
    } for row in data[["timestamp", "city_zone", water_column]].itertuples(index=False)]
    evaluation = _water_metrics(actual, predicted)
    if evaluation is not None:
        evaluation["observations"] = observations
    return {
        "status": "baseline_forecast" if forecasts else "insufficient_data",
        "data_source": "simulated sample data", "unit": "litres per sample reading interval",
        "method": "persistence baseline (last observed consumption)",
        "evaluation": evaluation,
        "evaluation_status": "exploratory_holdout" if evaluation else "insufficient_data",
        "evaluation_note": "Chronological final-reading holdout per zone; exploratory only, with very few observations.",
        "historical": history, "forecasts": forecasts,
        "shortage_assessment": assess_water_shortage(),
    }


def _water_metrics(actual, predicted):
    if not actual:
        return None
    actual_array = np.asarray(actual, dtype=float)
    predicted_array = np.asarray(predicted, dtype=float)
    error = actual_array - predicted_array
    r2 = None
    total_variation = np.square(actual_array - actual_array.mean()).sum()
    if len(actual_array) >= 2 and not np.isclose(total_variation, 0):
        r2 = float(1 - np.square(error).sum() / total_variation)
    return {
        "mae_litres": float(np.abs(error).mean()),
        "rmse_litres": float(np.sqrt(np.square(error).mean())),
        "r2": r2, "holdout_observations": len(actual), "reliable": False,
    }


def predict_solar_generation(features):
    """Future interface; solar generation prediction is outside this milestone."""
    raise NotImplementedError("Solar generation model has not been implemented.")


def predict_shortage_risk(features):
    """Future interface; shortage risk prediction is outside this milestone."""
    raise NotImplementedError("Shortage risk model has not been implemented.")

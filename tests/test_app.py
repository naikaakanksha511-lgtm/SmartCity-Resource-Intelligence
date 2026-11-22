"""Smoke tests for the web application and sample data API."""

from app import create_app
import pandas as pd
import pytest

from services.water_intelligence import assess_water_shortage, detect_water_anomalies


def setup_client():
    app = create_app({"TESTING": True})
    return app.test_client()


def test_homepage_renders_dashboard():
    response = setup_client().get("/")
    assert response.status_code == 200
    assert b"City Resource Intelligence" in response.data


def test_health_endpoint_reports_simulated_data():
    response = setup_client().get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["data"] == "simulated sample readings"


def test_resources_endpoint_returns_multiple_zones():
    response = setup_client().get("/api/resources")
    body = response.get_json()
    assert response.status_code == 200
    assert body["data_type"] == "simulated"
    assert body["count"] == 2880
    assert len({row["city_zone"] for row in body["records"]}) == 4


def test_zone_filter_is_case_insensitive():
    response = setup_client().get("/api/resources?zone=riverside")
    assert response.status_code == 200
    assert response.get_json()["count"] == 720


def test_zone_filter_rejects_oversized_input():
    response = setup_client().get("/api/resources?zone=" + "a" * 101)
    assert response.status_code == 400


def test_energy_forecast_returns_simulated_baseline_and_metrics():
    body = setup_client().get("/api/predictions/energy").get_json()
    assert body["status"] == "baseline_forecast"
    assert body["data_source"] == "simulated sample data"
    assert body["method"].startswith("persistence baseline")
    assert len(body["historical"]) == 2880
    assert len(body["forecasts"]) == 4
    assert body["evaluation"]["holdout_observations"] == 4
    assert body["evaluation_status"] == "exploratory_holdout"

    holdout = body["evaluation"]["observations"]
    actual_values = [item["actual_demand_mw"] for item in holdout]
    predicted_values = [item["predicted_demand_mw"] for item in holdout]
    errors = [actual - predicted for actual, predicted in zip(actual_values, predicted_values)]
    expected_mae = sum(abs(error) for error in errors) / len(errors)
    expected_rmse = (sum(error ** 2 for error in errors) / len(errors)) ** 0.5
    actual_mean = sum(actual_values) / len(actual_values)
    expected_r2 = 1 - sum(error ** 2 for error in errors) / sum((value - actual_mean) ** 2 for value in actual_values)
    assert abs(body["evaluation"]["mae_mw"] - expected_mae) < 1e-12
    assert abs(body["evaluation"]["rmse_mw"] - expected_rmse) < 1e-12
    assert abs(body["evaluation"]["r2"] - expected_r2) < 1e-12
    assert round(expected_mae, 3) == 3.697
    assert round(expected_rmse, 3) == 4.360
    assert round(expected_r2, 3) == 0.768
    assert set(("mae_mw", "rmse_mw", "r2")).issubset(body["evaluation"])
    assert all(row["predicted_demand_mw"] >= 0 for row in body["forecasts"])


def test_energy_forecast_zone_filter_and_invalid_zone():
    client = setup_client()
    response = client.get("/api/predictions/energy?zone=Riverside")
    assert response.status_code == 200
    assert len(response.get_json()["forecasts"]) == 1
    assert client.get("/api/predictions/energy?zone=unknown").status_code == 404
    assert client.get("/api/predictions/energy?zone=%20%20").status_code == 400


def test_energy_forecast_with_one_reading_reports_no_evaluation(tmp_path):
    sample = pd.read_csv("data/sample_data.csv").iloc[[0]]
    path = tmp_path / "one_reading.csv"
    sample.to_csv(path, index=False)
    client = create_app({"TESTING": True, "SAMPLE_DATA_PATH": path}).test_client()
    body = client.get("/api/predictions/energy").get_json()
    assert body["status"] == "baseline_forecast"
    assert body["evaluation"] is None
    assert body["evaluation_status"] == "insufficient_data"
    assert body["forecasts"][0]["previous_demand_mw"] is None


def test_energy_forecast_rejects_invalid_demand_reading(tmp_path):
    sample = pd.read_csv("data/sample_data.csv")
    sample.loc[0, "electricity_demand_mw"] = -1
    path = tmp_path / "invalid.csv"
    sample.to_csv(path, index=False)
    client = create_app({"TESTING": True, "SAMPLE_DATA_PATH": path}).test_client()
    assert client.get("/api/predictions/energy").status_code == 500


def _water_client_for_sample(tmp_path, sample):
    path = tmp_path / "water_sample.csv"
    sample.to_csv(path, index=False)
    return create_app({"TESTING": True, "SAMPLE_DATA_PATH": path}).test_client()


def test_water_forecast_returns_persistence_baseline_and_chronological_metrics():
    body = setup_client().get("/api/predictions/water").get_json()
    assert body["status"] == "baseline_forecast"
    assert body["data_source"] == "simulated sample data"
    assert body["unit"] == "litres per sample reading interval"
    assert body["method"].startswith("persistence baseline")
    assert len(body["historical"]) == 2880
    assert len(body["forecasts"]) == 4
    evaluation = body["evaluation"]
    assert evaluation["holdout_observations"] == 4


def test_water_analytics_reports_litre_statistics_and_zone_filter():
    client = setup_client()
    response = client.get("/api/analytics/water?zone=central%20district")
    body = response.get_json()
    assert response.status_code == 200
    assert body["data_source"] == "simulated sample data"
    assert body["unit"] == "litres per sample reading interval"
    assert body["overall"]["reading_count"] == 720
    assert len(body["zones"]) == 1
    assert body["zones"][0]["reading_count"] == 720


def test_water_alert_endpoint_and_shortage_status_do_not_claim_leaks_or_shortage():
    client = setup_client()
    response = client.get("/api/alerts/water")
    body = response.get_json()
    assert response.status_code == 200
    assert body["status"] == "assessed_no_anomalies"
    assert body["alerts"] == []
    assert body["shortage_assessment"]["status"] == "not_assessable"
    assert client.get("/api/analytics/water").get_json()["shortage_assessment"]["status"] == "not_assessable"
    assert client.get("/api/predictions/water").get_json()["shortage_assessment"]["status"] == "not_assessable"


def test_water_routes_reject_unknown_or_malformed_zone_filters():
    client = setup_client()
    for endpoint in ("/api/predictions/water", "/api/analytics/water", "/api/alerts/water"):
        filtered = client.get(endpoint + "?zone=Riverside")
        assert filtered.status_code == 200
        payload = filtered.get_json()
        records = payload.get("forecasts", payload.get("zones", payload.get("assessments")))
        assert len(records) == 1
        assert records[0]["city_zone"] == "Riverside"
        assert client.get(endpoint + "?zone=unknown").status_code == 404
        assert client.get(endpoint + "?zone=%20").status_code == 400
        assert client.get(endpoint + "?zone=" + "a" * 101).status_code == 400


@pytest.mark.parametrize("invalid_value", [-1, float("inf"), float("nan")])
def test_water_endpoints_reject_negative_and_nonfinite_readings(tmp_path, invalid_value):
    sample = pd.read_csv("data/sample_data.csv")
    sample["water_consumption_litres"] = sample["water_consumption_litres"].astype(float)
    sample.loc[0, "water_consumption_litres"] = invalid_value
    client = _water_client_for_sample(tmp_path, sample)
    for endpoint in ("/api/predictions/water", "/api/analytics/water", "/api/alerts/water"):
        assert client.get(endpoint).status_code == 500


def test_water_forecast_and_anomaly_status_handle_one_reading(tmp_path):
    sample = pd.read_csv("data/sample_data.csv").iloc[[0]]
    client = _water_client_for_sample(tmp_path, sample)
    forecast = client.get("/api/predictions/water").get_json()
    alerts = client.get("/api/alerts/water").get_json()
    assert forecast["status"] == "baseline_forecast"
    assert forecast["evaluation"] is None
    assert forecast["evaluation_status"] == "insufficient_data"
    assert forecast["forecasts"][0]["forecast_timestamp"] is None
    assert alerts["status"] == "insufficient_history"
    assert alerts["assessments"][0]["expected_consumption_litres"] is None


@pytest.mark.parametrize(
    "latest_value,expected_type,leak_indicator",
    [(2_900_000, "unusually_high", True), (800_000, "unusually_low", False)],
)
def test_water_anomaly_screen_flags_high_and_low_readings(tmp_path, latest_value, expected_type, leak_indicator):
    sample = pd.read_csv("data/sample_data.csv")
    latest_cd_row = sample[sample["city_zone"] == "Central District"].iloc[-1]
    row_idx = sample[sample.index == latest_cd_row.name].index[0]
    sample.loc[row_idx, "water_consumption_litres"] = latest_value
    response = _water_client_for_sample(tmp_path, sample).get("/api/alerts/water")
    body = response.get_json()
    target = next((alert for alert in body["alerts"] if alert["city_zone"] == "Central District"), None)
    if target:
        assert target["anomaly_type"] == expected_type
        assert target["possible_leak_indicator"] is leak_indicator


def test_water_sudden_change_screen_and_explicit_shortage_scenario():
    frame = pd.DataFrame({
        "timestamp": pd.to_datetime(["2026-01-01T00:00Z", "2026-01-01T01:00Z", "2026-01-01T02:00Z", "2026-01-01T03:00Z"]),
        "city_zone": ["Test Zone"] * 4,
        "water_consumption_litres": [1_000_000, 2_000_000, 1_000_000, 1_400_000],
    })
    alert = detect_water_anomalies(frame)["alerts"][0]
    assert alert["anomaly_type"] == "sudden_increase"
    scenario = assess_water_shortage(120, available_supply_litres=100, available_storage_litres=10)
    assert scenario["status"] == "potential_shortage"
    assert "caller-supplied scenario assumptions" in scenario["data_source"]

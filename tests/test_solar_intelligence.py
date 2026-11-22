import pandas as pd
import pytest

from app import create_app
from services.solar_intelligence import analyze_solar_generation, compare_solar_to_demand, analyze_solar_weather


def client(path=None):
    config = {"TESTING": True}
    if path is not None:
        config["SAMPLE_DATA_PATH"] = path
    return create_app(config).test_client()


def test_solar_endpoints_and_zone_filter():
    c = client()
    forecast = c.get('/api/predictions/solar').get_json()
    assert forecast["status"] == "baseline_forecast"
    assert forecast["data_source"] == "simulated sample data"
    assert len(forecast["historical"]) == 2880
    assert len(forecast["zones"]) == 4
    assert c.get('/api/analytics/solar?zone=riverside').get_json()["zones"][0]["city_zone"] == "Riverside"
    assert c.get('/api/alerts/solar?zone=unknown').status_code == 404
    assert c.get('/api/predictions/solar?zone=%20').status_code == 400
    assert c.get('/api/alerts/solar').status_code == 200


def test_solar_forecast_metrics_and_screening():
    frame = pd.read_csv('data/sample_data.csv')
    frame['timestamp'] = pd.to_datetime(frame.timestamp, utc=True)
    result = analyze_solar_generation(frame)
    assert result['evaluation']['holdout_observations'] == 4
    assert result['evaluation']['mae_mw'] is not None
    assert result['evaluation']['rmse_mw'] is not None
    assert result['evaluation']['r2'] is None or (pd.notna(result['evaluation']['r2']) and result['evaluation']['r2'] <= 1)
    assert len(result['alerts']) >= 0


def test_solar_missing_and_invalid_data_handling(tmp_path):
    c0 = pd.DataFrame(columns=['timestamp', 'city_zone'])
    assert analyze_solar_generation(c0)['status'] == 'unavailable'
    frame = pd.read_csv('data/sample_data.csv').iloc[[0]].copy()
    frame['solar_generation_mw'] = -1
    frame['timestamp'] = pd.to_datetime(frame.timestamp, utc=True)
    assert analyze_solar_generation(frame)['status'] == 'unavailable'
    missing = pd.read_csv('data/sample_data.csv').drop(columns=['solar_generation_mw'])
    path = tmp_path / 'missing.csv'; missing.to_csv(path, index=False)
    assert client(path).get('/api/analytics/solar').get_json()['status'] == 'unavailable'
    bad = pd.read_csv('data/sample_data.csv'); bad.loc[0, 'solar_generation_mw'] = float('nan')
    path = tmp_path / 'bad.csv'; bad.to_csv(path, index=False)
    assert client(path).get('/api/predictions/solar').get_json()['status'] == 'baseline_forecast'


def test_solar_demand_comparison_and_weather():
    c = client()
    response = c.get('/api/solar-demand-comparison')
    body = response.get_json()
    assert response.status_code == 200 and body['status'] == 'available'
    central = next(row for row in body['zones'] if row['city_zone'] == 'Central District')
    assert central['electricity_demand_mw'] > 0
    assert central['solar_generation_mw'] >= 0
    assert central['estimated_demand_not_covered_mw'] >= 0
    assert c.get('/api/solar-demand-comparison?zone=Riverside').get_json()['zones'][0]['city_zone'] == 'Riverside'
    assert c.get('/api/solar-demand-comparison?zone=missing').status_code == 404
    unavailable = analyze_solar_weather(pd.DataFrame({'solar_generation_mw':[1,2]}))
    assert unavailable['status'] == 'unavailable'


def test_existing_electricity_and_water_endpoints_still_work():
    c = client()
    assert c.get('/api/predictions/energy').status_code == 200
    assert c.get('/api/predictions/water').status_code == 200
    assert c.get('/api/analytics/water').status_code == 200
    assert c.get('/api/alerts/water').status_code == 200

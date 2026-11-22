"""Integration tests for Digital Twin frontend and backend."""
import json
import pytest
from app import app


@pytest.fixture
def client():
    """Create a Flask test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_digital_twin_section_in_homepage(client):
    """Verify that the Digital Twin section is present in the homepage HTML."""
    response = client.get('/')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Check for Digital Twin nav item
    assert 'href="#digital-twin"' in html
    assert 'Digital Twin' in html
    
    # Check for Digital Twin section ID
    assert 'id="digital-twin"' in html
    
    # Check for required form controls
    assert 'id="dt-scenario"' in html
    assert 'id="dt-run"' in html
    assert 'id="dt-duration"' in html
    assert 'id="dt-step-size"' in html
    
    # Check for chart canvases
    assert 'id="dt-severity-chart"' in html
    assert 'id="dt-risk-chart"' in html
    
    # Check for step controls
    assert 'id="dt-prev-step"' in html
    assert 'id="dt-next-step"' in html


def test_digital_twin_status_endpoint(client):
    """Verify the Digital Twin status endpoint."""
    response = client.get('/api/digital-twin/status')
    assert response.status_code == 200
    data = json.loads(response.get_data(as_text=True))
    
    assert data['status'] == 'ready'
    assert 'mode' in data
    assert data['mode'] == 'deterministic multi-hour time-stepped simulation'
    assert data['default_duration_hours'] == 24
    assert data['default_step_size_hours'] == 1
    assert 'simulation_data_label' in data or 'data_label' in data


def test_digital_twin_simulations_endpoint(client):
    """Verify the Digital Twin simulations endpoint returns built-in scenarios."""
    response = client.get('/api/digital-twin/simulations')
    assert response.status_code == 200
    data = json.loads(response.get_data(as_text=True))
    
    assert 'simulations' in data
    simulations = data['simulations']
    assert len(simulations) >= 4, "Should have at least 4 built-in scenarios"
    
    # Verify each simulation has required fields
    for sim in simulations:
        assert 'id' in sim, f"Simulation missing 'id': {sim}"
        assert 'name' in sim, f"Simulation missing 'name': {sim}"
        assert 'description' in sim, f"Simulation missing 'description': {sim}"
        assert 'config' in sim, f"Simulation missing 'config': {sim}"
        
        config = sim['config']
        assert 'scenario' in config, f"Config missing 'scenario': {config}"
        assert 'duration_hours' in config
        assert 'step_size_hours' in config


def test_digital_twin_run_endpoint_normal_scenario(client):
    """Test the Digital Twin run endpoint with normal scenario."""
    # Get available scenarios
    sim_response = client.get('/api/digital-twin/simulations')
    simulations = json.loads(sim_response.get_data(as_text=True))['simulations']
    normal_sim = simulations[0]
    
    # Run the simulation
    run_response = client.post(
        '/api/digital-twin/run',
        data=json.dumps(normal_sim['config']),
        content_type='application/json'
    )
    
    assert run_response.status_code == 200
    result = json.loads(run_response.get_data(as_text=True))
    
    # Verify result structure
    assert 'timeline' in result
    assert isinstance(result['timeline'], list)
    assert len(result['timeline']) > 0, "Timeline should not be empty"
    assert result['duration_hours'] == normal_sim['config']['duration_hours']
    assert result['num_steps'] == int(normal_sim['config']['duration_hours'] / normal_sim['config']['step_size_hours'])
    
    # Verify each timeline entry
    for i, step in enumerate(result['timeline']):
        assert 'step' in step
        assert 'timestamp' in step
        assert 'severity' in step
        assert 'risk_score' in step
        assert 'affected_zones' in step
        assert 'zone_count' in step
        assert 'alerts_count' in step
        assert step['severity'] in ['normal', 'warning', 'high', 'critical']


def test_digital_twin_run_endpoint_heatwave_scenario(client):
    """Test the Digital Twin run endpoint with heatwave scenario (with events)."""
    sim_response = client.get('/api/digital-twin/simulations')
    simulations = json.loads(sim_response.get_data(as_text=True))['simulations']
    heatwave_sim = simulations[1]  # Heatwave scenario
    
    run_response = client.post(
        '/api/digital-twin/run',
        data=json.dumps(heatwave_sim['config']),
        content_type='application/json'
    )
    
    assert run_response.status_code == 200
    result = json.loads(run_response.get_data(as_text=True))
    
    # Should have events applied
    assert result['events_applied'] > 0, "Heatwave scenario should have events"
    
    # Timeline should show some warning or higher severity
    severities = [step['severity'] for step in result['timeline']]
    assert any(s != 'normal' for s in severities), "Heatwave should trigger some alerts"


def test_digital_twin_run_endpoint_heatwave_with_intervention(client):
    """Test the Digital Twin run endpoint with intervention scenario."""
    sim_response = client.get('/api/digital-twin/simulations')
    simulations = json.loads(sim_response.get_data(as_text=True))['simulations']
    intervention_sim = simulations[2]  # Heatwave with intervention
    
    run_response = client.post(
        '/api/digital-twin/run',
        data=json.dumps(intervention_sim['config']),
        content_type='application/json'
    )
    
    assert run_response.status_code == 200
    result = json.loads(run_response.get_data(as_text=True))
    
    # Should have both events and interventions applied
    assert result['events_applied'] > 0, "Should have events"
    assert result['interventions_applied'] > 0, "Should have interventions"


def test_digital_twin_run_endpoint_validation(client):
    """Test that the Digital Twin run endpoint validates inputs."""
    # Missing scenario
    response = client.post(
        '/api/digital-twin/run',
        data=json.dumps({}),
        content_type='application/json'
    )
    assert response.status_code == 400
    error = json.loads(response.get_data(as_text=True))
    assert 'error' in error
    
    # Invalid content type
    response = client.post(
        '/api/digital-twin/run',
        data='not json',
        content_type='text/plain'
    )
    assert response.status_code == 400


def test_digital_twin_data_labels(client):
    """Verify that all responses include proper data labels."""
    # Check status endpoint
    status_response = client.get('/api/digital-twin/status')
    status_data = json.loads(status_response.get_data(as_text=True))
    assert 'simulated' in str(status_data).lower() or 'demonstration' in str(status_data).lower() or 'data_label' in status_data
    
    # Check simulations endpoint
    sims_response = client.get('/api/digital-twin/simulations')
    sims_data = json.loads(sims_response.get_data(as_text=True))
    assert 'simulated' in sims_data.get('data_label', '').lower() or 'fictional' in sims_data.get('data_label', '').lower()
    
    # Check run response
    sim = sims_data['simulations'][0]
    run_response = client.post(
        '/api/digital-twin/run',
        data=json.dumps(sim['config']),
        content_type='application/json'
    )
    run_data = json.loads(run_response.get_data(as_text=True))
    assert 'simulation_data_label' in run_data
    assert 'simulated' in run_data['simulation_data_label'].lower()


def test_digital_twin_deterministic_reproducibility(client):
    """Verify that simulations are deterministic and produce identical results."""
    sim_response = client.get('/api/digital-twin/simulations')
    simulations = json.loads(sim_response.get_data(as_text=True))['simulations']
    sim_config = simulations[0]['config']
    
    # Run the same scenario twice
    run_response_1 = client.post(
        '/api/digital-twin/run',
        data=json.dumps(sim_config),
        content_type='application/json'
    )
    result_1 = json.loads(run_response_1.get_data(as_text=True))
    
    run_response_2 = client.post(
        '/api/digital-twin/run',
        data=json.dumps(sim_config),
        content_type='application/json'
    )
    result_2 = json.loads(run_response_2.get_data(as_text=True))
    
    # Both runs should produce identical results
    assert len(result_1['timeline']) == len(result_2['timeline'])
    for i in range(len(result_1['timeline'])):
        step_1 = result_1['timeline'][i]
        step_2 = result_2['timeline'][i]
        assert step_1['severity'] == step_2['severity'], f"Step {i} severity differs"
        assert step_1['risk_score'] == step_2['risk_score'], f"Step {i} risk score differs"
        assert step_1['affected_zones'] == step_2['affected_zones'], f"Step {i} affected zones differ"


def test_digital_twin_no_false_emergency_alerts_in_normal_scenario(client):
    """Verify that normal scenario produces no emergency alerts."""
    sim_response = client.get('/api/digital-twin/simulations')
    simulations = json.loads(sim_response.get_data(as_text=True))['simulations']
    normal_sim = simulations[0]  # Should be normal scenario
    
    run_response = client.post(
        '/api/digital-twin/run',
        data=json.dumps(normal_sim['config']),
        content_type='application/json'
    )
    
    result = json.loads(run_response.get_data(as_text=True))
    
    # Normal scenario should have all normal severity
    for step in result['timeline']:
        assert step['severity'] == 'normal', f"Normal scenario should not have {step['severity']} severity"
        assert step['risk_score'] == 0, "Normal scenario should have zero risk"
        assert len(step['affected_zones']) == 0, "Normal scenario should have no affected zones"
        assert step['alerts_count'] == 0, "Normal scenario should have no alerts"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

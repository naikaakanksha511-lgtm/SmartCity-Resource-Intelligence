/* The dashboard consumes only the Flask sample-data API. */
const number = (value, digits = 1) => new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }).format(value);
const escapeHtml = (value) => String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
let resourceChart;
let energyHistoryChart;
let energyForecastChart;
let waterHistoryChart;
let waterForecastChart;
let solarHistoryChart;
let solarDemandChart;
let allocationLatest = [];

function setText(id, value) { document.getElementById(id).textContent = value; }

function renderZones(records) {
  const latestTime = records.reduce((latest, item) => item.timestamp > latest ? item.timestamp : latest, '');
  const latest = records.filter(item => item.timestamp === latestTime);
  const body = document.getElementById('zone-rows');
  if (!latest.length) {
    body.innerHTML = '<tr><td colspan="6" class="table-message">No sample readings match this view.</td></tr>';
    return latest;
  }
  body.innerHTML = latest.map(row => {
    const watch = row.resource_availability < 70;
    const status = watch ? 'Watch' : 'Stable';
    return `<tr><td><span class="zone-dot ${watch ? 'watch' : ''}"></span>${escapeHtml(row.city_zone)}</td><td>${number(row.electricity_demand_mw)} MW</td><td>${number(row.water_consumption_litres / 1000000, 2)}M L</td><td>${number(row.solar_generation_mw)} MW</td><td>${number(row.resource_availability, 0)}%</td><td><span class="status-pill ${watch ? 'watch' : ''}">${status}</span></td></tr>`;
  }).join('');
  return latest;
}

function renderAlerts(latest) {
  const alerts = [];
  latest.forEach(row => {
    if (row.resource_availability < 70) alerts.push({ kind: 'warning', title: `${row.city_zone}: lower availability`, detail: `Sample availability is ${number(row.resource_availability, 0)}%. Review resource balance in this demonstration.` });
    if (row.electricity_demand_mw >= 55) alerts.push({ kind: 'info', title: `${row.city_zone}: elevated demand`, detail: `Sample electricity demand reached ${number(row.electricity_demand_mw)} MW.` });
  });
  setText('alert-count', String(alerts.length).padStart(2, '0'));
  document.getElementById('alert-list').innerHTML = alerts.length ? alerts.map(alert => `<div class="alert-item"><span class="alert-marker ${alert.kind}">${alert.kind === 'warning' ? '!' : '↗'}</span><div><strong>${escapeHtml(alert.title)}</strong><p>${escapeHtml(alert.detail)}</p></div></div>`).join('') : '<div class="table-message">No sample alerts at this interval.</div>';
}

function renderChart(records) {
  const grouped = new Map();
  records.forEach(row => {
    const label = new Date(row.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' });
    const item = grouped.get(label) || { demand: 0, solar: 0 };
    item.demand += row.electricity_demand_mw;
    item.solar += row.solar_generation_mw;
    grouped.set(label, item);
  });
  if (typeof Chart === 'undefined') return;
  if (resourceChart) resourceChart.destroy();
  resourceChart = new Chart(document.getElementById('resource-chart'), {
    type: 'line', data: { labels: [...grouped.keys()], datasets: [
      { label: 'Electricity demand', data: [...grouped.values()].map(item => Number(item.demand.toFixed(1))), borderColor: '#52a9ff', backgroundColor: '#52a9ff18', fill: true, tension: .35, pointRadius: 3, pointBackgroundColor: '#52a9ff' },
      { label: 'Solar generation', data: [...grouped.values()].map(item => Number(item.solar.toFixed(1))), borderColor: '#42d6a0', backgroundColor: '#42d6a012', fill: true, tension: .35, pointRadius: 3, pointBackgroundColor: '#42d6a0' }
    ] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } }, scales: { x: { grid: { color: '#22303e' }, ticks: { color: '#8492a2', font: { size: 9 } }, border: { display: false } }, y: { grid: { color: '#22303e' }, ticks: { color: '#8492a2', font: { size: 9 } }, border: { display: false }, title: { display: true, text: 'MW · zone total', color: '#8492a2', font: { size: 9 } } } } }
  });
}

function renderEnergyAnalysis(payload) {
  const error = document.getElementById('energy-error');
  error.hidden = true;
  const history = payload.historical || [];
  const forecasts = payload.forecasts || [];
  const zones = payload.zones || [];
  if (!history.length || !forecasts.length) throw new Error(payload.reason || 'Not enough data for an electricity forecast.');

  const demands = history.map(row => Number(row.demand_mw));
  const mean = demands.reduce((a, b) => a + b, 0) / demands.length;
  const highZones = zones.filter(zone => zone.high_demand).length;
  const stats = document.getElementById('energy-statistics');
  stats.innerHTML = [
    ['AVERAGE HISTORICAL DEMAND', number(mean), 'MW across readings'],
    ['MAXIMUM RECORDED', number(Math.max(...demands)), 'MW'],
    ['MINIMUM RECORDED', number(Math.min(...demands)), 'MW'],
    ['HIGH-DEMAND ZONES', String(highZones), 'zone averages at/above city average']
  ].map(item => `<div class="energy-stat"><small>${item[0]}</small><strong>${item[1]}</strong><span>${item[2]}</span></div>`).join('');

  document.getElementById('energy-zone-rows').innerHTML = zones.map(zone => {
    const forecast = forecasts.find(item => item.city_zone === zone.city_zone);
    return `<tr><td>${escapeHtml(zone.city_zone)}</td><td>${number(zone.average_demand_mw)} MW</td><td>${number(zone.maximum_demand_mw)} MW</td><td>${number(zone.demand_range_mw)} MW</td><td>${forecast ? `${number(forecast.predicted_demand_mw)} MW` : '—'}</td><td><span class="status-pill ${zone.high_demand ? 'watch' : ''}">${zone.high_demand ? 'High demand' : 'Typical'}</span></td></tr>`;
  }).join('');

  const colors = ['#52a9ff', '#42d6a0', '#f0b85d', '#bd9cff', '#ff707a', '#65c9d4'];
  const zoneNames = zones.map(zone => zone.city_zone);
  const timestamps = [...new Set(history.map(row => row.timestamp))].sort();
  if (typeof Chart !== 'undefined') {
    if (energyHistoryChart) energyHistoryChart.destroy();
    energyHistoryChart = new Chart(document.getElementById('energy-history-chart'), {
      type: 'line', data: { labels: timestamps.map(value => new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })), datasets: zoneNames.map((name, index) => ({ label: name, data: timestamps.map(timestamp => { const point = history.find(row => row.timestamp === timestamp && row.city_zone === name); return point ? point.demand_mw : null; }), borderColor: colors[index % colors.length], backgroundColor: colors[index % colors.length], tension: .25, spanGaps: true, pointRadius: 3 })) },
      options: chartOptions()
    });
    if (energyForecastChart) energyForecastChart.destroy();
    energyForecastChart = new Chart(document.getElementById('energy-forecast-chart'), {
      type: 'bar', data: { labels: zoneNames, datasets: [
        { label: 'Last historical demand', data: forecasts.map(item => item.historical_demand_mw), backgroundColor: '#52a9ffb0' },
        { label: 'Next interval baseline', data: forecasts.map(item => item.predicted_demand_mw), backgroundColor: '#42d6a0b0' }
      ] }, options: { ...chartOptions(), scales: { ...chartOptions().scales, x: { ...chartOptions().scales.x, ticks: { color: '#8492a2', font: { size: 9 } } } } }
    });
  }
  setText('forecast-method', `${payload.method}. Each zone’s most recent reading is carried forward by ${payload.next_interval_hours ?? 'an inferred'} hours. Lag-1 and prior rolling mean are exposed as diagnostic context; no fitted ML model is used.`);
  const evaluation = payload.evaluation;
  document.getElementById('forecast-evaluation').innerHTML = evaluation ? `<strong>Chronological holdout · ${evaluation.holdout_observations} observations</strong><span>MAE ${number(evaluation.mae_mw)} MW</span><span>RMSE ${number(evaluation.rmse_mw)} MW</span><span>R² ${evaluation.r2 === null ? 'not meaningful' : number(evaluation.r2, 3)}</span>` : '<strong>Evaluation unavailable</strong><span>Insufficient prior readings for a chronological holdout.</span>';
}

function chartOptions() {
  return { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true, labels: { color: '#a4b0bd', boxWidth: 8, font: { size: 9 } } }, tooltip: { mode: 'index', intersect: false } }, scales: { x: { grid: { color: '#22303e' }, ticks: { color: '#8492a2', font: { size: 9 } }, border: { display: false } }, y: { beginAtZero: true, grid: { color: '#22303e' }, ticks: { color: '#8492a2', font: { size: 9 } }, border: { display: false }, title: { display: true, text: 'Electricity demand · MW', color: '#8492a2', font: { size: 9 } } } } };
}

function renderWaterIntelligence(analytics, forecast, anomalyPayload) {
  const history = analytics.historical || [];
  const forecasts = forecast.forecasts || [];
  const zones = analytics.zones || [];
  const latestStamp = analytics.overall?.latest_timestamp;
  const latest = history.filter(row => row.timestamp === latestStamp);
  const latestTotal = latest.reduce((sum, row) => sum + row.consumption_litres, 0);
  const overall = analytics.overall || {};
  document.getElementById('water-statistics').innerHTML = [
    ['AVERAGE CONSUMPTION', number(overall.average_consumption_litres, 0), 'litres per sample reading'],
    ['MAXIMUM RECORDED', number(overall.maximum_consumption_litres, 0), 'litres'],
    ['MINIMUM RECORDED', number(overall.minimum_consumption_litres, 0), 'litres'],
    ['LATEST SAMPLE', number(latestTotal, 0), 'all monitored zones · litres']
  ].map(item => `<div class="energy-stat"><small>${item[0]}</small><strong>${item[1]}</strong><span>${item[2]}</span></div>`).join('');

  document.getElementById('water-zone-rows').innerHTML = zones.map(zone => {
    const next = forecasts.find(item => item.city_zone === zone.city_zone);
    return `<tr><td>${escapeHtml(zone.city_zone)}</td><td>${number(zone.average_consumption_litres, 0)} L</td><td>${number(zone.minimum_consumption_litres, 0)} L</td><td>${number(zone.maximum_consumption_litres, 0)} L</td><td>${number(zone.consumption_range_litres, 0)} L</td><td>${number(zone.latest_consumption_litres, 0)} L</td><td>${next ? `${number(next.predicted_consumption_litres, 0)} L` : '—'}</td></tr>`;
  }).join('');

  const colorSet = ['#52a9ff', '#42d6a0', '#f0b85d', '#bd9cff', '#ff707a', '#65c9d4'];
  const zoneNames = zones.map(zone => zone.city_zone);
  const timestamps = [...new Set(history.map(row => row.timestamp))].sort();
  if (typeof Chart !== 'undefined') {
    if (waterHistoryChart) waterHistoryChart.destroy();
    waterHistoryChart = new Chart(document.getElementById('water-history-chart'), {
      type: 'line', data: {
        labels: timestamps.map(value => new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })),
        datasets: zoneNames.map((name, index) => ({
          label: name,
          data: timestamps.map(timestamp => history.find(row => row.timestamp === timestamp && row.city_zone === name)?.consumption_litres ?? null),
          borderColor: colorSet[index % colorSet.length], backgroundColor: colorSet[index % colorSet.length], tension: .25, spanGaps: true, pointRadius: 3
        }))
      }, options: waterChartOptions()
    });
    if (waterForecastChart) waterForecastChart.destroy();
    waterForecastChart = new Chart(document.getElementById('water-forecast-chart'), {
      type: 'bar', data: { labels: zoneNames, datasets: [
        { label: 'Latest actual reading', data: forecasts.map(item => item.latest_actual_consumption_litres), backgroundColor: '#52a9ffb0' },
        { label: 'Next interval baseline', data: forecasts.map(item => item.predicted_consumption_litres), backgroundColor: '#42d6a0b0' }
      ] }, options: waterChartOptions()
    });
  }

  const anomalyAssessments = anomalyPayload.assessments || [];
  const anomalyAlerts = anomalyPayload.alerts || [];
  setText('water-alert-count', String(anomalyAlerts.length).padStart(2, '0'));
  const alertList = document.getElementById('water-alert-list');
  if (anomalyAlerts.length) {
    alertList.innerHTML = anomalyAlerts.map(item => `<div class="alert-item"><span class="alert-marker ${item.severity === 'high' ? 'warning' : 'info'}">!</span><div><strong>${escapeHtml(item.city_zone)}: ${escapeHtml(item.anomaly_type.replaceAll('_', ' '))} · ${escapeHtml(item.severity)}</strong><p>Observed ${number(item.observed_consumption_litres, 0)} L vs baseline ${number(item.expected_consumption_litres, 0)} L. ${escapeHtml(item.explanation)}</p></div></div>`).join('');
  } else if (anomalyAssessments.some(item => item.status === 'insufficient_history')) {
    alertList.innerHTML = '<div class="table-message">Insufficient prior readings for anomaly screening.</div>';
  } else {
    alertList.innerHTML = '<div class="table-message">No sample readings crossed the anomaly screening thresholds.</div>';
  }

  setText('water-forecast-method', `${forecast.method}. The most recent reading per zone is carried forward to the next interval. Evaluation holds out each zone’s final reading chronologically; these few simulated observations are exploratory only.`);
  const evaluation = forecast.evaluation;
  document.getElementById('water-forecast-evaluation').innerHTML = evaluation
    ? `<strong>Chronological holdout · ${evaluation.holdout_observations} observations</strong><span>MAE ${number(evaluation.mae_litres, 0)} L</span><span>RMSE ${number(evaluation.rmse_litres, 0)} L</span><span>R² ${evaluation.r2 === null ? 'not meaningful' : number(evaluation.r2, 3)}</span>`
    : '<strong>Evaluation unavailable</strong><span>Not enough earlier observations for a chronological holdout.</span>';

  const shortage = analytics.shortage_assessment || forecast.shortage_assessment || {};
  setText('water-shortage-status', shortage.status === 'not_assessable' ? 'Not assessable from this dataset' : shortage.status.replaceAll('_', ' '));
  setText('water-shortage-detail', shortage.reason || shortage.assumption || 'Supply and usable storage need to be provided for a shortage assessment.');
}

function waterChartOptions() {
  const options = chartOptions();
  options.scales.y.title.text = 'Water consumption · litres';
  return options;
}

async function loadSolarIntelligence() {
  const error = document.getElementById('solar-error'); 
  error.hidden = true;
  try {
    console.log('[Solar] Starting load');
    const [forecastResponse, comparisonResponse, alertResponse] = await Promise.all([
      fetch('/api/predictions/solar', { headers: { Accept: 'application/json' } }), 
      fetch('/api/solar-demand-comparison', { headers: { Accept: 'application/json' } }), 
      fetch('/api/alerts/solar', { headers: { Accept: 'application/json' } })
    ]);
    console.log('[Solar] Responses received:', forecastResponse.status, comparisonResponse.status, alertResponse.status);
    
    const [forecast, comparison, alerts] = await Promise.all([forecastResponse.json(), comparisonResponse.json(), alertResponse.json()]);
    for (const response of [forecastResponse, comparisonResponse, alertResponse]) {
      if (!response.ok) throw new Error(`Solar API returned ${response.status}`);
    }
    console.log('[Solar] Data parsed successfully');
    
    const history = forecast.historical || [], zones = forecast.zones || [], forecasts = forecast.forecasts || [];
    const values = history.map(row => row.generation_mw), latestTotal = zones.reduce((sum, row) => sum + row.latest_generation_mw, 0);
    const overall = values.length ? { avg: values.reduce((a,b)=>a+b,0)/values.length, min: Math.min(...values), max: Math.max(...values) } : null;
    document.getElementById('solar-statistics').innerHTML = overall ? [
      ['AVERAGE GENERATION', number(overall.avg), 'MW per reading'], ['MAXIMUM RECORDED', number(overall.max), 'MW'], ['MINIMUM RECORDED', number(overall.min), 'MW'], ['LATEST GENERATION', number(latestTotal), 'MW across zones']
    ].map(item => `<div class="energy-stat"><small>${item[0]}</small><strong>${item[1]}</strong><span>${item[2]}</span></div>`).join('') : '<div class="table-message">Solar readings unavailable.</div>';
    const comparisonRows = comparison.zones || [];
    document.getElementById('solar-demand-rows').innerHTML = comparisonRows.length ? comparisonRows.map(row => `<tr><td>${escapeHtml(row.city_zone)}</td><td>${number(row.electricity_demand_mw)} MW</td><td>${number(row.solar_generation_mw)} MW</td><td>${number(row.estimated_demand_not_covered_mw)} MW</td><td>${row.solar_contribution_percent === null ? '—' : `${number(row.solar_contribution_percent)}%`}</td></tr>`).join('') : `<tr><td colspan="5" class="table-message">${escapeHtml(comparison.reason || 'Comparison unavailable.')}</td></tr>`;
    const alertsList = alerts.alerts || [];
    setText('solar-alert-count', String(alertsList.length).padStart(2, '0'));
    document.getElementById('solar-alert-list').innerHTML = alertsList.length ? alertsList.map(item => `<div class="alert-item"><span class="alert-marker warning">!</span><div><strong>${escapeHtml(item.city_zone)}: low sample generation</strong><p>${number(item.generation_mw)} MW is below the ${number(item.threshold_mw)} MW screening threshold.</p></div></div>`).join('') : '<div class="table-message">No latest readings below the screening threshold.</div>';
    setText('solar-forecast-method', `${forecast.method || 'Forecast unavailable'}. Latest timestamp and readings per zone are carried forward. Evaluation uses chronological final-reading holdout.`);
    const evaluation = forecast.evaluation;
    document.getElementById('solar-forecast-evaluation').innerHTML = evaluation ? `<strong>Chronological holdout · ${evaluation.holdout_observations} observations</strong><span>MAE ${number(evaluation.mae_mw)} MW</span><span>RMSE ${number(evaluation.rmse_mw)} MW</span><span>R² ${evaluation.r2 === null ? 'not meaningful' : number(evaluation.r2, 3)}</span>` : '<strong>Evaluation unavailable</strong><span>Insufficient earlier readings.</span>';
    const weather = comparison.weather_analysis || {status:'unavailable', reason:comparison.reason};
    setText('solar-weather-status', weather.status === 'exploratory' ? `Temperature relationship: Pearson r = ${number(weather.pearson_correlation, 3)} (${weather.paired_observations} paired simulated readings). Exploratory only.` : `${weather.status}: ${weather.reason || 'No suitable weather fields.'}`);
    if (typeof Chart !== 'undefined' && history.length) {
      const colors = ['#52a9ff','#42d6a0','#f0b85d','#bd9cff','#ff707a'];
      const names = zones.map(item => item.city_zone), stamps = [...new Set([...history.map(item => item.timestamp), ...forecasts.map(item => item.forecast_timestamp).filter(Boolean)])].sort();
      if (solarHistoryChart) solarHistoryChart.destroy();
      solarHistoryChart = new Chart(document.getElementById('solar-history-chart'), {type:'line',data:{labels:stamps.map(value=>new Date(value).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',timeZone:'UTC'})),datasets:names.flatMap((name,i)=>[{label:`${name} · historical`,data:stamps.map(timestamp=>history.find(row=>row.timestamp===timestamp&&row.city_zone===name)?.generation_mw??null),borderColor:colors[i%colors.length],backgroundColor:colors[i%colors.length],tension:.25,spanGaps:true,pointRadius:3},{label:`${name} · forecast`,data:stamps.map(timestamp=>{const forecast=forecasts.find(item=>item.city_zone===name);return forecast?.forecast_timestamp===timestamp?forecast.predicted_generation_mw:null;}),borderColor:colors[i%colors.length],backgroundColor:colors[i%colors.length],borderDash:[5,4],showLine:false,pointStyle:'rectRot',pointRadius:5,spanGaps:true}])},options:solarChartOptions('Solar generation · MW')});
      if (solarDemandChart) solarDemandChart.destroy();
      solarDemandChart = new Chart(document.getElementById('solar-demand-chart'), {type:'bar',data:{labels:comparisonRows.map(row=>row.city_zone),datasets:[{label:'Electricity demand',data:comparisonRows.map(row=>row.electricity_demand_mw),backgroundColor:'#52a9ffb0'},{label:'Solar generation',data:comparisonRows.map(row=>row.solar_generation_mw),backgroundColor:'#f0b85db0'}]},options:solarChartOptions('Matched readings · MW')});
    }
    console.log('[Solar] Load complete');
  } catch (failure) { 
    console.error('[Solar] Error:', failure.message);
    error.textContent = `Solar intelligence unavailable: ${failure.message}`; 
    error.hidden = false; 
    document.getElementById('solar-demand-rows').innerHTML = '<tr><td colspan="5" class="table-message">Solar analysis unavailable</td></tr>';
  }
}

function solarChartOptions(title) { const options = chartOptions(); options.scales.y.title.text = title; return options; }

function renderAllocationInputs(latest) {
  allocationLatest = latest;
  document.getElementById('allocation-zone-inputs').innerHTML = latest.map((row, index) => `<tr><td>${escapeHtml(row.city_zone)}<small class="allocation-demand">${number(row.electricity_demand_mw)} MW · ${number(row.water_consumption_litres, 0)} L sample demand</small></td><td><select data-priority="${index}"><option>standard</option><option>medium</option><option>high</option><option>critical</option></select></td><td><input aria-label="${escapeHtml(row.city_zone)} critical electricity requirement" data-critical-electricity="${index}" type="number" min="0" step="any" value="0"></td><td><input aria-label="${escapeHtml(row.city_zone)} critical water requirement" data-critical-water="${index}" type="number" min="0" step="any" value="0"></td></tr>`).join('');
  document.getElementById('alloc-emergency-zone').innerHTML = latest.map((row, index) => `<option value="${index}">${escapeHtml(row.city_zone)}</option>`).join('');
}

function allocationPayload() {
  const required = ['alloc-electricity-cap', 'alloc-water-cap'];
  for (const id of required) { const input = document.getElementById(id); if (input.value === '' || !Number.isFinite(Number(input.value)) || Number(input.value) < 0) throw new Error('Enter finite, non-negative electricity and water capacities.'); }
  const zones = allocationLatest.map((row, index) => ({ zone: row.city_zone, priority: document.querySelector(`[data-priority="${index}"]`).value,
    electricity_demand: Number(row.electricity_demand_mw), electricity_critical_demand: Number(document.querySelector(`[data-critical-electricity="${index}"]`).value),
    water_demand: Number(row.water_consumption_litres), water_critical_demand: Number(document.querySelector(`[data-critical-water="${index}"]`).value) }));
  const solar = document.getElementById('alloc-use-solar').checked ? allocationLatest.reduce((total, row) => total + Number(row.solar_generation_mw), 0) : 0;
  return { zones, availability: { electricity_mw: Number(document.getElementById('alloc-electricity-cap').value), water_litres: Number(document.getElementById('alloc-water-cap').value) }, solar_generation_mw: solar,
    assumptions: ['Demand is the latest simulated sample reading per zone.', 'Capacities are user-supplied and apply for one sample interval.', 'Priority and critical-service requirements are user-selected scenario assumptions.'] };
}

function allocationSummary(result) {
  const critical = value => value === null ? 'N/A (none declared)' : `${number(value)}%`;
  return `<div class="energy-metrics allocation-metrics">${['electricity','water'].map(resource => { const item=result.resources[resource]; return `<div class="energy-stat"><small>${resource.toUpperCase()} ALLOCATION</small><strong>${number(item.allocated, 2)} / ${number(item.capacity, 2)}</strong><span>${resource==='electricity'?'MW':'L'} supplied · ${number(item.utilisation_percent)}% utilisation · ${number(item.unmet_demand,2)} unmet</span></div>`; }).join('')}<div class="energy-stat"><small>CRITICAL COVERAGE</small><strong>Electricity ${critical(result.critical_service_coverage_percent.electricity)}</strong><span>Water ${critical(result.critical_service_coverage_percent.water)} of declared critical requirements</span></div></div>`;
}

async function runAllocation() {
  const error = document.getElementById('allocation-error'), button = document.getElementById('allocation-run'); error.hidden = true; button.disabled = true;
  try {
    const baseline = allocationPayload(), type = document.getElementById('alloc-scenario').value, severity = Number(document.getElementById('alloc-severity').value);
    if (!Number.isFinite(severity) || severity < 0 || severity > 100) throw new Error('Scenario severity must be between 0 and 100 percent.');
    const changes = {}, name = document.querySelector('#alloc-scenario option:checked').textContent;
    if (type === 'electricity_shortage') changes.electricity_availability_multiplier = 1-severity/100;
    if (type === 'water_shortage') changes.water_availability_multiplier = 1-severity/100;
    if (type === 'solar_reduction') changes.solar_reduction_fraction = severity/100;
    if (type === 'increased_demand') changes.demand_multiplier = 1+severity/100;
    if (type === 'emergency') { const zone = allocationLatest[Number(document.getElementById('alloc-emergency-zone').value)]; if (!zone) throw new Error('Choose a zone for the emergency priority change.'); changes.priority_overrides = { [zone.city_zone]: document.getElementById('alloc-emergency-priority').value }; }
    const response = await fetch('/api/allocation/simulate', {method:'POST', headers:{'Content-Type':'application/json',Accept:'application/json'}, body:JSON.stringify({baseline, scenario:{name,changes}})});
    const data = await response.json(); if (!response.ok) throw new Error(data.error || `Allocation API returned ${response.status}`);
    const zoneRows = data.scenario.zones.map(zone => `<tr><td>${escapeHtml(zone.zone)} · ${zone.priority}</td><td>${number(zone.electricity.demand,2)} MW</td><td>${number(zone.electricity.allocation,2)} MW</td><td>${number(zone.electricity.unmet_demand,2)} MW</td><td>${number(zone.water.allocation,0)} L</td><td>${number(zone.water.unmet_demand,0)} L</td><td>${escapeHtml(zone.electricity.explanation)} ${escapeHtml(zone.water.explanation)}</td></tr>`).join('');
    const changesRows = data.scenario.zones.map(zone => { const base=data.baseline.zones.find(item=>item.zone===zone.zone); return `<tr><td>${escapeHtml(zone.zone)}</td><td>${number(base.electricity.allocation,2)} → ${number(zone.electricity.allocation,2)} MW</td><td>${number(base.electricity.unmet_demand,2)} → ${number(zone.electricity.unmet_demand,2)} MW</td><td>${number(base.water.allocation,0)} → ${number(zone.water.allocation,0)} L</td><td>${number(base.water.unmet_demand,0)} → ${number(zone.water.unmet_demand,0)} L</td><td>${escapeHtml(zone.electricity.change_explanation)} ${escapeHtml(zone.water.change_explanation)}</td></tr>`; }).join('');
    document.getElementById('allocation-results').innerHTML = `<div class="allocation-result-columns"><article class="panel"><h3>Scenario summary · ${escapeHtml(data.scenario_name)}</h3>${allocationSummary(data.scenario)}</article><article class="panel"><h3>Baseline summary</h3>${allocationSummary(data.baseline)}</article></div><article class="panel"><h3>Zone allocations · simulated scenario</h3><div class="table-wrap"><table><thead><tr><th>ZONE / PRIORITY</th><th>POWER DEMAND</th><th>POWER ALLOCATED</th><th>POWER UNMET</th><th>WATER ALLOCATED</th><th>WATER UNMET</th><th>DECISION EXPLANATION</th></tr></thead><tbody>${zoneRows}</tbody></table></div></article><article class="panel"><h3>Before and after · zone changes</h3><div class="table-wrap"><table><thead><tr><th>ZONE</th><th>POWER ALLOCATED</th><th>POWER UNMET</th><th>WATER ALLOCATED</th><th>WATER UNMET</th><th>CHANGE EXPLANATION</th></tr></thead><tbody>${changesRows}</tbody></table></div><p class="panel-note">Scenario adjustments: ${escapeHtml(JSON.stringify(data.changes))}. ${(data.scenario.assumptions||[]).map(escapeHtml).join(' ')}</p></article>`;
  } catch (failure) { error.textContent = failure.message; error.hidden = false; }
  finally { button.disabled = false; }
}

async function loadWaterIntelligence() {
  const error = document.getElementById('water-error');
  error.hidden = true;
  try {
    const [analyticsResponse, forecastResponse, alertsResponse] = await Promise.all([
      fetch('/api/analytics/water', { headers: { Accept: 'application/json' } }),
      fetch('/api/predictions/water', { headers: { Accept: 'application/json' } }),
      fetch('/api/alerts/water', { headers: { Accept: 'application/json' } })
    ]);
    const [analytics, forecast, alerts] = await Promise.all([analyticsResponse.json(), forecastResponse.json(), alertsResponse.json()]);
    for (const response of [analyticsResponse, forecastResponse, alertsResponse]) {
      if (!response.ok) throw new Error(`Water API returned ${response.status}`);
    }
    renderWaterIntelligence(analytics, forecast, alerts);
  } catch (failure) {
    error.textContent = `Water intelligence unavailable: ${failure.message}`;
    error.hidden = false;
    document.getElementById('water-zone-rows').innerHTML = '<tr><td colspan="7" class="table-message">Water analysis could not be loaded.</td></tr>';
    document.getElementById('water-alert-list').innerHTML = '<div class="table-message">Anomaly analysis unavailable.</div>';
  }
}

async function loadEnergyAnalysis() {
  const error = document.getElementById('energy-error');
  error.hidden = true;
  try {
    const response = await fetch('/api/predictions/energy', { headers: { Accept: 'application/json' } });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `Forecast API returned ${response.status}`);
    renderEnergyAnalysis(payload);
  } catch (failure) {
    error.textContent = `Electricity analysis unavailable: ${failure.message}`;
    error.hidden = false;
    document.getElementById('energy-zone-rows').innerHTML = '<tr><td colspan="6" class="table-message">Electricity analysis could not be loaded.</td></tr>';
    setText('forecast-method', 'Forecast methodology is unavailable until sample data loads.');
  }
}

let emergencyScenarios = [];
function renderEmergency(result, comparison) {
  const severity = escapeHtml(result.overall_severity.toUpperCase());
  const zones = result.zones.map(z => `<tr><td>${escapeHtml(z.zone)}</td><td>${escapeHtml(z.severity.toUpperCase())} · ${number(z.risk_score)}%</td><td>${number(z.resource_shortfalls.electricity,2)} MW</td><td>${number(z.resource_shortfalls.water,0)} L</td><td>${z.critical_service_coverage_percent.electricity == null ? '—' : number(z.critical_service_coverage_percent.electricity)+'%'} / ${z.critical_service_coverage_percent.water == null ? '—' : number(z.critical_service_coverage_percent.water)+'%'}</td></tr>`).join('');
  const alerts = result.alerts.length ? result.alerts.map(a => `<div class="alert-item"><strong>${escapeHtml(a.zone)} · ${escapeHtml(a.resource)} · ${escapeHtml(a.severity)}</strong><p>${escapeHtml(a.explanation)} <small>${escapeHtml(a.evidence_quality)}</small></p></div>`).join('') : '<p>No resource shortfall or critical-service alert under these scenario inputs.</p>';
  const cascades = result.cascading_risks.length ? result.cascading_risks.map(c => `<li>${escapeHtml(c.explanation)} Risk contribution ${number(c.risk_contribution)} points. <small>${escapeHtml(c.evidence_quality)}</small></li>`).join('') : '<li>No configured dependency was activated.</li>';
  const actions = result.interventions.length ? result.interventions.map(a => `<article class="panel"><h3>#${a.rank} ${escapeHtml(a.proposed_action)}</h3><p><b>Trigger:</b> ${escapeHtml(a.triggering_condition)}</p><p><b>Expected benefit:</b> ${escapeHtml(a.expected_benefit)} <b>Trade-off:</b> ${escapeHtml(a.trade_off)}</p><p><b>Affected:</b> ${a.affected_zones.map(escapeHtml).join(', ')} · <b>Assumptions:</b> ${a.assumptions.map(escapeHtml).join('; ')}</p></article>`).join('') : '<article class="panel">No intervention is indicated by the selected simulated inputs.</article>';
  const compare = comparison ? `<article class="panel"><h3>Before and after · normal operations baseline</h3><p>Severity: ${escapeHtml(comparison.severity_before)} → ${escapeHtml(comparison.severity_after)} · risk score change ${number(comparison.risk_score_change)} points</p><p>Electricity shortfall: ${number(comparison.electricity_before,2)} → ${number(comparison.electricity_after,2)} MW · water shortfall: ${number(comparison.water_before,0)} → ${number(comparison.water_after,0)} L</p><p>Critical-service coverage (electricity): ${comparison.critical_before.electricity == null?'—':number(comparison.critical_before.electricity)+'%'} → ${comparison.critical_after.electricity == null?'—':number(comparison.critical_after.electricity)+'%'}</p></article>` : '';
  document.getElementById('emergency-results').innerHTML = `<div class="energy-metrics allocation-metrics"><div class="energy-stat"><small>OVERALL CITY STATUS</small><strong>${severity}</strong><span>${escapeHtml(result.data_label)}</span></div><div class="energy-stat"><small>CASCADING RISK</small><strong>${number(result.cascading_risk_score)}</strong><span>assumption-based points</span></div><div class="energy-stat"><small>AFFECTED ZONES</small><strong>${result.affected_zones.length}</strong><span>${result.affected_zones.map(escapeHtml).join(', ') || 'None'}</span></div></div>${compare}<article class="panel"><h3>Zone emergency risk · simulated</h3><div class="table-wrap"><table><thead><tr><th>ZONE</th><th>RISK</th><th>ELECTRICITY GAP</th><th>WATER GAP</th><th>CRITICAL COVERAGE · E/W</th></tr></thead><tbody>${zones}</tbody></table></div></article><div class="allocation-result-columns"><article class="panel"><h3>Stress indicators</h3>${alerts}</article><article class="panel"><h3>Cascading-risk explanations</h3><ul>${cascades}</ul><p class="panel-note">${escapeHtml(result.risk_formula)}</p></article></div><h3>Ranked interventions · recommendations only</h3>${actions}<article class="panel"><h3>Evidence and assumptions</h3><p>${result.assumptions.map(escapeHtml).join('<br>')}</p><p>Solar generation is treated only as the explicitly supplied scenario contribution. Nothing here indicates an intervention was executed.</p></article>`;
}
async function loadEmergencyScenarios() {
  const error = document.getElementById('emergency-error');
  try {
    const response = await fetch('/api/emergency/scenarios', {headers:{Accept:'application/json'}}); const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Emergency API returned ${response.status}`);
    emergencyScenarios = data.scenarios; const select = document.getElementById('emergency-scenario');
    select.innerHTML = emergencyScenarios.map((s,i)=>`<option value="${i}">${escapeHtml(s.name)}</option>`).join('');
    select.addEventListener('change', () => { const s=emergencyScenarios[Number(select.value)]; document.getElementById('emergency-description').textContent=s.description+' Fictional scenario; not a live event.'; renderEmergency(s.analysis); });
    document.getElementById('emergency-description').textContent=emergencyScenarios[0].description+' Fictional scenario; not a live event.';
    renderEmergency(emergencyScenarios[0].analysis);
  } catch (failure) { error.textContent=`Emergency scenarios unavailable: ${failure.message}`; error.hidden=false; }
}
async function compareEmergencyScenario() {
  const error=document.getElementById('emergency-error'), button=document.getElementById('emergency-run'); error.hidden=true; button.disabled=true;
  try {
    const selected=emergencyScenarios[Number(document.getElementById('emergency-scenario').value)], baseline=emergencyScenarios[0].scenario;
    const response=await fetch('/api/emergency/simulate',{method:'POST',headers:{'Content-Type':'application/json',Accept:'application/json'},body:JSON.stringify({baseline,scenario:{name:selected.name,changes:selected.scenario}})});
    const data=await response.json(); if(!response.ok) throw new Error(data.error||`Emergency API returned ${response.status}`);
    const before=data.baseline, after=data.scenario;
    renderEmergency(after,{severity_before:before.overall_severity,severity_after:after.overall_severity,risk_score_change:data.comparison.risk_score_change,
      electricity_before:before.resource_shortfalls.electricity.amount,electricity_after:after.resource_shortfalls.electricity.amount,
      water_before:before.resource_shortfalls.water.amount,water_after:after.resource_shortfalls.water.amount,
      critical_before:before.critical_service_coverage_percent,critical_after:after.critical_service_coverage_percent});
  } catch (failure) { error.textContent=failure.message; error.hidden=false; } finally {button.disabled=false;}
}

async function loadDashboard() {
  const button = document.getElementById('refresh-button');
  button.disabled = true;
  setText('updated-at', 'Loading sample data…');
  document.getElementById('zone-rows').innerHTML = '<tr><td colspan="6" class="table-message">Loading zone readings…</td></tr>';
  try {
    console.log('[Dashboard] Starting data load from /api/resources');
    const response = await fetch('/api/resources', { headers: { Accept: 'application/json' } });
    console.log('[Dashboard] API response status:', response.status);
    
    if (!response.ok) {
      throw new Error(`Resource API returned HTTP ${response.status}`);
    }
    
    const payload = await response.json();
    console.log('[Dashboard] Payload received, records:', payload.records ? payload.records.length : 'missing');
    
    if (!Array.isArray(payload.records) || payload.records.length === 0) {
      throw new Error('No sample records are available from API.');
    }
    
    console.log('[Dashboard] Rendering zones from', payload.records.length, 'records');
    const latest = renderZones(payload.records);
    console.log('[Dashboard] Latest timestamp has', latest.length, 'zones');
    
    if (!latest || latest.length === 0) {
      throw new Error('Could not find latest readings in data.');
    }
    
    renderAllocationInputs(latest);
    const sum = key => latest.reduce((total, row) => total + Number(row[key]), 0);
    
    const elecVal = sum('electricity_demand_mw');
    const waterVal = sum('water_consumption_litres') / 1000000;
    const solarVal = sum('solar_generation_mw');
    const tempVal = sum('temperature_c') / latest.length;
    
    console.log('[Dashboard] Calculated metrics:', { elecVal, waterVal, solarVal, tempVal });
    
    setText('electricity-value', number(elecVal));
    setText('water-value', number(waterVal, 2) + 'M');
    setText('solar-value', number(solarVal));
    setText('temperature-value', number(tempVal));
    
    const availability = Math.round(sum('resource_availability') / latest.length);
    setText('availability-value', `${availability}%`);
    setText('availability-caption', availability < 70 ? 'Sample availability needs review' : 'Sample resources within range');
    document.querySelector('.availability-ring').style.setProperty('--availability', `${availability}%`);
    
    renderAlerts(latest);
    renderChart(payload.records);
    setText('updated-at', `Sample snapshot · ${new Date(latest[0].timestamp).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' })} UTC`);
    console.log('[Dashboard] Data load complete');
  } catch (error) {
    console.error('[Dashboard] Error loading data:', error.message, error.stack);
    const errorMsg = `Could not load dashboard: ${error.message}. Check browser console for details.`;
    document.getElementById('zone-rows').innerHTML = `<tr><td colspan="6" class="table-message">${escapeHtml(errorMsg)}</td></tr>`;
    document.getElementById('alert-list').innerHTML = `<div class="table-message">${escapeHtml(errorMsg)}</div>`;
    setText('electricity-value', 'ERROR');
    setText('water-value', 'ERROR');
    setText('solar-value', 'ERROR');
    setText('temperature-value', 'ERROR');
    setText('availability-value', '0%');
    setText('updated-at', 'Failed to load - see error above');
  } finally { 
    button.disabled = false; 
  }
  
  // Load complementary analyses
  loadEnergyAnalysis();
  loadWaterIntelligence();
  loadSolarIntelligence();
}

/* DIGITAL TWIN SIMULATION */
let dtSeverityChart, dtRiskChart, currentSimulationResult = null, currentStepIndex = 0;

async function loadDigitalTwinScenarios() {
  try {
    const response = await fetch('/api/digital-twin/simulations');
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    const data = await response.json();
    const scenarios = data.simulations || [];
    const select = document.getElementById('dt-scenario');
    select.innerHTML = scenarios.map(sim => `<option value="${sim.id}" data-config="${btoa(JSON.stringify(sim.config))}">${escapeHtml(sim.name)}</option>`).join('');
    if (scenarios.length > 0) {
      select.addEventListener('change', onDigitalTwinScenarioChange);
      onDigitalTwinScenarioChange();
    }
  } catch (error) {
    console.error('Failed to load digital twin scenarios:', error);
    document.getElementById('dt-scenario').innerHTML = '<option>Error loading scenarios</option>';
  }
}

function onDigitalTwinScenarioChange() {
  const select = document.getElementById('dt-scenario');
  const option = select.options[select.selectedIndex];
  const configStr = option.getAttribute('data-config');
  if (!configStr) return;
  
  try {
    const config = JSON.parse(atob(configStr));
    document.getElementById('dt-description').textContent = `Scenario: ${escapeHtml(option.text)}. This is a fictional demonstration scenario.`;
  } catch (error) {
    console.error('Failed to parse scenario config:', error);
  }
}

async function runDigitalTwinSimulation() {
  const select = document.getElementById('dt-scenario');
  const option = select.options[select.selectedIndex];
  const configStr = option.getAttribute('data-config');
  if (!configStr) {
    showDtError('No scenario selected.');
    return;
  }

  try {
    const baseConfig = JSON.parse(atob(configStr));
    const duration = parseFloat(document.getElementById('dt-duration').value);
    const stepSize = parseFloat(document.getElementById('dt-step-size').value);
    const startTime = document.getElementById('dt-start-time').value;

    if (!duration || duration <= 0 || !stepSize || stepSize <= 0) {
      showDtError('Duration and step size must be positive numbers.');
      return;
    }

    const config = {
      ...baseConfig,
      duration_hours: duration,
      step_size_hours: stepSize,
      start_time: startTime ? new Date(startTime).toISOString() : undefined
    };

    document.getElementById('dt-run').disabled = true;
    clearDtError();
    document.getElementById('dt-results-container').hidden = true;

    const response = await fetch('/api/digital-twin/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || `HTTP ${response.status}`);
    }

    const result = await response.json();
    currentSimulationResult = result;
    currentStepIndex = 0;
    displayDigitalTwinResults(result);
    document.getElementById('dt-results-container').hidden = false;
    document.getElementById('dt-reset').hidden = false;
  } catch (error) {
    showDtError(`Simulation failed: ${error.message}`);
    console.error('Digital Twin simulation error:', error);
  } finally {
    document.getElementById('dt-run').disabled = false;
  }
}

function displayDigitalTwinResults(result) {
  const timeline = result.timeline || [];
  if (!timeline.length) {
    showDtError('Simulation produced no timeline data.');
    return;
  }

  document.getElementById('dt-info-duration').textContent = `${result.duration_hours} hours`;
  document.getElementById('dt-info-steps').textContent = `${result.num_steps} steps`;
  document.getElementById('dt-info-events').textContent = `${result.events_applied}`;
  document.getElementById('dt-info-interventions').textContent = `${result.interventions_applied}`;

  renderDtTimelines(timeline);
  renderDtZonesSummary(timeline);
  updateDtStepDisplay();
  renderDtAssumptions(result);
}

function renderDtTimelines(timeline) {
  const labels = timeline.map((step, i) => {
    const ts = new Date(step.timestamp);
    return ts.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' });
  });

  const severityMap = { normal: 0, warning: 1, high: 2, critical: 3 };
  const severityData = timeline.map(step => severityMap[step.severity] || 0);
  const riskData = timeline.map(step => step.risk_score || 0);

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: { mode: 'index', intersect: false }
    },
    scales: {
      x: { grid: { color: '#22303e' }, ticks: { color: '#8492a2', font: { size: 9 } }, border: { display: false } },
      y: { grid: { color: '#22303e' }, ticks: { color: '#8492a2', font: { size: 9 } }, border: { display: false } }
    }
  };

  if (typeof Chart !== 'undefined') {
    if (dtSeverityChart) dtSeverityChart.destroy();
    dtSeverityChart = new Chart(document.getElementById('dt-severity-chart'), {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Emergency Severity',
          data: severityData,
          borderColor: '#ff5566',
          backgroundColor: '#ff556622',
          fill: true,
          tension: 0.3,
          pointRadius: 4,
          pointBackgroundColor: '#ff5566',
          pointBorderColor: '#fff'
        }]
      },
      options: {
        ...chartOptions,
        scales: {
          ...chartOptions.scales,
          y: {
            ...chartOptions.scales.y,
            min: 0,
            max: 3,
            ticks: { callback: v => ['Normal', 'Warning', 'High', 'Critical'][v] || v, ...chartOptions.scales.y.ticks }
          }
        }
      }
    });

    if (dtRiskChart) dtRiskChart.destroy();
    dtRiskChart = new Chart(document.getElementById('dt-risk-chart'), {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Cascading Risk Score',
          data: riskData,
          borderColor: '#f0b85d',
          backgroundColor: '#f0b85d22',
          fill: true,
          tension: 0.3,
          pointRadius: 4,
          pointBackgroundColor: '#f0b85d',
          pointBorderColor: '#fff'
        }]
      },
      options: {
        ...chartOptions,
        scales: {
          ...chartOptions.scales,
          y: { ...chartOptions.scales.y, min: 0, max: 100 }
        }
      }
    });
  }
}

function renderDtZonesSummary(timeline) {
  const zoneStats = new Map();
  
  timeline.forEach(step => {
    (step.affected_zones || []).forEach(zone => {
      if (!zoneStats.has(zone)) {
        zoneStats.set(zone, { peakSeverity: 'normal', peakRisk: 0, alertCount: 0 });
      }
      const stats = zoneStats.get(zone);
      const severityOrder = { normal: 0, warning: 1, high: 2, critical: 3 };
      if ((severityOrder[step.severity] || 0) > (severityOrder[stats.peakSeverity] || 0)) {
        stats.peakSeverity = step.severity;
      }
      stats.peakRisk = Math.max(stats.peakRisk, step.risk_score || 0);
      stats.alertCount = Math.max(stats.alertCount, step.alerts_count || 0);
    });
  });

  const tbody = document.getElementById('dt-zone-rows');
  if (zoneStats.size === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="table-message">No affected zones in this simulation.</td></tr>';
    return;
  }

  const rows = [...zoneStats.entries()].map(([zone, stats]) => {
    const severityClass = `severity-${stats.peakSeverity}`;
    const severityLabel = stats.peakSeverity.charAt(0).toUpperCase() + stats.peakSeverity.slice(1);
    return `<tr><td>${escapeHtml(zone)}</td><td><span class="status-pill ${stats.peakSeverity === 'critical' ? 'watch' : ''}">${severityLabel}</span></td><td>${number(stats.peakRisk, 1)}</td><td>${stats.alertCount}</td><td><span class="status-pill ${stats.peakSeverity === 'critical' ? 'watch' : ''}">${stats.peakRisk > 50 ? 'High Risk' : 'Monitored'}</span></td></tr>`;
  }).join('');
  tbody.innerHTML = rows;
}

function updateDtStepDisplay() {
  if (!currentSimulationResult || !currentSimulationResult.timeline) return;
  
  const timeline = currentSimulationResult.timeline;
  const step = timeline[currentStepIndex];
  if (!step) return;

  document.getElementById('dt-step-label').textContent = `Step ${currentStepIndex + 1} of ${timeline.length}`;
  document.getElementById('dt-prev-step').disabled = currentStepIndex === 0;
  document.getElementById('dt-next-step').disabled = currentStepIndex === timeline.length - 1;

  document.getElementById('dt-detail-timestamp').textContent = new Date(step.timestamp).toLocaleString([], { dateStyle: 'short', timeStyle: 'short', timeZone: 'UTC' });
  document.getElementById('dt-detail-severity').textContent = step.severity.toUpperCase();
  document.getElementById('dt-detail-severity').className = `severity-${step.severity}`;
  document.getElementById('dt-detail-risk').textContent = `${number(step.risk_score, 1)} / 100`;
  document.getElementById('dt-detail-zones').textContent = step.affected_zones && step.affected_zones.length > 0 ? step.affected_zones.join(', ') : 'None';

  const alertsHtml = step.alerts_count > 0 ? `<div class="dt-alert-box"><p><strong>Alerts: ${step.alerts_count}</strong> condition(s) detected at this step.</p></div>` : '<p class="table-message">No emergency alerts for this step.</p>';
  document.getElementById('dt-detail-alerts').innerHTML = alertsHtml;
}

function renderDtAssumptions(result) {
  const assumptions = [];
  const scenario = result.base_scenario_name || 'Unknown scenario';
  assumptions.push(`<strong>Scenario:</strong> ${escapeHtml(scenario)}`);
  
  if (result.events_applied > 0) {
    assumptions.push(`<strong>Events:</strong> ${result.events_applied} event(s) configured and applied during simulation.`);
  }
  if (result.interventions_applied > 0) {
    assumptions.push(`<strong>Interventions:</strong> ${result.interventions_applied} intervention(s) configured and applied during simulation.`);
  }

  assumptions.push(`<strong>Simulation type:</strong> Deterministic multi-step simulation with explicit inputs. No supply capacity is inferred from historical data.`);
  assumptions.push(`<strong>Time-stepping:</strong> Discrete hourly intervals; each step calculates resource demand, allocation, severity, and risk independently.`);
  assumptions.push(`<strong>Critical services:</strong> Zone-specified critical electricity and water requirements are protected where possible.`);
  assumptions.push(`<strong>Cascading risks:</strong> Electricity shortage can affect water pumping. Water shortage can affect emergency services. Solar reduction increases electricity demand pressure.`);

  document.getElementById('dt-assumptions-list').innerHTML = assumptions.map(a => `<p>${a}</p>`).join('');
}

function showDtError(message) {
  const errorEl = document.getElementById('dt-error');
  errorEl.textContent = message;
  errorEl.hidden = false;
}

function clearDtError() {
  const errorEl = document.getElementById('dt-error');
  errorEl.textContent = '';
  errorEl.hidden = true;
}

function resetDigitalTwinUI() {
  currentSimulationResult = null;
  currentStepIndex = 0;
  document.getElementById('dt-results-container').hidden = true;
  document.getElementById('dt-reset').hidden = true;
  if (dtSeverityChart) { dtSeverityChart.destroy(); dtSeverityChart = null; }
  if (dtRiskChart) { dtRiskChart.destroy(); dtRiskChart = null; }
  clearDtError();
}

document.addEventListener('DOMContentLoaded', () => {
  console.log('[App] DOM loaded, initializing dashboard');
  
  try {
    document.getElementById('refresh-button').addEventListener('click', loadDashboard);
    document.getElementById('allocation-run').addEventListener('click', runAllocation);
    document.getElementById('emergency-run').addEventListener('click', compareEmergencyScenario);
    
    /* Digital Twin controls */
    document.getElementById('dt-run').addEventListener('click', runDigitalTwinSimulation);
    document.getElementById('dt-reset').addEventListener('click', resetDigitalTwinUI);
    document.getElementById('dt-prev-step').addEventListener('click', () => {
      if (currentStepIndex > 0) {
        currentStepIndex--;
        updateDtStepDisplay();
      }
    });
    document.getElementById('dt-next-step').addEventListener('click', () => {
      if (currentSimulationResult && currentStepIndex < currentSimulationResult.timeline.length - 1) {
        currentStepIndex++;
        updateDtStepDisplay();
      }
    });

    console.log('[App] Event listeners attached');
    
    loadEmergencyScenarios();
    console.log('[App] Loading emergency scenarios...');
    
    loadDigitalTwinScenarios();
    console.log('[App] Loading digital twin scenarios...');
    
    loadDashboard();
    console.log('[App] Loading main dashboard...');
  } catch (error) {
    console.error('[App] Error during initialization:', error.message, error.stack);
    alert('Dashboard initialization error. Check browser console for details.');
  }
});

// Global error handler for unhandled rejections
window.addEventListener('unhandledrejection', event => {
  console.error('[App] Unhandled promise rejection:', event.reason);
});

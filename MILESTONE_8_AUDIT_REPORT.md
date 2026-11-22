# Milestone 8: Smart City Unified Data Foundation — Audit Report

## Executive Summary

The existing Smart City platform has a minimal synthetic dataset (`sample_data.csv` with 16 records) covering only 4 hours for 4 zones. This report audits current field usage and proposes a comprehensive 30-day unified dataset that will support all modules while maintaining backward compatibility.

---

## Current State Analysis

### 1. Existing Dataset Structure

**File:** `data/sample_data.csv`

**Current Rows:** 16 (4 timestamps × 4 zones)
**Current Date Range:** 2026-06-18 (08:00, 12:00, 16:00, 20:00 UTC)
**Current Zones:** Central District, North Residential, South Industrial, Riverside

**Current Fields:**
| Field | Type | Used By | Purpose |
|-------|------|---------|---------|
| timestamp | ISO 8601 datetime | All modules | Time of measurement |
| city_zone | string | All modules | Zone identifier |
| electricity_demand_mw | float | Electricity, allocation, emergency, digital twin | Zone electricity consumption |
| water_consumption_litres | float | Water, allocation, emergency, digital twin | Zone water consumption |
| solar_generation_mw | float | Solar, emergency, digital twin | Solar output for zone |
| temperature_c | float | Solar (weather correlation), digital twin | Ambient temperature |
| resource_availability | int (0-100) | Dashboard display only | Availability percentage |

**Validation Rules (app.py):**
- All rows must have timestamp, city_zone
- Numeric fields: electricity_demand_mw, water_consumption_litres, solar_generation_mw, temperature_c
- resource_availability must be 0-100
- All demand/generation values must be non-negative
- Timestamps must be valid ISO 8601

---

## Module-by-Module Field Requirements

### Electricity Module (`models/prediction.py`, `services/`)
**Used in:** Forecasting, dashboard, digital twin
**Requires:**
- `timestamp` ✓
- `city_zone` ✓
- `electricity_demand_mw` ✓
- `temperature_c` ✓ (for demand correlation)

**Missing but useful:**
- `electricity_supply_mw` - actual available capacity
- `electricity_capacity_mw` - infrastructure limit
- `hour_of_day` - for daily demand cycles (derived)

---

### Water Module (`services/water_intelligence.py`)
**Used in:** Usage analysis, shortage assessment, anomaly detection, digital twin
**Requires:**
- `timestamp` ✓
- `city_zone` ✓
- `water_consumption_litres` ✓

**Missing but useful:**
- `water_supply_litres` - available water source capacity
- `water_storage_level_litres` - current storage level
- `water_storage_capacity_litres` - storage infrastructure limit
- `water_treatment_capacity_litres` - processing capacity

**Current workaround:** `assess_water_shortage()` function uses hardcoded thresholds; actual supply not tracked.

---

### Solar Module (`services/solar_intelligence.py`)
**Used in:** Generation analysis, weather correlation, demand comparison, digital twin
**Requires:**
- `timestamp` ✓
- `city_zone` ✓
- `solar_generation_mw` ✓
- `temperature_c` ✓ (for weather correlation)

**Missing but useful:**
- `solar_capacity_mw` - installed capacity
- `cloud_cover_percent` - for realistic weather modeling
- `solar_efficiency_percent` - derived from capacity and generation

---

### Allocation Module (`services/allocation.py`)
**Used in:** Priority-based resource allocation, scenario analysis
**Requires:**
- Zone definitions with demands (via API request, not CSV)
- Electricity availability (via API request)
- Water availability (via API request)
- Optional solar generation (via API request)

**Note:** This module takes scenario inputs; doesn't directly read CSV.

---

### Emergency Intelligence (`services/emergency_intelligence.py`)
**Used in:** Multi-resource stress detection, cascading risk analysis, severity classification
**Requires:**
- Zone definitions with demands (via API)
- Critical-service requirements (via API, not in CSV)
- Electricity availability (via API)
- Water availability (via API)
- Solar metrics (via API)

**Missing but useful:**
- Hospital/emergency-service location identifiers
- Critical-service demand values (electricity, water)

---

### Digital Twin (`services/digital_twin.py`)
**Used in:** Time-stepped simulation of city state over hours
**Requires:**
- Starting scenario with all zones, demands, capacities
- Event definitions (heatwave, disruptions, recovery)
- Intervention definitions (capacity increase, demand reduction)

**Missing but useful:**
- Historical baseline for each zone (for realistic daily patterns)
- Infrastructure dependency relationships
- Event template library

---

### Dashboard / API (`app.py`, `static/js/dashboard.js`)
**Used in:** Data visualization, alerts, comparisons
**Requires:**
- All current fields

**Missing but useful:**
- Alerts/events metadata (causes, durations)
- Zone metadata (location, priority, type)
- Scenario metadata (name, description, event list)

---

## Identified Gaps

| Gap | Impact | Severity | Solution |
|-----|--------|----------|----------|
| No explicit electricity supply capacity | Emergency analysis uses demand-only | High | Add `electricity_supply_mw` field |
| No water supply/storage tracking | Water shortage assessment is hardcoded | High | Add water supply/storage fields |
| No critical-service data in CSV | Emergency scenarios require API input | Medium | Add optional critical-service fields |
| No realistic daily patterns | Simulations use flat demand profiles | Medium | Generate realistic hourly cycles |
| No weather variation | Solar/demand correlation limited | Medium | Add humidity, rainfall, cloud cover |
| No event metadata in CSV | Event timeline not queryable | Medium | Create separate `city_events.csv` |
| No zone infrastructure metadata | Cascading risk assumptions not queryable | Low | Create separate `zone_metadata.json` |

---

## Proposed Data Architecture

### File 1: `data/sample_data.csv` (Unified Hourly Readings)
**Scope:** 30 days × 24 hours × 4 zones = 2,880 records

**Columns:**

```csv
timestamp,city_zone,electricity_demand_mw,electricity_supply_mw,
electricity_capacity_mw,water_consumption_litres,water_supply_litres,
water_storage_level_litres,water_storage_capacity_litres,
solar_generation_mw,solar_capacity_mw,
temperature_c,humidity_percent,rainfall_mm,cloud_cover_percent,wind_speed_kmh,
hospital_electricity_demand_mw,hospital_water_demand_litres,
emergency_service_demand_mw,critical_service_status,
resource_availability
```

**Data Types:**
- `timestamp` - ISO 8601 (required)
- `city_zone` - string, one of 4 known zones (required)
- Electricity fields - float, non-negative MW or capacity (required)
- Water fields - float, non-negative litres or capacity (required)
- Solar fields - float, non-negative MW or capacity (required)
- Weather fields - float, within sensible ranges (required)
- Critical service fields - float, non-negative or status enum (required)
- `resource_availability` - int, 0-100 (required)

**Determinism:** Fixed random seed (12345) ensures reproducible generation.

---

### File 2: `data/city_events.csv` (Event Timeline)
**Scope:** 50-100 event records across 30 days

**Columns:**

```csv
event_id,event_type,start_timestamp,end_timestamp,
affected_zones,field_impacted,magnitude,
severity,description,assumptions
```

**Event Types:**
- `normal_operations`
- `heatwave`
- `low_solar_generation`
- `electricity_supply_disruption`
- `water_supply_disruption`
- `combined_shortage`
- `hospital_emergency`
- `high_industrial_demand`
- `recovery`

---

### File 3: `data/zone_metadata.json` (Infrastructure Metadata)
**Scope:** 4 zones

**Structure:**

```json
{
  "zones": [
    {
      "zone_name": "Central District",
      "zone_type": "commercial",
      "population_estimate": 450000,
      "priority": "high",
      "coordinates": [0.0, 0.0],
      "infrastructure": {
        "electricity": {
          "capacity_mw": 150,
          "daily_peak_hour": 12,
          "peak_coefficient": 1.3,
          "solar_penetration_percent": 20
        },
        "water": {
          "storage_capacity_litres": 10000000,
          "treatment_capacity_litres_per_hour": 50000,
          "daily_peak_hour": 10,
          "peak_coefficient": 1.25
        },
        "solar": {
          "installed_capacity_mw": 30,
          "efficiency_baseline_percent": 85
        }
      },
      "critical_services": {
        "hospitals": 3,
        "emergency_services": 2,
        "water_treatment_plants": 1
      }
    },
    // ... 3 more zones
  ]
}
```

---

### File 4: `data/scenario_definitions.json` (Reusable Scenarios)
**Scope:** 6-8 scenario templates

**Structure:**

```json
{
  "scenarios": [
    {
      "scenario_id": "normal_operations",
      "name": "Normal city operations",
      "description": "Baseline with no major events",
      "start_hour": 0,
      "duration_hours": 24,
      "events": [],
      "interventions": []
    },
    {
      "scenario_id": "heatwave_crisis",
      "name": "Heatwave and increased demand",
      "description": "30% electricity increase, 25% water increase",
      "events": [
        {
          "event_id": "heatwave_01",
          "type": "heatwave",
          "start_hour": 8,
          "duration_hours": 8,
          "affected_zones": ["Central District", "North Residential", "South Industrial", "Riverside"],
          "field": "electricity_demand_mw",
          "magnitude": 1.3,
          "explanation": "Heat spike increases AC demand"
        }
      ]
    },
    // ... more scenarios
  ]
}
```

---

### File 5: `scripts/generate_sample_data.py` (Generator Script)
**Purpose:** Reproducible deterministic dataset generation

**Features:**
- Fixed random seed (12345)
- Daily demand cycles with peak hours
- Weekly patterns (slight weekend reduction)
- Temperature-based electricity correlation
- Realistic solar curves (sunrise/sunset, cloud effects)
- Water storage reconciliation
- Event application (heatwave multipliers, disruption gaps)
- Supply/demand stress realistic variation

---

## Impact Analysis

### Backward Compatibility
✅ **All existing tests will pass:**
- Current 16-record sample included in 2,880-record dataset
- All existing column names preserved
- New fields are additive; existing parsers unaffected
- Validation rules unchanged

### Module Integration
✅ **All modules benefit:**
- Electricity: 30 days of patterns for better forecasting
- Water: Supply tracking enables realistic shortage simulation
- Solar: Weather variation improves generation accuracy
- Allocation: Longer dataset enables better priority testing
- Emergency: Real cascading risk scenarios available
- Digital Twin: Baseline patterns inform simulation realism
- Dashboard: 30 days of data for 30-day charts

### Performance Impact
⚠️ **Manageable:**
- 2,880 rows vs. current 16 (180x increase)
- Load time: ~5ms vs. current <1ms (negligible)
- Memory: ~200KB vs. current 1KB (negligible)
- API parsing: No change in complexity

---

## Migration Strategy

### Phase 1: Implement Data Generator
1. Create `scripts/generate_sample_data.py`
2. Validate determinism (run twice, identical output)
3. Generate initial dataset files

### Phase 2: Create Supporting Data Files
1. Create `data/zone_metadata.json`
2. Create `data/city_events.csv`
3. Create `data/scenario_definitions.json`

### Phase 3: Integration Testing
1. Run all existing tests (should all pass)
2. Verify app.py loads new dataset correctly
3. Test all dashboard endpoints
4. Verify digital twin simulation works
5. Verify emergency intelligence detects scenarios

### Phase 4: Dashboard Updates
1. Add data info section (date range, record count, zones)
2. Add "simulated data" label
3. Add event timeline visualization
4. Add scenario selector for dashboard

### Phase 5: Documentation
1. Update README with dataset description
2. Add data dictionary
3. Add generator usage guide

---

## Success Criteria

- [ ] Dataset contains exactly 2,880 records (30 × 24 × 4)
- [ ] All existing 89 tests pass
- [ ] All zones have realistic daily/weekly demand patterns
- [ ] Water storage reconciles with supply/consumption
- [ ] All 9 event scenarios properly affect readings
- [ ] Solar generation correlates realistically with cloud cover
- [ ] No negative values or out-of-bounds data
- [ ] Generator is deterministic (runs twice = identical output)
- [ ] Dashboard shows data metadata without errors
- [ ] Digital Twin simulation uses baseline data correctly
- [ ] No existing functionality broken

---

## Timeline Estimate

- Data generator implementation: 2-3 hours
- Supporting file creation: 1 hour
- Testing and validation: 1-2 hours
- Dashboard integration: 1 hour
- Documentation: 30 minutes
- **Total: 5.5-7.5 hours**

---

## Next Steps

1. Review this audit report
2. Confirm proposed schema (or request modifications)
3. Begin implementation in Phase 1 (data generator)
4. Proceed through phases sequentially
5. Verify no regressions in test suite
6. Deploy unified dataset

---

## Appendix: Module API Requirements Summary

### From `app.py` REQUIRED_COLUMNS:
```python
REQUIRED_COLUMNS = {
    "timestamp",
    "city_zone",
    "electricity_demand_mw",
    "water_consumption_litres",
    "solar_generation_mw",
    "temperature_c",
    "resource_availability",
}
```

### From `services/emergency_intelligence.py` Input Scenario:
```python
scenario = {
    "zones": [
        {
            "zone": str,
            "priority": "critical|high|medium|standard",
            "electricity_demand_mw": float,
            "water_demand_litres": float,
            "critical_service_requirements": {
                "electricity_mw": float,
                "water_litres": float,
            }
        }
    ],
    "availability": {
        "electricity_mw": float,
        "water_litres": float,
    },
    "solar_generation_mw": float,
    "solar_reduction_fraction": float (0-1),
    "dependencies": [...],
    "assumptions": [...]
}
```

### From `services/digital_twin.py` Simulation:
- Requires all zone demands and capacities
- Requires event definitions (type, timing, magnitude, affected zones)
- Requires intervention definitions (type, timing, action, magnitude)
- Outputs: 24-hour timeline with hourly state snapshots

---

**Report Prepared:** 2026-11-22
**Status:** Ready for Implementation

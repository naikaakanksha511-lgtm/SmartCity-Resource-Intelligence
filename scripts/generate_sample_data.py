"""Generate reproducible 30-day synthetic city dataset for Smart City platform."""

import csv
import json
import math
from datetime import datetime, timedelta
import random

SEED = 12345
OUTPUT_CSV = "data/sample_data.csv"
ZONES = ["Central District", "North Residential", "South Industrial", "Riverside"]
START_DATE = datetime(2026, 6, 18, 0, 0, 0)
DURATION_DAYS = 30

ZONE_PROFILES = {
    "Central District": {
        "type": "commercial",
        "electricity_base": 45.0,
        "water_base": 2000000,
        "solar_capacity": 30.0,
        "critical_service_electricity": 5.0,
        "critical_service_water": 200000,
    },
    "North Residential": {
        "type": "residential",
        "electricity_base": 32.0,
        "water_base": 1500000,
        "solar_capacity": 25.0,
        "critical_service_electricity": 2.0,
        "critical_service_water": 150000,
    },
    "South Industrial": {
        "type": "industrial",
        "electricity_base": 60.0,
        "water_base": 1000000,
        "solar_capacity": 35.0,
        "critical_service_electricity": 1.0,
        "critical_service_water": 50000,
    },
    "Riverside": {
        "type": "mixed",
        "electricity_base": 28.0,
        "water_base": 1300000,
        "solar_capacity": 20.0,
        "critical_service_electricity": 3.0,
        "critical_service_water": 180000,
    },
}

EVENTS_SCHEDULE = [
    {"name": "Heatwave 1", "day": 2, "duration": 8, "zones": ZONES, "effect": "heat"},
    {"name": "Cloud cover spike", "day": 5, "duration": 6, "zones": ZONES, "effect": "clouds"},
    {"name": "High industrial demand", "day": 8, "duration": 12, "zones": ["South Industrial"], "effect": "demand"},
    {"name": "Heatwave 2", "day": 12, "duration": 10, "zones": ZONES, "effect": "heat"},
    {"name": "Electricity disruption", "day": 15, "duration": 4, "zones": ["Central District"], "effect": "disruption"},
    {"name": "Recovery from disruption", "day": 15, "start_hour": 4, "duration": 4, "zones": ["Central District"], "effect": "recovery"},
    {"name": "Water supply constraint", "day": 18, "duration": 6, "zones": ["North Residential", "Central District"], "effect": "water"},
    {"name": "Hospital emergency", "day": 22, "duration": 3, "zones": ["Central District"], "effect": "critical"},
    {"name": "Combined shortage", "day": 25, "duration": 5, "zones": ZONES, "effect": "combined"},
]


def temperature_for_day_hour(day, hour):
    """Generate realistic temperature with daily cycle and gradual change."""
    base_temp = 22 + 8 * math.sin((day / DURATION_DAYS) * math.pi)
    daily_cycle = 10 * math.sin((hour - 6) * math.pi / 12)
    variation = 2 * math.sin((day * 7 + hour) / 100)
    return max(10, base_temp + daily_cycle + variation)


def humidity_for_temperature(temp):
    """Generate humidity based on temperature."""
    base_humidity = 60 - (temp - 20) * 2
    return max(20, min(95, base_humidity + random.gauss(0, 5)))


def cloud_cover_base(day):
    """Generate base cloud cover varying over days."""
    return 40 + 30 * math.sin((day / DURATION_DAYS) * 4 * math.pi) + random.gauss(0, 10)


def cloud_cover_for_hour(day, hour, event_active=False):
    """Generate hourly cloud cover with daily variation."""
    base = cloud_cover_base(day)
    if event_active:
        base = min(95, base + 25)
    hourly_var = 15 * math.sin((hour * math.pi) / 12)
    return max(0, min(100, base + hourly_var))


def electricity_demand(zone, hour, day, temp, event_effect=1.0):
    """Calculate zone electricity demand with daily cycle."""
    base = ZONE_PROFILES[zone]["electricity_base"]
    
    if ZONE_PROFILES[zone]["type"] == "residential":
        peak_hour = 19
    elif ZONE_PROFILES[zone]["type"] == "commercial":
        peak_hour = 12
    elif ZONE_PROFILES[zone]["type"] == "industrial":
        peak_hour = 10
    else:
        peak_hour = 14
    
    daily_cycle = 1.0 + 0.3 * math.sin((hour - peak_hour) * math.pi / 12)
    temp_factor = 1.0 + (temp - 20) * 0.02
    weekly_factor = 1.0 if day % 7 < 5 else 0.9
    
    demand = base * daily_cycle * temp_factor * weekly_factor * event_effect
    return max(5, demand)


def solar_generation(zone, hour, day, cloud_cover, event_effect=1.0):
    """Calculate solar generation based on hour and cloud cover."""
    capacity = ZONE_PROFILES[zone]["solar_capacity"]
    
    if hour < 6 or hour >= 19:
        return 0.0
    
    solar_elevation = max(0, math.sin((hour - 6) * math.pi / 12))
    clear_sky_gen = capacity * solar_elevation
    cloud_reduction = (100 - cloud_cover) / 100.0
    generation = clear_sky_gen * cloud_reduction * event_effect
    
    return max(0, generation)


def water_consumption(zone, hour, day, temp, event_effect=1.0):
    """Calculate zone water consumption."""
    base = ZONE_PROFILES[zone]["water_base"]
    
    if ZONE_PROFILES[zone]["type"] == "residential":
        peak_hour = 8
    elif ZONE_PROFILES[zone]["type"] == "commercial":
        peak_hour = 12
    elif ZONE_PROFILES[zone]["type"] == "industrial":
        peak_hour = 14
    else:
        peak_hour = 10
    
    daily_cycle = 1.0 + 0.4 * math.sin((hour - peak_hour) * math.pi / 12)
    temp_factor = 1.0 + (temp - 20) * 0.015
    weekly_factor = 1.0 if day % 7 < 5 else 1.1
    
    consumption = base * daily_cycle * temp_factor * weekly_factor * event_effect
    return max(50000, consumption)


def event_effects(hour, day, zone):
    """Determine which events are active and their effects."""
    effects = {}
    
    for event in EVENTS_SCHEDULE:
        event_start_hour = event["day"] * 24 + event.get("start_hour", 0)
        event_end_hour = event_start_hour + event["duration"] * 24
        current_hour = day * 24 + hour
        
        if event_start_hour <= current_hour < event_end_hour and zone in event["zones"]:
            if event["effect"] == "heat":
                effects["temp_increase"] = effects.get("temp_increase", 0) + 3
                effects["electricity_multiplier"] = effects.get("electricity_multiplier", 1.0) * 1.2
                effects["water_multiplier"] = effects.get("water_multiplier", 1.0) * 1.15
            elif event["effect"] == "clouds":
                effects["cloud_increase"] = effects.get("cloud_increase", 0) + 40
            elif event["effect"] == "demand":
                effects["electricity_multiplier"] = effects.get("electricity_multiplier", 1.0) * 1.3
            elif event["effect"] == "disruption":
                effects["supply_reduction"] = 0.5
            elif event["effect"] == "recovery":
                effects["supply_recovery"] = True
            elif event["effect"] == "water":
                effects["water_supply_reduction"] = 0.6
            elif event["effect"] == "critical":
                effects["critical_service_active"] = True
            elif event["effect"] == "combined":
                effects["electricity_multiplier"] = effects.get("electricity_multiplier", 1.0) * 1.25
                effects["water_multiplier"] = effects.get("water_multiplier", 1.0) * 1.2
                effects["supply_reduction"] = 0.3
    
    return effects


def generate_dataset():
    """Generate 30-day synthetic dataset."""
    random.seed(SEED)
    
    rows = []
    
    # Initialize storage levels for each zone (track across time steps)
    zone_storage = {zone: 10000000 for zone in ZONES}
    
    for day in range(DURATION_DAYS):
        for hour in range(24):
            for zone in ZONES:
                current_time = START_DATE + timedelta(days=day, hours=hour)
                
                temp = temperature_for_day_hour(day, hour)
                humidity = humidity_for_temperature(temp)
                cloud_cover = cloud_cover_for_hour(day, hour)
                rainfall = max(0, random.gauss(0, 2)) if random.random() < 0.3 else 0
                wind_speed = max(0, random.gauss(10, 5))
                
                effects = event_effects(hour, day, zone)
                
                temp_adjusted = temp + effects.get("temp_increase", 0)
                cloud_adjusted = min(100, max(0, cloud_cover + effects.get("cloud_increase", 0)))
                
                elec_mult = effects.get("electricity_multiplier", 1.0)
                water_mult = effects.get("water_multiplier", 1.0)
                solar_mult = effects.get("solar_multiplier", 1.0)
                
                electricity_demand_mw = electricity_demand(zone, hour, day, temp_adjusted, elec_mult)
                solar_generation_mw = solar_generation(zone, hour, day, cloud_adjusted, solar_mult)
                water_consumption_litres = water_consumption(zone, hour, day, temp_adjusted, water_mult)
                
                electricity_capacity_mw = ZONE_PROFILES[zone]["electricity_base"] * 1.2 + (solar_generation_mw * 0.3)
                water_storage_capacity_litres = 15000000
                
                # Calculate electricity supply with reduction
                electricity_supply_mw = electricity_capacity_mw
                if effects.get("supply_reduction"):
                    electricity_supply_mw = electricity_capacity_mw * (1 - effects["supply_reduction"])
                if effects.get("supply_recovery"):
                    electricity_supply_mw = electricity_capacity_mw
                
                # Base water supply: 15M litres/day = 625k litres/hour normally
                base_water_supply = 15000000 / 24  # 625k litres/hour
                
                # Apply water supply reduction if event active
                water_supply_litres = base_water_supply
                if effects.get("water_supply_reduction"):
                    water_supply_litres = base_water_supply * (1 - effects["water_supply_reduction"])
                
                # Update water storage: previous_storage + supply - consumption
                prev_storage = zone_storage[zone]
                new_storage = prev_storage + water_supply_litres - water_consumption_litres
                new_storage = max(0, min(water_storage_capacity_litres, new_storage))
                zone_storage[zone] = new_storage
                water_storage_level_litres = new_storage
                
                hospital_electricity_demand_mw = ZONE_PROFILES[zone]["critical_service_electricity"]
                hospital_water_demand_litres = ZONE_PROFILES[zone]["critical_service_water"]
                emergency_service_demand_mw = hospital_electricity_demand_mw * 0.3
                
                critical_service_status = "active" if effects.get("critical_service_active") else "normal"
                
                resource_availability = int(100 - (electricity_demand_mw / electricity_capacity_mw * 30) if electricity_capacity_mw > 0 else 100)
                resource_availability = max(0, min(100, resource_availability))
                
                solar_capacity_mw = ZONE_PROFILES[zone]["solar_capacity"]
                solar_efficiency_percent = (solar_generation_mw / solar_capacity_mw * 100) if solar_capacity_mw > 0 else 0
                
                rows.append({
                    "timestamp": current_time.isoformat() + "Z",
                    "city_zone": zone,
                    "electricity_demand_mw": round(electricity_demand_mw, 2),
                    "electricity_supply_mw": round(electricity_supply_mw, 2),
                    "electricity_capacity_mw": round(electricity_capacity_mw, 2),
                    "water_consumption_litres": round(water_consumption_litres, 0),
                    "water_supply_litres": round(water_supply_litres, 0),
                    "water_storage_level_litres": round(water_storage_level_litres, 0),
                    "water_storage_capacity_litres": water_storage_capacity_litres,
                    "solar_generation_mw": round(solar_generation_mw, 2),
                    "solar_capacity_mw": solar_capacity_mw,
                    "solar_efficiency_percent": round(solar_efficiency_percent, 1),
                    "temperature_c": round(temp, 1),
                    "humidity_percent": round(humidity, 1),
                    "rainfall_mm": round(rainfall, 1),
                    "cloud_cover_percent": round(cloud_adjusted, 1),
                    "wind_speed_kmh": round(wind_speed, 1),
                    "hospital_electricity_demand_mw": round(hospital_electricity_demand_mw, 2),
                    "hospital_water_demand_litres": round(hospital_water_demand_litres, 0),
                    "emergency_service_demand_mw": round(emergency_service_demand_mw, 2),
                    "critical_service_status": critical_service_status,
                    "resource_availability": resource_availability,
                })
    
    return rows


def save_csv(rows):
    """Save rows to CSV file."""
    fieldnames = list(rows[0].keys())
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print("Generated {} records to {}".format(len(rows), OUTPUT_CSV))
    print("  Date range: {} to {}".format(rows[0]['timestamp'][:10], rows[-1]['timestamp'][:10]))
    print("  Zones: {}".format(len(set(r['city_zone'] for r in rows))))
    print("  Hours per zone: {}".format(len([r for r in rows if r['city_zone'] == ZONES[0]])))


if __name__ == "__main__":
    rows = generate_dataset()
    save_csv(rows)

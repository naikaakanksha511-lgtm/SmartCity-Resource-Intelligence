#!/usr/bin/env python3
"""Milestone 8.2 - Simplified Evidence Verification"""

import pandas as pd
import numpy as np
import json

# ============================================================================
# 1. WATER CONSERVATION - DETAILED ANALYSIS
# ============================================================================

print("=" * 70)
print("MILESTONE 8.2 - EVIDENCE-BASED DATA VERIFICATION")
print("=" * 70)

df = pd.read_csv('data/sample_data.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])

print("\n1. WATER CONSERVATION - DETAILED ANALYSIS")
print("-" * 70)

water_errors = []
for zone in sorted(df['city_zone'].unique()):
    zone_data = df[df['city_zone'] == zone].sort_values('timestamp').reset_index(drop=True)
    
    for idx in range(1, len(zone_data)):
        prev_storage = zone_data.loc[idx - 1, 'water_storage_level_litres']
        curr_supply = zone_data.loc[idx - 1, 'water_supply_litres']
        curr_consumption = zone_data.loc[idx - 1, 'water_consumption_litres']
        recorded_storage = zone_data.loc[idx, 'water_storage_level_litres']
        capacity = zone_data.loc[idx, 'water_storage_capacity_litres']
        
        expected_storage = prev_storage + curr_supply - curr_consumption
        expected_storage = max(0, min(expected_storage, capacity))
        
        residual = abs(recorded_storage - expected_storage)
        error_pct = (residual / capacity * 100) if capacity > 0 else 0
        
        if residual > 1000:
            water_errors.append({
                'timestamp': zone_data.loc[idx, 'timestamp'],
                'zone': zone,
                'prev_storage': prev_storage,
                'supply': curr_supply,
                'consumption': curr_consumption,
                'expected': expected_storage,
                'recorded': recorded_storage,
                'residual': residual,
                'error_pct': error_pct
            })

passing = 2880 - len(water_errors)
print("Total records: 2880")
print("Passing: {}".format(passing))
print("Failing: {}".format(len(water_errors)))
if water_errors:
    print("Max residual: {:.0f} L ({:.2f}%)".format(
        max(e['residual'] for e in water_errors),
        max(e['error_pct'] for e in water_errors)
    ))
    print("Mean residual: {:.0f} L".format(np.mean([e['residual'] for e in water_errors])))
    
    print("\nFirst 5 failing records:")
    for i, e in enumerate(water_errors[:5]):
        print("  {}: {} [{}] residual={:.0f}L".format(i+1, e['timestamp'], e['zone'], e['residual']))

# ============================================================================
# 2. DATASET DATES
# ============================================================================

print("\n2. DATASET DATES")
print("-" * 70)
print("Min timestamp: {}".format(df['timestamp'].min()))
print("Max timestamp: {}".format(df['timestamp'].max()))
days = (df['timestamp'].max() - df['timestamp'].min()).days + 1
print("Date range: {} days (expected 30, actual {})".format(30, days))
print("Total records: {} (expected 2880, actual {})".format(2880, len(df)))
records_per_day = len(df) / days
print("Records per day: {:.1f} (expected 96)".format(records_per_day))

# ============================================================================
# 3. HEATWAVE - ZONE BY ZONE
# ============================================================================

print("\n3. HEATWAVE TEMPERATURE AND DEMAND")
print("-" * 70)

# Find heatwave period
df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
min_ts = df['timestamp'].min()
start_offset_days = 19  # Day 20
heatwave_start = min_ts + pd.Timedelta(days=start_offset_days)
heatwave_end = heatwave_start + pd.Timedelta(days=3)

before_start = heatwave_start - pd.Timedelta(days=5)
after_end = heatwave_end + pd.Timedelta(days=5)

print("Heatwave period: {} to {}".format(heatwave_start, heatwave_end))

for zone in sorted(df['city_zone'].unique()):
    zone_df = df[df['city_zone'] == zone].copy()
    
    before = zone_df[(zone_df['timestamp'] >= before_start) & (zone_df['timestamp'] < heatwave_start)]
    during = zone_df[(zone_df['timestamp'] >= heatwave_start) & (zone_df['timestamp'] < heatwave_end)]
    after = zone_df[(zone_df['timestamp'] >= heatwave_end) & (zone_df['timestamp'] <= after_end)]
    
    if len(during) > 0:
        t_before = before['temperature_c'].mean() if len(before) > 0 else 0
        t_during = during['temperature_c'].mean()
        d_before = before['electricity_demand_mw'].mean() if len(before) > 0 else 0
        d_during = during['electricity_demand_mw'].mean()
        
        if d_before > 0:
            demand_increase_pct = (d_during - d_before) / d_before * 100
        else:
            demand_increase_pct = 0
        
        corr = during[['temperature_c', 'electricity_demand_mw']].corr().iloc[0, 1] if len(during) > 1 else 0
        
        print("\n{}:".format(zone))
        print("  Temp: {:.1f} C (before) -> {:.1f} C (during), delta={:.1f} C".format(
            t_before, t_during, t_during - t_before))
        print("  Demand: {:.1f} MW (before) -> {:.1f} MW (during), delta={:.1f}%".format(
            d_before, d_during, demand_increase_pct))
        print("  Correlation (temp vs demand): {:.3f}".format(corr))
        print("  Sample count during: {}".format(len(during)))

# ============================================================================
# 4. SOLAR GENERATION
# ============================================================================

print("\n4. SOLAR GENERATION")
print("-" * 70)

violations = []
nighttime_nonzero = 0
nighttime_total = 0

for idx, row in df.iterrows():
    solar_gen = row['solar_generation_mw']
    solar_capacity = row['solar_capacity_mw']
    hour = row['timestamp'].hour
    
    # Violations
    if solar_gen > solar_capacity + 0.1:
        violations.append((row['timestamp'], row['city_zone'], solar_gen, solar_capacity))
    
    # Nighttime
    if hour >= 20 or hour < 6:
        nighttime_total += 1
        if solar_gen > 0.1:
            nighttime_nonzero += 1

print("Total solar records: {}".format(len(df)))
print("Violations (exceeds capacity): {}".format(len(violations)))
print("Nighttime total records: {}".format(nighttime_total))
print("Nighttime with generation >0.1 MW: {} ({:.2f}%)".format(
    nighttime_nonzero,
    nighttime_nonzero / nighttime_total * 100 if nighttime_total > 0 else 0
))

# ============================================================================
# 5. ELECTRICITY AND WATER DISRUPTIONS
# ============================================================================

print("\n5. ELECTRICITY AND WATER DISRUPTIONS")
print("-" * 70)

events_df = pd.read_csv('data/city_events.csv')
print("Events in city_events.csv: {}".format(len(events_df)))
print("Event types:")
for idx, row in events_df.iterrows():
    print("  - {}: {} to {}".format(row['event_type'], row['start_timestamp'], row['end_timestamp']))

# Check for supply anomalies in Central District
central = df[df['city_zone'] == 'Central District'].sort_values('timestamp').copy()
central['supply_ma'] = central['electricity_supply_mw'].rolling(window=24, center=True).mean()
central['supply_ratio'] = central['electricity_supply_mw'] / central['supply_ma']

anomalies = central[central['supply_ratio'] < 0.75]
print("\nElectricity supply anomalies in Central District (ratio <0.75):")
print("  Found: {}".format(len(anomalies)))
if len(anomalies) > 0:
    print("  First 3 anomalies:")
    for idx, row in anomalies.head(3).iterrows():
        print("    - {}: {:.1f} MW (ratio {:.2f})".format(
            row['timestamp'], row['electricity_supply_mw'], row['supply_ratio']))

# ============================================================================
# 6. TESTS
# ============================================================================

print("\n6. TEST RESULTS")
print("-" * 70)

import subprocess
result = subprocess.run(
    ['python', '-m', 'pytest', 'tests/', '-v', '--tb=no'],
    capture_output=True,
    text=True,
    timeout=120
)

output = result.stdout + result.stderr
passed = output.count(' PASSED')
failed = output.count(' FAILED')

print("pytest return code: {}".format(result.returncode))
print("Tests passed: {}".format(passed))
print("Tests failed: {}".format(failed))

# ============================================================================
# 7. DETERMINISTIC GENERATION
# ============================================================================

print("\n7. DETERMINISTIC GENERATION")
print("-" * 70)

import hashlib

# Run 1
subprocess.run(['python', 'scripts/generate_sample_data.py'], 
               capture_output=True, timeout=30)
with open('data/sample_data.csv', 'rb') as f:
    data1 = f.read()
hash1 = hashlib.md5(data1).hexdigest()

# Run 2
subprocess.run(['python', 'scripts/generate_sample_data.py'], 
               capture_output=True, timeout=30)
with open('data/sample_data.csv', 'rb') as f:
    data2 = f.read()
hash2 = hashlib.md5(data2).hexdigest()

print("Run 1 MD5: {}".format(hash1))
print("Run 2 MD5: {}".format(hash2))
print("Byte-for-byte identical: {}".format(data1 == data2))
print("File size: {} bytes".format(len(data1)))

# ============================================================================
# EVIDENCE TABLE
# ============================================================================

print("\n" + "=" * 70)
print("EVIDENCE TABLE - PASS/FAIL/PARTIAL")
print("=" * 70)

results = {
    '1. Water Conservation': 'PARTIAL' if 0 < len(water_errors) <= 100 else 'FAIL' if len(water_errors) > 100 else 'PASS',
    '2. Dataset Dates': 'PASS' if days == 30 and len(df) == 2880 else 'FAIL',
    '3. Heatwave Effect': 'PARTIAL',  # Need zone-by-zone analysis
    '4. Solar Constraints': 'PASS' if len(violations) == 0 else 'FAIL',
    '5. Electricity Disruptions': 'PARTIAL',  # Need more detailed analysis
    '6. Test Results': 'PASS' if result.returncode == 0 else 'FAIL',
    '7. Deterministic Generation': 'PASS' if data1 == data2 else 'FAIL'
}

for check, status in results.items():
    print("{:<30} {}".format(check, status))

print("\n" + "=" * 70)

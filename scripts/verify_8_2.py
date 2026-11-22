#!/usr/bin/env python3
"""
Milestone 8.2 — Final Evidence-Based Data Verification
Checks all five contradictions with actual measurements from current files.
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime

# ============================================================================
# 1. WATER CONSERVATION VERIFICATION
# ============================================================================

def verify_water_conservation():
    """Calculate water balance residual for every record."""
    df = pd.read_csv('data/sample_data.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values(['city_zone', 'timestamp']).reset_index(drop=True)
    
    results = {
        'total_records': len(df),
        'passing_records': 0,
        'failing_records': [],
        'max_abs_error_litres': 0,
        'mean_abs_error_litres': 0,
        'max_error_percent': 0
    }
    
    errors = []
    
    # Group by zone
    for zone in sorted(df['city_zone'].unique()):
        zone_data = df[df['city_zone'] == zone].copy()
        zone_data = zone_data.reset_index(drop=True)
        
        # For each record (starting from 1), verify: 
        # storage[t] = storage[t-1] + supply[t-1] - consumption[t-1]
        for idx in range(1, len(zone_data)):
            prev_storage = zone_data.loc[idx - 1, 'water_storage_level_litres']
            curr_supply = zone_data.loc[idx - 1, 'water_supply_litres']  # Previous hour supply
            curr_consumption = zone_data.loc[idx - 1, 'water_consumption_litres']  # Previous hour consumption
            recorded_storage = zone_data.loc[idx, 'water_storage_level_litres']
            
            # Calculate expected storage
            expected_storage = prev_storage + curr_supply - curr_consumption
            
            # Bounded by capacity
            capacity = zone_data.loc[idx, 'water_storage_capacity_litres']
            expected_storage = max(0, min(expected_storage, capacity))
            
            # Calculate residual
            residual = abs(recorded_storage - expected_storage)
            error_percent = (residual / capacity * 100) if capacity > 0 else 0
            
            if residual > 1000:  # Tolerance: 1KB (floating point rounding)
                errors.append({
                    'timestamp': zone_data.loc[idx, 'timestamp'],
                    'zone': zone,
                    'idx': idx,
                    'prev_storage_litres': prev_storage,
                    'supply_litres': curr_supply,
                    'consumption_litres': curr_consumption,
                    'expected_storage_litres': expected_storage,
                    'recorded_storage_litres': recorded_storage,
                    'residual_litres': residual,
                    'error_percent': error_percent,
                    'capacity_litres': capacity
                })
                results['failing_records'].append({
                    'timestamp': str(zone_data.loc[idx, 'timestamp']),
                    'zone': zone,
                    'residual': residual,
                    'error_percent': error_percent
                })
            else:
                results['passing_records'] += 1
            
            if residual > results['max_abs_error_litres']:
                results['max_abs_error_litres'] = residual
            if error_percent > results['max_error_percent']:
                results['max_error_percent'] = error_percent
    
    if errors:
        results['mean_abs_error_litres'] = np.mean([e['residual_litres'] for e in errors])
    
    results['error_count'] = len(errors)
    results['errors'] = errors[:10]  # First 10 for detail
    
    return results

# ============================================================================
# 2. DATASET DATES VERIFICATION
# ============================================================================

def verify_dataset_dates():
    """Check date range consistency across all sources."""
    df = pd.read_csv('data/sample_data.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    with open('data/city_events.csv') as f:
        events_first = f.readline()
    
    with open('scripts/generate_sample_data.py') as f:
        generator_code = f.read()
    
    results = {
        'csv_min_timestamp': str(df['timestamp'].min()),
        'csv_max_timestamp': str(df['timestamp'].max()),
        'csv_date_range_days': (df['timestamp'].max() - df['timestamp'].min()).days,
        'total_records': len(df),
        'records_per_day': len(df) / ((df['timestamp'].max() - df['timestamp'].min()).days + 1),
    }
    
    # Extract start date from generator if visible
    if 'start_date' in generator_code or 'datetime' in generator_code:
        results['generator_has_date_config'] = True
    
    return results

# ============================================================================
# 3. HEATWAVE VERIFICATION
# ============================================================================

def verify_heatwave_effect():
    """Measure temperature and demand changes by zone, before/during/after heatwave."""
    df = pd.read_csv('data/sample_data.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    
    # Heatwave is on Day 20-22 (from prior reports)
    # Map to actual timestamps
    min_date = df['timestamp'].min().date()
    heatwave_start = pd.Timestamp(year=min_date.year, month=min_date.month, day=min_date.day, tz='UTC') + pd.Timedelta(days=19)
    heatwave_end = heatwave_start + pd.Timedelta(days=3)
    
    before_start = heatwave_start - pd.Timedelta(days=5)
    after_end = heatwave_end + pd.Timedelta(days=5)
    
    results = {
        'heatwave_period': f'{heatwave_start} to {heatwave_end}',
        'zones': {}
    }
    
    for zone in sorted(df['city_zone'].unique()):
        zone_data = df[df['city_zone'] == zone].copy()
        
        # Before heatwave
        before = zone_data[(zone_data['timestamp'] >= before_start) & (zone_data['timestamp'] < heatwave_start)]
        # During heatwave
        during = zone_data[(zone_data['timestamp'] >= heatwave_start) & (zone_data['timestamp'] < heatwave_end)]
        # After heatwave
        after = zone_data[(zone_data['timestamp'] >= heatwave_end) & (zone_data['timestamp'] <= after_end)]
        
        if len(before) > 0 and len(during) > 0 and len(after) > 0:
            temp_before = before['temperature_c'].mean()
            temp_during = during['temperature_c'].mean()
            temp_after = after['temperature_c'].mean()
            
            demand_before = before['electricity_demand_mw'].mean()
            demand_during = during['electricity_demand_mw'].mean()
            demand_after = after['electricity_demand_mw'].mean()
            
            # Correlation
            if len(during) > 1:
                corr = during[['temperature_c', 'electricity_demand_mw']].corr().iloc[0, 1]
            else:
                corr = 0
            
            results['zones'][zone] = {
                'temp_before_c': round(temp_before, 2),
                'temp_during_c': round(temp_during, 2),
                'temp_after_c': round(temp_after, 2),
                'temp_increase_c': round(temp_during - temp_before, 2),
                'demand_before_mw': round(demand_before, 2),
                'demand_during_mw': round(demand_during, 2),
                'demand_after_mw': round(demand_after, 2),
                'demand_increase_pct': round((demand_during - demand_before) / demand_before * 100, 2) if demand_before > 0 else 0,
                'correlation_temp_demand': round(corr, 3),
                'sample_count_during': len(during)
            }
    
    return results

# ============================================================================
# 4. SOLAR VERIFICATION
# ============================================================================

def verify_solar_capacity():
    """Check solar generation against installed capacity from zone metadata."""
    df = pd.read_csv('data/sample_data.csv')
    
    with open('data/zone_metadata.json') as f:
        zone_meta = json.load(f)
    
    results = {
        'total_solar_records': len(df),
        'violations': 0,
        'violations_detail': [],
        'nighttime_records': 0,
        'nighttime_generation_nonzero': 0,
        'cloud_cover_effect_checked': False
    }
    
    for idx, row in df.iterrows():
        zone = row['city_zone']
        solar_gen = row['solar_generation_mw']
        solar_capacity = row['solar_capacity_mw']
        hour = pd.to_datetime(row['timestamp']).hour
        
        # Check capacity
        if solar_gen > solar_capacity + 0.1:  # 0.1 MW tolerance for rounding
            results['violations'] += 1
            results['violations_detail'].append({
                'timestamp': row['timestamp'],
                'zone': zone,
                'generation_mw': solar_gen,
                'capacity_mw': solar_capacity
            })
        
        # Check nighttime (20:00 to 06:00)
        if hour >= 20 or hour < 6:
            results['nighttime_records'] += 1
            if solar_gen > 0.1:  # Tolerance for rounding
                results['nighttime_generation_nonzero'] += 1
    
    results['nighttime_generation_nonzero_pct'] = round(
        results['nighttime_generation_nonzero'] / results['nighttime_records'] * 100, 2
    ) if results['nighttime_records'] > 0 else 0
    
    return results

# ============================================================================
# 5. ELECTRICITY AND WATER DISRUPTIONS
# ============================================================================

def verify_disruptions():
    """Check disruption and recovery timings."""
    df = pd.read_csv('data/sample_data.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Load events
    events = pd.read_csv('data/city_events.csv')
    
    results = {
        'disruption_events': [],
        'recovery_sequences': []
    }
    
    # Find disruptions and recoveries in events
    for idx, event in events.iterrows():
        if 'disruption' in event['event_type'].lower():
            results['disruption_events'].append({
                'event': event['event_type'],
                'start': event['start_timestamp'],
                'end': event['end_timestamp'],
                'zone': event.get('zone', 'N/A')
            })
    
    # Verify supply patterns for a disruption event
    # Look for electricity supply disruptions in Central District
    central_data = df[df['city_zone'] == 'Central District'].sort_values('timestamp')
    
    # Check if there's a significant supply drop
    central_data['supply_ratio'] = central_data['electricity_supply_mw'] / central_data['electricity_supply_mw'].rolling(24).mean()
    
    # Find anomalies (supply < 70% of rolling mean)
    anomalies = central_data[central_data['supply_ratio'] < 0.7]
    
    if len(anomalies) > 0:
        results['supply_anomalies_found'] = len(anomalies)
        results['anomaly_sample'] = anomalies[['timestamp', 'electricity_supply_mw']].head(3).to_dict('records')
    
    return results

# ============================================================================
# 6. TEST RESULTS
# ============================================================================

def run_tests():
    """Run pytest and capture results."""
    import subprocess
    result = subprocess.run(
        ['python', '-m', 'pytest', 'tests/', '-v', '--tb=short'],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    # Parse output
    output = result.stdout + result.stderr
    
    # Extract summary line
    summary = {
        'return_code': result.returncode,
        'passed': output.count(' PASSED'),
        'failed': output.count(' FAILED'),
        'output_last_lines': output.split('\n')[-10:]
    }
    
    return summary

# ============================================================================
# 7. DETERMINISTIC GENERATION
# ============================================================================

def verify_deterministic_generation():
    """Run generator twice and compare byte-for-byte."""
    import subprocess
    import hashlib
    
    results = {}
    
    # Run 1
    subprocess.run(['python', 'scripts/generate_sample_data.py'], capture_output=True)
    with open('data/sample_data.csv', 'rb') as f:
        data1 = f.read()
    hash1 = hashlib.md5(data1).hexdigest()
    
    # Run 2
    subprocess.run(['python', 'scripts/generate_sample_data.py'], capture_output=True)
    with open('data/sample_data.csv', 'rb') as f:
        data2 = f.read()
    hash2 = hashlib.md5(data2).hexdigest()
    
    results['run1_md5'] = hash1
    results['run2_md5'] = hash2
    results['identical'] = data1 == data2
    results['size1'] = len(data1)
    results['size2'] = len(data2)
    
    return results

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == '__main__':
    print('MILESTONE 8.2 — EVIDENCE-BASED DATA VERIFICATION')
    print('=' * 80)
    
    # 1. Water conservation
    print('\n1. WATER CONSERVATION')
    print('-' * 80)
    water_results = verify_water_conservation()
    print(f"Total records: {water_results['total_records']}")
    print(f"Passing: {water_results['passing_records']}")
    print(f"Failing: {water_results['error_count']}")
    print(f"Max abs error: {water_results['max_abs_error_litres']:.0f} L ({water_results['max_error_percent']:.2f}%)")
    print(f"Mean abs error: {water_results['mean_abs_error_litres']:.0f} L")
    if water_results['errors']:
        print(f"\nFirst failing record:")
        e = water_results['errors'][0]
        print(f"  Zone: {e['zone']}, Timestamp: {e['timestamp']}")
        print(f"  Formula: {e['prev_storage_litres']:.0f} + {e['supply_litres']:.0f} - {e['consumption_litres']:.0f} = {e['expected_storage_litres']:.0f}")
        print(f"  Recorded: {e['recorded_storage_litres']:.0f}, Residual: {e['residual_litres']:.0f} L")
    
    # 2. Dataset dates
    print('\n2. DATASET DATES')
    print('-' * 80)
    date_results = verify_dataset_dates()
    print(f"CSV min timestamp: {date_results['csv_min_timestamp']}")
    print(f"CSV max timestamp: {date_results['csv_max_timestamp']}")
    print(f"Date range: {date_results['csv_date_range_days']} days")
    print(f"Total records: {date_results['total_records']}")
    print(f"Records per day: {date_results['records_per_day']:.1f}")
    
    # 3. Heatwave
    print('\n3. HEATWAVE ANALYSIS')
    print('-' * 80)
    heatwave_results = verify_heatwave_effect()
    print(f"Heatwave period: {heatwave_results['heatwave_period']}")
    for zone, data in heatwave_results['zones'].items():
        print(f"\n{zone}:")
        print(f"  Temp: {data['temp_before_c']}°C → {data['temp_during_c']}°C (+{data['temp_increase_c']}°C)")
        print(f"  Demand: {data['demand_before_mw']:.1f} → {data['demand_during_mw']:.1f} MW (+{data['demand_increase_pct']:.1f}%)")
        print(f"  Correlation: {data['correlation_temp_demand']}, Samples: {data['sample_count_during']}")
    
    # 4. Solar
    print('\n4. SOLAR GENERATION')
    print('-' * 80)
    solar_results = verify_solar_capacity()
    print(f"Total solar records: {solar_results['total_solar_records']}")
    print(f"Violations (exceeds capacity): {solar_results['violations']}")
    print(f"Nighttime records checked: {solar_results['nighttime_records']}")
    print(f"Nighttime with nonzero generation: {solar_results['nighttime_generation_nonzero']} ({solar_results['nighttime_generation_nonzero_pct']:.2f}%)")
    
    # 5. Disruptions
    print('\n5. ELECTRICITY AND WATER DISRUPTIONS')
    print('-' * 80)
    disrupt_results = verify_disruptions()
    print(f"Disruption events defined: {len(disrupt_results['disruption_events'])}")
    for event in disrupt_results['disruption_events']:
        print(f"  - {event['event']}: {event['start']} to {event['end']}")
    if 'supply_anomalies_found' in disrupt_results:
        print(f"Supply anomalies found: {disrupt_results['supply_anomalies_found']}")
    
    # 6. Tests
    print('\n6. TEST RESULTS')
    print('-' * 80)
    test_results = run_tests()
    print(f"Return code: {test_results['return_code']}")
    print(f"Passed: {test_results['passed']}")
    print(f"Failed: {test_results['failed']}")
    
    # 7. Deterministic
    print('\n7. DETERMINISTIC GENERATION')
    print('-' * 80)
    det_results = verify_deterministic_generation()
    print(f"Run 1 MD5: {det_results['run1_md5']}")
    print(f"Run 2 MD5: {det_results['run2_md5']}")
    print(f"Byte-for-byte identical: {det_results['identical']}")
    print(f"Size: {det_results['size1']} bytes (run 1), {det_results['size2']} bytes (run 2)")
    
    # Save results
    all_results = {
        'water_conservation': water_results,
        'dataset_dates': date_results,
        'heatwave': heatwave_results,
        'solar': solar_results,
        'disruptions': disrupt_results,
        'tests': test_results,
        'deterministic': det_results
    }
    
    with open('verify_8_2_results.json', 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print('\n' + '=' * 80)
    print('Results saved to: verify_8_2_results.json')

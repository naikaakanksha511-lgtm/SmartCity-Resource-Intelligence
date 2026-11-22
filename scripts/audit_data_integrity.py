"""Data integrity audit for Smart City synthetic dataset."""

import csv
import json
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

SAMPLE_DATA_PATH = "data/sample_data.csv"
ZONE_METADATA_PATH = "data/zone_metadata.json"
EVENTS_PATH = "data/city_events.csv"

class DataAudit:
    def __init__(self):
        self.df = pd.read_csv(SAMPLE_DATA_PATH)
        with open(ZONE_METADATA_PATH) as f:
            self.zone_metadata = json.load(f)
        self.events_df = pd.read_csv(EVENTS_PATH)
        self.issues = []
        self.measurements = {}
        
    def audit_water_balance(self):
        """Verify: previous_storage + supply - consumption = current_storage."""
        print("\n" + "="*80)
        print("AUDIT 1: WATER BALANCE VERIFICATION")
        print("="*80)
        
        water_issues = []
        zone_errors = {}
        
        for zone in self.df["city_zone"].unique():
            zone_data = self.df[self.df["city_zone"] == zone].sort_values("timestamp")
            storage_capacity = zone_data["water_storage_capacity_litres"].iloc[0]
            
            zone_errors[zone] = []
            
            for i in range(1, len(zone_data)):
                prev_row = zone_data.iloc[i-1]
                curr_row = zone_data.iloc[i]
                
                prev_storage = prev_row["water_storage_level_litres"]
                curr_storage = curr_row["water_storage_level_litres"]
                hourly_supply = prev_row["water_supply_litres"]
                hourly_consumption = prev_row["water_consumption_litres"]
                
                # Calculate expected storage: previous + supply - consumption
                expected_storage = prev_storage + hourly_supply - hourly_consumption
                expected_storage = max(0, min(storage_capacity, expected_storage))
                
                error = abs(curr_storage - expected_storage)
                
                if error > 100000:  # Tolerance: 100k litres (0.67% of 15M capacity)
                    zone_errors[zone].append({
                        "timestamp": curr_row["timestamp"],
                        "prev_storage": prev_storage,
                        "supply": hourly_supply,
                        "consumption": hourly_consumption,
                        "expected_storage": expected_storage,
                        "actual_storage": curr_storage,
                        "error": error
                    })
        
        print("\nZone-by-zone balance errors (>100k litres):")
        total_errors = sum(len(errors) for errors in zone_errors.values())
        
        for zone, errors in zone_errors.items():
            print("  {}: {} imbalances out of {}".format(zone, len(errors), len(self.df[self.df['city_zone'] == zone])))
            if errors:
                self.issues.append("Water balance: {} has {} storage calculation errors".format(zone, len(errors)))
                for err in errors[:3]:  # Show first 3
                    print("    {}: expected {:.0f}, got {:.0f} (error: {:.0f})".format(
                        err['timestamp'], err['expected_storage'], err['actual_storage'], err['error']))
        
        self.measurements["water_balance_errors"] = total_errors
        self.measurements["water_balance_errors_by_zone"] = {z: len(e) for z, e in zone_errors.items()}
        
        if total_errors == 0:
            print("\n[OK] Water storage balance is CORRECT across all zones")
        else:
            print("\n[ERROR] Found {} water balance errors".format(total_errors))
    
    def audit_electricity_recovery(self):
        """Verify: disruption and recovery occur at different times; supply recovers."""
        print("\n" + "="*80)
        print("AUDIT 2: ELECTRICITY RECOVERY VERIFICATION")
        print("="*80)
        
        # Check events file for disruption and recovery
        disruptions = self.events_df[self.events_df["event_type"] == "electricity_supply_disruption"]
        recoveries = self.events_df[self.events_df["event_type"] == "recovery"]
        
        print("\nFound {} disruption events and {} recovery events".format(len(disruptions), len(recoveries)))
        
        measurements = {
            "disruptions": [],
            "recoveries": [],
            "recovery_sequences": []
        }
        
        for idx, disruption in disruptions.iterrows():
            affected_zones = disruption["affected_zones"].split(", ")
            start = pd.Timestamp(disruption["start_timestamp"])
            end = pd.Timestamp(disruption["end_timestamp"])
            field = disruption["field_impacted"]
            
            if field == "electricity_supply_mw":
                magnitude = disruption["magnitude"]
                print("\nDisruption: {}".format(disruption['description']))
                print("  Time: {} to {}".format(start, end))
                print("  Zones: {}".format(affected_zones))
                print("  Impact: supply reduced to {:.0f}% capacity".format(magnitude*100))
                
                # Measure actual values during disruption
                for zone in affected_zones:
                    zone_data = self.df[self.df["city_zone"] == zone].copy()
                    zone_data["timestamp"] = pd.to_datetime(zone_data["timestamp"])
                    
                    during_disrupt = zone_data[(zone_data["timestamp"] >= start) & (zone_data["timestamp"] < end)]
                    
                    if len(during_disrupt) > 0:
                        normal_supply = zone_data[zone_data["timestamp"] < start]["electricity_supply_mw"].tail(1).values
                        disrupt_supply = during_disrupt["electricity_supply_mw"].values
                        
                        if len(normal_supply) > 0:
                            normal_avg = normal_supply[0]
                            disrupt_avg = disrupt_supply.mean()
                            reduction_ratio = disrupt_avg / normal_avg if normal_avg > 0 else 0
                            
                            print("    {}: {:.1f} MW -> {:.1f} MW (ratio: {:.2f})".format(
                                zone, normal_avg, disrupt_avg, reduction_ratio))
                            measurements["disruptions"].append({
                                "zone": zone,
                                "normal_supply_mw": normal_avg,
                                "disrupted_supply_mw": disrupt_avg,
                                "reduction_ratio": reduction_ratio,
                                "expected_ratio": magnitude
                            })
        
        # Check recovery sequences
        for idx, recovery in recoveries.iterrows():
            affected_zones = recovery["affected_zones"].split(", ")
            start = pd.Timestamp(recovery["start_timestamp"])
            end = pd.Timestamp(recovery["end_timestamp"])
            
            print("\nRecovery: {}".format(recovery['description']))
            print("  Time: {} to {}".format(start, end))
            print("  Zones: {}".format(affected_zones))
            
            for zone in affected_zones:
                zone_data = self.df[self.df["city_zone"] == zone].copy()
                zone_data["timestamp"] = pd.to_datetime(zone_data["timestamp"])
                
                before_recovery = zone_data[(zone_data["timestamp"] >= (start - timedelta(hours=2))) & (zone_data["timestamp"] < start)]
                during_recovery = zone_data[(zone_data["timestamp"] >= start) & (zone_data["timestamp"] < end)]
                after_recovery = zone_data[(zone_data["timestamp"] >= end) & (zone_data["timestamp"] < (end + timedelta(hours=2)))]
                
                if len(before_recovery) > 0 and len(after_recovery) > 0:
                    before_avg = before_recovery["electricity_supply_mw"].mean()
                    after_avg = after_recovery["electricity_supply_mw"].mean()
                    
                    print("    {}: {:.1f} MW (before) -> {:.1f} MW (after)".format(zone, before_avg, after_avg))
                    measurements["recovery_sequences"].append({
                        "zone": zone,
                        "before_recovery_supply_mw": before_avg,
                        "after_recovery_supply_mw": after_avg
                    })
        
        self.measurements["electricity_recovery"] = measurements
        
        if measurements["recovery_sequences"]:
            improved = sum(1 for seq in measurements["recovery_sequences"] if seq["after_recovery_supply_mw"] >= seq["before_recovery_supply_mw"] * 0.95)
            print("\n[OK] {}/{} recovery sequences show supply restoration".format(improved, len(measurements['recovery_sequences'])))
        
    def audit_heatwave_temperature_match(self):
        """Verify: recorded temperature matches temperature used in demand calculation."""
        print("\n" + "="*80)
        print("AUDIT 3: HEATWAVE TEMPERATURE DEMAND CORRELATION")
        print("="*80)
        
        # Find heatwave events
        heatwave_events = self.events_df[self.events_df["event_type"] == "heatwave"]
        
        print("\nFound {} heatwave events".format(len(heatwave_events)))
        
        measurements = {}
        
        for idx, event in heatwave_events.iterrows():
            affected_zones = event["affected_zones"].split(", ")
            start = pd.Timestamp(event["start_timestamp"])
            end = pd.Timestamp(event["end_timestamp"])
            
            print("\nHeatwave: {}".format(event['description']))
            print("  Time: {} to {}".format(start, end))
            print("  Impact: {} magnitude {}".format(event['field_impacted'], event['magnitude']))
            
            before_start = start - timedelta(hours=6)
            
            for zone in affected_zones:
                zone_data = self.df[self.df["city_zone"] == zone].copy()
                zone_data["timestamp"] = pd.to_datetime(zone_data["timestamp"])
                
                before_data = zone_data[(zone_data["timestamp"] >= before_start) & (zone_data["timestamp"] < start)]
                during_data = zone_data[(zone_data["timestamp"] >= start) & (zone_data["timestamp"] < end)]
                
                if len(before_data) > 0 and len(during_data) > 0:
                    before_temp = before_data["temperature_c"].mean()
                    during_temp = during_data["temperature_c"].mean()
                    temp_increase = during_temp - before_temp
                    
                    before_demand = before_data["electricity_demand_mw"].mean()
                    during_demand = during_data["electricity_demand_mw"].mean()
                    demand_increase_pct = ((during_demand - before_demand) / before_demand * 100) if before_demand > 0 else 0
                    
                    # Temperature-demand correlation
                    temp_demand_data = zone_data[["temperature_c", "electricity_demand_mw"]].copy()
                    if len(temp_demand_data) > 1:
                        correlation = temp_demand_data["temperature_c"].corr(temp_demand_data["electricity_demand_mw"])
                    else:
                        correlation = 0
                    
                    print("\n  {}:".format(zone))
                    print("    Temperature: {:.1f}C -> {:.1f}C (D {:.1f}C)".format(before_temp, during_temp, temp_increase))
                    print("    Electricity demand: {:.1f} MW -> {:.1f} MW (+{:.1f}%)".format(before_demand, during_demand, demand_increase_pct))
                    print("    Temperature-demand correlation: {:.3f}".format(correlation))
                    
                    measurements["{}_{}".format(zone, event['event_id'])] = {
                        "temp_before": before_temp,
                        "temp_during": during_temp,
                        "temp_increase": temp_increase,
                        "demand_before_mw": before_demand,
                        "demand_during_mw": during_demand,
                        "demand_increase_pct": demand_increase_pct,
                        "correlation": correlation
                    }
        
        self.measurements["heatwave_temperature_demand"] = measurements
        
        correlations = [m.get("correlation", 0) for m in measurements.values()]
        if correlations:
            avg_corr = statistics.mean(correlations)
            print("\n[OK] Average temperature-demand correlation: {:.3f}".format(avg_corr))
            if avg_corr > 0.3:
                print("  Positive correlation confirmed: heatwaves correlate with higher demand")
            else:
                self.issues.append("Heatwave-demand correlation is weak")
    
    def audit_solar_capacity_and_cloud_effects(self):
        """Verify: solar generation respects installed capacity and responds to cloud cover."""
        print("\n" + "="*80)
        print("AUDIT 4: SOLAR GENERATION CAPACITY AND CLOUD COVER EFFECTS")
        print("="*80)
        
        measurements = {}
        
        for zone in self.df["city_zone"].unique():
            zone_data = self.df[self.df["city_zone"] == zone].copy()
            solar_capacity = zone_data["solar_capacity_mw"].iloc[0]
            
            print("\n{} (capacity: {} MW):".format(zone, solar_capacity))
            
            # Check capacity constraint
            exceeds_capacity = zone_data[zone_data["solar_generation_mw"] > solar_capacity]
            if len(exceeds_capacity) > 0:
                print("  [ERROR] VIOLATION: {} readings exceed capacity".format(len(exceeds_capacity)))
                self.issues.append("Solar: {} has {} readings exceeding {} MW capacity".format(zone, len(exceeds_capacity), solar_capacity))
                for _, row in exceeds_capacity.head(3).iterrows():
                    print("      {}: {} MW > {} MW".format(row['timestamp'], row['solar_generation_mw'], solar_capacity))
            else:
                print("  [OK] No capacity violations")
            
            # Cloud cover correlation
            daylight_hours = zone_data[(zone_data["solar_generation_mw"] > 0.1)]
            if len(daylight_hours) > 0:
                cloud_gen_corr = daylight_hours["cloud_cover_percent"].corr(daylight_hours["solar_generation_mw"])
                print("  Cloud cover vs generation correlation: {:.3f}".format(cloud_gen_corr))
                
                if cloud_gen_corr < -0.3:
                    print("    [OK] Strong negative correlation (more clouds = less solar)")
                else:
                    print("    [WARN] Weak negative correlation")
                
                measurements[zone] = {
                    "solar_capacity_mw": solar_capacity,
                    "capacity_violations": len(exceeds_capacity),
                    "max_generation_mw": zone_data["solar_generation_mw"].max(),
                    "avg_generation_mw": zone_data["solar_generation_mw"].mean(),
                    "cloud_generation_correlation": cloud_gen_corr,
                    "daylight_hours_analyzed": len(daylight_hours)
                }
            
            # Cloud cover spike events
            cloud_events = self.events_df[self.events_df["event_type"] == "low_solar_generation"]
            for _, event in cloud_events.iterrows():
                affected = event["affected_zones"].split(", ")
                if zone in affected:
                    start = pd.Timestamp(event["start_timestamp"])
                    end = pd.Timestamp(event["end_timestamp"])
                    
                    before = zone_data[(zone_data["timestamp"] < str(start)) & 
                                      (zone_data["timestamp"] >= str(start - timedelta(hours=6)))]
                    during = zone_data[(zone_data["timestamp"] >= str(start)) & (zone_data["timestamp"] < str(end))]
                    
                    if len(before) > 0 and len(during) > 0:
                        before_cloud = before["cloud_cover_percent"].mean()
                        during_cloud = during["cloud_cover_percent"].mean()
                        before_gen = before["solar_generation_mw"].mean()
                        during_gen = during["solar_generation_mw"].mean()
                        gen_reduction_pct = ((before_gen - during_gen) / before_gen * 100) if before_gen > 0 else 0
                        
                        print("\n  Low solar event ({}):".format(event['event_id']))
                        print("    Cloud: {:.0f}% -> {:.0f}% (D {:.0f}%)".format(before_cloud, during_cloud, during_cloud - before_cloud))
                        print("    Generation: {:.2f} MW -> {:.2f} MW (-{:.1f}%)".format(before_gen, during_gen, gen_reduction_pct))
        
        self.measurements["solar_capacity_effects"] = measurements
        
        total_violations = sum(m.get("capacity_violations", 0) for m in measurements.values())
        if total_violations == 0:
            print("\n[OK] All solar generation values respect installed capacity")
        else:
            print("\n[ERROR] Found {} solar capacity violations".format(total_violations))
    
    def audit_scenario_effects(self):
        """Measure actual before/during/after effects for every event."""
        print("\n" + "="*80)
        print("AUDIT 5: SCENARIO EVENT EFFECTS ANALYSIS")
        print("="*80)
        
        measurements = {}
        
        for idx, event in self.events_df.iterrows():
            event_id = event["event_id"]
            event_type = event["event_type"]
            field_impacted = event["field_impacted"]
            magnitude = event["magnitude"]
            start = pd.Timestamp(event["start_timestamp"])
            end = pd.Timestamp(event["end_timestamp"])
            affected_zones = event["affected_zones"].split(", ")
            
            if event_type == "normal_operations":
                continue
            
            print("\n{}: {}".format(event_id, event_type.upper()))
            print("  Description: {}".format(event['description']))
            print("  Impact field: {}, magnitude: {}".format(field_impacted, magnitude))
            print("  Time: {} to {}".format(start, end))
            
            event_data = {
                "event_id": event_id,
                "type": event_type,
                "field": field_impacted,
                "zones_affected": affected_zones,
                "measurements": []
            }
            
            for zone in affected_zones:
                zone_data = self.df[self.df["city_zone"] == zone].copy()
                zone_data["timestamp"] = pd.to_datetime(zone_data["timestamp"])
                
                before = zone_data[(zone_data["timestamp"] >= (start - timedelta(hours=6))) & (zone_data["timestamp"] < start)]
                during = zone_data[(zone_data["timestamp"] >= start) & (zone_data["timestamp"] < end)]
                after = zone_data[(zone_data["timestamp"] >= end) & (zone_data["timestamp"] < (end + timedelta(hours=6)))]
                
                if len(before) > 0 and len(during) > 0:
                    # Map field to data column
                    if field_impacted == "electricity_demand_mw":
                        col = "electricity_demand_mw"
                    elif field_impacted == "electricity_supply_mw":
                        col = "electricity_supply_mw"
                    elif field_impacted == "water_consumption_litres":
                        col = "water_consumption_litres"
                    elif field_impacted == "water_supply_litres":
                        col = "water_supply_litres"
                    elif field_impacted == "solar_generation_mw":
                        col = "solar_generation_mw"
                    elif field_impacted == "critical_service_demand":
                        col = "hospital_electricity_demand_mw"
                    elif field_impacted == "demand_baseline":
                        col = "electricity_demand_mw"
                    else:
                        col = None
                    
                    if col and col in zone_data.columns:
                        before_val = before[col].mean()
                        during_val = during[col].mean()
                        
                        # Calculate ratio change vs expected magnitude
                        if before_val > 0:
                            actual_ratio = during_val / before_val
                        else:
                            actual_ratio = 1.0
                        
                        after_val = after[col].mean() if len(after) > 0 else None
                        
                        meas = {
                            "zone": zone,
                            "before_avg": before_val,
                            "during_avg": during_val,
                            "actual_ratio": actual_ratio,
                            "expected_ratio": magnitude,
                            "ratio_error": abs(actual_ratio - magnitude),
                            "after_avg": after_val
                        }
                        
                        print("  {}:".format(zone))
                        print("    Before: {:.1f}, During: {:.1f}, Ratio: {:.2f} (expected: {})".format(
                            before_val, during_val, actual_ratio, magnitude))
                        if after_val is not None:
                            print("    After: {:.1f}".format(after_val))
                        
                        event_data["measurements"].append(meas)
            
            if event_data["measurements"]:
                measurements[event_id] = event_data
        
        self.measurements["scenario_effects"] = measurements
        
        # Summary
        print("\n\nSummary of {} measured events:".format(len(measurements)))
        ratio_errors = []
        for event_id, event in measurements.items():
            for meas in event["measurements"]:
                ratio_errors.append(meas["ratio_error"])
        
        if ratio_errors:
            avg_error = statistics.mean(ratio_errors)
            max_error = max(ratio_errors)
            print("  Average magnitude error: {:.3f}".format(avg_error))
            print("  Maximum magnitude error: {:.3f}".format(max_error))
    
    def run_audit(self):
        """Run all audit checks."""
        print("\n" + "="*80)
        print("SMART CITY DATA INTEGRITY AUDIT")
        print("="*80)
        print("Dataset: {}".format(SAMPLE_DATA_PATH))
        print("Records: {}".format(len(self.df)))
        print("Zones: {}".format(self.df['city_zone'].nunique()))
        print("Date range: {} to {}".format(self.df['timestamp'].min(), self.df['timestamp'].max()))
        
        self.audit_water_balance()
        self.audit_electricity_recovery()
        self.audit_heatwave_temperature_match()
        self.audit_solar_capacity_and_cloud_effects()
        self.audit_scenario_effects()
        
        # Final summary
        print("\n" + "="*80)
        print("AUDIT SUMMARY")
        print("="*80)
        
        if self.issues:
            print("\n[ERROR] Found {} issues:\n".format(len(self.issues)))
            for i, issue in enumerate(self.issues, 1):
                print("  {}. {}".format(i, issue))
        else:
            print("\n[OK] No critical issues found")
        
        return len(self.issues) == 0, self.measurements

if __name__ == "__main__":
    audit = DataAudit()
    success, measurements = audit.run_audit()
    
    # Save measurements
    with open("audit_measurements.json", "w") as f:
        json.dump(measurements, f, indent=2, default=str)
    print("\n\nMeasurements saved to audit_measurements.json")
    
    exit(0 if success else 1)

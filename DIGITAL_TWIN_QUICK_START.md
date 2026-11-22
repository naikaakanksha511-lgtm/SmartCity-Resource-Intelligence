# Digital Twin Quick Start Guide

## Getting Started (60 seconds)

### 1. Navigate to Digital Twin
Click **"◉ Digital Twin"** in the left sidebar

### 2. Select a Scenario
Choose from the dropdown:
- **Normal city operations** - Baseline (no events)
- **Heatwave crisis** - Heat spike, increased demand
- **Heatwave with intervention** - Heat spike + emergency response
- **Supply disruption** - Power outage with recovery

### 3. Adjust Settings (Optional)
- **Duration:** 1-72 hours (default: 24)
- **Time step:** 0.5-12 hours (default: 1 hour)
- **Start time:** Pick date/time (default: 2026-06-18 08:00)

### 4. Run Simulation
Click **"▶ Run simulation"** button

### 5. View Results
- **Severity timeline:** Shows emergency level progression
- **Risk score chart:** 0-100 risk scale over time
- **Zone summary:** Which zones affected and severity
- **Hour-by-hour:** Step through with ◀ Previous / Next ▶

### 6. Reset & Try Again
Click **"↻ Reset"** to start over

---

## Understanding the Results

### Severity Levels
🟢 **Normal** - No issues detected  
🟡 **Warning** - Resource stress detected  
🟠 **High** - Multiple stress signals  
🔴 **Critical** - Cascading failures risk  

### Risk Score (0-100)
- **0-25** - Minimal risk
- **25-50** - Moderate stress
- **50-75** - Significant concern
- **75-100** - Critical situation

### What the Charts Show
**Severity Timeline (Red):** Emergency level progression  
**Risk Timeline (Amber):** Overall city stress level  

---

## Scenario Descriptions

### Normal Operations
Stable city with no events. All zones operate normally.
- **What to expect:** Flat lines, no alerts
- **Why useful:** Baseline for comparison

### Heatwave Crisis
30% jump in electricity demand from 08:00-16:00.
- **What to expect:** Warning level during 8-hour window
- **What causes it:** Heat increases AC demand
- **Why useful:** See stress from external event

### Heatwave + Intervention
Same heatwave, but city responds with:
- 15% demand reduction in industrial zone
- 25 MW emergency power generation
- **What to expect:** Lower severity than scenario 2
- **Why useful:** Compare intervention effectiveness

### Supply Disruption
50% electricity capacity loss from 12:00-16:00.
- **What to expect:** High severity during outage, recovery after
- **Why useful:** See cascading impacts and recovery

---

## Tips & Tricks

### Compare Scenarios
1. Run scenario A, note the peak severity/risk
2. Click "Reset"
3. Run scenario B
4. Compare results (browser back/forward or memory)

### Customize Duration
- Want shorter preview? Use 6-hour simulation
- Want full day? Use default 24 hours
- Want detailed analysis? Use 0.5-hour steps (2x more detail)

### Understanding Zones
Zones show which city areas are affected:
- **Central District** - Business, high priority
- **North Residential** - Housing, medium priority
- **South Industrial** - Manufacturing, standard priority
- **Riverside** - Mixed use, medium priority

### Data Quality
⚠️ **All data is SIMULATED**
- Not connected to real city infrastructure
- Based on demonstration scenarios only
- Shows concepts, not predictions
- Used for learning and analysis

---

## Frequently Asked Questions

### Q: Why all normal in normal scenario?
**A:** That's correct! Normal scenario has no events, so severity stays at zero.

### Q: Why does severity spike in heatwave?
**A:** The 30% demand increase puts pressure on electricity system, triggering warning level (25-50 risk score).

### Q: Can I edit scenarios?
**A:** Not in this version. Use built-in scenarios or modify backend directly.

### Q: Does this predict real emergencies?
**A:** No. This is a demonstration system. Real prediction requires live data.

### Q: Why can't I pause simulation?
**A:** Pause feature not yet implemented. Reset and re-run with different duration.

### Q: What do affected zones mean?
**A:** Zones experiencing resource stress or alert conditions at that time step.

### Q: How often does it update?
**A:** One-hour time steps by default (adjustable in config).

### Q: Can multiple simulations run?
**A:** One at a time. Reset first to run another.

---

## Troubleshooting

### "Scenarios not loading"
✓ Wait a few seconds  
✓ Refresh page (F5)  
✓ Check browser console (F12) for errors  
✓ Ensure internet connection active  

### "Simulation fails with error"
✓ Read error message carefully  
✓ Try a different scenario  
✓ Check all inputs are valid  
✓ Refresh and try again  

### "Charts not showing"
✓ Wait for simulation to complete  
✓ Check simulation produced results  
✓ Zoom out if screen is small  
✓ Try a different browser  

### "Previous/Next buttons not working"
✓ Make sure simulation has completed  
✓ You're at start (◀ disabled) or end (▶ disabled)  

### "Mobile layout broken"
✓ Rotate phone to landscape  
✓ Zoom out in browser  
✓ Refresh page  

---

## Understanding the Assumptions Panel

Shows:
- **Scenario name:** Which scenario is running
- **Events applied:** Count of time-dependent events
- **Interventions applied:** Count of emergency responses
- **Simulation type:** Deterministic (always same result)
- **Cascading risks:** How failures cascade (e.g., electricity shortage → water shortage)
- **Data label:** Reminder that this is simulated

---

## Contact & Support

For questions about:
- **How scenarios work:** See Assumptions panel
- **API details:** Check backend documentation
- **Code changes:** Review commit history
- **New features:** File an issue/request

---

**Remember:** This is a demonstration system showing city emergency management concepts. All data is simulated and should not be used for real operational decisions.

**Status:** ✅ Ready to use  
**Last Updated:** December 2024

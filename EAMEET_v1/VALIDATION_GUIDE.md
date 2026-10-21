# EAMEET Simulation Validation Guide

## Overview

This guide explains how to validate the accuracy and reliability of your EAMEET simulation results using the standalone validation script.

The script validates two core simulation methods:

| Method | Simulation function | Tests performed |
|--------|-------------------|-----------------|
| **Bootstrap** | `extrapolation()` | Stability test, Sensitivity analysis |
| **Below-MDL** | `simulate_below_mdl()` | Stability test, Sensitivity analysis |

## What is Validation?

Validation tests whether your simulation results are:
- **Consistent**: Do multiple runs produce similar results?
- **Robust**: How sensitive are results to parameter changes?

## Quick Start

### Requirements

```bash
# Install dependencies (if not already installed)
pip install -r requirements.txt
```

### Basic Usage

```bash
# Run both bootstrap and below-MDL validation (default)
python validate_simulation.py emission_events.csv --start-date 2025-01-01 --end-date 2025-12-31
```

### Command-Line Options

```
python validate_simulation.py <csv_file> [options]

Required arguments:
  csv_file              Path to emission events CSV file
  -s, --start-date     Start date (YYYY-MM-DD)
  -e, --end-date       End date (YYYY-MM-DD)

Optional arguments:
  -i, --iterations     Number of validation runs for stability tests (default: 50)
  -o, --output         Output JSON file for results
  -m, --method         Validation method: bootstrap, below-mdl, or both (default: both)
  -t, --technology     Detection technology for below-MDL (default: Qube)
  --mdl                User-defined MDL value in kg/hr (float)
  --mc-iterations      Monte Carlo iterations per below-MDL run (default: 10)
```

### Examples

```bash
# Bootstrap only (backward compatible)
python validate_simulation.py emission_events.csv -s 2025-01-01 -e 2025-12-31 -i 50 -m bootstrap

# Below-MDL only with Qube technology
python validate_simulation.py emission_events.csv -s 2025-01-01 -e 2025-12-31 -i 5 -m below-mdl -t Qube --mc-iterations 5

# Both methods
python validate_simulation.py emission_events.csv -s 2025-01-01 -e 2025-12-31 -i 5 -m both --mc-iterations 5

# Save results to JSON
python validate_simulation.py emission_events.csv -s 2025-01-01 -e 2025-12-31 -m both -i 5 --mc-iterations 5 -o results.json

# Custom MDL value
python validate_simulation.py emission_events.csv -s 2025-01-01 -e 2025-12-31 -i 5 -m below-mdl --mdl 1.5 --mc-iterations 10
```

## Input Data Requirements

### CSV File Format

Required columns depend on the validation method:

| Column | Bootstrap | Below-MDL | Description |
|--------|-----------|-----------|-------------|
| `rate` | required | required | Emission rate (kg/hr) |
| `duration` | required | required | Event duration (hours) |
| `start_time` | -- | required | Event start timestamp (`YYYY-MM-DD HH:MM:SS`) |
| `end_time` | -- | required | Event end timestamp (`YYYY-MM-DD HH:MM:SS`) |
| `source` | -- | required | Site or source identifier |
| `quantity` | -- | required | Total emission quantity (kg) |

When `--method both` is used and the CSV is missing below-MDL columns, the script gracefully falls back to bootstrap-only with a warning.

### Example CSV

```csv
id,rate,duration,start_time,end_time,source,quantity
1,10.5,2.5,2025-01-15 10:00:00,2025-01-15 12:30:00,Site_A,26.25
2,15.2,1.8,2025-02-20 14:00:00,2025-02-20 15:48:00,Site_B,27.36
3,8.3,3.2,2025-03-10 09:00:00,2025-03-10 12:12:00,Site_A,26.56
```

## Validation Tests Performed

### 1. Bootstrap Stability Test

**Purpose**: Tests if the bootstrap simulation produces consistent results across multiple runs.

**Method**:
- Runs `extrapolation()` N times (where N = validation iterations, set by `-i`)
- Each run uses 1000 internal Monte Carlo iterations
- Calculates mean, standard deviation, and Coefficient of Variation (CV)

**Interpretation**:
- CV < 10%: EXCELLENT - Results are highly consistent (PASS)
- CV 10-20%: ACCEPTABLE - Some variation present (PASS)
- CV > 20%: POOR - High variation (FAIL)

**Example Output**:
```
1. BOOTSTRAP STABILITY TEST
======================================================================
Running 50 simulations with 1000 iterations each...
  Completed 10/50 runs...
  Completed 20/50 runs...
  ...

Results:
  Mean Emissions:     1234.56 kg
  Std Deviation:      98.76 kg
  Coefficient of Var: 8.0%

Interpretation: EXCELLENT - Results are highly consistent
Status: PASS
```

**What to do if it fails**:
- Increase Monte Carlo iterations in your simulation
- Check for data quality issues
- Ensure sufficient sample size (>20 events)

---

### 2. Bootstrap Sensitivity Analysis

**Purpose**: Measures how much bootstrap results change when input parameters are perturbed by 10%.

**Perturbations tested**:
- **Rates** -- all emission rates scaled by 1.1
- **Durations** -- all event durations scaled by 1.1
- **Probability of emission (POE)** -- POE multiplied by 1.1 (capped at 1.0)

**Example Output**:
```
2. SENSITIVITY ANALYSIS
======================================================================
Testing impact of 10% parameter changes...
  Testing rate sensitivity...
  Testing duration sensitivity...
  Testing probability sensitivity...

Results:
  Baseline Emissions: 1234.56 kg
  Rate Sensitivity:   10% increase in rates -> 9.8% change in emissions
  Duration Sensitivity: 10% increase in durations -> 10.2% change in emissions
  Probability Sensitivity: 10% increase in probability -> 5.1% change in emissions
```

**Interpretation**:
- Parameters with high sensitivity (>10% change) need careful measurement
- Parameters with low sensitivity (<5% change) are less critical
- Results should be roughly proportional to parameter changes

---

### 3. Below-MDL Stability Test

**Purpose**: Tests if the below-MDL simulation produces consistent results across multiple runs.

**Method**:
- Runs `simulate_below_mdl()` N times (where N = validation iterations, set by `-i`)
- Each run uses the MC iteration count set by `--mc-iterations`
- Tracks two metrics separately:
  - **Total emissions** (measured + unmeasured)
  - **Unmeasured emissions** only
- The overall CV is the **maximum** of the two CVs

**Interpretation**: Same thresholds as bootstrap stability:
- CV < 10%: EXCELLENT (PASS)
- CV 10-20%: ACCEPTABLE (PASS)
- CV > 20%: POOR (FAIL)

**Example Output**:
```
3. BELOW-MDL STABILITY TEST
======================================================================
Running 5 simulations with 10 MC iterations each...
Technology: Qube

Results:
  Total Emissions  - Mean: 2152308.62 kg, Std: 304151.06 kg, CV: 14.13%
  Unmeasured Only  - Mean: 2151080.64 kg, Std: 304151.06 kg, CV: 14.14%
  Overall CV (max): 14.14%

Interpretation: ACCEPTABLE - Some variation present
Status: PASS
```

**What to do if it fails**:
- Increase `--mc-iterations` (e.g., from 10 to 50 or 100)
- Increase `-i` for more validation runs
- Verify data quality in source/start_time/end_time columns

---

### 4. Below-MDL Sensitivity Analysis

**Purpose**: Measures how much below-MDL results change when input parameters are perturbed by 10%.

**Perturbations tested**:
- **Leak rates** -- component-level leak data scaled by 1.1
- **MDL threshold** -- technology MDL value increased by 10%, tested using `"User Defined"` technology with the perturbed MDL. Skipped if the baseline MDL cannot be determined.
- **Event durations** -- all durations scaled by 1.1; `quantity` is recalculated as `rate * perturbed_duration`

Leak data is passed explicitly to every call to avoid global state issues.

**Example Output**:
```
4. BELOW-MDL SENSITIVITY ANALYSIS
======================================================================
Testing impact of 10% parameter changes...
  Testing leak-rate sensitivity...
  Testing MDL-threshold sensitivity...
  Testing event-duration sensitivity...

Results:
  Baseline Total Emissions: 1982985.01 kg
  Leak-Rate Sensitivity:    10% increase in leak rates -> 45.4% change in emissions
  MDL-Threshold Sensitivity: 10% increase in MDL threshold -> -99.9% change in emissions
  Duration Sensitivity:     10% increase in event durations -> 33.0% change in emissions
```

---

## Supported Technologies and Default MDL Values

The below-MDL tests use a detection technology to determine the Probability of Detection (POD). The following technologies are supported with their default Minimum Detection Limits:

| Technology | MDL (kg/hr) |
|------------|-------------|
| InsightM | 10 |
| Qube | 2 |
| SeekOps | 0.02 |
| Bridger Photonic | 0.5 |
| GHGSat-Air | 13.6 |
| Kuva Systems | 3.5 |
| Sensirion | 3.6 |
| Aeromon | 0.1 |
| Project Canary | 0.2 |
| Long Path | 0.06 |

Pass `--mdl <value>` to override with a custom MDL.

---

## Overall Assessment

The script reports an overall PASS only if **all** stability tests that were run pass. If any stability test fails, the overall result is FAIL.

```
OVERALL ASSESSMENT
======================================================================
Bootstrap Stability Test: PASS
Below-MDL Stability Test: PASS
Assessment: PASS - Simulation is stable and consistent

Recommendation: Results are suitable for use. CV is within acceptable limits.
======================================================================
```

### Exit Codes

- **0**: All stability tests passed
- **1**: At least one stability test failed, or an error occurred

This allows integration into automated workflows:

```bash
python validate_simulation.py data.csv -s 2025-01-01 -e 2025-12-31 -m both --mc-iterations 10
if [ $? -eq 0 ]; then
    echo "Validation passed - proceeding with analysis"
else
    echo "Validation failed - review results"
fi
```

## Output Options

### Console Output

By default, results are printed to console with formatted output including:
- Progress indicators
- Detailed test results
- Status indicators
- Overall assessment and recommendations

### JSON Output

Use `-o` flag to save results to JSON file:

```bash
python validate_simulation.py data.csv -s 2025-01-01 -e 2025-12-31 -m both -o results.json
```

JSON structure:
```json
{
  "bootstrap_stability": {
    "test": "Bootstrap Stability",
    "mean_emissions": 1234.56,
    "std_emissions": 98.76,
    "cv": 8.0,
    "interpretation": "...",
    "status": "PASS"
  },
  "bootstrap_sensitivity": {
    "test": "Sensitivity Analysis",
    "baseline_emissions": 1234.56,
    "sensitivities": {
      "rate": { "change": 9.8, "interpretation": "..." },
      "duration": { "change": 10.2, "interpretation": "..." },
      "probability": { "change": 5.1, "interpretation": "..." }
    }
  },
  "below_mdl_stability": {
    "test": "Below-MDL Stability",
    "total_mean_emissions": 2152308.62,
    "total_std_emissions": 304151.06,
    "total_cv": 14.13,
    "unmeasured_mean_emissions": 2151080.64,
    "unmeasured_std_emissions": 304151.06,
    "unmeasured_cv": 14.14,
    "cv": 14.14,
    "interpretation": "...",
    "status": "PASS"
  },
  "below_mdl_sensitivity": {
    "test": "Below-MDL Sensitivity Analysis",
    "baseline_emissions": 1982985.01,
    "sensitivities": {
      "leak_rate": { "change": 45.4, "interpretation": "..." },
      "mdl_threshold": { "change": -99.9, "interpretation": "..." },
      "event_duration": { "change": 33.0, "interpretation": "..." }
    }
  },
  "overall": {
    "all_passed": true,
    "methods_run": {
      "bootstrap": true,
      "below_mdl": true
    },
    "assessment": "...",
    "recommendation": "..."
  }
}
```

## Backward Compatibility

All new parameters have defaults. The original invocation still works:

```bash
python validate_simulation.py events.csv -s 2025-01-01 -e 2025-12-31 -i 50
```

This defaults to `--method both`, which gracefully falls back to bootstrap-only if the CSV lacks below-MDL columns (`start_time`, `end_time`, `source`, `quantity`).

The `run_validation()` Python API also preserves its original positional signature; all new parameters are keyword-only with defaults.

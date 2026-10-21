# Event-based Annualized Emissions Estimation Toolkit (EAMEET) v1

A Dash-based web application for analyzing emission events and estimating total emissions using advanced simulation techniques.

## Features

- **Data Loading**: Upload CSV files with emission measurements
- **Emission Event Conversion**: Automatically convert measurements to emission events using Allen's Interval Algebra
- **Distribution Fitting**: Fit statistical distributions to rate and duration data
- **Duration Uncertainty Analysis**: Estimate duration uncertainty for intermittent emissions
- **Simulation Methods**:
  - Bootstrap simulation for unmeasured emissions
  - Below detection limit (MDL) simulation with multiple technology support
- **Results Visualization**: Compare results with bottom-up inventories

## Installation

1. Install required packages:
```bash
pip install -r requirements.txt
```

## Running the Application

1. Navigate to the EAMEET_v1 directory:
```bash
cd EAMEET_v1
```

2. Run the application:
```bash
python EAMEET_dash_app.py
```

3. Open your web browser and navigate to:
```
http://localhost:8050
```

## Usage Guide

### Step 1: Load Emissions Data
1. Upload your CSV file containing emission measurements
2. Map columns to required fields (ID, Rate, Time, Source)
3. Review converted emission events

### Step 2: Emissions Event Browser
1. View rate and duration distributions
2. Fit statistical distributions to your data
3. Configure emission characteristics (intermittent or continuous)
4. Estimate duration uncertainty if needed

### Step 3: Run Simulations
1. Select estimation approach:
   - **Bootstrap**: For unmeasured emissions extrapolation
   - **Below MDL**: For emissions below detection limit
2. Configure simulation parameters:
   - Start and end dates
   - Number of Monte Carlo iterations
   - Measurement technology
   - Wind considerations (optional)
3. Run simulation

### Step 4: View Results
1. Review total emissions with confidence intervals
2. Compare measured vs unmeasured emissions
3. Compare with bottom-up inventory (optional)

## Data Format

Your CSV file should contain at minimum:
- **ID**: Unique identifier for each measurement
- **Rate**: Emission rate (kg/hr)
- **Time**: Detection/measurement timestamp
- **Source**: Source location or identifier

Optional columns:
- **Cause**: Root cause or mechanism
- **Start Time**: Temporal bound start
- **End Time**: Temporal bound end
- **Uncertainties**: Measurement uncertainties
- **Observation Type**: Type of observation (e.g., "operation")
- **Observation Scale** (`observation_scale`): spatial scale of each observation, `component`, `equipment` or
  `site` (default: the dataset-level `source_scale`, i.e. `site`)
- **Feature** (`feature`): the physical source feature (equipment or component) an observation is attributed
  to, used to tell replicates of one emission from concurrent emissions of distinct features

### Combining the observations of one event (v1.0.2)

Observations merged into one event are integrated in time: the event bound is split at the start/end of
every observation with a measured interval; in each sub-interval replicates of the same feature are
combined by the chosen rate operation (average, lowest uncertainty, preference), distinct features at the
same scale are summed, and a coarser-scale measurement is combined with (never added to) the finer-scale
aggregate. Event quantity = sum(rate_i x dt_i); resolved rate = quantity / duration. Duplicate records are
collapsed, consecutive pieces of one measured record are merged, and the result does not depend on the
input order (`integrate_event`, `resolve_rate_at`; tests in `test_event_integration.py`; worked examples
in `worked_examples_merging.py`).

## Supported Technologies

The tool supports multiple detection technologies:
- InsightM
- Qube
- SeekOps
- Bridger Photonic
- GHGSat-Air
- Kuva Systems
- Sensirion
- Aeromon
- Project Canary
- Long Path
- User Defined (custom MDL)

## Troubleshooting

### Application won't start
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check that port 8050 is not in use

### File upload fails
- Ensure your CSV file is properly formatted
- Check that required columns are present
- Verify data types (rates should be numeric)

### Simulation errors
- Verify that start date is before end date
- Ensure emission events overlap with simulation period
- Check that all required parameters are provided

## Technical Details

### Emission Event Conversion
Uses Allen's Interval Algebra to merge overlapping emission events from the same source. Events are classified as:
- **RE (Resolved Events)**: Events with observation_type = "operation"
- **PRE (Partially Resolved Events)**: Events with other observation types

### Simulation Methods

**Bootstrap Simulation**:
- Samples from rate and duration distributions
- Simulates unmeasured events as an alternating renewal process: event durations from the duration
  distribution, inter-event gaps exponential with mean calibrated so the simulated fraction of time
  emitting equals the prescribed event occupancy (total event duration / observation period)
- Supports fitted distributions for improved accuracy

**Below MDL Simulation**:
- Simulates emissions below detection limit
- Supports multiple technologies (emission detected if ANY technology detects)
- Can incorporate wind speed effects
- Uses component-level leak data

### Event Occupancy from Detection Records

When occupancy for the bootstrap simulation has to be estimated from a screening record of
*k* detections in *m* observation attempts (for example Carbon Mapper "persistence", which is
detection dates / observation dates), the raw ratio *k/m* is biased: an emitting source is detected
only with probability POD < 1, *m* is often small, and source lists usually contain only sources
with at least one detection. `occupancy.py` provides a corrected estimate:

- `fit_occupancy_prior(k, m, pod)` fits a Beta population prior across all listed sources by
  empirical Bayes, using a binomial likelihood truncated at *k* >= 1 so the selection is corrected
  at the population level
- `occupancy_posterior(k, m, pod, prior)` returns a source's posterior occupancy on a grid with
  mean, median and 2.5/97.5 percentiles
- `sample_occupancy(...)` draws occupancy values for use inside a Monte Carlo ensemble

```python
from occupancy import fit_occupancy_prior, occupancy_posterior
prior = fit_occupancy_prior(k_all, m_all, pod=0.9)        # all listed sources
grid, pdf, summary = occupancy_posterior(2, 8, 0.9, prior)  # one source: 2 detections in 8 attempts
phi = summary["mean"]                                       # pass as prob_dist={"UNKNOWN": phi}
```

POD is the per-attempt probability that an emitting source is detected; if it is unknown, report a
sensitivity over plausible values. See `test_occupancy.py` and the Case Study 1 notebook.

### Duration Uncertainty
- Estimates duration using leak production rate and repair rate
- Monte Carlo simulation for uncertainty quantification
- Provides 95% confidence intervals

## Contact

For questions, issues, or commercial licensing:
- Email: mozhou.gao@ucalgary.ca

## License

This software is provided exclusively for academic research and educational purposes.
Unauthorized commercial use, distribution, or modification is prohibited.

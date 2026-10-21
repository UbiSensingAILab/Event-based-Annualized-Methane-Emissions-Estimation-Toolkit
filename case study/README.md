# Case Studies: Emission Estimation Using Emission Events

This directory contains case studies demonstrating the process of estimating emissions using emission events. The case studies showcase different approaches to converting emission observations into emission events and estimating total emissions with uncertainty quantification.

More details about this study can be found in Gao et al., 2025.

## Overview

The case studies demonstrate:
- Conversion of emission observations to emission events
- Temporal and spatial event merging using Allen's Interval Algebra
- Uncertainty quantification for resolved (RE), partially resolved (PRE), and unresolved (UE) events
- Comparison with bottom-up inventories (Global Fuel Exploitation Inventory - GFEI)
- Integration of Carbon Mapper satellite data

## Directory Structure

```
case study/
├── Notebooks/
│   ├── Case_study_No1.ipynb                    # Case Study 1: Carbon Mapper data analysis
│   ├── Results_compare_for_case_study_No1.ipynb # Case Study 1: Results comparison with GFEI
│   ├── cs1_joint_ensemble.py                   # Case Study 1: joint Monte Carlo ensemble engine + dependence tests
├── Input Data/
│   ├── CM_sources.json                         # Carbon Mapper sources (GeoJSON)
│   ├── CM_plumes.csv                           # Carbon Mapper plume detections
│   ├── CM_emission_events.csv                  # Carbon Mapper emission events
│   ├── Global_Fuel_Exploitation_Inventory_v3_2020_Oil_All.nc   # download; see repository README
│   ├── Global_Fuel_Exploitation_Inventory_v3_2020_Gas_All.nc   # download; see repository README
│   ├── Global_Fuel_Exploitation_Inventory_Oil_All_rsd.nc       # GFEI v1.0 oil relative standard deviation
│   ├── Global_Fuel_Exploitation_Inventory_Gas_All_rsd.nc       # GFEI v1.0 gas relative standard deviation
│   ├── cs1_gfei.py                                             # loads the four files, oil+gas totals and uncertainty
│   └── shapefiles/                             # Geographic boundary files
│       ├── Boundary_PermianBasin_StudyArea_NAD27.*  # Permian Basin study area
│       └── Boundary_State_NAD27.*              # State boundaries
└── Output Data/
    ├── emission_events_case_study_2.csv        # Emission events for Case Study 2
    └── total_emissions.csv                     # Total emissions estimates with uncertainties

```

## Case Study 1: Carbon Mapper Satellite Data Analysis

### Description
This case study demonstrates the analysis of real-world satellite data from Carbon Mapper, converting plume detections into emission events and comparing results with the Global Fuel Exploitation Inventory (GFEI).

### Notebooks

#### `Case_study_No1.ipynb`
- **Purpose**: Processes Carbon Mapper satellite data to create emission observations and events
- **Key Steps**:
  1. Loads Carbon Mapper sources and plumes from JSON and CSV files
  2. Joins plume and source data to create emission observations
  3. Converts observations to emission events
  4. Analyzes event characteristics (rates, durations, uncertainties)
- **Input Files**:
  - `CM_sources.json` - Carbon Mapper source locations and metadata
  - `CM_plumes.csv` - Carbon Mapper plume detection data
  - `CM_emission_events.csv` - Pre-processed emission events
- **Output**: Emission events with resolved (RE) and partially resolved (PRE) classifications

#### `cs1_joint_ensemble.py`
- **Purpose**: Joint Monte Carlo ensemble of the Case Study 1 cohort total (imported by `Case_study_No1.ipynb`). In every
  iteration the plume quantification errors (optionally shared within platform-day and/or by a platform-wide bias), the
  event rates, optionally detection-conditioned event durations, the bootstrap-refit Weibull UE distributions, each
  source's occupancy and the renewal UE draws are sampled before PRE + UE are summed over all sources. The central
  estimate and 95% interval are percentiles of the ensemble of totals (never sums of component medians or bounds).
- **Dependence tests**: `run_dependence_tests()` writes `cs1_outputs/cs1_dependence_tests.{csv,md}` (variants A-J).
- **Run**: `python cs1_joint_ensemble.py [n_outer_headline] [n_outer_tests]` from this folder.

#### `Results_compare_for_case_study_No1.ipynb`
- **Purpose**: Compares emission estimates with bottom-up inventory (GFEI)
- **Key Steps**:
  1. Loads emission event results from Case Study 1
  2. Loads Global Fuel Exploitation Inventory (GFEI) data
  3. Processes geographic boundaries (Permian Basin study area)
  4. Creates spatial comparisons and visualizations
  5. Generates comparison plots between top-down (event-based) and bottom-up (inventory) estimates
- **Input Files**:
  - `CM_emission_events.csv` - Emission events from Case Study 1
  - GFEI v3.0 oil and gas sector files and GFEI v1.0 rsd files (see Input Data Files)
  - `shapefiles/Boundary_PermianBasin_StudyArea_NAD27.shp` - Study area boundary
  - `shapefiles/Boundary_State_NAD27.shp` - State boundaries
- **Output**: Comparison visualizations and analysis

### Input Data Files

#### Carbon Mapper Data
- **`CM_sources.json`**: GeoJSON file containing Carbon Mapper source locations with properties:
  - Source coordinates (latitude, longitude)
  - Plume IDs and counts
  - Observation scene names
  - Persistence metrics
  - Emission rates and uncertainties
  - Timestamp ranges

- **`CM_plumes.csv`**: CSV file containing individual plume detections with:
  - Plume IDs
  - Emission rates (`emission_auto`)
  - Emission uncertainties (`emission_uncertainty_auto`)
  - Detection timestamps

- **`CM_emission_events.csv`**: Pre-processed emission events derived from Carbon Mapper data

#### Global Fuel Exploitation Inventory (GFEI)
- **`Global_Fuel_Exploitation_Inventory_v3_2020_Oil_All.nc`** and **`..._Gas_All.nc`**: GFEI v3.0 (2020) oil and gas sector
  emissions (IPCC 1B2; Scarpelli et al., 2025), Mg a⁻¹ km⁻² on the 0.1° grid, converted to kg per cell with the `area`
  variable. These two files are not in the repository. Download them from
  [doi:10.7910/DVN/HH4EUM](https://doi.org/10.7910/DVN/HH4EUM) into this folder (direct links are in the repository README).
  The comparison uses their sum; the total-fuel-exploitation product is no longer used.
- **`Global_Fuel_Exploitation_Inventory_Oil_All_rsd.nc`** and **`..._Gas_All_rsd.nc`**: per-cell relative standard
  deviations of the GFEI v1.0 (2016) sector inventories (Scarpelli et al., 2020). GFEI v3.0 ships no uncertainty layer, so
  these are applied to the v3.0 sector emissions (`cs1_gfei.py`, emission-weighted over cells and sectors).

#### Geographic Data
- **`shapefiles/`**: Contains shapefiles for geographic boundaries
  - `Boundary_PermianBasin_StudyArea_NAD27.*` - Permian Basin study area boundary
  - `Boundary_State_NAD27.*` - State boundaries (NAD27 coordinate system)

## Case Study 2: Synthetic Multi-Scale Observations

### Description
This case study demonstrates the emission event framework using synthetic multi-scale emission observations, including different measurement technologies and temporal resolutions.

### Notebooks

#### `Case_study_No2_redone.ipynb`
- **Purpose**: Builds the Site A events from `Data_from_case_study_2.xlsx`, infers the flyover PRE duration, runs the Type 1 and Type 2 UE simulations and writes `cs2_outputs/` (results summary, Figure 6 and 7 panels).

### Input Data Files

- **`Data_from_case_study_2.xlsx`**: Synthetic multi-scale observations of Site A (CMS alarms, flyover and OGI surveys, operational venting records; SI Tables S3–S6), read by `Case_study_No2_redone.ipynb`.

### Output Data Files

- **`emission_events_case_study_2.csv`**: Emission events converted from observations with:
  - Event IDs (UUIDs)
  - Rates, durations, and quantities
  - Source locations
  - Start and end times
  - Merged observation IDs
  - Event types (RE, PRE, UE)
  - Uncertainty values

- **`total_emissions.csv`**: Aggregated emission estimates with:
  - Source identifiers
  - Partially resolved event emissions (PRE) with uncertainty bounds
  - Unresolved event emissions (UE) with uncertainty bounds
  - Total emissions with lower and upper bounds

## Shared Data Files

The component-level leak-rate sample (`sample_leak_rate.csv`, Rutherford et al., 2021; g/s, converted to kg/h by the toolkit) and the ERA5 wind file (`weather_permian.nc`) live in `../EAMEET_v1/` and are loaded from there by the toolkit; the case-study folder no longer keeps copies.

## Event Classifications

The case studies classify emission events into three categories:

1. **Resolved Events (RE)**: Events with both rate and duration fully observed
   - Complete temporal and quantitative information
   - Lower uncertainty compared to PRE and UE

2. **Partially Resolved Events (PRE)**: Events with rate observed but duration uncertain
   - Rate information available
   - Duration estimated using Leak Production Rate (LPR) and Non-Repair Rate (NRR)
   - Moderate uncertainty

3. **Unresolved Events (UE)**: Events not directly observed
   - Estimated using bootstrap methods or component-level leak data
   - Highest uncertainty
   - Critical for comprehensive emission inventories

## Dependencies

The notebooks require the following Python packages (see `../EAMEET_v1/requirements.txt`):
- `pandas` - Data manipulation
- `numpy` - Numerical computing
- `scipy` - Statistical distributions
- `matplotlib` - Plotting
- `netCDF4` - NetCDF file reading
- `cartopy` - Geographic projections and mapping
- `geopandas` - Geographic data processing
- `xarray` - Multi-dimensional arrays
- `rasterio` - Geospatial raster I/O
- `shapely` - Geometric operations

Additionally, the notebooks import modules from the main EAMEET application:
- `simulations` - Simulation functions
- `utils` - Utility functions
- `emission_event_converter` - Event conversion logic

## Usage

1. **Navigate to the case study directory**:
   ```bash
   cd "case study"
   ```

2. **Ensure dependencies are installed**:
   ```bash
   cd ../EAMEET_v1
   pip install -r requirements.txt
   ```

3. **Run notebooks in order**:
   - For Case Study 1: Start with `Case_study_No1.ipynb`, then `Results_compare_for_case_study_No1.ipynb`
   - For Case Study 2: Use `Case_study_No2_redone.ipynb` (events, duration model, UE simulations and Figure 7)

4. **Note**: Some notebooks may reference data files that need to be generated by previous steps or the main EAMEET application.

## Key Results

The case studies demonstrate:
- Successful conversion of multi-scale observations to emission events
- Temporal merging using Allen's Interval Algebra
- Uncertainty quantification across event types
- Comparison with bottom-up inventories (GFEI)
- Integration of satellite data (Carbon Mapper) with ground-based observations

## Citation

If you use these case studies in your research, please cite:

Gao et al., 2025 (DOI to be added)

## References

- Rutherford et al., 2021 - Component-level leak rate datasets
- Carbon Mapper - Satellite methane detection data
- Global Fuel Exploitation Inventory (GFEI) - Bottom-up emission inventory
- ERA5 - Weather reanalysis data

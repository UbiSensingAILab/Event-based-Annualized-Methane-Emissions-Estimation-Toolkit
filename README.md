# Event-based Annualized Emission Estimation Toolkit (EAMEET)

A comprehensive web-based toolkit for estimating emissions using emission events. This application provides an interactive interface for converting emission observations to emission events, running Monte Carlo simulations, and analyzing emission data with uncertainty quantification.


## Overview

The Event-based Annualized Emission Estimation Toolkit (EAMEET) is designed to help researchers and analysts:

- Convert emission observations into structured emission events
- Merge events using temporal and spatial relationships (Allen's Interval Algebra)
- Simulate emissions below detection limits
- Bootstrap emissions from unmeasured events
- Quantify uncertainties in emission estimates
- Visualize results with interactive charts and Sankey diagrams

More details about this study can be found in Gao et al., 2025.

## Features

### Core Functionality

1. **Data Loading & Mapping**
   - Upload CSV/Excel files with emission observations
   - Interactive column mapping interface
   - Data validation and quality checks

2. **Emission Event Conversion**
   - Convert observations to emission events using UML model structure
   - Support for intermittent and continuous emission characteristics
   - Temporal event merging using Allen's Interval Algebra
   - Spatial correlation handling

3. **Uncertainty Estimation**
   - Duration uncertainty simulation for partially resolved events
   - Rate uncertainty quantification
   - Leak Production Rate (LPR) and Non-Repair Rate (NRR) integration

4. **Simulation Capabilities**
   - **Simulate Below Detection Limit**: Estimates emissions below MDL using component-level leak data
   - **Bootstrap For Unmeasured Emissions**: Extrapolates emissions from measured events
   - Monte Carlo iterations with parallel processing
   - Wind condition consideration (optional)
   - Custom component-level leak data upload

5. **Visualization & Analysis**
   - Interactive Sankey diagrams showing observation-to-event flow
   - Emission event tables with filtering
   - Distribution histograms
   - Results comparison charts
   - Bottom-up inventory comparison

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd Emission-Estimation-Using-Emission-Events
```

2. Navigate to the application directory:
```bash
cd EAMEET_v1
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

### Required Packages

- `dash>=2.14.0` - Web framework
- `pandas>=1.5.0` - Data manipulation
- `numpy>=1.23.0` - Numerical computing
- `scipy>=1.9.0` - Scientific computing
- exact versions used for the manuscript: `EAMEET_v1/requirements-lock.txt`; release `EAMEET_v1/version.py`; run order `EAMEET_v1/RUNBOOK.md`
- `plotly>=5.14.0` - Interactive visualizations
- `netCDF4>=1.6.0` - For wind data support (NetCDF file reading)

## Usage

### Running the Application

1. Start the Dash application:
```bash
cd EAMEET_v1
python EAMEET_dash_app.py
```

2. Open your web browser and navigate to:
```
http://localhost:8050
```

### Workflow

1. **Load Emissions Data**
   - Upload your emission observation data (CSV or Excel)
   - Map columns to required fields (ID, Rate, Time, Source)
   - Review and validate the data

2. **Create Emission Events**
   - Convert observations to emission events
   - Review the converted events table
   - View the Sankey diagram showing observation-to-event relationships

3. **Configure Emission Characteristics**
   - Select whether emissions are intermittent or continuous
   - For continuous emissions: specify producing hours
   - Optionally simulate duration uncertainty

4. **Run Simulations**
   - Select estimation approach:
     - **Simulate Below Detection Limit**: Requires measurement technology, MDL, and optional wind data
     - **Bootstrap For Unmeasured Emissions**: Uses rate and duration distributions from events
   - Configure simulation parameters:
     - Processing resolution (by site, by site and source, by site and equipment)
     - Start and end dates
     - Number of Monte Carlo iterations
   - Upload custom component-level leak data (optional)
   - Upload custom wind speed data (optional, for below MDL approach)

5. **Review Results**
   - View simulation results with uncertainty bounds
   - Compare with bottom-up inventory (optional)
   - Export results as CSV or JSON

## Project Structure

```
Emission-Estimation-Using-Emission-Events/
├── EAMEET_v1/                          # Main application directory
│   ├── EAMEET_dash_app.py              # Main Dash application
│   ├── components.py                  # UI components and layout
│   ├── emission_event_converter.py    # Event conversion logic
│   ├── simulations.py                  # Simulation functions
│   ├── utils.py                       # Utility functions
│   ├── requirements.txt               # Python dependencies
│   ├── sample_leak_rate.csv          # Default leak rate data
│   └── weather_permian.nc            # Default wind data (NetCDF)
├── case study/                        # Case study notebooks and data
│   ├── README.md                      # Case study documentation
│   ├── *.ipynb                        # Jupyter notebooks
│   ├── *.csv                          # Data files
│   └── *.xlsx                         # Sample data files
├── LICENSE                            # GPL v3 License
└── README.md                          # This file
```

## Key Modules

### `EAMEET_dash_app.py`
Main application file containing:
- Dash app initialization
- Callback functions for user interactions
- Data processing and validation
- Results handling

### `components.py`
UI components including:
- Navigation bar
- Section layouts (Data Investigation, Simulations, Results, Uncertainty Calculator)
- Modal dialogs
- Charts and tables

### `emission_event_converter.py`
Core conversion logic:
- Converts observations to emission events
- Implements Allen's Interval Algebra for temporal merging
- Handles spatial correlation
- Supports intermittent and continuous emissions

### `simulations.py`
Simulation functions:
- `simulate_below_mdl()`: Estimates emissions below detection limit
- `extrapolation()`: Bootstrap simulation for unmeasured emissions
- `simulate_duration_uncertainty()`: Duration uncertainty simulation
- Parallel processing support for large iterations

### `utils.py`
Utility functions:
- Distribution fitting (lognormal, normal, uniform, exponential, Weibull, gamma)
- Quantification and duration corrections
- Probability of detection calculations

## Case Studies

The repository includes two case studies demonstrating different use cases:

### Case Study 1
- **Input**: 146 synthetic emission observations (CMS, flyover, OGI, venting)
- **Notebooks**:
  - `Emission_observations_to_emission_events_case_study_1.ipynb`: Event creation
  - `Estimate_duration_and_rate_uncertainty_for_PRE_case_study_1.ipynb`: Uncertainty estimation
  - `Emissions_from_unresolved_events_case_study_1.ipynb`: Unresolved events simulation
  - `Event_sankey_diagram_case_study_1.ipynb`: Visualization
  - `Plot_results_case_study_1.ipynb`: Results plotting

### Case Study 2
- **Input**: 36 synthetic CMS observations
- **Notebooks**:
  - `Bootstrap_unresolved_events_case_study_2.ipynb`: Bootstrap simulation
  - `Plot_results_case_study_2.ipynb`: Results plotting

See `case study/README.md` for detailed documentation.

## NetCDF data

Two GFEI v3.0 (2020) inventory files are too large to store in this repository. Download them from the Harvard Dataverse release of the Global Fuel Exploitation Inventory (Scarpelli et al., 2025), [doi:10.7910/DVN/HH4EUM](https://doi.org/10.7910/DVN/HH4EUM), and save them in `case study/` under these names:

| File | Direct download |
| --- | --- |
| `case study/Global_Fuel_Exploitation_Inventory_v3_2020_Oil_All.nc` | https://dataverse.harvard.edu/api/access/datafile/11828683 |
| `case study/Global_Fuel_Exploitation_Inventory_v3_2020_Gas_All.nc` | https://dataverse.harvard.edu/api/access/datafile/11828512 |

`cs1_gfei.py` reads those paths when comparing Case Study 1 with the inventory. The smaller relative-standard-deviation files and `EAMEET_v1/weather_permian.nc` are already in the repository.

## Data Requirements

### Input Data Format

Your emission observation data should include:
- **ID**: Unique identifier for each observation
- **Rate**: Emission rate (kg/hr)
- **Time/Timestamp**: When the observation was made
- **Source**: Source location or identifier
- **Source Scale**: Site, equipment, or component level
- **Optional**: Cause, duration, emission characteristics

### Component-Level Leak Data

For "Simulate Below Detection Limit" approach:
- CSV file with leak rates in kg/hr
- One column containing leak rate values
- Default sample data provided (`sample_leak_rate.csv`)

### Wind Data

For wind-aware simulations:
- NetCDF file with wind speed data (u10, v10 components)
- Or CSV file with wind speed column (m/s)
- Default weather data provided (`weather_permian.nc`)

## Simulation Approaches

### 1. Simulate Below Detection Limit

Estimates emissions that occur below the minimum detection limit of measurement technologies.

**Required Parameters:**
- Measurement technology (InsightM, Qube, SeekOps, Bridger Photonic, or custom MDL)
- Component-level leak data (default or user-uploaded)
- Optional: Wind speed data

**Output:**
- Total emissions (measured + unmeasured) with uncertainty bounds

### 2. Bootstrap For Unmeasured Emissions

Extrapolates emissions from measured events using bootstrap resampling.

**Required Parameters:**
- Rate and duration distributions from emission events
- Processing resolution
- Number of Monte Carlo iterations

**Output:**
- Extrapolated emissions with uncertainty bounds

## Features & Capabilities

- ✅ Interactive web interface
- ✅ CSV and Excel file upload
- ✅ Column mapping interface
- ✅ Temporal event merging (Allen's Interval Algebra)
- ✅ Spatial correlation handling
- ✅ Monte Carlo simulations with parallel processing
- ✅ Wind condition consideration
- ✅ Custom leak data upload
- ✅ Custom wind data upload
- ✅ Uncertainty quantification
- ✅ Interactive visualizations (Sankey diagrams, charts)
- ✅ Results export (CSV, JSON)
- ✅ Bottom-up inventory comparison

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0). See the [LICENSE](LICENSE) file for details.

## Citation

If you use this toolkit in your research, please cite:

Gao et al., 2025 (DOI to be added)

## Contributing

This software is provided for academic research and educational purposes. Contributions and improvements are welcome.

## Support

For questions, issues, or contributions, please refer to the case study documentation or contact the authors.

## Disclaimer

This software is provided exclusively for academic research and educational purposes. It is not licensed for commercial use, operational deployment, or regulatory compliance without explicit written agreement.

---

**Note**: Make sure you have all required dependencies installed before running the application. All dependencies, including `netCDF4` for wind data functionality, are included in `requirements.txt`.


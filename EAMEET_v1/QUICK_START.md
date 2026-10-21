# EAMEET v1 Quick Start Guide

## Installation

1. **Navigate to the EAMEET_v1 directory:**
   ```bash
   cd EAMEET_v1
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   
   **Note:** If `netCDF4` fails to install (common on Windows), that's okay - it's only needed for optional weather data features.

## Running the Application

1. **Start the application:**
   ```bash
   python EAMEET_dash_app.py
   ```

2. **Open your browser:**
   Navigate to: `http://localhost:8050`

3. **You should see:**
   - The Emission Event Data Analysis Tool interface
   - Navigation tabs at the top
   - User guide and instructions

## Basic Workflow

### Step 1: Load Your Data
1. Click "Load Emissions Data" tab (should be active by default)
2. Upload your CSV file (drag & drop or click to select)
3. Click "Map Columns to Required Format"
4. Map your columns to the required fields:
   - **ID** (required): Unique identifier
   - **Rate** (required): Emission rate in kg/hr
   - **Time** (required): Detection/measurement timestamp
   - **Source** (required): Source location/identifier
   - Optional: Cause, Start Time, End Time, Uncertainties, Observation Type
5. Click "Process Data"
6. Review the converted emission events

### Step 2: Explore Your Data
1. Click "Emissions Event Browser" tab
2. View rate and duration distributions
3. Optionally fit statistical distributions
4. Configure emission characteristics:
   - **Intermittent**: Events occur sporadically
   - **Continuous**: Events occur continuously
5. If needed, estimate duration uncertainty

### Step 3: Run Simulation
1. Click "Simulations" tab
2. Select estimation approach:
   - **Bootstrap**: For extrapolating unmeasured emissions
   - **Below MDL**: For emissions below detection limit
3. Configure parameters:
   - Start and end dates (auto-populated from your data)
   - Number of Monte Carlo iterations (1-100)
   - Measurement technology
   - Wind considerations (optional)
4. Click "Run Simulation"
5. Wait for completion (time depends on iterations)

### Step 4: View Results
1. Click "Results" tab
2. Review:
   - Total emissions (measured + unmeasured)
   - 95% confidence intervals
   - Breakdown of measured vs unmeasured
3. Optionally compare with bottom-up inventory

## Example Data Format

Your CSV should look like this:

```csv
id,rate,time,source,cause
1,10.5,2024-01-01 10:00:00,Site A,Equipment leak
2,0,2024-01-02 10:00:00,Site A,
3,15.2,2024-01-03 10:00:00,Site B,Valve failure
4,0,2024-01-04 10:00:00,Site B,
5,8.3,2024-01-05 10:00:00,Site A,Unknown
```

**Key points:**
- Rate of 0 indicates non-detection
- Timestamps should be parseable (YYYY-MM-DD HH:MM:SS recommended)
- Sources identify where emissions occur
- Causes are optional

## Supported Technologies

When using "Below MDL" simulation, you can select from:
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
- Define Technology (custom MDL)

You can select **multiple technologies** - an emission is detected if ANY technology detects it.

## Troubleshooting

### Application won't start
- **Check Python version:** Python 3.8+ required
- **Install dependencies:** `pip install -r requirements.txt`
- **Port conflict:** If port 8050 is in use, the app will show an error

### File upload fails
- **Check file format:** Must be CSV
- **Check encoding:** UTF-8 recommended
- **Check file size:** Very large files may take time to process

### Column mapping errors
- **Required fields:** ID, Rate, Time, and Source are mandatory
- **Data types:** Rate must be numeric
- **Column names:** Case-sensitive, make sure to select correct columns

### Simulation errors
- **Date range:** Start date must be before end date
- **Event overlap:** Events must overlap with simulation period
- **Technology selection:** At least one technology must be selected for Below MDL

### Results not showing
- **Run simulation first:** Must complete Step 3 before viewing results
- **Check for errors:** Look for error messages in the Simulation tab

## Tips for Best Results

1. **Data Quality:**
   - Include both detections (rate > 0) and non-detections (rate = 0)
   - More data points = better distribution fitting
   - Accurate timestamps improve temporal analysis

2. **Distribution Fitting:**
   - Try different distribution types
   - Lognormal often works well for emission rates
   - Visual inspection helps validate fit

3. **Simulation Parameters:**
   - Start with fewer iterations (10-20) for testing
   - Increase iterations (50-100) for final results
   - More iterations = more accurate but slower

4. **Wind Considerations:**
   - Use wind data if available for better accuracy
   - Default values work if wind data unavailable
   - Wind affects detection probability for some technologies

## Getting Help

If you encounter issues:
1. Check the DEBUG_REPORT.md for known issues
2. Review error messages carefully
3. Contact: mozhou.gao@ucalgary.ca

## Next Steps

After getting familiar with the basic workflow:
- Experiment with different simulation approaches
- Try fitting different distributions
- Compare results with bottom-up inventories
- Explore duration uncertainty analysis

---

**Happy analyzing! 🎉**

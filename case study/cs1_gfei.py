"""
GFEI v3.0 oil and gas sector inventory and its relative uncertainty for the Case Study 1 comparison.

Emissions: GFEI v3.0 (2020) sector files Oil_All + Gas_All (IPCC 1B2; Scarpelli et al., 2025), kg per 0.1 degree cell.
Uncertainty: GFEI v3.0 ships no uncertainty layer, so the per-cell relative standard deviations (rsd) of the GFEI v1.0
(2016) sector files Oil_All_rsd and Gas_All_rsd are used (Scarpelli et al., 2020). Under the assumption that the cell
errors are fully correlated (activity-data and emission-factor errors shared across the region and across the two
sectors), the standard deviation of a regional total is the sum of the per-cell, per-sector standard deviations, so the
relative standard deviation of the total is the emission-weighted mean of the per-cell rsd over both sectors.
"""
import os
import numpy as np
import netCDF4 as nc

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = {
    "oil": "Global_Fuel_Exploitation_Inventory_v3_2020_Oil_All.nc",
    "gas": "Global_Fuel_Exploitation_Inventory_v3_2020_Gas_All.nc",
    "oil_rsd": "Global_Fuel_Exploitation_Inventory_Oil_All_rsd.nc",
    "gas_rsd": "Global_Fuel_Exploitation_Inventory_Gas_All_rsd.nc",
}
VARS = {"oil": "Oil_All", "gas": "Gas_All", "oil_rsd": "rsd", "gas_rsd": "rsd"}


def _read(key, here=HERE):
    path = os.path.join(here, FILES[key])
    if not os.path.exists(path):
        raise FileNotFoundError(f"{FILES[key]} not found in {here} (GFEI {'v1.0 relative-uncertainty' if 'rsd' in key else 'v3.0 sector'} file)")
    d = nc.Dataset(path)
    lat = np.asarray(d.variables["lat"][:], float); lon = np.asarray(d.variables["lon"][:], float)
    a = np.ma.filled(d.variables[VARS[key]][:], np.nan)
    area = np.ma.filled(d.variables["area"][:], np.nan) if "area" in d.variables else None
    d.close()
    return lat, lon, a, area


def load_gfei(here=HERE):
    """Returns dict(lat, lon, kg_oil, kg_gas, kg (oil+gas), rsd_oil, rsd_gas); arrays on the 0.1 degree grid, kg per cell."""
    lat, lon, oil, area = _read("oil", here)
    _, _, gas, _ = _read("gas", here)
    kg_oil = np.nan_to_num(oil) * 1000.0 * area * 1e-6          # Mg a-1 km-2 -> kg a-1 per cell
    kg_gas = np.nan_to_num(gas) * 1000.0 * area * 1e-6
    _, _, rsd_oil, _ = _read("oil_rsd", here)
    _, _, rsd_gas, _ = _read("gas_rsd", here)
    assert rsd_oil.shape == oil.shape == rsd_gas.shape, "GFEI v1.0 rsd grids must match the v3.0 grid"
    return dict(lat=lat, lon=lon, kg_oil=kg_oil, kg_gas=kg_gas, kg=kg_oil + kg_gas,
                rsd_oil=np.nan_to_num(rsd_oil), rsd_gas=np.nan_to_num(rsd_gas))


def total_cv(g, mask):
    """Relative standard deviation of the oil+gas total over `mask` (boolean array on the same sub-grid as the kg
    arrays passed in g) for fully correlated cell and sector errors, plus the alternatives printed for reference."""
    E = g["kg_oil"][mask].sum() + g["kg_gas"][mask].sum()
    sd_oil = (g["kg_oil"][mask] * g["rsd_oil"][mask]).sum(); sd_gas = (g["kg_gas"][mask] * g["rsd_gas"][mask]).sum()
    return dict(
        fully_correlated=(sd_oil + sd_gas) / E,                               # adopted
        sectors_independent=np.sqrt(sd_oil ** 2 + sd_gas ** 2) / E,           # cells correlated within a sector, sectors independent
        cells_independent=np.sqrt(((g["kg_oil"][mask] * g["rsd_oil"][mask]) ** 2).sum()
                                  + ((g["kg_gas"][mask] * g["rsd_gas"][mask]) ** 2).sum()) / E,
        cv_oil=sd_oil / g["kg_oil"][mask].sum(), cv_gas=sd_gas / g["kg_gas"][mask].sum(),
        share_oil=g["kg_oil"][mask].sum() / E)

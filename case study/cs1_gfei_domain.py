"""
Case Study 1: geographic and sector alignment of the GFEI v3.0 comparison (reviewer comment 6).

Computes the GFEI v3.0 (2020) oil and gas sector total (Oil_All + Gas_All) over (a) the full Permian Basin study polygon, (b) the Texas part
of the polygon, (c) only the 0.1 degree cells that contain at least one Carbon Mapper 1B2 source of the
event cohort, and reports where the cohort's sources lie (state split, bounding box). The EAMEET
cohort total is read from total_emissions.csv when present (written by Case_study_No1.ipynb).
Requires geopandas, shapely, netCDF4.  Output: cs1_outputs/cs1_gfei_domain_alignment.{csv,md}
"""
import os, sys, json
import numpy as np, pandas as pd, geopandas as gpd, netCDF4 as nc
from shapely.geometry import Point
from shapely.prepared import prep

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "cs1_outputs"); os.makedirs(OUT, exist_ok=True)
poly_df = gpd.read_file(os.path.join(HERE, "shapefiles/Boundary_PermianBasin_StudyArea_NAD27.shp"))
poly_df = poly_df.drop(poly_df.index[1]).to_crs("EPSG:4326"); poly = poly_df.geometry.iloc[0]
states = gpd.read_file(os.path.join(HERE, "shapefiles/Boundary_State_NAD27.shp")).to_crs("EPSG:4326")
name_col = "abbv" if "abbv" in states.columns else "STATE"
print("states:", sorted(set(states[name_col].astype(str))))

# GFEI v3.0 (2020) oil and gas sector files (Oil_All + Gas_All, IPCC 1B2), kg per cell
_oil = nc.Dataset(os.path.join(HERE, "Global_Fuel_Exploitation_Inventory_v3_2020_Oil_All.nc"))
_gas = nc.Dataset(os.path.join(HERE, "Global_Fuel_Exploitation_Inventory_v3_2020_Gas_All.nc"))
lat = _oil.variables["lat"][:]; lon = _oil.variables["lon"][:]
area = _oil.variables["area"][:] * 1e-6                                              # m2 -> km2
kg = (_oil.variables["Oil_All"][:].filled(0.0) + _gas.variables["Gas_All"][:].filled(0.0)) * 1000.0 * area   # kg/a per cell
_oil.close(); _gas.close()
minx, miny, maxx, maxy = poly.bounds
ii = np.where((lat >= miny - 0.2) & (lat <= maxy + 0.2))[0]; jj = np.where((lon >= minx - 0.2) & (lon <= maxx + 0.2))[0]
pp = prep(poly)
in_poly = np.zeros((len(ii), len(jj)), bool)
for a, i in enumerate(ii):
    for b, j in enumerate(jj):
        in_poly[a, b] = pp.contains(Point(float(lon[j]), float(lat[i])))
sub = kg[np.ix_(ii, jj)]
tx = states[states[name_col].astype(str).str.strip().str.upper().isin(["TX", "TEXAS"])]
tx_geom = tx.geometry.union_all() if len(tx) else None
in_tx = np.zeros_like(in_poly)
if tx_geom is not None:
    ptx = prep(tx_geom)
    for a, i in enumerate(ii):
        for b, j in enumerate(jj):
            in_tx[a, b] = in_poly[a, b] and ptx.contains(Point(float(lon[j]), float(lat[i])))

# Carbon Mapper cohort sources (sector 1B2, with >= 1 quantified 2024 detection)
ev = pd.read_csv(os.path.join(HERE, "CM_emission_events.csv"))
eo = pd.read_csv(os.path.join(HERE, "CM_emissions_observation.csv"))
src = eo.drop_duplicates("source")[["source", "lon", "lat"]]
src = src[src.source.isin(ev.sourceLocation.unique())]
src["in_tx"] = [ptx.contains(Point(x, y)) if tx_geom is not None else np.nan for x, y in zip(src.lon, src.lat)]
cell_has_src = np.zeros_like(in_poly)
for x, y in zip(src.lon, src.lat):
    i = int(np.argmin(np.abs(lat - y))); j = int(np.argmin(np.abs(lon - x)))
    if i in ii and j in jj:
        cell_has_src[np.where(ii == i)[0][0], np.where(jj == j)[0][0]] = True

rows = [("GFEI v3.0 oil and gas (2020), full study polygon", np.nansum(sub[in_poly]) / 1e9, int(in_poly.sum())),
        ("GFEI v3.0 oil and gas (2020), Texas part of the polygon", np.nansum(sub[in_tx]) / 1e9, int(in_tx.sum())),
        ("GFEI v3.0 oil and gas (2020), cells containing >= 1 cohort source", np.nansum(sub[cell_has_src & in_poly]) / 1e9, int((cell_has_src & in_poly).sum()))]
tot_path = os.path.join(HERE, "total_emissions.csv")
if os.path.exists(tot_path):
    tdf = pd.read_csv(tot_path)
    if set(tdf.source) >= set(src.source):
        tdf = tdf[tdf.source.isin(src.source)]
        rows.append(("EAMEET v1.0 (2024), sum of per-source medians, cohort", tdf.total_emissions.sum() / 1e9, len(tdf)))
df = pd.DataFrame(rows, columns=["quantity", "Tg", "n"])
df.to_csv(os.path.join(OUT, "cs1_gfei_domain_alignment.csv"), index=False)
md = ["| Quantity | Tg CH4 | n cells / sources |", "|---|---|---|"] + [f"| {q} | {t:.3f} | {n} |" for q, t, n in rows]
md += ["", f"Cohort sources: {len(src)} (in Texas: {int(src.in_tx.sum())}, outside Texas: {int((~src.in_tx.astype(bool)).sum())}); "
       f"lon {src.lon.min():.2f} to {src.lon.max():.2f}, lat {src.lat.min():.2f} to {src.lat.max():.2f}.",
       f"Polygon bounds: lon {minx:.2f} to {maxx:.2f}, lat {miny:.2f} to {maxy:.2f}."]
open(os.path.join(OUT, "cs1_gfei_domain_alignment.md"), "w").write("\n".join(md) + "\n")
print("\n".join(md))

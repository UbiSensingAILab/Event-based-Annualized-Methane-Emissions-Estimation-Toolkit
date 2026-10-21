"""
Case Study 1 figures without cartopy (reviewer comment 6): (a) gridded EAMEET v1.0 annual emissions of the
2024 cohort on the 0.1 degree GFEI grid, (b) GFEI v3.0 over the study polygon, (c) basin-level comparison
with GFEI over three aligned domains. GFEI v3.0 oil and gas sector totals; 95 % intervals: lognormal with the emission-weighted mean of the GFEI v1.0 per-cell,
per-sector relative standard deviations (fully correlated errors; v3.0 ships no uncertainty layer). Requires geopandas (study polygon) and netCDF4.
Outputs: EAMEET_emissions_estimation.png, GFEI.png, CM_vs_GFEI.png, cs1_outputs/cs1_basin_comparison.csv
"""
import os, numpy as np, pandas as pd, geopandas as gpd, netCDF4 as nc, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from shapely.geometry import Point
from shapely.prepared import prep
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "cs1_outputs")
poly_df = gpd.read_file(os.path.join(HERE, "shapefiles/Boundary_PermianBasin_StudyArea_NAD27.shp"))
poly_df = poly_df.drop(poly_df.index[1]).to_crs("EPSG:4326"); poly = poly_df.geometry.iloc[0]; pp = prep(poly)
states = gpd.read_file(os.path.join(HERE, "shapefiles/Boundary_State_NAD27.shp")).to_crs("EPSG:4326")
from cs1_gfei import load_gfei, total_cv
G = load_gfei(HERE); lat = G["lat"]; lon = G["lon"]; kg = G["kg"]      # GFEI v3.0 Oil_All + Gas_All (kg per cell) and v1.0 rsd
west, east, south, north = -105.5, -99.5, 29.0, 34.5
ii = np.where((lat >= south) & (lat <= north))[0]; jj = np.where((lon >= west) & (lon <= east))[0]
sub = kg[np.ix_(ii, jj)]; mask = np.zeros_like(sub, bool)
for a, i in enumerate(ii):
    for b, j in enumerate(jj):
        mask[a, b] = pp.contains(Point(float(lon[j]), float(lat[i])))
gfei = np.where(mask, sub, np.nan)
tdf = pd.read_csv(os.path.join(HERE, "total_emissions.csv")); eo = pd.read_csv(os.path.join(HERE, "CM_emissions_observation.csv"))
src = eo.drop_duplicates("source").set_index("source")[["lon", "lat"]]; tdf = tdf.join(src, on="source")
em = np.full(sub.shape, np.nan)
for _, r in tdf.iterrows():
    i = int(np.argmin(np.abs(lat[ii] - r.lat))); j = int(np.argmin(np.abs(lon[jj] - r.lon)))
    em[i, j] = (0 if np.isnan(em[i, j]) else em[i, j]) + r.total_emissions
ext = [float(lon[jj].min()) - 0.05, float(lon[jj].max()) + 0.05, float(lat[ii].min()) - 0.05, float(lat[ii].max()) + 0.05]

def panel(ax, arr, label):
    im = ax.imshow(arr * 1e-9, extent=ext, origin="lower", cmap="viridis")
    poly_df.plot(ax=ax, facecolor="none", edgecolor="red", linewidth=1); states.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=0.8)
    ax.set_xlim(west - 1, east + 1); ax.set_ylim(south - 1, north + 1); ax.set_xlabel("longitude"); ax.set_ylabel("latitude")
    plt.colorbar(im, ax=ax, shrink=0.7, label=label)

fig, ax = plt.subplots(figsize=(5, 5)); panel(ax, em, "EAMEET v1.0 annual emissions (Tg)"); fig.tight_layout(); fig.savefig(os.path.join(HERE, "EAMEET_emissions_estimation.png"), dpi=300)
fig, ax = plt.subplots(figsize=(5, 5)); panel(ax, gfei, "GFEI v3.0 oil and gas annual emissions (Tg)"); fig.tight_layout(); fig.savefig(os.path.join(HERE, "GFEI.png"), dpi=300)

b = np.load(os.path.join(HERE, "cs1_basin_total_ensemble.npy")) / 1e9
med, lo, hi = np.median(b), np.percentile(b, 2.5), np.percentile(b, 97.5)
dom = pd.read_csv(os.path.join(OUT, "cs1_gfei_domain_alignment.csv"))
Gsub = {k: (G[k][np.ix_(ii, jj)] if k in ("kg_oil", "kg_gas", "rsd_oil", "rsd_gas") else G[k]) for k in G}
cvs = total_cv(Gsub, mask); cv = float(cvs["fully_correlated"])   # emission-weighted mean rsd over both sectors (fully correlated errors)
print("GFEI relative uncertainty of the polygon total:", {k: round(float(v), 3) for k, v in cvs.items()})
from scipy import stats
sig = np.sqrt(np.log(1 + cv ** 2)); f_lo, f_hi = np.exp(sig * stats.norm.ppf(0.025)), np.exp(sig * stats.norm.ppf(0.975))
rows = [("EAMEET v1.0 (2024), cohort of 629 detected sources", med, lo, hi)]
for q, t in zip(dom.quantity, dom.Tg):
    if q.startswith("GFEI"):
        rows.append((q, t, t * f_lo, t * f_hi))
cmp = pd.DataFrame(rows, columns=["estimate", "Tg", "lo", "hi"]); cmp["ratio_EAMEET_to_GFEI"] = med / cmp.Tg
cmp.to_csv(os.path.join(OUT, "cs1_basin_comparison.csv"), index=False); print(cmp.round(3).to_string(index=False)); print("GFEI CV", round(cv, 3))
fig, ax = plt.subplots(figsize=(9, 3.6)); y = np.arange(len(cmp))[::-1]
ax.barh(y, cmp.Tg, xerr=[cmp.Tg - cmp.lo, cmp.hi - cmp.Tg], color=["darkcyan"] + ["orange"] * (len(cmp) - 1), capsize=5, height=0.6)
ax.set_yticks(y); ax.set_yticklabels([e.replace("GFEI v3.0 oil and gas (2020), ", "GFEI v3.0 oil and gas (2020),\n") for e in cmp.estimate], fontsize=9); ax.set_xlabel("Annual methane emissions (Tg)")
fig.tight_layout(); fig.savefig(os.path.join(HERE, "CM_vs_GFEI.png"), dpi=300); print("figures written")

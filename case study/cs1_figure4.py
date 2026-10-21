"""
Figure 4(a) of the manuscript regenerated from the revised Case Study 1 data set (reviewer comment 6):
number of quantified Carbon Mapper plume detections per 0.1 degree grid cell in 2024 (all platforms, IPCC 1B2).
Panel (b) (Carbon Mapper portal screenshot) is unchanged and is cropped from the original composite.
Outputs: CM_plume_counts.png (panel a) and cs1_outputs/Figure4_revised_composite.png
"""
import os, sys, numpy as np, pandas as pd, geopandas as gpd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "cs1_outputs")
poly_df = gpd.read_file(os.path.join(HERE, "shapefiles/Boundary_PermianBasin_StudyArea_NAD27.shp"))
poly_df = poly_df.drop(poly_df.index[1]).to_crs("EPSG:4326")
states = gpd.read_file(os.path.join(HERE, "shapefiles/Boundary_State_NAD27.shp")).to_crs("EPSG:4326")
eo = pd.read_csv(os.path.join(HERE, "CM_emissions_observation.csv"))
det = eo[eo.detection & (eo.rate > 0)]
west, east, south, north = -105.5, -99.5, 29.0, 34.5
lon_edges = np.arange(west, east + 0.1, 0.1); lat_edges = np.arange(south, north + 0.1, 0.1)
H, _, _ = np.histogram2d(det.lat, det.lon, bins=[lat_edges, lon_edges])
H = np.where(H == 0, np.nan, H)
fig, ax = plt.subplots(figsize=(5, 5))
im = ax.imshow(H, extent=[west, east, south, north], origin="lower", cmap="viridis")
poly_df.plot(ax=ax, facecolor="none", edgecolor="red", linewidth=1); states.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=0.8)
ax.set_xlim(west - 1, east + 1); ax.set_ylim(south - 1, north + 1); ax.set_xlabel("longitude"); ax.set_ylabel("latitude")
plt.colorbar(im, ax=ax, shrink=0.7, label="Number of plumes detected by CM systems")
fig.text(0.02, 0.96, "(a)", fontsize=16); fig.tight_layout(rect=(0, 0, 1, 0.97)); fig.savefig(os.path.join(HERE, "CM_plume_counts.png"), dpi=300)
print("detections", len(det), "cells", int(np.nansum(~np.isnan(H))), "max per cell", int(np.nanmax(H)))
# composite with the unchanged panel (b)
orig = sys.argv[1] if len(sys.argv) > 1 else None
if orig and os.path.exists(orig):
    o = Image.open(orig).convert("RGB"); W, Hh = o.size
    b = o.crop((int(W * 0.372), 0, W, Hh))                     # panel (b) incl. its label
    a = Image.open(os.path.join(HERE, "CM_plume_counts.png")).convert("RGB")
    a = a.resize((int(a.width * Hh / a.height), Hh))
    comp = Image.new("RGB", (a.width + b.width, Hh), "white"); comp.paste(a, (0, 0)); comp.paste(b, (a.width, 0))
    comp.save(os.path.join(OUT, "Figure4_revised_composite.png")); print("composite", comp.size)

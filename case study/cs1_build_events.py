"""
Case Study 1: build the Carbon Mapper emission observations and emission events (reviewer comment 6).

Reads the Carbon Mapper source (CM_sources.json) and plume (CM_plumes.csv) downloads for the Permian
Basin study area and
  1. keeps oil-and-gas sources only (IPCC sector 1B2; the coal-mining, livestock and unclassified
     sources of the download are listed and dropped),
  2. keeps the 2024 plumes of ALL three Carbon Mapper platforms (GAO airborne, EMIT and Tanager-1);
     the earlier notebook parsed plume identifiers with `"2024" in plume_id.split("t")[0]`, which is
     empty for Tanager identifiers ("tan2024...") and therefore silently dropped every Tanager plume,
  3. drops plumes without an automated quantification (emission_auto missing),
  4. writes CM_emissions_observation.csv (positive detections + null detections per source) and
     converts them into emission events with the toolkit (EAMEET_v1.emission_event_converter), writing
     CM_emission_events.csv and a composition summary (cs1_outputs/cs1_dataset_composition.csv/.md).

Usage: python cs1_build_events.py   (from the 'case study' folder)
"""
import json, os, re, sys
from datetime import datetime
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "EAMEET_v1"))
from emission_event_converter import convert_to_emission_event_model

OUT = os.path.join(HERE, "cs1_outputs"); os.makedirs(OUT, exist_ok=True)
YEAR = 2024
SECTOR_KEEP = {"1B2"}                      # IPCC 1B2 = fugitive emissions from oil and natural gas
PLATFORM = {"GAO": "GAO (airborne)", "emi": "EMIT (ISS, satellite)", "tan": "Tanager-1 (satellite)",
            "ang": "AVIRIS-NG (airborne)"}

_ts_re = re.compile(r"^[A-Za-z]{3}(\d{8}t\d{6})")


def plume_time(pid):
    """Timestamp encoded in a Carbon Mapper plume / scene identifier (e.g. 'tan20241001t175004p...')."""
    m = _ts_re.match(pid)
    return datetime.strptime(m.group(1), "%Y%m%dt%H%M%S") if m else None


with open(os.path.join(HERE, "CM_sources.json")) as f:
    feats = json.load(f)["features"]
plumes = pd.read_csv(os.path.join(HERE, "CM_plumes.csv"))
plumes["t"] = pd.to_datetime(plumes["datetime"], format="mixed", utc=True).dt.tz_localize(None)

rows, dropped_sources, log = [], [], {}
for ft in feats:
    pr = ft["properties"]; sector = pr.get("sector")
    if sector not in SECTOR_KEEP:
        dropped_sources.append((ft["id"], sector)); continue
    lon, lat = ft["geometry"]["coordinates"][:2]
    pos_times = []
    for pid in dict.fromkeys(pr.get("plume_ids") or []):      # unique, order kept
        t = plume_time(pid)
        if t is None or t.year != YEAR:
            continue
        pl = plumes[plumes.plume_id == pid]
        if len(pl) == 0:
            log["plume id not in plume file"] = log.get("plume id not in plume file", 0) + 1; continue
        rate = pl["emission_auto"].iloc[0]
        if not np.isfinite(rate):
            log["plume without quantification (dropped)"] = log.get("plume without quantification (dropped)", 0) + 1
            continue
        pos_times.append(t)
        rows.append(dict(id=pid, rate=float(rate), rate_uncertainty=float(pl["emission_uncertainty_auto"].iloc[0]),
                         source=ft["id"], lon=lon, lat=lat, persistence=pr.get("persistence"),
                         observation_time=t, measurement_technology=pl["instrument"].iloc[0],
                         platform=PLATFORM.get(pl["instrument"].iloc[0], pl["instrument"].iloc[0]),
                         sector=sector, detection=True))
    if not pos_times:
        continue                                               # no quantified 2024 detection -> no event
    for sn in pr.get("observation_scenes_names") or []:
        if not sn:
            continue
        sid = sn.split(":")[-1]; t = plume_time(sid)
        if t is None or t.year < YEAR - 1 or t in pos_times:
            continue
        rows.append(dict(id=f"{ft['id']}-{t:%Y-%m-%d %H:%M:%S}", rate=0.0, rate_uncertainty=0.0, source=ft["id"],
                         lon=lon, lat=lat, persistence=pr.get("persistence"), observation_time=t,
                         measurement_technology=sid[:3], platform=PLATFORM.get(sid[:3], sid[:3]),
                         sector=sector, detection=False))

eo = pd.DataFrame(rows).drop_duplicates(subset=["id"]).sort_values(["source", "observation_time"]).reset_index(drop=True)
eo.to_csv(os.path.join(HERE, "CM_emissions_observation.csv"), index=False)

# ---- events with the toolkit (snapshot observations bracketed by null detections)
mapping = {"id": "id", "rate": "rate", "uncertainties": "rate_uncertainty", "source": "source",
           "observation_type": "measurement_technology", "time": "observation_time", "source_scale": "site"}
events = convert_to_emission_event_model(eo, column_mapping=mapping, time_column="observation_time",
                                         emission_characteristics="intermittent")
events["startTime"] = pd.to_datetime(events["startTime"]); events["endTime"] = pd.to_datetime(events["endTime"])
events.to_csv(os.path.join(HERE, "CM_emission_events.csv"), index=False)

# ---- composition summary
pos = eo[eo.detection]; nul = eo[~eo.detection]
ids = [s.strip() for m in events.merged_from.dropna() for s in str(m).split(",")]
comp = pd.Series([PLATFORM.get(i[:3], i[:3]) for i in ids]).value_counts()
lines = ["| Item | Value |", "|---|---|",
         f"| Sources in download | {len(feats)} |",
         f"| Sources dropped by sector filter (not 1B2) | {len(dropped_sources)} ({', '.join(f'{s}' for _, s in dropped_sources)}) |",
         f"| 1B2 sources with >= 1 quantified {YEAR} detection (event cohort) | {events.sourceLocation.nunique()} |",
         f"| Quantified positive detections {YEAR} | {len(pos)} |"]
for k, v in pos.platform.value_counts().items():
    lines.append(f"| &nbsp;&nbsp; {k} | {v} |")
lines += [f"| Valid null detections (scenes without a plume, {YEAR-1}-{YEAR}) | {len(nul)} |",
          f"| &nbsp;&nbsp; null detections in {YEAR} | {int((nul.observation_time.dt.year == YEAR).sum())} |",
          f"| Emission events | {len(events)} |",
          f"| Events with > 1 detection | {int((events.n_observations > 1).sum())} |",
          f"| Observation dates per source (median) | {np.median([len(set(g.observation_time.dt.date)) for _, g in eo.groupby('source')]):.0f} |"]
for k, v in log.items():
    lines.append(f"| {k} | {v} |")
md = "\n".join(lines) + "\n"
open(os.path.join(OUT, "cs1_dataset_composition.md"), "w").write(md)
pd.DataFrame({"platform": comp.index, "contributing_plumes": comp.values}).to_csv(
    os.path.join(OUT, "cs1_platform_composition.csv"), index=False)
print(md)
print("GAO detection dates:", pos[pos.measurement_technology == "GAO"].observation_time.min().date(), "->",
      pos[pos.measurement_technology == "GAO"].observation_time.max().date())
print("wrote CM_emissions_observation.csv, CM_emission_events.csv, cs1_outputs/cs1_dataset_composition.md")

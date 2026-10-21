"""
Worked examples of the time-weighted, scale-aware combination of observations within an event
(SI Section S2.1, reviewer comment 5). Prints the sub-interval table of each example and the resulting
event rate, duration and quantity, and writes validation_outputs/worked_examples_merging.md.
Run: python worked_examples_merging.py
"""
import os, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emission_event_converter import convert_to_emission_event_model, integrate_event

MAPPING = {"id": "id", "rate": "rate", "source": "source", "uncertainties": "unc", "start_time": "start",
           "end_time": "end", "time": "time", "observation_type": "obs_type", "observation_scale": "scale", "feature": "feature"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "validation_outputs"); os.makedirs(OUT, exist_ok=True)


def df(rows):
    return pd.DataFrame([dict(id=i, source="Site", time=t, start=s, end=e, rate=r, unc=u, obs_type=k, scale=sc, feature=f)
                         for i, t, s, e, r, u, k, sc, f in rows])


EXAMPLES = {
    "Example 1 - repeatedly observed persistent leak (two overlapping CMS alarms on one compressor)": [
        ("CMS-a", "2024-03-01 00:00", "2024-03-01 00:00", "2024-03-01 10:00", 10.0, 2.0, "cms", "equipment", "Compressor-1"),
        ("CMS-b", "2024-03-01 08:00", "2024-03-01 08:00", "2024-03-01 20:00", 20.0, 4.0, "cms", "equipment", "Compressor-1")],
    "Example 2 - concurrent emissions from two components (OGI-quantified, overlapping intervals)": [
        ("OGI-1", "2024-03-01 00:00", "2024-03-01 00:00", "2024-03-01 10:00", 2.0, 0.5, "ogi", "component", "Valve-1"),
        ("OGI-2", "2024-03-01 00:00", "2024-03-01 04:00", "2024-03-01 10:00", 3.0, 0.6, "ogi", "component", "Flange-7")],
    "Example 3 - facility measurement overlapping component measurements": [
        ("FLY-1", "2024-03-01 05:00", "2024-03-01 02:00", "2024-03-01 08:00", 12.0, 3.0, "flyover", "site", "Site"),
        ("OGI-1", "2024-03-01 00:00", "2024-03-01 00:00", "2024-03-01 10:00", 2.0, 0.5, "ogi", "component", "Valve-1"),
        ("OGI-2", "2024-03-01 00:00", "2024-03-01 04:00", "2024-03-01 10:00", 3.0, 0.6, "ogi", "component", "Flange-7")],
    "Example 4 - duplicate record and split record (Example 1 with CMS-b duplicated and CMS-a split at 06:00)": [
        ("CMS-a1", "2024-03-01 00:00", "2024-03-01 00:00", "2024-03-01 06:00", 10.0, 2.0, "cms", "equipment", "Compressor-1"),
        ("CMS-a2", "2024-03-01 06:00", "2024-03-01 06:00", "2024-03-01 10:00", 10.0, 2.0, "cms", "equipment", "Compressor-1"),
        ("CMS-b", "2024-03-01 08:00", "2024-03-01 08:00", "2024-03-01 20:00", 20.0, 4.0, "cms", "equipment", "Compressor-1"),
        ("CMS-b-dup", "2024-03-01 08:00", "2024-03-01 08:00", "2024-03-01 20:00", 20.0, 4.0, "cms", "equipment", "Compressor-1")],
}

lines = []
for title, rows in EXAMPLES.items():
    ev = convert_to_emission_event_model(df(rows), MAPPING, time_column="time", emission_characteristics="intermittent")
    obs = [dict(id=i, rate=r, uncertainty=u, observation_type=k, scale=sc, feature=f, start=s, end=e) for i, t, s, e, r, u, k, sc, f in rows]
    integ = integrate_event(obs, ev.startTime.iloc[0], ev.endTime.iloc[0])
    lines += [f"**{title}**", "", "| Observation | Scale / feature | Interval | Rate (kg/h) |", "|---|---|---|---|"]
    for i, t, s, e, r, u, k, sc, f in rows:
        lines.append(f"| {i} ({k}) | {sc} / {f} | {s[11:]}-{e[11:]} | {r:g} +/- {u:g} |")
    lines += ["", "| Sub-interval | Active observations | Rule | Rate (kg/h) | Mass (kg) |", "|---|---|---|---|---|"]
    for a, b, r, u in integ["segments"]:
        act = [o for o in obs if (o["start"] is None) or (pd.to_datetime(o["start"]) <= a and pd.to_datetime(o["end"]) >= b)]
        names = ", ".join(o["id"] for o in act)
        scales = {o["scale"] for o in act}; feats = {(o["scale"], o["feature"]) for o in act}
        if len(act) == 1: rule = "single observation"
        elif len(scales) > 1: rule = "components summed, then averaged with the site measurement"
        elif len(feats) > 1: rule = "distinct features summed"
        else: rule = "replicates averaged"
        lines.append(f"| {a:%H:%M}-{b:%H:%M} | {names} | {rule} | {r:.2f} | {r * (b - a).total_seconds() / 3600:.1f} |")
    naive = sum(r for *_, r, u, k, sc, f in rows) / len(rows)
    lines += ["", f"Event: duration {integ['duration']:.0f} h, quantity {integ['quantity']:.1f} kg, resolved rate {integ['rate']:.2f} kg/h "
              f"(uncertainty {integ['uncertainty']:.2f} kg/h). Former rule (mean of the observed rates x union): "
              f"{naive:.2f} kg/h x {integ['duration']:.0f} h = {naive * integ['duration']:.1f} kg.", ""]
    print(lines[-2])
open(os.path.join(OUT, "worked_examples_merging.md"), "w").write("\n".join(lines))
print("wrote validation_outputs/worked_examples_merging.md")

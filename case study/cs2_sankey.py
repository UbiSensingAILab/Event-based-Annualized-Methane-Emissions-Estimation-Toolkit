"""Sankey: Case Study 2 observations -> emission events -> equipment attribution.
Flow width = number of source observations (conserved across layers)."""
import pandas as pd, plotly.graph_objects as go
X = pd.ExcelFile("Data_from_case_study_2.xlsx")
cms, ogi, fly, op = (X.parse(s) for s in ["CMS", "OGI", "Flyover", "Operational"])
ev = pd.read_csv("emission_events_case_study_2.csv")

n_pre, n_re = (ev.event_type == "PRE").sum(), (ev.event_type == "RE").sum()
fly_det, fly_nd = fly[fly.detection], fly[~fly.detection]
ogi_nd, ogi_det = ogi[~ogi.detection], ogi[ogi.detection]

# layer 1 -> layer 2 -> layer 3 links as (source, target, value)
links = [
    (f"CMS ({len(cms)})", f"PRE ({n_pre} events)", len(cms)),
    (f"Flyover detections ({len(fly_det)})", f"PRE ({n_pre} events)", len(fly_det)),
    (f"Operational ({len(op)})", f"RE ({n_re} events)", len(op)),
    (f"Flyover non-detects ({len(fly_nd)})", "Detection bounds only (not events)", len(fly_nd)),
    (f"OGI non-detects ({len(ogi_nd)})", "Detection bounds only (not events)", len(ogi_nd)),
    (f"OGI detections, no rate ({len(ogi_det)})", "Excluded (no rate)", len(ogi_det)),
]
for eq, n in cms.groupby("equipment").size().items():
    links.append((f"PRE ({n_pre} events)", eq, n))
links.append((f"PRE ({n_pre} events)", "Facility (flyover)", len(fly_det)))
for eq, n in op.groupby("equipment").size().items():
    links.append((f"RE ({n_re} events)", eq, n))

labels = list(dict.fromkeys([l for s, t, _ in links for l in (s, t)]))
idx = {l: i for i, l in enumerate(labels)}
col = {"CMS": "#2a9d8f", "Flyover": "#e76f51", "OGI": "#8d99ae", "Operational": "#e9c46a",
       "PRE": "#264653", "RE": "#b08900", "Detection": "#bbb", "Excluded": "#bbb"}
def color(l, a=1.0):
    for k, c in col.items():
        if l.startswith(k): return c
    return "#7a8aa0"
src = [idx[s] for s, _, _ in links]; tgt = [idx[t] for _, t, _ in links]
fig = go.Figure(go.Sankey(
    arrangement="snap",
    node=dict(label=labels, color=[color(l) for l in labels], pad=14, thickness=18),
    link=dict(source=src, target=tgt, value=[v for *_, v in links],
              color=["rgba(120,130,150,0.35)"] * len(links))))
fig.update_layout(title=dict(text="Case Study 2: observations → emission events → equipment<br><sup>Flow width = number of source observations</sup>", x=0.01),
                  font_size=13, width=1200, height=640, margin=dict(t=90, b=20, l=20, r=20))
fig.write_html("cs2_outputs/cs2_observation_event_equipment_sankey.html")
PNG = "cs2_outputs/cs2_observation_event_equipment_sankey.png"
try:
    fig.write_image(PNG, width=1200, height=640, scale=3.5)   # 1200 px * 3.5 = 4200 px = 7 in wide at 600 dpi
    from PIL import Image
    Image.open(PNG).save(PNG, dpi=(600, 600))
except Exception as e: print("png skipped:", e)
print(len(labels), "nodes", len(links), "links;", sum(v for *_, v in links[:6]), "observations in")

"""Assemble the revised Figure 5 of the manuscript in the original layout: (a) EAMEET v1.0 gridded emissions,
(b) GFEI v3.0 over the study polygon, (c) basin-level comparison over the three GFEI domains.
Inputs: EAMEET_emissions_estimation.png, GFEI.png, CM_vs_GFEI.png (from cs1_figures.py).
Output: cs1_outputs/Figure5_revised_composite.png"""
import os, matplotlib
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "cs1_outputs")
font = ImageFont.truetype(os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data/fonts/ttf/DejaVuSans.ttf"), 48)
a = Image.open(os.path.join(HERE, "EAMEET_emissions_estimation.png")).convert("RGB")
b = Image.open(os.path.join(HERE, "GFEI.png")).convert("RGB")
c = Image.open(os.path.join(HERE, "CM_vs_GFEI.png")).convert("RGB")
W = a.width + b.width + 60; c = c.resize((W, int(c.height * W / c.width)))
H = a.height + c.height + 60
img = Image.new("RGB", (W, H), "white"); img.paste(a, (0, 40)); img.paste(b, (a.width + 60, 40)); img.paste(c, (0, a.height + 60))
d = ImageDraw.Draw(img)
for lab, xy in [("(a)", (10, 0)), ("(b)", (a.width + 70, 0)), ("(c)", (10, a.height + 40))]:
    d.text(xy, lab, fill="black", font=font)
img.save(os.path.join(OUT, "Figure5_revised_composite.png")); print("composite", img.size)

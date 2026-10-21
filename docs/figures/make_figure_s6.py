"""Generate Figure S6 (Type 1 simulation workflow) as SVG. Run: python make_figure_s6.py"""
W, H = 1700, 1080
out = []
def rect(cx, cy, w, h, lines, fill="#cfe6ff", stroke="#2b6cb0", rx=6, fs=14, bold=False):
    out.append(f'<rect x="{cx-w/2}" y="{cy-h/2}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    text(cx, cy, lines, fs, bold)
def pill(cx, cy, w, h, lines, fill="#4a4ad6"):
    out.append(f'<rect x="{cx-w/2}" y="{cy-h/2}" width="{w}" height="{h}" rx="{h/2}" fill="{fill}" stroke="#222" stroke-width="1.2"/>')
    text(cx, cy, lines, 14, False, "#fff")
def diamond(cx, cy, w, h, lines, fill="#cfe6ff", stroke="#2b6cb0", fs=13):
    out.append(f'<polygon points="{cx},{cy-h/2} {cx+w/2},{cy} {cx},{cy+h/2} {cx-w/2},{cy}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    text(cx, cy, lines, fs)
def text(cx, cy, lines, fs=14, bold=False, color="#111"):
    n = len(lines); y0 = cy - (n-1)*fs*0.62
    for i, ln in enumerate(lines):
        out.append(f'<text x="{cx}" y="{y0+i*fs*1.24:.1f}" text-anchor="middle" dominant-baseline="middle" font-size="{fs}"{" font-weight=\"bold\"" if bold else ""} fill="{color}">{ln}</text>')
def arrow(pts, label=None, lx=None, ly=None, anchor="middle"):
    d = "M" + " L".join(f"{x},{y}" for x, y in pts)
    out.append(f'<path d="{d}" fill="none" stroke="#111" stroke-width="1.5" marker-end="url(#arrow)"/>')
    if label:
        out.append(f'<text x="{lx}" y="{ly}" font-size="13" fill="#111" text-anchor="{anchor}" dominant-baseline="middle">{label}</text>')
def label(x, y, s, fs=15, bold=True, anchor="start"):
    out.append(f'<text x="{x}" y="{y}" font-size="{fs}"{" font-weight=\"bold\"" if bold else ""} text-anchor="{anchor}">{s}</text>')
I = lambda s: f'<tspan font-style="italic">{s}</tspan>'
SUB = lambda s: f'<tspan baseline-shift="sub" font-size="10">{s}</tspan>'
GREEN, GSTROKE = "#c9efc9", "#2f8f2f"; YEL, YSTROKE = "#ffe9a3", "#b58900"; GREY = "#eeeeee"

# ---------------- panel (a) ----------------
label(30, 34, "(a) Monte Carlo loop over the time budget of the monitored period")
cL, cM, cR = 200, 560, 880
pill(cL, 75, 90, 30, ["start"])
rect(cL, 130, 250, 40, ["Set number of iterations MC; mc = 1"])
rect(cL, 215, 330, 92, ["Build the time budget:", "hours with at least one observing technology",
                        "(coverage schedules: CMS uptime, survey instants;", "no schedule = whole monitored period)",
                        "minus union of observed RE/PRE hours → gap segments"], fill=GREY, stroke="#555", fs=13)
rect(cL, 300, 280, 40, [f"{I('E')}{SUB('UE')} = 0;  {I('t')} = start of the first gap"])
rect(cL, 375, 300, 52, ["Sample component-scale emission rate", f"and component count → {I('Q')} (equipment/site scale)"], fill=GREEN, stroke=GSTROKE, fs=13)
rect(cL, 455, 300, 52, [f"Sample duration {I('D')} from observed durations;", "clip to the end of the current gap"], fill=GREEN, stroke=GSTROKE, fs=13)
rect(cL, 535, 300, 52, [f"Wind speed {I('u')} at {I('t')}: time-matched series,", "or one random draw from the wind sample"], fill=GREEN, stroke=GSTROKE, fs=13)
diamond(cL, 650, 300, 110, ["Any technology whose", f"coverage overlaps [{I('t')}, {I('t')}+{I('D')})?", "(CMS: uptime interval overlaps;", "survey: instant inside the event)"])
rect(cL, 780, 250, 52, ["No technology could have", "observed it: unresolved"], fill=GREY, stroke="#555", fs=13)
rect(cM, 650, 230, 52, ["Technology-specific", "POD check (panel b)"], fill=YEL, stroke=YSTROKE)
diamond(cM, 780, 230, 90, ["Missed by all", "covering technologies?"])
rect(cM, 900, 230, 44, [f"{I('E')}{SUB('UE')} += {I('Q')} × {I('D')}"])
rect(cM, 985, 300, 52, [f"{I('t')} += {I('D')}  (move to the next gap", "when the current one is exhausted)"])
diamond(cR, 985, 220, 90, ["Time budget", "exhausted?"])
rect(cR, 860, 230, 44, [f"Save {I('E')}{SUB('UE')};  mc = mc + 1"])
diamond(cR, 740, 180, 80, ["mc = MC?"])
rect(cR, 620, 260, 52, ["Median and 2.5th / 97.5th percentiles", f"of the MC values of {I('E')}{SUB('UE')}"])
pill(cR, 530, 90, 30, ["end"])
arrow([(cL, 90), (cL, 110)]); arrow([(cL, 150), (cL, 169)]); arrow([(cL, 261), (cL, 280)]); arrow([(cL, 320), (cL, 349)])
arrow([(cL, 401), (cL, 429)]); arrow([(cL, 481), (cL, 509)]); arrow([(cL, 561), (cL, 595)])
arrow([(cL, 705), (cL, 754)], "No", cL+18, 728)
arrow([(cL+150, 650), (cM-115, 650)], "Yes", cL+200, 638)
arrow([(cM, 676), (cM, 735)])
arrow([(cM, 825), (cM, 878)], "Yes", cM+20, 850)
arrow([(cL, 806), (cL, 900), (cM-115, 900)])
# detected: nothing added, go straight to the clock advance (enter the box from the top)
arrow([(cM+115, 780), (cM+200, 780), (cM+200, 945), (cM+110, 945), (cM+110, 959)])
out.append(f'<text x="{cM+192}" y="848" font-size="12" text-anchor="end">No: detected, already</text>'
           f'<text x="{cM+192}" y="863" font-size="12" text-anchor="end">in an RE/PRE; add nothing</text>')
arrow([(cM, 922), (cM, 959)])
arrow([(cM+150, 985), (cR-110, 985)])
arrow([(cR, 1030), (cR, 1055), (20, 1055), (20, 375), (cL-150, 375)], "No", cR+18, 1045)
arrow([(cR, 940), (cR, 882)], "Yes", cR+22, 912)
arrow([(cR, 838), (cR, 780)])
arrow([(cR, 700), (cR, 646)], "Yes", cR+22, 675)
arrow([(cR+90, 740), (cR+150, 740), (cR+150, 300), (cL+140, 300)], "No", cR+118, 728)
arrow([(cR, 594), (cR, 545)])

# ---------------- panel (b) ----------------
bx = 1380
label(1070, 34, "(b) Technology-specific POD check for one hypothetical event")
out.append('<rect x="1045" y="50" width="640" height="770" rx="10" fill="none" stroke="#d33" stroke-width="1.5" stroke-dasharray="7,5"/>')
rect(bx, 95, 540, 52, [f"Input: {I('Q')}, {I('D')}, {I('u')}, event interval [{I('t')}, {I('t')}+{I('D')}),", "list of technologies whose coverage overlaps the interval"], fill=GREY, stroke="#555", fs=13)
rect(bx, 170, 300, 40, [f"{I('k')} = first covering technology"], fill=YEL, stroke=YSTROKE)
rect(bx, 245, 360, 66, [f"POD{SUB('k')} = {I('f')}{SUB('k')}({I('Q')}, {I('u')}) (wind-dependent curve, Table S2)",
                         f"or constant POD{SUB('k')} at the nominal MDL;", "a snapshot survey counts once per overlapping pass"], fill=YEL, stroke=YSTROKE, fs=13)
rect(bx, 325, 220, 40, [f"Draw ξ{SUB('k')} ~ U(0, 1)"], fill=GREEN, stroke=GSTROKE)
diamond(bx, 420, 200, 84, [f"ξ{SUB('k')} < POD{SUB('k')} ?"])
rect(bx+170, 520, 200, 52, ["True negative:", f"detected by {I('k')}"], fill="#dfe8f3", stroke="#2b6cb0", fs=13)
rect(bx-170, 520, 200, 52, ["False negative:", f"missed by {I('k')}"], fill="#f8d7da", stroke="#b03a2e", fs=13)
diamond(bx-170, 630, 210, 84, ["Another covering", "technology?"])
rect(bx-170, 740, 230, 52, ["Missed by all covering technologies", f"P = ∏{SUB('k')} (1 − POD{SUB('k')})  (Eq. S1)"], fill="#f8d7da", stroke="#b03a2e", fs=13)
rect(bx+170, 740, 200, 52, ["Event detected:", "add nothing, advance clock"], fill="#dfe8f3", stroke="#2b6cb0", fs=13)
arrow([(bx, 121), (bx, 149)]); arrow([(bx, 190), (bx, 211)]); arrow([(bx, 278), (bx, 304)]); arrow([(bx, 345), (bx, 377)])
arrow([(bx+100, 420), (bx+170, 420), (bx+170, 493)], "Yes", bx+135, 408)
arrow([(bx-100, 420), (bx-170, 420), (bx-170, 493)], "No", bx-135, 408)
arrow([(bx-170, 546), (bx-170, 587)])
arrow([(bx-170, 672), (bx-170, 713)], "No", bx-150, 692)
arrow([(bx-275, 630), (bx-310, 630), (bx-310, 170), (bx-150, 170)], "Yes: next k", bx-300, 600, anchor="middle")
out[-1] = f'<text x="{bx-318}" y="600" font-size="13" fill="#111" text-anchor="end" dominant-baseline="middle">Yes:</text><text x="{bx-318}" y="616" font-size="13" fill="#111" text-anchor="end" dominant-baseline="middle">next {I("k")}</text>'
arrow([(bx+170, 546), (bx+170, 713)])
out.append(f'<text x="{bx}" y="800" font-size="12" text-anchor="middle" fill="#444">Return "missed" (panel a adds {I("Q")} × {I("D")}) or "detected" (nothing added); the clock advances by {I("D")} in both cases</text>')

svg = (f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
       f'font-family="Times New Roman, Times, serif" font-size="14" fill="#111">\n<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="userSpaceOnUse">'
       f'<path d="M0,0 L10,5 L0,10 z" fill="#111"/></marker></defs>\n<rect width="{W}" height="{H}" fill="#fff"/>\n' + "\n".join(out) + "\n</svg>\n")
open("Figure_S6_type1_workflow.svg", "w", encoding="utf8").write(svg)
open("/private/tmp/claude-501/-Users-mo/d4a68a26-b8c9-40f9-b0a9-0383aab0c35f/scratchpad/fig_s6.html", "w", encoding="utf8").write(f'<html><head><meta charset="utf-8"></head><body style="margin:0">{svg[svg.find("<svg"):]}</body></html>')
print("svg written")

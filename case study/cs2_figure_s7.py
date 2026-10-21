"""Figure S7 (SI) regenerated from the revised Case Study 2 events (EAMEET v1.0.2 merge, reviewer comment 5):
histograms of the CMS-derived PRE rates (a) and durations (b) with the Weibull fit used in both case studies
(Eq. S2b; scipy weibull_min, loc = 0). The lognormal option of Eq. S2 is shown dashed for comparison.
Output: cs2_outputs/cs2_figure_s7_weibull_fit.png"""
import os, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.stats import lognorm, weibull_min
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "cs2_outputs")
ev = pd.read_csv(os.path.join(HERE, "emission_events_case_study_2.csv"))
pre = ev[(ev.event_type == "PRE") & (ev.duration < 1000)]  # CMS-derived PREs (the flyover-only PRE has a simulated multi-week duration)
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
for ax, col, color, lab, t in zip(axes, ["rate", "duration"], ["royalblue", "forestgreen"], ["Rate (kg/hr)", "Duration (hr)"], ["(a)", "(b)"]):
    v = pre[col].to_numpy(float); v = v[v > 0]
    ax.hist(v, bins=10, density=True, color=color, edgecolor="black", alpha=0.8)
    x = np.linspace(v.min() * 0.5, v.max() * 1.05, 400)
    k, loc, lam = weibull_min.fit(v, floc=0); ax.plot(x, weibull_min.pdf(x, k, loc, lam), "r-", lw=2.5, label=f"Weibull (k = {k:.2f}, λ = {lam:.1f})")
    s, loc2, sc = lognorm.fit(v, floc=0); ax.plot(x, lognorm.pdf(x, s, loc2, sc), "k--", lw=1.5, label=f"lognormal (σ = {s:.2f}, median = {sc:.1f})")
    ax.set_xlabel(lab); ax.set_ylabel("density"); ax.set_title(t); ax.legend(frameon=False)
    print(col, "n", len(v), "weibull k", round(k, 3), "lambda", round(lam, 2), "| lognormal sigma", round(s, 3), "median", round(sc, 2))
fig.tight_layout(); fig.savefig(os.path.join(OUT, "cs2_figure_s7_weibull_fit.png"), dpi=150); print("written")

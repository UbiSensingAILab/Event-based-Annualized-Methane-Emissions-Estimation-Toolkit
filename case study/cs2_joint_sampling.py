"""
Case Study 2: dependence between event rate and duration, and the effect of joint (paired or
class-stratified) sampling on the unmonitored-period (Type 2) extrapolation.

Reviewer comment 4: independently sampling pooled rate and duration distributions can create
combinations unsupported by the observed emission mechanisms; histograms alone do not establish
independence. This script (i) reports the paired rate-duration statistics of both case studies,
(ii) re-runs the Case Study 2 bootstrap with independent marginals (baseline), fitted marginals +
empirical copula of the observed pairs, raw observed pairs, and class-stratified renewal processes
(one per observation kind, each with its own occupancy), and (iii) draws the paired scatter figure.

Outputs: cs2_outputs/cs2_joint_sampling.{csv,md}, cs2_outputs/rate_duration_pairs.png
"""
import os, sys
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import spearmanr, weibull_min
import multiprocessing as mp
try:
    mp.set_start_method("fork", force=True)
except RuntimeError:
    pass
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "EAMEET_v1"))
from simulations import extrapolation, simulate_renewal_emissions_by_class
from utils import fitting_distribution

OUT = "cs2_outputs"; os.makedirs(OUT, exist_ok=True)
MEASURED_START, MEASURED_END = pd.Timestamp("2024-01-01 00:00:00"), pd.Timestamp("2024-07-31 23:59:59")
BOOT_START, YEAR_END = pd.Timestamp("2024-08-01 00:00:00"), pd.Timestamp("2024-12-31 23:59:59")
MC_BOOT, SEED_UE, BOOT_FIT = 10_000, 99, "weibull"

ev = pd.read_csv("emission_events_case_study_2.csv")
rates = ev["rate"].to_numpy(float); durs = ev["duration"].to_numpy(float)
obs_hours = (MEASURED_END - MEASURED_START).total_seconds() / 3600
poe = min(1.0, float(durs.sum()) / obs_hours)
rate_fit = {"type": BOOT_FIT, "params": fitting_distribution(rates, BOOT_FIT), "min": 0}
dur_fit = {"type": BOOT_FIT, "params": fitting_distribution(durs, BOOT_FIT), "min": 0}

# ------------------------------------------------------------------ paired statistics
cs1 = pd.read_csv("CM_emission_events.csv")
stats = []
def _row(label, r, d):
    rho, p = spearmanr(r, d)[:2]
    stats.append(dict(sample=label, n=len(r), spearman_rho=rho, p_value=p,
                      rate_median=np.median(r), duration_median_h=np.median(d)))
_row("CS2: all events (RE + PRE)", rates, durs)
cms = ev[ev.obs_kind == "CMS"]; _row("CS2: CMS-derived PREs", cms.rate.values, cms.duration.values)
for eq, g in cms.groupby("equipment_of_record"):
    if len(g) >= 5: _row(f"CS2: CMS PREs, {eq}", g.rate.values, g.duration.values)
_row("CS1: Carbon Mapper events", cs1.rate.values, cs1.duration.values)
stats_df = pd.DataFrame(stats)

# ------------------------------------------------------------------ bootstrap variants
def summ(arr):
    a = np.asarray(arr, float) / 1000
    return float(np.median(a)), float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))

rows = []
np.random.seed(SEED_UE)
b = extrapolation({"UNKNOWN": poe}, {"UNKNOWN": rates}, {"UNKNOWN": durs}, BOOT_START, YEAR_END, MC_BOOT,
                  fitted_rate_dist=rate_fit, fitted_duration_dist=dur_fit)["UNKNOWN"]
rows.append(("Independent Weibull marginals (baseline, Section 3.2)", *summ(b)))
np.random.seed(SEED_UE)
b = extrapolation({"UNKNOWN": poe}, {"UNKNOWN": rates}, {"UNKNOWN": durs}, BOOT_START, YEAR_END, MC_BOOT,
                  fitted_rate_dist=rate_fit, fitted_duration_dist=dur_fit, sampling="paired")["UNKNOWN"]
rows.append(("Weibull marginals + empirical copula of observed pairs", *summ(b)))
np.random.seed(SEED_UE)
b = extrapolation({"UNKNOWN": poe}, {"UNKNOWN": rates}, {"UNKNOWN": durs}, BOOT_START, YEAR_END, MC_BOOT,
                  sampling="paired")["UNKNOWN"]
rows.append(("Observed (rate, duration) pairs, no fit", *summ(b)))

# class-stratified: one renewal process per observation kind, own occupancy, pairs within class
total_hours = (YEAR_END - BOOT_START).total_seconds() / 3600
classes = []
for kind, g in ev.groupby("obs_kind"):
    classes.append(dict(label=kind, occupancy=min(1.0, g.duration.sum() / obs_hours),
                        rate_array=g.rate.to_numpy(float), duration_array=g.duration.to_numpy(float), paired=True))
rng = np.random.default_rng(SEED_UE)
cls = np.array([simulate_renewal_emissions_by_class(total_hours, classes, rng)[0] for _ in range(MC_BOOT)])
rows.append(("Class-stratified (CMS / flyover / operational), pairs within class", *summ(cls)))
# class-stratified without the single-event flyover class (its 'class' is one event)
classes2 = [c for c in classes if c["label"] != "Flyover"]
rng = np.random.default_rng(SEED_UE)
cls2 = np.array([simulate_renewal_emissions_by_class(total_hours, classes2, rng)[0] for _ in range(MC_BOOT)])
rows.append(("Class-stratified, flyover class excluded", *summ(cls2)))

res = pd.DataFrame(rows, columns=["sampling", "UE_boot_t", "UE_boot_lo_t", "UE_boot_hi_t"])
# annual total with the other components of the baseline run (RSS of one-sided deviations, Eqs. 12-13)
cs = pd.read_csv(f"{OUT}/cs2_results_summary.csv").set_index("component")
meas = cs.loc["Measured RE+PRE (all PREs via quadrature)"]; mdl = cs.loc["UE below-MDL (measured window)"]
res["TOTAL_t"] = (meas.kg + mdl.kg) / 1000 + res.UE_boot_t
res["TOTAL_lo_t"] = res.TOTAL_t - np.sqrt(((meas.kg - meas.lower_kg) / 1000) ** 2 + ((mdl.kg - mdl.lower_kg) / 1000) ** 2 + (res.UE_boot_t - res.UE_boot_lo_t) ** 2)
res["TOTAL_hi_t"] = res.TOTAL_t + np.sqrt(((meas.upper_kg - meas.kg) / 1000) ** 2 + ((mdl.upper_kg - mdl.kg) / 1000) ** 2 + (res.UE_boot_hi_t - res.UE_boot_t) ** 2)
res["change_pct"] = (res.TOTAL_t / res.TOTAL_t.iloc[0] - 1) * 100
res.to_csv(f"{OUT}/cs2_joint_sampling.csv", index=False)
stats_df.to_csv(f"{OUT}/rate_duration_pair_statistics.csv", index=False)
with open(f"{OUT}/cs2_joint_sampling.md", "w") as f:
    f.write("## Paired rate-duration statistics\n\n" + stats_df.round(3).to_markdown(index=False) + "\n\n")
    f.write(f"## CS2 unmonitored-period (Aug-Dec) extrapolation by sampling scheme (occupancy {poe:.3f}; classes: "
            + ", ".join(f"{c['label']} phi={c['occupancy']:.3f} n={len(c['rate_array'])}" for c in classes) + ")\n\n")
    f.write(res.round(1).to_markdown(index=False) + "\n")
print(stats_df.round(3).to_string(index=False)); print(res.round(1).to_string(index=False))

# ------------------------------------------------------------------ figure
fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.6))
ax = axes[0]
mk = {"CMS": ("o", "tab:blue"), "Operational": ("s", "tab:orange"), "Flyover": ("*", "tab:red")}
for kind, g in ev.groupby("obs_kind"):
    m, c = mk.get(kind, ("o", "grey"))
    ax.scatter(g.rate, g.duration, marker=m, s=160 if kind == "Flyover" else 28, c=c, alpha=0.8,
               label=f"{kind} ({'PRE' if kind != 'Operational' else 'RE'}, n={len(g)})")
r1 = stats_df[stats_df["sample"] == "CS2: CMS-derived PREs"].iloc[0]; r0 = stats_df.iloc[0]
ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel("event rate (kg h$^{-1}$)"); ax.set_ylabel("event duration (h)")
ax.set_title("(a) Case Study 2, Site A", loc="left")
ax.text(0.03, 0.03, f"CMS PREs: Spearman ρ = {r1.spearman_rho:+.2f} (p = {r1.p_value:.2f})\n"
        f"all events: ρ = {r0.spearman_rho:+.2f} (p = {r0.p_value:.3f})", transform=ax.transAxes, fontsize=8.5,
        va="bottom", bbox=dict(fc="white", ec="0.7"))
ax.legend(fontsize=8, loc="upper left"); ax.grid(alpha=0.3, which="both", lw=0.4)
ax = axes[1]
r2 = stats_df[stats_df["sample"] == "CS1: Carbon Mapper events"].iloc[0]
ax.scatter(cs1.rate, cs1.duration, s=10, c="tab:green", alpha=0.5)
ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel("event rate (kg h$^{-1}$)"); ax.set_ylabel("event duration (h)")
ax.set_title("(b) Case Study 1, Carbon Mapper events", loc="left")
ax.text(0.03, 0.03, f"n = {int(r2.n)}: Spearman ρ = {r2.spearman_rho:+.2f} (p = {r2.p_value:.1e})",
        transform=ax.transAxes, fontsize=8.5, va="bottom", bbox=dict(fc="white", ec="0.7"))
ax.grid(alpha=0.3, which="both", lw=0.4)
fig.tight_layout(); fig.savefig(f"{OUT}/rate_duration_pairs.png", dpi=200)
print("figure written")

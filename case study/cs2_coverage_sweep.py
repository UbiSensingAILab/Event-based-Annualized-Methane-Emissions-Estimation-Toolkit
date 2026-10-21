"""
Case Study 2: does reduced monitoring coverage produce appropriately wider uncertainty? (reviewer comment 7)

The monitored period of Site A is truncated at the end of month 1, 2, ..., 7 (the data cover 1 January to
31 July 2024). Events observed before the cut-off are kept (clipped to it; the flyover-only PRE keeps its
detection-conditioned duration capped at the cut-off), the below-MDL simulation runs over the monitored
gap hours, and the remainder of the year is extrapolated with the alternating renewal process. The
event occupancy, the fitted rate/duration distributions and the measured bands are recomputed for each
cut-off. Reports the annual total, its 95 % interval and the relative width.

Also reports Monte Carlo convergence and computational cost of the two simulations at the full coverage
(MC = 1,000 ... 20,000). Outputs: cs2_outputs/cs2_coverage_sweep.{csv,md,png}, cs2_outputs/cs2_mc_convergence.csv
"""
import os, sys, time, platform, multiprocessing as mp
try: mp.set_start_method("fork", force=True)
except RuntimeError: pass
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); APP = os.path.join(os.path.dirname(HERE), "EAMEET_v1")
OUT = os.path.join(HERE, "cs2_outputs"); sys.path.insert(0, APP)
from simulations import simulate_below_mdl, extrapolation
from utils import fitting_distribution

YEAR_START = pd.Timestamp("2024-01-01 00:00:00"); YEAR_END = pd.Timestamp("2024-12-31 23:59:59")
CMS_DUR_MULT = (0.5, 2.0); CMS_TECH = "Qube"; UNC_PCT = {"CMS": 0.40, "Mixed": 0.40, "Flyover": 0.25, "Operational": 0.30}
BOOT_FIT = "weibull"; SEED_UE = 99
BASE = pd.read_csv(os.path.join(HERE, "emission_events_case_study_2.csv"))
BASE["st"] = pd.to_datetime(BASE["startTime"], format="ISO8601"); BASE["en"] = pd.to_datetime(BASE["endTime"], format="ISO8601")


def annualize(events, mon_end, mc=10_000, seed=SEED_UE):
    ev = events.copy(); mon_h = (mon_end - YEAR_START).total_seconds() / 3600
    m_lo, m_hi = CMS_DUR_MULT; rss = lambda a: float(np.sqrt(np.sum(np.asarray(a, float) ** 2)))
    rel_q = np.where(np.isfinite(ev["uncertainties"] / ev["rate"]), ev["uncertainties"] / ev["rate"],
                     ev["obs_kind"].map(UNC_PCT)).astype(float)
    pt = (ev["rate"] * ev["duration"]).to_numpy(float)
    cms_m = ev["duration_uncertainty_applied"].astype(bool).to_numpy(); fly_m = ev["start_end_simulated"].astype(bool).to_numpy()
    re_m = (ev["event_type"] == "RE").to_numpy()
    rdu = np.where(cms_m, m_hi - 1, np.where(fly_m, np.maximum(0, ev["rate"] * ev["sim_duration_hi"] - pt) / np.where(pt > 0, pt, 1), 0.0))
    rdd = np.where(cms_m, 1 - m_lo, np.where(fly_m, np.maximum(0, pt - ev["rate"] * ev["sim_duration_lo"]) / np.where(pt > 0, pt, 1), 0.0))
    up = pt * np.sqrt(rel_q ** 2 + rdu ** 2); dn = pt * np.sqrt(rel_q ** 2 + rdd ** 2)
    measured, m_up, m_dn = float(pt.sum()), rss(up), rss(dn)
    e1 = ev.copy(); e1["source"] = "A"
    e1["start_time"] = e1["st"].dt.strftime("%Y-%m-%d %H:%M:%S"); e1["end_time"] = e1["en"].dt.strftime("%Y-%m-%d %H:%M:%S")
    e1["quantity"] = pt
    np.random.seed(seed); t0 = time.time()
    r = simulate_below_mdl(e1, YEAR_START, mon_end, mc_iterations=mc, technologies=[CMS_TECH], consider_wind=False)
    ue1, ue1_lo, ue1_hi = r[6], r[7], r[8]; t1 = time.time() - t0
    rates = ev["rate"].to_numpy(float); durs = ev["duration"].to_numpy(float)
    phi = min(1.0, float(durs.sum()) / mon_h)
    rate_fit = {"type": BOOT_FIT, "params": fitting_distribution(rates, BOOT_FIT), "min": 0}
    dur_fit = {"type": BOOT_FIT, "params": fitting_distribution(durs, BOOT_FIT), "min": 0}
    np.random.seed(seed); t0 = time.time()
    b = np.asarray(extrapolation({"UNKNOWN": phi}, {"UNKNOWN": rates}, {"UNKNOWN": durs}, mon_end, YEAR_END, mc,
                                 fitted_rate_dist=rate_fit, fitted_duration_dist=dur_fit)["UNKNOWN"], float)
    ue2, ue2_lo, ue2_hi = float(np.median(b)), float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5)); t2 = time.time() - t0
    total = measured + ue1 + ue2
    dn_t = float(np.sqrt(m_dn ** 2 + (ue1 - ue1_lo) ** 2 + (ue2 - ue2_lo) ** 2)); up_t = float(np.sqrt(m_up ** 2 + (ue1_hi - ue1) ** 2 + (ue2_hi - ue2) ** 2))
    return dict(measured=measured, ue1=ue1, ue1_lo=ue1_lo, ue1_hi=ue1_hi, ue2=ue2, ue2_lo=ue2_lo, ue2_hi=ue2_hi, phi=phi,
                total=total, total_lo=total - dn_t, total_hi=total + up_t, n_events=len(ev), sec_type1=t1, sec_type2=t2,
                mc_se_ue2=1.2533 * float(np.std(b)) / np.sqrt(mc))


def truncate(cut):
    ev = BASE[BASE["st"] < cut].copy()
    over = ev["en"] > cut
    ev.loc[over, "en"] = cut; ev["duration"] = (ev["en"] - ev["st"]).dt.total_seconds() / 3600
    ev["quantity"] = ev["rate"] * ev["duration"]
    for c in ("sim_duration_lo", "sim_duration_hi"):
        ev[c] = np.minimum(ev[c].astype(float), ev["duration"]) if c in ev else np.nan
    ev["sim_duration_hi"] = np.where(ev["start_end_simulated"].astype(bool), np.minimum(BASE.loc[ev.index, "sim_duration_hi"].astype(float), ev["duration"]), np.nan)
    ev["sim_duration_lo"] = np.where(ev["start_end_simulated"].astype(bool), np.minimum(BASE.loc[ev.index, "sim_duration_lo"].astype(float), ev["duration"]), np.nan)
    return ev


if __name__ == "__main__":
    rows = []
    for months in range(1, 8):
        cut = (YEAR_START + pd.DateOffset(months=months)) - pd.Timedelta(seconds=1)
        ev = truncate(cut); r = annualize(ev, cut)
        rows.append(dict(months=months, monitored_end=cut.date(), n_events=r["n_events"], phi=r["phi"],
                         measured_t=r["measured"] / 1000, ue1_t=r["ue1"] / 1000, ue2_t=r["ue2"] / 1000,
                         total_t=r["total"] / 1000, lo_t=r["total_lo"] / 1000, hi_t=r["total_hi"] / 1000,
                         rel_width=(r["total_hi"] - r["total_lo"]) / r["total"], ue2_share=r["ue2"] / r["total"]))
        print(rows[-1], flush=True)
    df = pd.DataFrame(rows); df.to_csv(os.path.join(OUT, "cs2_coverage_sweep.csv"), index=False)
    L = ["| Months monitored | Events | Occupancy | Measured (t) | Type 1 UE (t) | Type 2 UE (t) | Annual total (t) [95 % interval] | Relative width | Type 2 share |", "|---|---|---|---|---|---|---|---|---|"]
    for _, r in df.iterrows():
        L.append(f"| {r.months} (to {r.monitored_end}) | {r.n_events} | {r.phi:.3f} | {r.measured_t:.1f} | {r.ue1_t:.1f} | {r.ue2_t:.1f} | {r.total_t:.1f} [{r.lo_t:.0f}, {r.hi_t:.0f}] | {r.rel_width:.2f} | {r.ue2_share:.0%} |")
    open(os.path.join(OUT, "cs2_coverage_sweep.md"), "w").write("\n".join(L) + "\n"); print("\n".join(L))
    fig, ax = plt.subplots(figsize=(7, 4)); ax.errorbar(df.months, df.total_t, yerr=[df.total_t - df.lo_t, df.hi_t - df.total_t], fmt="o-", capsize=4)
    ax2 = ax.twinx(); ax2.plot(df.months, df.rel_width, "s--", color="C3"); ax2.set_ylabel("relative width of 95 % interval", color="C3")
    ax.set_xlabel("months of CMS monitoring (remainder extrapolated)"); ax.set_ylabel("annual total (t), 95 % interval")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "cs2_coverage_sweep.png"), dpi=150)

    # Monte Carlo convergence / cost at full coverage
    cut = pd.Timestamp("2024-07-31 23:59:59"); ev = truncate(cut); conv = []
    for mc in [1000, 2000, 5000, 10000, 20000]:
        r = annualize(ev, cut, mc=mc)
        conv.append(dict(MC=mc, ue1_t=r["ue1"] / 1000, ue1_lo_t=r["ue1_lo"] / 1000, ue1_hi_t=r["ue1_hi"] / 1000, sec_type1=round(r["sec_type1"], 1),
                         ue2_t=r["ue2"] / 1000, ue2_lo_t=r["ue2_lo"] / 1000, ue2_hi_t=r["ue2_hi"] / 1000, sec_type2=round(r["sec_type2"], 1),
                         mc_se_ue2_t=r["mc_se_ue2"] / 1000, total_t=r["total"] / 1000, lo_t=r["total_lo"] / 1000, hi_t=r["total_hi"] / 1000))
        print(conv[-1], flush=True)
    cdf = pd.DataFrame(conv); cdf["machine"] = f"{platform.machine()}, {os.cpu_count()} cores, python {platform.python_version()}"
    cdf.to_csv(os.path.join(OUT, "cs2_mc_convergence.csv"), index=False); print(cdf.round(2).to_string(index=False))

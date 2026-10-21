"""Case Study 2 sensitivity analyses (reviewer comment 2: "show how these choices affect the annual total").

Every scenario re-runs the FULL pipeline (measured bands with Eq. 6 + below-MDL + bootstrap + total),
because the flyover-PRE duration also feeds the below-MDL simulation and the bootstrap (occupancy and
the fitted duration distribution), not only the measured term.

Scenario groups
  A. Duration-model assumptions for the flyover-only PRE (re-simulated with sample_conditional_duration):
     p_max of the null-repair rate (Fox et al. 2021 Eq. S1), the per-day misreading of NRR used by
     EAMEET v1.0 before this revision, LPR halved/doubled, the succeeding cap (end of monitored window vs
     last detection + 90 d), and the validity (POD) of the null detections.
  B. CMS duration-multiplier range: 0.5-2x (~87 % interval of Daniels et al. 2024) vs 0.4-2.5x (~95 %).
  C. Structural: leave the flyover PRE out; cap its duration at 7 / 14 / 30 / 60 d.

Reads the regenerated baseline events (emission_events_case_study_2.csv) and the observation workbook
(for the null-detection chain). The "Baseline" scenario reproduces the notebook total as a check.
Writes cs2_outputs/cs2_sensitivity.{csv,md,png}.
"""
import os, sys, multiprocessing as mp
try: mp.set_start_method("fork", force=True)
except RuntimeError: pass
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
APP  = os.path.join(os.path.dirname(HERE), "EAMEET_v1")
OUT  = os.path.join(HERE, "cs2_outputs")
sys.path.insert(0, APP)
from simulations import simulate_below_mdl, extrapolation, sample_conditional_duration, null_repair_rate
from utils import fitting_distribution

# ---- CONFIG (mirrors the notebook CONFIG cell) ----
MEASURED_START = pd.Timestamp("2024-01-01 00:00:00"); MEASURED_END = pd.Timestamp("2024-07-31 23:59:59")
BOOT_START     = pd.Timestamp("2024-08-01 00:00:00"); YEAR_END     = pd.Timestamp("2024-12-31 23:59:59")
CMS_DUR_MULT   = (0.5, 2.0); CMS_TECH = "Qube"; CONSIDER_WIND = False
UNC_PCT        = {"CMS": 0.40, "Flyover": 0.25, "Operational": 0.30}   # relative quantification uncertainty (Eq. 6)
MC_MEASURED    = 10_000; BOOT_FIT = "weibull"; MC_BOOT = 10_000; SEED_UE = 99
LPR = 0.006; P_MAX = 0.25; VISIT_INTERVAL_DAYS = 7; LEAKS_PER_SITE = 10; NULL_POD = {"ogi": 0.9, "flyover": 0.9}
N_DUR_SIM = 100_000; SND_EXTENSION_DAYS = 90

BASE = pd.read_csv(os.path.join(HERE, "emission_events_case_study_2.csv"))
FLY_IDX = BASE.index[BASE["start_end_simulated"].astype(bool)]
assert len(FLY_IDX) == 1, "expected exactly one flyover-only PRE"
Q_MAX_PRE = float(BASE.loc[BASE.event_type == "PRE", "rate"].max())

# Null-detection chain (nearest first) from the observation workbook
xls = pd.ExcelFile(os.path.join(HERE, "Data_from_case_study_2.xlsx"))
ogi, fly = xls.parse("OGI"), xls.parse("Flyover")
_nulls = ([(pd.to_datetime(r["survey time"]), "ogi") for _, r in ogi.iterrows() if not bool(r["detection"])] +
          [(pd.to_datetime(r["survey time"]), "flyover") for _, r in fly.iterrows() if not bool(r["detection"])])


def resim_flyover(events, p_max=P_MAX, lpr=LPR, cap="measured_end", pod=None, nrr_interval_days=VISIT_INTERVAL_DAYS,
                  nrr_override=None):
    """Re-simulate the flyover-only PRE duration under alternative assumptions and adopt the median."""
    e = events.copy(); i = FLY_IDX[0]; row = e.loc[i]
    t_first, t_last = pd.to_datetime(row["first_detection"]), pd.to_datetime(row["last_detection"])
    pod = NULL_POD if pod is None else {"ogi": pod, "flyover": pod}
    chain = sorted([(t, pod[k]) for t, k in _nulls if t < t_first], key=lambda x: x[0], reverse=True)
    t_pnd, pnd_pod = chain[0]; fallbacks = chain[1:]
    t_snd = MEASURED_END if cap == "measured_end" else t_last + pd.Timedelta(days=SND_EXTENSION_DAYS)
    rate = float(row["rate"])
    nrr = nrr_override if nrr_override is not None else null_repair_rate(
        lpr, rate, Q_MAX_PRE, p_max=p_max, visit_interval_days=VISIT_INTERVAL_DAYS, leaks_per_site=LEAKS_PER_SITE)
    r = sample_conditional_duration(t_first, t_last, t_pnd, t_snd, LPR=lpr, NRR=nrr, N=N_DUR_SIM, seed=0,
                                    pnd_pod=pnd_pod, pnd_fallbacks=fallbacks, pnd_floor=MEASURED_START,
                                    nrr_interval_days=nrr_interval_days)
    nd = r["sim_duration_h"]; st = r["sim_start_time"].floor("s")
    e.at[i, "duration"] = nd; e.at[i, "quantity"] = rate * nd
    e.at[i, "startTime"] = st.isoformat(); e.at[i, "endTime"] = (st + pd.to_timedelta(nd, unit="h")).floor("s").isoformat()
    e.at[i, "sim_duration_lo"] = r["sim_duration_lo"]; e.at[i, "sim_duration_hi"] = r["sim_duration_hi"]
    e.attrs["nrr"] = nrr; e.attrs["dur_h"] = nd
    return e


def annualize(events, cms_mult=CMS_DUR_MULT):
    events = events.copy(); m_lo, m_hi = cms_mult
    cms_m = events["duration_uncertainty_applied"].to_numpy(bool)
    fly_m = events["start_end_simulated"].to_numpy(bool)
    re_m  = (events["event_type"] == "RE").to_numpy(bool)
    rel_q = (events["uncertainties"] / events["rate"]).to_numpy(float)
    kind2 = {"CMS": UNC_PCT["CMS"], "Mixed": UNC_PCT["CMS"], "Flyover": UNC_PCT["Flyover"], "Operational": UNC_PCT["Operational"]}
    rel_q = np.where(np.isfinite(rel_q), rel_q, events["obs_kind"].map(kind2).to_numpy(float))
    def eq6(pt, rq, rdu, rdd): return pt*np.sqrt(rq**2+rdu**2), pt*np.sqrt(rq**2+rdd**2)
    rss = lambda a: float(np.sqrt(np.sum(np.asarray(a)**2)))
    # CMS PREs (Eq. 6 per event, RSS across events)
    cms_base = (events.loc[cms_m, "rate"] * events.loc[cms_m, "duration"]).to_numpy(float)
    cms_up_i, cms_dn_i = eq6(cms_base, rel_q[cms_m], m_hi-1.0, 1.0-m_lo)
    cms_meas = float(cms_base.sum()); cms_up, cms_dn = rss(cms_up_i), rss(cms_dn_i)
    # Flyover PRE
    fly_pt = events.loc[fly_m, "quantity"].to_numpy(float)
    fly_lo_i = (events.loc[fly_m,"rate"]*events.loc[fly_m,"sim_duration_lo"]).to_numpy(float)
    fly_hi_i = (events.loc[fly_m,"rate"]*events.loc[fly_m,"sim_duration_hi"]).to_numpy(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        fly_rup = np.where(fly_pt > 0, np.maximum(0.0, fly_hi_i-fly_pt)/fly_pt, 0.0)
        fly_rdn = np.where(fly_pt > 0, np.maximum(0.0, fly_pt-fly_lo_i)/fly_pt, 0.0)
    fly_up_i, fly_dn_i = eq6(fly_pt, rel_q[fly_m], fly_rup, fly_rdn)
    fly_meas = float(fly_pt.sum()); fly_up, fly_dn = rss(fly_up_i), rss(fly_dn_i)
    # REs (Eq. 3): quantification only
    re_pt = events.loc[re_m, "quantity"].to_numpy(float)
    re_fixed = float(re_pt.sum()); re_up = re_dn = rss(re_pt*rel_q[re_m])
    pre_up = float(np.sqrt(cms_up**2+fly_up**2)); pre_dn = float(np.sqrt(cms_dn**2+fly_dn**2))
    measured = re_fixed+cms_meas+fly_meas
    meas_dn = float(np.sqrt(re_dn**2+pre_dn**2)); meas_up = float(np.sqrt(re_up**2+pre_up**2))
    # below-MDL
    ev = events.copy(); ev["source"]=ev["sourceLocation"]
    ev["start_time"]=pd.to_datetime(ev["startTime"],format="ISO8601").dt.strftime("%Y-%m-%d %H:%M:%S")
    ev["end_time"]  =pd.to_datetime(ev["endTime"],  format="ISO8601").dt.strftime("%Y-%m-%d %H:%M:%S")
    np.random.seed(SEED_UE)
    res = simulate_below_mdl(ev, MEASURED_START, MEASURED_END, mc_iterations=MC_MEASURED,
                             technologies=[CMS_TECH], consider_wind=CONSIDER_WIND)
    ue_mdl, ue_mdl_lo, ue_mdl_hi = res[6], res[7], res[8]
    # bootstrap
    rates=events["rate"].to_numpy(float); durs=events["duration"].to_numpy(float)
    poe = min(1.0, float(durs.sum())/((MEASURED_END-MEASURED_START).total_seconds()/3600))
    rate_fit={"type":BOOT_FIT,"params":fitting_distribution(rates,BOOT_FIT),"min":0}
    dur_fit ={"type":BOOT_FIT,"params":fitting_distribution(durs, BOOT_FIT),"min":0}
    np.random.seed(SEED_UE)
    boot = extrapolation(prob_dist={"UNKNOWN":poe}, rate_dist={"UNKNOWN":rates},
                         duration_dist={"UNKNOWN":durs}, start_time=BOOT_START, end_time=YEAR_END,
                         MC=MC_BOOT, fitted_rate_dist=rate_fit, fitted_duration_dist=dur_fit)
    b=np.asarray(boot["UNKNOWN"],float)
    ue_boot, ue_boot_lo, ue_boot_hi = float(np.median(b)), float(np.percentile(b,2.5)), float(np.percentile(b,97.5))
    # totals: deviations combined in quadrature (Eqs. 12-13), as in the notebook
    total = measured+ue_mdl+ue_boot
    total_dn = float(np.sqrt(meas_dn**2 + (ue_mdl-ue_mdl_lo)**2 + (ue_boot-ue_boot_lo)**2))
    total_up = float(np.sqrt(meas_up**2 + (ue_mdl_hi-ue_mdl)**2 + (ue_boot_hi-ue_boot)**2))
    return dict(RE=re_fixed, CMS=cms_meas, FLY=fly_meas, FLY_lo=fly_meas-fly_dn, FLY_hi=fly_meas+fly_up,
                UE_mdl=ue_mdl, UE_boot=ue_boot, poe=poe, MEAS=measured, MEAS_lo=measured-meas_dn, MEAS_hi=measured+meas_up,
                TOTAL=total, TOTAL_lo=total-total_dn, TOTAL_hi=total+total_up,
                FLY_dur_h=float(events.loc[fly_m, "duration"].sum()) if fly_m.any() else 0.0,
                NRR=float(events.attrs.get("nrr", np.nan)))


def cap_flyover(events, cap_h):
    e = events.copy()
    for i in e.index[e["start_end_simulated"].astype(bool)]:
        st = pd.to_datetime(e.at[i,"startTime"]); nd = min(float(e.at[i,"duration"]), cap_h)
        e.at[i,"duration"]=nd; e.at[i,"quantity"]=e.at[i,"rate"]*nd
        e.at[i,"endTime"]=(st+pd.to_timedelta(nd,unit="h")).floor("s").isoformat()
        e.at[i,"sim_duration_lo"]=min(float(e.at[i,"sim_duration_lo"]), cap_h)
        e.at[i,"sim_duration_hi"]=min(float(e.at[i,"sim_duration_hi"]), cap_h)
    return e


SCENARIOS = [  # (group, label, events-builder, cms_mult)
    ("baseline", "Baseline (p_max 0.25, V 7 d, cap 31 Jul, POD 0.9, CMS 0.5-2x)", lambda: resim_flyover(BASE), CMS_DUR_MULT),
    ("A", "p_max = 0 (no size-dependent repair)",            lambda: resim_flyover(BASE, p_max=0.0), CMS_DUR_MULT),
    ("A", "p_max = 0.05",                                    lambda: resim_flyover(BASE, p_max=0.05), CMS_DUR_MULT),
    ("A", "p_max = 0.10",                                    lambda: resim_flyover(BASE, p_max=0.10), CMS_DUR_MULT),
    ("A", "p_max = 0.50",                                    lambda: resim_flyover(BASE, p_max=0.50), CMS_DUR_MULT),
    ("A", "NRR read as per-day probability (p_max 0.5; EAMEET v1.0 before revision)",
          lambda: resim_flyover(BASE, p_max=0.50, nrr_interval_days=1.0), CMS_DUR_MULT),
    ("A", "LPR x 0.5 (0.003 d^-1)",                          lambda: resim_flyover(BASE, lpr=0.003), CMS_DUR_MULT),
    ("A", "LPR x 2 (0.012 d^-1)",                            lambda: resim_flyover(BASE, lpr=0.012), CMS_DUR_MULT),
    ("A", "Cap = last detection + 90 d",                     lambda: resim_flyover(BASE, cap="extension"), CMS_DUR_MULT),
    ("A", "Null-detection POD = 1.0 (hard bounds)",          lambda: resim_flyover(BASE, pod=1.0), CMS_DUR_MULT),
    ("A", "Null-detection POD = 0.5",                        lambda: resim_flyover(BASE, pod=0.5), CMS_DUR_MULT),
    ("B", "CMS multiplier 0.4-2.5x (~95 % interval)",        lambda: resim_flyover(BASE), (0.4, 2.5)),
    ("C", "Drop flyover PRE (leave-one-out)",                lambda: BASE[~BASE.start_end_simulated.astype(bool)].copy(), CMS_DUR_MULT),
    ("C", "Cap flyover duration at 7 d",                     lambda: cap_flyover(resim_flyover(BASE), 7*24), CMS_DUR_MULT),
    ("C", "Cap flyover duration at 14 d",                    lambda: cap_flyover(resim_flyover(BASE), 14*24), CMS_DUR_MULT),
    ("C", "Cap flyover duration at 30 d",                    lambda: cap_flyover(resim_flyover(BASE), 30*24), CMS_DUR_MULT),
    ("C", "Cap flyover duration at 60 d",                    lambda: cap_flyover(resim_flyover(BASE), 60*24), CMS_DUR_MULT),
]

rows = []
for grp, label, build, cms_mult in SCENARIOS:
    ev = build()
    res = annualize(ev, cms_mult)
    rows.append({"group": grp, "scenario": label, **res})
    print(f"[{grp}] {label:70s} FLY {res['FLY']/1000:6.1f} t  TOTAL {res['TOTAL']/1000:7.1f} t "
          f"[{res['TOTAL_lo']/1000:.0f}, {res['TOTAL_hi']/1000:.0f}]", flush=True)

df = pd.DataFrame(rows)
for c in ["RE","CMS","FLY","FLY_lo","FLY_hi","UE_mdl","UE_boot","MEAS","MEAS_lo","MEAS_hi","TOTAL","TOTAL_lo","TOTAL_hi"]:
    df[c+"_t"] = df[c]/1000
df.to_csv(os.path.join(OUT, "cs2_sensitivity.csv"), index=False)

# ---- markdown table (SI) ----
base = df.iloc[0]
L = ["| Scenario | NRR per visit | Flyover PRE duration (h) | Flyover PRE (t), 95 % interval | Measured RE+PRE (t) | Annual total (t), 95 % interval | Change in total |",
     "|---|---|---|---|---|---|---|"]
for _, r in df.iterrows():
    nrr = "-" if not np.isfinite(r["NRR"]) else f"{r['NRR']:.3f}"
    L.append(f"| {r['scenario']} | {nrr} | {r['FLY_dur_h']:,.0f} | {r['FLY_t']:.1f} [{r['FLY_lo_t']:.1f}, {r['FLY_hi_t']:.1f}] | "
             f"{r['MEAS_t']:.1f} | {r['TOTAL_t']:.1f} [{r['TOTAL_lo_t']:.0f}, {r['TOTAL_hi_t']:.0f}] | "
             f"{(r['TOTAL']/base['TOTAL']-1)*100:+.0f} % |")
open(os.path.join(OUT, "cs2_sensitivity.md"), "w").write("\n".join(L) + "\n")
pd.set_option("display.width", 220, "display.max_columns", 30)
print("\n" + "\n".join(L))

# ---- figure ----
comp=["RE","CMS","FLY","UE_mdl","UE_boot"]; labels=["RE (operational)","PRE CMS","PRE Flyover","UE below-MDL","UE bootstrap"]
colors=["#4C72B0","#DD8452","#CC6677","#C44E52","#8172B3"]
x=np.arange(len(df)); fig,ax=plt.subplots(figsize=(14,6.5)); bottom=np.zeros(len(df))
for c,lab,col in zip(comp,labels,colors):
    v=df[c].to_numpy()/1000; ax.bar(x,v,bottom=bottom,label=lab,color=col,edgecolor="black",lw=0.4); bottom+=v
tot=df["TOTAL"].to_numpy()/1000
ax.errorbar(x, tot, yerr=[tot-df["TOTAL_lo"].to_numpy()/1000, df["TOTAL_hi"].to_numpy()/1000-tot],
            fmt="none", ecolor="black", capsize=4, lw=1.1)
for xi,t in zip(x,tot): ax.text(xi, t+40, f"{t:,.0f}", ha="center", va="bottom", fontsize=8, fontweight="bold")
short = [s.split(" (")[0] if len(s) > 34 else s for s in df["scenario"]]
ax.set_xticks(x); ax.set_xticklabels(short, rotation=35, ha="right", fontsize=8)
ax.set_ylabel("Emissions (tonnes)"); ax.set_title("Case Study 2 - sensitivity of the annual total to the duration assumptions")
ax.legend(fontsize=8, loc="upper right"); fig.tight_layout()
fig.savefig(os.path.join(OUT,"cs2_sensitivity.png"), dpi=150)
print("\nwrote cs2_outputs/cs2_sensitivity.{csv,md,png}")

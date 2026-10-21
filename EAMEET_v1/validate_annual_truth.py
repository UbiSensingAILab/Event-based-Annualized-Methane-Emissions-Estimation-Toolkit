"""
Synthetic-truth validation of EAMEET v1.0 annual estimates (reviewer comment 7).

Full-year emission histories with KNOWN integrated mass are generated for a synthetic site, observations
are simulated from them with specified sampling and detection behaviour, and EAMEET is run on the
observations alone (it never sees the hidden history). Bias, error and empirical 95 %-interval coverage
are reported against a simple baseline (persistence-weighted mean-rate annualization).

Truth scenarios (3 equipment units per site; year 2024):
  persistent     one long leak per unit (onset uniform in the year, duration median 60 d), nothing else
  intermittent   Poisson arrivals of short, large events (median 6 h, median 150 kg/h) over a 0.5 kg/h baseline
  seasonal       as 'intermittent', with the arrival intensity and rates modulated (+/- 80 %) by a winter-peaking
                 annual cycle
  concurrent     three independent alternating-renewal units with heavy overlap (occupancy 0.4 each)
  renewal        one unit, alternating renewal with Weibull durations and lognormal rates (the assumed model)

Observation designs:
  cms_full       CMS on every unit all year (Type 1 simulation only)
  cms_campaign   CMS January-July, August-December extrapolated (Type 2 renewal), i.e. Case Study 2
  fly_monthly    facility-scale snapshot survey every 30 d (12 per year), Case Study 1 pipeline
  fly_bimonthly  snapshot survey every 61 d (6 per year)
CMS: an event is detected with POD(Q) = 0.9 / (1 + (MDL/Q)^2.2) (MDL 2 kg/h), its rate is reported with a
40 % lognormal error and its duration with a lognormal error whose 95 % range is 0.5-2x; events of one unit
that overlap in time are reported as one alarm. Snapshot: the site rate at the survey instant is detected with
the same POD form (MDL 10 kg/h) and reported with a 25 % error; a miss is a null detection.
Baseline: snapshot designs -> mean detected rate x (detections / surveys) x hours in year; CMS designs ->
observed alarm mass per monitored hour x hours in year.

Sweeps (reviewer comment 7, Case Study 2): monitored-period length 1-12 months (does reduced coverage widen
the interval?) and the CMS detection model assumed by EAMEET (flat POD 0.9; MDL-gated at the true MDL;
MDL-gated at 2.5x the true MDL).

Usage:  python validate_annual_truth.py [--reps 20] [--out validation_outputs] [--quick]
Outputs: annual_truth_replicates.csv, annual_truth_summary.csv, coverage_sweep.csv,
         detection_model_sweep.csv, annual_truth_validation.png, coverage_sweep.png, run_metadata.json
"""
import argparse, json, os, platform, sys, time
import multiprocessing as mp
try:
    mp.set_start_method("fork", force=True)
except RuntimeError:
    pass
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from emission_event_converter import convert_to_emission_event_model
from annualize import annualize_cms, annualize_snapshot, HOURS

Y0, Y1 = pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")
YEAR_H = HOURS(Y0, Y1)
UNITS = ["Unit-1", "Unit-2", "Unit-3"]
CMS_MDL, FLY_MDL, PLATEAU, K = 2.0, 10.0, 0.9, 2.2


def pod(q, mdl):
    q = max(float(q), 1e-9)
    return PLATEAU / (1.0 + np.exp(-K * np.log10(q / mdl)))


# ------------------------------------------------------------------ truth generators -> list of (unit, start_h, end_h, rate)
def _renewal_unit(rng, unit, occupancy, dur_shape, dur_scale, rate_med, rate_sig, total_h=YEAR_H, rate_mod=None):
    mean_d = dur_scale * __import__("math").gamma(1 + 1 / dur_shape)
    mean_g = mean_d * (1 - occupancy) / occupancy
    t, out = -rng.exponential(mean_g), []
    while t < total_h:
        t += rng.exponential(mean_g)
        d = dur_scale * rng.weibull(dur_shape)
        if t >= total_h:
            break
        q = rate_med * np.exp(rng.normal(0, rate_sig)) * (rate_mod(t) if rate_mod else 1.0)
        out.append((unit, max(t, 0.0), min(t + d, total_h), q)); t += d
    return out


def truth_persistent(rng):
    ev = []
    for u in UNITS:
        s = rng.uniform(0, YEAR_H); d = 24 * 60 * np.exp(rng.normal(0, 0.6))
        ev.append((u, s, min(s + d, YEAR_H), 15 * np.exp(rng.normal(0, 0.8))))
    return ev


def _poisson_events(rng, lam_per_year, intensity=None, rate_mod=None):
    ev, t = [], 0.0
    lam_h = lam_per_year / YEAR_H
    lam_max = lam_h * 1.8
    while True:                                       # thinning for a time-varying intensity
        t += rng.exponential(1 / lam_max)
        if t >= YEAR_H:
            break
        if intensity is not None and rng.random() > intensity(t) / 1.8:
            continue
        d = 6 * np.exp(rng.normal(0, 1.0)); q = 150 * np.exp(rng.normal(0, 1.0)) * (rate_mod(t) if rate_mod else 1.0)
        ev.append((UNITS[rng.integers(3)], t, min(t + d, YEAR_H), q))
    return ev


def truth_intermittent(rng):
    return [("Unit-1", 0.0, YEAR_H, 0.5)] + _poisson_events(rng, 25)


def truth_seasonal(rng):
    season = lambda t: 1 + 0.8 * np.cos(2 * np.pi * (t - 15 * 24) / YEAR_H)   # peak mid-January
    return [("Unit-1", 0.0, YEAR_H, 0.5)] + _poisson_events(rng, 25, intensity=season, rate_mod=season)


def truth_concurrent(rng):
    ev = []
    for u in UNITS:
        ev += _renewal_unit(rng, u, 0.4, 0.7, 20.0, 20.0, 0.9)
    return ev


def truth_renewal(rng):
    return _renewal_unit(rng, "Unit-1", 0.3, 0.6, 15.0, 20.0, 1.0)


SCENARIOS = {"persistent": truth_persistent, "intermittent": truth_intermittent, "seasonal": truth_seasonal,
             "concurrent": truth_concurrent, "renewal": truth_renewal}


def truth_mass(ev):
    return float(sum((e - s) * q for _, s, e, q in ev))


def site_rate_at(ev, t):
    return float(sum(q for _, s, e, q in ev if s <= t < e))


# ------------------------------------------------------------------ observation models
def observe_cms(ev, rng, mon_start_h, mon_end_h, rate_cv=0.40, dur_sig=np.log(2) / 1.96):
    """CMS alarms per unit inside [mon_start_h, mon_end_h): merge overlapping true events of a unit, detect
    with POD(Q), report rate with lognormal error (CV ~ rate_cv) and duration with lognormal error."""
    rows = []
    for u in UNITS:
        iv = sorted([(max(s, mon_start_h), min(e, mon_end_h), q) for uu, s, e, q in ev if uu == u and e > mon_start_h and s < mon_end_h])
        merged = []
        for s, e, q in iv:                            # concurrent events on one unit -> one true episode
            if merged and s < merged[-1][1]:
                ps, pe, pq = merged[-1]; ne = max(pe, e)
                merged[-1] = (ps, ne, (pq * (pe - ps) + q * (e - s)) / (ne - ps))
            else:
                merged.append((s, e, q))
        for n, (s, e, q) in enumerate(merged):
            if e - s <= 0 or rng.random() > pod(q, CMS_MDL):
                continue
            q_rep = q * np.exp(rng.normal(0, np.sqrt(np.log(1 + rate_cv ** 2))))
            d_rep = (e - s) * np.exp(rng.normal(0, dur_sig))
            st = Y0 + pd.Timedelta(hours=s); en = min(st + pd.Timedelta(hours=d_rep), Y0 + pd.Timedelta(hours=mon_end_h))
            if en <= st:
                en = st + pd.Timedelta(minutes=5)
            rows.append(dict(id=f"{u}-CMS-{n}", source=u, rate=q_rep, unc=0.4 * q_rep, start=st, end=en, time=st,
                             obs_type="cms", scale="equipment", feature=u))
    return pd.DataFrame(rows)


def observe_snapshot(ev, rng, every_days, rate_cv=0.25):
    rows, k, m = [], 0, 0
    t = rng.uniform(0, every_days * 24)               # random phase of the survey schedule
    n = 0
    while t < YEAR_H:
        q = site_rate_at(ev, t); m += 1
        ts = Y0 + pd.Timedelta(hours=t)
        if q > 0 and rng.random() < pod(q, FLY_MDL):
            k += 1
            q_rep = q * np.exp(rng.normal(0, np.sqrt(np.log(1 + rate_cv ** 2))))
            rows.append(dict(id=f"FLY-{n}", source="Site", rate=q_rep, unc=rate_cv * q_rep, start=None, end=None,
                             time=ts, obs_type="flyover", scale="site", feature="Site"))
        else:
            rows.append(dict(id=f"NULL-{n}", source="Site", rate=0.0, unc=0.0, start=None, end=None, time=ts,
                             obs_type="flyover", scale="site", feature="Site"))
        t += every_days * 24; n += 1
    return pd.DataFrame(rows), k, m


MAPPING = {"id": "id", "rate": "rate", "source": "source", "uncertainties": "unc", "start_time": "start",
           "end_time": "end", "time": "time", "observation_type": "obs_type", "observation_scale": "scale",
           "feature": "feature"}


# ------------------------------------------------------------------ estimators (blind: observations only)
def estimate_cms(obs, mon_start_h, mon_end_h, seed, mc=1000, **kw):
    ms, me = Y0 + pd.Timedelta(hours=mon_start_h), Y0 + pd.Timedelta(hours=mon_end_h)
    if len(obs) == 0:
        events = pd.DataFrame(columns=["rate", "duration", "quantity", "startTime", "endTime", "sourceLocation"])
    else:
        events = convert_to_emission_event_model(obs, MAPPING, time_column="time", emission_characteristics="intermittent")
    r = annualize_cms(events, ms, me, Y0, Y1, mc_type1=mc, mc_type2=mc, seed=seed, **kw)
    mass_obs = float((events["rate"] * events["duration"]).sum()) if len(events) else 0.0
    r["baseline"] = mass_obs / (mon_end_h - mon_start_h) * YEAR_H
    return r


def estimate_snapshot(obs, k, m, seed, duration_model="bracket", n_outer=1000):
    det = obs[obs.rate > 0]
    base = (det.rate.mean() * (k / m) * YEAR_H) if k > 0 else 0.0
    if k == 0:
        return dict(total=0.0, total_lo=0.0, total_hi=0.0, pre=0.0, ue=0.0, baseline=0.0, n_events=0, seconds=0.0)
    events = convert_to_emission_event_model(obs, MAPPING, time_column="time", emission_characteristics="intermittent")
    r = annualize_snapshot(events, obs, Y0, Y1, k, m, duration_model=duration_model, n_outer=n_outer, seed=seed)
    r["baseline"] = base
    return r


DESIGNS = {
    "cms_full": dict(kind="cms", mon=(0.0, YEAR_H)),
    "cms_campaign": dict(kind="cms", mon=(0.0, HOURS(Y0, "2024-08-01"))),
    "cms_campaign_byclass": dict(kind="cms", mon=(0.0, HOURS(Y0, "2024-08-01")), kw=dict(type2="by_class")),
    "fly_monthly": dict(kind="fly", every=30.0),
    "fly_bimonthly": dict(kind="fly", every=61.0),
}


def run_replicate(scenario, design, rep, mc=1000, cms_kw=None, duration_model="bracket"):
    rng = np.random.default_rng(1000 * list(SCENARIOS).index(scenario) + rep)
    ev = SCENARIOS[scenario](rng); truth = truth_mass(ev)
    d = DESIGNS[design]; t0 = time.time()
    if d["kind"] == "cms":
        obs = observe_cms(ev, rng, *d["mon"])
        r = estimate_cms(obs, *d["mon"], seed=rep, mc=mc, **{**d.get("kw", {}), **(cms_kw or {})})
        n_obs = len(obs)
    else:
        obs, k, m = observe_snapshot(ev, rng, d["every"])
        r = estimate_snapshot(obs, k, m, seed=rep, duration_model=duration_model, n_outer=mc)
        n_obs = int(k)
    return dict(scenario=scenario, design=design, rep=rep, truth_t=truth / 1000, est_t=r["total"] / 1000,
                lo_t=r["total_lo"] / 1000, hi_t=r["total_hi"] / 1000, baseline_t=r["baseline"] / 1000,
                covered=bool(r["total_lo"] <= truth <= r["total_hi"]), n_obs=n_obs,
                rel_err=(r["total"] - truth) / truth, rel_err_baseline=(r["baseline"] - truth) / truth,
                rel_width=(r["total_hi"] - r["total_lo"]) / truth, seconds=time.time() - t0,
                n_events=r.get("n_events", np.nan))


def summarize(df, by):
    g = df.groupby(by)
    out = pd.DataFrame({
        "n": g.size(),
        "truth_t_median": g.truth_t.median(),
        "bias_pct": 100 * g.rel_err.mean(), "mae_pct": 100 * g.rel_err.apply(lambda x: x.abs().mean()),
        "rmse_pct": 100 * g.rel_err.apply(lambda x: np.sqrt(np.mean(x ** 2))),
        "median_rel_err_pct": 100 * g.rel_err.median(),
        "coverage_95": g.covered.mean(), "rel_width_median": g.rel_width.median(),
        "baseline_bias_pct": 100 * g.rel_err_baseline.mean(), "baseline_mae_pct": 100 * g.rel_err_baseline.apply(lambda x: x.abs().mean()),
        "replicates_without_detection": g.n_obs.apply(lambda x: int((x == 0).sum())),
        "seconds_per_replicate": g.seconds.mean(),
    }).reset_index()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=20); ap.add_argument("--mc", type=int, default=1000)
    ap.add_argument("--out", default=os.path.join(HERE, "validation_outputs")); ap.add_argument("--quick", action="store_true")
    ap.add_argument("--only", default="all", choices=["all", "grid", "coverage", "detection"])
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    reps = 2 if a.quick else a.reps; mc = 200 if a.quick else a.mc
    T0 = time.time()

    # 1. main grid
    rows = []
    for sc in (SCENARIOS if a.only in ("all", "grid") else []):
        for ds in DESIGNS:
            for rep in range(reps):
                r = run_replicate(sc, ds, rep, mc=mc); rows.append(r)
                print(f"{sc:12s} {ds:13s} rep {rep:2d}  truth {r['truth_t']:8.1f} t  est {r['est_t']:8.1f} "
                      f"[{r['lo_t']:.0f}, {r['hi_t']:.0f}]  base {r['baseline_t']:8.1f}  {r['seconds']:.1f}s", flush=True)
            if not a.quick:   # the Case Study 2 style conditional duration model for the snapshot designs
                pass
    if rows:
        df = pd.DataFrame(rows); df.to_csv(os.path.join(a.out, "annual_truth_replicates.csv"), index=False)
        summ = summarize(df, ["scenario", "design"]); summ.to_csv(os.path.join(a.out, "annual_truth_summary.csv"), index=False)
        print(summ.round(3).to_string(index=False))
    else:
        summ = pd.read_csv(os.path.join(a.out, "annual_truth_summary.csv"))

    # 1b. snapshot designs with the detection-conditioned duration model (Section S3) instead of the bracket
    rows2 = []
    for sc in (SCENARIOS if a.only in ("all", "grid") else []):
        for ds in ("fly_monthly", "fly_bimonthly"):
            for rep in range(reps):
                r = run_replicate(sc, ds, rep, mc=mc, duration_model="conditional"); r["design"] = ds + "_cond"; rows2.append(r)
    if rows2:
        df2 = pd.DataFrame(rows2); df2.to_csv(os.path.join(a.out, "annual_truth_replicates_conditional.csv"), index=False)
        summ2 = summarize(df2, ["scenario", "design"]); summ2.to_csv(os.path.join(a.out, "annual_truth_summary_conditional.csv"), index=False)
        print(summ2.round(3).to_string(index=False))
    else:
        summ2 = pd.read_csv(os.path.join(a.out, "annual_truth_summary_conditional.csv"))

    # 2. coverage sweep: CMS monitored for 1..12 months, rest extrapolated
    rows = []
    for months in ([2, 6, 12] if a.quick else ([1, 2, 3, 4, 6, 8, 10, 12] if a.only in ("all", "coverage") else [])):
        me = HOURS(Y0, pd.Timestamp("2024-01-01") + pd.DateOffset(months=months))
        for sc in ("renewal", "intermittent", "persistent"):
            for rep in range(reps):
                rng = np.random.default_rng(5000 + rep); ev = SCENARIOS[sc](rng); truth = truth_mass(ev)
                obs = observe_cms(ev, rng, 0.0, me); r = estimate_cms(obs, 0.0, me, seed=rep, mc=mc)
                rows.append(dict(months=months, scenario=sc, rep=rep, truth_t=truth / 1000, est_t=r["total"] / 1000,
                                 lo_t=r["total_lo"] / 1000, hi_t=r["total_hi"] / 1000, ue2_t=r["ue2"] / 1000,
                                 covered=bool(r["total_lo"] <= truth <= r["total_hi"]),
                                 rel_err=(r["total"] - truth) / truth, rel_width=(r["total_hi"] - r["total_lo"]) / truth,
                                 rel_err_baseline=(r["baseline"] - truth) / truth))
        print(f"coverage sweep: {months} months done", flush=True)
    if rows:
        cov = pd.DataFrame(rows); cov.to_csv(os.path.join(a.out, "coverage_sweep_replicates.csv"), index=False)
    else:
        cov = pd.read_csv(os.path.join(a.out, "coverage_sweep_replicates.csv"))
    covs = cov.groupby(["scenario", "months"]).agg(n=("rep", "size"), bias_pct=("rel_err", lambda x: 100 * x.mean()),
                                                   mae_pct=("rel_err", lambda x: 100 * x.abs().mean()),
                                                   coverage_95=("covered", "mean"), rel_width_median=("rel_width", "median"),
                                                   ue2_share=("ue2_t", "mean")).reset_index()
    covs.to_csv(os.path.join(a.out, "coverage_sweep.csv"), index=False); print(covs.round(3).to_string(index=False))

    # 3. CMS detection model assumed by EAMEET (truth: MDL-gated POD at MDL 2 kg/h)
    rows = []
    models = {"flat POD 0.9 (default)": dict(technology="Qube", pod_model="flat"),
              "MDL-gated at true MDL (2 kg/h)": dict(technology="define_technology", mdl_define=2.0, pod_define=0.9, pod_model="mdl_gated"),
              "MDL-gated at 2.5x true MDL (5 kg/h)": dict(technology="define_technology", mdl_define=5.0, pod_define=0.9, pod_model="mdl_gated"),
              "flat POD 0.7": dict(technology="define_technology", mdl_define=2.0, pod_define=0.7, pod_model="flat"),
              "flat POD 0.9, site-specific component count (300 +/- 100)": dict(
                  technology="Qube", pod_model="flat", num_components=np.clip(np.random.default_rng(3).normal(300, 100, 10000), 1, None)),
              "MDL-gated at true MDL, site-specific component count (300 +/- 100)": dict(
                  technology="define_technology", mdl_define=2.0, pod_define=0.9, pod_model="mdl_gated",
                  num_components=np.clip(np.random.default_rng(3).normal(300, 100, 10000), 1, None))}
    for name, kw in (models.items() if a.only in ("all", "detection") else []):
        for sc in ("renewal", "intermittent"):
            for rep in range(reps):
                rng = np.random.default_rng(9000 + rep); ev = SCENARIOS[sc](rng); truth = truth_mass(ev)
                obs = observe_cms(ev, rng, 0.0, YEAR_H); r = estimate_cms(obs, 0.0, YEAR_H, seed=rep, mc=mc, **kw)
                rows.append(dict(model=name, scenario=sc, rep=rep, truth_t=truth / 1000, est_t=r["total"] / 1000,
                                 ue1_t=r["ue1"] / 1000, measured_t=r["measured"] / 1000,
                                 lo_t=r["total_lo"] / 1000, hi_t=r["total_hi"] / 1000,
                                 covered=bool(r["total_lo"] <= truth <= r["total_hi"]),
                                 rel_err=(r["total"] - truth) / truth, rel_width=(r["total_hi"] - r["total_lo"]) / truth))
        print(f"detection model '{name}' done", flush=True)
    if rows:
        dm = pd.DataFrame(rows); dm.to_csv(os.path.join(a.out, "detection_model_sweep_replicates.csv"), index=False)
    else:
        dm = pd.read_csv(os.path.join(a.out, "detection_model_sweep_replicates.csv"))
    dms = dm.groupby(["scenario", "model"]).agg(n=("rep", "size"), bias_pct=("rel_err", lambda x: 100 * x.mean()),
                                                mae_pct=("rel_err", lambda x: 100 * x.abs().mean()), coverage_95=("covered", "mean"),
                                                ue1_t_mean=("ue1_t", "mean"), measured_t_mean=("measured_t", "mean"),
                                                rel_width_median=("rel_width", "median")).reset_index()
    dms.to_csv(os.path.join(a.out, "detection_model_sweep.csv"), index=False); print(dms.round(3).to_string(index=False))

    # 4. figures
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    allsum = pd.concat([summ, summ2])
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    designs = list(DESIGNS) + ["fly_monthly_cond", "fly_bimonthly_cond"]; scen = list(SCENARIOS)
    x = np.arange(len(scen)); w = 0.8 / len(designs)
    for j, ds in enumerate(designs):
        s = allsum[allsum.design == ds].set_index("scenario").reindex(scen)
        axes[0].bar(x + (j - (len(designs) - 1) / 2) * w, s.bias_pct, w, label=ds)
        axes[1].bar(x + (j - (len(designs) - 1) / 2) * w, s.coverage_95, w, label=ds)
        axes[2].bar(x + (j - (len(designs) - 1) / 2) * w, s.rel_width_median, w, label=ds)
    for ax, t in zip(axes, ["Bias of the annual estimate (%)", "Empirical coverage of the 95 % interval", "Median relative width of the 95 % interval"]):
        ax.set_xticks(x); ax.set_xticklabels(scen, rotation=20); ax.set_title(t, fontsize=10); ax.axhline(0, color="k", lw=0.5)
    axes[1].axhline(0.95, color="r", ls="--", lw=0.8); axes[0].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(os.path.join(a.out, "annual_truth_validation.png"), dpi=150)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for sc, g in covs.groupby("scenario"):
        axes[0].plot(g.months, g.bias_pct, "o-", label=sc); axes[1].plot(g.months, g.rel_width_median, "o-", label=sc)
        axes[2].plot(g.months, g.coverage_95, "o-", label=sc)
    axes[0].set_ylabel("bias (%)"); axes[1].set_ylabel("median relative width of 95 % interval"); axes[2].set_ylabel("coverage")
    axes[2].axhline(0.95, color="r", ls="--", lw=0.8)
    for ax in axes:
        ax.set_xlabel("months monitored by CMS (rest extrapolated)"); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(a.out, "coverage_sweep.png"), dpi=150)

    meta = dict(reps=reps, mc=mc, total_minutes=(time.time() - T0) / 60, machine=f"{platform.machine()}, {os.cpu_count()} cores",
                python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__)
    json.dump(meta, open(os.path.join(a.out, "run_metadata.json"), "w"), indent=1); print(meta)


if __name__ == "__main__":
    main()

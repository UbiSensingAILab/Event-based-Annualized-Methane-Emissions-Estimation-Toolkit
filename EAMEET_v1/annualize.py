"""
Site-level annualization pipelines of EAMEET v1.0 as single functions (used by the synthetic-truth
validation harness `validate_annual_truth.py` and by the Case Study 2 coverage sweep).

annualize_cms()      -- the Case Study 2 pipeline: measured REs/PREs (Eqs. 3, 6, 10, 11), Type 1
                        below-detection simulation over the monitored period (simulate_below_mdl),
                        Type 2 alternating-renewal extrapolation over the unmonitored period
                        (extrapolation), totals and 95 % interval by quadrature (Eqs. 12, 13).
annualize_snapshot() -- the Case Study 1 pipeline for snapshot (flyover / satellite) records: PREs
                        bounded by null detections (optionally re-simulated with the detection-conditioned
                        duration model of Section S3), event occupancy from the detection record
                        (Section S9) and a joint Monte Carlo ensemble of PRE + renewal UE draws.
Both return a dict with the component medians, the 95 % interval of the total and run metadata.
"""
import os
import sys
import time
import numpy as np
import pandas as pd
from scipy.stats import weibull_min

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from simulations import (simulate_below_mdl, extrapolation, sample_conditional_duration, null_repair_rate,
                         simulate_renewal_emissions, simulate_renewal_emissions_by_class,
                         calculate_total_simulation_time_steps)
from utils import fitting_distribution
from occupancy import occupancy_posterior

HOURS = lambda a, b: (pd.Timestamp(b) - pd.Timestamp(a)).total_seconds() / 3600.0


def _rss(a):
    return float(np.sqrt(np.sum(np.asarray(a, float) ** 2)))


def _fit_or_empirical(values, fit="weibull", min_n=5):
    v = np.asarray(values, float); v = v[np.isfinite(v) & (v > 0)]
    if len(v) >= min_n and fit is not None:
        return {"type": fit, "params": fitting_distribution(v, fit), "min": 0}
    return None


def annualize_cms(events, monitored_start, monitored_end, year_start, year_end,
                  technology="Qube", mdl_define=None, pod_define=None, pod_model="flat", coverage=None,
                  rel_q=0.40, cms_dur_mult=(0.5, 2.0), mc_type1=1000, mc_type2=1000, fit="weibull",
                  seed=99, leak_data=None, type2="pooled", num_components=None):
    """
    Case Study 2 pipeline for a site observed by a continuous monitoring system (and operational records).

    events: DataFrame from convert_to_emission_event_model (columns rate, duration, quantity, startTime,
            endTime, sourceLocation, event_type optional). All PREs are treated as CMS-derived (duration
            multiplier `cms_dur_mult`); REs carry quantification uncertainty only.
    type2: "pooled" (default, Case Study 2): one renewal process for the site with pooled fitted marginals;
           "by_class": one renewal process per source feature (sourceLocation) with its own occupancy and its
           own observed (rate, duration) pairs (Section S4.2, class-stratified), summed over classes.
    Returns dict(measured, measured_lo, measured_hi, ue1, ue1_lo, ue1_hi, ue2, ue2_lo, ue2_hi, total,
                 total_lo, total_hi, phi, budget_h, seconds).
    """
    t0 = time.time()
    ev = events.copy()
    if len(ev) == 0:
        ev = pd.DataFrame(columns=["rate", "duration", "quantity", "startTime", "endTime", "sourceLocation"])
    ev["quantity"] = ev["rate"].astype(float) * ev["duration"].astype(float)
    is_re = ev["event_type"].eq("RE").to_numpy() if "event_type" in ev.columns else np.zeros(len(ev), bool)
    m_lo, m_hi = cms_dur_mult
    pt = ev["quantity"].to_numpy(float)
    up = np.where(is_re, pt * rel_q, pt * np.sqrt(rel_q ** 2 + (m_hi - 1.0) ** 2))
    dn = np.where(is_re, pt * rel_q, pt * np.sqrt(rel_q ** 2 + (1.0 - m_lo) ** 2))
    measured, meas_up, meas_dn = float(pt.sum()), _rss(up), _rss(dn)

    # Type 1: undetected emissions during the monitored period (gap hours of the coverage schedule)
    e1 = ev.copy()
    e1["source"] = "site"
    e1["start_time"] = pd.to_datetime(e1["startTime"], format="ISO8601").dt.strftime("%Y-%m-%d %H:%M:%S") if len(e1) else []
    e1["end_time"] = pd.to_datetime(e1["endTime"], format="ISO8601").dt.strftime("%Y-%m-%d %H:%M:%S") if len(e1) else []
    tech_name = "define_technology" if technology in ("define_technology", "User Defined") else technology
    cov = None if coverage is None else {tech_name: coverage}
    budget_h = calculate_total_simulation_time_steps(e1, pd.Timestamp(monitored_start), pd.Timestamp(monitored_end),
                                                     coverage=coverage) if len(e1) else HOURS(monitored_start, monitored_end)
    np.random.seed(seed)
    if len(e1) and budget_h > 0:
        res = simulate_below_mdl(e1, pd.Timestamp(monitored_start), pd.Timestamp(monitored_end),
                                 mc_iterations=mc_type1, technologies=[tech_name], mdl_define=mdl_define,
                                 pod_define=pod_define, pod_model=pod_model, consider_wind=False, coverage=cov,
                                 leak_data=leak_data, num_components=num_components)
        ue1, ue1_lo, ue1_hi = float(res[6]), float(res[7]), float(res[8])
    else:
        ue1 = ue1_lo = ue1_hi = 0.0

    # Type 2: alternating renewal process over the unmonitored remainder of the year
    unmon_h = max(HOURS(monitored_end, year_end), 0.0) + max(HOURS(year_start, monitored_start), 0.0)
    mon_h = HOURS(monitored_start, monitored_end)
    rates = ev["rate"].to_numpy(float); durs = ev["duration"].to_numpy(float)
    phi = min(1.0, float(durs.sum()) / mon_h) if mon_h > 0 else 0.0
    if unmon_h > 0 and len(ev) > 0 and phi > 0 and type2 == "by_class":
        classes = []
        for src, g in ev.groupby("sourceLocation"):
            classes.append(dict(occupancy=min(1.0, float(g["duration"].sum()) / mon_h),
                                rate_array=g["rate"].to_numpy(float), duration_array=g["duration"].to_numpy(float), paired=True))
        rng = np.random.default_rng(seed)
        b = np.array([simulate_renewal_emissions_by_class(unmon_h, classes, rng)[0] for _ in range(mc_type2)])
        ue2, ue2_lo, ue2_hi = float(np.median(b)), float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))
    elif unmon_h > 0 and len(ev) > 0 and phi > 0:
        rate_fit, dur_fit = _fit_or_empirical(rates, fit), _fit_or_empirical(durs, fit)
        np.random.seed(seed)
        boot = extrapolation({"UNKNOWN": phi}, {"UNKNOWN": rates}, {"UNKNOWN": durs},
                             pd.Timestamp(year_start), pd.Timestamp(year_start) + pd.Timedelta(hours=unmon_h),
                             mc_type2, fitted_rate_dist=rate_fit, fitted_duration_dist=dur_fit)["UNKNOWN"]
        b = np.asarray(boot, float)
        ue2, ue2_lo, ue2_hi = float(np.median(b)), float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))
    else:
        ue2 = ue2_lo = ue2_hi = 0.0

    total = measured + ue1 + ue2
    total_dn = float(np.sqrt(meas_dn ** 2 + (ue1 - ue1_lo) ** 2 + (ue2 - ue2_lo) ** 2))
    total_up = float(np.sqrt(meas_up ** 2 + (ue1_hi - ue1) ** 2 + (ue2_hi - ue2) ** 2))
    return dict(measured=measured, measured_lo=measured - meas_dn, measured_hi=measured + meas_up,
                ue1=ue1, ue1_lo=ue1_lo, ue1_hi=ue1_hi, ue2=ue2, ue2_lo=ue2_lo, ue2_hi=ue2_hi,
                total=total, total_lo=total - total_dn, total_hi=total + total_up,
                phi=phi, budget_h=float(budget_h), n_events=int(len(ev)), seconds=time.time() - t0)


def annualize_snapshot(events, obs, year_start, year_end, k, m, pod_survey=0.9, rel_q=0.25,
                       duration_model="bracket", n_outer=1000, fit="weibull", seed=0,
                       LPR=0.006, p_max=0.25, visit_interval_days=7.0, leaks_per_site=10.0,
                       prior=(1.0, 1.0)):
    """
    Case Study 1 pipeline for snapshot surveys (flyover / satellite) of one site.

    events: output of convert_to_emission_event_model for the site's positive detections bracketed by its
            null detections (columns rate, duration, startTime, endTime, first_detection, last_detection,
            uncertainties optional).
    obs:    the observation table (columns rate, time) used for the null-detection chain of the
            detection-conditioned duration model (duration_model="conditional").
    k, m:   detection dates and observation dates of the site (occupancy model, Section S9).
    duration_model: "bracket" (Case Study 1: PRE spans the null-detection bracket clipped to the year) or
            "conditional" (Section S3: median detection-conditioned duration with soft null bounds).
    Returns dict(pre, ue, total, total_lo, total_hi, phi_mean, n_events, seconds).
    """
    t0 = time.time()
    rng = np.random.default_rng(seed)
    y0, y1 = pd.Timestamp(year_start), pd.Timestamp(year_end)
    year_h = HOURS(y0, y1)
    ev = events.copy()
    rows = []
    nulls = obs[obs["rate"] == 0].copy() if obs is not None else pd.DataFrame(columns=["time"])
    nulls["time"] = pd.to_datetime(nulls["time"])
    q_max = float(ev["rate"].max()) if len(ev) else 1.0
    for i, (_, e) in enumerate(ev.iterrows()):
        st, en = pd.to_datetime(e["startTime"]), pd.to_datetime(e["endTime"])
        rate = float(e["rate"])
        if duration_model == "conditional":
            tf, tl = pd.to_datetime(e["first_detection"]), pd.to_datetime(e["last_detection"])
            before = nulls[nulls.time < tf].sort_values("time", ascending=False)
            after = nulls[nulls.time > tl].sort_values("time")
            pnd_chain = [(t, pod_survey) for t in before.time]
            snd_chain = [(t, pod_survey) for t in after.time]
            t_pnd, pnd_pod = (pnd_chain[0][0], pod_survey) if pnd_chain else (y0, 1.0)
            t_snd, snd_pod = (snd_chain[0][0], pod_survey) if snd_chain else (y1, 1.0)
            nrr = null_repair_rate(LPR, rate, q_max, p_max=p_max, visit_interval_days=visit_interval_days,
                                   leaks_per_site=leaks_per_site)
            r = sample_conditional_duration(tf, tl, max(t_pnd, y0), min(t_snd, y1), LPR=LPR, NRR=nrr, N=20_000,
                                            seed=seed * 1000 + i, pnd_pod=pnd_pod, snd_pod=snd_pod,
                                            pnd_fallbacks=[(max(t, y0), p) for t, p in pnd_chain[1:]],
                                            snd_fallbacks=[(min(t, y1), p) for t, p in snd_chain[1:]],
                                            pnd_floor=y0, snd_ceiling=y1, nrr_interval_days=visit_interval_days)
            hours = r["sim_duration_h"]
        else:
            hours = max(HOURS(max(st, y0), min(en, y1)), 0.0)
        rows.append((rate, hours))
    pre_hours = float(sum(h for _, h in rows))
    pre_point = float(sum(r * h for r, h in rows))

    # occupancy posterior of the site from k detections in m attempts (flat prior for a single site)
    g, pdf, summ = occupancy_posterior(float(k), float(m), pod_survey, prior)
    cdf = np.concatenate([[0.0], np.cumsum(0.5 * (pdf[1:] + pdf[:-1]) * np.diff(g))]); cdf /= cdf[-1]
    rates = np.array([r for r, _ in rows], float); durs = np.array([h for _, h in rows], float)
    rate_fit, dur_fit = _fit_or_empirical(rates, fit), _fit_or_empirical(durs, fit)
    window_h = max(year_h - pre_hours, 0.0)

    pre_draws = np.empty(n_outer); ue_draws = np.empty(n_outer)
    for it in range(n_outer):
        pre_draws[it] = sum(r * (1 + rng.uniform(-rel_q, rel_q)) * h for r, h in rows)
        if window_h <= 0 or len(rows) == 0:
            ue_draws[it] = 0.0; continue
        idx = rng.integers(0, len(rows), size=len(rows))
        if rate_fit is not None and dur_fit is not None and len(rows) >= 5:
            rp = weibull_min.fit(rates[idx], floc=0); dp = weibull_min.fit(durs[idx], floc=0)
            rs = weibull_min.rvs(*rp, size=512, random_state=rng); ds = weibull_min.rvs(*dp, size=512, random_state=rng)
            mean_d = weibull_min.mean(*dp)
        else:
            rs, ds, mean_d = rates[idx], durs[idx], float(np.mean(durs[idx]))
        phi = float(np.interp(rng.random(), cdf, g))
        ue_draws[it] = simulate_renewal_emissions(window_h, phi, rs, ds, rng, mean_duration=mean_d)[0]
    tot = pre_draws + ue_draws
    return dict(pre=pre_point, pre_hours=pre_hours, ue=float(np.median(ue_draws)), total=float(np.median(tot)),
                total_lo=float(np.percentile(tot, 2.5)), total_hi=float(np.percentile(tot, 97.5)),
                phi_mean=float(summ["mean"]), n_events=int(len(ev)), seconds=time.time() - t0)

"""
Case Study 1: joint Monte Carlo ensemble of the cohort (basin-level) annual total, with explicit
representation and tests of dependence (reviewer comment 1, second round).

Every quantity that enters the annual total is sampled INSIDE one outer iteration and the total is
summed within that iteration over all 629 sources; the reported central estimate and 95 % interval are
the median and the 2.5th / 97.5th percentiles of the resulting ensemble of totals. Nothing is obtained
by summing component medians or bounds, or by combining a bound with an uncertainty magnitude in
quadrature (the root-mean-square step of the earlier public comparison notebook is gone).

Per outer iteration m:
  1. Plume quantification errors. Each quantified plume j (1,321 plumes, 806 events) receives a
     multiplicative lognormal error with mean 1 whose log-standard deviation sigma_j follows from the
     Carbon Mapper reported relative uncertainty u_j (sigma_j^2 = ln(1 + u_j^2); u_j capped at 1).
     The error is split into a component SHARED by all plumes quantified by the same platform on the
     same day (a wind-field / retrieval error common to one overpass or flight day) and an independent
     component:   ln f_j = sigma_plat * z_platform(j) + sigma_j * ( sqrt(rho) * z_day(j) + sqrt(1-rho) * z_j )
     rho       : fraction of each plume's reported error variance that is shared within (platform, day);
                 0 = independent errors (Carbon Mapper's per-plume uncertainties taken at face value).
     sigma_plat: log-SD of a platform-wide (GAO / Tanager-1 / EMIT) multiplicative calibration bias,
                 one draw per platform per iteration; 0 = none.
  2. Event rates. The resolved rate of an event is the mean of its plume rates (Section 2.1), so the
     sampled event rate is the mean of the sampled plume rates.
  3. Event durations. "bracket": the interval between the bracketing null detections, clipped to the
     reporting year (the Case Study 1 rule of Section 3.1; deterministic). "conditional": the
     detection-conditioned model of Section 2.3.2 / S3 -- onset and cessation sampled from truncated
     exponentials between the detections and the bracketing null detections (hard bounds), one draw per
     event per iteration, so duration uncertainty propagates into PRE and (through the freed hours) UE.
  4. Fitted parameters (PREs parameterize UEs). The pooled event sample is bootstrap-resampled and the
     Weibull rate and duration distributions used for the unresolved-emission (UE) simulation are refit
     to that resample, using THIS iteration's sampled event rates and durations. A shared upward error in
     the measured rates therefore also raises the UE distribution of the same iteration.
  5. Occupancy. Each source's occupancy is drawn from its detection-record posterior (Section S9).
  6. UE. The unobserved hours of each source are filled by the alternating-renewal process of
     Section S4.2 with the iteration's refit distributions and occupancy draw.
  7. PRE + UE are summed over events and sources within the iteration.

run_ensemble() keeps the signature used by Case_study_No1.ipynb (pod_cm, n_outer, seed, sampling,
rate_source) and adds the dependence options (rho_day, sigma_platform, duration, refit, propagate).
run_dependence_tests() runs the grid reported in SI Section S9.2 and writes
cs1_outputs/cs1_dependence_tests.{csv,md}.

Usage (from the 'case study' folder):  python cs1_joint_ensemble.py [n_outer_headline] [n_outer_tests]
"""
import json
import os
import sys
import time
import multiprocessing as mp

import numpy as np
import pandas as pd
from scipy.stats import weibull_min

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "EAMEET_v1"))
from simulations import (simulate_renewal_emissions, sample_pairs_from_fitted,  # noqa: E402
                         _prob_to_hourly_hazard, null_repair_rate)
from occupancy import fit_occupancy_prior, occupancy_posterior  # noqa: E402

YEAR_START, YEAR_END = pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")
YEAR_HOURS = (YEAR_END - YEAR_START).total_seconds() / 3600.0          # 8784 (leap year)
OUT = os.path.join(HERE, "cs1_outputs")

# detection-conditioned duration model: same parameters as EAMEET_v1/annualize.annualize_snapshot
LPR = 0.006                 # leak production rate, per site per day (Kemp et al., 2016)
P_MAX, VISIT_DAYS, LEAKS_PER_SITE = 0.25, 7.0, 10.0   # null-repair rate of Fox et al. (2021), Eq. S1
REL_UNC_CAP = 1.0           # cap on the reported relative plume uncertainty used for sigma_j
N_CHUNKS = 16               # outer iterations are split into this many seeded chunks (result does not depend on core count)


# ----------------------------------------------------------------------------------------------- data
def load_sources(here=HERE):
    """Carbon Mapper sources of the cohort: detection dates k and observation dates m (as Case_study_No1.ipynb)."""
    with open(os.path.join(here, "CM_sources.json")) as f:
        feats = json.load(f)["features"]
    rows = []
    for ft in feats:
        pr = ft["properties"]
        if pr.get("sector") != "1B2" or not any("2024" in p for p in (pr.get("plume_ids") or [])):
            continue
        rows.append(dict(source_name=ft["id"], detection_date_count=pr.get("detection_date_count"),
                         observation_date_count=pr.get("observation_date_count"), persistence=pr.get("persistence")))
    return pd.DataFrame(rows)


def load_case(here=HERE):
    """Arrays describing the 806 events, their 1,321 plumes and the 629 sources."""
    ev = pd.read_csv(os.path.join(here, "CM_emission_events.csv"),
                     parse_dates=["startTime", "endTime", "first_detection", "last_detection"])
    eo = pd.read_csv(os.path.join(here, "CM_emissions_observation.csv"), parse_dates=["observation_time"])
    pos = eo[eo.detection].set_index("id")
    src = load_sources(here).set_index("source_name")

    sources = list(ev.sourceLocation.unique())
    s_index = {s: i for i, s in enumerate(sources)}
    ev_source = ev.sourceLocation.map(s_index).to_numpy()
    ev_rate = ev.rate.to_numpy(float)

    # plumes -> events
    p_event, p_rate, p_relu, p_platform, p_day = [], [], [], [], []
    for e, m in enumerate(ev.merged_from):
        for pid in [s.strip() for s in str(m).split(",")]:
            r = pos.loc[pid]
            p_event.append(e); p_rate.append(float(r.rate))
            p_relu.append(min(float(r.rate_uncertainty) / float(r.rate), REL_UNC_CAP) if r.rate > 0 else 0.0)
            p_platform.append(str(r.platform)); p_day.append(f"{r.platform}|{r.observation_time.date()}")
    p_event = np.asarray(p_event); p_rate = np.asarray(p_rate); p_relu = np.asarray(p_relu)
    platforms = sorted(set(p_platform)); p_platform = np.asarray([platforms.index(p) for p in p_platform])
    days = sorted(set(p_day)); p_day = np.asarray([days.index(d) for d in p_day])
    p_sigma = np.sqrt(np.log1p(p_relu ** 2))                       # lognormal log-SD from the relative SD
    ev_plume_rate_sum = np.bincount(p_event, weights=p_rate, minlength=len(ev))
    assert np.allclose(ev_plume_rate_sum / np.bincount(p_event, minlength=len(ev)), ev_rate), \
        "event rate must equal the mean of its plume rates"

    # durations: bracket (deterministic) and the quantities needed for the conditional model
    st, en = ev.startTime, ev.endTime
    h = lambda a, b: (b - a).dt.total_seconds().to_numpy() / 3600.0
    hours_bracket = np.maximum(h(st.clip(lower=YEAR_START), en.clip(upper=YEAR_END)), 0.0)
    first, last = ev.first_detection, ev.last_detection
    before_h = np.maximum(h(st, first), 0.0)          # room between the preceding null detection and the first detection
    after_h = np.maximum(h(last, en), 0.0)            # room between the last detection and the succeeding null detection
    span_h = np.maximum(h(first, last), 0.0)
    first_h = h(pd.Series([YEAR_START] * len(ev)), first)   # hours of the first detection after the year start
    q_max = float(ev_rate.max())
    lam_on = _prob_to_hourly_hazard(LPR, 1.0)
    nrr = np.array([null_repair_rate(LPR, r, q_max, p_max=P_MAX, visit_interval_days=VISIT_DAYS,
                                     leaks_per_site=LEAKS_PER_SITE) for r in ev_rate])
    lam_off = np.array([_prob_to_hourly_hazard(p, VISIT_DAYS) for p in nrr])
    lam_back = lam_off - lam_on

    # occupancy data per source; the population prior is fitted on every listed 1B2 source with a 2024 plume
    # identifier (as in Case_study_No1.ipynb), the posteriors on the 629 sources of the event cohort
    k = np.array([float(src.loc[s, "detection_date_count"]) if s in src.index else np.nan for s in sources])
    m = np.array([float(src.loc[s, "observation_date_count"]) if s in src.index else np.nan for s in sources])
    k_prior = src.detection_date_count.to_numpy(float); m_prior = src.observation_date_count.to_numpy(float)
    return dict(ev=ev, sources=sources, n_sources=len(sources), ev_source=ev_source, ev_rate=ev_rate,
                p_event=p_event, p_rate=p_rate, p_relu=p_relu, p_sigma=p_sigma, p_platform=p_platform,
                p_day=p_day, platforms=platforms, n_days=len(days), ev_plume_rate_sum=ev_plume_rate_sum,
                hours_bracket=hours_bracket, before_h=before_h, after_h=after_h, span_h=span_h,
                first_h=first_h, lam_off=lam_off, lam_back=lam_back, k_all=k, m_all=m,
                k_prior=k_prior, m_prior=m_prior)


def build_occupancy(case, pod_cm):
    """Empirical-Bayes prior and per-source posterior CDFs (Section S9); same as Case_study_No1.ipynb."""
    ok = np.isfinite(case["k_prior"]) & np.isfinite(case["m_prior"])
    prior = fit_occupancy_prior(case["k_prior"][ok], case["m_prior"][ok], pod=pod_cm)
    grids, cdfs, summaries = [], [], []
    for k_i, m_i in zip(case["k_all"], case["m_all"]):
        if not (np.isfinite(k_i) and np.isfinite(m_i)):
            grids.append(None); cdfs.append(None); summaries.append(None); continue
        g, pdf, summ = occupancy_posterior(k_i, m_i, pod_cm, prior)
        cdf = np.concatenate([[0.0], np.cumsum(0.5 * (pdf[1:] + pdf[:-1]) * np.diff(g))]); cdf /= cdf[-1]
        grids.append(g); cdfs.append(cdf); summaries.append(dict(k=k_i, m=m_i, persistence=k_i / m_i, **summ))
    return prior, grids, cdfs, summaries


# ------------------------------------------------------------------------------------------- sampling
def _trunc_exp(rate, t_max, rng):
    """Vectorised draw with density ∝ exp(-rate x) on [0, t_max]; rate may be negative (density increasing
    in x, i.e. onset pushed toward the preceding null detection) -- as simulations._truncated_exponential."""
    rate = np.asarray(rate, float); t_max = np.asarray(t_max, float)
    out = np.zeros_like(t_max); ok = t_max > 0
    u = rng.random(t_max.shape)
    r = np.abs(rate); small = r * t_max < 1e-9
    with np.errstate(divide="ignore", invalid="ignore"):
        c = -np.expm1(-r * t_max)
        x = np.where(small, u * t_max, -np.log1p(-u * c) / np.where(r > 0, r, 1.0))
    x = np.where(rate < 0, t_max - x, x)
    out[ok] = x[ok]
    return out


def sample_event_hours(case, rng, duration="bracket"):
    """Hours of each event inside the reporting year for this iteration."""
    if duration == "bracket":
        return case["hours_bracket"]
    if duration != "conditional":
        raise ValueError("duration must be 'bracket' or 'conditional'")
    a = _trunc_exp(case["lam_back"], case["before_h"], rng)      # hours the emission predates the first detection
    b = _trunc_exp(case["lam_off"], case["after_h"], rng)        # hours it outlasts the last detection
    start = case["first_h"] - a                                   # hours after the year start (may be negative)
    end = case["first_h"] + case["span_h"] + b
    return np.maximum(np.minimum(end, YEAR_HOURS) - np.maximum(start, 0.0), 0.0)


def sample_event_rates(case, rng, rho_day=0.0, sigma_platform=0.0):
    """Sampled event rates (mean of the sampled plume rates) with shared and independent plume errors."""
    z_ind = rng.standard_normal(len(case["p_rate"]))
    z_day = rng.standard_normal(case["n_days"])[case["p_day"]] if rho_day > 0 else 0.0
    z_plat = rng.standard_normal(len(case["platforms"]))[case["p_platform"]] if sigma_platform > 0 else 0.0
    log_f = (sigma_platform * z_plat
             + case["p_sigma"] * (np.sqrt(rho_day) * z_day + np.sqrt(1.0 - rho_day) * z_ind))
    # mean-preserving lognormal factors (E[f] = 1): the reported rate is taken as the expected value, so the
    # errors neither inflate nor deflate the expected annual total; var(log f) = sigma_plat^2 + sigma_j^2
    f = np.exp(log_f - 0.5 * (sigma_platform ** 2 + case["p_sigma"] ** 2))
    ev_factor = np.bincount(case["p_event"], weights=case["p_rate"] * f,
                            minlength=len(case["ev_rate"])) / case["ev_plume_rate_sum"]
    return case["ev_rate"] * ev_factor


def _run_chunk(args):
    (case, occ, n_iter, seed_entropy, pod_cm, cfg) = args
    rng = np.random.default_rng(seed_entropy)
    prior, grids, cdfs, _ = occ
    S = case["n_sources"]; E = len(case["ev_rate"])
    pre = np.empty((n_iter, S)); ue = np.empty((n_iter, S))
    # observed-sample fit (used when refit=False)
    fixed_rate = weibull_min.fit(case["ev_rate"], floc=0)
    fixed_dur = weibull_min.fit(case["hours_bracket"][case["hours_bracket"] > 0], floc=0)
    own_rates = [case["ev_rate"][case["ev_source"] == s] for s in range(S)] if cfg["rate_source"] == "own" else None
    for it in range(n_iter):
        rates = sample_event_rates(case, rng, cfg["rho_day"], cfg["sigma_platform"])
        hours = sample_event_hours(case, rng, cfg["duration"])
        pre[it] = np.bincount(case["ev_source"], weights=rates * hours, minlength=S)
        pre_hours = np.bincount(case["ev_source"], weights=hours, minlength=S)
        # distributions for the UE simulation (PREs parameterize UEs)
        fit_rates = rates if cfg["propagate"] else case["ev_rate"]
        fit_hours = hours if cfg["propagate"] else case["hours_bracket"]
        if cfg["refit"]:
            idx = rng.integers(0, E, size=E)
            r_sel, d_sel = fit_rates[idx], fit_hours[idx]
            d_sel = d_sel[d_sel > 0] if np.any(d_sel > 0) else fit_hours[fit_hours > 0]
            rate_params = weibull_min.fit(r_sel, floc=0); dur_params = weibull_min.fit(d_sel, floc=0)
        else:
            r_sel, d_sel = fit_rates, fit_hours[fit_hours > 0]
            rate_params, dur_params = fixed_rate, fixed_dur
        if cfg["sampling"] == "paired":
            rate_s, dur_s = sample_pairs_from_fitted(
                {"type": "weibull", "params": rate_params, "min": 0}, {"type": "weibull", "params": dur_params, "min": 0},
                r_sel[: len(d_sel)], d_sel[: len(r_sel)], cfg["n_dist"], rng)
        else:
            rate_s = weibull_min.rvs(*rate_params, size=cfg["n_dist"], random_state=rng)
            dur_s = weibull_min.rvs(*dur_params, size=cfg["n_dist"], random_state=rng)
        mean_dur = weibull_min.mean(*dur_params)
        u_occ = rng.random(S)
        for s in range(S):
            window = YEAR_HOURS - pre_hours[s]
            if window <= 0 or cdfs[s] is None:
                ue[it, s] = 0.0; continue
            phi = float(np.interp(u_occ[s], cdfs[s], grids[s]))
            r_arr = own_rates[s] if own_rates is not None else rate_s
            ue[it, s] = simulate_renewal_emissions(window, phi, r_arr, dur_s, rng, mean_duration=mean_dur,
                                                   paired=(cfg["sampling"] == "paired" and own_rates is None))[0]
    return pre, ue


def run_ensemble(pod_cm=0.9, n_outer=10_000, seed=2024, sampling="independent", rate_source="pooled",
                 rho_day=0.0, sigma_platform=0.0, duration="bracket", refit=True, propagate=True,
                 n_dist=2048, n_jobs=None, case=None, occ=None):
    """Joint ensemble. Returns (prior, info_list, pre_draws, ue_draws) as the notebook expects, where
    info_list[s] = {"source", "occupancy": {...posterior summary...} or None}."""
    case = case or load_case()
    occ = occ or build_occupancy(case, pod_cm)
    cfg = dict(sampling=sampling, rate_source=rate_source, rho_day=float(rho_day), sigma_platform=float(sigma_platform),
               duration=duration, refit=bool(refit), propagate=bool(propagate), n_dist=int(n_dist))
    n_chunks = min(N_CHUNKS, n_outer)
    sizes = [n_outer // n_chunks + (1 if i < n_outer % n_chunks else 0) for i in range(n_chunks)]
    seeds = np.random.SeedSequence(seed).spawn(n_chunks)
    args = [(case, occ, n, s, pod_cm, cfg) for n, s in zip(sizes, seeds) if n > 0]
    n_jobs = n_jobs or max(1, (os.cpu_count() or 2) - 1)
    if n_jobs > 1 and len(args) > 1:
        with mp.get_context("fork").Pool(min(n_jobs, len(args))) as pool:
            parts = pool.map(_run_chunk, args)
    else:
        parts = [_run_chunk(a) for a in args]
    pre = np.vstack([p for p, _ in parts]); ue = np.vstack([u for _, u in parts])
    prior, _, _, summaries = occ
    info_list = [{"source": s, "occupancy": summ} for s, summ in zip(case["sources"], summaries)]
    return prior, info_list, pre, ue


# ------------------------------------------------------------------------------------- dependence tests
DEPENDENCE_GRID = [
    ("A", "Baseline: independent plume errors, bracket durations, bootstrap refit on the sampled rates",
     dict()),
    ("B", "No parameter uncertainty: Weibull fitted once to the observed sample (no bootstrap refit)",
     dict(refit=False)),
    ("C", "UE distributions refit to the reported (unperturbed) rates, i.e. PRE rate errors not passed to the UEs",
     dict(propagate=False)),
    ("D", "Half of each plume's error variance shared within (platform, day): rho = 0.5",
     dict(rho_day=0.5)),
    ("E", "All of each plume's error shared within (platform, day): rho = 1",
     dict(rho_day=1.0)),
    ("F", "Platform-wide calibration bias, log-SD 0.2 per platform, plus independent plume errors",
     dict(sigma_platform=0.2)),
    ("G", "Platform-wide bias (0.2) with the UE distributions refit to the reported rates (link PRE -> UE cut)",
     dict(sigma_platform=0.2, propagate=False)),
    ("H", "Fully shared errors: platform-wide bias (0.2) and rho = 1",
     dict(sigma_platform=0.2, rho_day=1.0)),
    ("I", "Detection-conditioned PRE durations sampled per event (Section S3), independent plume errors",
     dict(duration="conditional")),
    ("J", "Detection-conditioned durations with fully shared errors (platform bias 0.2, rho = 1)",
     dict(duration="conditional", sigma_platform=0.2, rho_day=1.0)),
]


def summarize(pre, ue, label="", description="", n_outer=None, extra=None):
    tot = (pre + ue).sum(axis=1); pre_t = pre.sum(axis=1); ue_t = ue.sum(axis=1)
    med, lo, hi = np.median(tot), np.percentile(tot, 2.5), np.percentile(tot, 97.5)
    row = {"variant": label, "description": description, "N_outer": n_outer or len(tot),
           "PRE_Tg_median": np.median(pre_t) / 1e9, "UE_Tg_median": np.median(ue_t) / 1e9,
           "total_Tg_median": med / 1e9, "total_Tg_q2.5": lo / 1e9, "total_Tg_q97.5": hi / 1e9,
           "rel_width_95": (hi - lo) / med}
    row.update(extra or {})
    return row


def run_dependence_tests(n_outer=2000, seed=7, pod_cm=0.9, case=None, occ=None, grid=DEPENDENCE_GRID, verbose=True):
    case = case or load_case(); occ = occ or build_occupancy(case, pod_cm)
    rows = []
    for label, desc, kw in grid:
        t0 = time.time()
        _, _, pre, ue = run_ensemble(pod_cm, n_outer, seed=seed, case=case, occ=occ, **kw)
        rows.append(summarize(pre, ue, label, desc, n_outer, {"seconds": round(time.time() - t0, 1), **kw}))
        if verbose:
            r = rows[-1]
            print(f"{label}: total {r['total_Tg_median']:.3f} [{r['total_Tg_q2.5']:.3f}, {r['total_Tg_q97.5']:.3f}] Tg, "
                  f"PRE {r['PRE_Tg_median']:.3f}, UE {r['UE_Tg_median']:.3f}, rel. width {r['rel_width_95']:.3f} "
                  f"({r['seconds']} s)  -- {desc}")
    df = pd.DataFrame(rows)
    base = df.iloc[0]
    df["change_median_pct"] = (df.total_Tg_median / base.total_Tg_median - 1) * 100
    df["width_ratio_vs_baseline"] = df.rel_width_95 / base.rel_width_95
    os.makedirs(OUT, exist_ok=True)
    df.to_csv(os.path.join(OUT, "cs1_dependence_tests.csv"), index=False)
    md = ["| Variant | Description | PRE (Tg) | UE (Tg) | Total (Tg) [95 % interval] | Rel. width | Change in median | Width ratio |",
          "|---|---|---|---|---|---|---|---|"]
    for _, r in df.iterrows():
        md.append(f"| {r.variant} | {r.description} | {r.PRE_Tg_median:.3f} | {r.UE_Tg_median:.3f} | "
                  f"{r.total_Tg_median:.3f} [{r['total_Tg_q2.5']:.3f}, {r['total_Tg_q97.5']:.3f}] | {r.rel_width_95:.2f} | "
                  f"{r.change_median_pct:+.1f} % | {r.width_ratio_vs_baseline:.2f} |")
    with open(os.path.join(OUT, "cs1_dependence_tests.md"), "w") as f:
        f.write(f"Joint-ensemble dependence tests, Case Study 1 ({n_outer} outer iterations per variant, POD = {pod_cm}, "
                f"seed {seed}). Rel. width = (97.5th - 2.5th percentile) / median.\n\n" + "\n".join(md) + "\n")
    return df


if __name__ == "__main__":
    try:
        mp.set_start_method("fork", force=True)
    except RuntimeError:
        pass
    n_head = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000
    n_test = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    case = load_case(); occ = build_occupancy(case, 0.9)
    t0 = time.time()
    prior, info, pre, ue = run_ensemble(0.9, n_head, seed=2024, case=case, occ=occ)
    r = summarize(pre, ue, "headline", "", n_head)
    print(f"Headline joint ensemble (N={n_head}, {time.time() - t0:.0f} s): total {r['total_Tg_median']:.3f} Tg "
          f"[{r['total_Tg_q2.5']:.3f}, {r['total_Tg_q97.5']:.3f}], PRE {r['PRE_Tg_median']:.3f}, UE {r['UE_Tg_median']:.3f}")
    run_dependence_tests(n_test, case=case, occ=occ)

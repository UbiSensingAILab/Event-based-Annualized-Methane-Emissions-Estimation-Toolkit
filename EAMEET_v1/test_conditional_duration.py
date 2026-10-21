"""
Tests for the detection-conditioned PRE duration model (`sample_conditional_duration` and the
public `simulate_duration_uncertainty`).

Every realization must satisfy the four conditions
    t_PND <= t_start <= t_first   and   t_last <= t_end <= t_SND,
the backward extension must use the repair-minus-onset hazard (survival until first detection),
and a null detection is only a valid bound with probability POD -- otherwise the bound falls back
to the previous null detection (or the analysis floor / ceiling).

Run with:  python -m pytest test_conditional_duration.py
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulations import (null_repair_rate, sample_conditional_duration,  # noqa: E402
                         simulate_duration_uncertainty)

T_PND = pd.Timestamp("2024-04-01 16:00")
T_FIRST = pd.Timestamp("2024-05-21 17:00")
T_LAST = pd.Timestamp("2024-07-05 20:00")
T_SND = T_LAST + pd.Timedelta(days=90)
H = 3600.0


def hours(td):
    return td.total_seconds() / H


def hazard(p_daily):
    return -np.log(1.0 - p_daily) / 24.0


def truncexp_median(rate, t_max):
    c = 1.0 - np.exp(-rate * t_max)
    return -np.log(1.0 - 0.5 * c) / rate


def test_all_realizations_satisfy_four_conditions():
    r = sample_conditional_duration(T_FIRST, T_LAST, T_PND, T_SND, LPR=0.006, NRR=0.05, N=20_000, seed=1)
    a, b = r["a_samples"], r["b_samples"]
    assert a.shape == b.shape == (20_000,)
    assert np.all(a >= 0) and np.all(b >= 0)                       # start <= t_first, end >= t_last
    assert np.all(a <= hours(T_FIRST - T_PND) + 1e-9)              # start >= t_PND
    assert np.all(b <= hours(T_SND - T_LAST) + 1e-9)               # end   <= t_SND
    assert np.allclose(r["dur_samples"], a + hours(T_LAST - T_FIRST) + b)


def test_backward_extension_uses_repair_minus_onset_hazard():
    lpr, nrr = 0.006, 0.5
    r = sample_conditional_duration(T_FIRST, T_LAST, T_PND, T_SND, LPR=lpr, NRR=nrr, N=200_000, seed=2)
    rate = hazard(nrr) - hazard(lpr)
    expected = truncexp_median(rate, hours(T_FIRST - T_PND))
    assert r["lam_back_per_hr"] == pytest.approx(rate)
    assert np.median(r["a_samples"]) == pytest.approx(expected, rel=0.05)
    # with a 0.5/day repair hazard the onset sits about a day before the first detection,
    # not three weeks (which is what Exp(lambda_on) alone would give)
    assert np.median(r["a_samples"]) < 48


def test_backward_density_increases_toward_pnd_when_repair_slower_than_onset():
    r = sample_conditional_duration(T_FIRST, T_LAST, T_PND, T_SND, LPR=0.5, NRR=0.006, N=100_000, seed=3)
    t_max = hours(T_FIRST - T_PND)
    assert r["lam_back_per_hr"] < 0
    assert np.mean(r["a_samples"]) > 0.5 * t_max
    assert np.all(r["a_samples"] <= t_max + 1e-9)


def test_forward_extension_is_memoryless_repair_hazard():
    nrr = 0.5
    r = sample_conditional_duration(T_FIRST, T_LAST, T_PND, T_SND, LPR=0.006, NRR=nrr, N=200_000, seed=4)
    expected = truncexp_median(hazard(nrr), hours(T_SND - T_LAST))
    assert np.median(r["b_samples"]) == pytest.approx(expected, rel=0.05)


def test_hard_pnd_when_pod_is_one():
    r = sample_conditional_duration(T_FIRST, T_LAST, T_PND, T_SND, LPR=0.5, NRR=0.006, N=50_000, seed=5,
                                    pnd_pod=1.0, pnd_floor=T_PND - pd.Timedelta(days=60))
    assert r["pnd_valid_frac"] == 1.0
    assert np.max(r["a_samples"]) <= hours(T_FIRST - T_PND) + 1e-9


def test_missed_pnd_falls_back_to_floor():
    floor = T_PND - pd.Timedelta(days=60)
    r = sample_conditional_duration(T_FIRST, T_LAST, T_PND, T_SND, LPR=0.5, NRR=0.006, N=50_000, seed=6,
                                    pnd_pod=0.0, pnd_floor=floor)
    assert r["pnd_valid_frac"] == 0.0
    assert np.max(r["a_samples"]) > hours(T_FIRST - T_PND)
    assert np.max(r["a_samples"]) <= hours(T_FIRST - floor) + 1e-9


def test_partial_pod_mixes_hard_bound_and_floor():
    floor = T_PND - pd.Timedelta(days=60)
    r = sample_conditional_duration(T_FIRST, T_LAST, T_PND, T_SND, LPR=0.5, NRR=0.006, N=100_000, seed=7,
                                    pnd_pod=0.5, pnd_floor=floor)
    assert r["pnd_valid_frac"] == pytest.approx(0.5, abs=0.01)
    beyond = np.mean(r["a_samples"] > hours(T_FIRST - T_PND))
    # only draws with a missed PND can extend past it, and never more than that share
    assert 0.2 < beyond <= 1.0 - r["pnd_valid_frac"] + 1e-12


def test_nearest_valid_fallback_null_detection_wins():
    t_prev = T_PND - pd.Timedelta(days=20)
    floor = T_PND - pd.Timedelta(days=60)
    r = sample_conditional_duration(T_FIRST, T_LAST, T_PND, T_SND, LPR=0.5, NRR=0.006, N=50_000, seed=8,
                                    pnd_pod=0.0, pnd_fallbacks=[(t_prev, 1.0)], pnd_floor=floor)
    assert np.max(r["a_samples"]) > hours(T_FIRST - T_PND)
    assert np.max(r["a_samples"]) <= hours(T_FIRST - t_prev) + 1e-9


def test_soft_snd_falls_back_to_ceiling():
    ceiling = T_SND + pd.Timedelta(days=60)
    r = sample_conditional_duration(T_FIRST, T_LAST, T_PND, T_SND, LPR=0.006, NRR=0.0005, N=50_000, seed=9,
                                    snd_pod=0.0, snd_ceiling=ceiling)
    assert r["snd_valid_frac"] == 0.0
    assert np.max(r["b_samples"]) > hours(T_SND - T_LAST)
    assert np.max(r["b_samples"]) <= hours(T_SND - T_LAST) + 60 * 24 + 1e-9


def test_soft_bound_requires_a_floor():
    with pytest.raises(ValueError):
        sample_conditional_duration(T_FIRST, T_LAST, T_PND, T_SND, LPR=0.006, NRR=0.05, N=1000, pnd_pod=0.5)


def test_same_seed_is_reproducible():
    kw = dict(LPR=0.006, NRR=0.05, N=5000, seed=11, pnd_pod=0.7, pnd_floor=T_PND - pd.Timedelta(days=10))
    r1 = sample_conditional_duration(T_FIRST, T_LAST, T_PND, T_SND, **kw)
    r2 = sample_conditional_duration(T_FIRST, T_LAST, T_PND, T_SND, **kw)
    assert np.array_equal(r1["dur_samples"], r2["dur_samples"])


def test_null_repair_rate_follows_ldar_sim_eq_s1():
    # NRR = (LPR*V/Lbar0)*(Lt/L0) + p_max*Q_i/Q_max  (Fox et al. 2021, SI Eq. S1), per operator VISIT
    assert null_repair_rate(0.006, rate=10.0, q_max=100.0) == pytest.approx(0.006 * 7 / 10 + 0.25 * 0.1)
    assert null_repair_rate(0.006, rate=100.0, q_max=100.0, p_max=0.5, visit_interval_days=14,
                            leaks_per_site=5) == pytest.approx(0.006 * 14 / 5 + 0.5)
    assert null_repair_rate(0.006, rate=0.0, q_max=100.0, p_max=0.0) == pytest.approx(0.0042)


def test_nrr_is_converted_as_a_per_visit_probability():
    nrr, V = 0.254, 7.0
    r = sample_conditional_duration(T_FIRST, T_LAST, T_PND, T_SND, LPR=0.006, NRR=nrr, N=200_000, seed=12,
                                    nrr_interval_days=V)
    lam_off = -np.log(1.0 - nrr) / (24.0 * V)
    assert r["lam_off_per_hr"] == pytest.approx(lam_off)
    assert np.median(r["b_samples"]) == pytest.approx(truncexp_median(lam_off, hours(T_SND - T_LAST)), rel=0.05)
    # the per-day reading (interval 1) would make the repair hazard seven times larger
    r1 = sample_conditional_duration(T_FIRST, T_LAST, T_PND, T_SND, LPR=0.006, NRR=nrr, N=1000, seed=12,
                                     nrr_interval_days=1.0)
    assert r1["lam_off_per_hr"] == pytest.approx(7.0 * lam_off)


def test_public_routine_exposes_eq_s1_parameters():
    base = simulate_duration_uncertainty(0.006, _events(), MC_iterations=20_000)
    low = simulate_duration_uncertainty(0.006, _events(), MC_iterations=20_000, p_max=0.0)
    assert low["simulated_duration"].iloc[0] > base["simulated_duration"].iloc[0]
    assert "nrr_per_visit" in base.columns
    assert base["nrr_per_visit"].iloc[0] == pytest.approx(0.006 * 7 / 10 + 0.25)


def _events(**extra):
    row = dict(event_type="PRE", rate=150.0, start_time=T_PND, end_time=T_SND,
               first_detection=T_FIRST, last_detection=T_LAST)
    row.update(extra)
    return pd.DataFrame([row])


def test_public_routine_reports_median_duration():
    out = simulate_duration_uncertainty(0.006, _events(), MC_iterations=20_000)
    nrr = null_repair_rate(0.006, rate=150.0, q_max=150.0)      # Eq. S1 defaults: V=7 d, 10 leaks/site, p_max=0.25
    ref = sample_conditional_duration(T_FIRST, T_LAST, T_PND, T_SND, LPR=0.006, NRR=nrr, N=20_000, seed=0,
                                      nrr_interval_days=7.0)
    assert out["simulated_duration"].iloc[0] == pytest.approx(ref["sim_duration_h"])
    assert out["simulated_duration_lower"].iloc[0] == pytest.approx(ref["sim_duration_lo"])
    assert out["simulated_duration_upper"].iloc[0] == pytest.approx(ref["sim_duration_hi"])


def test_public_routine_uses_pod_columns():
    hard = simulate_duration_uncertainty(0.5, _events(), MC_iterations=20_000)
    soft = simulate_duration_uncertainty(0.5, _events(pnd_pod=0.0, pnd_floor=T_PND - pd.Timedelta(days=60)),
                                         MC_iterations=20_000)
    assert soft["simulated_duration_upper"].iloc[0] > hard["simulated_duration_upper"].iloc[0]

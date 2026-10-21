"""
Tests for the alternating-renewal unmeasured-emission (UE) process used by `extrapolation()`.

The process alternates emitting intervals (durations drawn from the duration sample) and
non-emitting gaps (exponential, mean = E[D] * (1 - phi) / phi) so that the long-run fraction of
time emitting equals the prescribed occupancy `phi` and the event frequency equals phi / E[D],
independent of any simulation time step.

Run with:  python -m pytest test_extrapolation_renewal.py
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulations import extrapolation, simulate_renewal_emissions  # noqa: E402


def _realized(total_hours, phi, durations, rates=None, seed=0, reps=200):
    rng = np.random.default_rng(seed)
    rates = np.ones(1) if rates is None else rates
    occ, n_ev, emis = [], [], []
    for _ in range(reps):
        total, emitting_hours, n_events = simulate_renewal_emissions(
            total_hours, phi, rates, durations, rng)
        occ.append(emitting_hours / total_hours)
        n_ev.append(n_events)
        emis.append(total)
    return np.mean(occ), np.mean(n_ev), np.mean(emis)


@pytest.mark.parametrize("phi", [0.1, 0.572, 0.9])
def test_constant_duration_recovers_prescribed_occupancy(phi):
    # Reviewer's diagnostic: phi=0.572 with constant 10 h events must give ~57% occupancy, not ~93%.
    occ, _, _ = _realized(3672, phi, np.array([10.0]))
    assert occ == pytest.approx(phi, abs=0.02)


@pytest.mark.parametrize("phi", [0.1, 0.572, 0.9])
def test_constant_duration_recovers_event_frequency(phi):
    # Expected number of event onsets in the window is phi * T / E[D].
    total_hours, mean_d = 20000, 10.0
    _, n_ev, _ = _realized(total_hours, phi, np.array([mean_d]))
    assert n_ev == pytest.approx(phi * total_hours / mean_d, rel=0.05)


def test_skewed_duration_sample_recovers_occupancy():
    # Case Study 2-like Weibull durations (shape 0.586, scale 15.4 h): heavy right tail.
    from scipy.stats import weibull_min
    durs = weibull_min.rvs(0.586, 0, 15.396, size=20000, random_state=1)
    occ, _, _ = _realized(3672, 0.572, durs, reps=400)
    assert occ == pytest.approx(0.572, abs=0.03)


def test_long_duration_sample_recovers_occupancy():
    # Case Study 1-like durations (mean ~3000 h) over a ~6500 h window: the old
    # geometric-gap scheme gave ~100% occupancy regardless of phi.
    from scipy.stats import weibull_min
    durs = weibull_min.rvs(0.558, 0, 1960.7, size=20000, random_state=2)
    occ, _, _ = _realized(6563, 0.5, durs, reps=2000)
    assert occ == pytest.approx(0.5, abs=0.03)


def test_emissions_equal_rate_times_emitting_hours_for_constant_rate():
    rng = np.random.default_rng(3)
    total, emitting_hours, _ = simulate_renewal_emissions(
        5000, 0.4, np.array([7.5]), np.array([3.0, 12.0, 40.0]), rng)
    assert total == pytest.approx(7.5 * emitting_hours)


def test_emitting_hours_never_exceed_window():
    rng = np.random.default_rng(4)
    for _ in range(50):
        _, emitting_hours, _ = simulate_renewal_emissions(
            100, 0.9, np.array([1.0]), np.array([500.0]), rng)
        assert 0 <= emitting_hours <= 100


def test_zero_occupancy_gives_no_emissions():
    rng = np.random.default_rng(5)
    total, emitting_hours, n_events = simulate_renewal_emissions(
        1000, 0.0, np.array([5.0]), np.array([10.0]), rng)
    assert (total, emitting_hours, n_events) == (0.0, 0.0, 0)


def test_full_occupancy_emits_whole_window():
    rng = np.random.default_rng(6)
    total, emitting_hours, _ = simulate_renewal_emissions(
        1000, 1.0, np.array([2.0]), np.array([10.0]), rng)
    assert emitting_hours == pytest.approx(1000)
    assert total == pytest.approx(2000)


def test_explicit_mean_duration_overrides_sample_mean():
    # When the caller knows E[D] analytically (e.g. a fitted Weibull) it can pass it instead of
    # relying on the mean of the finite sample.
    rng = np.random.default_rng(7)
    occ = []
    for _ in range(300):
        _, h, _ = simulate_renewal_emissions(
            5000, 0.3, np.ones(1), np.array([10.0]), rng, mean_duration=10.0)
        occ.append(h / 5000)
    assert np.mean(occ) == pytest.approx(0.3, abs=0.02)


def test_extrapolation_sequential_path_recovers_occupancy():
    # End-to-end through the public API (MC < 20 => sequential branch, no multiprocessing).
    from datetime import datetime
    np.random.seed(0)
    res = extrapolation(prob_dist={"UNKNOWN": 0.572},
                        rate_dist={"UNKNOWN": [1.0]}, duration_dist={"UNKNOWN": [10.0]},
                        start_time=datetime(2024, 8, 1), end_time=datetime(2025, 1, 1), MC=19)
    draws = np.asarray(res["UNKNOWN"], dtype=float)
    total_hours = (datetime(2025, 1, 1) - datetime(2024, 8, 1)).total_seconds() / 3600
    assert len(draws) == 19
    # rate = 1 kg/h, so emissions == emitting hours; occupancy must be ~0.572, not ~0.93
    assert draws.mean() / total_hours == pytest.approx(0.572, abs=0.04)


# ----------------------------------------------------------------------------------------------
# Reviewer comment 4 (B2): joint rate-duration sampling. Independent sampling of pooled marginals
# can create (rate, duration) combinations unsupported by the observed events; the renewal process
# therefore offers paired sampling (observed pairs, or the empirical copula of the observed pairs
# with fitted marginals) and class-stratified simulation.
# ----------------------------------------------------------------------------------------------
from simulations import sample_pairs_from_fitted, simulate_renewal_emissions_by_class  # noqa: E402


def _two_pair_sample():
    # long events are weak (1 kg/h for 100 h), short events are strong (100 kg/h for 1 h)
    return np.array([1.0, 100.0]), np.array([100.0, 1.0])


def test_paired_sampling_keeps_each_rate_with_its_own_duration():
    rates, durs = _two_pair_sample()
    rng = np.random.default_rng(3)
    tot, emitting, _ = simulate_renewal_emissions(200_000, 0.5, rates, durs, rng, paired=True)
    # emission per emitting hour: (1*100 + 100*1) / (100 + 1) ~ 1.98 kg/h
    assert tot / emitting == pytest.approx(1.98, rel=0.1)


def test_independent_sampling_mixes_rates_and_durations():
    rates, durs = _two_pair_sample()
    rng = np.random.default_rng(3)
    tot, emitting, _ = simulate_renewal_emissions(200_000, 0.5, rates, durs, rng)
    assert tot / emitting == pytest.approx(50.5, rel=0.1)   # mean rate, regardless of duration


def test_paired_sampling_requires_aligned_arrays():
    rng = np.random.default_rng(0)
    with pytest.raises(ValueError):
        simulate_renewal_emissions(100, 0.5, np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0]), rng, paired=True)


def test_sample_pairs_from_fitted_keeps_rank_correlation_and_marginals():
    from scipy.stats import spearmanr, weibull_min
    rng = np.random.default_rng(1)
    durs = weibull_min.rvs(0.8, 0, 20, size=400, random_state=rng)
    rates = durs ** 0.5 * np.exp(rng.normal(0, 0.3, size=400))        # positively dependent
    rho_obs = spearmanr(rates, durs).statistic
    fr = {"type": "weibull", "params": weibull_min.fit(rates, floc=0), "min": 0}
    fd = {"type": "weibull", "params": weibull_min.fit(durs, floc=0), "min": 0}
    r_s, d_s = sample_pairs_from_fitted(fr, fd, rates, durs, size=20_000, rng=rng)
    assert spearmanr(r_s, d_s).statistic == pytest.approx(rho_obs, abs=0.06)
    assert np.mean(d_s) == pytest.approx(weibull_min.mean(*fd["params"]), rel=0.05)
    assert np.mean(r_s) == pytest.approx(weibull_min.mean(*fr["params"]), rel=0.05)


def test_extrapolation_paired_option_uses_observed_pairs():
    import pandas as pd
    rates, durs = _two_pair_sample()
    t0, t1 = pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-01") + pd.Timedelta(hours=50_000)
    np.random.seed(0)
    ind = extrapolation({"UNKNOWN": 0.5}, {"UNKNOWN": rates}, {"UNKNOWN": durs}, t0, t1, MC=5)
    np.random.seed(0)
    pair = extrapolation({"UNKNOWN": 0.5}, {"UNKNOWN": rates}, {"UNKNOWN": durs}, t0, t1, MC=5, sampling="paired")
    assert np.mean(pair["UNKNOWN"]) < 0.2 * np.mean(ind["UNKNOWN"])


def test_class_stratified_simulation_sums_independent_class_processes():
    rng = np.random.default_rng(5)
    classes = [dict(occupancy=0.2, rate_array=np.array([10.0]), duration_array=np.array([5.0])),
               dict(occupancy=0.3, rate_array=np.array([1.0]), duration_array=np.array([50.0]))]
    T = 100_000
    tot, emitting_by_class = simulate_renewal_emissions_by_class(T, classes, rng)
    assert tot / T == pytest.approx(0.2 * 10 + 0.3 * 1, rel=0.05)
    assert emitting_by_class[0] / T == pytest.approx(0.2, abs=0.02)
    assert emitting_by_class[1] / T == pytest.approx(0.3, abs=0.03)

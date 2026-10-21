"""
Tests for occupancy.py: estimating event occupancy (fraction of time emitting) from a
detection record of k detections in m observation attempts, accounting for detection
probability (POD), the small number of attempts, and selection of sources with k >= 1.

Model: k ~ Binomial(m, phi * POD), truncated at k >= 1; phi ~ Beta(a, b) prior fitted across
sources by maximizing the truncated marginal likelihood (empirical Bayes).

Run with:  python -m pytest test_occupancy.py
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from occupancy import fit_occupancy_prior, occupancy_posterior, truncated_binomial_loglik  # noqa: E402


def test_truncated_loglik_conditions_on_at_least_one_detection():
    # P(k=1 | m=1, theta) / P(k>=1) = 1 for any theta: log-lik must be 0.
    assert truncated_binomial_loglik(k=1, m=1, theta=0.3) == pytest.approx(0.0)
    # m=2, k=1: P = 2 th (1-th) / (1-(1-th)^2) = 2(1-th)/(2-th)
    th = 0.4
    assert truncated_binomial_loglik(1, 2, th) == pytest.approx(np.log(2 * (1 - th) / (2 - th)))


def test_posterior_grid_integrates_to_one():
    grid, pdf, _ = occupancy_posterior(k=2, m=5, pod=0.9, prior=(1.0, 1.0))
    assert np.trapezoid(pdf, grid) == pytest.approx(1.0, abs=1e-3)
    assert grid.min() >= 0 and grid.max() <= 1


def test_posterior_mean_rises_as_pod_falls():
    # Missed detections mean the source emitted more often than the raw persistence suggests.
    m_hi = occupancy_posterior(k=2, m=8, pod=1.0, prior=(1.0, 1.0))[2]["mean"]
    m_lo = occupancy_posterior(k=2, m=8, pod=0.6, prior=(1.0, 1.0))[2]["mean"]
    assert m_lo > m_hi


def test_posterior_capped_at_one_when_pod_below_persistence():
    # k=m=3 with POD=0.6 is only possible if phi*POD <= 0.6, so phi is capped at 1 with mass near 1.
    grid, pdf, summ = occupancy_posterior(k=3, m=3, pod=0.6, prior=(1.0, 1.0))
    assert summ["mean"] <= 1.0
    assert summ["q97.5"] <= 1.0


def test_one_of_one_is_shrunk_below_raw_persistence():
    # A 1-of-1 source has raw persistence 1.0. Its posterior is the length-biased population
    # prior, phi * Beta(a, b) ~ Beta(a+1, b), with mean (a+1)/(a+b+1) = 0.5 for Beta(2, 3): far
    # below the raw ratio, because being detected once is weak evidence of high occupancy.
    grid, pdf, summ = occupancy_posterior(k=1, m=1, pod=1.0, prior=(2.0, 3.0))
    assert summ["mean"] == pytest.approx(3.0 / 6.0, abs=0.01)


def test_many_attempts_posterior_concentrates_on_true_value():
    grid, pdf, summ = occupancy_posterior(k=300, m=1000, pod=1.0, prior=(1.0, 1.0))
    assert summ["mean"] == pytest.approx(0.3, abs=0.01)
    assert summ["q97.5"] - summ["q2.5"] < 0.1


def test_fit_prior_recovers_simulated_beta_parameters():
    rng = np.random.default_rng(0)
    a_true, b_true, pod = 1.5, 2.5, 0.9
    n = 3000
    phi = rng.beta(a_true, b_true, size=n)
    m = rng.integers(1, 12, size=n)
    k = rng.binomial(m, phi * pod)
    keep = k >= 1  # selection: only sources with at least one detection are listed
    a_hat, b_hat = fit_occupancy_prior(k[keep], m[keep], pod=pod)
    # mean of the prior should be recovered closely; shape parameters within a tolerance
    assert a_hat / (a_hat + b_hat) == pytest.approx(a_true / (a_true + b_true), abs=0.03)
    assert a_hat == pytest.approx(a_true, rel=0.3)
    assert b_hat == pytest.approx(b_true, rel=0.3)


def test_fit_prior_ignores_selection_bias_if_not_truncated():
    # Sanity: with truncation handled, the fitted prior mean is NOT pulled up by the k>=1 filter.
    # (Attempt counts must vary across sources: with a single m the two prior parameters are not
    # separately identifiable from listed sources alone.)
    rng = np.random.default_rng(1)
    phi = rng.beta(1.0, 4.0, size=4000)  # mean 0.2
    m = rng.integers(1, 12, size=4000)
    k = rng.binomial(m, phi)
    keep = k >= 1
    a_hat, b_hat = fit_occupancy_prior(k[keep], m[keep], pod=1.0)
    assert a_hat / (a_hat + b_hat) == pytest.approx(0.2, abs=0.04)
    # raw persistence among kept sources is materially higher than the true mean 0.2
    assert np.mean(k[keep] / m[keep]) > 0.3


def test_fit_prior_respects_lower_bound_on_a():
    # Only-listed data with many 1-of-1 sources pushes a -> 0; the bound keeps the prior proper.
    k = np.array([1] * 50 + [1, 2, 1, 3])
    m = np.array([1] * 50 + [4, 8, 6, 10])
    a, b = fit_occupancy_prior(k, m, pod=0.9, a_min=0.05)
    assert a >= 0.05

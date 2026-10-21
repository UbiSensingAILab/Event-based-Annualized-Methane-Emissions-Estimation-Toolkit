"""
Event occupancy from a detection record.

A screening programme that revisits a source gives, per source, k detections in m observation
attempts. The raw ratio k/m ("persistence" in the Carbon Mapper data portal) is a biased
estimate of the event occupancy phi (fraction of time emitting) because
  (1) a source that is emitting is detected only with probability POD < 1,
  (2) m is small (a few attempts), and
  (3) the source is listed only because it was detected at least once (k >= 1).

Model
-----
    k | m, phi ~ Binomial(m, theta),  theta = phi * POD,  observed only if k >= 1
    phi ~ Beta(a, b)                                       (shared across sources)

`fit_occupancy_prior` estimates (a, b) by maximising the truncated marginal likelihood over all
listed sources (empirical Bayes). `occupancy_posterior` returns the per-source posterior of phi
on a grid, from which draws can be taken inside a Monte Carlo ensemble.
"""

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln
from scipy.stats import beta as beta_dist

GRID = np.linspace(0.0005, 0.9995, 2000)


def truncated_binomial_loglik(k, m, theta):
    """log P(k | m, theta, k >= 1) for a Binomial(m, theta) truncated at k >= 1."""
    k = np.asarray(k, dtype=float)
    m = np.asarray(m, dtype=float)
    theta = np.clip(np.asarray(theta, dtype=float), 1e-12, 1 - 1e-12)
    log_choose = gammaln(m + 1) - gammaln(k + 1) - gammaln(m - k + 1)
    log_pmf = log_choose + k * np.log(theta) + (m - k) * np.log1p(-theta)
    log_norm = np.log1p(-np.exp(m * np.log1p(-theta)))  # log(1 - (1-theta)^m)
    return log_pmf - log_norm


def _binomial_loglik(k, m, theta):
    """log P(k | m, theta) for an (untruncated) Binomial."""
    k = np.asarray(k, dtype=float)
    m = np.asarray(m, dtype=float)
    theta = np.clip(np.asarray(theta, dtype=float), 1e-12, 1 - 1e-12)
    log_choose = gammaln(m + 1) - gammaln(k + 1) - gammaln(m - k + 1)
    return log_choose + k * np.log(theta) + (m - k) * np.log1p(-theta)


FIT_GRID = np.linspace(0.001, 0.999, 500)


def _source_marginal_loglik(k, m, pod, a, b, grid=FIT_GRID):
    """
    log P(k | m, a, b, pod, k >= 1), the marginal likelihood of a LISTED source:

        int P(k | m, phi*pod) Beta(phi; a, b) dphi  /  int P(k >= 1 | m, phi*pod) Beta(phi; a, b) dphi

    The denominator is the population-level probability that a source is listed at all, which is
    what corrects the prior fit for the k >= 1 selection.
    """
    prior = beta_dist.pdf(grid, a, b)
    theta = np.clip(grid[None, :] * pod, 1e-12, 1 - 1e-12)
    num = np.trapezoid(np.exp(_binomial_loglik(k[:, None], m[:, None], theta)) * prior[None, :],
                       grid, axis=1)
    p_listed = -np.expm1(m[:, None] * np.log1p(-theta))  # 1 - (1-theta)^m
    den = np.trapezoid(p_listed * prior[None, :], grid, axis=1)
    return np.log(np.clip(num, 1e-300, None)) - np.log(np.clip(den, 1e-300, None))


def fit_occupancy_prior(k, m, pod=1.0, grid=FIT_GRID, a_min=0.05):
    """
    Empirical-Bayes Beta(a, b) prior for occupancy, fitted by maximising the selection-corrected
    marginal likelihood over all listed sources (k >= 1).

    `a_min` bounds the first shape parameter away from zero. With only listed sources the mass of
    never-emitting sources (phi -> 0) is not identifiable and the likelihood keeps improving as
    a -> 0; the bound keeps the prior proper. The per-source posterior means are insensitive to
    this choice (for the Case Study 1 data the basin-mean occupancy moves by < 0.005 for a between
    0.02 and 2).

    Returns (a, b).
    """
    k = np.asarray(k, dtype=float)
    m = np.asarray(m, dtype=float)
    if np.any(k < 1) or np.any(k > m):
        raise ValueError("each source needs 1 <= k <= m")

    def unpack(params):
        return a_min + np.exp(params[0]), np.exp(params[1])

    def nll(params):
        a, b = unpack(params)
        return -np.sum(_source_marginal_loglik(k, m, pod, a, b, grid))

    best = None
    for a0, b0 in [(1.0, 1.0), (1.0, 4.0)]:
        res = minimize(nll, [np.log(a0), np.log(b0)], method="Nelder-Mead",
                       options={"xatol": 1e-4, "fatol": 1e-6, "maxiter": 1000})
        if best is None or res.fun < best.fun:
            best = res
    a, b = unpack(best.x)
    return float(a), float(b)


def occupancy_posterior(k, m, pod=1.0, prior=(1.0, 1.0), grid=GRID):
    """
    Posterior of occupancy phi for one source with k detections in m attempts.

    Returns (grid, pdf, summary) where pdf integrates to 1 over grid and summary has
    'mean', 'median', 'q2.5', 'q97.5'. phi is restricted to phi * pod <= 1.

    Because k is observed, the k >= 1 selection does not alter this posterior; it is accounted
    for when the population prior (a, b) is fitted with `fit_occupancy_prior`. A listed source
    with few attempts is therefore pulled toward the (length-biased) population prior rather
    than toward its raw ratio k/m.
    """
    a, b = prior
    ll = _binomial_loglik(k, m, grid * pod)
    ll = np.where(grid * pod > 1, -np.inf, ll)
    log_post = ll + beta_dist.logpdf(grid, a, b)
    log_post -= np.max(log_post)
    pdf = np.exp(log_post)
    pdf /= np.trapezoid(pdf, grid)
    cdf = np.concatenate([[0.0], np.cumsum(0.5 * (pdf[1:] + pdf[:-1]) * np.diff(grid))])
    cdf /= cdf[-1]
    summary = {
        "mean": float(np.trapezoid(grid * pdf, grid)),
        "median": float(np.interp(0.5, cdf, grid)),
        "q2.5": float(np.interp(0.025, cdf, grid)),
        "q97.5": float(np.interp(0.975, cdf, grid)),
    }
    return grid, pdf, summary


def sample_occupancy(k, m, pod, prior, rng, size=1, grid=GRID):
    """Draw `size` occupancy values from the posterior of one source (inverse-CDF on the grid)."""
    g, pdf, _ = occupancy_posterior(k, m, pod, prior, grid)
    cdf = np.concatenate([[0.0], np.cumsum(0.5 * (pdf[1:] + pdf[:-1]) * np.diff(g))])
    cdf /= cdf[-1]
    return np.interp(rng.random(size), cdf, g)

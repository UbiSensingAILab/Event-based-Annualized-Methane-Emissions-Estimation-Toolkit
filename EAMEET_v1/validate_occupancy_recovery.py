"""
Recovery test for the Type 2 unmeasured-emission (UE) process used by `extrapolation()`.

Demonstrates that the alternating-renewal process (`simulations.simulate_renewal_emissions`)
recovers a prescribed event occupancy (fraction of time emitting) and event frequency, for
constant and heavy-tailed duration distributions, and that the result does not depend on any
simulation time step. For comparison it also evaluates the superseded hourly Bernoulli scheme
(a failed trial advanced the clock by one step, a successful trial by the sampled duration),
whose realized occupancy is inflated and drifts with the step length.

Usage:
    python validate_occupancy_recovery.py [--out validation_outputs] [--reps 200]

Writes <out>/occupancy_recovery.csv and <out>/occupancy_recovery.png.
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import weibull_min

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from simulations import simulate_renewal_emissions  # noqa: E402

# Duration models used in the demonstration (hours).
# "cs2_weibull": Weibull fit to the Case Study 2 event durations (shape 0.583, scale 15.4 h; 86 events,
#                regenerated 2026-10-10 with the detection-conditioned flyover-PRE duration).
# "cs1_weibull": Weibull fit to the Case Study 1 Carbon Mapper event durations (shape 0.558, scale 1961 h).
DURATION_MODELS = {
    "constant_10h": lambda rng, n: np.full(n, 10.0),
    "cs2_weibull": lambda rng, n: weibull_min.rvs(0.583, 0, 15.424, size=n, random_state=rng),
    "cs1_weibull": lambda rng, n: weibull_min.rvs(0.558, 0, 1960.7, size=n, random_state=rng),
}
DURATION_MEANS = {
    "constant_10h": 10.0,
    "cs2_weibull": weibull_min.mean(0.583, 0, 15.424),
    "cs1_weibull": weibull_min.mean(0.558, 0, 1960.7),
}
N_SAMPLES = 20000


def _bernoulli_legacy(total_hours, p, duration_array, rng, dt):
    """Superseded scheme: per step of length dt, Bernoulli(p); miss -> +dt, hit -> +D."""
    t, emitting, n = 0.0, 0.0, 0
    while t < total_hours:
        if rng.random() >= p:
            t += dt
        else:
            d = float(rng.choice(duration_array))
            d = min(d, total_hours - t)
            if d <= 0:
                d = dt
            emitting += d
            n += 1
            t += d
    return min(emitting, total_hours), n


def evaluate_recovery(scheme, phi, duration_array, total_hours=20000, reps=200, seed=0, dt=1.0,
                      mean_duration=None):
    """
    Simulate `reps` realizations of `scheme` ("renewal" or "bernoulli") over `total_hours` with
    prescribed occupancy `phi` and return mean realized occupancy and event count.

    For "renewal", dt is only the grid on which emitting time is tallied (the process itself is
    continuous in time). For "bernoulli", dt is the trial step length.
    """
    rng = np.random.default_rng(seed)
    duration_array = np.asarray(duration_array, dtype=float)
    mean_d = float(duration_array.mean()) if mean_duration is None else float(mean_duration)
    occ, n_ev = [], []
    for _ in range(reps):
        if scheme == "renewal":
            _, emitting, n = simulate_renewal_emissions(
                total_hours, phi, np.ones(1), duration_array, rng, mean_duration=mean_d)
            # tally on a dt grid (rounds emitting time to the nearest grid cell)
            emitting = np.round(emitting / dt) * dt
        elif scheme == "bernoulli":
            emitting, n = _bernoulli_legacy(total_hours, phi, duration_array, rng, dt)
        else:
            raise ValueError(scheme)
        occ.append(emitting / total_hours)
        n_ev.append(n)
    return {
        "scheme": scheme,
        "dt_hours": dt,
        "prescribed_occupancy": phi,
        "realized_occupancy": float(np.mean(occ)),
        "expected_events": phi * total_hours / mean_d,
        "realized_events": float(np.mean(n_ev)),
        "mean_duration_h": mean_d,
    }


def run_recovery_table(occupancies=(0.1, 0.3, 0.583, 0.9),   # 0.583 = Case Study 2 occupancy
                       duration_models=("constant_10h", "cs2_weibull", "cs1_weibull"),
                       time_steps=(0.25, 1.0, 6.0, 24.0), total_hours=20000, reps=200, seed=0):
    rows = []
    rng = np.random.default_rng(seed)
    for dm in duration_models:
        durs = DURATION_MODELS[dm](rng, N_SAMPLES)
        mean_d = DURATION_MEANS[dm]
        th = total_hours if dm != "cs1_weibull" else max(total_hours, 50 * int(mean_d))
        for phi in occupancies:
            for dt in time_steps:
                for scheme in ("renewal", "bernoulli"):
                    r = evaluate_recovery(scheme, phi, durs, total_hours=th, reps=reps,
                                          seed=seed, dt=dt, mean_duration=mean_d)
                    r["duration_model"] = dm
                    r["window_hours"] = th
                    rows.append(r)
    return pd.DataFrame(rows)


def _plot(df, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    models = list(dict.fromkeys(df["duration_model"]))
    fig, axes = plt.subplots(1, len(models), figsize=(4.2 * len(models), 3.8), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, dm in zip(axes, models):
        sub = df[df["duration_model"] == dm]
        ax.plot([0, 1], [0, 1], "k--", lw=1, label="1:1 (prescribed)")
        ren = sub[sub["scheme"] == "renewal"].groupby("prescribed_occupancy")["realized_occupancy"].mean()
        ax.plot(ren.index, ren.values, "o-", color="C2", label="alternating renewal (any Δt)")
        for dt, mk in zip(sorted(sub["dt_hours"].unique()), ["^", "s", "v", "D"]):
            b = sub[(sub["scheme"] == "bernoulli") & (sub["dt_hours"] == dt)]
            ax.plot(b["prescribed_occupancy"], b["realized_occupancy"], mk + "--", color="C3",
                    alpha=0.4 + 0.15 * list(sorted(sub["dt_hours"].unique())).index(dt),
                    label=f"hourly-Bernoulli scheme, Δt={dt:g} h")
        ax.set_title(f"{dm} (E[D] = {DURATION_MEANS[dm]:.0f} h)")
        ax.set_xlabel("prescribed occupancy φ")
        ax.set_xlim(0, 1); ax.set_ylim(0, 1.02); ax.grid(alpha=0.3)
    axes[0].set_ylabel("realized occupancy")
    axes[-1].legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "validation_outputs"))
    ap.add_argument("--reps", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    df = run_recovery_table(reps=args.reps, seed=args.seed)
    csv = os.path.join(args.out, "occupancy_recovery.csv")
    df.to_csv(csv, index=False)
    _plot(df, os.path.join(args.out, "occupancy_recovery.png"))
    pd.set_option("display.width", 200)
    print(df.round(3).to_string(index=False))
    print(f"\nWrote {csv}")


if __name__ == "__main__":
    main()

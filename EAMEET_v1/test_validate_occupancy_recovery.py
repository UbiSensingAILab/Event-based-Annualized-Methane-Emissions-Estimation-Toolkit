"""
Tests for validate_occupancy_recovery.py: the demonstration that the alternating-renewal UE
process recovers a prescribed occupancy and event frequency, and that the superseded hourly
Bernoulli scheme does not (and drifts with the time step).

Run with:  python -m pytest test_validate_occupancy_recovery.py
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from validate_occupancy_recovery import (  # noqa: E402
    evaluate_recovery,
    run_recovery_table,
)

CONST_10H = np.array([10.0])


def test_renewal_recovers_occupancy_and_event_frequency():
    r = evaluate_recovery("renewal", 0.572, CONST_10H, total_hours=20000, reps=100, seed=0)
    assert r["prescribed_occupancy"] == 0.572
    assert r["realized_occupancy"] == pytest.approx(0.572, abs=0.02)
    # expected onsets = phi * T / E[D]
    assert r["expected_events"] == pytest.approx(0.572 * 20000 / 10.0)
    assert r["realized_events"] == pytest.approx(r["expected_events"], rel=0.05)


def test_legacy_bernoulli_at_one_hour_reproduces_reviewer_example():
    # p = 0.572, constant 10 h events, 1 h step -> ~93% occupancy (reviewer's diagnostic)
    r = evaluate_recovery("bernoulli", 0.572, CONST_10H, total_hours=20000, reps=100, seed=0, dt=1.0)
    assert r["realized_occupancy"] == pytest.approx(0.930, abs=0.02)


def test_legacy_bernoulli_occupancy_depends_on_time_step():
    fine = evaluate_recovery("bernoulli", 0.572, CONST_10H, total_hours=20000, reps=50, seed=1, dt=0.25)
    coarse = evaluate_recovery("bernoulli", 0.572, CONST_10H, total_hours=20000, reps=50, seed=1, dt=24.0)
    assert fine["realized_occupancy"] > 0.95
    assert coarse["realized_occupancy"] < 0.60
    assert fine["realized_occupancy"] - coarse["realized_occupancy"] > 0.3


def test_renewal_is_independent_of_time_step_argument():
    # The renewal process has no time step; dt only sets the grid on which occupancy is measured.
    a = evaluate_recovery("renewal", 0.3, CONST_10H, total_hours=20000, reps=50, seed=2, dt=0.25)
    b = evaluate_recovery("renewal", 0.3, CONST_10H, total_hours=20000, reps=50, seed=2, dt=24.0)
    assert a["realized_occupancy"] == pytest.approx(0.3, abs=0.03)
    assert b["realized_occupancy"] == pytest.approx(0.3, abs=0.03)


def test_run_recovery_table_has_expected_shape():
    df = run_recovery_table(occupancies=[0.1, 0.572], duration_models=["constant_10h"],
                            time_steps=[1.0, 24.0], total_hours=5000, reps=5, seed=3)
    # one row per (scheme, duration model, occupancy, dt); renewal rows once per dt as well
    assert set(df["scheme"]) == {"renewal", "bernoulli"}
    assert len(df) == 2 * 1 * 2 * 2
    for col in ["prescribed_occupancy", "realized_occupancy", "expected_events", "realized_events"]:
        assert col in df.columns

"""
Tests for the Type 1 (undetected-during-monitoring) simulation time budget and coverage schedule.

Reviewer comment 4: the monitored-period time budget must correspond to actual monitoring coverage
(no gaps, no double counting), each technology may only test the hypothetical events it could have
observed, and wind must be sampled per event rather than taken as a best case over the series.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulations import (calculate_total_simulation_time_steps,  # noqa: E402
                         monitored_gap_segments, simulate_below_mdl,
                         _simulate_below_mdl_single_iteration)
from utils import probability_of_detection  # noqa: E402

T0 = pd.Timestamp("2024-01-01 00:00:00")
T1 = T0 + pd.Timedelta(hours=100)


def _events(intervals):
    rows = [{"source": "A", "quantity": 1.0, "duration": float(b - a),
             "start_time": (T0 + pd.Timedelta(hours=a)).strftime("%Y-%m-%d %H:%M:%S"),
             "end_time": (T0 + pd.Timedelta(hours=b)).strftime("%Y-%m-%d %H:%M:%S")}
            for a, b in intervals]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- time budget
def test_gap_budget_is_window_minus_union_of_observed_events():
    ev = _events([(10, 20), (15, 30)])          # overlapping events occupy 20 h in total
    assert calculate_total_simulation_time_steps(ev, T0, T1) == pytest.approx(80.0)


def test_gap_budget_respects_coverage_intervals():
    ev = _events([(10, 20)])
    cov = [(T0, T0 + pd.Timedelta(hours=50))]    # CMS only up for the first 50 h
    assert calculate_total_simulation_time_steps(ev, T0, T1, coverage=cov) == pytest.approx(40.0)


def test_gap_segments_are_explicit_intervals_in_hours():
    ev = _events([(10, 20), (15, 30)])
    seg = monitored_gap_segments(ev, T0, T1)
    assert seg.tolist() == [[0.0, 10.0], [30.0, 100.0]]


def test_superseded_budget_mode_sums_observed_event_hours():
    ev = _events([(10, 20), (15, 30)])
    assert calculate_total_simulation_time_steps(ev, T0, T1, mode="observed_event_hours") == pytest.approx(25.0)


# ---------------------------------------------------------- coverage schedule
def _iteration(segments, pods, coverage, wind=None, seed=1, dur=10.0):
    args = (np.asarray(segments, dtype=float), np.array([dur]), np.array([1.0]), np.array([1]),
            pods, wind, seed, coverage)
    return _simulate_below_mdl_single_iteration(args)


def test_without_schedule_every_technology_tests_every_event():
    # POD = 1 everywhere -> nothing is missed
    assert _iteration([[0, 100]], [1.0], [None]) == pytest.approx(0.0)


def test_snapshot_technology_only_tests_events_overlapping_a_survey_instant():
    # 10 events of 10 h tile the 100 h budget; a survey at t = 5 h overlaps only the first event
    cov = [{"instants": np.array([5.0])}]
    assert _iteration([[0, 100]], [1.0], cov) == pytest.approx(90.0)


def test_interval_coverage_only_tests_events_inside_the_interval():
    cov = [{"intervals": np.array([[0.0, 50.0]])}]
    assert _iteration([[0, 100]], [1.0], cov) == pytest.approx(50.0)


def test_coverage_is_evaluated_in_real_time_across_gap_segments():
    # Budget = [0,10) U [60,100); CMS covered only [60,100) in real time. Events of 10 h:
    # the first event sits in [0,10) (uncovered -> missed), the other four are covered -> detected.
    cov = [{"intervals": np.array([[60.0, 100.0]])}]
    assert _iteration([[0, 10], [60, 100]], [1.0], cov) == pytest.approx(10.0)


def test_event_missed_by_all_covering_technologies_is_counted_once():
    # Two technologies with POD = 1: one covers [0,50), the other [50,100) -> nothing missed
    cov = [{"intervals": np.array([[0.0, 50.0]])}, {"intervals": np.array([[50.0, 100.0]])}]
    assert _iteration([[0, 100]], [1.0, 1.0], cov) == pytest.approx(0.0)


# --------------------------------------------------------------------- wind
def test_wind_array_is_sampled_per_event_not_taken_as_best_case():
    # Qube curve: ws = 0.1 m/s -> POD ~ 1 for Q = 1 kg/h; ws = 1000 m/s -> POD = 0.577.
    # A best-case (np.any over the series) evaluation would detect everything.
    pod, _ = probability_of_detection("Qube", wind_speed=np.array([0.1, 1000.0]), wind_consider=True)
    missed = _iteration([[0, 2000]], [pod], [None], wind=np.array([0.1, 1000.0]), dur=1.0)
    assert 300 < missed < 550          # ~2000 events x 0.5 x 0.423


def test_time_indexed_wind_series_is_matched_to_the_event_time():
    idx = pd.date_range(T0, periods=100, freq="h")
    ws = pd.Series(np.where(np.arange(100) < 50, 0.1, 1000.0), index=idx)
    pod, _ = probability_of_detection("Qube", wind_speed=ws, wind_consider=True)
    missed = _iteration([[0, 100]], [pod], [None], wind=ws, dur=1.0)
    assert 10 < missed < 35            # only the calm... i.e. the high-wind second half can be missed


# ------------------------------------------------------------ public routine
def test_public_routine_accepts_coverage_schedule_and_uses_gap_budget():
    ev = _events([(10, 20)])
    # Coverage restricted to the event hours only -> zero budget -> zero unresolved emissions
    # A user-defined technology with POD = 0 misses everything it covers, so the result is the
    # tiled mass of the budget: zero when the schedule leaves no gap hours, positive otherwise.
    kw = dict(mc_iterations=5, technologies=["User Defined"], mdl_define=1.0, pod_define=0.0)
    cov = {"User Defined": [(T0 + pd.Timedelta(hours=10), T0 + pd.Timedelta(hours=20))]}
    np.random.seed(0)
    res = simulate_below_mdl(ev, T0, T1, coverage=cov, **kw)
    assert res[6] == pytest.approx(0.0)
    np.random.seed(0)
    res_full = simulate_below_mdl(ev, T0, T1, **kw)
    assert res_full[6] > 0

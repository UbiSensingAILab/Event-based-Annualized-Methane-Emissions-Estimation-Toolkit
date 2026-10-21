"""
Tests of the time-weighted, scale-aware combination of observations within an event
(reviewer comment 5): mass preservation, invariance to duplicates and to splitting an
observation, independence of merge order, and the three worked examples of SI Section S2.1.

Run with:  python -m pytest test_event_integration.py
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from emission_event_converter import (
    convert_to_emission_event_model,
    integrate_event,
    resolve_rate_at,
)

MAPPING = {
    "id": "id", "rate": "rate", "source": "source", "uncertainties": "unc",
    "start_time": "start", "end_time": "end", "time": "time",
    "observation_type": "obs_type", "observation_scale": "scale", "feature": "feature",
}


def _df(rows):
    """rows: (id, time, start, end, rate, unc, obs_type, scale, feature) for source 'S'."""
    return pd.DataFrame([dict(id=i, source="S", time=t, start=s, end=e, rate=r, unc=u,
                              obs_type=k, scale=sc, feature=f)
                         for i, t, s, e, r, u, k, sc, f in rows])


def _convert(df, **kw):
    return convert_to_emission_event_model(df, MAPPING, time_column="time",
                                           emission_characteristics="intermittent", **kw)


# ------------------------------------------------------------------ worked example 1: persistent leak
LEAK = [  # the same equipment-scale leak seen by a CMS twice (overlapping alarms) and by one flyover
    ("CMS-a", "2024-03-01 00:00", "2024-03-01 00:00", "2024-03-01 10:00", 10.0, 2.0, "cms", "equipment", "Comp-1"),
    ("CMS-b", "2024-03-01 08:00", "2024-03-01 08:00", "2024-03-01 20:00", 20.0, 4.0, "cms", "equipment", "Comp-1"),
]


def test_persistent_leak_mass_is_preserved():
    ev = _convert(_df(LEAK))
    assert len(ev) == 1
    # 0-8 h: 10 kg/h; 8-10 h: average of the two replicates = 15 kg/h; 10-20 h: 20 kg/h
    assert ev.quantity.iloc[0] == pytest.approx(8 * 10 + 2 * 15 + 10 * 20)        # 310 kg
    assert ev.duration.iloc[0] == pytest.approx(20.0)
    assert ev.rate.iloc[0] == pytest.approx(310.0 / 20.0)
    # the former rule (mean rate x union) would have given 15 x 20 = 300 kg


def test_persistent_leak_single_observation_is_its_own_mass():
    ev = _convert(_df(LEAK[:1]))
    assert ev.quantity.iloc[0] == pytest.approx(100.0)
    assert ev.rate.iloc[0] == pytest.approx(10.0)
    assert ev.uncertainties.iloc[0] == pytest.approx(2.0)


def test_repeated_snapshot_detections_count_the_emission_once():
    """A persistent leak seen by three flyovers whose null-detection brackets overlap becomes ONE event:
    the snapshots are samples of the event rate (averaged) and the quantity is rate x bound once,
    not once per detection."""
    rows = [
        ("N0", "2024-01-01 00:00", None, None, 0.0, 0.0, "flyover", "site", "S"),      # null detection
        ("F1", "2024-01-10 12:00", None, None, 100.0, 25.0, "flyover", "site", "S"),
        ("F2", "2024-01-20 12:00", None, None, 140.0, 35.0, "flyover", "site", "S"),
        ("F3", "2024-01-30 12:00", None, None, 120.0, 30.0, "flyover", "site", "S"),
        ("N1", "2024-02-05 00:00", None, None, 0.0, 0.0, "flyover", "site", "S"),      # null detection
    ]
    ev = _convert(_df(rows))
    assert len(ev) == 1
    assert ev.n_observations.iloc[0] == 3
    hours = (pd.Timestamp("2024-02-05") - pd.Timestamp("2024-01-01")).total_seconds() / 3600
    assert ev.duration.iloc[0] == pytest.approx(hours)
    assert ev.rate.iloc[0] == pytest.approx(120.0)
    assert ev.quantity.iloc[0] == pytest.approx(120.0 * hours)
    assert pd.Timestamp(ev.first_detection.iloc[0]) == pd.Timestamp("2024-01-10 12:00")
    assert pd.Timestamp(ev.last_detection.iloc[0]) == pd.Timestamp("2024-01-30 12:00")


# ------------------------------------------------------------------ worked example 2: concurrent components
CONCURRENT = [
    ("OGI-1", "2024-03-01 00:00", "2024-03-01 00:00", "2024-03-01 10:00", 2.0, 0.5, "ogi", "component", "Valve-1"),
    ("OGI-2", "2024-03-01 00:00", "2024-03-01 04:00", "2024-03-01 10:00", 3.0, 0.6, "ogi", "component", "Flange-7"),
]


def test_concurrent_components_are_summed_not_averaged():
    ev = _convert(_df(CONCURRENT))
    assert len(ev) == 1
    # 0-4 h: Valve-1 only (2 kg/h); 4-10 h: Valve-1 + Flange-7 (5 kg/h)
    assert ev.quantity.iloc[0] == pytest.approx(4 * 2 + 6 * 5)                    # 38 kg
    assert ev.rate.iloc[0] == pytest.approx(38.0 / 10.0)
    assert ev.uncertainties.iloc[0] == pytest.approx((4 * 0.5 + 6 * (0.5**2 + 0.6**2) ** 0.5) / 10)


def test_replicates_of_the_same_component_are_averaged():
    rows = [r[:8] + ("Valve-1",) for r in CONCURRENT]    # both observations on the same component
    ev = _convert(_df(rows))
    assert ev.quantity.iloc[0] == pytest.approx(4 * 2 + 6 * 2.5)                  # 31 kg


# ------------------------------------------------------------------ worked example 3: facility over components
NESTED = [
    ("FLY-1", "2024-03-01 05:00", "2024-03-01 02:00", "2024-03-01 08:00", 12.0, 3.0, "flyover", "site", "S"),
    ("OGI-1", "2024-03-01 00:00", "2024-03-01 00:00", "2024-03-01 10:00", 2.0, 0.5, "ogi", "component", "Valve-1"),
    ("OGI-2", "2024-03-01 00:00", "2024-03-01 04:00", "2024-03-01 10:00", 3.0, 0.6, "ogi", "component", "Flange-7"),
]


def test_facility_measurement_is_combined_with_not_added_to_components():
    ev = _convert(_df(NESTED))
    assert len(ev) == 1
    # 0-2 h: 2;  2-4 h: avg(12, 2) = 7;  4-8 h: avg(12, 2+3) = 8.5;  8-10 h: 5
    assert ev.quantity.iloc[0] == pytest.approx(2 * 2 + 2 * 7 + 4 * 8.5 + 2 * 5)   # 62 kg
    assert ev.rate.iloc[0] == pytest.approx(62.0 / 10.0)
    # never 12 + 2 + 3 = 17 kg/h (adding the facility measurement to the components it already contains)
    assert ev.rate.iloc[0] < 12.0


def test_facility_preference_overrides_components_where_it_is_active():
    ev = _convert(_df(NESTED), rate_operation="preference", preferred_observation_type="flyover")
    # 0-2 h: 2 (components only);  2-8 h: 12 (flyover preferred);  8-10 h: 5
    assert ev.quantity.iloc[0] == pytest.approx(2 * 2 + 6 * 12 + 2 * 5)            # 86 kg


def test_lowest_uncertainty_across_scales_uses_relative_choice_of_absolute_uncertainty():
    ev = _convert(_df(NESTED), rate_operation="lowest_uncertainty")
    # components aggregate has unc 0.5 (0-4 h) / 0.78 (4-10 h) < flyover 3.0 -> components win where present
    assert ev.quantity.iloc[0] == pytest.approx(4 * 2 + 6 * 5)                     # 38 kg


# ------------------------------------------------------------------ invariances
def test_duplicate_record_does_not_change_the_event():
    base = _convert(_df(LEAK))
    dup = _convert(_df(LEAK + [LEAK[1]]))                                 # exact duplicate (same id)
    dup2 = _convert(_df(LEAK + [("CMS-b-copy",) + LEAK[1][1:]]))          # identical fields, new id
    for d in (dup, dup2):
        assert len(d) == 1
        assert d.quantity.iloc[0] == pytest.approx(base.quantity.iloc[0])
        assert d.rate.iloc[0] == pytest.approx(base.rate.iloc[0])
        assert d.uncertainties.iloc[0] == pytest.approx(base.uncertainties.iloc[0])


def test_splitting_an_observation_does_not_change_the_result():
    whole = [("CMS-a", "2024-03-01 00:00", "2024-03-01 00:00", "2024-03-01 10:00", 10.0, 2.0, "cms", "equipment", "Comp-1")]
    halves = [("CMS-a1", "2024-03-01 00:00", "2024-03-01 00:00", "2024-03-01 06:00", 10.0, 2.0, "cms", "equipment", "Comp-1"),
              ("CMS-a2", "2024-03-01 06:00", "2024-03-01 06:00", "2024-03-01 10:00", 10.0, 2.0, "cms", "equipment", "Comp-1")]
    # (a) alone: the halves 'meet' and stay separate events, but the total mass is unchanged
    assert _convert(_df(halves)).quantity.sum() == pytest.approx(_convert(_df(whole)).quantity.sum())
    # (b) inside a larger event (overlapping CMS-b): same single event, same mass, same rate
    ev_w = _convert(_df(whole + [LEAK[1]]))
    ev_h = _convert(_df(halves + [LEAK[1]]))
    assert len(ev_w) == len(ev_h) == 1
    assert ev_h.quantity.iloc[0] == pytest.approx(ev_w.quantity.iloc[0])
    assert ev_h.rate.iloc[0] == pytest.approx(ev_w.rate.iloc[0])
    assert ev_h.uncertainties.iloc[0] == pytest.approx(ev_w.uncertainties.iloc[0])


@pytest.mark.parametrize("seed", range(5))
def test_result_is_independent_of_input_order(seed):
    rows = LEAK + NESTED[1:] + [
        ("CMS-c", "2024-03-01 15:00", "2024-03-01 15:00", "2024-03-01 23:00", 40.0, 8.0, "cms", "equipment", "Comp-2"),
    ]
    ref = _convert(_df(rows))
    rng = np.random.default_rng(seed)
    shuffled = [rows[i] for i in rng.permutation(len(rows))]
    out = _convert(_df(shuffled))
    assert len(out) == len(ref) == 1
    assert out.quantity.iloc[0] == pytest.approx(ref.quantity.iloc[0])
    assert out.rate.iloc[0] == pytest.approx(ref.rate.iloc[0])
    assert out.uncertainties.iloc[0] == pytest.approx(ref.uncertainties.iloc[0])
    assert sorted(out.merged_from.iloc[0].split(", ")) == sorted(ref.merged_from.iloc[0].split(", "))


def test_integrate_event_three_way_merge_equals_direct_integration():
    """Merging A+B then C gives exactly the integral over the pooled set (no pairwise weighting)."""
    obs = [dict(id="A", rate=10.0, uncertainty=1.0, observation_type="cms", scale="equipment", feature="E",
                start="2024-01-01 00:00", end="2024-01-01 06:00"),
           dict(id="B", rate=20.0, uncertainty=1.0, observation_type="cms", scale="equipment", feature="E",
                start="2024-01-01 01:00", end="2024-01-01 05:00"),
           dict(id="C", rate=60.0, uncertainty=1.0, observation_type="cms", scale="equipment", feature="E",
                start="2024-01-01 02:00", end="2024-01-01 04:00")]
    r = integrate_event(obs, "2024-01-01 00:00", "2024-01-01 06:00")
    assert r["quantity"] == pytest.approx(110.0)
    assert r["rate"] == pytest.approx(110.0 / 6.0)
    # observation-level masses: 60 + 80 + 120 = 260 kg would triple-count the shared hours; the
    # time-weighted average over the overlap keeps the event mass at 110 kg


def test_resolve_rate_at_hierarchy():
    comp = [dict(rate=2.0, uncertainty=0.5, observation_type="ogi", scale="component", feature="V1"),
            dict(rate=3.0, uncertainty=0.6, observation_type="ogi", scale="component", feature="F7")]
    site = [dict(rate=12.0, uncertainty=3.0, observation_type="flyover", scale="site", feature="S")]
    assert resolve_rate_at(comp)[0] == pytest.approx(5.0)                 # distinct components: summed
    assert resolve_rate_at(site + comp)[0] == pytest.approx(8.5)          # nested: averaged with 5.0
    assert resolve_rate_at(site + comp, "addition")[0] == pytest.approx(8.5)   # 'addition' never crosses scales
    assert resolve_rate_at(site + comp, "preference", "flyover")[0] == pytest.approx(12.0)
    assert resolve_rate_at(site + comp, "lowest_uncertainty")[0] == pytest.approx(5.0)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))


# ------------------------------------------------------------------ continuation records ('meets')
def test_consecutive_pieces_of_one_measured_record_merge():
    halves = [("CMS-a1", "2024-03-01 00:00", "2024-03-01 00:00", "2024-03-01 06:00", 10.0, 2.0, "cms", "equipment", "Comp-1"),
              ("CMS-a2", "2024-03-01 06:00", "2024-03-01 06:00", "2024-03-01 10:00", 10.0, 2.0, "cms", "equipment", "Comp-1")]
    ev = _convert(_df(halves))
    assert len(ev) == 1
    assert ev.quantity.iloc[0] == pytest.approx(100.0)
    assert ev.rate.iloc[0] == pytest.approx(10.0)
    assert ev.uncertainties.iloc[0] == pytest.approx(2.0)


def test_meeting_records_of_different_type_or_feature_stay_separate():
    a = ("CMS-a", "2024-03-01 00:00", "2024-03-01 00:00", "2024-03-01 06:00", 10.0, 2.0, "cms", "equipment", "Comp-1")
    other_type = ("OGI-x", "2024-03-01 06:00", "2024-03-01 06:00", "2024-03-01 10:00", 10.0, 2.0, "ogi", "equipment", "Comp-1")
    other_feat = ("CMS-y", "2024-03-01 06:00", "2024-03-01 06:00", "2024-03-01 10:00", 10.0, 2.0, "cms", "equipment", "Comp-2")
    assert len(_convert(_df([a, other_type]))) == 2
    assert len(_convert(_df([a, other_feat]))) == 2


def test_snapshot_bounds_meeting_at_a_null_detection_stay_separate():
    rows = [
        ("N0", "2024-01-01 00:00", None, None, 0.0, 0.0, "flyover", "site", "S"),
        ("F1", "2024-01-10 12:00", None, None, 100.0, 25.0, "flyover", "site", "S"),
        ("N1", "2024-02-05 00:00", None, None, 0.0, 0.0, "flyover", "site", "S"),   # emission stopped
        ("F2", "2024-02-20 12:00", None, None, 140.0, 35.0, "flyover", "site", "S"),
        ("N2", "2024-03-05 00:00", None, None, 0.0, 0.0, "flyover", "site", "S"),
    ]
    ev = _convert(_df(rows))
    assert len(ev) == 2

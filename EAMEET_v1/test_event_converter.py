"""
Tests for the event-merging rules and rate-resolution operations in emission_event_converter.

Run with:  python -m pytest test_event_converter.py   (or: python test_event_converter.py)
"""

import os
import sys
import warnings

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from emission_event_converter import (
    RATE_OPERATIONS,
    can_merge_events,
    convert_to_emission_event_model,
    resolve_event_rate,
)

MAPPING = {
    "id": "id",
    "rate": "rate",
    "source": "source",
    "uncertainties": "unc",
    "start_time": "start",
    "end_time": "end",
    "time": "start",
    "observation_type": "obs_type",
}


def _obs(rows):
    """rows: (id, start, end, rate, unc, obs_type) -> observation DataFrame for one source."""
    return pd.DataFrame(
        [dict(id=i, source="S", start=s, end=e, rate=r, unc=u, obs_type=t) for i, s, e, r, u, t in rows]
    )


def _convert(df, **kw):
    return convert_to_emission_event_model(df, MAPPING, emission_characteristics="intermittent", **kw)


def _ev(start, end):
    return {"source": {"physicalSource": "S", "sourceLocation": "S"}, "startTime": start, "endTime": end}


# --- Allen relations: which keep events separate and which merge -----------------------------

@pytest.mark.parametrize(
    "a, b, merges",
    [
        (("2024-01-01 00:00", "2024-01-01 02:00"), ("2024-01-01 03:00", "2024-01-01 04:00"), False),  # precedes
        (("2024-01-01 00:00", "2024-01-01 02:00"), ("2024-01-01 02:00", "2024-01-01 04:00"), False),  # meets
        (("2024-01-01 02:00", "2024-01-01 04:00"), ("2024-01-01 00:00", "2024-01-01 02:00"), False),  # met by
        (("2024-01-01 00:00", "2024-01-01 03:00"), ("2024-01-01 02:00", "2024-01-01 05:00"), True),   # overlaps
        (("2024-01-01 00:00", "2024-01-01 02:00"), ("2024-01-01 00:00", "2024-01-01 05:00"), True),   # starts
        (("2024-01-01 01:00", "2024-01-01 02:00"), ("2024-01-01 00:00", "2024-01-01 05:00"), True),   # during
        (("2024-01-01 03:00", "2024-01-01 05:00"), ("2024-01-01 00:00", "2024-01-01 05:00"), True),   # finishes
        (("2024-01-01 00:00", "2024-01-01 05:00"), ("2024-01-01 00:00", "2024-01-01 05:00"), True),   # equals
        (("2024-01-01 00:00", "2024-01-01 00:00"), ("2024-01-01 00:00", "2024-01-01 00:00"), True),   # equals, zero length
    ],
)
def test_can_merge_events_follows_allen_relations(a, b, merges):
    assert can_merge_events(_ev(*a), _ev(*b)) is merges


def test_different_sources_never_merge():
    e1, e2 = _ev("2024-01-01 00:00", "2024-01-01 05:00"), _ev("2024-01-01 01:00", "2024-01-01 02:00")
    e2["source"] = {"physicalSource": "T", "sourceLocation": "T"}
    assert can_merge_events(e1, e2) is False


def test_meeting_observations_become_separate_events_unless_continuation():
    # two measured-interval records of the same feature and technology that touch end-to-start are
    # pieces of one continued record (merged, mass preserved); records of different technologies that
    # merely meet stay separate (Allen 'meets')
    same = _obs([
        ("A", "2024-01-01 00:00", "2024-01-01 02:00", 10.0, 1.0, "cms"),
        ("B", "2024-01-01 02:00", "2024-01-01 04:00", 20.0, 2.0, "cms"),
    ])
    ev = _convert(same)
    assert len(ev) == 1 and ev.quantity.iloc[0] == pytest.approx(20 + 40)
    different = _obs([
        ("A", "2024-01-01 00:00", "2024-01-01 02:00", 10.0, 1.0, "cms"),
        ("B", "2024-01-01 02:00", "2024-01-01 04:00", 20.0, 2.0, "ogi"),
    ])
    assert len(_convert(different)) == 2


# --- Rate operations (Table 1) ---------------------------------------------------------------

THREE = [
    ("A", "2024-01-01 00:00", "2024-01-01 06:00", 10.0, 3.0, "cms"),
    ("B", "2024-01-01 01:00", "2024-01-01 05:00", 20.0, 4.0, "flyover"),
    ("C", "2024-01-01 02:00", "2024-01-01 04:00", 60.0, 12.0, "cms"),
]
# Time-weighted combination (revision for reviewer comment 5). The three interval observations split the
# 6 h bound into 0-1 h (A), 1-2 h (A, B), 2-4 h (A, B, C), 4-5 h (A, B) and 5-6 h (A). With 'average'
# the sub-interval rates are 10, 15, 30, 15, 10 kg/h -> 110 kg over 6 h -> 18.33 kg/h. The former rule
# (mean of the three rates, 30 kg/h, times the 6 h union = 180 kg) did not preserve integrated mass.


def test_average_is_time_weighted_over_sub_intervals():
    ev = _convert(_obs(THREE))
    assert len(ev) == 1
    assert ev.quantity.iloc[0] == pytest.approx(110.0)
    assert ev.duration.iloc[0] == pytest.approx(6.0)
    assert ev.rate.iloc[0] == pytest.approx(110.0 / 6.0)
    # sub-interval uncertainties (RSS/n of the active replicates) combined linearly in time, / duration
    u01 = 3.0; u12 = (3**2 + 4**2) ** 0.5 / 2; u24 = (3**2 + 4**2 + 12**2) ** 0.5 / 3
    assert ev.uncertainties.iloc[0] == pytest.approx((u01 * 1 + u12 * 1 + u24 * 2 + u12 * 1 + u01 * 1) / 6)


def test_addition_sums_rates_within_each_sub_interval():
    ev = _convert(_obs(THREE), rate_operation="addition")
    # 10 + 30 + 2*90 + 30 + 10 = 260 kg over 6 h
    assert ev.quantity.iloc[0] == pytest.approx(260.0)
    assert ev.rate.iloc[0] == pytest.approx(260.0 / 6.0)
    u01 = 3.0; u12 = (3**2 + 4**2) ** 0.5; u24 = (3**2 + 4**2 + 12**2) ** 0.5
    assert ev.uncertainties.iloc[0] == pytest.approx((u01 + u12 + 2 * u24 + u12 + u01) / 6)


def test_lowest_uncertainty_selects_best_observation():
    ev = _convert(_obs(THREE), rate_operation="lowest_uncertainty")
    assert ev.rate.iloc[0] == pytest.approx(10.0)
    assert ev.uncertainties.iloc[0] == pytest.approx(3.0)


def test_preference_selects_preferred_type_where_it_is_active():
    ev = _convert(_obs(THREE), rate_operation="preference", preferred_observation_type="flyover")
    # B (flyover) is active over 1-5 h -> 20 kg/h there; only A is active over 0-1 and 5-6 h -> 10 kg/h
    assert ev.quantity.iloc[0] == pytest.approx(10 + 20 * 4 + 10)
    assert ev.rate.iloc[0] == pytest.approx(100.0 / 6.0)


def test_preference_averages_several_preferred_observations():
    ev = _convert(_obs(THREE), rate_operation="preference", preferred_observation_type="CMS")
    # cms observations A and C: 0-2 h -> 10, 2-4 h -> 35, 4-6 h -> 10  => 20 + 70 + 20 = 110 kg
    assert ev.quantity.iloc[0] == pytest.approx(110.0)


def test_preference_falls_back_to_average_with_warning():
    with pytest.warns(UserWarning):
        ev = _convert(_obs(THREE), rate_operation="preference", preferred_observation_type="ogi")
    assert ev.rate.iloc[0] == pytest.approx(110.0 / 6.0)


def test_single_observation_is_unchanged_by_any_operation():
    df = _obs([("A", "2024-01-01 00:00", "2024-01-01 02:00", 10.0, 1.0, "cms")])
    for op in ("average", "addition", "lowest_uncertainty"):
        assert _convert(df, rate_operation=op).rate.iloc[0] == pytest.approx(10.0)


def test_invalid_options_raise():
    df = _obs(THREE)
    with pytest.raises(ValueError):
        _convert(df, rate_operation="median")
    with pytest.raises(ValueError):
        _convert(df, rate_operation="preference")  # no preferred type given


def test_resolve_event_rate_missing_uncertainty_gives_none():
    obs = [
        {"rate": 10.0, "uncertainty": None, "observation_type": None},
        {"rate": 20.0, "uncertainty": 2.0, "observation_type": None},
    ]
    assert resolve_event_rate(obs, "average") == (15.0, None)
    with pytest.warns(UserWarning):
        assert resolve_event_rate(
            [dict(o, uncertainty=None) for o in obs], "lowest_uncertainty"
        ) == (15.0, None)


def test_all_documented_operations_are_exposed():
    assert set(RATE_OPERATIONS) == {"average", "addition", "lowest_uncertainty", "preference"}


# --- detection-time evidence carried on every event (needed by the duration model) -------------

def test_single_detection_carries_its_detection_time():
    df = _obs([("a", "2024-01-01 00:00", "2024-01-01 02:00", 10.0, 1.0, "cms")])
    ev = _convert(df)
    assert pd.Timestamp(ev.first_detection.iloc[0]) == pd.Timestamp("2024-01-01 00:00")
    assert pd.Timestamp(ev.last_detection.iloc[0]) == pd.Timestamp("2024-01-01 00:00")


def test_merged_event_spans_first_to_last_detection():
    df = _obs([
        ("a", "2024-01-01 00:00", "2024-01-01 03:00", 10.0, 1.0, "cms"),   # overlaps b
        ("b", "2024-01-01 02:00", "2024-01-01 05:00", 10.0, 1.0, "cms"),   # overlaps c
        ("c", "2024-01-01 04:00", "2024-01-01 06:00", 10.0, 1.0, "cms"),
    ])
    ev = _convert(df)
    assert len(ev) == 1
    assert pd.Timestamp(ev.first_detection.iloc[0]) == pd.Timestamp("2024-01-01 00:00")
    assert pd.Timestamp(ev.last_detection.iloc[0]) == pd.Timestamp("2024-01-01 04:00")
    # detections always lie inside the event's temporal bound
    assert pd.Timestamp(ev.startTime.iloc[0]) <= pd.Timestamp(ev.first_detection.iloc[0])
    assert pd.Timestamp(ev.last_detection.iloc[0]) <= pd.Timestamp(ev.endTime.iloc[0])


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

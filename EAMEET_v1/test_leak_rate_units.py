"""
Units of the component-scale leak rates used by the Type 1 (below-MDL) simulation.

The simulation integrates rate x duration with durations in hours and reports kg, so the sampled
rates must be in kg/h. The bundled Rutherford et al. (2021) sample (sample_leak_rate.csv) is stored in
g/s (column 'gpersec') and must be converted with the factor 3.6 on loading; user-supplied rates are
kg/h unless leak_units="g/s" is passed.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import simulations  # noqa: E402
from simulations import G_PER_S_TO_KG_PER_H, _load_leak_data, simulate_below_mdl  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def _reset():
    simulations._leaks_dist = None
    simulations._leak_rates = None
    simulations._num_comps = None


def test_bundled_sample_is_converted_from_g_per_s_to_kg_per_h():
    _reset()
    _load_leak_data()
    raw = pd.read_csv(os.path.join(HERE, "sample_leak_rate.csv"))["gpersec"].values
    assert G_PER_S_TO_KG_PER_H == 3.6
    assert np.median(simulations._leaks_dist) == pytest.approx(np.median(raw) * 3.6)
    assert simulations._leaks_dist.max() == pytest.approx(raw.max() * 3.6)
    _reset()


def test_user_rates_default_to_kg_per_h_and_g_per_s_is_converted():
    _reset()
    _load_leak_data(leak_data=[1.0, 2.0])
    assert simulations._leaks_dist.tolist() == [1.0, 2.0]
    _load_leak_data(leak_data=[1.0, 2.0], leak_units="g/s")
    assert simulations._leaks_dist.tolist() == pytest.approx([3.6, 7.2])
    with pytest.raises(ValueError):
        _load_leak_data(leak_data=[1.0], leak_units="lb/min")
    _reset()


def _events():
    t0 = pd.Timestamp("2024-01-01")
    return pd.DataFrame([{"source": "A", "quantity": 1.0, "duration": 10.0,
                          "start_time": t0.strftime("%Y-%m-%d %H:%M:%S"),
                          "end_time": (t0 + pd.Timedelta(hours=10)).strftime("%Y-%m-%d %H:%M:%S")}])


def test_type1_term_scales_with_the_unit_conversion():
    """The same rates given in g/s must yield exactly 3.6x the kg/h result for the same seed."""
    _reset()
    ev = _events(); t0 = pd.Timestamp("2024-01-01"); t1 = t0 + pd.Timedelta(hours=200)
    kw = dict(mc_iterations=4, technology="define_technology", mdl_define=1.0, pod_define=0.5,
              num_components=np.ones(10))
    np.random.seed(5)
    a = simulate_below_mdl(ev, t0, t1, leak_data=[0.5, 1.0, 2.0], **kw)
    np.random.seed(5)
    b = simulate_below_mdl(ev, t0, t1, leak_data=[0.5, 1.0, 2.0], leak_units="g/s", **kw)
    assert a[6] > 0
    assert b[6] == pytest.approx(a[6] * 3.6)
    _reset()

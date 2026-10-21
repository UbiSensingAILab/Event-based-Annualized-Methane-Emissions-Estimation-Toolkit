"""Figure S10 (SI) redrawn: inputs of the Type 1 (below-MDL) simulation of Case Study 2 as the toolkit uses them.
(a) component-scale emission rates of the bundled Rutherford et al. (2021) sample, converted from the g/s stored in
    sample_leak_rate.csv to the kg/h the simulation integrates (factor 3.6; the earlier figure plotted the g/s values
    on a kg/h axis);
(b) the generic component-count prior of v1.0 (normal, mean 2,720, SD 800, truncated to 1-5,440; 10,000 draws);
(c) the empirical durations of the 86 observed events (REs and PREs) that the simulation samples from.
The wind-speed panel of the earlier figure is dropped: the wind-independent POD of the Qube CMS was used, so no wind
record enters the Case Study 2 simulation.
Output: cs2_outputs/cs2_figure_s10_type1_inputs.png"""
import os, sys, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "cs2_outputs")
sys.path.insert(0, os.path.join(HERE, "..", "EAMEET_v1"))
import simulations
from simulations import _load_leak_data
np.random.seed(0); simulations._leaks_dist = None; simulations._num_comps = None
_load_leak_data()                                # bundled sample -> kg/h, generic component prior
rates = simulations._leaks_dist; comps = simulations._num_comps
ev = pd.read_csv(os.path.join(HERE, "emission_events_case_study_2.csv")); dur = ev["duration"].to_numpy(float)
print(f"rates n={rates.size} median={np.median(rates):.4f} kg/h mean={rates.mean():.3f} kg/h | comps n={comps.size} "
      f"mean={comps.mean():.0f} | durations n={dur.size} median={np.median(dur):.2f} h")
fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
ax = axes[0]; v = rates[rates > 0]
ax.hist(v, bins=np.logspace(np.log10(v.min()), np.log10(v.max()), 40), color="orange", edgecolor="black")
ax.set_xscale("log"); ax.set_xlabel("Component-scale emission rate (kg/hr)"); ax.set_ylabel("Count"); ax.set_title("(a)", loc="left")
ax = axes[1]; ax.hist(comps, bins=12, color="red", edgecolor="black"); ax.set_xlabel("Component count"); ax.set_ylabel("Count"); ax.set_title("(b)", loc="left")
ax = axes[2]; ax.hist(dur, bins=np.logspace(np.log10(dur.min()), np.log10(dur.max()), 20), color="green", edgecolor="black")
ax.set_xscale("log"); ax.set_xlabel("Event duration (hr)"); ax.set_ylabel("Count"); ax.set_title("(c)", loc="left")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "cs2_figure_s10_type1_inputs.png"), dpi=150); print("written")

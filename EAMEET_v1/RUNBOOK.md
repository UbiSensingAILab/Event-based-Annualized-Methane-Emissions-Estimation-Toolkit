# EAMEET v1.0.2 — reproduction runbook

Release: `EAMEET_v1/version.py` (`__version__ = "1.0.2"`, 2026-10-11). The bundled component-scale leak-rate sample
(`sample_leak_rate.csv`, column `gpersec`) is in g/s and is converted to kg/h on loading (`simulations.G_PER_S_TO_KG_PER_H`);
results produced before this conversion (CHANGELOG.md, v1.0.2 unit fix) have a Type 1 term 3.6x too small. Pinned dependencies:
`requirements-lock.txt`. Random seeds are fixed in every script (listed below); Monte Carlo
simulations that use `multiprocessing.Pool` draw per-worker seeds from the global NumPy RNG, which is
seeded immediately before each call, so repeated runs reproduce the reported medians and intervals to
Monte Carlo precision (see the convergence tables).

## 0. Environment

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r EAMEET_v1/requirements-lock.txt
cd EAMEET_v1 && python -m pytest -q          # 115 tests (unit, invariance, worked examples, leak-rate units)
```

## 1. Toolkit worked examples (SI Section S2.1)

```bash
cd EAMEET_v1 && python worked_examples_merging.py      # -> validation_outputs/worked_examples_merging.md
```

## 2. Case Study 1 (Carbon Mapper, Permian Basin, 2024)

Inputs (in `case study/`): `CM_sources.json`, `CM_plumes.csv` (Carbon Mapper portal download, Permian
Basin study polygon, 1 Jan–31 Dec 2024), `shapefiles/`, GFEI v3.0 NetCDF files.

```bash
cd "case study"
python cs1_build_events.py                 # sector filter, all platforms -> CM_emissions_observation.csv, CM_emission_events.csv
jupyter nbconvert --to notebook --execute --inplace Case_study_No1.ipynb
#   seeds: ensemble 2024 (N_OUTER = 10,000), sensitivities 7 (2,000), convergence 11; POD_CM = 0.9
#   -> total_emissions.csv, cs1_basin_total_ensemble.npy, cs1_outputs/*.csv|png
python cs1_gfei_domain.py                  # needs geopandas/netCDF4 -> cs1_outputs/cs1_gfei_domain_alignment.md
```

## 3. Case Study 2 (synthetic Site A)

Input: `case study/Data_from_case_study_2.xlsx` (Tables S3–S6).

```bash
cd "case study"
jupyter nbconvert --to notebook --execute --inplace Case_study_No2_redone.ipynb   # SEED_UE = 99, N = 10^5 duration draws, 10,000 MC
python cs2_sensitivity.py                  # Table S10 / Figure S14
python cs2_joint_sampling.py               # Tables S11-S12 / Figure S15
python cs2_figure_s7.py                    # Figure S7 (Weibull fit of Eq. S2 on the revised CMS PREs; lognormal dashed)
python cs2_figure_s10.py                   # Figure S10 (Type 1 inputs: bundled component rates converted g/s -> kg/h, component prior, event durations)
# in the geopandas environment:
python cs1_figure4.py <original Figure 4 png>  # Figure 4a plume-count map (+ composite with the unchanged panel b)
python cs1_figure5_composite.py            # Figure 5 (a)/(b)/(c) composite from the three cs1_figures.py panels (any environment with Pillow)
python cs2_coverage_sweep.py               # coverage sweep + MC convergence and cost
```

## 4. Synthetic-truth validation (SI Section S12)

```bash
cd EAMEET_v1 && python validate_annual_truth.py --reps 20     # seeds: 1000*scenario_index + rep; 5000 + rep; 9000 + rep
#   -> validation_outputs/annual_truth_*.csv, coverage_sweep*.csv, detection_model_sweep*.csv, *.png, run_metadata.json
python validate_occupancy_recovery.py                          # SI Section S8, Table S7 / Figure S12
```

## Computational cost (Apple M-series, 12 cores)

See `case study/cs1_outputs/cs1_mc_convergence.csv`, `case study/cs2_outputs/cs2_mc_convergence.csv` and
`EAMEET_v1/validation_outputs/run_metadata.json`.

# Changelog

## v1.0.2 (2026-10-11) — second-round revision (reviewer comments 5–7)

- `simulations.py` (unit fix, 2026-10-11, before release): the bundled component-scale leak-rate
  sample `sample_leak_rate.csv` (Rutherford et al., 2021; column `gpersec`) is stored in g/s, but the
  Type 1 simulation integrates rate x duration with durations in hours and reports kg, i.e. it needs
  kg/h. The values were sampled unconverted, so the Type 1 (below-MDL) term was 3.6 times too small in
  every earlier result. `_load_leak_data()` now converts the bundled file (`G_PER_S_TO_KG_PER_H = 3.6`),
  user-supplied `leak_data` is kg/h by default and `simulate_below_mdl(..., leak_units="g/s")` converts
  other inputs; the dashboard no longer converts uploaded kg/h rates to g/s. New tests:
  `test_leak_rate_units.py`. Case Study 2 (Type 1 term 19.9 -> 71.7 t), its sensitivity, joint-sampling
  and coverage sweeps, and the synthetic-truth validation were re-run.
- `emission_event_converter.py`: the observations merged into an event are now combined by a
  time-weighted, scale-aware integration (`integrate_event`, `resolve_rate_at`): the event bound is
  split at the start/end of every measured-interval observation; within each sub-interval replicates
  of the same feature are combined by the chosen operation, distinct features at the same scale are
  summed, and a coarser-scale measurement is combined with (never added to) the finer-scale aggregate.
  Event quantity = sum(rate_i x dt_i); resolved rate = quantity / duration. Exact duplicate records are
  collapsed; consecutive pieces of one measured record (same feature and technology, end == start) are
  merged. The result no longer depends on the merge order. New optional column mappings
  `observation_scale` (component / equipment / site) and `feature`. New tests:
  `test_event_integration.py` (worked examples, duplicate/splitting/order invariance).
- `annualize.py` (new): the Case Study 2 (CMS) and Case Study 1 (snapshot) site pipelines as functions.
- `validate_annual_truth.py` (new): synthetic-truth validation harness (full-year hidden histories,
  simulated observations, blind EAMEET estimation, bias / error / 95 %-interval coverage against a
  persistence-weighted mean-rate baseline; coverage-length and detection-model sweeps).
- `worked_examples_merging.py` (new): SI Section S2.1 worked examples.
- Case Study 1 GFEI comparison (2026-10-20): `case study/cs1_gfei.py` loads the GFEI v3.0 oil and gas sector files
  (Oil_All + Gas_All) and the GFEI v1.0 per-sector relative standard deviations (v3.0 ships no uncertainty layer);
  `cs1_gfei_domain.py`, `cs1_figures.py` and `Results_compare_for_case_study_No1.ipynb` use them. Totals are unchanged
  inside the study polygon (no coal); the relative uncertainty of the polygon total is 0.46 (was 0.40).
- Case Study 1 (`case study/cs1_joint_ensemble.py`, new, 2026-10-19; reviewer comment 1): the cohort total is
  computed by one joint Monte Carlo ensemble in which plume quantification errors (mean-preserving lognormal from
  the reported uncertainty, optionally shared within (platform, day) and/or by a platform-wide bias), event rates,
  optionally detection-conditioned event durations, the bootstrap-refit Weibull UE distributions (refit to the
  iteration's SAMPLED rates), occupancy posteriors and renewal UE draws are all sampled before PRE + UE are summed
  over sources; central estimate and 95 % interval = percentiles of the ensemble of totals. Dependence tests
  (variants A-J) in `cs1_outputs/cs1_dependence_tests.{csv,md}`; the ensemble runs in parallel (16 seeded chunks,
  ~40 s for 10,000 iterations). `Results_compare_for_case_study_No1.ipynb`: the root-mean-square combination of the
  PRE bound and the UE uncertainty and the sum-of-bounds cells were removed; GFEI uncertainty is aggregated as the
  emission-weighted mean of the per-cell relative standard deviations (fully correlated cells) instead of their RMS.
- Case Study 1 (`case study/cs1_build_events.py`, `Case_study_No1.ipynb`): oil-and-gas (IPCC 1B2)
  sector filter; all three Carbon Mapper platforms (the earlier plume-identifier parsing dropped every
  Tanager-1 plume); unquantified plumes counted and dropped; events rebuilt with the toolkit;
  preferential-sampling bound (source-specific UE rates, no extrapolation); Monte Carlo convergence
  and cost. `cs1_gfei_domain.py`: GFEI totals over aligned domains.
- Case Study 2: `cs2_coverage_sweep.py` (monitored-period length 1–7 months; MC convergence and cost);
  notebook, `cs2_sensitivity.py` and `cs2_joint_sampling.py` re-run with the v1.0.2 merge.

## v1.0.1 (2026-10-10) — first-round revision

- Detection-conditioned PRE duration model (`sample_conditional_duration`), per-visit null-repair
  rate, soft null-detection bounds; alternating-renewal Type 2 simulation calibrated to occupancy;
  coverage-schedule time budget and symmetric clock of the Type 1 simulation; MDL/POD separation and
  opt-in MDL-gated POD; paired / class-stratified sampling; occupancy from detection records
  (`occupancy.py`).

## v1.0.0 — original submission

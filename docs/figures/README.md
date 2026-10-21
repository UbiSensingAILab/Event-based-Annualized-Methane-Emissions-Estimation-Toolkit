# Figures of the revised manuscript and SI (state of 2026-10-20)

Generated figures of the second-round revision, named by their number in `Gao_et_al_EAMEET_MS_revised_2026_10_20.docx`
(MS) and `Gao_et_al_EAMEET_SI_revised_2026_10_20.docx` (SI). Figures S1–S4, S8, S9 and S11 of the SI are drawn
diagrams / portal screenshots and are not reproduced here.

| File | Document | Source script |
|---|---|---|
| Figure_4_revised_plume_counts.png (panel a alone: Figure_4a_plume_counts_panel.png) | MS Fig. 4 | `case study/cs1_figure4.py` |
| Figure_5_revised_cs1_emissions.png | MS Fig. 5 (joint-ensemble total 2.08 Tg; GFEI v3.0 oil and gas sector totals with GFEI v1.0 emission-weighted relative uncertainty) | `case study/cs1_figures.py` + `cs1_figure5_composite.py` |
| Figure_6_cs2_distributions.png | MS Fig. 6 | `case study/Case_study_No2_redone.ipynb` |
| Figure_7_cs2_breakdown.png | MS Fig. 7 (annual total 804.61 t) | `case study/Case_study_No2_redone.ipynb` |
| Figure_S5_conditional_duration.png / .svg (variant: Figure_S5a_conditional_duration.svg) | SI Fig. S5 | hand-drawn SVG |
| Figure_S6_type1_workflow.png / .svg | SI Fig. S6 | `make_figure_s6.py` |
| Figure_S7_weibull_fit.png | SI Fig. S7 | `case study/cs2_figure_s7.py` |
| Figure_S10_type1_inputs.png | SI Fig. S10 | `case study/cs2_figure_s10.py` |
| Figure_S12_cs1_occupancy_posterior.png | SI Fig. S12 (posterior occupancy vs. persistence) | `case study/Case_study_No1.ipynb` |
| Figure_S13_rate_duration_pairs.png | SI Fig. S13 | `case study/cs2_joint_sampling.py` |
| Figure_S14_cs2_coverage_sweep.png | SI Fig. S14 | `case study/cs2_coverage_sweep.py` |

Generated but not embedded in the current SI (kept for reference; the corresponding results are reported in tables or
in the response to reviewers):

| File | Content | Source script |
|---|---|---|
| Figure_occupancy_recovery_notEmbedded.png | recovery of prescribed occupancy and event frequency (SI Table S7) | `EAMEET_v1/validate_occupancy_recovery.py` |
| Figure_cs2_sensitivity_notEmbedded.png | Case Study 2 duration-assumption sensitivity (SI Table S11) | `case study/cs2_sensitivity.py` |
| Figure_annual_truth_validation_notEmbedded.png | synthetic-truth validation (bias, coverage per scenario and design) | `EAMEET_v1/validate_annual_truth.py` |
| Figure_synthetic_coverage_sweep_notEmbedded.png | synthetic coverage sweep (interval width vs. months monitored) | `EAMEET_v1/validate_annual_truth.py --only coverage` |

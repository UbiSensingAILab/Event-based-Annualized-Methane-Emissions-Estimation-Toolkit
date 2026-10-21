# Case Study No. 2 — Results Summary (EAMEET v1.0, redone)

*Site A, calendar year 2024. Hybrid estimation: below-MDL over the measured window (2024-01-01 – 2024-07-31) + bootstrap over the unmeasured window (2024-08-01 – 2024-12-31).*

## 1. Configuration

| Parameter | Value |
|---|---|
| Measured window | 2024-01-01 – 2024-07-31 |
| Unmeasured (bootstrap) window | 2024-08-01 – 2024-12-31 |
| Quantification uncertainty | CMS 40%, Flyover 25%, Operational 30% |
| CMS PRE duration uncertainty | M~log-uniform, symmetric about 1, 95% CI (0.5, 2.0) (illustrative, Daniels et al. 2024) |
| Flyover PRE duration workflow | LPR 0.006/day; NRR = Fox et al. (2021) Eq. S1 per visit (p_max 0.25, V 7 d, 10 leaks/site); t_SND = end of monitored window; N=100,000, adopted **median**; null-detection POD {'ogi': 0.9, 'flyover': 0.9} (soft bounds) |
| Below-MDL technology / iters | Qube / 10000 |
| Below-MDL time budget | 2,231 gap h of 5,112 h (CMS coverage: whole window; superseded sum-of-durations budget 2,981 h) |
| Bootstrap fit / iters | weibull / 10000 |

## 2. Observations and event creation

| Observation type | Count | Role |
|---|---|---|
| CMS | 89 | quantified detections -> PRE (per equipment) |
| Flyover | 4 (3 detections, 1 non-detection) | facility PRE + null-detect |
| OGI | 4 (2 detections, 2 non-detection) | non-detections = null markers; detections excluded (no rate) |
| Operational | 10 | Resolved Events (quantity from record) |

**Emission events created: 86** — **10 Resolved (RE)**, **76 Partially Resolved (PRE)**.
- PRE composition: **75 CMS-derived**, **1 flyover-only** (flagged `start_end_simulated`).
- OGI true-detections excluded (no quantification): ['OGI-2', 'OGI-3']

## 3. Event statistics (median rate & duration)

| Event type | n | Median rate (kg/hr) | Median duration (h) |
|---|---|---|---|
| RE (operational) | 10 | 2262.88 | 0.10 |
| PRE — all | 76 | 16.50 | 10.15 |
| PRE — CMS | 75 | 16.23 | 10.15 |
| PRE — flyover | 1 | 152.25 | 1710.82 |

## 4. Emissions by event type (measured window)

*Per event, the technology-specific quantification uncertainty (CMS 40%, flyover 25%, operational 30%) and the duration uncertainty are combined in quadrature per event (Eq. 6); events are then aggregated in **quadrature (root-sum-square)** (Eqs. 10-11). CMS PRE: point = measured emission, relative duration uncertainty +1.0/−0.5 from the log-uniform multiplier M (95% CI 0.5×–2×). Flyover PRE: point = adopted median, asymmetric relative duration uncertainty from the LPR/NRR duration CI. RE: quantification only (Eq. 3).*

| Component | Emissions (t) | 95% CI (t) |
|---|---|---|
| Measured RE (operational, 30% Q) | 2.45 | [2.18, 2.73] |
| Measured PRE — CMS (measured, M~logU 0.5-2x, RSS) | 25.33 | [22.05, 30.85] |
| Measured PRE — Flyover (duration-simulated) | 260.47 | [169.61, 407.13] |
| **Measured RE+PRE total** | **288.25** | [197.33, 435.02] |

- CMS PRE: point = measured emission **25.33 t** (= sum of rate×measured-duration over 75 PREs); per-event uncertainty combines 40% quantification with the two-sided duration uncertainty from a log-uniform multiplier M (95% CI 0.5×–2.0×, centred on 1), aggregated in quadrature -> **[22.05, 30.85] t**. RSS of 75 independent per-event errors narrows the band (~1/√N); a correlated/systematic error shared by all CMS events would instead give [9.18, 52.57] t (linear sum).
- **Flyover PRE**: point 260.5 t; its 25% quantification uncertainty and 95% duration CI map to a **169.6–407.1 t** emissions range, which dominates the measured PRE band — hence the separate line and the wide whisker in the figure.

## 5. Flyover-only PRE — simulated start/end (LPR/NRR workflow)

Merged observations **FLY-2, FLY-3, FLY-4**, rate 152.2 kg/hr.

| Quantity | Start | End | Duration (h) | Emission (t) |
|---|---|---|---|---|
| Estimated (null-detect bracket) | 2024-04-01 | 2024-07-05 | 2284 | 347.7 |
| Simulated — median | 2024-05-07 | 2024-07-15 | 1711 | 260.5 |
| Simulated — mean | — | — | 1772 | 269.8 |
| Simulated 95% CI | start [2024-04-03, 2024-05-22] | end [2024-07-06, 2024-07-30] | [1168, 2642] | — |

**Adopted into the total: `median` -> 1711 h, 260.5 t.**

## 6. Unresolved emissions (UE)

| UE component | Window | Emissions (t) | 95% CI (t) |
|---|---|---|---|
| Below-MDL (Qube) | 2024-01-01–2024-07-31 | 71.71 | [11.53, 445.60] |
| Bootstrap (weibull, poe=0.583) | 2024-08-01–2024-12-31 | 444.65 | [175.58, 1425.86] |
| **Total UE** | 2024 | **516.35** | [240.64, 1566.39] |

## 7. Full-year 2024 annualized total

| Component | Emissions (t) | 95% CI (t) |
|---|---|---|
| Measured RE (operational) | 2.45 | [2.18, 2.73] |
| Measured PRE - CMS (measured, M~logU 0.5-2x, RSS) | 25.33 | [22.05, 30.85] |
| Measured PRE - Flyover (duration-simulated) | 260.47 | [169.61, 407.13] |
| Measured RE+PRE (all PREs via quadrature) | 288.25 | [197.33, 435.02] |
| UE below-MDL (measured window) | 71.71 | [11.53, 445.60] |
| UE bootstrap (unmeasured window) | 444.65 | [175.58, 1425.86] |
| UE total (below-MDL + bootstrap, RSS) | 516.35 | [240.64, 1566.39] |
| TOTAL annualized 2024 | 804.61 | [514.29, 1864.85] |

**TOTAL annualized 2024 = 804.6 t (95% CI 514–1865 t).**
Measured share 36%; UE share 64%.

## 8. Notes & sensitivities

- Flyover-only PRE(s) dominate measured PRE. Point estimate = `median` of the LPR/NRR duration workflow; its 95% duration CI is converted to asymmetric emission bounds and **combined with the CMS PRE bounds in quadrature (RSS)**, then reported separately. Every draw contains the detection span; the onset extension uses the repair-minus-onset hazard and the preceding null detection is a valid bound only with probability {'ogi': 0.9, 'flyover': 0.9} (else the chain of earlier nulls / window start), so the band reflects both the survival constraint and the reliability of the null detections.
- Below-MDL samples empirical component leaks (Rutherford et al.) + empirical event durations (no lognormal-fit hook). Bootstrap uses the Weibull fit.
- CMS PRE duration uncertainty is a DEFAULT ILLUSTRATIVE assumption (Daniels et al. 2024, not universal): a log-uniform multiplier M symmetric about 1 (95% CI 0.5×–2×), so the band is two-sided with the point estimate = measured emission. Per-event bounds are aggregated in quadrature (RSS), so the independent aggregate band is narrow (~1/√N); a systematic CMS bias would sum linearly instead.

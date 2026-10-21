Joint-ensemble dependence tests, Case Study 1 (2000 outer iterations per variant, POD = 0.9, seed 7). Rel. width = (97.5th - 2.5th percentile) / median.

| Variant | Description | PRE (Tg) | UE (Tg) | Total (Tg) [95 % interval] | Rel. width | Change in median | Width ratio |
|---|---|---|---|---|---|---|---|
| A | Baseline: independent plume errors, bracket durations, bootstrap refit on the sampled rates | 1.263 | 0.816 | 2.079 [1.924, 2.288] | 0.18 | +0.0 % | 1.00 |
| B | No parameter uncertainty: Weibull fitted once to the observed sample (no bootstrap refit) | 1.264 | 0.827 | 2.090 [1.967, 2.233] | 0.13 | +0.5 % | 0.73 |
| C | UE distributions refit to the reported (unperturbed) rates, i.e. PRE rate errors not passed to the UEs | 1.263 | 0.822 | 2.086 [1.935, 2.288] | 0.17 | +0.3 % | 0.97 |
| D | Half of each plume's error variance shared within (platform, day): rho = 0.5 | 1.262 | 0.819 | 2.079 [1.880, 2.309] | 0.21 | +0.0 % | 1.18 |
| E | All of each plume's error shared within (platform, day): rho = 1 | 1.260 | 0.817 | 2.078 [1.856, 2.349] | 0.24 | -0.1 % | 1.36 |
| F | Platform-wide calibration bias, log-SD 0.2 per platform, plus independent plume errors | 1.252 | 0.810 | 2.074 [1.622, 2.654] | 0.50 | -0.3 % | 2.84 |
| G | Platform-wide bias (0.2) with the UE distributions refit to the reported rates (link PRE -> UE cut) | 1.252 | 0.822 | 2.085 [1.761, 2.504] | 0.36 | +0.3 % | 2.03 |
| H | Fully shared errors: platform-wide bias (0.2) and rho = 1 | 1.248 | 0.803 | 2.057 [1.587, 2.652] | 0.52 | -1.1 % | 2.96 |
| I | Detection-conditioned PRE durations sampled per event (Section S3), independent plume errors | 0.606 | 0.919 | 1.523 [1.342, 1.747] | 0.27 | -26.7 % | 1.52 |
| J | Detection-conditioned durations with fully shared errors (platform bias 0.2, rho = 1) | 0.596 | 0.909 | 1.505 [1.158, 1.984] | 0.55 | -27.6 % | 3.13 |

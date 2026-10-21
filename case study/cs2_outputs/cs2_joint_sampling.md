## Paired rate-duration statistics

| sample                      |   n |   spearman_rho |   p_value |   rate_median |   duration_median_h |
|:----------------------------|----:|---------------:|----------:|--------------:|--------------------:|
| CS2: all events (RE + PRE)  |  86 |         -0.274 |     0.011 |        17.214 |               9.425 |
| CS2: CMS-derived PREs       |  75 |          0.011 |     0.924 |        16.235 |              10.15  |
| CS2: CMS PREs, Compressor-2 |  12 |          0.021 |     0.948 |        14.581 |              11.658 |
| CS2: CMS PREs, Compressor-3 |   5 |         -0.3   |     0.624 |        13.437 |              15.367 |
| CS2: CMS PREs, Dehydrator-1 |  30 |          0.13  |     0.492 |        17.214 |              10.667 |
| CS2: CMS PREs, Separator-1  |  12 |          0.21  |     0.513 |        16.025 |               7.642 |
| CS2: CMS PREs, Separator-2  |  11 |         -0.455 |     0.16  |        29.79  |               8.1   |
| CS1: Carbon Mapper events   | 806 |          0.327 |     0     |       242.656 |             333.668 |

## CS2 unmonitored-period (Aug-Dec) extrapolation by sampling scheme (occupancy 0.583; classes: CMS phi=0.197 n=75, Flyover phi=0.335 n=1, Operational phi=0.051 n=10)

| sampling                                                           |   UE_boot_t |   UE_boot_lo_t |   UE_boot_hi_t |   TOTAL_t |   TOTAL_lo_t |   TOTAL_hi_t |   change_pct |
|:-------------------------------------------------------------------|------------:|---------------:|---------------:|----------:|-------------:|-------------:|-------------:|
| Independent Weibull marginals (baseline, Section 3.2)              |       444.6 |          175.6 |         1425.9 |     804.6 |        514.3 |       1864.8 |          0   |
| Weibull marginals + empirical copula of observed pairs             |       283.3 |           97.6 |          629.4 |     643.2 |        427.9 |       1173.5 |        -20.1 |
| Observed (rate, duration) pairs, no fit                            |       242.3 |           23.8 |          468.6 |     602.3 |        358.1 |       1063.3 |        -25.1 |
| Class-stratified (CMS / flyover / operational), pairs within class |       239.8 |           15.1 |          480.7 |     599.8 |        350   |       1068.2 |        -25.5 |
| Class-stratified, flyover class excluded                           |        19.7 |           13   |           28.3 |     379.7 |        270.5 |        781.5 |        -52.8 |

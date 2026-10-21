**Example 1 - repeatedly observed persistent leak (two overlapping CMS alarms on one compressor)**

| Observation | Scale / feature | Interval | Rate (kg/h) |
|---|---|---|---|
| CMS-a (cms) | equipment / Compressor-1 | 00:00-10:00 | 10 +/- 2 |
| CMS-b (cms) | equipment / Compressor-1 | 08:00-20:00 | 20 +/- 4 |

| Sub-interval | Active observations | Rule | Rate (kg/h) | Mass (kg) |
|---|---|---|---|---|
| 00:00-08:00 | CMS-a | single observation | 10.00 | 80.0 |
| 08:00-10:00 | CMS-a, CMS-b | replicates averaged | 15.00 | 30.0 |
| 10:00-20:00 | CMS-b | single observation | 20.00 | 200.0 |

Event: duration 20 h, quantity 310.0 kg, resolved rate 15.50 kg/h (uncertainty 3.02 kg/h). Former rule (mean of the observed rates x union): 15.00 kg/h x 20 h = 300.0 kg.

**Example 2 - concurrent emissions from two components (OGI-quantified, overlapping intervals)**

| Observation | Scale / feature | Interval | Rate (kg/h) |
|---|---|---|---|
| OGI-1 (ogi) | component / Valve-1 | 00:00-10:00 | 2 +/- 0.5 |
| OGI-2 (ogi) | component / Flange-7 | 04:00-10:00 | 3 +/- 0.6 |

| Sub-interval | Active observations | Rule | Rate (kg/h) | Mass (kg) |
|---|---|---|---|---|
| 00:00-04:00 | OGI-1 | single observation | 2.00 | 8.0 |
| 04:00-10:00 | OGI-1, OGI-2 | distinct features summed | 5.00 | 30.0 |

Event: duration 10 h, quantity 38.0 kg, resolved rate 3.80 kg/h (uncertainty 0.67 kg/h). Former rule (mean of the observed rates x union): 2.50 kg/h x 10 h = 25.0 kg.

**Example 3 - facility measurement overlapping component measurements**

| Observation | Scale / feature | Interval | Rate (kg/h) |
|---|---|---|---|
| FLY-1 (flyover) | site / Site | 02:00-08:00 | 12 +/- 3 |
| OGI-1 (ogi) | component / Valve-1 | 00:00-10:00 | 2 +/- 0.5 |
| OGI-2 (ogi) | component / Flange-7 | 04:00-10:00 | 3 +/- 0.6 |

| Sub-interval | Active observations | Rule | Rate (kg/h) | Mass (kg) |
|---|---|---|---|---|
| 00:00-02:00 | OGI-1 | single observation | 2.00 | 4.0 |
| 02:00-04:00 | FLY-1, OGI-1 | components summed, then averaged with the site measurement | 7.00 | 14.0 |
| 04:00-08:00 | FLY-1, OGI-1, OGI-2 | components summed, then averaged with the site measurement | 8.50 | 34.0 |
| 08:00-10:00 | OGI-1, OGI-2 | distinct features summed | 5.00 | 10.0 |

Event: duration 10 h, quantity 62.0 kg, resolved rate 6.20 kg/h (uncertainty 1.18 kg/h). Former rule (mean of the observed rates x union): 5.67 kg/h x 10 h = 56.7 kg.

**Example 4 - duplicate record and split record (Example 1 with CMS-b duplicated and CMS-a split at 06:00)**

| Observation | Scale / feature | Interval | Rate (kg/h) |
|---|---|---|---|
| CMS-a1 (cms) | equipment / Compressor-1 | 00:00-06:00 | 10 +/- 2 |
| CMS-a2 (cms) | equipment / Compressor-1 | 06:00-10:00 | 10 +/- 2 |
| CMS-b (cms) | equipment / Compressor-1 | 08:00-20:00 | 20 +/- 4 |
| CMS-b-dup (cms) | equipment / Compressor-1 | 08:00-20:00 | 20 +/- 4 |

| Sub-interval | Active observations | Rule | Rate (kg/h) | Mass (kg) |
|---|---|---|---|---|
| 00:00-06:00 | CMS-a1 | single observation | 10.00 | 60.0 |
| 06:00-08:00 | CMS-a2 | single observation | 10.00 | 20.0 |
| 08:00-10:00 | CMS-a2, CMS-b, CMS-b-dup | replicates averaged | 15.00 | 30.0 |
| 10:00-20:00 | CMS-b, CMS-b-dup | replicates averaged | 20.00 | 200.0 |

Event: duration 20 h, quantity 310.0 kg, resolved rate 15.50 kg/h (uncertainty 3.02 kg/h). Former rule (mean of the observed rates x union): 15.00 kg/h x 20 h = 300.0 kg.

# Preregistration

A preregistration is the analysis plan, written and **committed to git before
the analysis is run**. The commit date proves which choices were made before
seeing the results. Any deviation from it is reported as a deviation.

---

## Part A: pilot hypothesis tests (H1, H2), 2024 Abu Dhabi

**Written:** 2026-10-16, before any hypothesis test was run on real data.
**Disclosure:** the descriptive feature values (means, standard errors) of
the pilot were computed and seen before this was written
(`results/05_pilot_features/`, Phase 4), as planned in the project roadmap.
The features, thresholds and estimators were fixed earlier: features and
thresholds in the original plan (committed 2026-10-14), estimators by the
Phase 2 Monte Carlo (`docs/decisions.md`, 2026-10-16), all before any
real-data feature was computed.

### Data
- 2024 Abu Dhabi GP. Lando Norris (NOR) vs Oscar Piastri (PIA).
- **H2:** qualifying laps kept by `select_laps()`, at corners T5, T6, T9,
  excluding (lap, corner) pairs with a feed gap in the window (decisions.md).
  Usable laps: T5 NOR 4 / PIA 4, T6 4 / 2, T9 3 / 4.
- **H1:** the same qualifying laps, plus the matched FP2 medium long runs
  (NOR stint 4, PIA stint 4), usable pairs only.
- Features as computed by `features.corner_features()` (no change after
  this commit).

### Features and corners (27 comparisons)
`brake_onset_m`, `apex_m`, `min_speed_kmh`, `throttle_pickup_m`,
`full_throttle_m`, `entry_speed_kmh`, `exit_speed_kmh`, `mean_decel_ms2`,
`corner_time_s` × T5, T6, T9. (`min_gear` is excluded as discrete;
`braking_distance_m` is excluded because it is apex − onset, two features
already included.)

### H2: do the teammates differ (qualifying)?
For each of the 27 (feature, corner) pairs:
1. Difference of means NOR − PIA.
2. **Exact two-sided permutation test** of the difference of means (all
   splits of the pooled laps).
3. **95 % percentile bootstrap interval** of the difference: 10,000
   resamples within each driver, seed 2026.
4. **Hedges' g** (effect size, small-sample corrected).
5. **Benjamini–Hochberg** adjustment of the 27 p-values; discovery =
   adjusted p ≤ 0.05.
6. Each difference is shown next to the per-lap measurement error
   (Monte Carlo + alignment).

**Stated in advance (power):** with exact permutation tests, the smallest
possible p-value is 2/70 = 0.029 for 4 vs 4 laps, 2/35 = 0.057 for 3 vs 4,
and 2/15 = 0.13 for 2 vs 4. With Benjamini–Hochberg over 27 tests, a
discovery would need at least 16 of the 27 tests at that minimum
(0.029 × 27/16 = 0.049). **The pilot is therefore not expected to produce any
discovery, whatever the true differences are.** The pilot's results are the
effect sizes and intervals. A two-sample t-test has 80 % power only for
effects of at least d = 2.38 (4 vs 4 laps), 2.68 (3 vs 4) or 3.26 (2 vs 4)
(`stats.min_detectable_effect`). Confirmatory tests need more sessions
(Part B, written before it is run).

### H1: is each feature repeatable? (exploratory)
For each (feature, corner):
1. Within-driver lap-to-lap standard deviation, separately for Q and for the
   FP2 long runs, compared with the per-lap measurement error. Ratio > 1 means
   the driver varies more than the measurement error.
2. ICC(1) on the qualifying laps (2 drivers), with a 95 % bootstrap interval
   (resampling laps within each driver, 2,000 resamples, seed 2026). With
   only two drivers this is a rough estimate; the real H1 test comes with
   all drivers (Phase 6).

### Analysis code
`experiments/06_pilot_stats.py` and `src/apextrace/stats.py`, committed
together with this file and not run on real data before this commit.
Results go to `results/06_pilot_stats/`.

### What would change the conclusions
Nothing in the pilot is used to choose features, thresholds or corners for
later phases. If a bug is found after the run, it is fixed, re-run, and both
results are reported.

---

## Part B: final evaluation on the frozen 2025 season (H3, H4)

*To be written and committed before any 2025 session is loaded (Phase 7).*

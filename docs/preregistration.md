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

**Written:** 2026-10-18, before any 2025 data was loaded. Since the start of
the project the code has refused to load 2025 (`data_loading.check_not_frozen`,
used by both the FastF1 and the OpenF1 paths), and no 2025 session is in the
cache. The development results that motivate these tests are on 2023–2024
(`results/12_identification/`, `results/13_signature_stability/`).

**Code:** the version committed together with this text. The final run is
`experiments/14_final_2025.py`, which uses the same modules as the
development runs (`session_build`, `dataset`, `identification`, `protocol`,
`signatures`). It refuses to run unless `FINAL_TEST=1` is set, this file is
committed and unchanged, and `results/final/` doesn't exist yet. **It is run
once.** If a bug is found afterwards, it is fixed, the evaluation is re-run
into a new folder, and both results are reported in
`docs/preregistration_deviations.md`.

### Data
- Every 2025 main qualifying session on OpenF1 (no sprint qualifying),
  downloaded and built exactly as 2023–2024 (`08`/`09` logic): lap selection,
  automatic corner detection on each session's fastest kept lap, features per
  corner window, cleaning rules (`dataset.clean`: dry only, min speed < 40 km/h
  dropped, impossible values → missing), field-relative values, lap vectors
  (30 columns) and raw lap statistics (`identification.build_lap_table`).
- Reference season for H4: the 2024 development data, unchanged.

### H3: replication of teammate identification on 2025
- Teams: each 2025 team's two drivers with the most laps, sessions where both
  have laps, at least 5 such sessions (the development rule, `protocol.teammate_task`).
- Leave-one-session-out within 2025; logistic regression; feature sets as in
  development: majority, lap time only, raw lap statistics, our corner
  features; shuffled labels (5×, seed 2026).
- **Primary test:** Wilcoxon signed-rank test (two-sided) of the per-team
  balanced accuracy, our corner features vs lap time only. **H3 is replicated
  if p < 0.05 and our features score higher** (development: 0.685 vs 0.565).
- Secondary (reported, not a decision): ours vs raw lap statistics (Wilcoxon);
  weekend vote; ablation by feature group; shuffled labels (expected ≈ 0.5;
  a mean outside 0.45–0.55 flags a pipeline problem).

### H4: does the signature follow drivers who changed teams?
- **Team changers (fixed now):** Hamilton (Mercedes → Ferrari), Sainz
  (Ferrari → Williams), Ocon (Alpine → Haas), Hülkenberg (Haas → Kick Sauber),
  Tsunoda (RB → Red Bull Racing, from round 3). Lawson (two teams in 2025, few
  2024 weekends) and Bearman (too few 2024 weekends) are not included.
- **Signatures** (`signatures.season_signatures`): the season mean of the 30
  lap-vector features, every weekend counted once, at least 5 weekends.
  2024: all drivers with ≥ 5 weekends. 2025: each changer only on weekends with
  their 2025 team (the team they drove for on most weekends), and their new
  teammate (the other driver of that team with the most shared weekends) on
  the same weekends. Everything is z-scored with the 2024 spread; distance =
  root-mean-square difference over shared features.
- **Primary test:** for each changer, is their 2025 signature closer to their
  own 2024 signature (a different car) than to their new teammate's 2025
  signature (the same car, the same season)? Count the changers for whom it
  is; **one-sided sign test; H4 is supported if p < 0.05.** If the signature
  belonged to the car, the new teammate would be closer.
  **Power, stated in advance:** with 5 changers the smallest possible p is
  1/32 = 0.031, so H4 can be supported only if all 5 go the driver's way;
  with 4 included changers (if one has fewer than 5 weekends) H4 cannot reach
  p < 0.05 (minimum 1/16 = 0.0625), and the result is then reported as
  descriptive only.
- Secondary (reported, not a decision): the same comparison for the brake-flag
  share (field-relative season mean; the strongest raw statistic in H3); each
  changer's rank of their own 2024 signature among all 2024 signatures; and the
  development check (own 2024 vs old teammate 2024) for 2025 drivers who did
  NOT change teams, as a replication of the 2023 → 2024 result (17 of 20).

### What this can and can't show
- A "yes" on H4 with 5 drivers is weak evidence on its own; it is a first
  test, reported with all five distances, not a general law.
- A "no" doesn't prove the signature is the car: a driver can adapt their
  style to a new car. Both readings will be discussed.
- No result is used to change features, thresholds, models or rules afterwards.

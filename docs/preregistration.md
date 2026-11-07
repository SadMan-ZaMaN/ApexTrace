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

---

<!-- Part C below is generated by experiments/17_write_docs.py from docs/templates/preregistration_part_c.md.j2: edit the template, not this text. -->

## Part C: the 2026 season (H5, and H4 on the 2026 team changers)

**Written:** 2026-11-06, before any 2026 data was loaded. Since 2026-10-26 the code has
refused to load 2026 (`data_loading.FROZEN_SEASONS`, its own switch `FINAL_TEST_2026`,
checked by both data paths before any request), and no 2026 session is in the cache. The
design and its reasons are in `docs/h5_design.md`; a fresh-eyes review of a first draft of
this Part C (2026-11-06) led to the changes listed in `docs/decisions.md` under that date.

**What was known about 2026 when this was written:**
- *The analysis code and this text* were written with an AI assistant (Claude) working only from
  the FIA's rule texts (`docs/regulations_2026.md`) and the names of the two entrants announced
  before the season (Audi takes over the Sauber entry; Cadillac is a new team), used in the
  team map below. The assistant was trained on text up to mid-2026 and may therefore know
  some early-2026 results; it was told not to use them, and no part of the design depends on
  how anyone performed in 2026. No 2026 timing data was loaded.
- *The author:* "I know the driver line-up and which drivers changed teams, but not much about results. I know Kimi won this year's F1 title in Mexico." None of this is used in the design: team changers are found from the data by a fixed rule (`teams.team_changers`), and no rule depends on any driver's 2026 results.

**Code:** the version committed together with this text. The run is
`experiments/23_final_2026.py`; every result comes from `apextrace/h5_protocol.py`, the code
the dry runs tested. It refuses to run unless `FINAL_TEST_2026=1` is set, this file is
committed and unchanged, the script, `src/apextrace/` and the pinned reference files are
identical to the commit that added this Part C, the 2025 reference files match their
fingerprints (SHA-256, `results/24_dry_run_checks/summary.json`), and no
`results/final_2026*/summary.json` exists. **It is run once.**

This text is generated by `experiments/17_write_docs.py` from
`docs/templates/preregistration_part_c.md.j2`. Every result number in it comes from a results
file and every rule value from the code itself; the few fixed facts typed into the template
(the FIA's −30 % / −55 % targets, the feed's "104" marker, the grid of q values) are rule texts
or design choices. Once committed, the generator refuses to change this Part C.

### What changed in 2026
A new car generation: smaller and lighter cars, about 30 % less downforce and 55 % less drag
(FIA targets), active front and rear wings instead of DRS, and a power unit with about half
its power from the battery, whose electric power falls away at high speed
(`docs/regulations_2026.md`, from FIA Section C Issue 17 and Section B Issue 07).

### Data
- **Sessions:** every 2026 main qualifying session on OpenF1 (no sprint qualifying) that ended
  before **2026-11-06 00:00 UTC**. This cutoff was fixed when this text was written, so the day
  of the run can't change which sessions count; the run may start from 2026-11-07 00:00 UTC
  (OpenF1 needs a day to finish its data). The 2026 season is not over by then, and the test
  does not wait for it. Power is set mainly by the number of drivers; fewer weekends make each
  signature noisier, which pulls the comparison towards a coin flip, so a short season can only
  make a "yes" harder.
- **Order (the Baku lesson):** first every session is downloaded into the cache. A failed
  download is tried 2 more times; if it still fails, the run **stops** with
  no result (crash rule below). Only then come the checks, then the build, then the analysis.
- **Build:** exactly as 2023–2025 (`session_build.build_session`): lap selection, automatic
  corner detection on each session's fastest kept lap with the same corner-type rule (slow
  below 120 km/h, fast from 200 km/h), features per corner
  window, cleaning (`dataset.clean`: dry compounds only, minimum speed below
  40 km/h dropped, impossible values set to missing), field-relative values,
  lap vectors. Drivers are matched across seasons by their three-letter code.
- **Reference season:** 2025, from the saved data in `results/final/`, built the same way.

### Checks before any feature (all on the downloaded 2026 data; any failure stops the run)
1. **The feed** (`quality.feed_check`, only samples inside kept laps; in the garage the feed
   sends 104 for throttle and brake):
   - channels present: speed, throttle, brake, gear, x, y;
   - at most 1 % empty in each;
   - at least 99.9 % of values in range (speed 0–400 km/h, throttle 0–100 %, brake only 0 or 100, gear 0–8; our braking
     features assume an on/off brake);
   - median interval between samples 0.20–0.28 s;
   - at least 95 % of the intervals shorter than 0.6 s on the 40 ms clock;
   - 3.3–4.3 samples per second.
   For comparison, 2024 in the dry run: median 0.240 s,
   99.99 % on the clock, 3.77 samples per second, throttle
   in range 99.99 %, brake 0 or 100 for 99.99 %.
2. **The team names:** every 2026 team name must match exactly **one** lineage in
   `teams.LINEAGE_PATTERNS`; a name that matches none, or two or more (a constructor-style
   "McLaren Mercedes"), or is missing, stops the run:

   | Lineage | Patterns (lower case) |
   |---|---|
   | Red Bull Racing | `red bull racing` |
   | Racing Bulls | `racing bulls\|alphatauri\|toro rosso\|^rb$\|\brb f1\b` |
   | Sauber / Audi | `sauber\|alfa romeo\|\baudi\b` |
   | Haas | `\bhaas\b` |
   | Ferrari | `ferrari` |
   | Mercedes | `mercedes` |
   | McLaren | `mclaren` |
   | Aston Martin | `aston martin` |
   | Alpine | `alpine` |
   | Williams | `williams` |
   | Cadillac | `cadillac` |

3. **The tyre labels** (`dataset.compound_check`): every kept lap's compound must be one of
   HARD, INTERMEDIATE, MEDIUM, SOFT, UNKNOWN, WET, and at most 5 % may be empty. (The cleaning
   keeps only HARD, MEDIUM, SOFT, so a new label would otherwise drop every lap as "not dry"
   without a word.)

**If a check fails:** no feature or result is computed. The failure is described in
`docs/preregistration_deviations.md`, and a written addendum to this Part C is committed before
anything else is run. The addendum may change **only** what the failed check is about (for
example, add a team name to the map or a tyre label to the known list); it may not touch the
features, the tests, the decision rule or the sessions.

### H5 (primary): does a driver's signature survive the new car generation?
- **Drivers:** everyone with at least 5 dry qualifying weekends in 2025
  and in 2026, whose 2025 team had another driver sharing at least 5
  of those weekends. Drivers who changed team for 2026 are included. 2025 gives an upper
  bound of **21** drivers.
- **Signatures** (`signatures.own_vs_past_teammate`): the mean of the 30
  lap-vector features (10 field-relative corner features × slow, medium and fast corners),
  each weekend counted once.
  - 2026: all of the driver's dry 2026 weekends.
  - 2025: the driver and their 2025 teammate, both built only on the weekends they shared,
    and on each of those weekends from **the same number of laps**: the smaller of the two
    counts, each driver's first laps of that session. The teammate is the other driver of the
    driver's most-driven 2025 team with the most shared weekends (alphabetical on a tie; the
    most-driven team is also chosen alphabetically on a tie).
  - All z-scored with the spread of the **other** drivers' 2025 full-season signatures (the
    pair left out); distance = root-mean-square difference over shared features.
- **Test:** a driver is a success if their 2026 signature is closer to their own 2025
  signature than to their 2025 teammate's. **One-sided sign test; H5 is supported if
  p < 0.05.** If fewer than 5 drivers can be compared, no result can reach
  p < 0.05, and H5 is reported as **not testable** (not as "not supported").
- **Why the coin is fair.** If the signature were only the car, both references (same car,
  same weekends, same number of laps) would be equally close: a fair coin per driver. Both
  the weekends and the laps have to match. A reference built on more laps is less noisy and
  sits closer to everything: in a car-only synthetic world where the driver who keeps the seat
  had 6 laps a weekend and the teammate 2, using all laps gave
  0.73 "own closer" instead of 0.5; with equal laps, 0.50
  (`experiments/22_h5_null_check.py`). Whatever the new car changes for a whole team (the car,
  its energy plan, what the throttle channel means, corners changing type) moves the driver's
  2026 signature the same way relative to both references, which can only push the result
  towards a coin flip.
- **Drivers are not fully independent.** Two 2025 teammates may both be compared, against the
  same two references. In 300 car-only synthetic studies of 20 drivers,
  71 % of such pairs split one-and-one (50 % if they were independent), the variance of
  the count was 3.06 against 5.00 for independent drivers, and the
  test came out "significant" in 0.007 of the studies. The test therefore says
  "yes" by chance less often than 5 %: dependence makes it conservative, not too easy. The power table below assumes independent drivers.

**Power, stated in advance.** The successes needed for p < 0.05 with n drivers:
8 → 7, 9 → 8, 10 → 9, 11 → 9, 12 → 10, 13 → 10, 14 → 11, 15 → 12, 16 → 12, 17 → 13, 18 → 13, 19 → 14, 20 → 15, 21 → 15. Power is the chance of a "yes" if each driver is closer to their own past with
probability q:

| Drivers | Needed | q = 0.6 | q = 0.7 | q = 0.8 | q = 0.85 | q = 0.9 |
|---|---|---|---|---|---|---|
| 12 | 10 | 0.08 | 0.25 | 0.56 | 0.74 | 0.89 |
| 14 | 11 | 0.12 | 0.36 | 0.70 | 0.85 | 0.96 |
| 16 | 12 | 0.17 | 0.45 | 0.80 | 0.92 | 0.98 |
| 18 | 13 | 0.21 | 0.53 | 0.87 | 0.96 | 0.99 |
| 20 | 15 | 0.13 | 0.42 | 0.80 | 0.93 | 0.99 |
| 21 | 15 | 0.20 | 0.55 | 0.89 | 0.97 | 1.00 |

Without a rule change, with exactly this procedure, q was 16 of 20 (0.80, 95 % interval 0.56–0.94) for
2023 → 2024 and 14 of 16 (0.88, 95 % interval 0.62–0.98) for 2024 → 2025 (`results/20_h5_development/`). At
those rates, with 14–21 drivers, the test would find the signature 70–89 % and
91–99 % of the time. **A "no" therefore can't tell a weakened signature from a
lost one**, and will be reported that way.

### Secondary analyses (reported, not decisions)
1. **Feature groups**, each with the same test, shown side by side with no test of the
   difference: control points (`brake_onset_m`, `min_speed_kmh`, `apex_m`, `throttle_pickup_m`; 12 columns) and
   energy-sensitive (`entry_speed_kmh`, `exit_speed_kmh`, `full_throttle_m`, `corner_time_s`; 12 columns). Development:
   control points 15 of 20 (0.75, 95 % interval 0.51–0.91) and 11 of 16 (0.69, 95 % interval 0.41–0.89); energy-sensitive
   14 of 20 (0.70, 95 % interval 0.46–0.88) and 12 of 16 (0.75, 95 % interval 0.48–0.93).
2. **Without throttle** (`throttle_pickup_m`, `full_throttle_m` left out; 24 columns), in
   case the 2026 throttle channel means power demand rather than pedal position.
   Development: 16 of 20 (0.80, 95 % interval 0.56–0.94) and 12 of 16 (0.75, 95 % interval 0.48–0.93).
3. **The share** of successes with an exact 95 % interval, next to the development values above,
   and, for each driver, the laps used per reference.
4. **The number of corners of each type** in 2025 and 2026 (`h5_protocol.corner_type_counts`):
   with less downforce some fast corners may become medium ones. Descriptive only.
5. **H4 again, on the 2026 team changers** (`h5_protocol.h4_results`). Changers come from the
   data, not from a typed list (`teams.team_changers`: the most-driven team in each season,
   a different lineage, at least 5 weekends in both). For each: is the
   2026 signature closer to the driver's own 2025 signature than to the new teammate's 2026
   signature on the same weekends? That is Part B's comparison, with one change learned since
   (`docs/engineering_notes.md`, 2026-11-03): the driver and the new teammate are left out of
   the z-score spread. Within 2026, teams are grouped by lineage, so a mid-season rename can't
   split one. One-sided sign test, reported but not a decision. With
   3 changers: no p < 0.05 possible; 4 changers: no p < 0.05 possible; 5 changers: 5 needed; 6 changers: 6 needed; 7 changers: 7 needed; 8 changers: 7 needed. **Caveats:** for these drivers the team and the rules change at once;
   and two changers in the same new team (for example both drivers of a new team) share the
   same distance to each other, which makes their outcomes alike, so this sign test (and
   Fisher's test below) can say "yes" more easily than its p-value suggests.
6. **The stayer control:** the same comparison for the drivers who stayed in their team, and
   Fisher's exact test of changers against stayers. This comparison leans towards the
   teammate (same car, same weekends). Development: stayers 11 of 20 for
   2023 → 2024 and 8 of 10 for 2024 → 2025.

### Measurement notes, fixed in advance
- **Coasting before braking** (`experiments/21_coasting_check.py`): the brake-onset estimator's
  worst error on synthetic 2026-like corners is 4.89 m, under the
  8.4 m set in advance, so no variant is added. Coasting moves the
  estimate by 3.9–4.7 m, which will be kept in mind
  when brake onset differs.
- **Dry runs** (`results/final_2026_dry_run/`, `results/24_dry_run_checks/`): on 2024 the script
  went through every phase from the cache and rebuilt 15,129 rows identical to the
  development dataset (largest difference 0.0); H5 gave 16 of 20,
  as in development. On 2025, H5 gave 14 of 16, and with Part B's spread the H4 code
  reproduced the frozen distances of all 16 drivers of the exploratory 2025
  follow-up (6 changers including Colapinto, and 10 stayers) to the stored precision.

### What this can and can't show
- A "yes" on H5 says a driver-specific part of the corner signature survives a new car
  generation. It doesn't say how much, and it doesn't rank drivers.
- A "no" is either a lost signature or a weakened one; the power table above says which
  effects the test could see.
- H3 (teammate identification) is not retested on 2026.
- **Deviations.** Crash rule: if the run stops before writing any result file, the attempt is
  recorded in `docs/preregistration_deviations.md`, its folder is renamed
  `final_2026_attempt_<n>`, and the run is repeated with the same fixed cutoff. Results are
  computed in memory and written only at the end; if any result file (`h5_*`, `h4_*`,
  `team_changes.csv`) was written, the attempt counts as a run. Bug rule: a bug found after
  results exist is fixed, the run is repeated into a new folder, and both results are
  reported.
- No 2026 result is used to change features, thresholds, models or rules. Anything not listed
  here is exploratory and labelled so.

<!-- end of Part C -->

<!-- Addendum 1 to Part C below is generated by experiments/17_write_docs.py from docs/templates/preregistration_part_c_addendum_1.md.j2: edit the template, not this text. -->

## Addendum 1 to Part C (2026-11-07): the feed's "no value" marker inside laps

**Why there is an addendum.** The one-time run stopped at the feed check before any feature or
result was computed (attempt 1; `docs/preregistration_deviations.md`, 2026-11-07). Part C says
that an addendum may then change **only** what the failed check is about, and must be committed
before anything else is run. This is it.

**What the check found** (`experiments/25_feed_check_2026_diagnosis.py`, which reads only the two
failing channels inside kept laps, as the check did): every throttle value outside 0–100 and every
brake value that is not 0 or 100 is **104**, the feed's "no value" marker, until now seen in the
garage and pit lane. There were 5,808 throttle and 6,496 brake samples of
576,625; 6,539 samples (1.13 %) had one or both. No other new
value appears. The marker is concentrated in a few sessions (Suzuka 8.3 %, Shanghai 8.0 %, Monza 1.1 % of their samples; every
other session at most 0.29 %). In the development seasons it was in 2023 0.015 %, 2024 0.006 %, 2025 0.007 % of
the throttle samples inside kept laps. (Sakhir and Jeddah have no kept laps in OpenF1; the build
skips sessions without laps, as it did for Baku in 2025. This is not part of the change.)

**Why it has to be handled.** The feature code reads a throttle of 104 as "above 99 %" (full
throttle) and a brake of 104 as "on". Left in, these samples would move throttle and braking events.

**The change.**
- Inside a kept lap, a car sample whose throttle or brake is 104 is a **missing sample**. It is
  removed before any feature is computed (`openf1.drop_no_value_samples`, used by `openf1.slice_lap`),
  exactly like a feed dropout. The existing rule that drops a (lap, corner) pair when its corner
  window has a gap above 0.6 s applies unchanged.
- The feed check runs on the same cleaned samples, with all its rules unchanged, so any
  out-of-range value other than 104 still stops the run. The number of samples removed is
  reported for each session (`checks.json`).

**Not changed:** the features, the tests, the decision rule, the sessions, the cutoff, and the 2025
reference season (it stays as built and pinned; the marker was too rare there to matter).

**Rehearsed** (`23_final_2026.py --dry-run 2024`, `experiments/26_addendum_1_dry_run_check.py`): with
the rule, 2024 went through every phase from the cache, and the checks
passed. 92 marker samples were removed, 18
of 15,129 (driver, lap, corner) rows changed against the development dataset (usable rows
12,749 → 12,736), and H5 gave 16 of 20, the same as in development.

**The repeated run:** the folder of attempt 1 is renamed `final_2026_attempt_1`, and the run is
repeated with the same fixed cutoff (2026-11-06 00:00 UTC), the same sessions and this rule.

<!-- end of Addendum 1 -->

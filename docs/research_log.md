# Research log

Newest entry at the bottom. Each entry: what I tried, what happened (numbers,
not impressions), and what's next. Negative results count as results. If I
stop in the middle of a step, write "stopped at … / next: …".

---

## 2026-10-14 — Phase 0: setup

**Did**
- Split `CLAUDE.md` into a short working file (242 lines) plus
  `docs/PROJECT_CONTEXT.md` (the full plan, original section numbers kept).
  Deleted the chat reply that had been pasted at the end of the file by accident.
- Recorded the answers to the open questions (PROJECT_CONTEXT §19): solo; time;
  repo ApexTrace with package `apextrace`; 2025 frozen as the final test set;
  no faculty member yet.
- Created `docs/decisions.md`, this log, and `docs/related_work.md` (seeded
  from §12.2).
- Environment: `.venv` with Python 3.13.2, `requirements.txt` (pinned with
  `pip freeze`), `pyproject.toml`, `.gitignore`, folder structure, and
  `tests/test_smoke.py`.

**Versions:** Python 3.13.2 · FastF1 3.8.3 · NumPy 2.5.4 · SciPy 1.18.1 ·
pandas 2.3.3 · Matplotlib 3.11.2 · pytest 9.1.1.

**Result**
- FastF1 3.8.3 installs and imports on Python 3.13, so the fallback to 3.12 isn't needed.
- Smoke test: fails with `ModuleNotFoundError: No module named 'apextrace'`
  before `pip install -e .` (good: it catches a missing install), and passes after it.
- No F1 data has been downloaded yet.

**Next**
- `experiments/00_hello_lap.py`: load 2024 Abu Dhabi Q, plot Norris's fastest
  lap, speed vs distance → `results/figures/00_hello_lap.png`. Check the
  FastF1 method names (`pick_drivers`, `pick_fastest`, `get_car_data`,
  `add_distance`) against 3.8.3.
- Phase 1: `src/apextrace/data_loading.py` (`load_session`, `select_laps`, which
  returns the kept laps plus a table of dropped laps with reasons), then the
  NOR/PIA lap table for Q and FP2 (§7 checklist items 6 and 8).

---

## 2026-10-15 — Phase 0 finished, Phase 1 started (checks 6 and 8)

**Did**
- `experiments/00_hello_lap.py` → `results/figures/00_hello_lap.png`:
  Norris's pole lap, speed vs distance, one dot per car-data sample.
- `src/apextrace/data_loading.py`: `load_session()` (cache, plus a guard
  that refuses 2025) and `select_laps()` (kept laps + dropped laps with reasons).
- `src/apextrace/plots.py`: shared figure style, fixed colours per driver.
- `tests/test_data_loading.py`: 6 tests on a hand-made lap table. Each one was
  checked to fail when the code is deliberately broken (5 deliberate bugs,
  all caught).
- `experiments/01_data_pilot.py` → `results/01_data_pilot/lap_table.csv`
  (checks 6 and 8).

**Results (all numbers printed by the scripts)**
- Hello lap: 1:22.595 (matches the official pole time). 320 car-data samples
  in 82.595 s = 3.87 samples/s on average. Speed 68–324 km/h. Distance from
  integrating speed: 5,211 m. ⚠️ The official Yas Marina lap length is
  ~5.28 km (from memory, not checked), so integration may come out ~70 m
  short. Measure properly in check 5.
- First download of a session: ~19 s and 45.5 MB of cache (a first number for check 9).
- FastF1's own docs (`Session.load`) warn: *"Expect an error of around ±10m
  when overlapping telemetry data of different laps."* That is the size of the
  alignment problem for Phase 3.
- **Check 6, usable laps:**
  - Q: **4 push laps per driver** (one in Q1, one in Q2, two in Q3), all on
    soft tyres. Piastri's best 82.804 − Norris's 82.595 = 0.209 s, which
    matches the official gap.
  - FP2: NOR keeps 10 of 25 laps and PIA 12 of 28. Both have a **7-lap
    medium long run** (NOR laps 15–21, tyre age 10–16; PIA laps 18–24,
    tyre age 12–18). Those are matched runs for the FP2 repeatability check.
  - `timing check failed` (FastF1 `IsAccurate`) never drops a lap on its own:
    it only ever appears together with out lap, in lap or no lap time.
- **Check 8, FastF1 helpers:** all of these exist in 3.8.3: `pick_wo_box`,
  `pick_not_deleted`, `pick_track_status`, `pick_accurate`, `pick_quicklaps`
  (plus `split_qualifying_sessions`). In Q, chaining them keeps the same laps
  as `select_laps()`. In FP2 they differ, as expected (see the problem below).

**Problem found and fixed: the first slow-lap rule was biased**
The first version dropped laps slower than 107 % of the driver's *session*
best. In FP2 that best lap was on soft tyres, and the medium long run sits at
106–109 % of it. Result: 6 of Norris's 7 long-run laps were dropped
(threshold 83.517 × 1.07 = 89.36 s) but only 2 of Piastri's (83.751 × 1.07 =
89.61 s). The same kind of lap was treated differently just because one
driver's soft lap was 0.23 s quicker. Fix: compare each lap with the best lap
of its own stint, plus a rule that drops stints that were never timed runs
(decisions.md, 2026-10-15). Lesson: a threshold measured against a single
extreme value (the best lap) carries that value's noise and its confounders.

**Next (Phase 1, checks 1–5, 7, 9)**
- `src/apextrace/quality.py`: sample-interval statistics, a gap finder, and a
  quantisation check.
- Extend `01_data_pilot.py`: timing histogram (check 1), channel resolution (2),
  brake values (3), position data rate and noise (4), distance drift on the 4 Q
  laps per driver (5), `get_circuit_info()` corners (7), cache size and load time (9).

---

## 2026-10-16 — Phase 1: data checks 1–5, 7, 9

**Did**
- `src/apextrace/quality.py`: `sample_intervals`, `interval_summary`,
  `event_timing_error_s`, `share_on_grid`, `find_gaps`, `smallest_step`,
  `path_length`, `distance_to_path`. `tests/test_quality.py` has 11 tests on
  synthetic signals, including a Monte Carlo check of the timing-error formula.
  5 deliberate bugs, all caught.
- `experiments/01_data_pilot.py` now runs checks 1–9 and writes everything to
  `results/01_data_pilot/`: `summary.json`, `lap_table.csv`, `gaps.csv`,
  `interval_histogram.csv`, `lap_distances.csv`, `corners.csv`,
  `sample_intervals.png`, `corners_on_speed.png`.

**Results** (30 kept laps: 2024 Abu Dhabi Q + FP2, NOR + PIA; numbers from `summary.json`)
- **Check 1, timing.** Car data: 3.77 samples/s on average (mean interval
  0.265 s), median 0.24 s. Every interval is a whole number of **40 ms clock
  ticks** (100 % within 2 ms). Normal intervals run from 0.16 to 0.56 s, which
  at 300 km/h is **13–47 m between samples** (mean 22 m). Position data: 3.85/s,
  on a 20 ms clock.
- **Feed dropouts:** 36 car-data gaps of 0.64–1.36 s (up to 113 m at 300 km/h)
  in 21 of 30 laps. Every one coincides with a position-data gap, and both
  drivers lose data at the same session moments (24 distinct moments), so these
  are pauses in the whole timing feed, not car problems. Some fall in braking
  zones: PIA Q lap 2 goes from 295 to 139 km/h across a 1.16 s gap at ~2,520 m
  (Turn 6). Full list: `gaps.csv`.
- **Event timing error** (an on/off event placed at the middle of its interval,
  one lap): 0.093 s with gaps, 0.087 s without, against 0.077 s if sampling were
  regular at the mean interval. At 300 km/h that is 7.7 m, against the 6.4 m of
  the naive formula. The reason is the inspection paradox: events land in long
  intervals more often.
- **Check 2, resolution:** Speed in whole km/h (61–327), Throttle in whole %
  (0–100), RPM in whole rpm, X/Y/Z in whole decimetres (0.1 m). DRS codes 8,
  10, 12, 14.
- **Check 3, brake:** `bool`, only True/False; braking in 14.8 % of samples.
- **Check 4, position:** all samples `OnTrack`. Other laps lie a median of 0.06 m
  (95th percentile 0.54 m) from a driver's reference path, and **exactly the
  same** from the teammate's path (0.06 / 0.54 m), and FP2 laps from the Q path
  (0.05 / 0.49 m). Real racing lines differ by more than that between drivers.
  ⚠️ Hypothesis: the position feed is smoothed or matched to a track model. Either
  way, X/Y can't show racing-line differences.
- **Check 5, distance** (integrating speed from the exact lap start to the exact
  lap end): mean 5,219 m, 62 m (1.2 %) shorter than the official centre-line
  length of 5,281 m (formula1.com, checked); the X/Y path gives 5,230 m. A racing
  line is shorter than the centre line, so being short isn't an error by itself.
  Lap-to-lap: in Q, gap-free laps are within 2.0 m of the driver's mean, laps
  with gaps up to 9.0 m. In FP2 the spread is up to 19 m, with or without gaps
  (cause not known yet). FastF1's default `add_distance()` leaves out the stretch
  from the last sample to the line and spreads more (up to 43 m).
  → Distance needs aligning (Phase 3); feed gaps are a main error source.
- **Check 7, corners:** `get_circuit_info()` gives 16 corners with a distance
  along the session's fastest lap (NOR's pole lap), at the position sample
  nearest each marker, so each corner's distance is uncertain by about half a
  sample (up to ~10 m at speed). Usable for placing corner windows.
- **Check 9, cost:** cache 40.4 MB for Q, 61.3 MB for FP2, plus a 17.1 MB HTTP
  cache. Load from cache 1–3 s; the first download of Q took ~19 s. Phase 6
  estimate: ~46 qualifying sessions × ~40 MB ≈ 1.9 GB ⚠️ (session count not
  checked yet).

**Surprises and traps found**
- FastF1 3.8.3's docs say interpolated rows have `Source == 'interpolated'`,
  but the code writes `'interpolation'`. A check for `'interpolated'` silently
  finds nothing.
- Sampling isn't "3.7 Hz with jitter". It is a 40 ms clock with 4–14 ticks
  between samples, plus dropouts. The synthetic-lap generator (Phase 2) must
  draw intervals from the real distribution (`interval_histogram.csv`), not
  use 3.7 Hz plus small jitter. Otherwise the error bars will be too optimistic.

**Next (Day 4):** choose the 3 corners (check 10), using `corners_on_speed.png`.
Decide a rule for (lap, corner) pairs with a feed gap inside the corner window:
at Turn 6, PIA's Q laps 2 and 7 both have gaps nearby. Then write
`docs/data_report.md` and log the choices in `decisions.md`.

---

## 2026-10-16 (later) — Phase 1 finished (M1), Phase 2: measurement science

Context: Sadman has exams; Claude builds autonomously, and everything is
documented in `learn/` for later study.

**Phase 1 finished:** check 10 chose T6 (heavy braking), T5 (medium) and T9
(fast) by a fixed rule (decisions.md); gap rule decided; `docs/data_report.md`
written. **Milestone M1 done.**

**Phase 2 built:** `synthetic.py` (true corners at 500 Hz, realistic physics:
4.8–5.9 g peak braking, ~110–125 m braking zone at the T6 type),
`degrade_like_feed()` (real interval distribution, 1 km/h rounding, on/off
brake), `resampling.py`, `filters.py`, `events.py` (naive vs refined
estimators). 45 tests, including a 200-corner full-path test.

**Results**
- `02_group_delay_demo.py`: causal filters delay a mid-braking point by
  +14 to +25 m; zero-phase filters by only +2 to +3 m. **But** zero-phase
  smoothing still moves a braking-*onset* detector 23–36 m *early*: it removes
  the delay, not the smearing of a sharp event (Consonance lesson 4). Group
  delays: MA(5) 0.50 s, Butterworth 0.5 Hz 0.46 s, EMA(0.5) 0.21 s. Raw
  derivative noise from 1 km/h rounding: 0.49 m/s² (0.05 g), against the
  theoretical 0.42 m/s² for regular sampling.
- Real speed spectrum: never meets the 1 km/h rounding floor; it flattens at
  14× the floor above a knee at **1.19 Hz**. The flat part behaves like noise
  from irregular sampling and interpolation, not from rounding.
- `03_synthetic_errors.py` (1,000 laps per corner type): see decisions.md for
  the chosen estimators. Brake onset: naive +12.5 m late; midpoint unbiased,
  std 7.7 m (**matches the 7.7 m predicted from real intervals in Phase 1**);
  breakpoint inside the interval: +3.2 ± 2.7 m. Averaging N laps shrinks the
  spread like 1/√N (16 laps: 2.70 → 0.68 m). Irregular sampling costs ~11 %
  more error than regular sampling at the same rate. Peak deceleration can't
  be measured (biased −6 to −20 m/s²) → replaced by mean deceleration.

**Negative result kept:** peak deceleration isn't measurable from this feed.

---

## 2026-10-16 (later) — Phase 3: alignment (M3)

**Built:** `alignment.py` (projection onto a path, normalised cross-correlation,
parabolic peak), `track.py` (FastF1 lap → samples with track coordinate),
`corners.py` (corner positions, windows, gap check, fused coordinate).
Tests: projection on a curved track, hairpin snapping, the 7.3 m synthetic
shift recovered to < 0.1 m, fusion removing a 12 m drift. 53 tests pass.
`experiments/04_alignment.py` → `results/04_alignment/`.

**Results (30 laps, 2024 Abu Dhabi Q + FP2)**
- Projection: median 0.05 m from the path; s ran backwards (> 0.5 m) once.
- X/Y has ~3 m longitudinal noise per sample (4.5 m std of increment
  residuals); likely timestamp jitter (residual correlates with interval
  length, r ≈ −0.3 to −0.4; no constant lag).
- Integrated distance drifts relative to X/Y by up to 13 m at T9 in Q
  (std 4.8 m on gap-free laps).
- Fused coordinate: offset noise 1.15 m with 1/speed² weighting (1.46 m
  without). The theory said ~0.6 m; the measured value is used.
- Sampling phase uniform (KS p = 0.43): averaging laps is valid.
- Usable (lap, corner) pairs, Q: T6 NOR 4 / PIA 2, T5 4 / 4, T9 3 / 4.
  FP2: T6 8 / 9, T5 7 / 10, T9 10 / 10.
- The aligned overlays (`corners_Q.png`, `corners_FP2.png`) line up within a
  few metres in the braking zones.

**Surprise:** the plan assumed X/Y projection would be clean. It isn't
along the track, but it is drift-free, and fusing it with speed is a
classic complementary filter.

---

## 2026-10-16 (later) — Phase 4 (features, output A), Phase 5 prepared, data-source problem

**Phase 4:** `features.py` (11 features, estimators from Phase 2; full-path test
on 150 synthetic corners). `experiments/05_pilot_features.py` → 75 of 90
(lap, corner) pairs usable. Qualifying, descriptive: NOR's brake onset is later
than PIA's at T5 (+7.42 m, SE 2.11, 4 vs 4 laps, same laps for both) and T9
(+7.20 m, SE 2.05, 3 vs 4); T6 inconclusive (+3.06, SE 6.22, 4 vs 2). Minimum
speeds within 0.5 km/h; corner times within 0.03 s. Visual check: the event
markers sit where expected. Output A drafted: `docs/writeups/norris_vs_piastri.md`.

**Phase 5 prepared:** `stats.py` (exact permutation test, bootstrap interval,
Hedges' g, Holm, Benjamini–Hochberg, ICC(1), minimum detectable effect), with
9 tests on known answers (false-positive rate ~5 %, bootstrap coverage ~95 %,
hand-computed ICC). `docs/preregistration.md` Part A written. **The pilot can't
produce any discovery:** with 4 vs 4 laps the smallest possible p-value is
0.029, and Benjamini–Hochberg over 27 tests would need 16 of them at that
minimum. 80 % power needs d ≥ 2.38. `experiments/06_pilot_stats.py` refuses to
run until the preregistration is committed (checked: it stops).

**Data-source problem:** the F1 live-timing archive returns 401 for everything
not already cached (FastF1 download of 2023 failed for all sessions tried).
OpenF1 serves the identical feed (checked sample by sample on the pole lap).
Phase 6 will use OpenF1 (decisions.md).

**Next:** Sadman commits (the preregistration first). Then run
`06_pilot_stats.py`, and build the OpenF1 adapter for Phase 6.

---

## 2026-10-17 — Phase 5: preregistered pilot tests run (H1, H2)

Ran `experiments/06_pilot_stats.py` after the preregistration was committed
(`ab2510c`); the script checks this with git. Results: `results/06_pilot_stats/`.

**H2 (qualifying, NOR − PIA, 27 tests):** **0 discoveries** after
Benjamini–Hochberg, as stated in advance. Largest effects:
- Brake onset T5: +7.42 m, Hedges' g +2.16, p = 0.057 (4 vs 4 laps).
- Brake onset T9: +7.20 m, g +1.92, p = 0.057 (3 vs 4).
- Full throttle T9: −56.71 m, g −4.43, p = 0.029 (the smallest possible for
  3 vs 4).
- Throttle pickup T6: +3.54 m, g +2.05, p = 0.067 (the smallest possible for 4 vs 2).
The bootstrap 95 % intervals for both brake onsets exclude 0 ([+3.5, +10.5] m
at T5, [+3.5, +10.4] m at T9). But with 3–4 laps the bootstrap only knows the
variation it has seen, so these intervals are too narrow to rely on alone.
Pilot verdict: **consistent with Norris braking ~7 m later at T5 and T9, not
confirmed.**

**The T9 full-throttle effect, looked at in the raw traces:** NOR reaches
100 % about 30–55 m after the marker. PIA holds partial throttle (80–95 %) for
~50–80 m, then reads 99 % for ~100 m before 100 %. The pattern is real in all
4 laps, but the size of the 57 m figure depends on where the fixed 99 %
threshold falls. Idea for Phase 6 (exploratory, not preregistered): a
threshold-free throttle feature, such as mean throttle over the 100 m after the apex.

**H1 (exploratory):** lap-to-lap SD / per-lap measurement error, Q: brake onset
0.19–3.04 (often at the measurement-error level); minimum speed 1.98–12.19
(laps genuinely differ by several km/h, far more than the 0.35 km/h
measurement error). FP2 long runs: larger (brake onset 2.3–5.9). ICC with 2
drivers: very wide intervals (e.g. T5 brake onset 0.74 [0.34, 0.99]); no
conclusion until Phase 6 has all drivers.

**Correction found:** `min_permutation_p` used 2/C also for unequal groups
(wrong: 1/C). Fixed and tested; recorded in `docs/preregistration_deviations.md`.
The p-values themselves were always right.

**Phase 5 done (M5).**

---

## 2026-10-17 — Phase 6, part 1: OpenF1 adapter, validated

**Built:**
- `openf1.py`: cached downloads with retry/backoff; sessions, drivers;
  deleted laps from race-control messages (matched by lap time, reinstatements
  undone); flag intervals (yellow per mini-sector until CLEAR, red, SC, VSC);
  the lap table with FastF1's columns; per-lap car and position streams;
  lap → track coordinate.
- `track.py` refactor: a source-independent core (`clip_to_lap`,
  `samples_on_track`, `reference_path_from_xy`) plus thin FastF1 wrappers.
  Checked: all 90 pilot feature rows identical before and after.
- `check_not_frozen()` shared by both data sources (2025 guard).
- 6 new tests (deleted/reinstated, flag intervals, the lap-table rules,
  overlapping stints, edge samples). 70 tests pass.

**Validation (`experiments/07_openf1_validation.py`, 2024 Abu Dhabi):**
- Lap times identical on every non-out lap in Q (FP2: 92.6 %), out/in laps
  100 %, deleted laps 100 %, green/not green 100 %, stint and compound 100 %.
- First run: OpenF1 kept ~1 lap per driver instead of ~4, because FastF1's
  check 4 (lap start = previous lap end within 3 ms) fails on OpenF1's
  less precise lap start times, and stint boundaries overlap. After the two
  fixes: **kept laps identical for 20 of 20 drivers in both sessions.**
- Features: all 75 usable pilot (lap, corner) pairs usable in both;
  differences ≤ 0.23 m (brake onset), ≤ 0.10 m (apex), ≤ 0.004 km/h (min speed).

**Removed:** `experiments/07_download_qualifying.py` (FastF1 download, which no
longer works: every 2023 session failed with 401 on 2026-10-16).

**Next (Phase 6, part 2):** download 2023–2024 qualifying through OpenF1 (only
the kept laps' car and position data), automatic corner detection (braking
corners from the reference lap's speed dips), and the dataset: one row per
(session, driver, lap, corner).

---

## 2026-10-17 (later) — Phase 6, part 2: 2023–2024 dataset and EDA

**Download** (`08_download_openf1.py`): 47 sessions, 4,500 kept laps, 4,499
with data (2023 Imola: cancelled, no data). 156 MB compressed cache. The first
per-lap version ran into OpenF1's ~30 requests/min limit (429). Fix: one
request per driver per session, starts paced 2.1 s apart, 3 in flight → ~92 s
per session.

**Corner detection and robustness** (`corners.detect_braking_corners`,
`events.braking_event`): see decisions.md. The pilot is unchanged (90/90 rows).
A first version moved some FP2 brake onsets by 153 m (brief brake releases);
fixed by merging brake runs without throttle opening in between.

**Dataset** (`09_build_dataset.py`): 30,441 (lap, corner) rows, 24,496 usable
(80 %; exclusions: 5,938 feed gaps, 7 without data); 4,497 laps, 25 drivers,
314 detected corners (5–11 per track), 46 sessions. Raw samples: 1,443,744
rows in `raw_samples.parquet` (36.9 MB, local only).

**EDA** (`10_eda.py`): laps per driver and session: median 5 (1–14).
Missing: full throttle 8 %, throttle pickup 5 % (clean rows). 798 values
outside physical limits before cleaning. Causes: wet sessions, flat-bottomed
fast corners, corner sequences, corners without throttle closing, and a few
broken laps → cleaning rules (decisions.md) → **21,493 clean rows, 44 dry
sessions**. Correlations of field-relative features are physically sensible:
min speed ↔ corner time −0.62, apex ↔ throttle pickup +0.57.

**Next (Phase 6, part 3):** H1 with all drivers (ICC per feature and corner
type), then H3: identification on held-out sessions with baselines
(majority, lap time only, raw stats) and our features; ablation; shuffled
labels.

---

## 2026-10-17 (later) — Phase 6, part 3: H1 with all drivers, H3 identification (development)

**Built:** `identification.py` (lap vectors per corner type, leave-one-session-out
with a leakage assert, scikit-learn pipelines fitted on training sessions only,
balanced accuracy / macro-F1, shuffled labels within sessions);
`stats.icc_from_groups` and `stats.icc_from_group_stats` (fast ICC, tested equal
to `icc_oneway`); `11_repeatability.py`, `12_identification.py`. 6 identification
tests, including a synthetic signature whose accuracy must fall in its
theoretical range (an upper bound catches leakage). scikit-learn 1.9.1 added.

**H1 (`results/11_repeatability/`), 21,493 clean rows:** lap-level ICC
0.15–0.58 (drivers clearly distinguishable on the same day); weekend-level ICC
0.04–0.40. Braking points are distinctive on the day but hardly persist (slow
corners: 0.45 vs 0.04); minimum speed persists best (0.23/0.30/0.40 slow/medium/fast)
and medium-corner throttle (0.38). Lap-to-lap spread is 5–25× the measurement
error: the limit is real variation, not the 4 Hz feed.
Mistake caught: the first weekend-level bootstrap resampled sessions,
duplicating identical driver means; estimates fell outside their intervals.
Fixed by resampling driver-seasons (sessions for the lap level). With group
summaries the run went from 9.6 min to 13 s (1,000 resamples).

**H3 (`results/12_identification/`), 3,873 laps:** teammates (20 team-seasons):
ours 0.685 [0.654, 0.716], weekend vote 0.763, lap time only 0.565 (ours better
in 18/20, Wilcoxon p = 0.0001), raw lap statistics 0.729 (ours better in 8/20,
p = 0.14), shuffled labels 0.500 (no leakage). Ablation: throttle carries the
most (without it 0.633). All drivers per season: ours 0.245 / 0.240 (chance
0.048 / 0.045), raw 0.326 / 0.287, lap time 0.079 / 0.087 (confounded by the car).
Investigated the raw baseline: the strongest single statistic is the share of
samples with the brake flag on (0.610 on average; Alpine GAS/OCO 0.92 and 0.88,
same sign in 94.7 % / 100 % of weekends); max speed alone 0.502. Driving habit or
the car's brake-sensor threshold? Can't be told with 2023–24 → H4.

**Verdict (development):** corner features carry a teammate signature that
generalises to unseen weekends (clearly above chance and lap time) but don't
beat simple whole-lap telemetry statistics. Part of any signature may be the car.

**Next (Phase 7):** H4 development on "same driver, same car, new year"
(2023 → 2024); write preregistration Part B (final H3 + H4 on 2025); Sadman
commits it; then the one-time 2025 run.

---

## 2026-10-18 — Phase 7, part 1: H4 development, preregistration Part B

**H4 development (`13_signature_stability.py`, 2023 → 2024, 20 drivers):**
season signatures (30 corner features, each weekend once) are stable: own 2023
signature ranks 3.05 of 21 on average (chance 11.0), first for 12 of 20,
permutation p = 0.0001. **Own 2023 closer than the 2023 teammate (same car)
for 17 of 20 drivers, sign test p = 0.0013**: the signature is more than the
car. Brake-flag share: correlation 0.95 between years; own closer than
teammate 15 of 20 (p = 0.021).
Correction during the run: the first version didn't match renamed teams
(AlphaTauri 2023 = RB 2024, Alfa Romeo = Kick Sauber), so BOT, ZHO, TSU and RIC
had no teammate (14 of 16, p = 0.0021; brake share 11 of 16, p = 0.105).
After mapping the renames (a factual correction, not a choice after seeing
results): 17 of 20 and 15 of 20.

**Built for the final run:** `signatures.py` (+ 5 tests, including a realistic
20-driver check and a no-signature control; a first 5-driver test was too
small: with 5 random drivers one feature's spread was tiny and noise got
magnified), `protocol.py`, `session_build.py`, `openf1.download_session`,
`experiments/14_final_2025.py` (guards: FINAL_TEST=1, preregistration committed,
run once). Dry-run on development data: all code paths work.

**Preregistration Part B written:** H3 replication (Wilcoxon, ours vs lap time,
p < 0.05) and H4 (5 changers, sign test, needs 5/5 for p = 0.031), with
secondary analyses and what can and can't be concluded.

**Next:** Sadman commits; then `$env:FINAL_TEST = "1"` and run
`14_final_2025.py` once (~45–70 min: download of ~24 sessions + analysis).

---

## 2026-10-18 — Phase 7, part 2: the one-time final test on 2025

**How it ran:** after Sadman committed Part B (`225385c`), `14_final_2025.py`
ran with `FINAL_TEST=1`. Attempt 1 crashed in the download step at session 17
(2025 Baku: OpenF1 has no lap rows, 404); no result had been produced. Fix:
`lap_table` returns an empty table, and the session is skipped (+ a test that
fails on the old code). Recorded in `docs/preregistration_deviations.md`
**before** the rerun. Attempt 2 completed. Data: 23 of 24 sessions built, Las
Vegas wet (dropped by the dry rule), so 22 dry sessions; 9,272 usable rows →
8,871 clean; 1,984 laps; 10 teams.

**H3 (primary) — replicated.** Teammate identification, leave-one-session-out:
our corner features 0.662 [0.634, 0.694] vs lap time only 0.575 [0.527, 0.626];
better in 8 of 10 teams, Wilcoxon p = 0.027. Secondary, as in development:
raw lap statistics 0.680 [0.621, 0.745], ours not better (5 of 10, p = 1.0);
weekend vote 0.746; shuffled labels 0.507 (pipeline OK); dropping throttle
features costs the most (0.592); brake-flag share alone 0.610 (development:
0.610). Ferrari (HAM vs LEC): raw statistics 0.87, ours 0.62.

**H4 (primary) — not supported.** For the 5 preregistered team changers, the
2025 signature was closer to their own 2024 signature than to the new
teammate's for **2 of 5** (Hülkenberg 0.69 vs 1.40, Tsunoda 0.84 vs 1.01);
closer to the new teammate for Sainz (1.26 vs 0.73), Ocon (1.35 vs 0.96) and
Hamilton (1.04 vs 0.99, nearly equal). Sign test p = 0.81. Secondary: the
brake-flag share stayed closer to the driver's own for 4 of 5 (p = 0.19); own
2024 signature ranked 1st (HUL), 2nd (TSU), 4th (HAM), 12th (OCO), 15th (SAI)
of 22. Drivers who stayed: own 2024 closer than old teammate for 10 of 11
(p = 0.006), replicating development (17 of 20).

**Found after the run:** Colapinto (Williams 2024 → Alpine 2025) changed teams
but was missing from the preregistered list (he showed up in the non-changer
check). Primary left as preregistered; deviation recorded.

**Exploratory (`15_final_exploratory.py`, not preregistered):** changers
derived from the data = the 5 + COL; with COL 3 of 6 (p = 0.66). **Control:**
the exact H4 comparison for the 10 drivers who stayed (own 2024 vs current
teammate, same weekends): own closer for 8 of 10 (p = 0.055; exceptions ALB,
whose new teammate is Sainz, and LAW, only 6 weekends in 2024). Changers 2 of
5 vs stayers 8 of 10: Fisher's exact p = 0.25, too few changers to tell.
Non-changer check without COL: 9 of 10 (p = 0.011).

**Verdict:** within a team, drivers have a measurable signature that
generalises to an unseen season (H3) and persists from year to year (10 of 11).
Whether it **follows the driver into another car** was not shown: 3 of 5
changers moved closer to their new teammate. The preregistered caveat applies:
this doesn't prove the signature is the car (drivers adapt to a new car), and
with 5 changers the test was weak. Both readings remain open.

**Next:** Phase 8 — report, README with results, frontend (Flask + vanilla JS
or Streamlit, to decide with Sadman), CI.

---

## 2026-10-19 — Phase 8, part 1: web app foundation, overview, lap compare

**Built:** a local web app (Sadman chose Flask + vanilla JS + any library):
`app/` (application factory, blueprints, JSON API), D3 7.9.0 and Barlow fonts
stored in the repo with their licences, `experiments/16_app_data.py` (exports
sessions, team colours from the OpenF1 driver list, corners, track outlines,
the hero laps and the H1-H4 headline numbers into `results/app/`).
Pages: **Overview** (hero replaying 2024 Abu Dhabi NOR vs PIA pole laps in real
time on a track drawn from the feed's own X/Y; results board; pipeline) and
**Lap compare** (any two kept qualifying laps 2023-2025: speed, gap, throttle,
brake, gear on one distance axis, braking-zone zoom, hover readout, track map
coloured by mini-sector winner). Checked by screenshots (Playwright + Edge) at
1440 px and 390 px.

**Found and fixed while building: the gap curve was noise.** The first version
interpolated time over the projected position `s_m`: a ±0.1 s sawtooth. Measured
on 2024 Abu Dhabi NOR vs PIA (official gap +0.209 s): with `s_m` jitter 0.041 s
and +0.290 s at the line; with integrated speed `d_m` jitter 0.007 s and +0.198 s;
fused coordinate 0.005 s but +0.281 s. Projected position carries a
lap-specific offset of a few metres (likely position-vs-car timing), which a
difference of two laps doesn't cancel; the drift of integrated speed is
common to both laps and does cancel. Fix: gap on `d_m`, charts on the fused
coordinate `d + moving_average(s − d)` (400 m). The page now prints the check
(curve at the line vs official lap-time gap). With the fix, 12 of 24
mini-sectors are within 0.02 s ("even").

**Open question (not checked yet):** if projected position carries a
lap-specific offset of a few metres, the fused window coordinate used for the
corner features (Phase 3) inherits it: that coordinate is d plus an offset
estimated from the window's position samples, and the half-split check
(1.15 m) can't see an offset shared by the whole lap. It would add lap-to-lap
noise to the position features (brake onset, apex, throttle pickup), which
makes the H1 repeatability numbers conservative, but would bias drivers only if
the offset depended on the car or driver. Evidence so far is one lap pair; a
check over many lap pairs (end-of-lap gap from s vs the official lap-time gap)
belongs to future work. The frozen results are not affected by this note.

**Tests:** 9 new (synthetic laps with a known 1.0 s gap, the Flask API on a fake
results folder; the gap test fails on the old `s_m` version). All 101 pass.

**Next (Phase 8, part 2):** corner lab (per-corner features, repeatability)
and signatures page (H3/H4 visual), then README, report, CI.

---

## 2026-10-19 (later) — Phase 8, part 2: Corner lab and Driver vs car pages

**Built:**
- **Corner lab:** a dot plot per braking zone and feature, with the per-lap
  measurement error drawn on the axis and H1 repeatability in words. It uses
  the committed datasets through `dataset.clean`, tested so the exact analysed
  rows are shown.
- **Driver vs car:** H3 per team for each season, with the lap-time baseline,
  raw statistics and corner features; the H4 scatter of changers plus the
  exploratory control; and a 30-cell signature "fingerprint" heat strip per
  driver.
- **Export** (`16_app_data.py`): `features.json`, `identification.json` and
  `signatures.json`. The signatures are rebuilt with the exact H4 steps, and
  the script asserts that all 16 drivers' distances match the frozen and
  exploratory results to 0.001 (they do).
- **Checks:** the chart colours (blue/orange) passed the dataviz palette
  validator on the dark surface; screenshots at 1440 px and 390 px, all four
  pages without horizontal overflow; 3 new tests (cleaning rules on the corner
  rows, optional exports, feature list in sync). All tests pass.

**Reading aids, not new results:** the pages only display exported numbers. One
check made while writing the guide: lap-to-lap spread is 2.9–28 times the
per-lap measurement error for all 21 measured (feature, corner type) cases
(`results/11_repeatability/summary.json`).

**Next (Phase 8, part 3):** README with results, a short report, CI (GitHub Actions).

---

## 2026-10-19 (final build) — Phase 8, part 3: README, report, CI, handover

**Built:**
- **Generated documents.** `README.md` and `docs/report.md` are rendered from
  templates (`docs/templates/*.j2`) by `experiments/17_write_docs.py`. Every number
  comes from the results files through `collect_numbers()`, and a placeholder
  without a number is an error (Jinja2 StrictUndefined). All numbers are also
  saved to `results/report_numbers.json`. `tests/test_docs.py` re-renders the
  documents and fails if the committed files differ. Checked: it fails after a
  one-number hand edit of the README.
- **Report:** about 2,900 words, written for a faculty reader: abstract, data,
  measurement science, statistical design, results H1–H4 with both deviations,
  discussion, limitations (including the open position-offset question),
  references.
- **CI:** `.github/workflows/tests.yml` (Python 3.13, pinned requirements, pytest).
  Checked before adding: the suite passes in a fresh clone without any
  gitignored files, and a dry-run resolve finds Linux/Python 3.13 wheels for all
  58 pinned packages.
- **README screenshots** of the four app pages (`docs/images/`).
- **Related work:** Enev et al. 2016 (PoPETs) and Bell et al. 2016 (JQAS) were
  verified by web search, and only verified works are cited.
- **Handover:** `learn/14_presenting_and_next_steps.md` covers the video shot list,
  pitch, faculty email, CV lines, the update loop and what is most likely to break;
  the private roadmap has a task list for working alone.

**Wording checks made while writing:** balanced accuracy is not described as "the
share of laps"; "own signature closest" was changed to "closer than the
teammate's" (rank 1 only for 12 of 20); the 25.1 m filter shift is for the middle
of a braking event.

**State:** Phases 0–8 complete. 106 tests pass.

---

## 2026-10-20 — Replay controls, overview gap fixed, readability pass

- **Bug found and fixed:** the overview hero's live gap used projected position
  `s_m` (the Lap compare bug of 2026-10-19 had survived there). Measured on the
  hero laps: with `s_m` the gap ranged +0.051 to +0.465 s and read +0.290 s at the
  line; with `d_m` it ranged −0.059 to +0.223 s and read +0.198 s (official
  +0.209 s). `hero.json` now carries `d`, and the gap uses it.
- **Replay** (`app/static/js/replay.js`) on the overview and Lap compare:
  play/pause, ×1/×2/×4, a timeline, click-to-jump on the track and on the charts.
  On Lap compare there are position lines in every chart and a readout of the gap
  in seconds and metres. With reduced motion, nothing moves until the viewer
  presses play.
- **Readability:** a line legend on Lap compare, a mark key on the Corner lab, and
  evidence links from the results board to each hypothesis's page.
- Checked in Edge via Playwright: ×4 advanced 8 s in 2 s, click-to-jump worked on
  the track, chart and map, and there were no page errors.

---

## 2026-10-20 (later) — Method page: the measurement science as live charts

- **New page** `/method` (`app/templates/method.html`, `app/static/js/method.js`).
  Its data come from `method.json`, written by `16_app_data.build_method`: the pilot
  interval histogram; one synthetic braking event through each filter (the
  02_group_delay_demo functions; this corner's shifts match the 200-corner means, e.g.
  causal moving average +24.9 m here vs +25.1 m on average); every estimator's Monte
  Carlo error; the hero lap's position − integrated offset and the gap from each
  coordinate; and the cleaning funnel.
- **Wording corrected:** the slow difference between position and integrated distance
  is not a steady drift. On the hero lap it wanders from −3.7 to +14.1 m (range 17.8 m)
  and changes by 11.8 m from start to end (the "~12 m" quoted before). The
  `fused_distance` docstring, learn/13 and the page now describe it this way.
- **Links:** the overview's "How it works" points to the Method page, and the README
  table shows it. Checked at 1440 px and 390 px (estimator chart and cleaning funnel
  re-laid out for phones).

---

## 2026-10-26 — Day 1 of the extension: 2026 locked in the code

- **Next phase planned:** H5 (does a driver's signature survive the 2026 new car
  generation?) plus a second H4 test with the 2026 team changes, planned on
  2023–2025 data, preregistered as Part C, then run once on 2026.
- **Before anything else, the 2026 season was frozen.** `check_not_frozen` now
  refuses each held-out season unless its own switch is set (2025: `FINAL_TEST`,
  2026: `FINAL_TEST_2026`). Checked first: no 2026 file in the OpenF1 cache, no 2026
  row in any cached session list, and no 2026 FastF1 folder.
- **Tests:** `test_2026_is_held_out_with_its_own_switch` (the 2025 switch must not
  open 2026) and `test_openf1_refuses_2026_before_any_download`; both fail on the
  previous code. 108 tests pass.

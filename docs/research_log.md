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

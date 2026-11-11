# Engineering notes

How the code is organised, the conventions it follows, how results flow into the
app and the documents, and the bugs that took real debugging. **Read the bug history
before "simplifying" anything**: each entry is a mistake that looked reasonable.

## Repository structure

```
src/apextrace/          the package
  data_loading.py       FastF1 wrappers, the 2025 guard, lap selection with reasons
  quality.py            sampling-interval checks, gaps, interpolated rows
  synthetic.py          synthetic corners with a known truth, sampled like the feed
  filters.py            moving average, EMA, Butterworth, zero-phase, frequency response
  resampling.py         irregular samples -> uniform grids, gap masks
  corners.py            braking-zone detection, corner windows, the fused window coordinate
  alignment.py          cross-correlation lag, parabolic peak
  events.py             brake onset, slowest point, throttle crossings (sub-sample)
  track.py              lap samples -> track coordinate
  openf1.py             the OpenF1 data source (lap table, car and position streams)
  features.py           the corner features per (driver, lap, corner)
  dataset.py            loading, cleaning rules, field-relative features
  stats.py              ICC, bootstrap, permutation tests, effect sizes, corrections
  identification.py     lap vectors, leave-one-session-out, baselines, metrics
  protocol.py           the identification protocol shared by development and the final test
  signatures.py         season signatures, distances, own-rank, sign test
  session_build.py      one session -> dataset rows
experiments/            numbered scripts 00-17; every number and figure comes from one of them
  14_final_2025.py      the one-time final test (run once; results/final/ is frozen)
  16_app_data.py        exports results/app/*.json for the web app
  17_write_docs.py      renders README.md and docs/report.md from docs/templates/*.j2
app/                    the web app (Flask + vanilla JavaScript + D3)
tests/                  pytest, on synthetic signals and tiny fixtures; never downloads F1 data
docs/                   report, preregistration, deviations, research log, decisions,
                        data report, related work, these notes
results/                small outputs (JSON, CSV, PNG); raw Parquet files are gitignored
```

## Conventions

- **Explicit, readable code:** plain loops over clever one-liners; every non-trivial
  function has a docstring that explains *why*, with a worked numeric example.
- **Tested before trusted:** every function is tested on a synthetic signal with a
  known answer before it touches real data, and the full path (sample -> filter ->
  align -> extract) is tested too. A new test is checked to **fail** on the broken
  version it guards against.
- **Numbers only from scripts:** README.md and docs/report.md are generated; edit
  `docs/templates/*.j2`, add any new number to `collect_numbers()` in
  `experiments/17_write_docs.py`, and re-run it. `tests/test_docs.py` fails if the
  documents are stale or edited by hand.
- **Hand-written documents are checked too:** `tests/test_design_numbers.py` rebuilds every
  number quoted in `docs/h5_design.md` from the results files. Every "k of n" and every
  interval in the file must come from a result. Hand-written statistics are
  cross-checked against SciPy in `tests/test_cross_checks.py`.
- **Events on raw samples:** smoothing is never applied before locating an event
  (filters shift or smear events; see the Method page and Phase 2).
- **No random splits** in identification: whole weekends are left out.
- **Held-out seasons are frozen in the code** (`data_loading.FROZEN_SEASONS`), each
  with its own switch: 2025 (`FINAL_TEST`, used once; never re-run `14_final_2025.py`
  into `results/final/`; a fix is re-run into a new folder and both results are
  reported) and 2026 (`FINAL_TEST_2026`, held out for preregistration Part C).
- **No raw data or media in the repository:** `*.parquet` and `cache/` are gitignored;
  no logos, photos, broadcast footage or team radio.

## The update loop

After changing an analysis: re-run its experiment script, then
`experiments/16_app_data.py` (app data), then `experiments/17_write_docs.py`
(README and report), then `pytest`, then a research-log entry.

Every few weeks, and before anything is shown to someone: `experiments/30_audit.py`. It
re-runs every development experiment with the network blocked (no output may change),
recomputes the three preregistered tests in memory from the saved data, checks lap counts
across files and the 2026 timeline, and runs the tests (which include the checks of the
hand-written documents). `--quick` skips the re-runs. Results: `results/30_audit/`.

After changing what a page shows: `experiments/31_screenshots.py` re-takes the five README
images the same way every time (Edge through Playwright, 1440 x 1000).

## Bug history

- **2026-10-15 — Don't judge "slow laps" against the driver's session best.**
  A 107 % rule against the session best (also what FastF1's `pick_quicklaps()` does)
  cut 6 of Norris's 7 medium long-run laps in 2024 Abu Dhabi FP2 but only 2 of
  Piastri's, only because his soft-tyre lap was 0.23 s quicker. Fix: 107 % of the best
  lap *of the same stint*, plus a "not a timed run" rule for whole stints (> 115 % of
  the driver's best). Guarded by `test_long_run_is_judged_against_its_own_stint` and
  `test_stint_that_was_never_a_timed_run_is_dropped`.
- **2026-10-17 — The minimum permutation p-value is 1/C for unequal groups, 2/C only
  for equal groups** (no mirror split otherwise). Found when a 3 vs 4 test gave
  p = 1/35, below the stated "minimum" 2/35. Guarded by
  `test_minimum_p_for_unequal_groups_has_no_mirror_split`.
- **2026-10-17 — OpenF1 lap table: don't use FastF1's "lap start = previous lap end
  (3 ms)" check, and give overlapping stint laps to the NEW stint.** OpenF1 lap starts
  are only accurate to ~0.1 s; with the check, about 3 of 4 push laps per driver were
  dropped. Guarded by the validation experiment (kept laps identical for 20 of 20
  drivers) and `test_overlapping_stints_give_the_shared_lap_to_the_new_stint`.
- **2026-10-18 — OpenF1 can have no laps for a whole session** (2025 Baku qualifying:
  `laps` returns 404 while stints, race control and drivers exist). `lap_table` grouped
  an empty table and the one-time final run crashed before any result. Fix: return an
  empty table; `build_session` skips the session ("no laps"). Guarded by
  `test_session_without_laps_is_skipped_not_crashed`. Lesson: before a one-time run,
  download everything first, then analyse.
- **2026-10-19 — Don't compute the time gap between two laps from projected position
  `s_m`.** It gave a ±0.1 s sawtooth and ended 0.08 s off the official gap (position
  scatter of ~3 m plus a lap-specific offset). Use integrated distance `d_m`: smooth
  (jitter 0.007 s instead of 0.041 s). Correction (2026-10-30, experiment 18): on that
  one lap pair it ended within 0.011 s of the official gap, but across 15,326 lap pairs
  the typical error at the line is about 0.06 s for BOTH coordinates (median 0.064 s
  from `d_m`, 0.061 s from `s_m`); `d_m`'s advantage is the smooth curve, not accuracy
  at the line. Charts use the fused coordinate `d + moving_average(s − d)`. Guarded by
  `test_gap_from_integrated_distance_beats_projected_position` and
  `test_compare_returns_both_laps_and_a_correct_gap`. The same mistake survived in the
  overview's live gap until 2026-10-20 (it read +0.05..+0.47 s instead of
  −0.06..+0.22 s); any new gap readout must use `d`.
- **2026-11-03 — When comparing a driver with a teammate's signature, leave both of
  them out of the spread used for the z-scores, and build both references on the
  weekends they shared.** Found while testing the H5 comparison
  (`signatures.own_vs_past_teammate`) on synthetic laps where the signature is ONLY the
  car (the answer must be a fair coin, 0.5):
  - Full-season references with a teammate who drove 5 of 12 weekends: 0.73 over
    1,500 drivers, 0.71–0.80 over six small seeds (the teammate's signature is
    noisier, so it sits farther away).
  - Shared weekends, but the pair inside the spread: 0.43 over 1,500 trials (5 standard
    errors low). The noisy teammate inflates the spread of the feature where it is
    farthest out, which shrinks the distance on exactly that feature.
  - Both fixes: 0.493 and 0.497.
  All four numbers are reproduced by `experiments/22_h5_null_check.py`
  (`results/22_h5_null_check/summary.json`).
  Guarded by `test_shared_weekends_and_leaving_the_pair_out_keep_the_coin_fair` (checked
  to fail on both broken versions) and
  `test_full_season_references_fake_a_yes_when_a_teammate_drove_few_weekends`. The
  frozen H4 results (2025) used the older full-reference spread and are not re-run;
  how much this moves the development numbers is measured in experiment 20.
- **2026-11-04 — Check the feed only inside the laps we measure.** The new feed check
  (`quality.feed_check`, for the one-time 2026 run) failed on the real 2023 and 2024 feed:
  26 % of throttle values were outside 0–100 and 26 % of brake values were neither 0 nor
  100. All of them were **104**, a "no value" marker the feed sends in the garage and pit
  lane (202,632 throttle samples in the first four 2024 sessions, none inside a kept lap).
  The helper had passed each driver's whole download span. `openf1.session_feed_tables`
  now returns one table per kept lap, and both seasons pass (throttle in range 0.9999,
  brake 0/100 for 0.9997–0.9999). Inside kept laps, 5 of 113,606 brake samples are 104;
  `brake > 0` counts them as "on".
- **2026-11-06 — Equal laps per shared weekend, not only equal weekends** (found by the
  fresh-eyes review of Part C). A weekend mean over fewer laps is noisier, and a driver out in
  Q1 has fewer laps than one in Q3. With the 2025 references on shared weekends but all laps,
  a car-only synthetic world where the driver who keeps the seat had 6 laps a weekend and the
  teammate 2 gave 0.734 "own closer" over 1,500 drivers instead of 0.5.
  `signatures.equal_laps_per_session` keeps, on each shared weekend, the smaller lap count for
  both drivers (each driver's first laps): 0.497. Guarded by
  `test_all_laps_fake_a_yes_when_the_driver_who_stays_had_more_laps` and
  `test_equal_laps_keep_the_coin_fair_when_the_driver_who_stays_had_more_laps` (checked to
  fail with the rule switched off); `experiments/22_h5_null_check.py` cases E and F.
- **2026-11-07 — The "no value" marker 104 also appears INSIDE laps in 2026.** In 2023–2025 it
  was 0.006–0.015 % of throttle samples inside kept laps; in 2026, 1.13 % of samples (8 % in
  Shanghai and Suzuka), which stopped the one-time run at its feed check (attempt 1, before
  any result). The features read throttle 104 as full throttle and brake 104 as "on".
  `openf1.drop_no_value_samples` (Addendum 1 to Part C) removes those samples in `slice_lap`
  and in the feed check. Guarded by `test_no_marker_reaches_the_features_through_slice_lap`
  (checked to fail with the rule removed).
- **2026-11-08 — SciPy's `binomtest(...).proportion_ci` follows the test's alternative.** With
  `alternative="greater"` (our one-sided sign test) it returns a one-sided interval (low, 1.0),
  not the two-sided exact (Clopper–Pearson) interval our summaries report. Found when the first
  version of `experiments/27_final_2026_figures.py` disagreed with all six frozen intervals. The
  interval comes from a separate `alternative="two-sided"` test object. Guarded by
  `test_every_frozen_block_matches_its_per_driver_table` (checked to fail with the one-sided interval).
- **2026-11-09 — OpenF1's "no rows" answers are not cached.** For a session with no laps
  (2026 Sakhir and Jeddah) OpenF1 answers 404, and `openf1.fetch` returns an empty list without
  writing a cache file. So a script that reads only the cache (network blocked) still tries to
  send a request for those sessions. `experiments/28_lost_laps_2026.py` skips the sessions that
  the frozen download log records with 0 laps.
- **2026-11-09 — Saved datasets have 3 decimals, so recomputing from them is close, not exact.**
  The one-time runs compute from full-precision features but save `dataset_*.csv.gz` with
  `float_format="%.3f"`. Recomputing H5 from the saved 2026 file gave the same 19 answers, with
  distances up to 0.00034 away from the frozen ones (which are saved to 4 decimals). A check that
  recomputes a frozen result from saved files must compare answers exactly and distances to about
  0.001, not to the 4th decimal. (Found while building experiment 28; relevant to the Day 17 audit.)
- **2026-11-09 — The pilot tests (06) recorded "the latest commit" of the preregistration
  file at run time.** Parts B and C were later committed to the same file, so re-running
  `experiments/06_pilot_stats.py` would have written a later commit over the Part A one
  (`ab2510c`) that the README and the report quote. Found while planning Audit I, before
  anything was re-run. 06 now refuses to run once its summary exists, like the two one-time
  scripts; the audit recomputes its tables in memory instead. Guarded by
  `tests/test_pilot_stats_guard.py`.
- **2026-11-09 — Two columns of `results/09_dataset/sessions.csv` can't be reproduced.**
  `seconds` is a stopwatch, and the note for 2023 Imola (a cancelled weekend) was written by the
  build of 2026-10-17, before the "session without laps" fix of 2026-10-18. The audit compares
  that file without those two columns and lists any note that differs; the data files of the
  build must match exactly.
- **2026-11-09 — Public files must not point to local-only files.** Audit I found 23 lines
  where a public file cited the local planning notes, the study notes or the private schedule
  (code comments, early log entries, and two lines written on Day 16). All were reworded;
  `tests/test_public_files.py` now fails on any new one, including a section number with no file
  name, and checks that every repository path in a public document exists.
- **2026-11-09 — A rule added for 2026 silently changed the rebuild of the development data.**
  Addendum 1 (2026-11-07) put the 104-marker removal into `openf1.slice_lap`, the code every
  build uses. The development dataset was built on 2026-10-17, without it. Audit I's first full
  run rebuilt it and got 24,465 usable rows instead of 24,496 (31 corner passes moved to "feed
  gap in window"), and 40 result files changed downstream. With the rule switched off, the
  rebuild matched the committed dataset exactly (same decompressed content). Fix:
  `openf1.DROP_NO_VALUE` (on by default) and `09_build_dataset.py` switches it off, so the
  development data stay reproducible; the rule's effect on them is measured by experiment 26.
  Lesson: a change to shared code must be checked against every dataset it rebuilds, not only
  the one it was written for. Guarded by `test_the_development_rebuild_can_switch_the_marker_rule_off`
  and by the audit's re-run check.
- **2026-11-10 — Lap compare: across a hole in the car data, integrated distance loses track.**
  Removing the 2026 "no value" samples left holes of up to 23 s in 120 of 1,764 laps (2023–2024:
  21 laps over 2 s, 2025: 9). Integrating speed across a hole misses the slow part of a corner:
  2026 Suzuka, ANT lap 14, a 10.3 s hole, 86 m lost, and the gap at the line read −1.63 s against
  the official +0.24 s. Fix in `app.data.compare`: if a lap has a hole longer than `HOLE_S` (2 s),
  the gap is computed on the position-corrected coordinate (+0.37 s here), and no gap is shown
  within 200 m of a hole (`hole_spans`: half the fusion window, where that coordinate can't
  re-anchor yet); those mini-sectors say "no data". Lines are not drawn across a hole, and the
  default pair uses each driver's fastest lap without one. Laps without holes keep the
  validated gap on integrated distance. Guarded by
  `test_a_hole_breaks_the_gap_from_integrated_distance_and_the_fallback_repairs_it` (fails with
  the fallback switched off) and `test_hole_spans_worked_example`.
- **2026-11-10 — The public-files test flagged itself once it was committed.**
  `tests/test_public_files.py` must name the local-only files to look for them. While
  untracked it wasn't scanned; committed (`48c167a`), it failed on its own text, so CI on that
  commit fails. It now skips itself, like `.gitignore`.

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

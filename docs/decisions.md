# Decisions

One entry per decision: the date, what we chose, and why. Add new entries at
the bottom. Decisions made before this repo existed (the project direction,
the pilot, the corrections to the first plan) are in PROJECT_CONTEXT §4.

---

## 2026-10-14 — Working solo
Sadman works on ApexTrace alone. Consequence: no `CONTRACTS.md` and no module
split between people. If a faculty member or collaborator joins later, agree
on authorship early (PROJECT_CONTEXT §12.8).

## 2026-10-14 — Names: repo ApexTrace, package `apextrace`
The Python package is `apextrace` (the original plan said `f1sig`).
**Why:** code that matches the repo name is easier to find and explain.

## 2026-10-14 — 2025 season = frozen final test set
Confirmed. Develop everything on 2023–2024. Write `docs/preregistration.md`
and commit it **before** any 2025 session is loaded. Then run the final
H3/H4 evaluation on 2025 once.
**Why:** if we look at the test data while developing, we will (without
meaning to) tune the method to it, and the final numbers will look better
than they really are.
**Open issue (decide in Phase 6):** every planned team changer (Hamilton,
Sainz, Ocon, Hülkenberg, Lawson ↔ Tsunoda) changed teams *for 2025*, so the
H4 method can't be developed on them. Options: develop H4 on a "same driver,
same car, new year" check (2023 → 2024), or add the 2022 season to get
earlier team changers.

## 2026-10-14 — Python 3.13 + FastF1 3.8.3
FastF1 3.8.3 installed and imported without problems on Python 3.13.2, so we
stay on 3.13 (no need for 3.12). Exact versions of everything are pinned in
`requirements.txt` (made with `pip freeze`).

## 2026-10-14 — Package layout: `src/` + `pyproject.toml` + editable install
Code lives in `src/apextrace/`, installed with `pip install -e .`.
**Why:** `import apextrace` then works from `experiments/`, `tests/` and
`notebooks/` without editing `sys.path`, and code edits take effect without
reinstalling. The `src/` folder means tests always use the installed
package, never a stray copy. `pyproject.toml` lists the libraries we need;
`requirements.txt` records the exact versions we used.

## 2026-10-14 — CLAUDE.md split
`CLAUDE.md` (loaded in every Claude session) was cut from ~950 to under 250
lines. The long reference parts moved word for word to
`docs/PROJECT_CONTEXT.md`, which **keeps the original section numbers**, so
"§9.7" still means the same thing everywhere. The chat reply that had been
pasted by accident at the end of the file was deleted.

## 2026-10-15 — Lap selection rules (`select_laps`)
A lap is kept only if it has a lap time, is not an out lap or in lap, was not
deleted, ran under green flag only (track status `1`), and passed FastF1's
timing check (`IsAccurate`). Then two pace rules:
- **Slow lap:** slower than **107 % of the best clean lap of its own stint**
  (one set of tyres). Removes cool-down laps.
- **Not a timed run:** the stint's best lap is slower than **115 % of the
  driver's best clean lap** of the session. Removes runs that were never
  timed, such as practice starts at the end of FP2.

Every dropped lap is logged with its reason(s).
**Why per stint, not per session:** with the session best as reference, the
107 % rule cut 6 of Norris's 7 FP2 long-run laps but only 2 of Piastri's,
only because his soft-tyre lap was quicker (details in the research log of
2026-10-15). **Why 115 %:** in 2024 Abu Dhabi FP2, long runs were 106–109 %
of the driver's best and end-of-session runs 130–141 %; 115 % sits in that gap.
Re-check this gap when more sessions are loaded (Phase 6).
**Consequence:** we don't use FastF1's `pick_quicklaps()`, which compares
with the session best. In qualifying it keeps the same laps as our rules.

## 2026-10-15 — 2025 guard in code
`load_session()` refuses any 2025 session unless the environment variable
`FINAL_TEST=1` is set. It was added now rather than in Phase 6, because one
accidental look at 2025 can't be undone.

## 2026-10-16 — The three pilot corners: T6, T5, T9
Chosen by a fixed rule on Norris's pole lap, before any driver comparison
(`check_10_choose_corners` in `experiments/01_data_pilot.py`; table in
`results/01_data_pilot/corner_choice.csv`). Candidates must have a real
braking zone (speed drop ≥ 50 km/h, the minimum a true dip within ±100 m of
the marker) and a window [−300 m, +200 m] inside the lap. Then:
- **Heavy braking = biggest speed drop → T6** (324 → 68 km/h, end of the
  1.2 km back straight; T6/T7 is a chicane with one slowest point).
- **Fast = highest minimum speed → T9** (320 → 181 km/h).
- **Medium = minimum speed closest to halfway (124.5 km/h) → T5** (294 → 108 km/h).

Honest limits: Yas Marina has no braking corner with a minimum speed above
200 km/h, so "fast" means the fastest braking corner. T16 (138 km/h) was
excluded because its window crosses the finish line.

## 2026-10-16 — Feed gaps inside a corner window: drop the (lap, corner) pair
If a car-data gap longer than 0.6 s falls inside a corner's window, that lap
is not used *at that corner* (it can still be used at the other corners).
Every exclusion is logged. **Why:** across a 1 s gap at 300 km/h there are
~80 m with no data, so a braking point inside it can't be located (example:
PIA's Q1 lap goes from 295 to 139 km/h across one gap in the T6 braking zone).
**Consequence:** in qualifying, PIA has only 2 usable laps at T6 (NOR 4);
at T5 both have 4; at T9 NOR 3, PIA 4.

## 2026-10-16 — Only main qualifying ("Q") for Phase 6, not sprint qualifying
Sprint qualifying has different tyre rules and a different session format.
One kind of session keeps the comparison clean. Can be revisited if more
data is needed.

## 2026-10-16 — Which estimator for each feature (from the Phase 2 Monte Carlo)
Chosen from `results/03_synthetic_errors/error_table.csv` (1,000 synthetic laps
per corner type, real feed sampling, no feed gap in the window):

| Feature | Estimator | Error (heavy braking) |
|---|---|---|
| Brake onset | speed breakpoint inside the brake off→on interval | bias +3.2 m, std 2.7 m |
| Apex position, minimum speed | parabola through the 3 lowest samples | ~1 m; bias +0.03, std 0.35 km/h |
| Throttle pickup (10 %), full throttle (99 %) | interpolated crossing | pickup bias −0.9 m, std 1.0 m |
| Entry and exit speed | linear interpolation at a fixed point | std 0.24 km/h |

**Peak deceleration is dropped as a feature.** Every estimator reads it far too
low (−6 to −20 m/s² against a true ~57 m/s²), because the true peak is too short
to survive ~4 samples per second, and smoothing makes it worse. Instead we use
**mean deceleration** between brake onset and apex, built from two
well-measured events.

The +3 m bias of the brake breakpoint comes from the brake-pressure build-up
(the synthetic ramp is 0.05–0.25 s). It is the same for both drivers if they
build pressure equally fast, so it cancels in teammate differences. If they
don't, that is a real difference in braking style, which this data can't
separate from the bias. This is stated as a limitation.

## 2026-10-16 — No smoothing when locating events; 1 Hz for drawing deceleration
Smoothing smears sharp events: a zero-phase filter has no delay, but it moves
a braking-*onset* detector 23–36 m early (`results/02_group_delay`). So events
are located on the raw samples with the estimators above. Deceleration traces
for figures are smoothed zero-phase at **1 Hz**, just below the 1.19 Hz knee
where the real speed spectrum flattens into noise.

## 2026-10-16 — Track coordinate: X/Y projection, fused with integrated speed per corner
- **Reference path:** the X/Y path of Norris's pole lap (Q lap 15), s = 0 at the
  timing line, length 5,230.9 m. Every lap's position samples are projected onto
  it (`alignment.project_onto_path`, with a ±200 m search around the expected
  position so no point snaps to another part of the track).
- **Why not X/Y alone:** each projected position has ~3 m of noise *along* the
  track (X/Y increments vs integrated speed: 4.5 m std per ~0.26 s interval).
  The noise grows with longer intervals (r ≈ −0.4) and there is no constant
  lag between streams (≤ 0.06 s), which suggests position-timestamp jitter
  of ~40 ms. This is a hypothesis.
- **Why not integrated speed alone:** it drifts (d − s at T9 in Q: std 4.8 m)
  and jumps at feed gaps.
- **Decision: complementary fusion per corner window**
  (`corners.fuse_window_coordinate`): fused(t) = d(t) + one offset per window,
  the 1/speed²-weighted mean of (s − d) over the window's ~37 position
  samples. Measured offset noise (half-split check, 75 lap-corner pairs):
  **1.15 m** (1.46 m without weighting). This alignment error adds to each
  event's estimator error.
- **Checked:** the sampling phase at fixed track points is uniform (480
  phases, KS p = 0.43), so averaging laps does shrink errors like 1/√N.
- Cross-correlation is used only over whole laps as a diagnostic, never per
  corner: per-corner alignment on the speed trace would absorb the braking
  differences we want to measure.

## 2026-10-16 — Phase 6 data source: OpenF1 (the F1 live-timing archive now refuses access)
On 2026-10-16, `livetiming.formula1.com/static/...` answered **401 Unauthorized**
for every file (2023 and 2024), and FastF1's mirror answered 404. FastF1 3.8.3
(the latest release) can therefore not download any session that isn't already
cached. Its F1 TV login covers only the live client. The 2024 Abu Dhabi
sessions still work because they were cached on 2026-10-14/15.
**Checked:** OpenF1 (`api.openf1.org`) serves the same raw feed. For Norris's
pole lap, all 320 car samples matched the cached FastF1 data within 1 ms, with
identical speed, throttle, gear and RPM (brake 0/100 instead of False/True),
and all 323 position samples had identical X/Y. So every Phase 1–3 result
applies unchanged.
**Decision:** Phase 6 (2023–2024 qualifying, all teams) uses OpenF1 through an
adapter that rebuilds the lap table: track status from race-control flags,
deleted laps from race-control messages, and a timing check from sector sums.
The adapter is validated by re-computing the Abu Dhabi pilot features and
comparing them with the FastF1-based ones.

## 2026-10-17 — OpenF1 adapter validated; two adaptations of FastF1's rules
`src/apextrace/openf1.py` rebuilds FastF1's lap table from OpenF1. Validated on
2024 Abu Dhabi Q and FP2, all 20 drivers (`results/07_openf1_validation/`):
**the kept laps are identical for 20 of 20 drivers in both sessions**, and the
75 pilot (lap, corner) features match FastF1's within 0.23 m (brake onset),
0.10 m (apex) and 0.004 km/h (minimum speed). Two rules had to change:
- **Timing check:** FastF1's 4th check (a lap starts where the previous one
  ended, within 3 ms) is dropped for OpenF1. OpenF1's lap start times are
  accurate only to ~0.05–0.15 s, and for out laps they mark the pit exit, so the
  check failed almost every push lap. Checks 1–3 are kept. Result: the timing
  check agrees with FastF1 on 100 % of qualifying laps and 95.5 % of FP2 laps.
- **Stints:** OpenF1 stints overlap by one lap (the out lap of the new stint
  is also listed as the last lap of the old one); the later stint wins, as
  in FastF1.
Known small difference: tyre age agrees on 97.7 % of qualifying laps but only
61 % of FP2 laps (FastF1 seems to count used tyres differently). Lap
selection doesn't use tyre age.

## 2026-10-17 — Which braking event, apex and throttle belong to a corner (for any track)
On other tracks a corner window [−300 m, +200 m] can contain two braking zones
(chicanes, a previous corner). `features.corner_features` now chooses:
- **Apex:** the slowest sample within ±80 m of the corner reference, refined
  with a parabola.
- **Brake onset:** the braking *event* that leads into that apex
  (`events.braking_event`). Brake-on runs separated by a gap in which the
  throttle never reaches 10 % count as one event. Why: in Norris's 2024 Abu
  Dhabi FP2 long runs the brake channel switches off for 1–4 samples
  (0.44–1.32 s) in the middle of braking zones; a plain "last brake-on before
  the apex" rule then moved the onset by up to 153 m. Two different braking
  zones always have the throttle opened between them.
- **Throttle pickup / full throttle:** searched from the end of that braking
  event to the start of the next one.
Regression check: the 90 pilot feature rows are identical to before the change.

## 2026-10-17 — Corners for multi-track data: detected automatically
OpenF1 has no corner list. `corners.detect_braking_corners` finds them on each
session's reference lap (its fastest kept lap): the slowest point within
±100 m, a speed drop of at least 50 km/h from the fastest point in the 500 m
before, and a window [−300, +200] m that fits inside the lap. The corner's
reference point is the dip itself (the apex on the reference lap), unlike the
pilot, which used FastF1's corner markers. Corner type by minimum speed:
**slow < 120 km/h, medium 120–200 km/h, fast ≥ 200 km/h**. Corner identities
(C1, C2, …) are per track; only the types are comparable across tracks.

## 2026-10-17 — OpenF1 downloads: one request per driver per session, paced
OpenF1 allows ~30 requests per minute. Per-lap requests (~160 per session)
ran into 429 "Too Many Requests". Now: one car-data and one position request
per driver, covering all of their kept laps (~44 requests per session), sent
at most every 2.1 s, cached gzip-compressed.

## 2026-10-17 — Cleaning rules for the multi-season dataset (decided in the EDA, before any modelling)
`apextrace.dataset.clean`, used by every later analysis:
1. **Dry laps only** (SOFT/MEDIUM/HARD): 2,997 intermediate/wet rows dropped
   (two sessions were wet throughout). Wet driving is a different regime.
2. **Minimum speed < 40 km/h = broken data:** 6 rows dropped (e.g. a lap whose
   speed integrated to zero distance, 2023 Jeddah).
3. **Other values outside physical limits become missing** for that row only:
   brake onset outside [−400, 0] m (111 rows; braking "after the apex
   reference" means the wrong braking event was matched in a corner
   sequence), mean deceleration outside [3, 60] m/s² (232), apex beyond
   ±80 m (130, flat-bottomed fast corners), throttle pickup outside
   [−200, 200] m (126, corners taken without closing the throttle).
   Braking distance and mean deceleration follow the brake onset.
Result: **21,493 clean rows, 44 sessions**. The rules were fixed on the
evidence of `results/10_eda/outliers.csv`, before looking at any driver
comparison or model.

## 2026-10-17 — Identification protocol (H3, development on 2023–2024)
- Unit: one lap; features = the lap's mean field-relative value per corner type
  (`identification.lap_vectors`, 30 columns).
- Split: leave-one-session-out; imputer, scaler and model fitted on training
  sessions only (scikit-learn pipelines). Field-relative values use the
  held-out session's own median, which needs no labels.
- Task (a), main evidence: each team-season's two drivers with the most laps,
  sessions where both have laps, at least 5 sessions (20 team-seasons).
  Task (b): all drivers of a season with laps in ≥ 5 sessions (confounded by the car).
- Baselines: majority, lap time only, raw lap statistics; models: logistic
  regression (class-balanced), nearest centroid. Checks: shuffled labels within
  sessions (5×), ablation by feature group, weekend vote.
- Comparison across team-seasons: Wilcoxon signed-rank test on paired balanced
  accuracies; 95 % bootstrap intervals over team-seasons.

## 2026-10-17 — H4 development can't use team changers from 2023–2024
OpenF1 has data from 2023 only (the F1 archive needed for 2022 returns 401),
and no regular driver changed teams between 2023 and 2024 (the AlphaTauri →
RB change is a rename; stand-ins have too few laps). So the H4 method is
developed on "same driver, same car, new year" (is a driver's 2024 signature
closest to their own 2023 one?), and the real team-change test (Hamilton,
Sainz, Ocon, Hülkenberg, Lawson ↔ Tsunoda) runs once on 2025, after
preregistration Part B is committed.

## 2026-10-18 — Shared code for the final run; H4 design
- The pieces used by both development and the final 2025 run were moved into
  the package so that the final run uses exactly the development code:
  `session_build.py` (from `09_build_dataset.py`), `openf1.download_session`
  (from `08_download_openf1.py`), `protocol.py` (from `12_identification.py`),
  `identification.build_lap_table`. Regression checks: the identification
  summary and the lap table are identical; the 2023–24 dataset rebuild is
  compared below.
- **H4 primary comparison:** a changer's 2025 signature vs (a) their own 2024
  signature (another car) and (b) their new teammate's 2025 signature (the same
  car, the same season); one-sided sign test over the five changers (Hamilton,
  Sainz, Ocon, Hülkenberg, Tsunoda). Details and power: `docs/preregistration.md`,
  Part B. **Why the new teammate:** the cleanest "car" reference is the other
  driver of the same car in the same season; the development analogue (own
  2023 vs the 2023 teammate, same car) gave 17 of 20.
- `experiments/14_final_2025.py` was dry-run on development data (2024 as the
  "final" year, 2023 as reference) to exercise every code path before the
  one-time run.

## 2026-10-18 — Final run: rerun after a crash, exploratory follow-ups
- **Rerun after a crash before any result.** Attempt 1 stopped in the download
  step (2025 Baku has no laps on OpenF1). The fix was forced (skip a session
  without laps; `build_session` already had that branch) and was recorded in
  the deviations file before the rerun. The empty `results/final/` folder was
  removed to pass the run-once guard; the guard itself was not changed.
- **Download first, then run.** Before attempt 2 the remaining sessions were
  downloaded into the cache (download step only, no analysis), so that any
  other data-source problem would show up there and not as a third attempt.
- **Primary results are never touched afterwards.** Everything added after the
  run is in `experiments/15_final_exploratory.py` /
  `results/15_final_exploratory/`, labelled exploratory: the missed changer
  (COL), and a control that runs the H4 comparison on drivers who stayed.
  **Why the control:** H4 compares "own signature one year apart" with
  "teammate, same season and same weekends", which is not symmetric. The
  control shows how often the own signature wins when the car stays the same
  (8 of 10), so the changers' 2 of 5 can be read against it.

## 2026-10-19 — Web app (Phase 8)
- **Stack:** Flask + vanilla JavaScript + D3 (Sadman's choice; he knows Flask and
  vanilla JS from Consonance). D3 7.9.0 and the Barlow fonts are stored in
  `app/static/` (with licences), so the app runs offline.
- **Data:** the app shows only exported results (`experiments/16_app_data.py` →
  `results/app/*.json`, committed, ~1 MB) plus raw laps read on demand from the
  gitignored Parquet files (~40 ms per lap, no cache needed).
- **Design rules:** timing-screen look (dark, condensed capitals, hairlines),
  one red interface accent, team colours only for drivers, purple = session best,
  second driver of the same team = lighter shade + dashed, chamfered corners,
  imagery only from telemetry; no logos, photos or official fonts; head-shot
  URLs from OpenF1 are not exported.
- **Gap curve on integrated distance, charts on the fused coordinate** (measured;
  see the research log). Mini-sectors with |gain| < 0.02 s are "even"
  (alignment error 1.15 m ≈ 0.017 s at 250 km/h).
- **Corner lab and Driver vs car (2026-10-19):** dot plots ("timing tower") rather
  than box plots, so every lap stays visible (4–6 laps per driver is too few for
  a box). The per-lap measurement error is drawn on the axis, so differences can
  be judged against it. Driver vs car chart colours: blue `#3987e5` = corner
  features / drivers who stayed, orange `#d95926` = raw statistics / team
  changers, grey ring = lap-time baseline; shapes differ too. Heat strip:
  blue–grey–red diverging, clamped at ±2 SD. Signatures are exported only if
  they reproduce the frozen H4 distances.

## 2026-10-19 — Documents generated from results; CI
- **README.md and docs/report.md are generated** from Jinja2 templates by
  `experiments/17_write_docs.py`, so the rule "numbers only from scripts" holds
  mechanically, not by care. A test fails if they are stale or edited by hand.
- **CI on GitHub Actions** runs the tests on Python 3.13 with the pinned
  requirements. The tests need no F1 data (synthetic signals, fake results
  folders, committed result files).
- **Citations:** only works whose details were verified are cited in the report.

## 2026-10-25 — What is public
- **Public:** the code, the results, the report and README, the preregistration and
  its deviations, the research log, the decisions, the data report, related work, and
  the new `docs/engineering_notes.md` (structure, conventions, update loop and the full
  bug history, moved out of a local working file so that reviewers can see it).
- **Local only:** the AI working notes and the personal study guide (chapters, viva
  practice, CV and email drafts). Public files no longer point to them.

## 2026-10-26 — 2026 is the next held-out season
- **2026 is frozen in the code** before anything about it was looked at:
  `data_loading.FROZEN_SEASONS = {2025: "FINAL_TEST", 2026: "FINAL_TEST_2026"}`.
  Each season has its own switch, so the 2025 switch can't open 2026 by accident.
  Checked first: the local cache holds no 2026 data at all.
- **Why 2026:** the 2026 regulations introduced a new car generation, which allows
  a new question (H5: does a driver's signature survive a new car?) and a second,
  independent test of H4 with the 2026 team changes. It will be planned on
  2023–2025 data, preregistered as Part C, committed, and then run once.
- **2025 becomes development data for these new questions.** Its final test
  (H3/H4) is done and frozen in `results/final/`; the saved 2025 dataset may now
  be used to develop H5, the way 2023–2024 were used for H3/H4. The 2025 download
  guard stays in place.

## 2026-10-29 — Position-offset check: design fixed BEFORE running it
The open question (research log, 2026-10-19): does projected position carry a
lap-specific offset of a few metres? Measured with `quality.start_offset` (median of
position − integrated distance over the first 300 m after the line; single-lap noise
0.8–1.0 m on synthetic laps; drift bias about −0.4 m at 0.25 % drift). The experiment
(`experiments/18_position_offset.py`, 2023–2025 kept laps, development data only)
answers four questions with rules written down now:
1. **Do laps carry offsets beyond the noise?** Yes if the median within-session
   standard deviation of the per-lap offset is more than twice the synthetic noise floor.
2. **Whose offset is it?** Split the variance into between sessions, between drivers
   within a session, and between laps of the same driver and session.
3. **Does it explain the gap error at the line?** For pairs of laps of the same driver
   and session: correlation between (gap at the line from projected position − official
   lap-time gap) and the difference of the two laps' offsets.
4. **Does it leak into the corner features?** Slope of the lap's position-feature
   residuals (brake onset, slowest point, throttle pickup, each minus the
   driver-session-corner median) against the lap's offset. A slope near +1 means the
   offset passes straight into the features.
**Consequence fixed in advance:** if (1) holds and the slope in (4) is above 0.5, a
per-lap offset correction becomes a preregistered *secondary* feature variant for the
2026 test (Part C); the frozen 2023–2025 results are not changed.

## 2026-10-30 — Position-offset check: outcome
Run as designed the day before (`experiments/18_position_offset.py`). Q1 holds (the
offsets are real), but Q4's pooled slope is 0.006, far below 0.5, so by the rule fixed
in advance **no offset correction is added for 2026** and the frozen results stand. The
offsets explain the line-gap error of projected position (Q3) but not the corner
features. An exploratory check of a lap-start-timing explanation was inconclusive; the
cause stays open. A claim made on 2026-10-19 from one lap pair ("integrated distance
ends within ~0.01 s of the official gap") was corrected everywhere: the typical error
at the line is about 0.06 s for both coordinates.

## 2026-10-31 — What we may read about 2026 before Part C is committed
Rule texts (FIA Sections B and C, the FIA's 2024 announcement) and data-source
documentation only. No 2026 session data, results, lap times or telemetry analyses
until preregistration Part C is committed, so the H5 plan can't be shaped by what 2026
looked like. Where an explainer and the FIA text disagree, the FIA text wins (one
explainer calls the active-wing switch automatic; B7.1.1(c) says the driver commands
it). Every rule number cites its issue, because the rules changed between the 2024
announcement and Issue 17 (April 2026). The notes are in `docs/regulations_2026.md`.

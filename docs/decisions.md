# Decisions

One entry per decision: the date, what we chose, and why. Add new entries at
the bottom. Decisions made before this repo existed (the project direction,
the pilot, the corrections to the first plan) are in the author's planning notes, which
are not part of the repository.

---

## 2026-10-14 — Working solo
Sadman works on ApexTrace alone. Consequence: no `CONTRACTS.md` and no module
split between people. If a faculty member or collaborator joins later, agree
on authorship early.

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

## 2026-10-14 — Working notes split
The AI assistant's working file (loaded in every session) was cut from ~950 to
under 250 lines. The long reference parts moved word for word to a planning file,
which **keeps the original section numbers**, so "§9.7" still means the same thing
everywhere. (Both are local working notes, not in the repository since 2026-10-25.) The chat reply that had been
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

## 2026-11-01 — Licences: MIT for the code, CC BY-NC-SA 4.0 for derived data
- **Code and documentation: MIT** (`LICENSE`). The simplest common permissive licence,
  the same as FastF1's, so anyone (a supervisor, another student) can reuse the code.
- **Derived data and figures (`results/`, `docs/images/`): CC BY-NC-SA 4.0**
  (`results/LICENSE.md`). OpenF1 publishes its data under this licence, for
  "educational purposes, personal learning projects, research, and non-commercial fan
  engagement" (openf1.org, checked 2026-11-01). Its "ShareAlike" term asks that
  adaptations carry the same licence, and the committed feature tables are built from
  OpenF1 data, so they follow it. This is the cautious reading; the notice also says the
  author doesn't own the underlying timing data.
- **Citation:** `CITATION.cff` (validated with cffconvert 2.0.0 against schema 1.2.0).
- The licence is the copyright holder's choice: Sadman confirms it by committing.

## 2026-11-02 — H5 design (becomes preregistration Part C)
Full design: `docs/h5_design.md`. The choices, all made on development data:
- **Primary comparison:** a driver's 2026 signature vs their own 2025 signature and
  their 2025 teammate's (both made in the same car). One-sided sign test, p < 0.05.
  Drivers who changed team for 2026 are included. Why not Part B's comparison (own past
  vs the new teammate on the same weekends)? It is lopsided towards the teammate. Here
  both references are a year earlier in the same car, so the null hypothesis is a fair
  coin.
- **Both 2025 references are built on the weekends the two teammates shared**, so a
  teammate with fewer weekends (a noisier signature) can't make the driver's own past
  look closer for no reason.
- **Everything 2026 does to a whole team** (new car, energy plan, throttle meaning,
  corner types) shifts the target equally against both references: it can only
  dilute, not create, a "yes". So the primary keeps all 30 features and the unchanged
  corner-type rule; the feature split and the version without throttle are secondary.
- **Sign test, not a test on distance sizes:** simple, assumption-free, and comparable
  with the 17 of 20 and 10 of 11 baselines.
- **Power stated in advance** (`experiments/19_h5_power.py`): with 14–20 drivers the test
  finds a signature that survives as well as without a rule change (q ≈ 0.85) 85–96 % of
  the time, but a weakened one (q ≈ 0.7) only 36–53 % of the time. A "no" can't tell
  "weakened" from "gone".
- **The secondary H4 on 2026 changers** gets its changers from team names by a fixed map,
  not from a hand-typed list (the Colapinto lesson). The stayer control is preregistered
  this time.
- **Coasting check rule fixed before running:** if brake-onset error with a coasting phase
  is above 8.4 m (2 × 4.2 m), add a secondary variant without the braking features.

## 2026-11-03 — H5: the z-score spread leaves the pair out; secondary versions stay secondary
- **Changed in the H5 procedure:** the spread used for the z-scores comes from the OTHER
  drivers' reference signatures, not all of them. With the pair inside, a noisy
  part-season teammate inflates the spread where it differs most and looks closer than
  it is: 0.43 instead of 0.5 on car-only synthetic laps (1,500 drivers). Found by the
  synthetic tests before any real data was run through the new function.
- **Primary unchanged otherwise** (all 30 features, sign test). On development data the
  12-column groups are weaker than all 30 (control points 0.75 and 0.75; energy-sensitive
  0.70 and 0.69; all 30: 0.80 and 0.94), so splitting the primary would cost power.
- **Secondary versions kept as planned:** feature groups side by side (no test of the
  difference), and no-throttle (17 of 20 and 15 of 16: nothing lost without throttle).
- The frozen H4 results used the older spread and are not re-run. The H4 development
  number under the H5 rules is 16 of 20 (it was 17 of 20).

## 2026-11-04 — Coasting check: scenarios fixed BEFORE running
The rule was fixed on 2026-11-02 (`docs/h5_design.md` §4). The chosen brake-onset estimator
(speed breakpoint inside the brake off→on interval) is checked on synthetic corners where
the car is already slowing before the brake goes on. If its root-mean-square error stays at or
below 8.4 m (twice Phase 2's 4.2 m), nothing changes. If it is larger, Part C adds a
secondary variant without the three braking features (brake onset, braking distance, mean
deceleration). The primary test stays the same either way.
- **The rule is applied to every corner type and every scenario.** Any one above 8.4 m is
  enough to add the variant. Phase 2 errors: heavy braking 4.2 m, medium 3.4 m, fast 4.2 m.
  For scale, guessing the middle of the off→on interval (no speed information) gave 6.9–7.7 m.
- **Scenarios:** 1,000 corners per corner type each, with real-feed sampling and no gaps,
  exactly as in Phase 2:
  1. the Phase 2 car, no pre-braking phase (must reproduce Phase 2: a pipeline check);
  2. lift and coast: throttle closed, brake off, for 0.3–1.0 s before braking, with the
     motor harvesting 0–350 kW (C5.2.7 allows 350 kW);
  3. superclipping: full throttle for 0.5–2.0 s before braking, with a 400 kW engine minus
     100–350 kW harvested by the motor;
  4. a 2026-like car: downforce × 0.7, drag × 0.45 (the FIA's −30 % / −55 % targets), and
     no pre-braking phase;
  5. and 6. the 2026-like car with lift and coast, and with superclipping.
  Mass for the harvesting deceleration: 770 kg (FIA 2024: 768 kg).
- These are rough physics, chosen to be in the right range, not a 2026 car model. The
  question is only whether the estimator still works when the speed is already falling.

## 2026-11-04 — Coasting check: outcome, and how numbers are verified from now on
- **Outcome** (`experiments/21_coasting_check.py`, rule and scenarios fixed beforehand): the
  worst brake-onset error is 4.89 m, under the 8.4 m threshold, so **no variant without the
  braking features is added**. Caveat for the write-up: coasting moves the estimator's
  bias by 3.9–4.7 m (late → early), so a difference in coasting between teammates would
  look like a brake-onset difference.
- **Verification, from today:**
  - Hand-written documents that quote results are checked by tests:
    `tests/test_design_numbers.py` for `docs/h5_design.md`. Every "k of n" and every
    interval in the file must come from a results file, which also catches a mistyped
    copy of a number quoted more than once.
  - Statistics are cross-checked against SciPy or a second implementation
    (`tests/test_cross_checks.py`).
  - Every research-log entry ends with a "Verified" list.
  - Part C will be generated from a template like the report, and reviewed with fresh
    eyes before Sadman commits it.

## 2026-11-05 — The one-time 2026 script: what goes into Part C
Built on 2026-11-04/05 (`experiments/23_final_2026.py`, `apextrace/h5_protocol.py`,
`teams.py`, `quality.feed_check`), tested, and rehearsed on 2024 and 2025. To be written
into Part C:
- **Guards:** `FINAL_TEST_2026=1`; Part C written (no placeholder), committed and unchanged;
  the script and `src/apextrace/` committed and unchanged, so the code that runs is the code
  that was committed with the plan (new compared with 2025); `results/final_2026/summary.json`
  must not exist. An attempt that stops early leaves a folder without a summary, and the
  script then refuses until the attempt is recorded in the deviations file and the folder
  renamed.
- **Sessions:** every 2026 main qualifying session that ended at least 24 h before the run.
  A session whose download fails is listed and skipped.
- **Order:** download everything → checks → build → analyse (the Baku lesson).
- **Checks before any feature:**
  - the feed (`quality.feed_check` on samples inside kept laps: channels, ≤ 1 % empty,
    values in range with brake 0/100, median interval 0.20–0.28 s, ≥ 95 % on the 40 ms
    clock, 3.3–4.3 samples/s);
  - every team name known to `teams.LINEAGE_PATTERNS`.
  Either failing → stop with no result, and a deviation is logged before anything else.
- **Team changers** from the data (`teams.team_changers`: most-weekends team, ≥ 5 weekends
  in both seasons).
- **H4 on changers:** Part B's comparison with the pair left out of the z-score spread. On
  2025 this changes no verdict. With Part B's spread the code reproduces the frozen distances.

## 2026-11-06 — Part C written; what the fresh-eyes review changed
Part C is generated from `docs/templates/preregistration_part_c.md.j2` by `17_write_docs.py`.
Every result number in it comes from a results file, and every rule value from the code. Once
Part C is committed, the generator refuses to rewrite it. A separate reviewer with no shared
context read the draft, the design and the code, and listed 9 groups of findings. I checked each
one myself before acting on it:
- **Equal laps per shared weekend** (the most important). Sharing weekends equalised the noise
  of the two references, but not the laps within a weekend: a driver out in Q1 has fewer laps
  than one in Q3. The teammate who keeps a seat tends to have more, so their own past looks
  closer for no real reason. Measured in a car-only world, 6 against 2 laps: all laps gave
  0.73 "own closer", equal laps 0.50 (`22_h5_null_check.py`, cases E and F). The rule: on each
  shared weekend, both references use the smaller lap count, each driver's first laps of the
  session. Development numbers re-run: 2023 → 2024 still 16 of 20; 2024 → 2025 14 of 16
  (it was 15).
- **Dependence between drivers.** Two 2025 teammates are compared against the same two
  references. Measured (case G): pairs split one-and-one 71 % of the time; 0.7 % false
  positives in 300 car-only studies. So the H5 sign test is conservative. For H4, two
  changers in the same new team make their outcomes alike, so its p-value is too small.
  This is a caveat; H4 is secondary.
- **Guards:**
  - The code and pinned files must be identical to the commit that added Part C.
  - The 2025 reference files are pinned by SHA-256 (`24_dry_run_checks.py`); the raw samples
    are not in git.
  - Any `final_2026*/summary.json` blocks a run, so renaming a folder doesn't help.
  - Results are written only at the end; a folder with any result file counts as a run.
- **Fixed session cutoff, 2026-11-06 00:00 UTC**, instead of "24 h before the run", so the day
  of the run can't change the sessions. Failed downloads are retried twice, then the run stops
  (it no longer silently skips a session).
- **Smaller fixes:**
  - The team map stops on an ambiguous or missing name ("McLaren Mercedes" used to become
    Mercedes).
  - Tyre labels are checked, so a new label can't silently drop every lap.
  - H5 has three verdicts (supported, not supported, not testable), and no longer crashes
    when nobody is eligible.
  - H4 groups 2026 teams by lineage.
  - Corner-type counts are reported.
  - The addendum allowed after a failed check is limited to what that check is about.
  - The "own rank" secondary analysis was dropped: it was never built, and the sign test
    already covers it.
- **Not done, with reasons:**
  - a "paired-only" sensitivity count: equal laps removes the mechanism it would probe,
    and the laps per reference are reported for each driver;
  - "an 11th team shifts the session medians": the field median is a constant per session
    and corner, the same for every car, so it moves every 2026 signature equally (dilution,
    not bias).
- **Disclosure:** Part C now says what the AI assistant could know about 2026 (trained to
  mid-2026, told not to use it). Sadman must write his own part. Until he does, the
  placeholder makes the 2026 script refuse to run.

## 2026-11-07 — Addendum 1 to Part C: the "no value" marker inside laps
The one-time 2026 run stopped at the feed check (attempt 1): about 1.1 % of throttle and brake
samples inside kept laps were 104, mostly in Shanghai and Suzuka; in 2023–2025 it had been
0.006–0.015 %. It is the feed's known "no value" marker, nothing new. Decided with Sadman:
treat it as a missing sample (`openf1.drop_no_value_samples`, in `slice_lap` and the feed
check), and change nothing else. Why this and not the alternatives:
`docs/preregistration_deviations.md` (2026-11-07). The addendum text is generated from
`experiments/25_feed_check_2026_diagnosis.py` and `26_addendum_1_dry_run_check.py`, and is
frozen once committed, like Part C. Its dry runs go to new folders (`*_addendum_1`), so the
evidence quoted by Part C stays as committed.

## 2026-11-09 — Day 16: two exploratory follow-ups, rules fixed before running
Both are EXPLORATORY: they come after the frozen 2026 test, are not preregistered, and cannot
change its verdict (H5 not supported). Each is reported whatever it shows. Written before
either script was run.

**E1. Which drivers lost the 30 laps to the marker removal (experiment 28).**
- For every kept 2026 lap, `openf1.slice_lap` is run twice on the cached streams: with the
  Addendum 1 rule (104 removed) and without it. A lap is "lost to the marker" if it has data
  without the rule and none with it. The reason is recorded: fewer than 10 car samples, or
  the lap's start or end no longer bracketed by samples.
- Check: the per-session counts must equal the two frozen download logs (Shanghai 21,
  Suzuka 7, Mexico City 1, Monza 1); otherwise the script stops.
- Reported: per driver and session, the laps lost and the laps kept; whether any driver lost
  a whole weekend; and the share of usable corner passes per session (already in
  `results/final_2026/sessions_2026.csv`), to see whether the marker-heavy sessions also lost
  corner passes to gaps.
- Sensitivity, one only: the H5 comparison recomputed from the frozen 2026 data with
  Shanghai and Suzuka (the sessions with about 8 % markers) left out for every driver.
  Reported as "with / without these two sessions"; no other session subsets are tried.

**E2. Teammate-relative signatures (experiment 29).**
- Why: on the same weekend, two teammates share the car, its set-up direction, the track and
  the weather. The difference between their weekend means cancels all of that, like a
  differential amplifier rejecting the common-mode signal. What remains is the drivers'
  difference (plus noise).
- Pairs: two drivers of the same team lineage with at least 5 shared weekends in both of two
  consecutive seasons. Seasons: 2023→2024 and 2024→2025 (same rules), 2025→2026 (new rules).
- Per pair and season: on each shared weekend, equal laps for both drivers (each driver's
  first laps, `signatures.equal_laps_per_session`), the weekend mean of the 30 lap-vector
  columns, the difference A − B (A = alphabetically first), then the mean over weekends.
  Each column is divided by the spread (SD) of the weekend differences of all pairs in the
  EARLIER season of the comparison, so each column counts in "typical weekend differences".
  No centring: centring would remove the sign.
- Measure: the cosine similarity of the two seasons' difference vectors (over columns present
  in both). Near +1: the same driver is ahead or behind on the same features; near 0: no
  common direction.
- Reported: per pair; the count with cosine > 0 and the median, for each pair of seasons; a
  one-sided sign test p as orientation, not as a decision. Also, as a rough reference, the
  split-half cosine within the earlier season (odd against even shared weekends): how alike
  the difference is to itself over half a season.
- Tests first (synthetic, known truth): with a personal offset the cosine is high even when
  the car is redrawn and large; with no personal offset it averages 0.
- Not done: the first plan (subtract the team median, then re-run the H4
  comparison). With two drivers, the teammate-relative values are +d and −d, so "own past
  against teammate" compares a vector with its own mirror image, a comparison whose answer
  depends on the size of d and not only on whether it persisted. The cosine asks the
  persistence question directly.

## 2026-11-13 — Day 21: do corner features add anything on top of whole-lap statistics? (E3)
EXPLORATORY, not preregistered; written before the script was run, and reported whatever it shows.
Why: H3 found that corner features identify teammates better than lap time but not better than
simple whole-lap statistics (development 0.685 vs 0.729; 2025 0.662 vs 0.680). That leaves open
whether the corner features carry information the whole-lap statistics don't, or only the same
information in an interpretable form. Instead of a neural network (planned as optional Phase 9;
not done now: no unused test season is left, the data are small for it, and it would not be
explainable yet), one combined model answers that directly.

- **Same machinery as H3:** the same team-season pairs (the two drivers with most laps, weekends
  where both drove, at least 5 weekends), the same leave-one-weekend-out logistic regression
  (`protocol.run`, no tuning), the same balanced accuracy.
- **Three inputs:** whole-lap statistics (5), corner features (30), both together (35).
- **Data:** development 2023–2024 (20 team-seasons) first; then the saved 2025 data as a second
  look (10 teams). 2025 was used once for H3 already, so both are exploratory. 2026 is not used
  (the cars changed).
- **Check first:** the script's own runs of whole-lap statistics and corner features must equal the
  committed H3 per-team results exactly, or it stops (the same pairs, the same models).
- **Reported:** per team-season and mean balanced accuracy of each input; for "both minus whole-lap
  statistics", the mean difference with a bootstrap 95 % interval over team-seasons (resampling
  team-seasons, 5,000 draws) and the number of team-seasons where both was higher; Wilcoxon p for
  orientation only.
- **Words fixed now:** if the interval for "both minus whole-lap statistics" lies above 0:
  "corner features add information beyond whole-lap statistics"; if it includes 0: "no clear gain
  from adding corner features"; if it lies below 0: "adding them made it worse" (35 inputs fitted on
  about 100–250 laps per team can overfit). The same words for development and 2025, each on its own.

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

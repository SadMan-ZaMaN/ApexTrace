# Deviations from the preregistration

`docs/preregistration.md` is left exactly as committed (Part A: commit
`ab2510c`, 2026-10-16; Part B: commit `225385c`, 2026-10-18). Every later
correction or deviation is recorded here, with the date and its effect on the
results.

## 2026-10-18 — Part B: the first final run crashed in the download step (no result produced)

**What happened:** the one-time final run (`experiments/14_final_2025.py`,
started 01:43 after commit `225385c`) stopped while downloading session 17 of
24, the 2025 Azerbaijan GP qualifying in Baku (OpenF1 `session_key` 9900).
OpenF1 has **no lap rows** for that session: `laps` answers 404 "No results
found", while `stints` (122 rows), `race_control` (217) and `drivers` (20) are
there. `openf1.lap_table()` assumed every session has laps (true for all 47
development sessions) and raised `KeyError: 'driver_number'`.

**What had been seen at that point:** no result. The crash happened in the
data step, before any lap table, model or test was run; `results/final/` was
still empty. The only 2025 output on screen was the per-session progress line
(kept laps, detected corners, usable pairs) for sessions 1–16, which are data
counts, not H3/H4 results.

**Fix:** `lap_table()` returns an empty table when OpenF1 has no laps. The
session is then skipped by the "no laps" branch that `session_build.build_session()`
already had in the committed code. Test added:
`test_session_without_laps_is_skipped_not_crashed` (fails on the old code with
the same KeyError). No data rule, feature, model, statistical test or decision
rule changed, and the development data can't change (every 2023–2024 session
has laps).

**Effect:** the 2025 Baku qualifying session is not in the final data. The
preregistration says "every 2025 main qualifying session on OpenF1"; OpenF1
has no laps for this one, so it can't be built with the committed pipeline.
Rebuilding laps from other endpoints would be new, untested code, so it was
not attempted.

**Rerun:** the remaining sessions were downloaded into the cache first
(download step only, no analysis) to catch any other data-source problem; the
empty `results/final/` folder was removed; the final script was run again
(attempt 2) with the fixed code. Attempt 1's log is kept as
`results/final/attempt_1_crash.log`.

**Attempt 2** completed on 2026-10-18 at 02:25 (log:
`results/final/run_attempt_2.log`). Its results in `results/final/` are the
final results. 23 of 24 sessions were built; Las Vegas was wet and removed by
the dry-only rule, as in development, leaving 22 dry sessions.

## 2026-10-18 — Part B: one team changer was missing from the preregistered list

**What the preregistration said:** the team changers are Hamilton, Sainz, Ocon,
Hülkenberg and Tsunoda. Lawson and Bearman were named and excluded.

**What was missed:** Franco Colapinto drove for Williams in 2024 (enough
weekends for a 2024 signature) and for Alpine in 2025 (16 weekends). He changed
teams and wasn't on the list. This came to light after the run, because he
appeared in the preregistered "non-changer" check (own vs old teammate,
`results/final/h4_non_changers.csv`), which is meant only for drivers who
stayed.

**What was done:**
- **The primary H4 test is left exactly as preregistered** (5 changers: 2 of 5,
  p = 0.81, not supported).
- **Exploratory, labelled as such:** `experiments/15_final_exploratory.py`
  derives the changers from the data and finds exactly the five preregistered
  ones plus Colapinto. With him as a 6th changer, the result is 3 of 6
  (p = 0.66). Whatever his result, the count could only have been 2 or 3 of 6
  (p ≥ 0.66), so the H4 conclusion doesn't depend on the omission.
- The non-changer check is also reported without Colapinto: 9 of 10 instead
  of 10 of 11 (p = 0.011 instead of 0.006).

## 2026-10-17 — Part A: wrong minimum p-value for unequal group sizes (text only)

**What the preregistration said:** the smallest possible p-value is 2/35 = 0.057
for 3 vs 4 laps and 2/15 = 0.13 for 2 vs 4.

**Correct values:** 1/35 = 0.029 for 3 vs 4, and 1/15 = 0.067 for 2 vs 4.
(4 vs 4 stays 2/70 = 0.029.) The "2" counts the mirror-image split (groups
swapped), which only exists when both groups have the same size.

**How it was found:** the T9 full-throttle test (3 vs 4 laps) returned
p = 0.029, below the stated "minimum" of 0.057. `stats.min_permutation_p` was
corrected and given a test (`test_minimum_p_for_unequal_groups_has_no_mirror_split`).

**Effect on the results:** none on the tests themselves. The permutation test
always computed the right p-values; only the reported "minimum possible p"
column and the sentence in the preregistration were wrong. The preregistered
conclusion still holds: Benjamini–Hochberg over 27 tests found **0
discoveries**, and could not have found one with these lap counts.

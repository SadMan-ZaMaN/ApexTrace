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

## 2026-11-07 — Part C: the one-time 2026 run stopped at the feed check (attempt 1, no result produced)

**What happened:** the run (`experiments/23_final_2026.py`) started on 2026-11-07 at 08:41 UTC,
after commit `f653d49` (Part C and the code; all guards passed). Phase 1 downloaded all 21
sessions that ended before the fixed cutoff (2026-11-06 00:00 UTC), with no download error.
Phase 2 stopped the run, as Part C prescribes. Two value-range checks failed:
- **throttle in 0–100:** 98.99 % of samples (rule: at least 99.9 %);
- **brake only 0 or 100:** 98.87 % (same rule).

Every other check passed:
- all channels present, none empty;
- speed and gear in range;
- median sample interval 0.240 s; 99.98 % of intervals on the 40 ms clock; 3.74 samples
  per second;
- all 11 team names known (including Audi and Cadillac);
- all tyre labels known, none empty.

**What had been seen at that point:** no feature and no result. `results/final_2026/` holds
only `run_started.json`, `download_log.csv` and `checks.json`. The console showed the phase
lines and the STOP.

**Diagnosis** (`experiments/25_feed_check_2026_diagnosis.py`, `results/25_feed_check_2026_diagnosis/`):
reads only the two failing channels, inside kept laps, as the check did.
- Every out-of-range value is **104**, the feed's "no value" marker (until now seen in the
  garage and pit lane): 5,808 throttle and 6,496 brake samples of 576,625. 6,539 samples
  (1.13 %) have one or both.
- No other new value appears: no brake pressure, no throttle above 100 other than 104.
- It is concentrated in a few sessions (share of samples with one or both markers): Suzuka
  8.3 %, Shanghai 8.0 %, Monza 1.1 %, every other session at most 0.29 %.
- In 2023, 2024 and 2025 the marker was in 0.015 %, 0.006 % and 0.007 % of throttle samples
  inside kept laps.
- Separately: Sakhir and Jeddah have no kept laps in OpenF1 (0 samples). The build step
  skips sessions without laps, as it did for Baku in 2025.

**Why it matters:** the feature code reads a throttle of 104 as "above 99 %" (full throttle)
and a brake of 104 as "on". Left in, these samples would move throttle and braking events
in the affected sessions.

**Decided with Sadman (2026-11-07):** Addendum 1 to Part C (`docs/preregistration.md`).
Inside a kept lap, a sample with throttle or brake 104 is a missing sample, removed before
features, like a feed dropout. The feed check runs on the same cleaned samples with its rules
unchanged. Rejected alternatives:
- dropping the affected sessions (Part C forbids changing the sessions);
- lowering the 99.9 % threshold (arbitrary after seeing the data, and the wrong values would
  stay in the features);
- giving up H5 (the marker is known, not a changed feed).
Rehearsed on 2024 (experiment 26). The folder of this attempt was renamed
`results/final_2026_attempt_1/`; it keeps `run_started.json`, `download_log.csv`, `checks.json`
and the console log `run_attempt_1.log`. The run is repeated with the same fixed cutoff after
the addendum is committed.

## 2026-11-07 — Part C: attempt 2 completed (no further deviation)

After Addendum 1 was committed (`ac3a793`), the run was repeated with the same fixed cutoff and
the same 21 sessions. All checks passed (6,539 marker samples removed, as the addendum says); 19
sessions were built (Sakhir and Jeddah have no laps in OpenF1, skipped as Part C's build rule
says); the analysis ran as preregistered and wrote `results/final_2026/` (see its README). No
other deviation. Afterwards the script refuses to run again, even with the switch set.

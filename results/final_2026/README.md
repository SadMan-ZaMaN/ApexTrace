# The one-time 2026 test (H5, and H4 on the 2026 team changers)

The preregistered test of `docs/preregistration.md`, Part C (commit `f653d49`) with Addendum 1
(commit `ac3a793`). Produced by `experiments/23_final_2026.py`. **These numbers are frozen**:
the script refuses to run again (any `results/final_2026*/summary.json` blocks it).

## How it was run
- **Attempt 1** (2026-11-07, 08:41 UTC, after `f653d49`) downloaded all 21 sessions that ended
  before the fixed cutoff (2026-11-06 00:00 UTC) and stopped at the feed check, before any feature:
  1.13 % of throttle and brake samples inside kept laps were the feed's "no value" marker 104.
  No result was produced. Folder: `results/final_2026_attempt_1/`; record and diagnosis:
  `docs/preregistration_deviations.md`, `experiments/25_feed_check_2026_diagnosis.py`.
- **Addendum 1** (agreed with Sadman, committed as `ac3a793`): 104 inside a kept lap is a missing
  sample, removed before features and before the feed check. Rehearsed on 2024
  (`experiments/26_addendum_1_dry_run_check.py`).
- **Attempt 2** (2026-11-07, after `ac3a793`): same cutoff and sessions. All checks passed (6,539
  marker samples removed); 19 sessions built (Sakhir and Jeddah have no laps in OpenF1), 1,751
  laps; analysis as preregistered. Log: `run_attempt_2.log`.

## Files
| File | What |
|---|---|
| `summary.json` | Every headline number; `h5.verdict` is the preregistered decision |
| `run_started.json` | The commit, the cutoff and the session list of attempt 2 |
| `download_log.csv`, `checks.json` | Phase 1 and phase 2 (feed, team names, tyre labels, markers removed per session) |
| `h5_all.csv` | H5 primary, one row per driver: teammate, shared weekends, laps used per reference, both distances, own_closer |
| `h5_control_points.csv`, `h5_energy-sensitive.csv`, `h5_no_throttle.csv` | The secondary feature sets |
| `team_changes.csv`, `h4_changers.csv`, `h4_stayers.csv` | H4 on the 2026 team changers and the stayer control |
| `dataset_2026.csv.gz`, `corners_2026.csv`, `sessions_2026.csv` | The 2026 build |
| `raw_samples_2026.parquet` | Raw samples per lap (gitignored) |

## Results in one paragraph
**H5 is not supported.** 13 of 19 drivers' 2026 signatures were closer to their own 2025 signature
than to their 2025 teammate's (share 0.68, exact 95 % interval 0.43–0.87); the one-sided sign test
gives p = 0.084, and 14 of 19 were needed for p < 0.05. Without a rule change the same procedure
gave 16 of 20 (2023 → 2024) and 14 of 16 (2024 → 2025). As stated in advance, this "no" can't tell a
weakened signature from a lost one: the share is above one half but the test can't separate it from
chance. The secondary feature sets agree (control points 12, energy-sensitive 13, no throttle 12 of
19). H4 on the 2026 team changers had one eligible changer (HAD, Racing Bulls → Red Bull Racing), so
it is descriptive only (0 of 1); the stayer control gave 5 of 18 (the comparison leans towards the
current teammate). Per session, 2026 has fewer fast corners than 2025 (0.58 against 0.87) and more
slow ones (3.84 against 3.17), as expected with less downforce.

Anything beyond these preregistered numbers is exploratory and will be labelled so.

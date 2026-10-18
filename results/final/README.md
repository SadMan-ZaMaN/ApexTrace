# Final evaluation on the frozen 2025 season

The preregistered, one-time test of H3 and H4 (`docs/preregistration.md`,
Part B, commit `225385c`). Produced by `experiments/14_final_2025.py`. These
numbers are frozen. Exploratory follow-ups are in `results/15_final_exploratory/`.

## How it was run
- **Attempt 1** (2026-10-18, 01:43) crashed in the download step at session
  17 of 24 (2025 Baku: OpenF1 has no lap rows). No result had been produced.
  Log: `attempt_1_crash.log`.
- **Fix:** `openf1.lap_table` returns an empty table for a session without
  laps, and the session is skipped. Recorded in
  `docs/preregistration_deviations.md` before the rerun.
- **Attempt 2** (2026-10-18, finished 02:25): code = commit `225385c` + that fix.
  Log: `run_attempt_2.log`.

## Files
| File | What |
|---|---|
| `summary.json` | All headline numbers and the two preregistered decisions (`h3_supported`, `h4_supported`) |
| `sessions_2025.csv` | One row per qualifying session: laps, kept laps, corners, usable pairs, note |
| `corners_2025.csv` | The corners detected automatically on each session's fastest kept lap |
| `dataset_2025.csv.gz` | One row per (driver, lap, corner) with the features (before cleaning) |
| `h3_teammates_2025.csv` | Per team: balanced accuracy of every feature set, vote, shuffled labels, ablation |
| `h4_changers.csv` | Per preregistered team changer: distances, own vs new teammate, brake share, own rank |
| `h4_non_changers.csv` | Secondary check for drivers who stayed (contains COL by mistake; see the deviations file) |
| `raw_samples_2025.parquet` | Raw samples per lap (gitignored, rebuilt by the script) |

## Results in one paragraph
**H3 is replicated:** on 10 teams, corner features identify which teammate
drove a lap with balanced accuracy 0.662 vs 0.575 for lap time only (better
in 8 of 10 teams, Wilcoxon p = 0.027). As in development, they don't beat
simple whole-lap statistics (0.680; p = 1.0). **H4 is not supported:** the
2025 signature was closer to the driver's own 2024 signature than to the
new teammate's for 2 of 5 team changers (Hülkenberg, Tsunoda); sign test
p = 0.81.

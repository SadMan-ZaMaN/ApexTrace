"""Why did the 2026 feed check fail? (Part C: the failure is described before anything else.)

The one-time 2026 run (attempt 1, 2026-11-07) stopped in phase 2: the value-range checks for
throttle and brake failed. This reads ONLY what the check itself read (the cached samples
inside kept laps) and ONLY the two failing channels: which values are out of range, how
often, in which sessions, and where in the lap. No feature, no driver-level number, nothing
about H5 or H4 is computed.

Outputs results/25_feed_check_2026_diagnosis/summary.json. Run from the repo root (reads only
the local cache; ~1 minute):
    .venv\\Scripts\\python.exe experiments\\25_feed_check_2026_diagnosis.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from apextrace.openf1 import session_feed_tables

REPO_ROOT = Path(__file__).resolve().parent.parent
RUN_STARTED = REPO_ROOT / "results" / "final_2026" / "run_started.json"
OUT_DIR = REPO_ROOT / "results" / "25_feed_check_2026_diagnosis"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    start = json.loads(RUN_STARTED.read_text(encoding="utf-8"))
    sessions, throttle_out, brake_out, where = [], [], [], []
    total = 0
    for session in start["sessions"]:
        cars, _ = session_feed_tables(int(session["session_key"]), pd.Timestamp(session["date_end"]), drop_no_value=False)
        samples = bad_throttle = bad_brake = either = 0
        for car in cars:
            throttle = car["throttle"].to_numpy(dtype=float)
            brake = car["brake"].to_numpy(dtype=float)
            outside_throttle = (throttle < 0) | (throttle > 100)
            outside_brake = (brake != 0) & (brake != 100)
            throttle_out.extend(throttle[outside_throttle].tolist())
            brake_out.extend(brake[outside_brake].tolist())
            where.extend(np.linspace(0, 1, len(car))[outside_throttle | outside_brake].tolist())
            samples += len(car)
            bad_throttle += int(outside_throttle.sum())
            bad_brake += int(outside_brake.sum())
            either += int((outside_throttle | outside_brake).sum())
        total += samples
        sessions.append({"session": session["location"], "session_key": int(session["session_key"]),
                         "samples": samples, "throttle_out_of_range": bad_throttle, "brake_not_0_or_100": bad_brake,
                         "samples_with_either": either,
                         "share_with_either": either / samples if samples else None})
    summary = {
        "note": "Diagnosis of the failed feed check of the 2026 run, attempt 1. Only the two failing channels.",
        "samples_inside_kept_laps": total,
        "throttle_out_of_range_values": {str(k): int(v) for k, v in pd.Series(throttle_out).value_counts().items()},
        "brake_out_of_range_values": {str(k): int(v) for k, v in pd.Series(brake_out).value_counts().items()},
        "share_by_tenth_of_lap": (np.histogram(where, bins=10, range=(0, 1))[0] / max(len(where), 1)).round(3).tolist(),
        "sessions": sessions,
    }
    # for comparison: how often the marker appeared inside kept laps in the development seasons
    # (the saved raw samples keep the raw throttle value, so a 104 there is still visible)
    development = {}
    for raw_path in (REPO_ROOT / "results" / "09_dataset" / "raw_samples.parquet",
                     REPO_ROOT / "results" / "final" / "raw_samples_2025.parquet"):
        raw = pd.read_parquet(raw_path, columns=["year", "throttle_pct"])
        for year, part in raw.groupby("year"):
            development[str(year)] = {"samples": int(len(part)), "throttle_104": int((part["throttle_pct"] == 104).sum())}
    summary["development_throttle_marker"] = development
    print(json.dumps({k: v for k, v in summary.items() if k != "sessions"}, indent=1))
    print(pd.DataFrame(sessions).to_string(index=False))
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=1)


if __name__ == "__main__":
    main()

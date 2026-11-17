"""Code review check (2026-11-18): corner passes whose longest interval is EXACTLY the 0.6 s gap limit.

The usable-window rule drops a corner pass if any interval between car samples in its window is
longer than 0.6 s (corners.has_feed_gap: diff > GAP_S). The feed runs on a 40 ms clock, so 0.60 s
(15 ticks) is a real interval length, and for it "longer than 0.6" is decided by floating-point
rounding of the timestamps: 0.9 - 0.3 = 0.6000000000000001 counts as a gap, 0.6 - 0.0 = 0.6 does
not. The rule is not changed: every dataset, including the frozen 2025 and 2026 tests, was built
with it, and it is deterministic (the same data always give the same answer). This script only
measures how many passes sit on that boundary and how the build classified them.

Read-only: the saved raw samples (times rounded to 1 ms, enough to tell 0.60 s from 0.56 or 0.64)
and the saved datasets. A pass is matched to its dataset row by (session, driver, lap, corner
position). Outputs: results/34_gap_boundary/summary.json.
Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\34_gap_boundary.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from apextrace.corners import GAP_S, window_bounds

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "results"
OUT_DIR = RESULTS / "34_gap_boundary"
CLOCK_S = 0.04
SEASONS = {
    "2023-2024": ("09_dataset/raw_samples.parquet", "09_dataset/corners.csv", "09_dataset/dataset.csv.gz"),
    "2025": ("final/raw_samples_2025.parquet", "final/corners_2025.csv", "final/dataset_2025.csv.gz"),
    "2026": ("final_2026/raw_samples_2026.parquet", "final_2026/corners_2026.csv", "final_2026/dataset_2026.csv.gz"),
}


def longest_interval_ticks(times_s):
    """The longest interval between consecutive samples, in 40 ms clock ticks (whole number).

    Example: samples at 0.00, 0.28, 0.88 s -> intervals 0.28 and 0.60 s -> 15 ticks.
    """
    return int(round(float(np.max(np.diff(times_s))) / CLOCK_S))


def boundary_passes(raw, corners):
    """(session, driver, lap, corner position) of every corner pass with samples, and its longest
    interval in ticks, using the same window and extra edge samples as the build."""
    corner_positions = {key: group["s_m"].to_numpy() for key, group in corners.groupby("session_key")}
    rows = []
    for (session, driver, lap), samples in raw.groupby(["session_key", "driver", "lap"], sort=False):
        s = samples["s_m"].to_numpy()
        t = samples["time_s"].to_numpy()
        for corner_s in corner_positions.get(session, []):
            start, end = window_bounds(corner_s)
            inside = np.where((s >= start) & (s <= end))[0]
            if len(inside) == 0:
                continue
            first, last = max(inside[0] - 1, 0), min(inside[-1] + 1, len(s) - 1)
            if last == first:
                continue
            rows.append({"session_key": session, "driver": driver, "lap": lap, "corner_s_m": round(float(corner_s), 1),
                         "ticks": longest_interval_ticks(t[first:last + 1])})
    return pd.DataFrame(rows)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    limit_ticks = int(round(GAP_S / CLOCK_S))
    summary = {"note": "code review check; the rule is not changed (frozen datasets)", "gap_s": GAP_S,
               "limit_ticks": limit_ticks, "seasons": {}}
    for name, (raw_file, corners_file, dataset_file) in SEASONS.items():
        raw = pd.read_parquet(RESULTS / raw_file, columns=["session_key", "driver", "lap", "time_s", "s_m"])
        corners = pd.read_csv(RESULTS / corners_file)
        passes = boundary_passes(raw, corners)
        dataset = pd.read_csv(RESULTS / dataset_file,
                              usecols=["session_key", "driver", "lap", "corner_s_m", "usable", "reason"])
        dataset["corner_s_m"] = dataset["corner_s_m"].round(1)
        at_limit = passes[passes["ticks"] == limit_ticks].merge(
            dataset, on=["session_key", "driver", "lap", "corner_s_m"], how="left")
        block = {"passes_with_samples": int(len(passes)), "longest_exactly_at_limit": int(len(at_limit)),
                 "share": round(len(at_limit) / len(passes), 4),
                 "of_those_usable": int((at_limit["usable"] == True).sum()),  # noqa: E712
                 "of_those_feed_gap": int((at_limit["reason"] == "feed gap in window").sum()),
                 "of_those_unmatched": int(at_limit["usable"].isna().sum())}
        summary["seasons"][name] = block
        print(f"{name}: {block['longest_exactly_at_limit']:,} of {block['passes_with_samples']:,} passes "
              f"({block['share']:.2%}) have a longest interval of exactly {GAP_S} s; the build kept "
              f"{block['of_those_usable']} and dropped {block['of_those_feed_gap']} as a feed gap "
              f"({block['of_those_unmatched']} not matched)")
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=1)


if __name__ == "__main__":
    main()

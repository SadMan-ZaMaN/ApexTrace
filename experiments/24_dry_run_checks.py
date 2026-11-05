"""Two checks of the 2026 dry runs, saved so that Part C can quote them.

  1. Rebuild: is the 2024 dataset rebuilt by `23_final_2026.py --dry-run 2024` (download from
     the cache -> checks -> session_build) identical to the one built on 2026-10-17 by
     `09_build_dataset.py`? Same rows, same usable rows, same feature values.
  2. Frozen H4: with Part B's spread (leave_pair_out=False), does h5_protocol give the
     frozen 2025 H4 distances (results/15_final_exploratory) for every driver, with the
     same teammate and the same verdict? The frozen files keep 4 decimals, so differences
     up to 0.00005 are rounding. (These are the 6 changers including Colapinto and the 10
     stayers of the exploratory follow-up, not Part B's preregistered 5.)
  3. Fingerprints (SHA-256) of the 2025 reference files the 2026 run reads; its guard
     refuses to run if a file is missing or different.

Needs the dry run's local files (run `23_final_2026.py --dry-run 2024` first).
Outputs results/24_dry_run_checks/summary.json. Run from the repo root (~1 minute):
    .venv\\Scripts\\python.exe experiments\\24_dry_run_checks.py
"""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

from apextrace import h5_protocol
from apextrace.dataset import load_dataset
from apextrace.features import FEATURES

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "results"
OUT_DIR = RESULTS / "24_dry_run_checks"
ROUNDING = 0.00005


def rebuild_check():
    original = load_dataset()
    original = original[original["year"] == 2024]
    rebuilt = pd.read_csv(RESULTS / "final_2026_dry_run" / "2024" / "dataset_2024.csv.gz")
    keys = ["session_key", "driver", "lap", "corner"]
    merged = original.merge(rebuilt, on=keys, suffixes=("_original", "_rebuilt"))
    largest, empty_mismatches = 0.0, 0
    for feature in FEATURES:
        a = merged[f"{feature}_original"].to_numpy(dtype=float)
        b = merged[f"{feature}_rebuilt"].to_numpy(dtype=float)
        empty_mismatches += int(np.sum(np.isnan(a) != np.isnan(b)))
        both = ~np.isnan(a) & ~np.isnan(b)
        if both.any():
            largest = max(largest, float(np.max(np.abs(a[both] - b[both]))))
    return {"rows_original": int(len(original)), "rows_rebuilt": int(len(rebuilt)), "rows_matched": int(len(merged)),
            "usable_original": int(original["usable"].sum()), "usable_rebuilt": int(rebuilt["usable"].sum()),
            "largest_feature_difference": largest, "empty_value_mismatches": empty_mismatches,
            "identical": bool(len(original) == len(rebuilt) == len(merged) and largest == 0.0 and empty_mismatches == 0)}


def frozen_h4_check():
    spec = importlib.util.spec_from_file_location("final_2026", REPO_ROOT / "experiments" / "23_final_2026.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    laps = pd.concat([script.reference_lap_table(2024), script.reference_lap_table(2025)], ignore_index=True)
    _, changers, stayers, _ = h5_protocol.h4_results(laps, 2024, 2025, leave_pair_out=False)
    frozen = {"changers": pd.read_csv(RESULTS / "15_final_exploratory" / "h4_all_changers.csv"),
              "stayers": pd.read_csv(RESULTS / "15_final_exploratory" / "h4_shape_control_non_changers.csv")}
    out = {}
    for name, ours in (("changers", changers), ("stayers", stayers)):
        old = frozen[name][frozen[name]["included"]]
        merged = ours[ours["included"]].merge(old, on="driver", suffixes=("", "_frozen"))
        gap = max(float((merged["distance_own_reference"] - merged["distance_own_2024"]).abs().max()),
                  float((merged["distance_new_teammate"] - merged["distance_new_teammate_2025"]).abs().max()))
        out[name] = {"drivers": int(len(merged)), "drivers_frozen": int(len(old)), "largest_distance_difference": gap,
                     "same_teammates": bool((merged["teammate_target"] == merged["teammate_2025"]).all()),
                     "same_verdicts": bool((merged["own_closer"] == merged["own_closer_frozen"]).all())}
    out["all_match"] = all(part["drivers"] == part["drivers_frozen"] and part["largest_distance_difference"] <= ROUNDING
                           and part["same_teammates"] and part["same_verdicts"]
                           for part in (out["changers"], out["stayers"]))
    return out


def reference_fingerprints():
    """SHA-256 of each 2025 reference file the one-time 2026 run reads. Committed with Part C,
    so the run can check that it uses exactly these files (the raw samples are not in git)."""
    spec = importlib.util.spec_from_file_location("final_2026", REPO_ROOT / "experiments" / "23_final_2026.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    fingerprints = {}
    for relative in script.REFERENCE_FILES:
        fingerprints[relative] = script.sha256(REPO_ROOT / relative)
    return fingerprints


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {"rebuild_2024": rebuild_check(), "frozen_h4_2025": frozen_h4_check(), "rounding": ROUNDING,
               "reference_files": reference_fingerprints()}
    print(json.dumps(summary, indent=1))
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=1)


if __name__ == "__main__":
    main()

"""Addendum 1 dry run: what does removing the "no value" marker 104 change on 2024?

`23_final_2026.py --dry-run 2024` (after Addendum 1) rebuilds 2024 from the cache with the
marker removed inside kept laps (openf1.drop_no_value_samples). This compares that rebuild with
the development dataset built on 2026-10-17 without the rule: how many (driver, lap, corner)
rows change at all, and how many usable rows are lost. In 2024 the marker was in 41 of 725,799
throttle samples inside kept laps, so very few rows should change. Also records the H5 count of
the dry run next to experiment 20's.

Needs the dry run's local files. Outputs results/26_addendum_1_dry_run_check/summary.json.
Run from the repo root (~1 minute):
    .venv\\Scripts\\python.exe experiments\\26_addendum_1_dry_run_check.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from apextrace.dataset import load_dataset
from apextrace.features import FEATURES

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "results"
DRY_RUN = RESULTS / "final_2026_dry_run" / "2024_addendum_1"
OUT_DIR = RESULTS / "26_addendum_1_dry_run_check"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    original = load_dataset()
    original = original[original["year"] == 2024]
    rebuilt = pd.read_csv(DRY_RUN / "dataset_2024.csv.gz")
    keys = ["session_key", "driver", "lap", "corner"]
    merged = original.merge(rebuilt, on=keys, how="outer", suffixes=("_original", "_rebuilt"), indicator=True)
    both = merged[merged["_merge"] == "both"]
    changed = np.zeros(len(both), dtype=bool)
    for feature in FEATURES:
        a = both[f"{feature}_original"].to_numpy(dtype=float)
        b = both[f"{feature}_rebuilt"].to_numpy(dtype=float)
        differs = ~((np.isnan(a) & np.isnan(b)) | (a == b))
        changed |= differs
    changed |= (both["usable_original"] != both["usable_rebuilt"]).to_numpy()
    dry = json.loads((DRY_RUN / "summary.json").read_text(encoding="utf-8"))
    checks = json.loads((DRY_RUN / "checks.json").read_text(encoding="utf-8"))
    development = json.loads((RESULTS / "20_h5_development" / "summary.json").read_text(encoding="utf-8"))
    summary = {
        "rows_original": int(len(original)), "rows_rebuilt": int(len(rebuilt)),
        "rows_only_in_one": int((merged["_merge"] != "both").sum()),
        "rows_changed": int(changed.sum()),
        "usable_original": int(original["usable"].sum()), "usable_rebuilt": int(rebuilt["usable"].sum()),
        "marker_samples_removed": int(sum(row["no_value_removed"] for row in checks["no_value_marker_removed"])),
        "checks_ok": bool(checks["feed"]["ok"] and not checks["unknown_team_names"] and checks["compounds"]["ok"]),
        "h5_dry_run": dry["h5"]["sets"]["all"], "h5_experiment_20": development["pairs"]["2023 -> 2024"]["all"],
    }
    summary["h5_same_count"] = (summary["h5_dry_run"]["own_closer"] == summary["h5_experiment_20"]["own_closer"]
                                and summary["h5_dry_run"]["drivers"] == summary["h5_experiment_20"]["drivers"])
    print(json.dumps(summary, indent=1))
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=1)


if __name__ == "__main__":
    main()

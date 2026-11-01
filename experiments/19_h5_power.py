"""H5 design: how many drivers will the 2026 test have, and what can it detect?

Development data only (2023-2025); nothing about 2026 is loaded. Design: docs/h5_design.md.

The H5 comparison: a driver's 2026 season signature is "closer to their own past" if it
is nearer their own 2025 signature than their 2025 teammate's (both made in the same
2025 car). A one-sided sign test counts those drivers. This script answers three
questions before the test is preregistered:

  1. How often did that happen WITHOUT a rule change? Two development baselines,
     already measured: 2023 -> 2024 (results/13_signature_stability) and the drivers
     who stayed in their team 2024 -> 2025 (results/final, non_changer_check).
     Each with an exact 95 % interval (Clopper-Pearson).
  2. How many drivers can take part? Upper bound from 2025: drivers with >= 5 dry
     weekends whose most-driven team had another driver with >= 5 shared weekends.
     The 2026 number can only be lower (drivers who left are lost).
  3. Power: the chance of a significant sign test (p < 0.05) for a range of driver
     counts and per-driver success probabilities (signatures.sign_test_power).

Outputs in results/19_h5_power/: summary.json, power_table.csv.
Run from the repo root (reads only local files, a few seconds):
    .venv\\Scripts\\python.exe experiments\\19_h5_power.py
"""

import json
from pathlib import Path

import pandas as pd
from scipy.stats import binomtest

from apextrace.dataset import clean
from apextrace.signatures import sign_test_p, sign_test_power, sign_test_threshold

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "results"
OUT_DIR = RESULTS / "19_h5_power"
MIN_WEEKENDS = 5
DRIVER_COUNTS = [8, 10, 12, 14, 16, 18, 20]
SUCCESS_PROBABILITIES = [0.6, 0.7, 0.8, 0.85, 0.9]
CHANGER_COUNTS = [3, 4, 5, 6, 7, 8]


def baseline(successes, trials, label):
    """One development baseline: the count, its share, an exact 95 % interval and the sign-test p."""
    interval = binomtest(successes, trials).proportion_ci(confidence_level=0.95, method="exact")
    return {"label": label, "successes": successes, "trials": trials, "share": successes / trials,
            "ci95_low": float(interval.low), "ci95_high": float(interval.high),
            "sign_test_p": sign_test_p(successes, trials)}


def eligible_drivers_2025():
    """Drivers who could enter the H5 comparison from the 2025 side.

    A driver counts if they have >= 5 dry weekends in 2025 and, in the team they drove
    for on most weekends, another driver shared >= 5 of those weekends (needed for the
    teammate reference, built on the shared weekends only).
    Example: a driver with 22 weekends whose teammate was replaced after 2 rounds still
    counts, through the replacement (20 shared weekends).
    """
    data, _ = clean(pd.read_csv(RESULTS / "final" / "dataset_2025.csv.gz"))
    rows = []
    for driver in sorted(data["driver"].unique()):
        own = data[data["driver"] == driver]
        weekends_per_team = own.groupby("team")["session_key"].nunique()
        if weekends_per_team.sum() < MIN_WEEKENDS:
            continue
        team = weekends_per_team.idxmax()
        own_weekends = set(own.loc[own["team"] == team, "session_key"])
        team_rows = data[(data["team"] == team) & (data["driver"] != driver)]
        best_mate, best_shared = None, 0
        for mate in sorted(team_rows["driver"].unique()):
            shared = len(own_weekends & set(team_rows.loc[team_rows["driver"] == mate, "session_key"]))
            if shared > best_shared:
                best_mate, best_shared = mate, shared
        rows.append({"driver": driver, "team_2025": team, "weekends_with_team": len(own_weekends),
                     "teammate": best_mate, "shared_weekends": best_shared,
                     "eligible": best_shared >= MIN_WEEKENDS})
    return pd.DataFrame(rows)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. baselines without a rule change
    dev = json.loads((RESULTS / "13_signature_stability" / "summary.json").read_text(encoding="utf-8"))
    final = json.loads((RESULTS / "final" / "summary.json").read_text(encoding="utf-8"))
    baselines = [
        baseline(dev["corner_features"]["own_closer_than_teammate"], dev["corner_features"]["pairs"],
                 "2023 -> 2024, all drivers in both seasons"),
        baseline(final["non_changer_check"]["own_closer"], final["non_changer_check"]["drivers"],
                 "2024 -> 2025, drivers who stayed in their team"),
    ]
    for b in baselines:
        print(f"{b['label']}: {b['successes']} of {b['trials']} = {b['share']:.2f} "
              f"[{b['ci95_low']:.2f}, {b['ci95_high']:.2f}], p = {b['sign_test_p']:.4f}")

    # 2. how many drivers can take part (upper bound from 2025)
    eligible = eligible_drivers_2025()
    eligible.to_csv(OUT_DIR / "eligible_2025.csv", index=False)
    n_eligible = int(eligible["eligible"].sum())
    print(f"\n2025 drivers with >= {MIN_WEEKENDS} dry weekends: {len(eligible)}; "
          f"with a teammate sharing >= {MIN_WEEKENDS} weekends: {n_eligible}")
    print(eligible.to_string(index=False))

    # 3. power of the H5 sign test
    rows = []
    for drivers in DRIVER_COUNTS:
        row = {"drivers": drivers, "needed": sign_test_threshold(drivers)}
        for probability in SUCCESS_PROBABILITIES:
            row[f"power_at_{probability}"] = round(sign_test_power(drivers, probability), 3)
        rows.append(row)
    power = pd.DataFrame(rows)
    power.to_csv(OUT_DIR / "power_table.csv", index=False)
    print("\nPower of the one-sided sign test (p < 0.05):")
    print(power.to_string(index=False))

    changers = []
    for count in CHANGER_COUNTS:
        changers.append({"changers": count, "needed": sign_test_threshold(count),
                         "smallest_possible_p": sign_test_p(count, count)})
    print("\nSecondary H4 on 2026 team changers: how many must go the driver's way")
    print(pd.DataFrame(changers).to_string(index=False))

    summary = {"min_weekends": MIN_WEEKENDS, "baselines": baselines,
               "drivers_2025_with_min_weekends": int(len(eligible)), "eligible_upper_bound": n_eligible,
               "power_table": rows, "changer_thresholds": changers}
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=1)
    print(f"\nwrote {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

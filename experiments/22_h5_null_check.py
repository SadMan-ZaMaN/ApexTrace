"""Is the H5 comparison a fair coin when the signature is only the car? (synthetic, large)

The sign test assumes that, without a personal signature, each driver is closer to their
own past with probability exactly 0.5. This simulates that world many times
(synthetic.signature_seasons with personal_sd = 0: every lap = car + noise, and a new car
in the target season) and measures the share, for the H5 rules and for the two broken
versions found while building them (docs/engineering_notes.md, 2026-11-03):

  A  full-season references, teammate drove 5 of 12 weekends     (broken: noise asymmetry)
  B  shared weekends, but the pair inside the z-score spread      (broken: self-shrinking)
  C  H5 rules (shared weekends, pair left out), same teammate     (should be 0.5)
  D  H5 rules, teammates on every weekend                         (should be 0.5)
  E  all laps, the lead driver 6 laps a weekend, the teammate 2 and then gone
     (survivorship: the driver with more laps keeps the seat)     (broken: lap-count asymmetry)
  F  H5 rules (equal laps per shared weekend), the same world     (should be 0.5)
  A also over six small seeds (93-98, 150 drivers each), as quoted in the design file.
  E was found by the fresh-eyes review of Part C (2026-11-06).
  G  the whole H5 test under the null: 300 studies of 10 teams (20 drivers; two 2025 teammates
     share the same pair of references, so their outcomes are not independent). How often is
     the sign test "significant" (p < 0.05)? An exact test on independent drivers would be at
     or below 0.05; dependence between teammates could push it up or down.

One standard error of a share over n drivers is sqrt(0.25 / n); "z" below = (share - 0.5) / SE.

Outputs in results/22_h5_null_check/summary.json. Run from the repo root (~3 minutes):
    .venv\\Scripts\\python.exe experiments\\22_h5_null_check.py
"""

import json
import math
from pathlib import Path

import numpy as np

from apextrace.signatures import own_vs_past_teammate, sign_test_p
from apextrace.synthetic import SIGNATURE_FEATURES, own_closer_share, signature_seasons

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "results" / "22_h5_null_check"
SEED = 1234
STUDIES = 300
FEW_WEEKENDS_TEAMMATE = {"personal_sd": 0.0, "weekends": 12, "teammate_weekends": 5, "noise": 2.0, "car_sd": 0.3}
FULL_SEASON_TEAMMATE = {"personal_sd": 0.0, "weekends": 12, "noise": 2.0, "car_sd": 0.3}
FEWER_LAPS_TEAMMATE = {"personal_sd": 0.0, "weekends": 12, "noise": 2.0, "car_sd": 0.3, "laps_lead": 6,
                       "laps_second": 2, "second_continues": False}

CASES = {
    "A full-season references": {"shared_weekends_only": False, **FEW_WEEKENDS_TEAMMATE},
    "B pair inside the spread": {"leave_pair_out": False, **FEW_WEEKENDS_TEAMMATE},
    "C H5 rules, few-weekends teammate": FEW_WEEKENDS_TEAMMATE,
    "D H5 rules, full-season teammates": FULL_SEASON_TEAMMATE,
    "E all laps, teammate with fewer laps": {"equal_laps": False, **FEWER_LAPS_TEAMMATE},
    "F H5 rules, teammate with fewer laps": FEWER_LAPS_TEAMMATE,
}


def describe(share, drivers):
    standard_error = math.sqrt(0.25 / drivers)
    return {"share": share, "drivers": drivers, "standard_error": standard_error,
            "z": (share - 0.5) / standard_error}


def false_positive_rate(seed=SEED + 7, studies=300, teams=10):
    """Case G: the H5 sign test on many car-only studies. Returns the share of studies with
    p < 0.05, the variance of the success count against the binomial n/4, and how often the
    two teammates of a pair came out one-and-one."""
    rng = np.random.default_rng(seed)
    significant, counts, split_pairs, pairs = 0, [], 0, 0
    drivers = 0
    for _ in range(studies):
        laps = signature_seasons(rng, teams=teams, **FULL_SEASON_TEAMMATE)
        table = own_vs_past_teammate(laps, 2025, 2026, SIGNATURE_FEATURES)
        included = table[table["included"]]
        successes, drivers = int(included["own_closer"].sum()), len(included)
        counts.append(successes)
        if sign_test_p(successes, drivers) < 0.05:
            significant += 1
        for team in range(teams):
            pair = included[included["driver"].isin([f"A{team}", f"B{team}"])]
            if len(pair) == 2:
                pairs += 1
                split_pairs += int(pair["own_closer"].sum() == 1)
    return {"studies": studies, "drivers_per_study": drivers, "false_positive_rate": significant / studies,
            "count_variance": float(np.var(counts, ddof=1)), "binomial_variance": drivers / 4,
            "pairs_split_one_and_one": split_pairs / pairs}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {"seed": SEED, "studies": STUDIES, "setup": FEW_WEEKENDS_TEAMMATE, "setup_laps": FEWER_LAPS_TEAMMATE,
               "cases": {}}
    for name, options in CASES.items():
        share, drivers = own_closer_share(SEED, STUDIES, **options)
        summary["cases"][name] = describe(share, drivers)
        c = summary["cases"][name]
        print(f"{name}: {share:.3f} over {drivers} drivers, z = {c['z']:+.2f}", flush=True)

    small = {}
    for seed in range(93, 99):
        share, drivers = own_closer_share(seed, 30, shared_weekends_only=False, **FEW_WEEKENDS_TEAMMATE)
        small[str(seed)] = describe(share, drivers)
    summary["A over six small seeds"] = {"min_share": min(v["share"] for v in small.values()),
                                         "max_share": max(v["share"] for v in small.values()), "seeds": small}
    print(f"A over seeds 93-98 (150 drivers each): {summary['A over six small seeds']['min_share']:.3f}"
          f"-{summary['A over six small seeds']['max_share']:.3f}")

    summary["G whole test under the null"] = false_positive_rate()
    g = summary["G whole test under the null"]
    print(f"G: sign test 'significant' in {g['false_positive_rate']:.3f} of {g['studies']} car-only studies "
          f"({g['drivers_per_study']} drivers each); count variance {g['count_variance']:.2f} vs binomial "
          f"{g['binomial_variance']:.2f}; pairs split one-and-one {g['pairs_split_one_and_one']:.2f}")
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=1)
    print(f"wrote {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

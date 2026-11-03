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
  A also over six small seeds (93-98, 150 drivers each), as quoted in the design file.

One standard error of a share over n drivers is sqrt(0.25 / n); "z" below = (share - 0.5) / SE.

Outputs in results/22_h5_null_check/summary.json. Run from the repo root (~3 minutes):
    .venv\\Scripts\\python.exe experiments\\22_h5_null_check.py
"""

import json
import math
from pathlib import Path

from apextrace.synthetic import own_closer_share

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "results" / "22_h5_null_check"
SEED = 1234
STUDIES = 300
FEW_WEEKENDS_TEAMMATE = {"personal_sd": 0.0, "weekends": 12, "teammate_weekends": 5, "noise": 2.0, "car_sd": 0.3}
FULL_SEASON_TEAMMATE = {"personal_sd": 0.0, "weekends": 12, "noise": 2.0, "car_sd": 0.3}

CASES = {
    "A full-season references": {"shared_weekends_only": False, **FEW_WEEKENDS_TEAMMATE},
    "B pair inside the spread": {"leave_pair_out": False, **FEW_WEEKENDS_TEAMMATE},
    "C H5 rules, few-weekends teammate": FEW_WEEKENDS_TEAMMATE,
    "D H5 rules, full-season teammates": FULL_SEASON_TEAMMATE,
}


def describe(share, drivers):
    standard_error = math.sqrt(0.25 / drivers)
    return {"share": share, "drivers": drivers, "standard_error": standard_error,
            "z": (share - 0.5) / standard_error}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {"seed": SEED, "studies": STUDIES, "setup": FEW_WEEKENDS_TEAMMATE, "cases": {}}
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

    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=1)
    print(f"wrote {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

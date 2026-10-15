"""Phase 5: the preregistered pilot tests (docs/preregistration.md, Part A), H1 and H2.

This script REFUSES TO RUN unless docs/preregistration.md is committed in git
and unchanged since that commit, so the plan provably came before the results.

H2 (qualifying, NOR vs PIA, 9 features x 3 corners = 27 comparisons):
    difference of means, exact permutation p-value, 95 % bootstrap interval,
    Hedges' g, Benjamini-Hochberg adjustment, per-lap measurement error.
H1 (exploratory): within-driver lap-to-lap spread vs measurement error
    (Q and FP2 long runs), ICC(1) on Q laps with a bootstrap interval.

Inputs: results/05_pilot_features/features.csv and driver_summary.csv.
Outputs: results/06_pilot_stats/ (h2_tests.csv, h1_repeatability.csv,
summary.md, forest_plot.png, summary.json).

Run from the repo root, after committing docs/preregistration.md:
    .venv\\Scripts\\python.exe experiments\\06_pilot_stats.py
"""

import json
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from apextrace.plots import DRIVER_COLORS, TEXT_SECONDARY, apply_style
from apextrace.stats import (
    benjamini_hochberg,
    bootstrap_ci,
    hedges_g,
    icc_oneway,
    min_detectable_effect,
    min_permutation_p,
    permutation_test,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
FEATURES_CSV = REPO_ROOT / "results" / "05_pilot_features" / "features.csv"
DRIVER_SUMMARY_CSV = REPO_ROOT / "results" / "05_pilot_features" / "driver_summary.csv"
OUT_DIR = REPO_ROOT / "results" / "06_pilot_stats"
PREREGISTRATION = "docs/preregistration.md"

TESTED_FEATURES = ["brake_onset_m", "apex_m", "min_speed_kmh", "throttle_pickup_m", "full_throttle_m",
                   "entry_speed_kmh", "exit_speed_kmh", "mean_decel_ms2", "corner_time_s"]
CORNERS = ["T6", "T5", "T9"]
SEED = 2026
FP2_LONG_RUN_STINT = 4      # NOR and PIA medium long runs (Phase 1, check 6)


def preregistration_is_committed():
    """True if the preregistration file is in a commit and has no uncommitted changes."""
    in_history = subprocess.run(["git", "log", "--format=%H %ci", "-1", "--", PREREGISTRATION],
                                cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
    unchanged = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", PREREGISTRATION],
                               cwd=REPO_ROOT).returncode == 0
    return bool(in_history) and unchanged, in_history


def h2_tests(features, errors):
    rng = np.random.default_rng(SEED)
    q = features[(features["session"] == "Q") & (features["usable"])]
    rows = []
    for corner in CORNERS:
        for feature in TESTED_FEATURES:
            nor = q[(q["corner"] == corner) & (q["driver"] == "NOR")][feature].dropna().to_numpy()
            pia = q[(q["corner"] == corner) & (q["driver"] == "PIA")][feature].dropna().to_numpy()
            difference, p = permutation_test(nor, pia)
            low, high = bootstrap_ci(nor, pia, rng=rng, n_boot=10000)
            rows.append({"corner": corner, "feature": feature, "n_NOR": len(nor), "n_PIA": len(pia),
                         "difference_NOR_minus_PIA": difference, "ci95_low": low, "ci95_high": high,
                         "hedges_g": hedges_g(nor, pia), "p_permutation": p,
                         "min_possible_p": min_permutation_p(len(nor), len(pia)),
                         "min_detectable_d_80pct": min_detectable_effect(len(nor), len(pia)),
                         "per_lap_measurement_error": errors.get((corner, feature), np.nan)})
    table = pd.DataFrame(rows)
    table["p_bh_adjusted"] = benjamini_hochberg(table["p_permutation"].to_numpy())
    table["discovery"] = table["p_bh_adjusted"] <= 0.05
    return table


def h1_repeatability(features, errors):
    rng = np.random.default_rng(SEED + 1)
    usable = features[features["usable"]]
    rows = []
    for corner in CORNERS:
        for feature in TESTED_FEATURES:
            error = errors.get((corner, feature), np.nan)
            row = {"corner": corner, "feature": feature, "per_lap_measurement_error": error}
            for label, subset in [("Q", usable[usable["session"] == "Q"]),
                                  ("FP2_long_run", usable[(usable["session"] == "FP2")
                                                          & (usable["stint"] == FP2_LONG_RUN_STINT)])]:
                for driver in ["NOR", "PIA"]:
                    values = subset[(subset["corner"] == corner) & (subset["driver"] == driver)][feature].dropna()
                    sd = float(values.std(ddof=1)) if len(values) > 1 else np.nan
                    row[f"{label}_{driver}_n"] = len(values)
                    row[f"{label}_{driver}_sd"] = sd
                    row[f"{label}_{driver}_sd_over_error"] = sd / error if error and np.isfinite(error) else np.nan
            q = usable[(usable["session"] == "Q") & (usable["corner"] == corner)][["driver", feature]].dropna()
            row["icc_Q"] = icc_oneway(q[feature].to_numpy(), q["driver"].to_numpy())
            boot = []
            for _ in range(2000):
                resampled_values, resampled_groups = [], []
                for driver in ["NOR", "PIA"]:
                    values = q[q["driver"] == driver][feature].to_numpy()
                    picked = rng.choice(values, size=len(values))
                    resampled_values.extend(picked)
                    resampled_groups.extend([driver] * len(values))
                boot.append(icc_oneway(np.array(resampled_values), np.array(resampled_groups)))
            boot = np.array(boot)
            boot = boot[np.isfinite(boot)]
            row["icc_Q_ci95_low"] = float(np.percentile(boot, 2.5)) if len(boot) else np.nan
            row["icc_Q_ci95_high"] = float(np.percentile(boot, 97.5)) if len(boot) else np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def forest_plot(h2):
    groups = [("Distances (m from marker)", ["brake_onset_m", "apex_m", "throttle_pickup_m", "full_throttle_m"]),
              ("Speeds (km/h)", ["entry_speed_kmh", "min_speed_kmh", "exit_speed_kmh"]),
              ("Mean deceleration (m/s²)", ["mean_decel_ms2"]),
              ("Corner time (s)", ["corner_time_s"])]
    fig, axes = plt.subplots(1, 4, figsize=(17, 6), gridspec_kw={"width_ratios": [4, 3, 1.4, 1.4]})
    for ax, (title, names) in zip(axes, groups):
        labels = []
        y = 0
        for feature in names:
            for corner in CORNERS:
                row = h2[(h2["feature"] == feature) & (h2["corner"] == corner)].iloc[0]
                ax.plot([row["ci95_low"], row["ci95_high"]], [y, y], color=TEXT_SECONDARY, linewidth=1.5)
                ax.plot(row["difference_NOR_minus_PIA"], y, "o", color=DRIVER_COLORS["NOR"], markersize=6)
                labels.append(f"{feature.replace('_m', '').replace('_kmh', '').replace('_ms2', '').replace('_s', '')} {corner}")
                y += 1
        ax.axvline(0, color=TEXT_SECONDARY, linewidth=0.8)
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=8)
        ax.invert_yaxis()
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("NOR − PIA (95 % bootstrap interval)", fontsize=9)
    fig.suptitle("Pilot H2, 2024 Abu Dhabi qualifying: teammate differences with intervals "
                 "(2–4 laps per driver: intervals are rough)", x=0.0, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "forest_plot.png", bbox_inches="tight")
    plt.close(fig)


def main():
    committed, commit_info = preregistration_is_committed()
    if not committed:
        print("STOP: docs/preregistration.md must be committed (and unchanged) before the tests are run.")
        print("Commit it in GitHub Desktop, then run this script again.")
        sys.exit(1)
    print(f"preregistration committed: {commit_info}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    apply_style()
    features = pd.read_csv(FEATURES_CSV)
    summary = pd.read_csv(DRIVER_SUMMARY_CSV)
    errors = {}
    for _, row in summary.drop_duplicates(["corner", "feature"]).iterrows():
        errors[(row["corner"], row["feature"])] = row["measurement_error_per_lap"]

    h2 = h2_tests(features, errors)
    h2.to_csv(OUT_DIR / "h2_tests.csv", index=False, float_format="%.4f")
    h1 = h1_repeatability(features, errors)
    h1.to_csv(OUT_DIR / "h1_repeatability.csv", index=False, float_format="%.4f")
    forest_plot(h2)

    print("\n--- H2 (qualifying): NOR - PIA ---")
    for _, r in h2.iterrows():
        print(f"{r['corner']} {r['feature']:18s} n {r['n_NOR']}/{r['n_PIA']}  diff {r['difference_NOR_minus_PIA']:+8.2f}  "
              f"95% CI [{r['ci95_low']:+7.2f}, {r['ci95_high']:+7.2f}]  g {r['hedges_g']:+5.2f}  "
              f"p {r['p_permutation']:.3f} (min {r['min_possible_p']:.3f})  BH {r['p_bh_adjusted']:.3f}")
    print(f"discoveries after Benjamini-Hochberg: {int(h2['discovery'].sum())} of {len(h2)}")

    print("\n--- H1: lap-to-lap SD / per-lap measurement error, and ICC (Q) ---")
    for _, r in h1.iterrows():
        print(f"{r['corner']} {r['feature']:18s} Q: NOR {r['Q_NOR_sd_over_error']:5.2f} PIA {r['Q_PIA_sd_over_error']:5.2f} | "
              f"FP2 long run: NOR {r['FP2_long_run_NOR_sd_over_error']:5.2f} PIA {r['FP2_long_run_PIA_sd_over_error']:5.2f} | "
              f"ICC {r['icc_Q']:+.2f} [{r['icc_Q_ci95_low']:+.2f}, {r['icc_Q_ci95_high']:+.2f}]")

    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump({"preregistration_commit": commit_info, "discoveries": int(h2["discovery"].sum()),
                   "h2": h2.to_dict(orient="records"), "h1": h1.to_dict(orient="records")},
                  file, indent=1, default=float)
    print(f"\nSaved results to {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

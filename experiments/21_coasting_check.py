"""Coasting check: does the brake-onset estimator still work when the car is already slowing?

In 2026 a car may lift and coast or "superclip" (harvest at full throttle) before the
brake goes on (docs/regulations_2026.md). Our brake-onset estimator looks for the bend in
the speed curve inside the interval where the brake channel switches on. If the car is
already slowing, that bend is smaller. Scenarios and the decision rule were fixed before
this was run (docs/decisions.md, 2026-11-02 and 2026-11-04):

  rule: root-mean-square error <= 8.4 m (twice Phase 2's 4.2 m) for every corner type and
        scenario -> nothing changes; any one above -> Part C adds a secondary variant
        without the three braking features. The primary test is unchanged either way.

Scenarios (1,000 corners per corner type each; real-feed sampling without gaps, exactly
as in experiments/03_synthetic_errors.py):
  1 Phase 2 car                 no pre-braking phase (pipeline check: should give ~4.2 / 3.4 / 4.2 m)
  2 lift and coast              throttle closed, brake off, 0.3-1.0 s, harvesting 0-350 kW
  3 superclipping               full throttle, 0.5-2.0 s, 400 kW engine minus 100-350 kW harvested
  4 2026-like car               downforce x 0.7, drag x 0.45, no pre-braking phase
  5 2026-like + lift and coast
  6 2026-like + superclipping
For scale, "the middle of the off->on interval" (no speed information) is computed too.

Outputs in results/21_coasting_check/: error_table.csv, summary.json, coasting_check.png.
Run from the repo root (a few minutes):
    .venv\\Scripts\\python.exe experiments\\21_coasting_check.py
"""

import json
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from apextrace.events import brake_onset_breakpoint, brake_onset_midpoint
from apextrace.plots import SERIES, TEXT_SECONDARY, apply_style
from apextrace.synthetic import CORNER_TYPES, degrade_like_feed, load_interval_distribution, make_true_corner, \
    random_corner_params

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "results" / "21_coasting_check"
HISTOGRAM = REPO_ROOT / "results" / "01_data_pilot" / "interval_histogram.csv"
PHASE2_TABLE = REPO_ROOT / "results" / "03_synthetic_errors" / "error_table.csv"
LAPS_PER_CELL = 1000
SEED = 20261104
NO_GAPS_S = 0.6                 # as in Phase 2: corner windows with a feed gap are excluded
THRESHOLD_M = 8.4               # the rule fixed on 2026-11-02
CAR_2026 = {"aero_scale": 0.7, "drag_scale": 0.45}

SCENARIOS = ["Phase 2 car", "lift and coast", "superclipping", "2026-like car",
             "2026-like + lift and coast", "2026-like + superclipping"]


def scenario_params(scenario, corner_type, rng):
    """One corner's parameters: the Phase 2 driver variation plus the scenario's extras.

    Example: "lift and coast" might draw 0.62 s of coasting with 140 kW harvested.
    """
    params = random_corner_params(corner_type, rng)
    if scenario.startswith("2026-like"):
        params.update(CAR_2026)
    if scenario.endswith("lift and coast"):
        params.update({"pre_brake": "lift", "pre_brake_s": rng.uniform(0.3, 1.0), "harvest_kw": rng.uniform(0, 350)})
    if scenario.endswith("superclipping"):
        params.update({"pre_brake": "superclip", "pre_brake_s": rng.uniform(0.5, 2.0),
                       "harvest_kw": rng.uniform(100, 350)})
    return params


def onset_errors(truth, samples):
    """Errors (m, estimate - truth, along the true track) of the chosen estimator and of the
    no-information reference (middle of the off->on interval)."""
    t = samples["time_s"]

    def metres(time_s):
        return float(np.interp(time_s, truth["time_s"], truth["distance_m"]))

    true_onset = truth["events"]["brake_onset"]["d"]
    chosen = brake_onset_breakpoint(t, samples["speed_kmh"], samples["brake"], within_brake_interval=True)
    middle = brake_onset_midpoint(t, samples["brake"])
    return metres(chosen) - true_onset, metres(middle) - true_onset


def summarise(errors):
    errors = np.asarray(errors)
    return {"bias_m": float(np.mean(errors)), "std_m": float(np.std(errors, ddof=1)),
            "rmse_m": float(np.sqrt(np.mean(errors ** 2))), "p95_abs_m": float(np.percentile(np.abs(errors), 95))}


def figure(table, phase2):
    """Error per scenario (rows) and corner type (colours), with the decision threshold."""
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    rows = list(reversed(SCENARIOS))
    for k, corner_type in enumerate(CORNER_TYPES):
        part = table[table["corner_type"] == corner_type].set_index("scenario").loc[rows]
        positions = np.arange(len(rows)) - (k - 1) * 0.22   # same top-to-bottom order as the legend
        ax.scatter(part["chosen_rmse_m"], positions, s=48, color=SERIES[k], edgecolors="white", linewidths=1.0,
                   zorder=3, label=corner_type.replace("_", " "))
    ax.axvline(THRESHOLD_M, color=TEXT_SECONDARY, linestyle="--", linewidth=1)
    ax.text(THRESHOLD_M + 0.1, len(rows) - 0.55, "decision threshold\n8.4 m", fontsize=8, color=TEXT_SECONDARY,
            va="top")
    ax.axvline(phase2, color=TEXT_SECONDARY, linestyle=":", linewidth=1)
    ax.text(phase2 + 0.1, -0.45, f"Phase 2: {phase2:.1f} m", fontsize=8, color=TEXT_SECONDARY)
    ax.set_yticks(np.arange(len(rows)))
    ax.set_yticklabels(rows, fontsize=8.5)
    ax.set_xlim(0, 10)
    ax.set_xlabel("brake-onset error, root-mean-square (m)")
    ax.set_title("Brake-onset error when the car is already slowing before the brake (1,000 synthetic corners each)",
                 fontsize=9.5, pad=10)
    ax.legend(loc="lower left", fontsize=8, frameon=False)    # no dot falls below 2.5 m
    fig.savefig(OUT_DIR / "coasting_check.png", bbox_inches="tight")
    plt.close(fig)


def main():
    laps = int(sys.argv[1]) if len(sys.argv) > 1 else LAPS_PER_CELL   # a smaller number only for a quick trial
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    apply_style()
    intervals, probs = load_interval_distribution(HISTOGRAM)

    rows = []
    for index, scenario in enumerate(SCENARIOS):
        rng = np.random.default_rng(SEED + index)
        start = time.perf_counter()
        for corner_type in CORNER_TYPES:
            chosen, middle, slowing = [], [], []
            for _ in range(laps):
                truth = make_true_corner(scenario_params(scenario, corner_type, rng))
                samples = degrade_like_feed(truth, intervals, probs, rng, max_interval_s=NO_GAPS_S)
                error_chosen, error_middle = onset_errors(truth, samples)
                chosen.append(error_chosen)
                middle.append(error_middle)
                params = truth["params"]
                if params.get("pre_brake"):
                    t = truth["time_s"]
                    onset_t = truth["events"]["brake_onset"]["t"]
                    window = (t >= onset_t - params["pre_brake_s"]) & (t < onset_t)
                    slowing.append(-float(np.mean(truth["accel_ms2"][window])))
            row = {"scenario": scenario, "corner_type": corner_type, "laps": laps}
            row.update({f"chosen_{k}": v for k, v in summarise(chosen).items()})
            row.update({f"middle_{k}": v for k, v in summarise(middle).items()})
            row["mean_decel_before_brake_ms2"] = float(np.mean(slowing)) if slowing else 0.0
            rows.append(row)
        print(f"{scenario}: {3 * laps} corners in {time.perf_counter() - start:.0f} s", flush=True)

    table = pd.DataFrame(rows)
    table.to_csv(OUT_DIR / "error_table.csv", index=False, float_format="%.3f")
    print(table[["scenario", "corner_type", "chosen_rmse_m", "chosen_bias_m", "middle_rmse_m",
                 "mean_decel_before_brake_ms2"]].round(2).to_string(index=False))

    phase2 = pd.read_csv(PHASE2_TABLE)
    phase2_rmse = phase2[(phase2["feature"] == "brake_onset_m") & (phase2["scenario"] == "real")
                         & (phase2["estimator"] == "speed breakpoint inside off-on interval")]
    phase2_rmse = dict(zip(phase2_rmse["corner_type"], phase2_rmse["rmse"]))
    worst = table.loc[table["chosen_rmse_m"].idxmax()]
    summary = {"laps_per_cell": laps, "seed": SEED, "threshold_m": THRESHOLD_M, "phase2_rmse_m": phase2_rmse,
               "worst": {"scenario": worst["scenario"], "corner_type": worst["corner_type"],
                         "rmse_m": float(worst["chosen_rmse_m"])},
               "any_above_threshold": bool((table["chosen_rmse_m"] > THRESHOLD_M).any()),
               "consequence_add_variant_without_braking_features": bool((table["chosen_rmse_m"] > THRESHOLD_M).any()),
               "cells": rows}
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=1)
    figure(table, phase2_rmse["heavy_braking"])
    print(f"\nworst: {worst['scenario']} / {worst['corner_type']}: {worst['chosen_rmse_m']:.2f} m "
          f"(threshold {THRESHOLD_M} m) -> add variant without braking features: "
          f"{summary['consequence_add_variant_without_braking_features']}")


if __name__ == "__main__":
    main()

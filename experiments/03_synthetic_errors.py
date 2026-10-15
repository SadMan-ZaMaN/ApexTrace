"""Phase 2 Monte Carlo: how accurately can each corner feature be measured from the real feed?

For each of the three corner types (like T6, T5, T9) we simulate 1000 laps
with known truth, degrade each one exactly like the live feed (real interval
distribution, no feed gap inside the corner, 1 km/h rounding, on/off brake),
run every estimator, and compare with the truth.

"Monte Carlo" = answering a question by simulating it many times with
random inputs and looking at the spread of the results.

Outputs in results/03_synthetic_errors/:
  error_table.csv     one row per (corner type, feature, estimator, sampling):
                      bias (mean error), std (spread), RMSE, 95th percentile of |error|
  error_table.png     bias +- std per estimator
  averaging.csv/.png  the "dithering" check: does averaging N laps shrink the
                      error like 1/sqrt(N)?
  summary.json

Sampling scenarios:
  real        intervals drawn from the real distribution (0.16-0.56 s, no gaps)
  regular     every interval = the real mean (0.265 s): what you'd assume
              if you believed "3.77 Hz"; shows what irregular sampling costs

Errors in distance are measured along the TRUE track (time error converted
with the true distance), so they contain timing error only; the error of the
distance axis itself (integration drift) is handled by alignment in Phase 3.

Run from the repo root (takes a few minutes):
    .venv\\Scripts\\python.exe experiments\\03_synthetic_errors.py
"""

import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from apextrace.events import (
    apex_lowest_sample,
    apex_parabola,
    brake_onset_breakpoint,
    brake_onset_first_on,
    brake_onset_midpoint,
    crossing_first_sample,
    crossing_interpolated,
    last_brake_on_time,
    peak_decel_naive,
    peak_decel_smoothed,
)
from apextrace.plots import SERIES, TEXT_SECONDARY, apply_style
from apextrace.synthetic import (
    CORNER_TYPES,
    degrade_like_feed,
    load_interval_distribution,
    make_true_corner,
    random_corner_params,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "results" / "03_synthetic_errors"
HISTOGRAM = REPO_ROOT / "results" / "01_data_pilot" / "interval_histogram.csv"

LAPS_PER_TYPE = 1000
SEED = 20261016
NO_GAPS_S = 0.6                       # corner windows with a feed gap are excluded (decisions.md)
DECEL_CUTOFFS_HZ = [0.5, 0.75, 1.0, 1.25, 1.5]
ENTRY_POINT_BEFORE_APEX_M = 200.0     # "entry speed" = speed 200 m before the apex (on the straight)
EXIT_POINT_AFTER_APEX_M = 150.0       # "exit speed" = speed 150 m after the apex


def measure_one_lap(truth, samples):
    """Every estimator on one degraded lap; returns {(feature, estimator): error}."""
    ev = truth["events"]
    t = samples["time_s"]
    speed = samples["speed_kmh"]
    throttle = samples["throttle_pct"]
    brake = samples["brake"]

    def metres(time_s):
        """Distance along the true track at a given time."""
        return float(np.interp(time_s, truth["time_s"], truth["distance_m"]))

    def time_at(distance_m):
        return float(np.interp(distance_m, truth["distance_m"], truth["time_s"]))

    errors = {}
    # brake onset (m)
    true_onset = ev["brake_onset"]["d"]
    errors[("brake_onset_m", "first on sample")] = metres(brake_onset_first_on(t, brake)) - true_onset
    errors[("brake_onset_m", "middle of off-on interval")] = metres(brake_onset_midpoint(t, brake)) - true_onset
    errors[("brake_onset_m", "speed breakpoint")] = metres(brake_onset_breakpoint(t, speed, brake)) - true_onset
    errors[("brake_onset_m", "speed breakpoint inside off-on interval")] = \
        metres(brake_onset_breakpoint(t, speed, brake, within_brake_interval=True)) - true_onset

    # apex: position (m) and minimum speed (km/h)
    t_low, v_low = apex_lowest_sample(t, speed)
    t_p3, v_p3 = apex_parabola(t, speed, points=3)
    t_p5, v_p5 = apex_parabola(t, speed, points=5)
    for name, (t_est, v_est) in [("lowest sample", (t_low, v_low)),
                                 ("parabola 3 points", (t_p3, v_p3)),
                                 ("parabola 5 points", (t_p5, v_p5))]:
        errors[("apex_m", name)] = metres(t_est) - ev["apex"]["d"]
        errors[("min_speed_kmh", name)] = v_est - ev["apex"]["speed_kmh"]

    # throttle pickup (10 %) and full throttle (99 %), searched after the last brake-on sample
    start = last_brake_on_time(t, brake)
    errors[("throttle_pickup_m", "first sample >= 10 %")] = \
        metres(crossing_first_sample(t, throttle, 10.0, start)) - ev["throttle_pickup"]["d"]
    errors[("throttle_pickup_m", "interpolated crossing")] = \
        metres(crossing_interpolated(t, throttle, 10.0, start)) - ev["throttle_pickup"]["d"]
    errors[("full_throttle_m", "first sample >= 99 %")] = \
        metres(crossing_first_sample(t, throttle, 99.0, start)) - ev["full_throttle"]["d"]
    errors[("full_throttle_m", "interpolated crossing")] = \
        metres(crossing_interpolated(t, throttle, 99.0, start)) - ev["full_throttle"]["d"]

    # speed at fixed points (entry and exit): interpolate the samples at the true passing time
    for feature, offset in [("entry_speed_kmh", -ENTRY_POINT_BEFORE_APEX_M),
                            ("exit_speed_kmh", EXIT_POINT_AFTER_APEX_M)]:
        passing = time_at(ev["apex"]["d"] + offset)
        true_value = float(np.interp(passing, truth["time_s"], truth["speed_kmh"]))
        errors[(feature, "linear interpolation")] = float(np.interp(passing, t, speed)) - true_value

    # peak deceleration (m/s^2)
    errors[("peak_decel_ms2", "largest drop between samples")] = peak_decel_naive(t, speed) - ev["peak_decel_ms2"]
    for cutoff in DECEL_CUTOFFS_HZ:
        errors[("peak_decel_ms2", f"zero-phase {cutoff} Hz then derivative")] = \
            peak_decel_smoothed(t, speed, cutoff_hz=cutoff) - ev["peak_decel_ms2"]
    return errors


def summarise(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    return {
        "n": int(len(values)),
        "bias": float(np.mean(values)),
        "std": float(np.std(values)),
        "rmse": float(np.sqrt(np.mean(values ** 2))),
        "p95_abs": float(np.percentile(np.abs(values), 95)),
    }


def run_monte_carlo(intervals, probs):
    rng = np.random.default_rng(SEED)
    regular = np.array([float(np.sum(intervals * probs))])  # the mean interval, always
    records = {}
    for corner_type in CORNER_TYPES:
        start = time.perf_counter()
        for _ in range(LAPS_PER_TYPE):
            truth = make_true_corner(random_corner_params(corner_type, rng))
            scenarios = {
                "real": degrade_like_feed(truth, intervals, probs, rng, max_interval_s=NO_GAPS_S),
                "regular": degrade_like_feed(truth, regular, np.array([1.0]), rng),
            }
            for scenario, samples in scenarios.items():
                for (feature, estimator), error in measure_one_lap(truth, samples).items():
                    records.setdefault((corner_type, feature, estimator, scenario), []).append(error)
        print(f"{corner_type}: {LAPS_PER_TYPE} laps in {time.perf_counter() - start:.0f} s", flush=True)
    return records


def averaging_check(records):
    """Std of the AVERAGE error over N laps, compared with std / sqrt(N).

    If the sampling phase is random from lap to lap, single-lap errors are
    independent, and averaging N laps shrinks the random part like 1/sqrt(N)
    (the same reason dithering works). The bias does not shrink.
    """
    rng = np.random.default_rng(SEED + 1)
    rows = []
    for (corner_type, feature, estimator, scenario), errors in records.items():
        if scenario != "real" or feature != "brake_onset_m":
            continue
        errors = np.asarray(errors)
        for n in [1, 2, 4, 8, 16]:
            means = []
            for _ in range(2000):
                means.append(np.mean(rng.choice(errors, size=n, replace=False)))
            rows.append({"corner_type": corner_type, "estimator": estimator, "laps_averaged": n,
                         "std_of_mean_m": float(np.std(means)),
                         "predicted_std_over_sqrt_n_m": float(np.std(errors) / np.sqrt(n)),
                         "bias_m": float(np.mean(errors))})
    return pd.DataFrame(rows)


def plot_error_table(table):
    features = [("brake_onset_m", "Brake onset (m)"), ("apex_m", "Apex position (m)"),
                ("min_speed_kmh", "Minimum speed (km/h)"), ("throttle_pickup_m", "Throttle pickup, 10 % (m)"),
                ("full_throttle_m", "Full throttle, 99 % (m)"), ("peak_decel_ms2", "Peak deceleration (m/s²)")]
    real = table[table["scenario"] == "real"]
    fig, axes = plt.subplots(3, 2, figsize=(14, 13))
    for ax, (feature, title) in zip(axes.flat, features):
        subset = real[real["feature"] == feature]
        estimators = list(dict.fromkeys(subset["estimator"]))
        for k, corner_type in enumerate(CORNER_TYPES):
            rows = subset[subset["corner_type"] == corner_type].set_index("estimator").loc[estimators]
            y = np.arange(len(estimators)) + (k - 1) * 0.25
            ax.errorbar(rows["bias"], y, xerr=rows["std"], fmt="o", color=SERIES[k], markersize=5,
                        capsize=3, label=corner_type.replace("_", " "))
        ax.axvline(0, color=TEXT_SECONDARY, linewidth=0.8)
        ax.set_yticks(np.arange(len(estimators)))
        ax.set_yticklabels(estimators, fontsize=9)
        ax.invert_yaxis()
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("error: bias (dot) +- 1 std (bar)")
    axes.flat[0].legend(fontsize=9, loc="lower right")
    fig.suptitle(f"Measurement error of each estimator, {LAPS_PER_TYPE} synthetic laps per corner type, "
                 "real feed sampling", x=0.0, ha="left", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "error_table.png", bbox_inches="tight")
    plt.close(fig)


def plot_averaging(averaging):
    fig, ax = plt.subplots(figsize=(8, 4.6))
    estimators = ["middle of off-on interval", "speed breakpoint inside off-on interval"]
    for k, estimator in enumerate(estimators):
        rows = averaging[(averaging["corner_type"] == "heavy_braking") & (averaging["estimator"] == estimator)]
        ax.plot(rows["laps_averaged"], rows["std_of_mean_m"], "o-", color=SERIES[k], label=f"{estimator}: measured")
        ax.plot(rows["laps_averaged"], rows["predicted_std_over_sqrt_n_m"], "--", color=SERIES[k],
                label="std / sqrt(N)")
    ax.set_xscale("log", base=2)
    ax.set_xlabel("Laps averaged (N)")
    ax.set_ylabel("Spread of the averaged brake point (m)")
    ax.set_title("Averaging laps shrinks the random error like 1/sqrt(N) (heavy braking)", pad=12)
    ax.legend(fontsize=8)
    fig.savefig(OUT_DIR / "averaging.png", bbox_inches="tight")
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    apply_style()
    intervals, probs = load_interval_distribution(HISTOGRAM)

    records = run_monte_carlo(intervals, probs)
    rows = []
    for (corner_type, feature, estimator, scenario), errors in records.items():
        row = {"corner_type": corner_type, "feature": feature, "estimator": estimator, "scenario": scenario}
        row.update(summarise(errors))
        rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(OUT_DIR / "error_table.csv", index=False, float_format="%.3f")
    plot_error_table(table)

    averaging = averaging_check(records)
    averaging.to_csv(OUT_DIR / "averaging.csv", index=False, float_format="%.3f")
    plot_averaging(averaging)

    real = table[table["scenario"] == "real"]
    print("\n--- Error table, real sampling (bias / std / RMSE / 95 % of |error| below) ---")
    for feature in real["feature"].unique():
        print(f"\n{feature}")
        for _, row in real[real["feature"] == feature].iterrows():
            print(f"  {row['corner_type']:14s} {row['estimator']:42s} bias {row['bias']:+7.2f}  "
                  f"std {row['std']:6.2f}  rmse {row['rmse']:6.2f}  p95 {row['p95_abs']:6.2f}")

    print("\n--- Irregular vs regular sampling: brake onset, middle of off-on interval (std, m) ---")
    for corner_type in CORNER_TYPES:
        pick = table[(table["corner_type"] == corner_type) & (table["feature"] == "brake_onset_m")
                     & (table["estimator"] == "middle of off-on interval")].set_index("scenario")
        print(f"  {corner_type:14s} real {pick.loc['real', 'std']:5.2f}   regular {pick.loc['regular', 'std']:5.2f}")

    print("\n--- Averaging N laps (heavy braking, brake onset) ---")
    print(averaging[averaging["corner_type"] == "heavy_braking"].to_string(index=False))

    summary = {"laps_per_type": LAPS_PER_TYPE, "seed": SEED, "no_gaps_max_interval_s": NO_GAPS_S,
               "rows": rows}
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=1)
    print(f"\nSaved results to {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

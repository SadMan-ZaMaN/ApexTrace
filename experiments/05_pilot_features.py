"""Phase 4: corner features for Norris and Piastri at T6, T5, T9 (2024 Abu Dhabi), DESCRIPTIVE ONLY.

For every usable (lap, corner) pair (no feed gap in the window, Phase 3):
features.corner_features() on the raw samples, with the fused track
coordinate. Then, per driver: mean, lap-to-lap spread, standard error, next
to the measurement error from the Phase 2 Monte Carlo. No hypothesis tests
here: those are preregistered first (docs/preregistration.md, Phase 5).

Words:
  lap-to-lap std  how much the driver's value changes from lap to lap
                  (real variation + measurement error)
  standard error  how uncertain the driver's MEAN is: std / sqrt(n laps)
  measurement error (per lap)  from the Monte Carlo (estimator) combined
                  with the alignment offset noise (1.15 m), for distances

Outputs in results/05_pilot_features/: features.csv, driver_summary.csv,
summary.md (the tables the write-up quotes), corner_events_Q.png,
features_Q.png, summary.json.

Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\05_pilot_features.py
"""

import json
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from apextrace.corners import (corner_positions, fuse_window_coordinate, has_feed_gap,
                               samples_in_window, window_bounds)
from apextrace.data_loading import load_session, select_laps
from apextrace.features import FEATURES, corner_features
from apextrace.plots import DRIVER_COLORS, TEXT_SECONDARY, apply_style
from apextrace.track import lap_on_track, reference_path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "results" / "05_pilot_features"
ERROR_TABLE = REPO_ROOT / "results" / "03_synthetic_errors" / "error_table.csv"
ALIGNMENT_SUMMARY = REPO_ROOT / "results" / "04_alignment" / "summary.json"

YEAR, EVENT = 2024, "Abu Dhabi"
SESSIONS = ["Q", "FP2"]
DRIVERS = ["NOR", "PIA"]
PILOT = {"T6": "heavy_braking", "T5": "medium", "T9": "fast"}   # decisions.md, 2026-10-16

# Which Monte Carlo row gives each feature's per-lap measurement error
MC_ROWS = {
    "brake_onset_m": ("brake_onset_m", "speed breakpoint inside off-on interval"),
    "min_speed_kmh": ("min_speed_kmh", "parabola 3 points"),
    "apex_m": ("apex_m", "parabola 3 points"),
    "throttle_pickup_m": ("throttle_pickup_m", "interpolated crossing"),
    "full_throttle_m": ("full_throttle_m", "interpolated crossing"),
    "entry_speed_kmh": ("entry_speed_kmh", "linear interpolation"),
    "exit_speed_kmh": ("exit_speed_kmh", "linear interpolation"),
}
DISTANCE_FEATURES = {"brake_onset_m", "apex_m", "throttle_pickup_m", "full_throttle_m"}
SHOWN = ["brake_onset_m", "min_speed_kmh", "apex_m", "throttle_pickup_m", "entry_speed_kmh",
         "exit_speed_kmh", "mean_decel_ms2", "corner_time_s"]


def measurement_errors():
    """{(corner, feature): (bias, per-lap std)}, from the Monte Carlo plus alignment noise."""
    table = pd.read_csv(ERROR_TABLE)
    alignment_noise = json.loads(ALIGNMENT_SUMMARY.read_text(encoding="utf-8"))["fusion_offset_noise_m"]
    errors = {}
    for corner, corner_type in PILOT.items():
        for feature, (mc_feature, estimator) in MC_ROWS.items():
            row = table[(table["corner_type"] == corner_type) & (table["feature"] == mc_feature)
                        & (table["estimator"] == estimator) & (table["scenario"] == "real")].iloc[0]
            std = float(row["std"])
            if feature in DISTANCE_FEATURES:
                std = float(np.sqrt(std ** 2 + alignment_noise ** 2))
            errors[(corner, feature)] = (float(row["bias"]), std)
    return errors, alignment_noise


def compute_features():
    logging.getLogger("fastf1").setLevel(logging.WARNING)
    sessions = {name: load_session(YEAR, EVENT, name) for name in SESSIONS}
    reference = reference_path(sessions["Q"].laps.pick_fastest())
    circuit = sessions["Q"].get_circuit_info().corners
    names = [f"T{int(n)}{l if isinstance(l, str) else ''}" for n, l in zip(circuit["Number"], circuit["Letter"])]
    all_s = dict(zip(names, corner_positions(circuit["X"], circuit["Y"], circuit["Distance"], reference)))

    rows, traces = [], []
    for session_name, session in sessions.items():
        for driver in DRIVERS:
            kept, _ = select_laps(session.laps.pick_drivers(driver))
            for _, lap in kept.iterrows():
                samples = lap_on_track(lap, reference)
                for corner in PILOT:
                    start, end = window_bounds(all_s[corner])
                    window = samples_in_window(samples, start, end)
                    base = {"session": session_name, "driver": driver, "lap": int(lap["LapNumber"]),
                            "stint": int(lap["Stint"]), "compound": lap["Compound"],
                            "tyre_life": float(lap["TyreLife"]), "lap_time_s": lap["LapTime"].total_seconds(),
                            "corner": corner}
                    if window is None or has_feed_gap(window):
                        rows.append({**base, "usable": False, "reason": "feed gap in window"})
                        continue
                    fused, offset, _, _ = fuse_window_coordinate(samples, window)
                    features = corner_features(window, fused, all_s[corner])
                    rows.append({**base, "usable": True, "reason": "", "fusion_offset_m": offset, **features})
                    traces.append({**base, "relative_s": fused - all_s[corner],
                                   "speed": window["speed_kmh"], "features": features})
    return pd.DataFrame(rows), traces, all_s


def driver_summary(table, errors):
    rows = []
    usable = table[table["usable"]]
    for (session_name, corner, driver), group in usable.groupby(["session", "corner", "driver"]):
        for feature in FEATURES:
            values = group[feature].dropna().to_numpy()
            if len(values) == 0:
                continue
            bias, per_lap_error = errors.get((corner, feature), (np.nan, np.nan))
            rows.append({"session": session_name, "corner": corner, "driver": driver, "feature": feature,
                         "n": len(values), "mean": float(np.mean(values)),
                         "lap_to_lap_std": float(np.std(values, ddof=1)) if len(values) > 1 else np.nan,
                         "standard_error": float(np.std(values, ddof=1) / np.sqrt(len(values))) if len(values) > 1 else np.nan,
                         "measurement_bias": bias, "measurement_error_per_lap": per_lap_error,
                         "values": " ".join(f"{v:.1f}" for v in values)})
    return pd.DataFrame(rows)


def teammate_differences(summary):
    """NOR mean - PIA mean per (session, corner, feature), with the combined standard error."""
    rows = []
    for (session_name, corner, feature), group in summary.groupby(["session", "corner", "feature"]):
        by_driver = group.set_index("driver")
        if not all(d in by_driver.index for d in DRIVERS):
            continue
        nor, pia = by_driver.loc["NOR"], by_driver.loc["PIA"]
        se = float(np.sqrt(nor["standard_error"] ** 2 + pia["standard_error"] ** 2))
        rows.append({"session": session_name, "corner": corner, "feature": feature,
                     "NOR_mean": nor["mean"], "PIA_mean": pia["mean"], "n_NOR": int(nor["n"]), "n_PIA": int(pia["n"]),
                     "difference_NOR_minus_PIA": float(nor["mean"] - pia["mean"]),
                     "combined_standard_error": se,
                     "measurement_error_per_lap": nor["measurement_error_per_lap"]})
    return pd.DataFrame(rows)


def write_summary_markdown(differences, summary, alignment_noise):
    lines = ["# Pilot features: Norris vs Piastri, 2024 Abu Dhabi (generated by experiments/05_pilot_features.py)", "",
             f"Alignment offset noise used for distance features: {alignment_noise:.2f} m.", "",
             "Distances are metres from the corner marker (negative = before it). "
             "Difference = NOR mean − PIA mean. SE = combined standard error of that difference. "
             "Per-lap error = measurement error of one lap (Monte Carlo + alignment).", ""]
    for session_name in SESSIONS:
        lines += [f"## {session_name}", "",
                  "| Corner | Feature | NOR mean (n) | PIA mean (n) | Difference | SE | Per-lap error |",
                  "|---|---|---|---|---|---|---|"]
        subset = differences[differences["session"] == session_name]
        for corner in PILOT:
            for feature in SHOWN:
                row = subset[(subset["corner"] == corner) & (subset["feature"] == feature)]
                if row.empty:
                    continue
                r = row.iloc[0]
                per_lap = "" if np.isnan(r["measurement_error_per_lap"]) else f"{r['measurement_error_per_lap']:.2f}"
                lines.append(f"| {corner} | {feature} | {r['NOR_mean']:.2f} ({r['n_NOR']}) | {r['PIA_mean']:.2f} ({r['n_PIA']}) "
                             f"| {r['difference_NOR_minus_PIA']:+.2f} | {r['combined_standard_error']:.2f} | {per_lap} |")
        lines.append("")
    lines += ["## Lap-to-lap spread vs measurement error (per driver)", "",
              "| Session | Corner | Driver | Feature | n | Lap-to-lap std | Per-lap measurement error | Values |",
              "|---|---|---|---|---|---|---|---|"]
    for _, r in summary[summary["feature"].isin(["brake_onset_m", "min_speed_kmh", "throttle_pickup_m"])].iterrows():
        std = "" if np.isnan(r["lap_to_lap_std"]) else f"{r['lap_to_lap_std']:.2f}"
        err = "" if np.isnan(r["measurement_error_per_lap"]) else f"{r['measurement_error_per_lap']:.2f}"
        lines.append(f"| {r['session']} | {r['corner']} | {r['driver']} | {r['feature']} | {r['n']} | {std} | {err} | {r['values']} |")
    (OUT_DIR / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def plot_corner_events(traces):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    for ax, corner in zip(axes, PILOT):
        for trace in traces:
            if trace["session"] != "Q" or trace["corner"] != corner:
                continue
            color = DRIVER_COLORS[trace["driver"]]
            ax.plot(trace["relative_s"], trace["speed"], "-o", markersize=2.2, linewidth=1.0, alpha=0.75, color=color)
            f = trace["features"]
            for key, marker in [("brake_onset_m", "v"), ("apex_m", "o"), ("throttle_pickup_m", "s")]:
                if np.isfinite(f[key]):
                    y = np.interp(f[key], trace["relative_s"], trace["speed"])
                    ax.plot(f[key], y, marker, markersize=8, markerfacecolor="white", markeredgecolor=color,
                            markeredgewidth=1.6)
        ax.set_xlim(-300, 200)
        ax.set_title(f"{corner}: ▽ brake onset, ○ apex, □ throttle 10 %", fontsize=10)
        ax.set_xlabel("Metres from the corner marker")
    axes[0].set_ylabel("Speed (km/h)")
    for driver in DRIVERS:
        axes[0].plot([], [], color=DRIVER_COLORS[driver], label=driver)
    axes[0].legend(fontsize=9, loc="lower left")
    fig.suptitle("2024 Abu Dhabi qualifying, usable laps, events located between samples",
                 x=0.0, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "corner_events_Q.png", bbox_inches="tight")
    plt.close(fig)


def plot_features(table, errors):
    shown = [("brake_onset_m", "Brake onset (m from marker)"), ("min_speed_kmh", "Minimum speed (km/h)"),
             ("throttle_pickup_m", "Throttle 10 % (m from marker)"), ("exit_speed_kmh", "Exit speed (km/h)")]
    usable = table[(table["usable"]) & (table["session"] == "Q")]
    fig, axes = plt.subplots(len(shown), 3, figsize=(12, 11))
    for row, (feature, label) in enumerate(shown):
        for column, corner in enumerate(PILOT):
            ax = axes[row, column]
            for k, driver in enumerate(DRIVERS):
                values = usable[(usable["corner"] == corner) & (usable["driver"] == driver)][feature].dropna()
                x = np.full(len(values), k) + np.linspace(-0.08, 0.08, max(len(values), 1))[:len(values)]
                ax.plot(x, values, "o", color=DRIVER_COLORS[driver], markersize=7, alpha=0.85)
                if len(values):
                    _, per_lap = errors.get((corner, feature), (0, 0))
                    ax.errorbar(k + 0.25, values.mean(), yerr=per_lap, fmt="_", color=TEXT_SECONDARY,
                                markersize=14, capsize=4)
            ax.set_xticks([0, 1])
            ax.set_xticklabels(DRIVERS)
            ax.set_xlim(-0.5, 1.6)
            if row == 0:
                ax.set_title(corner, fontsize=11)
            if column == 0:
                ax.set_ylabel(label, fontsize=9)
    fig.suptitle("Qualifying laps (dots) and each driver's mean ± one lap's measurement error (grey bar)",
                 x=0.0, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "features_Q.png", bbox_inches="tight")
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    apply_style()
    errors, alignment_noise = measurement_errors()
    table, traces, all_s = compute_features()
    table.to_csv(OUT_DIR / "features.csv", index=False, float_format="%.3f")
    summary = driver_summary(table, errors)
    summary.to_csv(OUT_DIR / "driver_summary.csv", index=False, float_format="%.3f")
    differences = teammate_differences(summary)
    differences.to_csv(OUT_DIR / "teammate_differences.csv", index=False, float_format="%.3f")
    write_summary_markdown(differences, summary, alignment_noise)
    plot_corner_events(traces)
    plot_features(table, errors)

    print(f"usable (lap, corner) pairs: {int(table['usable'].sum())} of {len(table)}")
    for session_name in SESSIONS:
        print(f"\n=== {session_name}: NOR - PIA (descriptive; SE = combined standard error) ===")
        subset = differences[differences["session"] == session_name]
        for _, r in subset[subset["feature"].isin(SHOWN)].iterrows():
            print(f"{r['corner']} {r['feature']:18s} NOR {r['NOR_mean']:8.2f} (n={r['n_NOR']})  PIA {r['PIA_mean']:8.2f} "
                  f"(n={r['n_PIA']})  diff {r['difference_NOR_minus_PIA']:+7.2f}  SE {r['combined_standard_error']:5.2f}  "
                  f"per-lap error {r['measurement_error_per_lap']:.2f}")
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump({"usable_pairs": int(table["usable"].sum()), "pairs": len(table),
                   "alignment_noise_m": alignment_noise,
                   "differences": differences.to_dict(orient="records")}, file, indent=1, default=float)
    print(f"\nSaved results to {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

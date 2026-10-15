"""Phase 3: put every lap on one track coordinate s, and measure how well it worked.

Method (alignment.py, track.py): the X/Y path of Norris's pole lap is the
reference; every position sample of every lap is projected onto it, and
each car sample gets its s by interpolation in time. Then:

  1. Projection quality: how far from the path are the points (sideways),
     and does s ever run backwards?
  2. Consistency with integrated speed: over each ~0.26 s position interval,
     does the distance from X/Y match the distance from integrating speed?
  3. Drift: how far does integrated distance drift from s by the time the
     car reaches each pilot corner? Separately for laps with and without a
     feed gap before the corner.
  4. Whole-lap cross-correlation of each lap's speed trace against the
     reference lap, on s and on integrated distance: the remaining shift.
  5. Is the sampling phase random at a fixed track point (the assumption
     behind "averaging N laps shrinks the error like 1/sqrt(N)")?
  6. Corner windows: which (lap, corner) pairs are usable (no feed gap in
     the window), and overlay plots of all usable laps at T6, T5, T9.
  7. The fused coordinate used for measurements (corners.fuse_window_coordinate):
     integrated distance pinned to the X/Y frame by one offset per window.
     Its noise is checked by splitting each window's position samples in two
     halves and comparing the two offsets.

Outputs in results/04_alignment/. Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\04_alignment.py
"""

import json
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from apextrace.alignment import lag_metres
from apextrace.corners import (corner_positions, fuse_window_coordinate, has_feed_gap,
                               samples_in_window, window_bounds)
from apextrace.data_loading import load_session, select_laps
from apextrace.plots import DRIVER_COLORS, TEXT_SECONDARY, apply_style
from apextrace.resampling import resample_by_distance
from apextrace.track import lap_on_track, reference_path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "results" / "04_alignment"
CORNER_CHOICE = REPO_ROOT / "results" / "01_data_pilot" / "corner_choice.csv"

YEAR = 2024
EVENT = "Abu Dhabi"
SESSIONS = ["Q", "FP2"]
DRIVERS = ["NOR", "PIA"]
GRID_M = 1.0


def load_everything():
    """Sessions, the reference path (NOR pole lap), every kept lap on the track coordinate."""
    logging.getLogger("fastf1").setLevel(logging.WARNING)
    sessions = {name: load_session(YEAR, EVENT, name) for name in SESSIONS}
    pole_lap = sessions["Q"].laps.pick_fastest()
    reference = reference_path(pole_lap)
    reference_samples = lap_on_track(pole_lap, reference)

    laps = []
    for session_name, session in sessions.items():
        for driver in DRIVERS:
            kept, _ = select_laps(session.laps.pick_drivers(driver))
            for _, lap in kept.iterrows():
                laps.append({"session": session_name, "driver": driver,
                             "lap_number": int(lap["LapNumber"]),
                             "lap_time_s": lap["LapTime"].total_seconds(),
                             "samples": lap_on_track(lap, reference)})
    corners = sessions["Q"].get_circuit_info().corners
    corner_s = corner_positions(corners["X"], corners["Y"], corners["Distance"], reference)
    names = [f"T{int(n)}{l if isinstance(l, str) else ''}" for n, l in zip(corners["Number"], corners["Letter"])]
    return sessions, reference, reference_samples, laps, dict(zip(names, corner_s))


def gap_times(samples, threshold=0.6):
    times = samples["time_s"]
    return [times[i] for i in range(1, len(times)) if times[i] - times[i - 1] > threshold]


def per_lap_quality(laps, reference, reference_samples, corner_s, pilot):
    rows = []
    ref_grid, ref_speed = resample_by_distance(reference_samples["s_m"], reference_samples["speed_kmh"],
                                               GRID_M, start_m=0, end_m=reference["length"])
    for lap in laps:
        smp = lap["samples"]
        pos_s = smp["pos_s_m"]
        backwards = int(np.sum(np.diff(pos_s) < -0.5))

        # 2. consistency over each position interval: X/Y distance vs integrated speed
        scale = reference["length"] / smp["lap_distance_m"]
        increment_residual = np.diff(pos_s) - np.diff(smp["pos_d_m"]) * scale
        normal = np.diff(smp["pos_time_s"]) <= 0.6

        row = {"session": lap["session"], "driver": lap["driver"], "lap": lap["lap_number"],
               "lap_time_s": round(lap["lap_time_s"], 3),
               "side_median_m": float(np.median(smp["pos_side_m"])),
               "side_p95_m": float(np.percentile(smp["pos_side_m"], 95)),
               "side_max_m": float(np.max(smp["pos_side_m"])),
               "s_runs_backwards": backwards,
               "increment_residual_std_m": float(np.std(increment_residual[normal])),
               "feed_gaps": len(gap_times(smp))}

        # 3. drift of integrated distance relative to s at each pilot corner
        drift = smp["d_m"] - smp["s_m"]
        for corner in pilot:
            k = int(np.argmin(np.abs(smp["s_m"] - corner_s[corner])))
            row[f"drift_at_{corner}_m"] = float(drift[k])
            row[f"gap_before_{corner}"] = any(t < smp["time_s"][k] for t in gap_times(smp))
        row["drift_at_end_m"] = float(drift[-1])

        # 4. whole-lap cross-correlation against the reference lap, on s and on integrated d
        _, speed_on_s = resample_by_distance(smp["s_m"], smp["speed_kmh"], GRID_M, 0, reference["length"])
        _, speed_on_d = resample_by_distance(smp["d_m"] * scale, smp["speed_kmh"], GRID_M, 0, reference["length"])
        row["whole_lap_lag_on_s_m"], row["whole_lap_corr_on_s"] = lag_metres(ref_speed, speed_on_s, GRID_M, 40)
        row["whole_lap_lag_on_d_m"], row["whole_lap_corr_on_d"] = lag_metres(ref_speed, speed_on_d, GRID_M, 40)
        rows.append(row)
    return pd.DataFrame(rows)


def sampling_phase(laps, corner_s):
    """Where, within its sampling interval, does each corner marker fall? 0 = on a sample, 1 = on the next.

    If the feed's sampling is unrelated to the track, this phase is uniform
    between 0 and 1. Kolmogorov-Smirnov test: compares the observed
    distribution with the uniform one; a small p-value would say "not uniform".
    """
    phases = []
    for lap in laps:
        s = lap["samples"]["s_m"]
        for name, marker in corner_s.items():
            i = int(np.searchsorted(s, marker))
            if 0 < i < len(s) and s[i] > s[i - 1]:
                phases.append((marker - s[i - 1]) / (s[i] - s[i - 1]))
    phases = np.array(phases)
    ks = stats.kstest(phases, "uniform")
    return phases, {"count": int(len(phases)), "mean": float(np.mean(phases)),
                    "ks_statistic": float(ks.statistic), "ks_p_value": float(ks.pvalue)}


def corner_usability(laps, corner_s, pilot):
    """One row per (lap, corner): usable or not, and the fusion offset with its half-split check."""
    rows = []
    for lap in laps:
        for corner in pilot:
            start, end = window_bounds(corner_s[corner])
            window = samples_in_window(lap["samples"], start, end)
            gap = window is None or has_feed_gap(window)
            row = {"session": lap["session"], "driver": lap["driver"], "lap": lap["lap_number"],
                   "corner": corner, "usable": not gap, "reason": "feed gap in window" if gap else "",
                   "fusion_offset_m": np.nan, "position_samples": 0, "half_split_difference_m": np.nan}
            if not gap:
                _, offset, count, half_difference = fuse_window_coordinate(lap["samples"], window)
                row.update({"fusion_offset_m": offset, "position_samples": count,
                            "half_split_difference_m": half_difference})
            rows.append(row)
    return pd.DataFrame(rows)


def overlay_figure(laps, corner_s, pilot, usability, session_name, path):
    fig, axes = plt.subplots(1, len(pilot), figsize=(15, 4.6), sharey=False)
    for ax, corner in zip(axes, pilot):
        start, end = window_bounds(corner_s[corner])
        counts = {}
        for lap in laps:
            if lap["session"] != session_name:
                continue
            ok = usability[(usability["session"] == session_name) & (usability["driver"] == lap["driver"])
                           & (usability["lap"] == lap["lap_number"]) & (usability["corner"] == corner)]
            if not bool(ok["usable"].iloc[0]):
                continue
            w = samples_in_window(lap["samples"], start, end)
            fused, _, _, _ = fuse_window_coordinate(lap["samples"], w)
            ax.plot(fused - corner_s[corner], w["speed_kmh"], "-", marker="o", markersize=2.5,
                    linewidth=1.0, alpha=0.8, color=DRIVER_COLORS[lap["driver"]])
            counts[lap["driver"]] = counts.get(lap["driver"], 0) + 1
        label = ", ".join(f"{d} {counts.get(d, 0)} laps" for d in DRIVERS)
        ax.set_title(f"{corner} ({pilot[corner]}): {label}", fontsize=10)
        ax.set_xlabel("Metres from the corner marker (fused track coordinate)")
        ax.set_xlim(-300, 200)
    axes[0].set_ylabel("Speed (km/h)")
    for driver in DRIVERS:
        axes[0].plot([], [], color=DRIVER_COLORS[driver], label=driver)
    axes[0].legend(fontsize=9, loc="lower left")
    fig.suptitle(f"Aligned corner traces, 2024 Abu Dhabi {session_name}, laps without a feed gap in the window "
                 "(dots = real samples)", x=0.0, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def phase_figure(phases, ks):
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.hist(phases, bins=10, range=(0, 1), color=DRIVER_COLORS["NOR"], rwidth=0.9)
    ax.axhline(len(phases) / 10, color=TEXT_SECONDARY, linestyle="--", linewidth=1, label="perfectly uniform")
    ax.set_xlabel("Where the corner marker falls inside its sampling interval (0 = on a sample)")
    ax.set_ylabel("Count")
    ax.set_title(f"Sampling phase at 16 corners x 30 laps (KS test p = {ks['ks_p_value']:.2f})", pad=10)
    ax.legend(fontsize=9)
    fig.savefig(OUT_DIR / "sampling_phase.png", bbox_inches="tight")
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    apply_style()
    choice = pd.read_csv(CORNER_CHOICE)
    pilot = {}
    for _, row in choice[choice["Role"].notna() & (choice["Role"] != "")].iterrows():
        pilot[row["Corner"]] = row["Role"]
    pilot = dict(sorted(pilot.items(), key=lambda item: ["heavy braking", "medium", "fast"].index(item[1])))

    sessions, reference, reference_samples, laps, corner_s = load_everything()
    quality = per_lap_quality(laps, reference, reference_samples, corner_s, pilot)
    quality.to_csv(OUT_DIR / "alignment_quality.csv", index=False, float_format="%.3f")
    phases, ks = sampling_phase(laps, corner_s)
    phase_figure(phases, ks)
    usability = corner_usability(laps, corner_s, pilot)
    usability.to_csv(OUT_DIR / "corner_laps.csv", index=False)
    for session_name in SESSIONS:
        overlay_figure(laps, corner_s, pilot, usability, session_name, OUT_DIR / f"corners_{session_name}.png")

    print(f"reference path: NOR pole lap {reference['lap_number']}, length {reference['length']:.1f} m")
    print("pilot corners on the track coordinate: "
          + ", ".join(f"{c} {corner_s[c]:.1f} m" for c in pilot))
    print("\n--- 1. Projection quality (all 30 laps) ---")
    print(f"sideways distance to the reference path: median {quality['side_median_m'].median():.2f} m, "
          f"worst 95th percentile {quality['side_p95_m'].max():.2f} m, worst {quality['side_max_m'].max():.2f} m")
    print(f"position steps where s runs backwards by > 0.5 m: {int(quality['s_runs_backwards'].sum())}")
    print("\n--- 2. X/Y distance vs integrated speed, per ~0.26 s position interval ---")
    print(f"residual std per lap: median {quality['increment_residual_std_m'].median():.2f} m, "
          f"max {quality['increment_residual_std_m'].max():.2f} m")
    print("\n--- 3. Drift of integrated distance relative to s (d - s) at each pilot corner ---")
    drift_summary = {}
    for corner in pilot:
        for has_gap in [False, True]:
            for session_name in SESSIONS:
                subset = quality[(quality["session"] == session_name) & (quality[f"gap_before_{corner}"] == has_gap)]
                if len(subset) == 0:
                    continue
                values = subset[f"drift_at_{corner}_m"]
                key = f"{corner} {session_name} {'gap before' if has_gap else 'no gap before'}"
                drift_summary[key] = {"laps": int(len(values)), "mean_m": float(values.mean()),
                                      "std_m": float(values.std(ddof=0)), "range_m": float(values.max() - values.min())}
                d = drift_summary[key]
                print(f"{key:28s} {d['laps']:2d} laps: mean {d['mean_m']:+6.1f} m, "
                      f"spread (std) {d['std_m']:4.1f} m, range {d['range_m']:5.1f} m")
    print("\n--- 4. Whole-lap cross-correlation lag against the reference lap ---")
    for axis in ["s", "d"]:
        lags = quality[f"whole_lap_lag_on_{axis}_m"]
        print(f"on {'X/Y track coordinate s' if axis == 's' else 'integrated distance d'}: "
              f"|lag| median {lags.abs().median():.2f} m, max {lags.abs().max():.2f} m; "
              f"correlation min {quality[f'whole_lap_corr_on_{axis}'].min():.4f}")
    print("\n--- 5. Sampling phase at the corner markers ---")
    print(f"{ks['count']} phases, mean {ks['mean']:.3f} (uniform: 0.5), "
          f"KS statistic {ks['ks_statistic']:.3f}, p = {ks['ks_p_value']:.3f}")
    print("\n--- 6. Usable (lap, corner) pairs, no feed gap in the window ---")
    counts = usability.groupby(["session", "corner", "driver"])["usable"].agg(["sum", "count"])
    print(counts.to_string())
    usable = usability[usability["usable"]]
    half = usable["half_split_difference_m"].dropna()
    fused_noise = float(np.std(half) / 2)
    print("\n--- 7. Fused coordinate: offset noise from the half-split check ---")
    print(f"{len(half)} usable (lap, corner) pairs, {usable['position_samples'].median():.0f} position samples "
          f"per window (median); half-split difference std {np.std(half):.2f} m "
          f"-> noise of the full-window offset ~ {fused_noise:.2f} m")

    summary = {
        "reference_lap": reference["lap_number"], "reference_length_m": reference["length"],
        "pilot_corners_s_m": {c: float(corner_s[c]) for c in pilot},
        "all_corners_s_m": {c: float(v) for c, v in corner_s.items()},
        "side_median_m": float(quality["side_median_m"].median()),
        "side_p95_worst_m": float(quality["side_p95_m"].max()),
        "s_runs_backwards_total": int(quality["s_runs_backwards"].sum()),
        "increment_residual_std_median_m": float(quality["increment_residual_std_m"].median()),
        "drift": drift_summary,
        "whole_lap_lag_abs_median_on_s_m": float(quality["whole_lap_lag_on_s_m"].abs().median()),
        "whole_lap_lag_abs_median_on_d_m": float(quality["whole_lap_lag_on_d_m"].abs().median()),
        "whole_lap_lag_abs_max_on_s_m": float(quality["whole_lap_lag_on_s_m"].abs().max()),
        "whole_lap_lag_abs_max_on_d_m": float(quality["whole_lap_lag_on_d_m"].abs().max()),
        "sampling_phase": ks,
        "usable_pairs": {f"{s} {c} {d}": [int(v["sum"]), int(v["count"])] for (s, c, d), v in counts.iterrows()},
        "fusion_half_split_std_m": float(np.std(half)),
        "fusion_offset_noise_m": fused_noise,
        "fusion_position_samples_median": float(usable["position_samples"].median()),
    }
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)
    print(f"\nSaved results to {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

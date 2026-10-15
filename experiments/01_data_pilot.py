"""Phase 1 data pilot: what does the real data look like, before we build on it?

Each check from the PROJECT_CONTEXT §7 checklist becomes numbers, a table or
a figure here, and one sentence in docs/data_report.md. Every number goes
into results/01_data_pilot/summary.json, so the report quotes the script,
never a hand-typed value.

Data: 2024 Abu Dhabi GP, qualifying and FP2, Norris and Piastri, kept laps
only (see select_laps). The checks:
  1  sample timing                 -> sample_intervals.png, interval_histogram.csv
  2  channel resolution
  3  brake channel
  4  position data: rate, resolution, lap-to-lap path spread
  5  distance drift                -> lap_distances.csv
  6  usable laps                   -> lap_table.csv
  7  corner info                   -> corners.csv, corners_on_speed.png
  8  FastF1 lap-filter helpers vs select_laps()
  9  cost: cache size and load time

Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\01_data_pilot.py
"""

import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from apextrace.data_loading import DEFAULT_CACHE_DIR, load_session, select_laps
from apextrace.plots import DRIVER_COLORS, SERIES, TEXT_SECONDARY, apply_style
from apextrace.quality import (
    distance_to_path,
    event_timing_error_s,
    find_gaps,
    interval_summary,
    path_length,
    sample_intervals,
    share_on_grid,
    smallest_step,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "results" / "01_data_pilot"

YEAR = 2024
EVENT = "Abu Dhabi"
SESSIONS = ["Q", "FP2"]
DRIVERS = ["NOR", "PIA"]

# Official lap length of the current Yas Marina layout, measured along the
# track's centre line (formula1.com, checked 2026-10-16). A racing line cuts
# the corners, so a measured lap somewhat shorter than this is expected.
OFFICIAL_LAP_LENGTH_M = 5281

# Longer than any normal interval seen in this data (car data up to 0.48 s,
# position data up to ~0.50 s), so anything above it is a real gap.
GAP_THRESHOLD_S = 0.6

# Speeds at which we translate seconds into metres (km/h)
REFERENCE_SPEEDS_KMH = [300, 200, 100]


# ---------------------------------------------------------------- helpers

def seconds(timedeltas):
    """A pandas column of timedeltas -> numpy array of seconds."""
    return timedeltas.dt.total_seconds().to_numpy()


def kmh_to_ms(speed_kmh):
    return speed_kmh / 3.6


def round_floats(value, digits=4):
    """Round every float inside nested dicts/lists, so summary.json stays readable."""
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, dict):
        return {key: round_floats(item, digits) for key, item in value.items()}
    if isinstance(value, list):
        return [round_floats(item, digits) for item in value]
    return value


def qualifying_segment_by_lap(session):
    """{(driver, lap number): 'Q1' / 'Q2' / 'Q3'} for a qualifying session."""
    segment_by_lap = {}
    parts = session.laps.split_qualifying_sessions()
    for segment_name, part in zip(["Q1", "Q2", "Q3"], parts):
        if part is None:
            continue
        for _, lap in part.iterrows():
            segment_by_lap[(lap["Driver"], lap["LapNumber"])] = segment_name
    return segment_by_lap


def build_lap_table(session_name, session, laps, dropped):
    """One row per lap: the columns we need to judge it, plus Kept and Reason."""
    reason_by_lap = {}
    for _, row in dropped.iterrows():
        reason_by_lap[(row["Driver"], row["LapNumber"])] = row["Reason"]

    segment_by_lap = {}
    if session_name == "Q":
        segment_by_lap = qualifying_segment_by_lap(session)

    records = []
    for _, lap in laps.iterrows():
        key = (lap["Driver"], lap["LapNumber"])
        lap_time = lap["LapTime"]
        records.append({
            "Session": session_name,
            "Driver": lap["Driver"],
            "LapNumber": int(lap["LapNumber"]),
            "Segment": segment_by_lap.get(key, ""),
            "Stint": lap["Stint"],
            "Compound": lap["Compound"],
            "TyreLife": lap["TyreLife"],
            "FreshTyre": lap["FreshTyre"],
            "LapTime_s": round(lap_time.total_seconds(), 3) if not pd.isna(lap_time) else None,
            "Deleted": lap["Deleted"],
            "TrackStatus": lap["TrackStatus"],
            "OutLap": not pd.isna(lap["PitOutTime"]),
            "InLap": not pd.isna(lap["PitInTime"]),
            "IsAccurate": lap["IsAccurate"],
            "Kept": key not in reason_by_lap,
            "Reason": reason_by_lap.get(key, ""),
        })
    return pd.DataFrame(records)


def fastf1_helper_chain(laps):
    """Lap numbers kept by chaining FastF1's own filters (check 8).

    Order matters: pick_quicklaps() measures 107 % against the fastest lap
    *in what it is given*, so it has to come last, after the bad laps are gone.
    It uses the driver's session best, not the stint best, so in practice
    sessions it is expected to drop long-run laps that select_laps() keeps.
    """
    chained = (laps.pick_wo_box()
               .pick_not_deleted()
               .pick_track_status("1")
               .pick_accurate()
               .pick_quicklaps())
    return sorted(int(n) for n in chained["LapNumber"])


# ---------------------------------------------------------------- checks 6 and 8

def check_6_and_8_usable_laps(sessions):
    """Lap table with drop reasons (check 6) and FastF1's helpers (check 8).

    Returns the summary dict and the kept laps as (session, driver, lap) tuples.
    """
    tables = []
    kept_laps = []
    helper_check = {}

    for session_name, session in sessions.items():
        print(f"\n=== {YEAR} {EVENT} {session_name} ===")
        for driver in DRIVERS:
            laps = session.laps.pick_drivers(driver)
            kept, dropped = select_laps(laps)
            tables.append(build_lap_table(session_name, session, laps, dropped))
            for _, lap in kept.iterrows():
                kept_laps.append((session_name, driver, lap))

            ours = sorted(int(n) for n in kept["LapNumber"])
            helpers = fastf1_helper_chain(laps)
            helper_check[f"{session_name} {driver}"] = {
                "select_laps": ours, "fastf1_helpers": helpers, "same": ours == helpers}
            same = "same laps" if ours == helpers else f"DIFFERENT: helpers keep {helpers}"
            print(f"{driver}: {len(laps)} laps, kept {len(kept)}: {ours}")
            print(f"     check 8, FastF1 helper chain: {same}")

    table = pd.concat(tables, ignore_index=True)
    table.to_csv(OUT_DIR / "lap_table.csv", index=False)

    kept_counts = {}
    for (session_name, driver, compound), group in table[table["Kept"]].groupby(
            ["Session", "Driver", "Compound"]):
        kept_counts[f"{session_name} {driver} {compound}"] = len(group)

    reason_counts = {}
    for reasons in table.loc[~table["Kept"], "Reason"]:
        for reason in reasons.split("; "):
            if reason.startswith("slow lap"):
                reason = "slow lap (> 107 % of stint best)"
            if reason.startswith("not a timed run"):
                reason = "not a timed run (stint best > 115 % of driver's best)"
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    print("\n--- Check 6: kept laps by session, driver, compound ---")
    for key, count in kept_counts.items():
        print(f"{count:4d}  {key}")
    print("--- Drop reasons (a lap can have several) ---")
    for reason, count in sorted(reason_counts.items(), key=lambda item: -item[1]):
        print(f"{count:4d}  {reason}")

    summary = {
        "laps_total": len(table),
        "laps_kept": int(table["Kept"].sum()),
        "kept_by_session_driver_compound": kept_counts,
        "drop_reasons": reason_counts,
        "check_8_helper_chain": helper_check,
    }
    return summary, kept_laps


# ---------------------------------------------------------------- check 1

# The clock ticks found in this data: car-data intervals are multiples of
# 40 ms, position-data intervals multiples of 20 ms (to within ~1 ms).
CLOCK_TICK_S = {"car": 0.04, "pos": 0.02}


def check_1_sample_timing(kept_laps):
    """How often do car-data and position samples arrive? Uses the raw streams, not merged data.

    Returns the summary dict and {(session, driver, lap number): number of
    car-data gaps}, which check 5 uses.
    """
    intervals = {"car": [], "pos": []}
    gap_rows = []
    source_counts = {}

    for session_name, driver, lap in kept_laps:
        car = lap.get_car_data().add_distance()
        pos = lap.get_pos_data()
        for name, data in [("car", car), ("pos", pos)]:
            intervals[name].extend(sample_intervals(seconds(data["SessionTime"])))
            for source, count in data["Source"].value_counts().items():
                source_counts[source] = source_counts.get(source, 0) + int(count)

        # Gaps in the car data: where on the lap, at what speed, and whether
        # the position stream has a gap at the same moment too
        car_times = seconds(car["SessionTime"])
        pos_gaps = find_gaps(seconds(pos["SessionTime"]), GAP_THRESHOLD_S)
        for gap_start, gap_length in find_gaps(car_times, GAP_THRESHOLD_S):
            i = int(np.argmin(np.abs(car_times - gap_start)))  # sample just before the gap
            position_gap_too = False
            for pos_start, pos_length in pos_gaps:
                if pos_start < gap_start + gap_length and pos_start + pos_length > gap_start:
                    position_gap_too = True
            gap_rows.append({
                "Session": session_name,
                "Driver": driver,
                "LapNumber": int(lap["LapNumber"]),
                "SessionTime_s": round(gap_start, 2),
                "Gap_s": round(gap_length, 3),
                "Distance_m": round(float(car["Distance"].iloc[i])),
                "SpeedBefore_kmh": float(car["Speed"].iloc[i]),
                "SpeedAfter_kmh": float(car["Speed"].iloc[i + 1]),
                "PositionGapToo": position_gap_too,
            })

    gaps = pd.DataFrame(gap_rows)
    gaps.to_csv(OUT_DIR / "gaps.csv", index=False)
    gaps_per_lap = {}
    for row in gaps.itertuples():
        key = (row.Session, row.Driver, row.LapNumber)
        gaps_per_lap[key] = gaps_per_lap.get(key, 0) + 1

    summary = {"source_counts": source_counts}
    for name in ["car", "pos"]:
        values = np.array(intervals[name])
        normal = values[values <= GAP_THRESHOLD_S]
        stats = interval_summary(values)
        stats["clock_tick_s"] = CLOCK_TICK_S[name]
        stats["share_within_1ms_of_tick"] = share_on_grid(values, CLOCK_TICK_S[name], 0.001)
        stats["share_within_2ms_of_tick"] = share_on_grid(values, CLOCK_TICK_S[name], 0.002)
        stats["normal_max_s"] = float(np.max(normal))
        stats["gaps_longer_than_threshold"] = int(np.sum(values > GAP_THRESHOLD_S))
        stats["event_timing_error_s"] = event_timing_error_s(values)
        stats["event_timing_error_without_gaps_s"] = event_timing_error_s(normal)
        stats["regular_sampling_error_s"] = stats["mean_s"] / np.sqrt(12)
        stats["metres_between_samples"] = {}
        stats["event_timing_error_m"] = {}
        for speed in REFERENCE_SPEEDS_KMH:
            v = kmh_to_ms(speed)
            stats["metres_between_samples"][f"{speed} km/h"] = {
                "min": stats["min_s"] * v, "mean": stats["mean_s"] * v,
                "normal_max": stats["normal_max_s"] * v, "max": stats["max_s"] * v}
            stats["event_timing_error_m"][f"{speed} km/h"] = stats["event_timing_error_s"] * v
        summary[name] = stats

    summary["gaps"] = {
        "threshold_s": GAP_THRESHOLD_S,
        "car_gaps": int(len(gaps)),
        "with_position_gap_at_same_time": int(gaps["PositionGapToo"].sum()),
        "distinct_moments": int(gaps["SessionTime_s"].round(0).nunique()),
        "laps_with_gaps": len(gaps_per_lap),
        "laps_total": len(kept_laps),
        "longest_s": float(gaps["Gap_s"].max()),
    }

    # Histogram table (10 ms bins, every interval including gaps): the real
    # interval distribution, which the synthetic-lap generator (Phase 2)
    # will draw from.
    car_rounded = np.round(intervals["car"], 2)
    pos_rounded = np.round(intervals["pos"], 2)
    top = max(np.max(car_rounded), np.max(pos_rounded))
    rows = []
    for centre in np.round(np.arange(0.0, top + 0.005, 0.01), 2):
        rows.append({
            "interval_s": centre,
            "car_count": int(np.sum(car_rounded == centre)),
            "pos_count": int(np.sum(pos_rounded == centre)),
        })
    histogram = pd.DataFrame(rows)
    histogram = histogram[(histogram["car_count"] > 0) | (histogram["pos_count"] > 0)]
    histogram.to_csv(OUT_DIR / "interval_histogram.csv", index=False)

    # Figure: one panel per stream, normal intervals; gaps are counted in the note
    fig, axes = plt.subplots(2, 1, figsize=(9, 5.8), sharex=True)
    labels = {"car": "Car data (speed, throttle, brake, gear, RPM)",
              "pos": "Position data (X, Y, Z)"}
    for ax, name, color in zip(axes, ["car", "pos"], [SERIES[0], SERIES[2]]):
        counts = histogram[f"{name}_count"].to_numpy()
        share = 100 * counts / counts.sum()
        ax.bar(histogram["interval_s"], share, width=0.008, color=color)
        stats = summary[name]
        ax.set_title(labels[name], fontsize=11, pad=18)
        ax.text(0.0, 1.02, f"{stats['count']} intervals · mean {stats['mean_s']:.3f} s "
                f"({stats['rate_from_mean_hz']:.2f} samples/s) · on a "
                f"{stats['clock_tick_s'] * 1000:.0f} ms clock · "
                f"{stats['gaps_longer_than_threshold']} gaps of {GAP_THRESHOLD_S}–"
                f"{stats['max_s']:.2f} s not shown",
                transform=ax.transAxes, fontsize=9, color=TEXT_SECONDARY, va="bottom")
        ax.set_ylabel("Share of intervals (%)")
    axes[1].set_xlabel("Time between consecutive samples (s)")
    axes[1].set_xlim(0, GAP_THRESHOLD_S)
    fig.suptitle("Sample timing, 2024 Abu Dhabi Q + FP2, NOR + PIA kept laps",
                 x=0.0, ha="left", fontweight="bold", fontsize=12)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "sample_intervals.png", bbox_inches="tight")
    plt.close(fig)

    car_stats = summary["car"]
    spacing = car_stats["metres_between_samples"]["300 km/h"]
    g = summary["gaps"]
    print("\n--- Check 1: sample timing ---")
    for name in ["car", "pos"]:
        s = summary[name]
        print(f"{name}: {s['count']} intervals, mean {s['mean_s']:.4f} s "
              f"({s['rate_from_mean_hz']:.2f}/s), median {s['median_s']:.3f} s, "
              f"normal range {s['min_s']:.3f}-{s['normal_max_s']:.3f} s, "
              f"{100 * s['share_within_2ms_of_tick']:.1f} % within 2 ms of a "
              f"{s['clock_tick_s'] * 1000:.0f} ms tick "
              f"({100 * s['share_within_1ms_of_tick']:.1f} % within 1 ms)")
    print(f"car, metres between samples at 300 km/h: {spacing['min']:.1f} to "
          f"{spacing['normal_max']:.1f} m normally (mean {spacing['mean']:.1f} m), "
          f"up to {spacing['max']:.1f} m in a gap")
    print(f"gaps > {GAP_THRESHOLD_S} s: {g['car_gaps']} in car data "
          f"({g['with_position_gap_at_same_time']} with a position gap at the same time), "
          f"at {g['distinct_moments']} distinct moments, in {g['laps_with_gaps']} of "
          f"{g['laps_total']} laps, longest {g['longest_s']:.2f} s")
    print(f"car, event timing error (one lap, middle of interval): "
          f"{car_stats['event_timing_error_s']:.4f} s with gaps, "
          f"{car_stats['event_timing_error_without_gaps_s']:.4f} s without; "
          f"regular sampling at the mean interval would give "
          f"{car_stats['regular_sampling_error_s']:.4f} s. At 300 km/h: "
          f"{car_stats['event_timing_error_m']['300 km/h']:.1f} m vs "
          f"{car_stats['regular_sampling_error_s'] * kmh_to_ms(300):.1f} m")
    print(f"Source values: {source_counts}")
    return summary, gaps_per_lap


# ---------------------------------------------------------------- checks 2 and 3

def check_2_and_3_resolution_and_brake(kept_laps):
    """Smallest step of each channel (check 2) and what the brake channel contains (check 3)."""
    car_frames = []
    pos_frames = []
    for _, _, lap in kept_laps:
        car_frames.append(lap.get_car_data())
        pos_frames.append(lap.get_pos_data())
    car = pd.concat(car_frames, ignore_index=True)
    pos = pd.concat(pos_frames, ignore_index=True)

    channels = {}
    for frame, names in [(car, ["Speed", "Throttle", "RPM", "nGear", "DRS"]),
                         (pos, ["X", "Y", "Z"])]:
        for name in names:
            values = frame[name].to_numpy(dtype=float)
            channels[name] = {
                "dtype": str(frame[name].dtype),
                "smallest_step": smallest_step(values),
                "whole_numbers_only": bool(np.all(values == np.round(values))),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "distinct_values": int(len(np.unique(values))),
            }

    brake = car["Brake"]
    brake_summary = {
        "dtype": str(brake.dtype),
        "distinct_values": sorted(str(value) for value in brake.unique()),
        "share_of_samples_braking": float(brake.astype(float).mean()),
        "samples": int(len(brake)),
    }
    drs_values = sorted(int(value) for value in car["DRS"].unique())

    print("\n--- Check 2: channel resolution (X, Y, Z are in 1/10 m) ---")
    for name, c in channels.items():
        print(f"{name:9s} {c['dtype']:8s} step {c['smallest_step']:g}  whole numbers: "
              f"{c['whole_numbers_only']}  range {c['min']:g} to {c['max']:g}  "
              f"({c['distinct_values']} distinct values)")
    print(f"DRS codes seen: {drs_values}")
    print("--- Check 3: brake ---")
    print(f"dtype {brake_summary['dtype']}, values {brake_summary['distinct_values']}, "
          f"braking in {100 * brake_summary['share_of_samples_braking']:.1f} % of samples")

    return {"channels": channels, "drs_codes": drs_values}, brake_summary


# ---------------------------------------------------------------- check 4

def xy_metres(pos):
    """X and Y of a position table in metres (FastF1 stores them in decimetres)."""
    return pos["X"].to_numpy() / 10.0, pos["Y"].to_numpy() / 10.0


def spread_summary(distances):
    distances = np.array(distances)
    return {
        "points": int(len(distances)),
        "median_m": float(np.median(distances)),
        "p95_m": float(np.percentile(distances, 95)),
        "max_m": float(np.max(distances)),
    }


def check_4_position(kept_laps):
    """How far apart are the X/Y paths of different laps? An upper bound on position noise.

    For each driver, the fastest kept Q lap is the reference path (padded by
    one sample at each end, so the start and finish are covered). Three
    comparisons, each pooled over both drivers:
      - same driver, Q:   the driver's other Q laps vs their own reference;
      - other driver, Q:  the driver's Q laps vs the *teammate's* reference;
      - same driver, FP2: the driver's FP2 laps vs their own Q reference.
    If the second and third were no larger than the first, the X/Y paths
    could not show any difference in racing line between drivers or sessions.
    """
    status_counts = {}
    laps_by = {}
    for session_name, driver, lap in kept_laps:
        laps_by.setdefault((session_name, driver), []).append(lap)
        for status, count in lap.get_pos_data()["Status"].value_counts().items():
            status_counts[status] = status_counts.get(status, 0) + int(count)

    references = {}
    for driver in DRIVERS:
        fastest = laps_by[("Q", driver)][0]
        for lap in laps_by[("Q", driver)]:
            if lap["LapTime"] < fastest["LapTime"]:
                fastest = lap
        ref_x, ref_y = xy_metres(fastest.get_pos_data(pad=1, pad_side="both"))
        references[driver] = {"lap": fastest, "x": ref_x, "y": ref_y}

    comparisons = {"same_driver_Q": [], "other_driver_Q": [], "same_driver_FP2_vs_Q": []}
    for driver in DRIVERS:
        teammate = DRIVERS[1] if driver == DRIVERS[0] else DRIVERS[0]
        own = references[driver]
        other = references[teammate]
        for lap in laps_by[("Q", driver)]:
            x, y = xy_metres(lap.get_pos_data())
            if lap["LapNumber"] != own["lap"]["LapNumber"]:
                comparisons["same_driver_Q"].extend(distance_to_path(x, y, own["x"], own["y"]))
            comparisons["other_driver_Q"].extend(distance_to_path(x, y, other["x"], other["y"]))
        for lap in laps_by[("FP2", driver)]:
            x, y = xy_metres(lap.get_pos_data())
            comparisons["same_driver_FP2_vs_Q"].extend(distance_to_path(x, y, own["x"], own["y"]))

    summary = {
        "status_counts": status_counts,
        "reference_laps": {driver: int(references[driver]["lap"]["LapNumber"]) for driver in DRIVERS},
    }
    print("\n--- Check 4: position data (rate and resolution: see checks 1 and 2) ---")
    print(f"Status values: {status_counts}")
    for name, distances in comparisons.items():
        summary[name] = spread_summary(distances)
        s = summary[name]
        print(f"{name:22s}: distance to reference path median {s['median_m']:.2f} m, "
              f"95th percentile {s['p95_m']:.2f} m, max {s['max_m']:.2f} m ({s['points']} points)")
    return summary


# ---------------------------------------------------------------- check 5

def check_5_distance(kept_laps, gaps_per_lap):
    """Lap distance from integrating speed, lap to lap, compared with the X/Y path length.

    Three lap lengths per lap:
      - fastf1:  get_car_data().add_distance(), FastF1's default. It counts the
                 bit from the lap start to the first sample, but not the bit
                 from the last sample to the finish line.
      - edges:   the same, with interpolate_edges=True, so the integration
                 runs from exactly the lap start to exactly the lap end.
      - xy_path: the length of the X/Y path (straight lines between samples).

    Each lap's "edges" distance is also compared with the mean of the same
    driver in the same session, separately for laps with and without feed gaps
    (check 1): integrating speed across a 1 s hole is a likely error source.
    """
    rows = []
    for session_name, driver, lap in kept_laps:
        default = lap.get_car_data().add_distance()
        edges = lap.get_car_data(interpolate_edges=True).add_distance()
        pos = lap.get_pos_data(interpolate_edges=True)
        rows.append({
            "Session": session_name,
            "Driver": driver,
            "LapNumber": int(lap["LapNumber"]),
            "Compound": lap["Compound"],
            "LapTime_s": round(lap["LapTime"].total_seconds(), 3),
            "dist_fastf1_m": round(float(default["Distance"].iloc[-1]), 1),
            "dist_edges_m": round(float(edges["Distance"].iloc[-1]), 1),
            "xy_path_m": round(path_length(pos["X"].to_numpy() / 10.0,
                                           pos["Y"].to_numpy() / 10.0), 1),
            "Gaps": gaps_per_lap.get((session_name, driver, int(lap["LapNumber"])), 0),
        })
    table = pd.DataFrame(rows)
    group_mean = table.groupby(["Session", "Driver"])["dist_edges_m"].transform("mean")
    table["dev_from_driver_session_mean_m"] = (table["dist_edges_m"] - group_mean).round(1)
    table.to_csv(OUT_DIR / "lap_distances.csv", index=False)

    deviation_by_gaps = {}
    for session_name in SESSIONS:
        for label, has_gaps in [("no_gaps", False), ("with_gaps", True)]:
            subset = table[(table["Session"] == session_name) & ((table["Gaps"] > 0) == has_gaps)]
            deviations = subset["dev_from_driver_session_mean_m"].abs()
            deviation_by_gaps[f"{session_name} {label}"] = {
                "laps": int(len(subset)),
                "max_abs_deviation_m": float(deviations.max()) if len(subset) else None,
                "mean_abs_deviation_m": float(deviations.mean()) if len(subset) else None,
            }

    groups = {}
    print("\n--- Check 5: lap distance (m) ---")
    print(f"official centre-line length: {OFFICIAL_LAP_LENGTH_M} m")
    for (session_name, driver), group in table.groupby(["Session", "Driver"], sort=False):
        edges = group["dist_edges_m"]
        default = group["dist_fastf1_m"]
        groups[f"{session_name} {driver}"] = {
            "laps": len(group),
            "edges_mean_m": float(edges.mean()),
            "edges_range_m": float(edges.max() - edges.min()),
            "edges_std_m": float(edges.std()),
            "fastf1_default_range_m": float(default.max() - default.min()),
            "xy_path_mean_m": float(group["xy_path_m"].mean()),
        }
        g = groups[f"{session_name} {driver}"]
        print(f"{session_name:3s} {driver}: {g['laps']:2d} laps | integrated speed (edges) "
              f"mean {g['edges_mean_m']:.0f}, range {g['edges_range_m']:.1f}, "
              f"std {g['edges_std_m']:.1f} | FastF1 default range {g['fastf1_default_range_m']:.1f} "
              f"| X/Y path mean {g['xy_path_mean_m']:.0f}")

    all_edges = table["dist_edges_m"]
    summary = {
        "official_length_m": OFFICIAL_LAP_LENGTH_M,
        "groups": groups,
        "all_laps_edges_mean_m": float(all_edges.mean()),
        "all_laps_edges_range_m": float(all_edges.max() - all_edges.min()),
        "mean_edges_minus_official_m": float(all_edges.mean() - OFFICIAL_LAP_LENGTH_M),
        "mean_edges_minus_xy_path_m": float((table["dist_edges_m"] - table["xy_path_m"]).mean()),
        "deviation_from_driver_session_mean_by_gaps": deviation_by_gaps,
    }
    print(f"all {len(table)} laps: integrated speed mean {summary['all_laps_edges_mean_m']:.0f} m, "
          f"{summary['mean_edges_minus_official_m']:+.0f} m vs official; "
          f"integrated speed minus X/Y path: {summary['mean_edges_minus_xy_path_m']:+.1f} m on average")
    print("deviation of each lap from its driver-session mean (edges), by feed gaps:")
    for key, d in deviation_by_gaps.items():
        if d["laps"]:
            print(f"   {key:14s}: {d['laps']:2d} laps, mean |dev| {d['mean_abs_deviation_m']:.1f} m, "
                  f"max |dev| {d['max_abs_deviation_m']:.1f} m")
    return summary


# ---------------------------------------------------------------- check 7

def check_7_corners(q_session):
    """Corner numbers and positions from FastF1's circuit info, drawn on the fastest laps.

    FastF1 measures each corner's Distance along the session's fastest lap
    (Norris's pole lap here), at that lap's position sample nearest to the
    corner marker.
    """
    circuit = q_session.get_circuit_info()
    corners = circuit.corners[["Number", "Letter", "Angle", "Distance"]].copy()
    corners["Distance"] = corners["Distance"].round(1)
    corners["Angle"] = corners["Angle"].round(1)
    corners.to_csv(OUT_DIR / "corners.csv", index=False)

    fig, ax = plt.subplots(figsize=(12, 4.6))
    for driver in DRIVERS:
        lap = q_session.laps.pick_drivers(driver).pick_fastest()
        car = lap.get_car_data().add_distance()
        ax.plot(car["Distance"], car["Speed"], color=DRIVER_COLORS[driver], linewidth=1.4,
                label=f"{driver} fastest Q lap ({lap['LapTime'].total_seconds():.3f} s)")
    # Corners closer than 150 m to the previous label go on a second row, so
    # labels like T11, T12, T13, T14 don't overlap
    previous_distance = -1000.0
    previous_row = 1
    for _, corner in corners.iterrows():
        ax.axvline(corner["Distance"], color=TEXT_SECONDARY, linewidth=0.6, linestyle=":")
        row = 1
        if corner["Distance"] - previous_distance < 150 and previous_row == 1:
            row = 2
        label_height = 1.01 if row == 1 else 1.06
        ax.text(corner["Distance"], label_height, f"T{corner['Number']}{corner['Letter']}",
                transform=ax.get_xaxis_transform(), ha="center", va="bottom",
                fontsize=8, color=TEXT_SECONDARY)
        previous_distance = corner["Distance"]
        previous_row = row
    ax.set_title("Corners from FastF1 circuit info on the fastest laps, 2024 Abu Dhabi Q", pad=30)
    ax.set_xlabel("Distance along the lap (m)")
    ax.set_ylabel("Speed (km/h)")
    ax.set_xlim(0, OFFICIAL_LAP_LENGTH_M)
    ax.legend(loc="lower left", fontsize=9)
    fig.savefig(OUT_DIR / "corners_on_speed.png", bbox_inches="tight")
    plt.close(fig)

    print("\n--- Check 7: corners from get_circuit_info() ---")
    print(f"{len(corners)} corners; distance along the fastest lap (m):")
    print(", ".join(f"T{row['Number']}{row['Letter']} {row['Distance']:.0f}"
                    for _, row in corners.iterrows()))
    return {
        "corner_count": int(len(corners)),
        "corners": [{"number": int(row["Number"]), "letter": row["Letter"],
                     "distance_m": float(row["Distance"])} for _, row in corners.iterrows()],
    }


# ---------------------------------------------------------------- check 10

# Corner window used to count feed gaps: from 300 m before the corner marker
# (covers the braking zone) to 200 m after it (covers the exit). Phase 3
# sets the exact windows; this is only for choosing corners.
WINDOW_BEFORE_M = 300
WINDOW_AFTER_M = 200
MIN_SPEED_DROP_KMH = 50


def check_10_choose_corners(q_session, kept_laps):
    """Choose the 3 pilot corners with a fixed rule, before comparing any drivers.

    Per corner, on Norris's pole lap (the lap FastF1's corner distances are
    measured on):
      - entry speed = highest speed from 500 m to 50 m before the marker
      - minimum speed within 100 m of the marker; it must be a true dip
        (not at the edge of that +-100 m search window)
      - speed drop = entry - minimum

    A corner is a candidate if it has a real braking zone (drop >= 50 km/h)
    and its whole window [-300 m, +200 m] lies inside the lap. When two
    markers share one dip (a chicane), only the marker nearest the dip
    counts. Then:
      - heavy braking = the biggest speed drop
      - fast          = the highest minimum speed
      - medium        = of the rest, the minimum speed closest to halfway
                        between the heavy and fast corners' minimum speeds

    Also counts, per driver, the kept Q laps with no feed gap inside each
    corner's window (gaps.csv from check 1).
    """
    corners = pd.read_csv(OUT_DIR / "corners.csv")
    gaps = pd.read_csv(OUT_DIR / "gaps.csv")
    pole_lap = q_session.laps.pick_fastest()
    car = pole_lap.get_car_data().add_distance()
    distance = car["Distance"].to_numpy()
    speed = car["Speed"].to_numpy()
    lap_length = distance[-1]

    q_laps_by_driver = {}
    for session_name, driver, lap in kept_laps:
        if session_name == "Q":
            q_laps_by_driver.setdefault(driver, []).append(int(lap["LapNumber"]))

    rows = []
    for _, corner in corners.iterrows():
        marker = corner["Distance"]
        letter = corner["Letter"] if isinstance(corner["Letter"], str) else ""
        name = f"T{int(corner['Number'])}{letter}"

        entry_mask = (distance >= marker - 500) & (distance <= marker - 50)
        search_mask = (distance >= marker - 100) & (distance <= marker + 100)
        entry_speed = float(np.max(speed[entry_mask])) if entry_mask.any() else float("nan")
        search_indices = np.where(search_mask)[0]
        lowest = search_indices[np.argmin(speed[search_indices])]
        true_dip = search_indices[0] < lowest < search_indices[-1]
        min_speed = float(speed[lowest])

        window_start = marker - WINDOW_BEFORE_M
        window_end = marker + WINDOW_AFTER_M
        inside_lap = window_start >= 0 and window_end <= lap_length

        row = {
            "Corner": name,
            "Marker_m": round(float(marker), 1),
            "EntrySpeed_kmh": entry_speed,
            "MinSpeed_kmh": min_speed,
            "MinSpeedAt_m": round(float(distance[lowest]), 1),
            "SpeedDrop_kmh": entry_speed - min_speed,
            "TrueDip": bool(true_dip),
            "WindowInsideLap": bool(inside_lap),
        }
        for driver in DRIVERS:
            usable = 0
            for lap_number in q_laps_by_driver[driver]:
                lap_gaps = gaps[(gaps["Session"] == "Q") & (gaps["Driver"] == driver)
                                & (gaps["LapNumber"] == lap_number)]
                in_window = ((lap_gaps["Distance_m"] >= window_start)
                             & (lap_gaps["Distance_m"] <= window_end))
                if not in_window.any():
                    usable += 1
            row[f"GapFreeQLaps_{driver}"] = usable
        row["Candidate"] = bool(true_dip and inside_lap and row["SpeedDrop_kmh"] >= MIN_SPEED_DROP_KMH)
        rows.append(row)

    table = pd.DataFrame(rows)
    # Two markers can share one speed dip (T6/T7 is a chicane with a single
    # slowest point). The dip belongs to the marker nearest to it; the other
    # marker stops being a candidate.
    for dip_at, group in table[table["Candidate"]].groupby("MinSpeedAt_m"):
        if len(group) > 1:
            nearest = (group["Marker_m"] - dip_at).abs().idxmin()
            for index in group.index:
                if index != nearest:
                    table.loc[index, "Candidate"] = False
    candidates = table[table["Candidate"]]
    heavy = candidates.loc[candidates["SpeedDrop_kmh"].idxmax()]
    fast = candidates.loc[candidates["MinSpeed_kmh"].idxmax()]
    halfway = (heavy["MinSpeed_kmh"] + fast["MinSpeed_kmh"]) / 2
    rest = candidates[~candidates["Corner"].isin([heavy["Corner"], fast["Corner"]])]
    medium = rest.loc[(rest["MinSpeed_kmh"] - halfway).abs().idxmin()]

    table["Role"] = ""
    for role, choice in [("heavy braking", heavy), ("medium", medium), ("fast", fast)]:
        table.loc[table["Corner"] == choice["Corner"], "Role"] = role
    table.to_csv(OUT_DIR / "corner_choice.csv", index=False)

    print("\n--- Check 10: choosing the 3 corners (NOR pole lap) ---")
    print(table[["Corner", "Marker_m", "EntrySpeed_kmh", "MinSpeed_kmh", "SpeedDrop_kmh",
                 "TrueDip", "WindowInsideLap", "GapFreeQLaps_NOR", "GapFreeQLaps_PIA",
                 "Candidate", "Role"]].to_string(index=False))
    chosen = {}
    for role, choice in [("heavy_braking", heavy), ("medium", medium), ("fast", fast)]:
        chosen[role] = {
            "corner": choice["Corner"],
            "marker_m": float(choice["Marker_m"]),
            "entry_speed_kmh": float(choice["EntrySpeed_kmh"]),
            "min_speed_kmh": float(choice["MinSpeed_kmh"]),
            "speed_drop_kmh": float(choice["SpeedDrop_kmh"]),
            "gap_free_q_laps": {driver: int(choice[f"GapFreeQLaps_{driver}"]) for driver in DRIVERS},
        }
        print(f"{role}: {choice['Corner']} ({choice['EntrySpeed_kmh']:.0f} -> "
              f"{choice['MinSpeed_kmh']:.0f} km/h), gap-free Q laps NOR "
              f"{choice['GapFreeQLaps_NOR']}, PIA {choice['GapFreeQLaps_PIA']}")
    return {"rule": "see check_10_choose_corners docstring", "halfway_min_speed_kmh": float(halfway),
            "candidates": list(candidates["Corner"]), "chosen": chosen}


# ---------------------------------------------------------------- check 9

def folder_size_mb(folder):
    total = 0
    for path in Path(folder).rglob("*"):
        if path.is_file():
            total += path.stat().st_size
    return total / 1e6


def check_9_cost(load_seconds):
    """Cache size per session and load time from the cache."""
    session_sizes = {}
    for folder in sorted(Path(DEFAULT_CACHE_DIR).glob(f"{YEAR}/*/*")):
        if folder.is_dir():
            session_sizes[folder.name] = folder_size_mb(folder)
    http_cache = Path(DEFAULT_CACHE_DIR) / "fastf1_http_cache.sqlite"
    summary = {
        "session_cache_mb": session_sizes,
        "http_cache_mb": http_cache.stat().st_size / 1e6 if http_cache.exists() else None,
        "total_cache_mb": folder_size_mb(DEFAULT_CACHE_DIR),
        "load_from_cache_s": load_seconds,
    }
    print("\n--- Check 9: cost ---")
    for name, size in session_sizes.items():
        print(f"{name}: {size:.1f} MB")
    print(f"HTTP cache: {summary['http_cache_mb']:.1f} MB, whole cache: {summary['total_cache_mb']:.1f} MB")
    for name, secs in load_seconds.items():
        print(f"load {name} from cache: {secs:.1f} s")
    return summary


# ---------------------------------------------------------------- main

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    apply_style()

    sessions = {}
    load_seconds = {}
    for session_name in SESSIONS:
        start = time.perf_counter()
        sessions[session_name] = load_session(YEAR, EVENT, session_name)
        load_seconds[session_name] = time.perf_counter() - start

    summary = {"event": f"{YEAR} {EVENT}", "sessions": SESSIONS, "drivers": DRIVERS}
    summary["check_6_usable_laps"], kept_laps = check_6_and_8_usable_laps(sessions)
    summary["check_1_sample_timing"], gaps_per_lap = check_1_sample_timing(kept_laps)
    summary["check_2_resolution"], summary["check_3_brake"] = \
        check_2_and_3_resolution_and_brake(kept_laps)
    summary["check_4_position"] = check_4_position(kept_laps)
    summary["check_5_distance"] = check_5_distance(kept_laps, gaps_per_lap)
    summary["check_7_corners"] = check_7_corners(sessions["Q"])
    summary["check_10_corner_choice"] = check_10_choose_corners(sessions["Q"], kept_laps)
    summary["check_9_cost"] = check_9_cost(load_seconds)

    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(round_floats(summary), file, indent=2)
    print(f"\nSaved results to {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

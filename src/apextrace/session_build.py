"""Building the dataset rows of one qualifying session (OpenF1): shared by the 2023-2024 build and the 2025 run.

Moved here from experiments/09_build_dataset.py (unchanged; checked: the
2023-2024 dataset is identical) so that the one-time 2025 evaluation builds
its data with EXACTLY the code that built the development data.

  kept_laps_by_driver  lap selection per driver (same rules as the pilot)
  build_session        reference lap -> detected corners -> every kept lap on the
                       track coordinate -> features per corner window
  raw_sample_table     one lap's measured samples as a flat table
"""

import numpy as np
import pandas as pd

from apextrace.corners import (detect_braking_corners, fuse_window_coordinate, has_feed_gap,
                               samples_in_window, window_bounds)
from apextrace.data_loading import select_laps
from apextrace.features import corner_features
from apextrace.openf1 import driver_streams, kept_laps_span, lap_samples_on_track, lap_table, reference_from_lap


def kept_laps_by_driver(laps):
    """{driver: kept laps table} for one session, drivers with at least one kept lap."""
    kept = {}
    for driver in sorted(laps["Driver"].unique()):
        driver_kept, _ = select_laps(laps[laps["Driver"] == driver])
        if not driver_kept.empty:
            kept[driver] = driver_kept
    return kept


def build_session(year, round_number, session):
    """All rows for one session, plus its corner list and a summary row."""
    key = int(session["session_key"])
    laps = lap_table(key, session["date_end"])
    summary = {"year": year, "round": round_number, "location": session["location"], "session_key": key,
               "laps": len(laps), "kept_laps": 0, "corners": 0, "pairs": 0, "usable_pairs": 0, "note": ""}
    if laps.empty:
        summary["note"] = "no laps"
        return [], [], summary, pd.DataFrame()
    kept = kept_laps_by_driver(laps)
    summary["kept_laps"] = int(sum(len(table) for table in kept.values()))
    if not kept:
        summary["note"] = "no kept laps"
        return [], [], summary, pd.DataFrame()

    streams = {}
    for driver, table in kept.items():
        span_start, span_end = kept_laps_span(table)
        streams[driver] = driver_streams(key, int(table["DriverNumber"].iloc[0]), span_start, span_end)

    # reference: the fastest kept lap of the session (with data)
    all_kept = pd.concat(kept.values()).sort_values("LapTime")
    reference, reference_lap = None, None
    for _, lap in all_kept.iterrows():
        if streams.get(lap["Driver"]) is None:
            continue
        reference = reference_from_lap(key, int(lap["DriverNumber"]), lap["LapStartDate"], lap["LapTime"],
                                       streams=streams[lap["Driver"]])
        if reference is not None:
            reference_lap = lap
            break
    if reference is None:
        summary["note"] = "no reference lap with data"
        return [], [], summary, pd.DataFrame()
    reference_samples = lap_samples_on_track(key, int(reference_lap["DriverNumber"]), reference_lap["LapStartDate"],
                                             reference_lap["LapTime"], reference, streams=streams[reference_lap["Driver"]])
    corners = detect_braking_corners(reference_samples["s_m"], reference_samples["speed_kmh"], reference["length"])
    summary["corners"] = len(corners)
    summary["reference"] = f"{reference_lap['Driver']} lap {int(reference_lap['LapNumber'])}"
    corner_rows = [{"year": year, "round": round_number, "location": session["location"], "session_key": key,
                    **corner} for corner in corners]

    rows = []
    raw_tables = []
    for driver, table in kept.items():
        for _, lap in table.iterrows():
            base = {"year": year, "round": round_number, "location": session["location"], "session_key": key,
                    "driver": driver, "driver_number": int(lap["DriverNumber"]), "team": lap["Team"],
                    "lap": int(lap["LapNumber"]), "lap_time_s": lap["LapTime"].total_seconds(),
                    "compound": lap["Compound"], "tyre_life": lap["TyreLife"], "stint": lap["Stint"]}
            samples = None
            if streams.get(driver) is not None:
                samples = lap_samples_on_track(key, int(lap["DriverNumber"]), lap["LapStartDate"], lap["LapTime"],
                                               reference, streams=streams[driver])
            if samples is not None:
                raw_tables.append(raw_sample_table(base, samples))
            for corner in corners:
                row = {**base, "corner": corner["corner"], "corner_type": corner["type"],
                       "corner_min_speed_ref_kmh": corner["min_speed_kmh"], "corner_s_m": corner["s_m"]}
                summary["pairs"] += 1
                if samples is None:
                    rows.append({**row, "usable": False, "reason": "no car/position data"})
                    continue
                start, end = window_bounds(corner["s_m"])
                window = samples_in_window(samples, start, end)
                if window is None or has_feed_gap(window):
                    rows.append({**row, "usable": False, "reason": "feed gap in window"})
                    continue
                fused, offset, _, _ = fuse_window_coordinate(samples, window)
                features = corner_features(window, fused, corner["s_m"])
                rows.append({**row, "usable": True, "reason": "", "fusion_offset_m": offset, **features})
                summary["usable_pairs"] += 1
    raw = pd.concat(raw_tables, ignore_index=True) if raw_tables else pd.DataFrame()
    return rows, corner_rows, summary, raw


def raw_sample_table(base, samples):
    """One lap's measured car samples as a flat table (for the raw-sample export).

    x_m, y_m are interpolated in time from the position samples (car and
    position samples come at different moments), so they are for drawing
    track maps, not measurements.
    """
    times = samples["time_s"]
    columns = {}
    for name in ["year", "round", "location", "session_key", "driver", "team", "lap", "lap_time_s",
                 "compound", "tyre_life"]:
        columns[name] = [base[name]] * len(times)   # the same value on every sample of the lap
    columns.update({
        "time_s": np.round(times, 3),
        "s_m": np.round(samples["s_m"], 2),
        "d_m": np.round(samples["d_m"], 2),
        "speed_kmh": samples["speed_kmh"],
        "throttle_pct": samples["throttle_pct"],
        "brake": samples["brake"],
        "gear": samples["gear"].astype(int),
        "x_m": np.round(np.interp(times, samples["pos_time_s"], samples["pos_x_m"]), 2),
        "y_m": np.round(np.interp(times, samples["pos_time_s"], samples["pos_y_m"]), 2),
    })
    return pd.DataFrame(columns)

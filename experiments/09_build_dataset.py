"""Phase 6: build the multi-season dataset, one row per (session, driver, lap, corner).

Works from the OpenF1 cache filled by 08_download_openf1.py (run that first;
anything missing would be downloaded on the fly). For each 2023/2024
qualifying session:
  1. lap table + lap selection (same rules as the pilot);
  2. reference path = the session's fastest kept lap (X/Y, s = 0 at the line);
  3. braking corners detected automatically on that lap
     (corners.detect_braking_corners: speed dips of >= 50 km/h; reference
     point = the dip, i.e. the apex on the reference lap; type by min speed);
  4. every kept lap of every driver on the track coordinate; for each corner:
     window [-300 m, +200 m], feed-gap check, fused coordinate, features
     (features.corner_features), exactly as in the validated pilot.

Outputs in results/09_dataset/:
  dataset.csv.gz       one row per (session, driver, lap, corner), usable or not (+ reason)
  corners.csv          the detected corners of every session
  sessions.csv         per session: laps, kept laps, corners, usable pairs
  summary.json
  raw_samples.parquet  every measured car sample of every kept lap, with its
                       track coordinate s and (interpolated) X/Y: the "classic"
                       flat dataset for free exploration. Local only (*.parquet
                       is gitignored); rebuilt by running this script.

Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\09_build_dataset.py
"""

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from apextrace.corners import (detect_braking_corners, fuse_window_coordinate, has_feed_gap,
                               samples_in_window, window_bounds)
from apextrace.data_loading import select_laps
from apextrace.features import FEATURES, corner_features
from apextrace.openf1 import (driver_streams, kept_laps_span, lap_samples_on_track, lap_table,
                              qualifying_sessions, reference_from_lap)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "results" / "09_dataset"
YEARS = [2023, 2024]


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


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_rows, all_corners, summaries, raw_tables = [], [], [], []
    for year in YEARS:
        sessions = qualifying_sessions(year)
        for index, session in sessions.iterrows():
            start = time.perf_counter()
            try:
                rows, corner_rows, summary, raw = build_session(year, index + 1, session)
            except Exception as exc:  # log and continue
                rows, corner_rows, raw = [], [], pd.DataFrame()
                summary = {"year": year, "round": index + 1, "location": session["location"],
                           "session_key": int(session["session_key"]), "note": f"{type(exc).__name__}: {exc}"}
            summary["seconds"] = round(time.perf_counter() - start, 1)
            all_rows.extend(rows)
            if len(raw):
                raw_tables.append(raw)
            all_corners.extend(corner_rows)
            summaries.append(summary)
            print(f"{year} R{index + 1:02d} {session['location']:20s} kept {summary.get('kept_laps', 0):3d} "
                  f"corners {summary.get('corners', 0):2d} usable {summary.get('usable_pairs', 0):4d}/"
                  f"{summary.get('pairs', 0):4d}  {summary['seconds']:5.1f} s  {summary.get('note', '')}", flush=True)

    dataset = pd.DataFrame(all_rows)
    dataset.to_csv(OUT_DIR / "dataset.csv.gz", index=False, float_format="%.3f")
    pd.DataFrame(all_corners).to_csv(OUT_DIR / "corners.csv", index=False, float_format="%.1f")
    sessions = pd.DataFrame(summaries)
    sessions.to_csv(OUT_DIR / "sessions.csv", index=False)
    raw_samples = pd.concat(raw_tables, ignore_index=True) if raw_tables else pd.DataFrame()
    raw_samples.to_parquet(OUT_DIR / "raw_samples.parquet", index=False)
    print(f"raw samples: {len(raw_samples)} rows -> {(OUT_DIR / 'raw_samples.parquet').relative_to(REPO_ROOT)} "
          f"({(OUT_DIR / 'raw_samples.parquet').stat().st_size / 1e6:.1f} MB, local only)")

    usable = dataset[dataset["usable"]] if len(dataset) else dataset
    summary = {
        "sessions": len(sessions),
        "sessions_with_data": int((sessions.get("usable_pairs", pd.Series(dtype=float)).fillna(0) > 0).sum()),
        "rows": len(dataset), "usable_rows": len(usable),
        "drivers": int(usable["driver"].nunique()) if len(usable) else 0,
        "laps": int(usable[["session_key", "driver", "lap"]].drop_duplicates().shape[0]) if len(usable) else 0,
        "corners": len(all_corners),
        "usable_by_corner_type": usable["corner_type"].value_counts().to_dict() if len(usable) else {},
        "exclusion_reasons": dataset.loc[~dataset["usable"], "reason"].value_counts().to_dict() if len(dataset) else {},
        "features": FEATURES,
    }
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, default=int)
    print(f"\n{summary['sessions']} sessions ({summary['sessions_with_data']} with data), "
          f"{summary['usable_rows']} usable rows of {summary['rows']}, {summary['drivers']} drivers, "
          f"{summary['laps']} laps, {summary['corners']} corners")
    print(f"usable rows by corner type: {summary['usable_by_corner_type']}")
    print(f"exclusions: {summary['exclusion_reasons']}")


if __name__ == "__main__":
    main()

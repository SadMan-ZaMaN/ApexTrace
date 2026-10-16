"""Phase 6, part 1: is OpenF1 a valid replacement for FastF1? Checked on 2024 Abu Dhabi.

Why: the F1 archive now refuses FastF1 downloads (401), so Phase 6 must use
OpenF1. Before trusting it, everything is compared with the FastF1 data we
already have (cached) for 2024 Abu Dhabi qualifying and FP2:

  1. Lap tables, all drivers: lap times, out/in laps, deleted laps, track
     status, the timing check (IsAccurate), compound, tyre age.
  2. Lap selection: does select_laps() keep the same laps with both sources?
  3. Features (NOR, PIA, pilot corners T6/T5/T9): computed end to end through
     OpenF1 (own reference path and lap edges) vs the FastF1-based Phase 4
     values in results/05_pilot_features/features.csv.

Outputs in results/07_openf1_validation/. Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\07_openf1_validation.py
"""

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from apextrace.corners import (corner_positions, fuse_window_coordinate, has_feed_gap,
                               samples_in_window, window_bounds)
from apextrace.data_loading import load_session, select_laps
from apextrace.features import FEATURES, corner_features
from apextrace.openf1 import fetch, lap_samples_on_track, lap_table, reference_from_lap, to_utc_naive

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "results" / "07_openf1_validation"
FASTF1_FEATURES = REPO_ROOT / "results" / "05_pilot_features" / "features.csv"
PILOT = ["T6", "T5", "T9"]
SESSION_NAMES = {"Q": "Qualifying", "FP2": "Practice 2"}


def openf1_session(year, location, session_name):
    rows = fetch("sessions", {"year": year, "session_name": session_name})
    for row in rows:
        if location.lower() in row["location"].lower():
            return int(row["session_key"]), to_utc_naive(pd.Series([row["date_end"]])).iloc[0]
    raise ValueError(f"no {session_name} session at {location} in {year}")


def compare_lap_tables(fastf1_laps, openf1_laps):
    """Join both lap tables on (driver, lap number) and count agreements column by column."""
    a = fastf1_laps[["Driver", "LapNumber", "LapTime", "PitOutTime", "PitInTime", "Deleted", "TrackStatus",
                     "IsAccurate", "Compound", "TyreLife", "Stint"]].copy()
    a["LapNumber"] = a["LapNumber"].astype(int)
    b = openf1_laps.copy()
    joined = a.merge(b, on=["Driver", "LapNumber"], how="outer", suffixes=("_fastf1", "_openf1"), indicator=True)
    both = joined[joined["_merge"] == "both"]
    result = {"laps_fastf1": len(a), "laps_openf1": len(b), "laps_in_both": len(both)}
    # Out laps: OpenF1 gives them a "lap time" that includes the time in the
    # garage, FastF1 gives none. Both drop them as out laps, so lap times are
    # compared on the other laps.
    not_out = both[both["PitOutTime_fastf1"].isna()]
    lap_time_equal = (not_out["LapTime_fastf1"].isna() & not_out["LapTime_openf1"].isna()) | \
                     ((not_out["LapTime_fastf1"] - not_out["LapTime_openf1"]).abs() <= pd.Timedelta(1, unit="ms"))
    result["lap_time_equal_except_out_laps"] = float(lap_time_equal.mean())
    result["out_lap_equal"] = float((both["PitOutTime_fastf1"].notna() == both["PitOutTime_openf1"].notna()).mean())
    result["in_lap_equal"] = float((both["PitInTime_fastf1"].notna() == both["PitInTime_openf1"].notna()).mean())
    result["deleted_equal"] = float((both["Deleted_fastf1"].fillna(False).astype(bool)
                                     == both["Deleted_openf1"].astype(bool)).mean())
    timed = both[both["LapTime_fastf1"].notna()]
    result["green_equal_on_timed_laps"] = float(((timed["TrackStatus_fastf1"] == "1")
                                                 == (timed["TrackStatus_openf1"] == "1")).mean())
    result["is_accurate_equal"] = float((both["IsAccurate_fastf1"].astype(bool)
                                         == both["IsAccurate_openf1"].astype(bool)).mean())
    result["compound_equal"] = float((both["Compound_fastf1"].fillna("") == both["Compound_openf1"].fillna("")).mean())
    result["tyre_life_equal"] = float(((both["TyreLife_fastf1"] - both["TyreLife_openf1"]).abs() < 0.5).mean())
    result["stint_equal"] = float((both["Stint_fastf1"] == both["Stint_openf1"]).mean())
    mismatches = both[(both["PitInTime_fastf1"].notna() != both["PitInTime_openf1"].notna())
                      | (both["IsAccurate_fastf1"].astype(bool) != both["IsAccurate_openf1"].astype(bool))
                      | (both["Stint_fastf1"] != both["Stint_openf1"])]
    return result, mismatches


def compare_kept_laps(fastf1_laps, openf1_laps):
    rows = []
    for driver in sorted(set(fastf1_laps["Driver"])):
        kept_a, _ = select_laps(fastf1_laps[fastf1_laps["Driver"] == driver])
        kept_b, _ = select_laps(openf1_laps[openf1_laps["Driver"] == driver])
        set_a = set(int(n) for n in kept_a["LapNumber"])
        set_b = set(int(n) for n in kept_b["LapNumber"])
        rows.append({"driver": driver, "kept_fastf1": len(set_a), "kept_openf1": len(set_b),
                     "same": set_a == set_b, "only_fastf1": sorted(set_a - set_b), "only_openf1": sorted(set_b - set_a)})
    return pd.DataFrame(rows)


def openf1_features(session_label, session_key, openf1_laps, reference, corner_s):
    rows = []
    for driver in ["NOR", "PIA"]:
        kept, _ = select_laps(openf1_laps[openf1_laps["Driver"] == driver])
        for _, lap in kept.iterrows():
            samples = lap_samples_on_track(session_key, int(lap["DriverNumber"]), lap["LapStartDate"],
                                           lap["LapTime"], reference)
            for corner in PILOT:
                start, end = window_bounds(corner_s[corner])
                window = samples_in_window(samples, start, end)
                row = {"session": session_label, "driver": driver, "lap": int(lap["LapNumber"]), "corner": corner}
                if window is None or has_feed_gap(window):
                    rows.append({**row, "usable": False})
                    continue
                fused, _, _, _ = fuse_window_coordinate(samples, window)
                rows.append({**row, "usable": True, **corner_features(window, fused, corner_s[corner])})
    return pd.DataFrame(rows)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    logging.getLogger("fastf1").setLevel(logging.WARNING)
    summary = {"lap_tables": {}, "kept_laps": {}}
    feature_tables = []

    fastf1_q = load_session(2024, "Abu Dhabi", "Q")
    q_key, q_end = openf1_session(2024, "Yas", SESSION_NAMES["Q"])
    q_laps = lap_table(q_key, q_end)
    pole = q_laps[q_laps["LapTime"] == q_laps["LapTime"].min()].iloc[0]
    reference = reference_from_lap(q_key, int(pole["DriverNumber"]), pole["LapStartDate"], pole["LapTime"])
    circuit = fastf1_q.get_circuit_info().corners
    names = [f"T{int(n)}" for n in circuit["Number"]]
    corner_s = dict(zip(names, corner_positions(circuit["X"], circuit["Y"], circuit["Distance"], reference)))

    for label in ["Q", "FP2"]:
        fastf1_session = fastf1_q if label == "Q" else load_session(2024, "Abu Dhabi", "FP2")
        key, end = (q_key, q_end) if label == "Q" else openf1_session(2024, "Yas", SESSION_NAMES[label])
        laps = q_laps if label == "Q" else lap_table(key, end)
        result, mismatches = compare_lap_tables(fastf1_session.laps, laps)
        mismatches.to_csv(OUT_DIR / f"lap_table_mismatches_{label}.csv", index=False)
        kept = compare_kept_laps(fastf1_session.laps, laps)
        kept.to_csv(OUT_DIR / f"kept_laps_{label}.csv", index=False)
        summary["lap_tables"][label] = result
        summary["kept_laps"][label] = {"drivers": len(kept), "same_kept_laps": int(kept["same"].sum())}
        print(f"\n=== {label}: lap tables, FastF1 vs OpenF1 (share of laps that agree) ===")
        for key_name, value in result.items():
            print(f"  {key_name:28s} {value if isinstance(value, int) else round(value, 4)}")
        print(f"  kept laps identical for {int(kept['same'].sum())} of {len(kept)} drivers")
        different = kept[~kept["same"]]
        if len(different):
            print(different.to_string(index=False))
        feature_tables.append(openf1_features(label, key, laps, reference, corner_s))

    ours = pd.concat(feature_tables, ignore_index=True)
    ours.to_csv(OUT_DIR / "features_openf1.csv", index=False, float_format="%.3f")
    theirs = pd.read_csv(FASTF1_FEATURES)
    joined = theirs.merge(ours, on=["session", "driver", "lap", "corner"], suffixes=("_fastf1", "_openf1"))
    both_usable = joined[joined["usable_fastf1"] & joined["usable_openf1"]]
    print(f"\n=== Features, FastF1 vs OpenF1: {len(both_usable)} (lap, corner) pairs usable in both; "
          f"usable in FastF1 only {int((joined['usable_fastf1'] & ~joined['usable_openf1']).sum())}, "
          f"OpenF1 only {int((~joined['usable_fastf1'] & joined['usable_openf1']).sum())} ===")
    feature_summary = {}
    for feature in FEATURES:
        difference = (both_usable[f"{feature}_openf1"] - both_usable[f"{feature}_fastf1"]).dropna()
        feature_summary[feature] = {"pairs": int(len(difference)),
                                    "median_abs_diff": float(difference.abs().median()),
                                    "max_abs_diff": float(difference.abs().max()),
                                    "mean_diff": float(difference.mean())}
        f = feature_summary[feature]
        print(f"  {feature:20s} median |diff| {f['median_abs_diff']:7.3f}   max |diff| {f['max_abs_diff']:7.3f}   "
              f"mean diff {f['mean_diff']:+7.3f}")
    summary["features"] = feature_summary
    summary["feature_pairs_usable_in_both"] = int(len(both_usable))
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)
    print(f"\nSaved results to {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

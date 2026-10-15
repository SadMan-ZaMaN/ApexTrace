"""Phase 1 data pilot: what does the real data look like, before we build on it?

Each check from the PROJECT_CONTEXT §7 checklist becomes one number or table
here, plus one sentence in docs/data_report.md. This script grows check by
check; so far it does:

  Check 6, usable laps: every NOR and PIA lap in 2024 Abu Dhabi qualifying
           and FP2, with compound, tyre age, and kept/dropped plus the
           reason. -> results/01_data_pilot/lap_table.csv
  Check 8, FastF1's lap-filter helpers: do they exist in our version, and
           does chaining them keep the same laps as our select_laps()?

Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\01_data_pilot.py
"""

from pathlib import Path

import pandas as pd

from apextrace.data_loading import load_session, select_laps

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "results" / "01_data_pilot"

YEAR = 2024
EVENT = "Abu Dhabi"
SESSIONS = ["Q", "FP2"]
DRIVERS = ["NOR", "PIA"]


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


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tables = []

    for session_name in SESSIONS:
        session = load_session(YEAR, EVENT, session_name)
        print(f"\n=== {YEAR} {EVENT} {session_name} ===")

        for driver in DRIVERS:
            laps = session.laps.pick_drivers(driver)
            kept, dropped = select_laps(laps)
            tables.append(build_lap_table(session_name, session, laps, dropped))

            ours = sorted(int(n) for n in kept["LapNumber"])
            helpers = fastf1_helper_chain(laps)
            same = "same laps" if ours == helpers else f"DIFFERENT: helpers keep {helpers}"
            print(f"{driver}: {len(laps)} laps, kept {len(kept)}: {ours}")
            print(f"     check 8, FastF1 helper chain: {same}")

    table = pd.concat(tables, ignore_index=True)
    table.to_csv(OUT_DIR / "lap_table.csv", index=False)

    # Summary 1: kept laps per session and driver, by compound
    print("\n--- Kept laps by session, driver, compound ---")
    kept_rows = table[table["Kept"]]
    print(kept_rows.groupby(["Session", "Driver", "Compound"]).size().to_string())

    # Summary 2: why laps were dropped
    print("\n--- Drop reasons (a lap can have several) ---")
    reason_counts = {}
    for reasons in table.loc[~table["Kept"], "Reason"]:
        for reason in reasons.split("; "):
            if reason.startswith("slow lap"):
                reason = "slow lap (> 107 % of stint best)"
            if reason.startswith("not a timed run"):
                reason = "not a timed run (stint best > 115 % of driver's best)"
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    for reason, count in sorted(reason_counts.items(), key=lambda item: -item[1]):
        print(f"{count:4d}  {reason}")

    print(f"\nSaved {(OUT_DIR / 'lap_table.csv').relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

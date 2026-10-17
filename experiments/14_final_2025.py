"""Phase 7: THE ONE-TIME FINAL EVALUATION on the frozen 2025 season (docs/preregistration.md, Part B).

Everything here was written, and committed with the preregistration, BEFORE
any 2025 data was loaded. It uses exactly the development code
(session_build, dataset, identification, protocol, signatures).

Guards (it stops otherwise):
  - the environment variable FINAL_TEST must be "1" (2025 is frozen);
  - docs/preregistration.md must contain Part B and be committed, unchanged;
  - results/final/ must not exist yet: the final evaluation runs ONCE.
    (If a bug is found afterwards: fix it, rerun into a new folder, report both;
    see the preregistration.)

Steps:
  1. download and build every 2025 qualifying session (same pipeline as 2023-24);
  2. H3 replication: teammate identification on 2025, leave-one-session-out,
     our features vs lap time only (primary, Wilcoxon) and vs raw lap statistics;
  3. H4: drivers who changed teams for 2025 (HAM, SAI, OCO, HUL, TSU): is each
     one's 2025 signature closer to their OWN 2024 signature (other car) than to
     their NEW TEAMMATE's 2025 signature (same car)? One-sided sign test.
     Secondary: the same for the brake-flag share; own-rank among 2024 signatures;
     and the development check (own vs teammate) for drivers who did NOT change teams.

Run from the repo root, once, after committing the preregistration (PowerShell):
    $env:FINAL_TEST = "1"; .venv\\Scripts\\python.exe experiments\\14_final_2025.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from apextrace.dataset import add_field_relative, clean, load_dataset
from apextrace.identification import build_lap_table
from apextrace.openf1 import download_session, qualifying_sessions
from apextrace.protocol import summarise_teammates, teammate_task
from apextrace.session_build import build_session
from apextrace.signatures import distance, distance_table, own_rank, season_signatures, sign_test_p, standardise

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "results" / "final"
DEV_RAW = REPO_ROOT / "results" / "09_dataset" / "raw_samples.parquet"
PREREGISTRATION = "docs/preregistration.md"
FINAL_YEAR = 2025
REFERENCE_YEAR = 2024
SEED = 2026
SHUFFLES = 5
CHANGERS = ["HAM", "SAI", "OCO", "HUL", "TSU"]      # preregistered (Part B)
MIN_WEEKENDS = 5


# ---------------------------------------------------------------- guards

def guards():
    problems = []
    if os.environ.get("FINAL_TEST") != "1":
        problems.append("FINAL_TEST is not 1")
    text = (REPO_ROOT / PREREGISTRATION).read_text(encoding="utf-8")
    if "## Part B" not in text or "*To be written" in text:
        problems.append("Part B of the preregistration is not written")
    committed = subprocess.run(["git", "log", "--format=%H %ci", "-1", "--", PREREGISTRATION],
                               cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
    unchanged = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", PREREGISTRATION], cwd=REPO_ROOT).returncode == 0
    if not committed or not unchanged:
        problems.append("the preregistration is not committed (or has uncommitted changes)")
    if OUT_DIR.exists():
        problems.append(f"{OUT_DIR.relative_to(REPO_ROOT)} exists: the final evaluation has already been run")
    if problems:
        print("STOP:\n  - " + "\n  - ".join(problems))
        sys.exit(1)
    return committed


# ---------------------------------------------------------------- data

def build_2025():
    rows, corners, summaries, raw_tables = [], [], [], []
    sessions = qualifying_sessions(FINAL_YEAR)
    for index, session in sessions.iterrows():
        counts = download_session(int(session["session_key"]), session["date_end"])
        session_rows, session_corners, summary, raw = build_session(FINAL_YEAR, index + 1, session)
        summary.update({f"download_{k}": v for k, v in counts.items()})
        rows.extend(session_rows)
        corners.extend(session_corners)
        summaries.append(summary)
        if len(raw):
            raw_tables.append(raw)
        print(f"{FINAL_YEAR} R{index + 1:02d} {session['location']:20s} kept {summary.get('kept_laps', 0):3d} "
              f"corners {summary.get('corners', 0):2d} usable {summary.get('usable_pairs', 0):4d}/"
              f"{summary.get('pairs', 0):4d} {summary.get('note', '')}", flush=True)
    dataset = pd.DataFrame(rows)
    raw = pd.concat(raw_tables, ignore_index=True)
    return dataset, pd.DataFrame(corners), pd.DataFrame(summaries), raw


def lap_tables(dataset_2025, raw_2025):
    clean_2025, cleaning_2025 = clean(dataset_2025)
    laps_2025 = build_lap_table(add_field_relative(clean_2025), raw_2025)
    development = load_dataset()
    clean_2024, _ = clean(development[development["year"] == REFERENCE_YEAR])
    raw_dev = pd.read_parquet(DEV_RAW, columns=["session_key", "driver", "lap", "speed_kmh", "throttle_pct", "brake"])
    laps_2024 = build_lap_table(add_field_relative(clean_2024), raw_dev)
    return laps_2025, laps_2024, cleaning_2025


# ---------------------------------------------------------------- H4

def most_weekends_team(laps, driver):
    weekends = laps[laps["driver"] == driver].groupby("team")["session_key"].nunique()
    return weekends.idxmax(), int(weekends.max())


def h4(laps_2025, laps_2024):
    corner_columns = [c for c in laps_2024.columns if "__" in c]
    columns = corner_columns + ["share_braking_rel"]
    reference_raw = season_signatures(laps_2024, columns, min_sessions=MIN_WEEKENDS).xs(REFERENCE_YEAR, level="year")
    reference = standardise(reference_raw, corner_columns, reference_raw)

    rows = []
    for driver in CHANGERS:
        row = {"driver": driver}
        if driver not in reference.index:
            rows.append({**row, "included": False, "reason": f"fewer than {MIN_WEEKENDS} weekends in {REFERENCE_YEAR}"})
            continue
        team, weekends = most_weekends_team(laps_2025, driver)
        team_laps = laps_2025[laps_2025["team"] == team]
        driver_sessions = set(team_laps.loc[team_laps["driver"] == driver, "session_key"])
        others = team_laps[(team_laps["driver"] != driver) & team_laps["session_key"].isin(driver_sessions)]
        if weekends < MIN_WEEKENDS or others.empty:
            rows.append({**row, "included": False, "reason": f"fewer than {MIN_WEEKENDS} weekends with the new team"})
            continue
        teammate = others.groupby("driver")["session_key"].nunique().idxmax()
        pair_laps = team_laps[team_laps["driver"].isin([driver, teammate]) & team_laps["session_key"].isin(driver_sessions)]
        new_raw = season_signatures(pair_laps, columns, min_sessions=MIN_WEEKENDS).xs(FINAL_YEAR, level="year")
        if teammate not in new_raw.index or driver not in new_raw.index:
            rows.append({**row, "included": False, "reason": "teammate with fewer than 5 shared weekends"})
            continue
        new = standardise(new_raw, corner_columns, reference_raw)
        d_own = distance(new.loc[driver, corner_columns], reference.loc[driver, corner_columns])
        d_mate = distance(new.loc[driver, corner_columns], new.loc[teammate, corner_columns])
        share_own = abs(new_raw.loc[driver, "share_braking_rel"] - reference_raw.loc[driver, "share_braking_rel"])
        share_mate = abs(new_raw.loc[driver, "share_braking_rel"] - new_raw.loc[teammate, "share_braking_rel"])
        distances = distance_table(new.loc[[driver]], reference, corner_columns)
        rows.append({**row, "included": True, "reason": "", "team_2025": team, "weekends_2025": weekends,
                     "teammate_2025": teammate, "team_2024": reference_raw.loc[driver, "team"],
                     "distance_own_2024": d_own, "distance_new_teammate_2025": d_mate, "own_closer": bool(d_own < d_mate),
                     "share_braking_own_gap": share_own, "share_braking_teammate_gap": share_mate,
                     "share_braking_own_closer": bool(share_own < share_mate),
                     "own_rank_among_2024": own_rank(distances, driver), "drivers_2024": int(len(reference))})
    table = pd.DataFrame(rows)
    included = table[table["included"]]
    wins = int(included["own_closer"].sum())
    share_wins = int(included["share_braking_own_closer"].sum())
    summary = {"changers_included": int(len(included)), "own_closer": wins,
               "sign_test_p": sign_test_p(wins, len(included)) if len(included) else None,
               "share_braking_own_closer": share_wins,
               "share_braking_sign_test_p": sign_test_p(share_wins, len(included)) if len(included) else None,
               "min_possible_p": sign_test_p(len(included), len(included)) if len(included) else None}
    return table, summary


def non_changer_check(laps_2025, laps_2024):
    """The development check (own vs teammate, same team both years) for 2025 drivers who did NOT change teams."""
    corner_columns = [c for c in laps_2024.columns if "__" in c]
    reference_raw = season_signatures(laps_2024, corner_columns, min_sessions=MIN_WEEKENDS).xs(REFERENCE_YEAR, level="year")
    new_raw = season_signatures(laps_2025, corner_columns, min_sessions=MIN_WEEKENDS).xs(FINAL_YEAR, level="year")
    reference = standardise(reference_raw, corner_columns, reference_raw)
    new = standardise(new_raw, corner_columns, reference_raw)
    rows = []
    for driver in sorted(set(new.index) & set(reference.index)):
        if driver in CHANGERS:
            continue
        mates = [d for d in reference.index if d != driver and reference_raw.loc[d, "team"] == reference_raw.loc[driver, "team"]]
        if not mates:
            continue
        d_own = distance(new.loc[driver, corner_columns], reference.loc[driver, corner_columns])
        d_mate = float(np.mean([distance(new.loc[driver, corner_columns], reference.loc[m, corner_columns]) for m in mates]))
        rows.append({"driver": driver, "distance_own": d_own, "distance_old_teammate": d_mate, "own_closer": bool(d_own < d_mate)})
    table = pd.DataFrame(rows)
    wins = int(table["own_closer"].sum()) if len(table) else 0
    return table, {"drivers": int(len(table)), "own_closer": wins,
                   "sign_test_p": sign_test_p(wins, len(table)) if len(table) else None}


def main():
    commit = guards()
    OUT_DIR.mkdir(parents=True)
    print(f"preregistration commit: {commit}\n")

    dataset, corners, sessions, raw = build_2025()
    dataset.to_csv(OUT_DIR / "dataset_2025.csv.gz", index=False, float_format="%.3f")
    corners.to_csv(OUT_DIR / "corners_2025.csv", index=False, float_format="%.1f")
    sessions.to_csv(OUT_DIR / "sessions_2025.csv", index=False)
    raw.to_parquet(OUT_DIR / "raw_samples_2025.parquet", index=False)
    laps_2025, laps_2024, cleaning = lap_tables(dataset, raw)

    rng = np.random.default_rng(SEED)
    print("\n--- H3 replication on 2025: teammates ---")
    teammates = teammate_task(laps_2025, rng, shuffles=SHUFFLES)
    teammates.to_csv(OUT_DIR / "h3_teammates_2025.csv", index=False, float_format="%.4f")
    h3 = summarise_teammates(teammates, rng)

    print("\n--- H4: team changers ---")
    h4_table, h4_summary = h4(laps_2025, laps_2024)
    h4_table.to_csv(OUT_DIR / "h4_changers.csv", index=False, float_format="%.4f")
    print(h4_table.to_string(index=False))
    control_table, control_summary = non_changer_check(laps_2025, laps_2024)
    control_table.to_csv(OUT_DIR / "h4_non_changers.csv", index=False, float_format="%.4f")

    primary = h3["ours minus lap time only"]
    summary = {"preregistration_commit": commit, "cleaning_2025": cleaning, "laps_2025": int(len(laps_2025)),
               "h3": h3, "h4": h4_summary, "non_changer_check": control_summary,
               "h3_supported": bool(primary["wilcoxon_p"] < 0.05 and primary["mean_difference"] > 0),
               "h4_supported": bool(h4_summary["sign_test_p"] is not None and h4_summary["sign_test_p"] < 0.05)}
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, default=float)
    print(f"\nH3 (primary): ours minus lap time {primary['mean_difference']:+.3f}, better in {primary['wins']} of "
          f"{primary['team_seasons']}, Wilcoxon p = {primary['wilcoxon_p']:.4f} -> supported: {summary['h3_supported']}")
    print(f"H4 (primary): own 2024 closer than new 2025 teammate for {h4_summary['own_closer']} of "
          f"{h4_summary['changers_included']}, sign test p = {h4_summary['sign_test_p']} -> supported: {summary['h4_supported']}")
    print(f"Saved results to {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

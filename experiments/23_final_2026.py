"""THE ONE-TIME 2026 TEST (docs/preregistration.md, Part C): H5, and H4 on the 2026 team changers.

Everything here is written, and committed with Part C, BEFORE any 2026 data is loaded.
Every result comes from apextrace.h5_protocol, the same code the dry runs test.

Guards (it stops otherwise):
  - the environment variable FINAL_TEST_2026 must be "1" (2026 is frozen in the code);
  - docs/preregistration.md must contain Part C and be committed, unchanged;
  - this script and the package (src/apextrace/) must be committed, unchanged, so the
    code that runs is the code that was committed with the plan;
  - results/final_2026/summary.json must not exist: the test runs ONCE. If an earlier
    attempt stopped before any result, its folder must be recorded in
    docs/preregistration_deviations.md and renamed to final_2026_attempt_<n> first.

Phases, each finished before the next starts (the Baku lesson: download first, then analyse):
  1. download every 2026 main qualifying session that ended at least 24 h before the run
     (a session whose download fails is listed and skipped);
  2. checks BEFORE any feature: the feed (quality.feed_check, only samples inside kept
     laps) and the team names (teams.unknown_team_names). Either failing -> STOP, no result;
  3. build the 2026 dataset from the cache (session_build, exactly as for 2023-2025);
  4. analyse (h5_protocol): H5 primary + secondary, H4 on changers + stayer control.

Dry runs (no guards; never write into results/final_2026/):
  --dry-run 2024   target 2024, reference 2023: phases 1-4 from the local cache. The H5 count
                   must equal experiments/20_h5_development.py (16 of 20).
  --dry-run 2025   target 2025, reference 2024, analysis only (2025's download stays guarded):
                   H5 must equal experiment 20 (15 of 16), and with Part B's spread
                   (leave_pair_out=False) H4 must reproduce the frozen numbers.

Run (PowerShell), the real test, once, after Part C is committed:
    $env:FINAL_TEST_2026 = "1"; .venv\\Scripts\\python.exe experiments\\23_final_2026.py
Dry runs:
    .venv\\Scripts\\python.exe experiments\\23_final_2026.py --dry-run 2024
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from apextrace import h5_protocol
from apextrace.dataset import load_dataset
from apextrace.openf1 import download_session, drivers_of, qualifying_sessions, session_feed_tables
from apextrace.quality import feed_check
from apextrace.session_build import build_session
from apextrace.teams import unknown_team_names

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "results"
OUT_DIR = RESULTS / "final_2026"
DRY_RUN_DIR = RESULTS / "final_2026_dry_run"
PREREGISTRATION = "docs/preregistration.md"
THIS_SCRIPT = "experiments/23_final_2026.py"
PACKAGE = "src/apextrace"
FINAL_YEAR, REFERENCE_YEAR = 2026, 2025
SWITCH = "FINAL_TEST_2026"
CUTOFF_HOURS = 24


# ---------------------------------------------------------------- guards

def guard_problems(switch_value, preregistration_text, preregistration_committed, preregistration_unchanged,
                   code_unchanged, out_dir):
    """Every reason not to run, as a list (empty = go). Pure, so the tests can check each one."""
    problems = []
    if switch_value != "1":
        problems.append(f"{SWITCH} is not 1")
    if "## Part C" not in preregistration_text:
        problems.append("Part C of the preregistration is not written")
    elif "*To be written" in preregistration_text.split("## Part C", 1)[1]:
        problems.append("Part C of the preregistration still has a placeholder")
    if not preregistration_committed or not preregistration_unchanged:
        problems.append("the preregistration is not committed (or has uncommitted changes)")
    if not code_unchanged:
        problems.append(f"{THIS_SCRIPT} or {PACKAGE}/ has uncommitted changes: commit the code that will run")
    out_dir = Path(out_dir)
    if (out_dir / "summary.json").exists():
        problems.append(f"{out_dir.name}/summary.json exists: the 2026 test has already been run")
    elif out_dir.exists():
        problems.append(f"{out_dir.name}/ exists from an attempt that stopped early: record it in "
                        f"docs/preregistration_deviations.md, rename it to {out_dir.name}_attempt_<n>, then run again")
    return problems


def git(*arguments):
    return subprocess.run(["git", *arguments], cwd=REPO_ROOT, capture_output=True, text=True)


def guards():
    text = (REPO_ROOT / PREREGISTRATION).read_text(encoding="utf-8")
    committed = git("log", "--format=%H %ci", "-1", "--", PREREGISTRATION).stdout.strip()
    preregistration_unchanged = git("diff", "--quiet", "HEAD", "--", PREREGISTRATION).returncode == 0
    code_unchanged = (git("diff", "--quiet", "HEAD", "--", THIS_SCRIPT, PACKAGE).returncode == 0
                      and not git("ls-files", "--others", "--exclude-standard", PACKAGE).stdout.strip())
    problems = guard_problems(os.environ.get(SWITCH), text, committed, preregistration_unchanged, code_unchanged,
                              OUT_DIR)
    if problems:
        print("STOP:\n  - " + "\n  - ".join(problems))
        sys.exit(1)
    return committed, git("rev-parse", "HEAD").stdout.strip()


# ---------------------------------------------------------------- phases

def sessions_to_use(sessions, now, cutoff_hours=CUTOFF_HOURS):
    """Main qualifying sessions that ended at least cutoff_hours before `now` (UTC, naive).
    Example: run on Monday 10:00 -> a session that ended on Sunday 11:00 is in (23 h is not)."""
    cutoff = now - timedelta(hours=cutoff_hours)
    return sessions[sessions["date_end"] <= cutoff].reset_index(drop=True), cutoff


def download_all(sessions):
    """Phase 1: everything into the cache, before anything is analysed. Errors are listed, not fatal."""
    rows = []
    for index, session in sessions.iterrows():
        row = {"round": index + 1, "location": session["location"], "session_key": int(session["session_key"]),
               "error": ""}
        try:
            row.update(download_session(row["session_key"], session["date_end"]))
        except Exception as error:      # listed and skipped, as Part C says
            row["error"] = f"{type(error).__name__}: {error}"
        rows.append(row)
        print(f"  download R{row['round']:02d} {row['location']:20s} {row.get('kept_laps', '-')!s:>4} kept laps "
              f"{row['error']}", flush=True)
    return pd.DataFrame(rows)


def run_checks(sessions):
    """Phase 2: the feed and the team names, before any feature. Returns (ok, report)."""
    cars, positions, team_names = [], [], set()
    for _, session in sessions.iterrows():
        session_cars, session_positions = session_feed_tables(int(session["session_key"]), session["date_end"])
        cars.extend(session_cars)
        positions.extend(session_positions)
        for _, team in drivers_of(int(session["session_key"])).values():
            team_names.add(team)
    feed = feed_check(cars, positions)
    unknown = unknown_team_names(team_names)
    report = {"feed": feed, "team_names": sorted(team_names), "unknown_team_names": unknown,
              "lap_tables_checked": len(cars)}
    return bool(feed["ok"] and not unknown), report


def build_all(year, sessions):
    """Phase 3: the dataset, from the cache, with the 2023-2025 code (session_build)."""
    rows, corners, summaries, raw_tables = [], [], [], []
    for index, session in sessions.iterrows():
        session_rows, session_corners, summary, raw = build_session(year, index + 1, session)
        rows.extend(session_rows)
        corners.extend(session_corners)
        summaries.append(summary)
        if len(raw):
            raw_tables.append(raw)
        print(f"  build R{index + 1:02d} {session['location']:20s} usable {summary.get('usable_pairs', 0):4d} "
              f"{summary.get('note', '')}", flush=True)
    return pd.DataFrame(rows), pd.DataFrame(corners), pd.DataFrame(summaries), pd.concat(raw_tables, ignore_index=True)


def analyse(laps, reference_year, target_year, out_dir, leave_pair_out=True):
    """Phase 4: every result, from h5_protocol. Writes the per-driver tables; returns the summary."""
    tables, h5 = h5_protocol.h5_results(laps, reference_year, target_year)
    for name, table in tables.items():
        table.to_csv(out_dir / f"h5_{name.replace(' ', '_')}.csv", index=False, float_format="%.4f")
    changes, changers, stayers, h4 = h5_protocol.h4_results(laps, reference_year, target_year, leave_pair_out)
    changes.to_csv(out_dir / "team_changes.csv", index=False)
    changers.to_csv(out_dir / "h4_changers.csv", index=False, float_format="%.4f")
    stayers.to_csv(out_dir / "h4_stayers.csv", index=False, float_format="%.4f")
    return {"h5": h5, "h4": h4}


def save_build(out_dir, year, dataset, corners, summaries, raw):
    dataset.to_csv(out_dir / f"dataset_{year}.csv.gz", index=False, float_format="%.3f")
    corners.to_csv(out_dir / f"corners_{year}.csv", index=False, float_format="%.1f")
    summaries.to_csv(out_dir / f"sessions_{year}.csv", index=False)
    raw.to_parquet(out_dir / f"raw_samples_{year}.parquet", index=False)


def reference_lap_table(year):
    """The reference season's lap table from the saved development data."""
    if year == 2025:
        dataset = pd.read_csv(RESULTS / "final" / "dataset_2025.csv.gz")
        raw = pd.read_parquet(RESULTS / "final" / "raw_samples_2025.parquet")
    else:
        development = load_dataset()
        dataset = development[development["year"] == year]
        raw = pd.read_parquet(RESULTS / "09_dataset" / "raw_samples.parquet")
    laps, _ = h5_protocol.lap_table_from(dataset, raw)
    return laps


def report(summary):
    primary = summary["h5"]["sets"]["all"]
    print(f"\nH5 (primary): own past closer for {primary['own_closer']} of {primary['drivers']}, "
          f"sign test p = {primary['sign_test_p']} -> supported: {summary['h5']['supported']}")
    for name, result in summary["h5"]["sets"].items():
        print(f"   {name:17s} {result['own_closer']} of {result['drivers']}")
    h4 = summary["h4"]
    print(f"H4 (secondary): changers {h4['changer_names']}: {h4['changers']['own_closer']} of "
          f"{h4['changers']['drivers']}; stayers {h4['stayers']['own_closer']} of {h4['stayers']['drivers']}; "
          f"Fisher p = {h4['fisher_exact_two_sided_p']}")


# ---------------------------------------------------------------- the real run and the dry runs

def real_run():
    preregistration_commit, code_commit = guards()
    OUT_DIR.mkdir(parents=True)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    sessions, cutoff = sessions_to_use(qualifying_sessions(FINAL_YEAR), now)
    start = {"preregistration_commit": preregistration_commit, "code_commit": code_commit,
             "started_utc": now.isoformat(), "cutoff_utc": cutoff.isoformat(),
             "sessions": sessions[["session_key", "location", "date_end"]].astype(str).to_dict("records")}
    (OUT_DIR / "run_started.json").write_text(json.dumps(start, indent=2), encoding="utf-8")

    print(f"phase 1: download {len(sessions)} sessions (ended before {cutoff:%Y-%m-%d %H:%M} UTC)")
    downloads = download_all(sessions)
    downloads.to_csv(OUT_DIR / "download_log.csv", index=False)
    sessions = sessions[downloads["error"].eq("").to_numpy()].reset_index(drop=True)

    print("phase 2: checks before any feature")
    ok, checks = run_checks(sessions)
    (OUT_DIR / "checks.json").write_text(json.dumps(checks, indent=2, default=str), encoding="utf-8")
    if not ok:
        print("STOP: the feed or the team names failed the checks (results/final_2026/checks.json). "
              "No result was produced; follow Part C (log a deviation before anything else).")
        sys.exit(2)

    print("phase 3: build")
    dataset, corners, summaries, raw = build_all(FINAL_YEAR, sessions)
    save_build(OUT_DIR, FINAL_YEAR, dataset, corners, summaries, raw)
    target, cleaning = h5_protocol.lap_table_from(dataset, raw)
    laps = pd.concat([reference_lap_table(REFERENCE_YEAR), target], ignore_index=True)

    print("phase 4: analyse")
    summary = analyse(laps, REFERENCE_YEAR, FINAL_YEAR, OUT_DIR)
    summary.update({**start, "cleaning": cleaning, "laps": int(len(target)), "checks_ok": ok})
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, default=str)
    report(summary)


def dry_run(target_year):
    out_dir = DRY_RUN_DIR / str(target_year)
    out_dir.mkdir(parents=True, exist_ok=True)
    reference_year = target_year - 1
    expected = json.loads((RESULTS / "20_h5_development" / "summary.json").read_text(encoding="utf-8"))
    expected = expected["pairs"][f"{reference_year} -> {target_year}"]

    if target_year == 2024:
        sessions = qualifying_sessions(target_year)
        print(f"phase 1: download {len(sessions)} sessions (from the local cache)")
        downloads = download_all(sessions)
        downloads.to_csv(out_dir / "download_log.csv", index=False)
        sessions = sessions[downloads["error"].eq("").to_numpy()].reset_index(drop=True)
        print("phase 2: checks")
        ok, checks = run_checks(sessions)
        (out_dir / "checks.json").write_text(json.dumps(checks, indent=2, default=str), encoding="utf-8")
        print(f"  checks ok: {ok}; unknown team names: {checks['unknown_team_names']}")
        print("phase 3: build")
        dataset, corners, summaries, raw = build_all(target_year, sessions)
        save_build(out_dir, target_year, dataset, corners, summaries, raw)
        target, _ = h5_protocol.lap_table_from(dataset, raw)
    elif target_year == 2025:
        print("analysis only: 2025 from the saved data in results/final/ (its download stays guarded)")
        target = reference_lap_table(2025)
    else:
        raise SystemExit("dry runs: 2024 or 2025")

    laps = pd.concat([reference_lap_table(reference_year), target], ignore_index=True)
    summary = analyse(laps, reference_year, target_year, out_dir)
    if target_year == 2025:
        _, _, _, part_b = h5_protocol.h4_results(laps, reference_year, target_year, leave_pair_out=False)
        summary["h4_with_part_b_spread"] = part_b
    primary = summary["h5"]["sets"]["all"]
    summary["matches_experiment_20"] = (primary["own_closer"] == expected["all"]["own_closer"]
                                        and primary["drivers"] == expected["all"]["drivers"])
    with open(out_dir / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, default=str)
    report(summary)
    print(f"\nH5 equals experiment 20 ({expected['all']['own_closer']} of {expected['all']['drivers']}): "
          f"{summary['matches_experiment_20']}")
    if target_year == 2025:
        b = summary["h4_with_part_b_spread"]
        print(f"H4 with Part B's spread: changers {b['changers']['own_closer']} of {b['changers']['drivers']}, "
              f"stayers {b['stayers']['own_closer']} of {b['stayers']['drivers']} "
              f"(frozen exploratory: 3 of 6 and 8 of 10)")
    print(f"wrote {out_dir.relative_to(REPO_ROOT)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", type=int, choices=[2024, 2025], help="rehearse on a past season")
    arguments = parser.parse_args()
    if arguments.dry_run:
        dry_run(arguments.dry_run)
    else:
        real_run()


if __name__ == "__main__":
    main()

"""THE ONE-TIME 2026 TEST (docs/preregistration.md, Part C): H5, and H4 on the 2026 team changers.

Everything here is written, and committed with Part C, BEFORE any 2026 data is loaded.
Every result comes from apextrace.h5_protocol, the same code the dry runs test.

Guards (it stops otherwise):
  - the environment variable FINAL_TEST_2026 must be "1" (2026 is frozen in the code);
  - docs/preregistration.md must contain Part C and be committed, unchanged;
  - this script, the package (src/apextrace/) and the pinned reference files must be the
    same as in the commit that added Part C, and committed, unchanged: the code that runs
    is the code that was committed with the plan;
  - the 2025 reference files must exist and match their fingerprints (SHA-256) recorded in
    results/24_dry_run_checks/summary.json (the raw samples are not in git);
  - the run must start at least 24 h after the fixed session cutoff, CUTOFF_UTC;
  - no results/final_2026*/summary.json may exist anywhere: the test runs ONCE, and
    renaming a finished folder doesn't make it run again;
  - results/final_2026/ must not exist. A folder from an attempt that stopped early must be
    recorded in docs/preregistration_deviations.md and renamed final_2026_attempt_<n>
    first. If that folder holds any result file (h5_*, h4_*, team_changes.csv), the attempt
    counts as a run: the bug rule applies, not the crash rule.

Phases, each finished before the next starts (the Baku lesson: download first, then analyse):
  1. download every 2026 main qualifying session that ended before CUTOFF_UTC; failed
     downloads are retried twice, and a session that still fails STOPS the run (no result);
  2. checks BEFORE any feature: the feed (quality.feed_check, only samples inside kept
     laps), the team names (teams.unknown_team_names) and the tyre-compound labels
     (dataset.compound_check). Any failing -> STOP, no result;
  3. build the 2026 dataset from the cache (session_build, exactly as for 2023-2025);
  4. analyse (h5_protocol), entirely in memory; every result file is written at the end,
     summary.json last.

Dry runs (no guards; never write into results/final_2026/):
  --dry-run 2024   target 2024, reference 2023: phases 1-4 from the local cache. The H5 count
                   must equal experiments/20_h5_development.py.
  --dry-run 2025   target 2025, reference 2024, analysis only (2025's download stays guarded):
                   H5 must equal experiment 20, and with Part B's spread (leave_pair_out=False)
                   the H4 code must reproduce the frozen distances (experiments/24_dry_run_checks.py).

Run (PowerShell), the real test, once, after Part C is committed:
    $env:FINAL_TEST_2026 = "1"; .venv\\Scripts\\python.exe experiments\\23_final_2026.py
Dry runs:
    .venv\\Scripts\\python.exe experiments\\23_final_2026.py --dry-run 2024
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from apextrace import h5_protocol
from apextrace.data_loading import select_laps
from apextrace.dataset import compound_check, load_dataset
from apextrace.openf1 import download_session, drivers_of, lap_table, qualifying_sessions, session_feed_tables
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
REFERENCE_PIN = "results/24_dry_run_checks/summary.json"
# must be identical to the commit that added Part C (tracked files) ...
PINNED_PATHS = [THIS_SCRIPT, PACKAGE, REFERENCE_PIN, "results/final/dataset_2025.csv.gz",
                "results/final/corners_2025.csv"]
# ... and these must match the SHA-256 fingerprints in REFERENCE_PIN (the raw samples are not in git)
REFERENCE_FILES = ["results/final/dataset_2025.csv.gz", "results/final/raw_samples_2025.parquet",
                   "results/final/corners_2025.csv"]
FINAL_YEAR, REFERENCE_YEAR = 2026, 2025
SWITCH = "FINAL_TEST_2026"
# Fixed when Part C was written (2026-11-06), so the day the run happens can't change which sessions count
CUTOFF_UTC = datetime(2026, 11, 6, 0, 0)
CUTOFF_HOURS = 24          # the run starts at least this long after the cutoff (OpenF1 finishes its data)
DOWNLOAD_RETRIES = 2
RESULT_FILE_PREFIXES = ("h5_", "h4_", "team_changes")


# ---------------------------------------------------------------- guards

def guard_problems(switch_value, preregistration_text, preregistration_committed, preregistration_unchanged,
                   code_unchanged, code_same_as_part_c, reference_problems, now, out_dir):
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
        problems.append(f"{THIS_SCRIPT}, {PACKAGE}/ or a pinned file has uncommitted changes: commit the code that will run")
    if not code_same_as_part_c:
        problems.append("the code or a pinned file differs from the commit that added Part C")
    problems.extend(reference_problems)
    if now < CUTOFF_UTC + timedelta(hours=CUTOFF_HOURS):
        problems.append(f"too early: the run may start from {CUTOFF_UTC + timedelta(hours=CUTOFF_HOURS):%Y-%m-%d %H:%M} UTC")
    out_dir = Path(out_dir)
    finished = sorted(path.parent.name for path in out_dir.parent.glob(f"{out_dir.name}*/summary.json"))
    if finished:
        problems.append(f"{', '.join(finished)} has a summary.json: the 2026 test has already been run")
    elif out_dir.exists():
        result_files = [path.name for path in out_dir.iterdir() if path.name.startswith(RESULT_FILE_PREFIXES)]
        if result_files:
            problems.append(f"{out_dir.name}/ holds result files ({', '.join(sorted(result_files))}) from an attempt "
                            "that did not finish: it counts as a run (bug rule in Part C)")
        else:
            problems.append(f"{out_dir.name}/ exists from an attempt that stopped early: record it in "
                            f"docs/preregistration_deviations.md, rename it to {out_dir.name}_attempt_<n>, then run again")
    return problems


def git(*arguments):
    return subprocess.run(["git", *arguments], cwd=REPO_ROOT, capture_output=True, text=True)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def reference_file_problems():
    """The 2025 reference files must exist and match the fingerprints recorded with Part C."""
    pin_path = REPO_ROOT / REFERENCE_PIN
    if not pin_path.exists():
        return [f"{REFERENCE_PIN} is missing"]
    pinned = json.loads(pin_path.read_text(encoding="utf-8")).get("reference_files", {})
    problems = []
    for relative in REFERENCE_FILES:
        path = REPO_ROOT / relative
        if not path.exists():
            problems.append(f"{relative} is missing (rebuild it before the run)")
        elif pinned.get(relative) != sha256(path):
            problems.append(f"{relative} differs from its fingerprint in {REFERENCE_PIN}")
    return problems


def guards():
    text = (REPO_ROOT / PREREGISTRATION).read_text(encoding="utf-8")
    committed = git("log", "--format=%H %ci", "-1", "--", PREREGISTRATION).stdout.strip()
    part_c_commit = committed.split(" ")[0] if committed else ""
    preregistration_unchanged = git("diff", "--quiet", "HEAD", "--", PREREGISTRATION).returncode == 0
    code_unchanged = (git("diff", "--quiet", "HEAD", "--", *PINNED_PATHS).returncode == 0
                      and not git("ls-files", "--others", "--exclude-standard", PACKAGE).stdout.strip())
    code_same_as_part_c = bool(part_c_commit) and git("diff", "--quiet", part_c_commit, "HEAD", "--",
                                                      *PINNED_PATHS).returncode == 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    problems = guard_problems(os.environ.get(SWITCH), text, committed, preregistration_unchanged, code_unchanged,
                              code_same_as_part_c, reference_file_problems(), now, OUT_DIR)
    if problems:
        print("STOP:\n  - " + "\n  - ".join(problems))
        sys.exit(1)
    return committed, git("rev-parse", "HEAD").stdout.strip(), now


# ---------------------------------------------------------------- phases

def sessions_to_use(sessions, cutoff=CUTOFF_UTC):
    """Main qualifying sessions that ended before the fixed cutoff (UTC, naive).
    Example: cutoff 2026-11-06 00:00 -> a session that ended on 2026-11-05 at 15:00 is in,
    one that ended on 2026-11-07 is not, whenever the script is run."""
    return sessions[sessions["date_end"] <= cutoff].reset_index(drop=True)


def download_all(sessions, retries=DOWNLOAD_RETRIES, pause_s=60):
    """Phase 1: everything into the cache, before anything is analysed.

    A failed download is tried again `retries` more times (a network or rate-limit error is
    usually temporary). Returns the log; rows with a non-empty "error" still failed.
    """
    rows = {}
    for index, session in sessions.iterrows():
        rows[index] = {"round": index + 1, "location": session["location"],
                       "session_key": int(session["session_key"]), "error": "not tried", "attempts": 0}
    for attempt in range(retries + 1):
        pending = [index for index, row in rows.items() if row["error"]]
        if not pending:
            break
        if attempt:
            print(f"  retry {attempt} of {retries} for {len(pending)} sessions in {pause_s} s", flush=True)
            time.sleep(pause_s)
        for index in pending:
            session = sessions.loc[index]
            row = rows[index]
            row["attempts"] += 1
            try:
                row.update(download_session(row["session_key"], session["date_end"]))
                row["error"] = ""
            except Exception as error:
                row["error"] = f"{type(error).__name__}: {error}"
            print(f"  download R{row['round']:02d} {row['location']:20s} {row.get('kept_laps', '-')!s:>4} kept laps "
                  f"{row['error']}", flush=True)
    return pd.DataFrame(list(rows.values()))


def kept_lap_compounds(session):
    """The tyre-compound label of every kept lap of one session (from the cache)."""
    laps = lap_table(int(session["session_key"]), session["date_end"])
    compounds = []
    for driver in sorted(laps["Driver"].unique()) if len(laps) else []:
        kept, _ = select_laps(laps[laps["Driver"] == driver])
        compounds.extend(kept["Compound"].tolist())
    return compounds


def run_checks(sessions):
    """Phase 2, before any feature: the feed, the team names and the tyre-compound labels.
    Returns (ok, report)."""
    cars, positions, team_names, compounds = [], [], [], []
    for _, session in sessions.iterrows():
        session_cars, session_positions = session_feed_tables(int(session["session_key"]), session["date_end"])
        cars.extend(session_cars)
        positions.extend(session_positions)
        for _, team in drivers_of(int(session["session_key"])).values():
            team_names.append(team)
        compounds.extend(kept_lap_compounds(session))
    feed = feed_check(cars, positions)
    unknown = unknown_team_names(team_names)
    tyres = compound_check(compounds)
    known_names = sorted({str(name) for name in team_names if str(name) not in unknown})
    report = {"feed": feed, "team_names": known_names, "unknown_team_names": unknown,
              "compounds": tyres, "lap_tables_checked": len(cars)}
    return bool(feed["ok"] and not unknown and tyres["ok"]), report


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


def analyse(laps, reference_year, target_year, reference_corners, target_corners, leave_pair_out=True):
    """Phase 4, in memory: every result from h5_protocol. Returns (summary, files to write)."""
    tables, h5 = h5_protocol.h5_results(laps, reference_year, target_year)
    files = {f"h5_{name.replace(' ', '_')}.csv": table for name, table in tables.items()}
    changes, changers, stayers, h4 = h5_protocol.h4_results(laps, reference_year, target_year, leave_pair_out)
    files.update({"team_changes.csv": changes, "h4_changers.csv": changers, "h4_stayers.csv": stayers})
    corner_types = {str(reference_year): h5_protocol.corner_type_counts(reference_corners),
                    str(target_year): h5_protocol.corner_type_counts(target_corners)}
    return {"h5": h5, "h4": h4, "corner_types": corner_types}, files


def write_results(out_dir, summary, files):
    """Every result file first, summary.json last (its presence means "this run finished")."""
    for name, table in files.items():
        table.to_csv(out_dir / name, index=False, float_format="%.4f")
    with open(out_dir / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, default=str)


def save_build(out_dir, year, dataset, corners, summaries, raw):
    dataset.to_csv(out_dir / f"dataset_{year}.csv.gz", index=False, float_format="%.3f")
    corners.to_csv(out_dir / f"corners_{year}.csv", index=False, float_format="%.1f")
    summaries.to_csv(out_dir / f"sessions_{year}.csv", index=False)
    raw.to_parquet(out_dir / f"raw_samples_{year}.parquet", index=False)


def reference_season(year):
    """The reference season's lap table and corners, from the saved data."""
    if year == 2025:
        dataset = pd.read_csv(RESULTS / "final" / "dataset_2025.csv.gz")
        raw = pd.read_parquet(RESULTS / "final" / "raw_samples_2025.parquet")
        corners = pd.read_csv(RESULTS / "final" / "corners_2025.csv")
    else:
        development = load_dataset()
        dataset = development[development["year"] == year]
        raw = pd.read_parquet(RESULTS / "09_dataset" / "raw_samples.parquet")
        corners = pd.read_csv(RESULTS / "09_dataset" / "corners.csv")
        corners = corners[corners["year"] == year]
    laps, _ = h5_protocol.lap_table_from(dataset, raw)
    return laps, corners


def reference_lap_table(year):
    return reference_season(year)[0]


def report(summary):
    primary = summary["h5"]["sets"]["all"]
    print(f"\nH5 (primary): own past closer for {primary['own_closer']} of {primary['drivers']}, "
          f"sign test p = {primary['sign_test_p']} -> {summary['h5']['verdict']}")
    for name, result in summary["h5"]["sets"].items():
        print(f"   {name:17s} {result['own_closer']} of {result['drivers']}")
    h4 = summary["h4"]
    print(f"H4 (secondary): changers {h4['changer_names']}: {h4['changers']['own_closer']} of "
          f"{h4['changers']['drivers']}; stayers {h4['stayers']['own_closer']} of {h4['stayers']['drivers']}; "
          f"Fisher p = {h4['fisher_exact_two_sided_p']}")
    print("corner types:", {year: {k: v["corners"] for k, v in counts.items()}
                            for year, counts in summary["corner_types"].items()})


# ---------------------------------------------------------------- the real run and the dry runs

def real_run():
    preregistration_commit, code_commit, now = guards()
    OUT_DIR.mkdir(parents=True)
    sessions = sessions_to_use(qualifying_sessions(FINAL_YEAR))
    start = {"preregistration_commit": preregistration_commit, "code_commit": code_commit,
             "started_utc": now.isoformat(), "cutoff_utc": CUTOFF_UTC.isoformat(),
             "sessions": sessions[["session_key", "location", "date_end"]].astype(str).to_dict("records")}
    (OUT_DIR / "run_started.json").write_text(json.dumps(start, indent=2), encoding="utf-8")

    print(f"phase 1: download {len(sessions)} sessions (ended before {CUTOFF_UTC:%Y-%m-%d %H:%M} UTC)")
    downloads = download_all(sessions)
    downloads.to_csv(OUT_DIR / "download_log.csv", index=False)
    if downloads["error"].ne("").any():
        print("STOP: some downloads still failed after the retries (results/final_2026/download_log.csv). "
              "No result was produced; follow Part C (crash rule: log a deviation before anything else).")
        sys.exit(2)

    print("phase 2: checks before any feature")
    ok, checks = run_checks(sessions)
    (OUT_DIR / "checks.json").write_text(json.dumps(checks, indent=2, default=str), encoding="utf-8")
    if not ok:
        print("STOP: the feed, the team names or the tyre labels failed the checks (results/final_2026/checks.json). "
              "No result was produced; follow Part C (log a deviation before anything else).")
        sys.exit(2)

    print("phase 3: build")
    dataset, corners, summaries, raw = build_all(FINAL_YEAR, sessions)
    save_build(OUT_DIR, FINAL_YEAR, dataset, corners, summaries, raw)
    target, cleaning = h5_protocol.lap_table_from(dataset, raw)
    reference, reference_corners = reference_season(REFERENCE_YEAR)
    laps = pd.concat([reference, target], ignore_index=True)

    print("phase 4: analyse")
    summary, files = analyse(laps, REFERENCE_YEAR, FINAL_YEAR, reference_corners, corners)
    summary.update({**start, "cleaning": cleaning, "laps": int(len(target)), "checks_ok": ok})
    write_results(OUT_DIR, summary, files)
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
        print("phase 2: checks")
        ok, checks = run_checks(sessions)
        (out_dir / "checks.json").write_text(json.dumps(checks, indent=2, default=str), encoding="utf-8")
        print(f"  checks ok: {ok}; unknown team names: {checks['unknown_team_names']}; "
              f"compounds: {checks['compounds']}")
        print("phase 3: build")
        dataset, target_corners, summaries, raw = build_all(target_year, sessions)
        save_build(out_dir, target_year, dataset, target_corners, summaries, raw)
        target, _ = h5_protocol.lap_table_from(dataset, raw)
    elif target_year == 2025:
        print("analysis only: 2025 from the saved data in results/final/ (its download stays guarded)")
        target, target_corners = reference_season(2025)
    else:
        raise SystemExit("dry runs: 2024 or 2025")

    reference, reference_corners = reference_season(reference_year)
    laps = pd.concat([reference, target], ignore_index=True)
    summary, files = analyse(laps, reference_year, target_year, reference_corners, target_corners)
    if target_year == 2025:
        _, _, _, part_b = h5_protocol.h4_results(laps, reference_year, target_year, leave_pair_out=False)
        summary["h4_with_part_b_spread"] = part_b
    primary = summary["h5"]["sets"]["all"]
    summary["matches_experiment_20"] = (primary["own_closer"] == expected["all"]["own_closer"]
                                        and primary["drivers"] == expected["all"]["drivers"])
    write_results(out_dir, summary, files)
    report(summary)
    print(f"\nH5 equals experiment 20 ({expected['all']['own_closer']} of {expected['all']['drivers']}): "
          f"{summary['matches_experiment_20']}")
    if target_year == 2025:
        b = summary["h4_with_part_b_spread"]
        print(f"H4 with Part B's spread: changers {b['changers']['own_closer']} of {b['changers']['drivers']}, "
              f"stayers {b['stayers']['own_closer']} of {b['stayers']['drivers']}")
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

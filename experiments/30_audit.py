"""The full audit (Audit I on Day 17; run again on Days 22 and 28): is everything still what the
documents say it is? Nothing here changes a result; it checks.

  A. Fingerprint every output (all of results/, README.md, docs/report.md, docs/preregistration.md).
  B. Re-run every development experiment that can be re-run safely, with the network BLOCKED
     (a proxy that refuses every connection), so everything comes from the local cache.
  C. Fingerprint again: no output may have changed. Text files are compared with Windows/Unix
     line endings made equal and .gz files after decompressing (gzip stores a time stamp).
  D. The preregistered pilot tests (06, Part A), recomputed in memory (06 refuses to re-run).
  E. The frozen 2025 test (14, Part B), recomputed in memory from the saved 2025 data.
  F. The frozen 2026 test (23, Part C + Addendum 1), recomputed in memory from the saved data.
  G. Data counts that must agree across files (kept laps >= laps with data >= laps in the dataset).
  H. The 2026 timeline: no 2026 result committed before Part C, no 2026 lap table downloaded
     before the run.
  I. The whole test suite (it includes the checks of the hand-written documents).

Recomputations from SAVED data (E, F) can't match to the last digit: the one-time runs computed
from full-precision features and saved the datasets with 3 decimals. So decisions and counts
must match exactly and every number to within 0.01; the largest difference is reported.

Writes results/30_audit/audit_<date>.json and prints a summary. Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\30_audit.py            # everything (~30-60 minutes)
    .venv\\Scripts\\python.exe experiments\\30_audit.py --quick    # skip B and C (~5 minutes)
"""

import argparse
import gzip
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "results"
OUT_DIR = RESULTS / "30_audit"
PART_C_COMMIT = "f653d49"
NUMBER_TOLERANCE = 0.01
TEXT_SUFFIXES = {".json", ".csv", ".md", ".txt", ".log", ".html", ".svg", ".tsv"}
# Columns that can't be reproduced, compared separately and reported:
#   seconds - how long each session took to build (a stopwatch, different on every run);
#   note    - 2023 Imola (cancelled weekend, no laps): the committed build (2026-10-17) predates
#             the "session without laps" fix of 2026-10-18 and wrote "KeyError: 'driver_number'";
#             a rebuild today writes another note (and, offline, can't ask OpenF1 at all, because
#             a "no rows" answer is never cached). No data row depends on it.
VOLATILE_COLUMNS = {"results/09_dataset/sessions.csv": ["seconds", "note"]}
# Parts of JSON files that measure this computer, not the data, compared separately and reported:
#   check_9_cost - cache sizes and load times of the pilot (the cache has grown since).
VOLATILE_KEYS = {"results/01_data_pilot/summary.json": ["check_9_cost"]}
# A field of every record of a JSON list: the app's session list copies the session notes of
# 09's sessions.csv (so it carries the same 2023 Imola note).
VOLATILE_RECORD_FIELDS = {"results/app/sessions.json": "note"}

# B: re-run in this order (09 before 10-13; 17 last, because it reads every other result)
RERUN = ["00_hello_lap", "01_data_pilot", "02_group_delay_demo", "03_synthetic_errors", "04_alignment",
         "05_pilot_features", "07_openf1_validation", "09_build_dataset", "10_eda", "11_repeatability",
         "12_identification", "13_signature_stability", "15_final_exploratory", "16_app_data",
         "18_position_offset", "19_h5_power", "20_h5_development", "21_coasting_check", "22_h5_null_check",
         "24_dry_run_checks", "26_addendum_1_dry_run_check", "27_final_2026_figures", "28_lost_laps_2026",
         "29_teammate_relative", "17_write_docs"]
NOT_RERUN = {
    "06_pilot_stats": "records the latest preregistration commit at run time, so it refuses to re-run; "
                      "recomputed in memory (D)",
    "08_download_openf1": "downloads from OpenF1; its log is the record of the download",
    "14_final_2025": "the one-time 2025 test; refuses to run; recomputed in memory (E)",
    "23_final_2026": "the one-time 2026 test; refuses to run; recomputed in memory (F). Its dry runs are "
                     "evidence quoted by Part C, re-checked by 24",
    "25_feed_check_2026_diagnosis": "asks OpenF1 for the two 2026 sessions without laps, whose 'no rows' answers "
                                    "are never cached (a network request); its marker count must equal the run's "
                                    "removal count (asserted by 17_write_docs)",
    "30_audit": "this script",
}
EXTRA_ENVIRONMENT = {"15_final_exploratory": {"FINAL_TEST": "1"}}


def load_script(name):
    spec = importlib.util.spec_from_file_location(name.replace("_", ""), REPO_ROOT / "experiments" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(*arguments):
    return subprocess.run(["git", *arguments], cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8")


# ---------------------------------------------------------------- A, C: fingerprints

def fingerprint(path):
    """SHA-256 of a file's content, with .gz decompressed and text line endings made equal.

    Why: gzip writes the time of writing into its header, and on Windows a file written by Python
    can have CRLF where the committed one has LF; neither is a change of content.
    Example: "a,b\\r\\n1,2\\r\\n" and "a,b\\n1,2\\n" give the same fingerprint.
    """
    data = path.read_bytes()
    suffixes = path.suffixes
    if suffixes and suffixes[-1] == ".gz":
        data = gzip.decompress(data)
        suffixes = suffixes[:-1]
    if suffixes and suffixes[-1] in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def snapshot():
    files = {}
    for path in sorted(RESULTS.rglob("*")):
        if path.is_file() and OUT_DIR not in path.parents:
            name = path.relative_to(REPO_ROOT).as_posix()
            if name in VOLATILE_COLUMNS:
                table = pd.read_csv(path)
                files[name] = hashlib.sha256(table.drop(columns=VOLATILE_COLUMNS[name])
                                             .to_csv(index=False).encode("utf-8")).hexdigest()
                files[name + " [volatile columns]"] = table[["session_key"] + VOLATILE_COLUMNS[name]].to_dict("records")
                continue
            if name in VOLATILE_KEYS:
                content = json.loads(path.read_text(encoding="utf-8"))
                for key in VOLATILE_KEYS[name]:
                    content.pop(key, None)
                files[name] = hashlib.sha256(json.dumps(content, sort_keys=True).encode("utf-8")).hexdigest()
                continue
            if name in VOLATILE_RECORD_FIELDS:
                field = VOLATILE_RECORD_FIELDS[name]
                records = json.loads(path.read_text(encoding="utf-8"))
                stripped = [{k: v for k, v in record.items() if k != field} for record in records]
                files[name] = hashlib.sha256(json.dumps(stripped, sort_keys=True).encode("utf-8")).hexdigest()
                continue
            files[name] = fingerprint(path)
    for name in ("README.md", "docs/report.md", "docs/preregistration.md"):
        files[name] = fingerprint(REPO_ROOT / name)
    return files


def compare_snapshots(before, after):
    """Changed, new and removed files. The volatile columns are listed, not judged: for each
    session whose note differs, both notes are shown."""
    volatile = [name for name in before if name.endswith(" [volatile columns]")]
    changed = sorted(name for name in before if name in after and name not in volatile and before[name] != after[name])
    new = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    notes = []
    for name in volatile:
        old = {row["session_key"]: row for row in before[name]}
        for row in after.get(name, []):
            previous = old.get(row["session_key"], {})
            if str(previous.get("note")) != str(row.get("note")):
                notes.append({"session_key": row["session_key"], "note_before": previous.get("note"),
                              "note_now": row.get("note")})
    return {"ok": not (changed or new or removed), "files": len(before) - len(volatile), "changed": changed,
            "new": new, "removed": removed, "volatile_note_differences": notes}


def keep_original_bytes():
    """The exact bytes of the files whose bytes can differ while their content doesn't: .gz files
    (time stamp in the header) and the files with volatile parts."""
    originals = {}
    names = set(VOLATILE_COLUMNS) | set(VOLATILE_KEYS) | set(VOLATILE_RECORD_FIELDS)
    for path in RESULTS.rglob("*"):
        name = path.relative_to(REPO_ROOT).as_posix()
        if path.is_file() and OUT_DIR not in path.parents and (path.suffix == ".gz" or name in names):
            originals[name] = path.read_bytes()
    return originals


def restore_unchanged(originals, outputs):
    """Put back the original bytes of every kept file whose content did NOT change, so the audit
    leaves the working tree as it found it. A file that really changed is left as the re-run
    wrote it, to be looked at. Returns the restored names."""
    really_changed = set(outputs["changed"]) | set(outputs["new"]) | set(outputs["removed"])
    restored = []
    for name, data in sorted(originals.items()):
        path = REPO_ROOT / name
        if name in really_changed or not path.exists():
            continue
        if path.read_bytes() != data:
            path.write_bytes(data)
            restored.append(name)
    return restored


# ---------------------------------------------------------------- B: re-run

def offline_environment():
    """The current environment, with every HTTP(S) request sent to a proxy that doesn't exist
    (port 9 on this computer refuses connections), so a missing cache file fails loudly."""
    environment = dict(os.environ)
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        environment[name] = "http://127.0.0.1:9"
    environment["NO_PROXY"] = environment["no_proxy"] = ""
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["MPLBACKEND"] = "Agg"
    return environment


def rerun_experiments():
    runs = []
    for name in RERUN:
        environment = offline_environment()
        environment.update(EXTRA_ENVIRONMENT.get(name, {}))
        started = time.time()
        result = subprocess.run([sys.executable, str(REPO_ROOT / "experiments" / f"{name}.py")], cwd=REPO_ROOT,
                                env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=3600)
        seconds = round(time.time() - started, 1)
        tail = (result.stdout + result.stderr).strip().splitlines()[-6:]
        runs.append({"experiment": name, "exit_code": result.returncode, "seconds": seconds, "last_lines": tail})
        print(f"  {name:32s} exit {result.returncode}  {seconds:7.1f} s", flush=True)
    return {"ok": all(run["exit_code"] == 0 for run in runs), "runs": runs, "not_rerun": NOT_RERUN}


# ---------------------------------------------------------------- comparing frozen and recomputed numbers

def compare(frozen, now, tolerance, path="", report=None):
    """Walk two nested results (dicts/lists/numbers/text). Integers, booleans and text must be
    equal; floats within `tolerance`. Returns {"differences": [...], "largest": float}.
    Example: compare({"wins": 8, "mean": 0.662}, {"wins": 8, "mean": 0.664}, 0.01) -> no
    difference, largest 0.002."""
    if report is None:
        report = {"differences": [], "largest": 0.0}
    if isinstance(frozen, dict) and isinstance(now, dict):
        for key in frozen:
            if key not in now:
                report["differences"].append(f"{path}/{key}: missing now")
                continue
            compare(frozen[key], now[key], tolerance, f"{path}/{key}", report)
    elif isinstance(frozen, (list, tuple)) and isinstance(now, (list, tuple)):
        if len(frozen) != len(now):
            report["differences"].append(f"{path}: {len(frozen)} items frozen, {len(now)} now")
        for index, (a, b) in enumerate(zip(frozen, now)):
            compare(a, b, tolerance, f"{path}[{index}]", report)
    elif isinstance(frozen, bool) or isinstance(now, bool) or isinstance(frozen, str) or frozen is None:
        if frozen != now:
            report["differences"].append(f"{path}: {frozen!r} frozen, {now!r} now")
    elif isinstance(frozen, int) and isinstance(now, int):
        if frozen != now:
            report["differences"].append(f"{path}: {frozen} frozen, {now} now")
    else:
        a, b = float(frozen), float(now)
        if math.isnan(a) and math.isnan(b):
            return report
        gap = abs(a - b)
        report["largest"] = max(report["largest"], gap)
        if not gap <= tolerance:
            report["differences"].append(f"{path}: {a} frozen, {b} now")
    return report


def as_plain(value):
    """numpy/pandas numbers -> plain Python, so the comparison sees ints as ints."""
    return json.loads(json.dumps(value, default=lambda x: x.item() if hasattr(x, "item") else str(x)))


def table_gaps(frozen, now, key, columns, exact):
    """Largest difference per numeric column between a frozen per-driver table and a recomputed one,
    and the rows whose exact columns (answers) differ."""
    merged = frozen.merge(now, on=key, suffixes=("_frozen", "_now"))
    gaps = {}
    for column in columns:
        gaps[column] = float((merged[f"{column}_frozen"] - merged[f"{column}_now"]).abs().max())
    disagreements = []
    for column in exact:
        different = merged[merged[f"{column}_frozen"] != merged[f"{column}_now"]]
        disagreements.extend(f"{row[key]}: {column}" for _, row in different.iterrows())
    rows_match = len(merged) == len(frozen) == len(now)
    return {"rows_match": rows_match, "largest": gaps, "answers_differ": disagreements}


# ---------------------------------------------------------------- D: pilot tests (Part A)

def recompute_pilot():
    script = load_script("06_pilot_stats")
    features = pd.read_csv(script.FEATURES_CSV)
    summary = pd.read_csv(script.DRIVER_SUMMARY_CSV)
    errors = {}
    for _, row in summary.drop_duplicates(["corner", "feature"]).iterrows():
        errors[(row["corner"], row["feature"])] = row["measurement_error_per_lap"]
    frozen = json.loads((RESULTS / "06_pilot_stats" / "summary.json").read_text(encoding="utf-8"))
    h2 = script.h2_tests(features, errors)
    h1 = script.h1_repeatability(features, errors)
    now = {"discoveries": int(h2["discovery"].sum()), "h2": as_plain(h2.to_dict(orient="records")),
           "h1": as_plain(h1.to_dict(orient="records"))}
    report = compare({k: frozen[k] for k in now}, now, 1e-9)
    return {"ok": not report["differences"], "differences": report["differences"][:20],
            "largest": report["largest"], "discoveries": now["discoveries"]}


# ---------------------------------------------------------------- E: the 2025 test (Part B)

def recompute_2025():
    import numpy as np

    script = load_script("14_final_2025")
    dataset = pd.read_csv(RESULTS / "final" / "dataset_2025.csv.gz")
    raw = pd.read_parquet(RESULTS / "final" / "raw_samples_2025.parquet")
    laps_2025, laps_2024, cleaning = script.lap_tables(dataset, raw)
    rng = np.random.default_rng(script.SEED)
    teammates = script.teammate_task(laps_2025, rng, shuffles=script.SHUFFLES)
    h3 = script.summarise_teammates(teammates, rng)
    h4_table, h4_summary = script.h4(laps_2025, laps_2024)
    control_table, control_summary = script.non_changer_check(laps_2025, laps_2024)
    primary = h3["ours minus lap time only"]
    now = as_plain({"cleaning_2025": cleaning, "laps_2025": int(len(laps_2025)), "h3": h3, "h4": h4_summary,
                    "non_changer_check": control_summary,
                    "h3_supported": bool(primary["wilcoxon_p"] < 0.05 and primary["mean_difference"] > 0),
                    "h4_supported": bool(h4_summary["sign_test_p"] is not None and h4_summary["sign_test_p"] < 0.05)})
    frozen = json.loads((RESULTS / "final" / "summary.json").read_text(encoding="utf-8"))
    frozen.pop("preregistration_commit")
    report = compare(frozen, now, NUMBER_TOLERANCE)
    changers = table_gaps(pd.read_csv(RESULTS / "final" / "h4_changers.csv"), h4_table[h4_table["included"]],
                          "driver", ["distance_own_2024", "distance_new_teammate_2025"], ["own_closer"])
    teams = table_gaps(pd.read_csv(RESULTS / "final" / "h3_teammates_2025.csv"), teammates, "team_season",
                       ["our features | balanced_accuracy", "lap time only | balanced_accuracy",
                        "raw lap statistics | balanced_accuracy"], [])
    ok = (not report["differences"] and changers["rows_match"] and not changers["answers_differ"]
          and max(changers["largest"].values()) <= NUMBER_TOLERANCE and teams["rows_match"])
    return {"ok": bool(ok), "differences": report["differences"][:20], "largest_summary_difference": report["largest"],
            "h4_changers": changers, "h3_per_team": teams,
            "decisions": {"h3_supported": now["h3_supported"], "h4_supported": now["h4_supported"]}}


# ---------------------------------------------------------------- F: the 2026 test (Part C)

def recompute_2026():
    script = load_script("23_final_2026")
    from apextrace import h5_protocol

    dataset = pd.read_csv(RESULTS / "final_2026" / "dataset_2026.csv.gz")
    raw = pd.read_parquet(RESULTS / "final_2026" / "raw_samples_2026.parquet")
    target, cleaning = h5_protocol.lap_table_from(dataset, raw)
    reference, reference_corners = script.reference_season(2025)
    corners = pd.read_csv(RESULTS / "final_2026" / "corners_2026.csv")
    summary, files = script.analyse(pd.concat([reference, target], ignore_index=True), 2025, 2026,
                                    reference_corners, corners)
    now = as_plain({**summary, "cleaning": cleaning, "laps": int(len(target))})
    frozen = json.loads((RESULTS / "final_2026" / "summary.json").read_text(encoding="utf-8"))
    report = compare({key: frozen[key] for key in now}, now, NUMBER_TOLERANCE)
    tables = {}
    for name in ("h5_all.csv", "h5_control_points.csv", "h5_energy-sensitive.csv", "h5_no_throttle.csv"):
        tables[name] = table_gaps(pd.read_csv(RESULTS / "final_2026" / name), files[name], "driver",
                                  ["distance_own", "distance_teammate"], ["own_closer"])
    for name in ("h4_changers.csv", "h4_stayers.csv"):
        tables[name] = table_gaps(pd.read_csv(RESULTS / "final_2026" / name), files[name], "driver",
                                  ["distance_own_reference", "distance_new_teammate"], ["own_closer"])
    ok = not report["differences"]
    for table in tables.values():
        ok = ok and table["rows_match"] and not table["answers_differ"]
        ok = ok and max(table["largest"].values()) <= NUMBER_TOLERANCE
    return {"ok": bool(ok), "differences": report["differences"][:20], "largest_summary_difference": report["largest"],
            "tables": tables, "verdict": now["h5"]["verdict"]}


# ---------------------------------------------------------------- G: counts across files

def check_counts():
    from apextrace.dataset import clean, load_dataset

    """Lap counts, one definition each, must agree between files and shrink step by step:
    kept (lap-selection rules) = laps with dataset rows (every kept lap gets rows, with a reason
    when it can't be measured) >= laps with car data >= laps with a usable corner pass (data, no
    feed gap) >= laps with a clean corner pass (also dry, plausible). Re-cleaning each saved
    dataset must also give the cleaning counts its summary reports."""
    problems, facts = [], {}

    def laps_in(table):
        return int(table.groupby(["session_key", "driver", "lap"]).ngroups)

    def describe(kept, with_data, dataset):
        rows, cleaning = clean(dataset)
        return {"kept": kept, "with_dataset_rows": laps_in(dataset), "with_car_data": with_data,
                "with_a_usable_corner": laps_in(dataset[dataset["usable"]]), "with_a_clean_corner": laps_in(rows),
                "rows": int(len(dataset))}, cleaning

    log = pd.read_csv(RESULTS / "08_download" / "download_log.csv")
    development = load_dataset()
    facts["2023-2024"], cleaning = describe(int(log["kept_laps"].sum()), int(log["kept_laps_with_data"].sum()),
                                            development)
    built = json.loads((RESULTS / "09_dataset" / "summary.json").read_text(encoding="utf-8"))
    if built["laps"] != facts["2023-2024"]["with_a_usable_corner"] or built["rows"] != len(development):
        problems.append("09_dataset/summary.json disagrees with dataset.csv.gz")
    if as_plain(cleaning) != json.loads((RESULTS / "10_eda" / "summary.json").read_text(encoding="utf-8"))["cleaning"]:
        problems.append("cleaning the development dataset again gives other counts than 10_eda/summary.json")

    for year, folder, cleaning_key in ((2025, "final", "cleaning_2025"), (2026, "final_2026", "cleaning")):
        sessions = pd.read_csv(RESULTS / folder / f"sessions_{year}.csv")
        frozen = json.loads((RESULTS / folder / "summary.json").read_text(encoding="utf-8"))
        with_data_column = "download_kept_laps_with_data" if year == 2025 else "kept_laps_with_data"
        source = sessions if year == 2025 else pd.read_csv(RESULTS / folder / "download_log.csv")
        with_data = int(source[with_data_column].sum())
        facts[str(year)], cleaning = describe(int(sessions["kept_laps"].sum()), with_data,
                                              pd.read_csv(RESULTS / folder / f"dataset_{year}.csv.gz"))
        if as_plain(cleaning) != frozen[cleaning_key]:
            problems.append(f"cleaning the saved {year} dataset again gives other counts than its summary.json")
        lap_table = frozen["laps_2025"] if year == 2025 else frozen["laps"]
        if facts[str(year)]["with_a_clean_corner"] != lap_table:
            problems.append(f"{year}: laps with a clean corner differ from the lap table in summary.json")

    for period, counts in facts.items():
        if counts["kept"] != counts["with_dataset_rows"]:
            problems.append(f"{period}: {counts['kept']} kept laps but {counts['with_dataset_rows']} with dataset rows")
        chain = [counts["kept"], counts["with_car_data"], counts["with_a_usable_corner"], counts["with_a_clean_corner"]]
        if not chain[0] >= chain[1] >= chain[2] >= chain[3]:
            problems.append(f"{period}: kept >= car data >= usable corner >= clean corner does not hold: {chain}")
    return {"ok": not problems, "problems": problems, "laps": facts}


# ---------------------------------------------------------------- H: the 2026 timeline

def check_2026_timeline():
    """1. Every committed 2026 result was ADDED in a commit that comes after Part C (f653d49).
    2. Every 2026 lap table in the cache was written after attempt 1 started (the first
       moment 2026 data could be downloaded). A lap table is the first request for a session
       and car data is asked for over its laps, so no 2026 car data can be older."""
    problems = []
    prefixes = ("results/final_2026/", "results/final_2026_attempt_1/", "results/25_", "results/26_",
                "results/27_", "results/28_", "results/29_")
    tracked = [name for name in git("ls-files").stdout.splitlines() if name.startswith(prefixes)]
    checked = 0
    for name in tracked:
        added = git("log", "--diff-filter=A", "--format=%H", "--", name).stdout.split()
        for commit in added:
            checked += 1
            if git("merge-base", "--is-ancestor", PART_C_COMMIT, commit).returncode != 0:
                problems.append(f"{name} was added in {commit[:7]}, which does not come after Part C")

    started = json.loads((RESULTS / "final_2026_attempt_1" / "run_started.json").read_text(encoding="utf-8"))
    first_moment = datetime.fromisoformat(started["started_utc"]).replace(tzinfo=timezone.utc)
    oldest = None
    tables_2026 = 0
    for path in (REPO_ROOT / "cache" / "openf1" / "laps").glob("*.json*"):
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as file:
            rows = json.load(file)
        # the first lap of a session can have no start time, so look for any lap that has one
        starts = [str(row.get("date_start")) for row in rows if row.get("date_start")]
        if not starts or not starts[0].startswith("2026"):
            continue
        tables_2026 += 1
        written = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        oldest = written if oldest is None or written < oldest else oldest
        if written < first_moment:
            problems.append(f"{path.name}: a 2026 lap table written {written:%Y-%m-%d %H:%M} UTC, before the run")
    return {"ok": not problems, "problems": problems, "committed_2026_files_checked": checked,
            "lap_tables_2026_in_cache": tables_2026,
            "oldest_2026_lap_table_utc": oldest.isoformat() if oldest else None,
            "first_allowed_utc": first_moment.isoformat()}


# ---------------------------------------------------------------- I: the tests

def run_tests():
    result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=REPO_ROOT, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", env=offline_environment())
    last = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    return {"ok": result.returncode == 0, "summary": last}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="skip re-running the experiments (B, C)")
    quick = parser.parse_args().quick
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {"date": date.today().isoformat(), "quick": quick,
              "commit": git("rev-parse", "--short", "HEAD").stdout.strip(),
              "uncommitted_files": git("status", "--porcelain").stdout.splitlines()}
    steps = []
    if not quick:
        steps += [("A+B+C re-run, no output may change", None)]
    steps += [("D pilot tests (Part A) recomputed", recompute_pilot),
              ("E 2025 test (Part B) recomputed", recompute_2025),
              ("F 2026 test (Part C) recomputed", recompute_2026),
              ("G counts across files", check_counts),
              ("H 2026 timeline", check_2026_timeline),
              ("I test suite", run_tests)]
    for title, step in steps:
        print(f"\n{title}", flush=True)
        started = time.time()
        if step is None:
            before = snapshot()
            originals = keep_original_bytes()
            reruns = rerun_experiments()
            after = snapshot()
            outputs = compare_snapshots(before, after)
            outputs["restored_original_bytes"] = restore_unchanged(originals, outputs)
            # keep both fingerprints of every changed file, so a difference can be traced later
            outputs["fingerprints"] = {name: {"before": before.get(name), "after": after.get(name)}
                                       for name in outputs["changed"] + outputs["new"] + outputs["removed"]}
            result = {"ok": reruns["ok"] and outputs["ok"], "reruns": reruns, "outputs": outputs}
        else:
            try:
                result = step()
            except Exception as error:          # a crash is a failed check, reported like the others
                result = {"ok": False, "error": f"{type(error).__name__}: {error}"}
        result["seconds"] = round(time.time() - started, 1)
        report[title] = result
        shown = {k: v for k, v in result.items() if k not in ("reruns", "tables", "h3_per_team", "h4_changers")}
        print(f"  -> {'OK' if result['ok'] else 'PROBLEM'}  {json.dumps(shown, default=str)[:600]}", flush=True)
    report["all_ok"] = all(report[title]["ok"] for title, _ in steps)
    out = OUT_DIR / f"audit_{report['date']}{'_quick' if quick else ''}.json"
    out.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    print(f"\nall checks ok: {report['all_ok']}  (written to {out.relative_to(REPO_ROOT)})")


if __name__ == "__main__":
    main()

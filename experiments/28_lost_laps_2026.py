"""Day 16, EXPLORATORY (E1 in docs/decisions.md, 2026-11-09): which 2026 laps did the marker
removal cost, whose were they, and does it matter? Written after the frozen 2026 test; nothing
here can change its verdict.

Addendum 1 treats the feed's "no value" marker 104 as a missing sample: it is removed before
anything else (openf1.drop_no_value_samples, inside openf1.slice_lap). A lap whose car data is
then too thin is dropped: slice_lap needs at least 10 car samples, with samples on both sides of
the lap's start and end. The two frozen download logs show 30 such laps (attempt 1 counted
laps with data WITHOUT the rule, attempt 2 WITH it).

  1. Every kept 2026 lap goes through slice_lap twice, with and without the rule, on the CACHED
     streams. Lost = data without the rule, none with it. The per-session counts must equal both
     frozen download logs, or the script stops.
  2. Per driver and session: laps kept and lost; any whole weekend lost?
  3. The share of usable corner passes per session (frozen sessions_2026.csv): did the
     marker-heavy sessions also lose corner passes, to the gaps the removed samples leave?
  4. One sensitivity check, fixed before running: H5 recomputed from the frozen 2026 data with
     Shanghai and Suzuka (about 8 % markers) left out. First the full data must reproduce the
     frozen result (the same 19 drivers and answers; distances within 0.001, because the saved
     dataset has 3 decimals while the run used full precision).

Reads only the local cache and results/ (no request is sent: the network call is replaced by
one that raises). 2026 data needs its switch, set here for reading only; the one-time script
23_final_2026.py refuses to run whatever the switch says.
Run from the repo root (~1 minute):
    .venv\\Scripts\\python.exe experiments\\28_lost_laps_2026.py
"""

import importlib.util
import json
import os
from pathlib import Path

import pandas as pd

from apextrace import h5_protocol, openf1
from apextrace.data_loading import select_laps

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "results"
FINAL_DIR = RESULTS / "final_2026"
OUT_DIR = RESULTS / "28_lost_laps_2026"
MARKER_HEAVY = ["Shanghai", "Suzuka"]            # fixed in docs/decisions.md before running
PAD_S = 2.0                                       # slice_lap's default padding


def no_network(*args, **kwargs):
    raise RuntimeError("experiment 28 reads only the cache: a request would have been sent")


def keep_everything(car):
    return car


def has_data(streams, start, end, rule):
    """slice_lap with or without Addendum 1's rule (the rule is switched off by replacing the
    function slice_lap calls, so slice_lap itself is the code that decides)."""
    original = openf1.drop_no_value_samples
    if not rule:
        openf1.drop_no_value_samples = keep_everything
    try:
        return openf1.slice_lap(streams, start, end) is not None
    finally:
        openf1.drop_no_value_samples = original


def why_lost(streams, start, end):
    """Which of slice_lap's two conditions failed once the markers were removed, and how many
    car samples and markers the padded lap had."""
    pad = pd.Timedelta(PAD_S, unit="s")
    car = streams["car"][(streams["car"]["date"] >= start - pad) & (streams["car"]["date"] <= end + pad)]
    kept = openf1.drop_no_value_samples(car)
    if len(kept) < 10:
        reason = "fewer than 10 car samples"
    else:
        reason = "start or end not bracketed by samples"
    return {"reason": reason, "car_samples": len(car), "marker_samples": len(car) - len(kept)}


def lap_rows(sessions):
    # sessions with no laps (Sakhir, Jeddah): OpenF1 answered "no rows" (404), which is not
    # cached, so asking again would send a request; the frozen log already records 0 laps
    log = pd.read_csv(FINAL_DIR / "download_log.csv").set_index("session_key")
    rows = []
    for session in sessions:
        session_key, end = int(session["session_key"]), pd.Timestamp(session["date_end"])
        if log.loc[session_key, "laps"] == 0:
            continue
        laps = openf1.lap_table(session_key, end)
        for driver in sorted(laps["Driver"].unique()) if len(laps) else []:
            kept, _ = select_laps(laps[laps["Driver"] == driver])
            if kept.empty:
                continue
            span_start, span_end = openf1.kept_laps_span(kept)
            streams = openf1.driver_streams(session_key, int(kept["DriverNumber"].iloc[0]), span_start, span_end)
            for _, lap in kept.iterrows():
                start, finish = lap["LapStartDate"], lap["LapStartDate"] + lap["LapTime"]
                without = streams is not None and has_data(streams, start, finish, rule=False)
                with_rule = streams is not None and has_data(streams, start, finish, rule=True)
                row = {"session_key": session_key, "location": session["location"], "driver": driver,
                       "lap": int(lap["LapNumber"]), "data_without_rule": without, "data_with_rule": with_rule,
                       "lost": without and not with_rule}
                if row["lost"]:
                    row.update(why_lost(streams, start, finish))
                rows.append(row)
    return pd.DataFrame(rows)


def check_against_logs(table):
    """Per session, laps with data without / with the rule must equal attempt 1 / attempt 2's logs."""
    log_1 = pd.read_csv(RESULTS / "final_2026_attempt_1" / "download_log.csv").set_index("session_key")
    log_2 = pd.read_csv(FINAL_DIR / "download_log.csv").set_index("session_key")
    counts = table.groupby("session_key")[["data_without_rule", "data_with_rule"]].sum()
    problems = []
    for session_key in log_2.index:
        without = int(counts["data_without_rule"].get(session_key, 0))
        with_rule = int(counts["data_with_rule"].get(session_key, 0))
        if without != int(log_1.loc[session_key, "kept_laps_with_data"]):
            problems.append(f"{session_key}: {without} laps with data without the rule, attempt 1 logged "
                            f"{log_1.loc[session_key, 'kept_laps_with_data']}")
        if with_rule != int(log_2.loc[session_key, "kept_laps_with_data"]):
            problems.append(f"{session_key}: {with_rule} laps with data with the rule, attempt 2 logged "
                            f"{log_2.loc[session_key, 'kept_laps_with_data']}")
    return problems


def h5_recomputed(leave_out=()):
    """H5 primary from the FROZEN 2026 data (dataset + raw samples), exactly as the run built it,
    optionally without some 2026 sessions. Returns the per-driver table."""
    spec = importlib.util.spec_from_file_location("final_2026", REPO_ROOT / "experiments" / "23_final_2026.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    dataset = pd.read_csv(FINAL_DIR / "dataset_2026.csv.gz")
    raw = pd.read_parquet(FINAL_DIR / "raw_samples_2026.parquet")
    target, _ = h5_protocol.lap_table_from(dataset, raw)
    sessions = pd.read_csv(FINAL_DIR / "sessions_2026.csv")
    dropped = set(sessions.loc[sessions["location"].isin(leave_out), "session_key"])
    target = target[~target["session_key"].isin(dropped)]
    reference = script.reference_lap_table(2025)
    tables, _ = h5_protocol.h5_results(pd.concat([reference, target], ignore_index=True), 2025, 2026)
    return tables["all"]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["FINAL_TEST_2026"] = "1"                      # reading the cache only (see above)
    openf1.requests.get = no_network
    start = json.loads((FINAL_DIR / "run_started.json").read_text(encoding="utf-8"))

    # 1. every kept lap, with and without the rule
    table = lap_rows(start["sessions"])
    problems = check_against_logs(table)
    assert not problems, problems
    lost = table[table["lost"]]
    lost.to_csv(OUT_DIR / "lost_laps.csv", index=False)
    print(f"{len(table)} kept laps, {int(table['data_without_rule'].sum())} with data without the rule, "
          f"{int(table['data_with_rule'].sum())} with it: {len(lost)} lost (matches both download logs)")

    # 2. per driver and session
    per_driver = table.groupby(["location", "driver"]).agg(kept=("lap", "size"),
                                                           with_data=("data_with_rule", "sum"),
                                                           lost=("lost", "sum")).reset_index()
    affected = per_driver[per_driver["lost"] > 0].sort_values(["location", "lost"], ascending=[True, False])
    affected.to_csv(OUT_DIR / "per_driver.csv", index=False)
    print(affected.to_string(index=False))
    whole_weekends = affected[(affected["with_data"] == 0)]

    # 3. usable corner passes per session (frozen build)
    sessions = pd.read_csv(FINAL_DIR / "sessions_2026.csv")
    sessions = sessions[sessions["pairs"] > 0].copy()
    sessions["usable_share"] = sessions["usable_pairs"] / sessions["pairs"]
    usable = sessions[["location", "pairs", "usable_pairs", "usable_share"]].sort_values("usable_share")
    usable.to_csv(OUT_DIR / "usable_share.csv", index=False, float_format="%.3f")
    print(usable.to_string(index=False))
    others = sessions[~sessions["location"].isin(MARKER_HEAVY)]
    marker_sessions = sessions[sessions["location"].isin(MARKER_HEAVY)]

    # 4. the sensitivity check: first reproduce the frozen result, then leave out the two sessions
    frozen = pd.read_csv(FINAL_DIR / "h5_all.csv")
    full = h5_recomputed()
    # The run computed from full-precision features but SAVED the dataset with 3 decimals
    # (save_build, float_format "%.3f"), so distances recomputed from the saved file differ in
    # the 4th decimal. The test: the same drivers, the same answers, distances within 0.001.
    merged = frozen.merge(full, on="driver", suffixes=("_frozen", "_now"))
    largest = max((merged["distance_own_frozen"] - merged["distance_own_now"]).abs().max(),
                  (merged["distance_teammate_frozen"] - merged["distance_teammate_now"]).abs().max())
    reproduced = (len(merged) == len(frozen) == len(full)
                  and (merged["own_closer_frozen"] == merged["own_closer_now"]).all() and largest < 1e-3)
    assert reproduced, "the frozen H5 table could not be reproduced from the saved data"
    without = h5_recomputed(leave_out=MARKER_HEAVY)
    without = without[without["included"]]
    changed = full.merge(without, on="driver", suffixes=("_all", "_without"))
    flipped = changed[changed["own_closer_all"] != changed["own_closer_without"]]
    print(f"H5 recomputed: {int(full['own_closer'].sum())} of {len(full)} (reproduces the frozen table); "
          f"without {' and '.join(MARKER_HEAVY)}: {int(without['own_closer'].sum())} of {len(without)}")

    summary = {
        "note": "EXPLORATORY (docs/decisions.md 2026-11-09, E1); cannot change the frozen 2026 verdict",
        "kept_laps": int(len(table)),
        "with_data_without_rule": int(table["data_without_rule"].sum()),
        "with_data_with_rule": int(table["data_with_rule"].sum()),
        "lost": int(len(lost)),
        "matches_download_logs": True,
        "lost_by_session": {k: int(v) for k, v in lost.groupby("location").size().sort_values(ascending=False).items()},
        "lost_by_reason": {k: int(v) for k, v in lost["reason"].value_counts().items()},
        "drivers_affected": int(affected["driver"].nunique()),
        "largest_loss": affected.sort_values("lost", ascending=False).head(5).to_dict("records"),
        "whole_weekends_lost": whole_weekends[["location", "driver", "kept"]].to_dict("records"),
        "usable_share": {"marker_heavy": {r.location: round(r.usable_share, 3) for r in marker_sessions.itertuples()},
                         "other_sessions_median": round(float(others["usable_share"].median()), 3),
                         "other_sessions_min": round(float(others["usable_share"].min()), 3),
                         "other_sessions_max": round(float(others["usable_share"].max()), 3)},
        "h5_sensitivity": {"reproduced_frozen_table": bool(reproduced),
                           "largest_distance_difference_vs_frozen": round(float(largest), 6),
                           "all_sessions": {"own_closer": int(full["own_closer"].sum()), "drivers": int(len(full))},
                           "without_marker_heavy": {"left_out": MARKER_HEAVY,
                                                    "own_closer": int(without["own_closer"].sum()),
                                                    "drivers": int(len(without))},
                           "drivers_whose_answer_changed": [
                               {"driver": r.driver, "all_sessions": bool(r.own_closer_all),
                                "without": bool(r.own_closer_without)} for r in flipped.itertuples()]},
    }
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, default=int)
    print(json.dumps({k: summary[k] for k in ("lost_by_session", "lost_by_reason", "whole_weekends_lost",
                                              "usable_share", "h5_sensitivity")}, indent=1, default=int))


if __name__ == "__main__":
    main()

"""Phase 8: export the small data files the web app shows (results/app/).

The app never computes research results itself: every number it shows comes
from a results file written by an experiment script, and this script gathers
them into three small JSON files (committed, unlike the raw-sample Parquet):

  sessions.json  every qualifying session 2023-2025: event names, drivers with
                 team colours, kept laps, detected corners, and a track outline
                 (the reference lap's X/Y, rotated to lie landscape)
  hero.json      two laps for the animated track on the home page
                 (2024 Abu Dhabi qualifying, Norris vs Piastri: the pilot)
  headline.json  the hypothesis results (H1-H4) with the file each number came from
  features.json  the 10 corner features: meaning, unit, per-lap measurement error
                 (Phase 2) and repeatability (H1 ICC) per corner type
  identification.json  per team-season teammate identification (H3), 2023-2025
  signatures.json      the H4 season signatures (z-scores, 30 features) for every
                 driver in both 2024 and 2025, built with the exact H4 steps and
                 CHECKED to reproduce the frozen H4 distances
  method.json    the measurement science for the Method page: the sampling histogram,
                 one synthetic braking event through each filter (02_group_delay_demo's
                 own functions), every estimator's Monte Carlo error, the alignment of the
                 hero lap, and what each cleaning step removed

Team colours come from the OpenF1 driver list (cached, no download).
Driver head-shot URLs in that list are deliberately NOT exported (no photos).

Run from the repo root (reads only local files):
    .venv\\Scripts\\python.exe experiments\\16_app_data.py
"""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from apextrace.identification import ALL_FEATURES, CORNER_TYPES, FEATURE_GROUPS
from apextrace.openf1 import fetch
from apextrace.signatures import distance, season_signatures, standardise

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "results" / "app"
RESULTS = REPO_ROOT / "results"
RAW = {2023: RESULTS / "09_dataset" / "raw_samples.parquet",
       2024: RESULTS / "09_dataset" / "raw_samples.parquet",
       2025: RESULTS / "final" / "raw_samples_2025.parquet"}
HERO = {"year": 2024, "location": "Yas Island", "drivers": ["NOR", "PIA"]}


# ---------------------------------------------------------------- helpers

def landscape_rotation(x, y):
    """Angle (degrees) that turns a track outline so its long side is horizontal.

    WHY: track X/Y come in the timing system's own orientation, so some tracks
    are tall and thin. A tall track wastes most of a wide panel. The direction in
    which the points spread the most is the first principal component (the
    eigenvector of the 2 x 2 covariance matrix with the larger eigenvalue);
    rotating by minus its angle lays that direction along the x axis.
    Example: a track whose long straight runs at 60 degrees gets angle -60.
    """
    points = np.vstack([x - np.mean(x), y - np.mean(y)])
    covariance = points @ points.T / points.shape[1]
    values, vectors = np.linalg.eigh(covariance)          # eigenvalues in ascending order
    main = vectors[:, 1]                                  # the direction of the larger spread
    return float(-np.degrees(np.arctan2(main[1], main[0])))


def rotate(x, y, angle_deg):
    """Rotate points about the origin by angle_deg (counter-clockwise)."""
    a = np.radians(angle_deg)
    return x * np.cos(a) - y * np.sin(a), x * np.sin(a) + y * np.cos(a)


def round_list(values, digits):
    return [round(float(v), digits) for v in values]


def session_table():
    """All sessions of the three seasons with their build summary (dev + final)."""
    dev = pd.read_csv(RESULTS / "09_dataset" / "sessions.csv")
    final = pd.read_csv(RESULTS / "final" / "sessions_2025.csv")
    return pd.concat([dev, final], ignore_index=True)


def corner_table():
    dev = pd.read_csv(RESULTS / "09_dataset" / "corners.csv")
    final = pd.read_csv(RESULTS / "final" / "corners_2025.csv")
    return pd.concat([dev, final], ignore_index=True)


def openf1_session_info(year):
    """{session_key: OpenF1 session record}, from the local cache (no download)."""
    records = fetch("sessions", {"year": year, "session_name": "Qualifying"})
    return {int(r["session_key"]): r for r in records}


def openf1_drivers(session_key):
    """{code: (number, full name, team, '#rrggbb')} for one session, from the cache."""
    out = {}
    for r in fetch("drivers", {"session_key": int(session_key)}):
        colour = r.get("team_colour") or "888888"
        out[r["name_acronym"]] = (int(r["driver_number"]), r.get("full_name") or r["name_acronym"],
                                  r.get("team_name") or "", "#" + colour.lower())
    return out


# ---------------------------------------------------------------- sessions.json

def lap_list(raw_session):
    """Kept laps per driver (the laps that have raw samples), fastest first."""
    laps = (raw_session.groupby(["driver", "lap"])
            .agg(lap_time_s=("lap_time_s", "first"), compound=("compound", "first"),
                 tyre_life=("tyre_life", "first"), team=("team", "first"), samples=("time_s", "size"))
            .reset_index())
    return laps.sort_values(["driver", "lap_time_s"])


def track_outline(raw_session, reference):
    """The reference lap's X/Y (every sample), centred and rotated landscape."""
    code, _, lap = reference.split(" ")
    lap_samples = raw_session[(raw_session["driver"] == code) & (raw_session["lap"] == int(lap))]
    lap_samples = lap_samples.sort_values("time_s")
    x = lap_samples["x_m"].to_numpy()
    y = lap_samples["y_m"].to_numpy()
    centre = (float(np.mean(x)), float(np.mean(y)))
    angle = landscape_rotation(x, y)
    rx, ry = rotate(x - centre[0], y - centre[1], angle)
    return {"centre": [round(centre[0], 2), round(centre[1], 2)], "rotation_deg": round(angle, 3),
            "s": round_list(lap_samples["s_m"], 1), "x": round_list(rx, 1), "y": round_list(ry, 1)}


def build_sessions():
    sessions = session_table()
    corners = corner_table()
    info = {}
    for year in (2023, 2024, 2025):
        info.update(openf1_session_info(year))

    out = []
    raw_cache = {}   # each Parquet file is read once, then filtered per session
    for _, row in sessions.iterrows():
        key, year = int(row["session_key"]), int(row["year"])
        meta = info.get(key, {})
        entry = {"key": key, "year": year, "round": int(row["round"]), "location": row["location"],
                 "country": meta.get("country_name", ""), "circuit": meta.get("circuit_short_name", ""),
                 "date": (meta.get("date_start") or "")[:10], "note": "" if pd.isna(row["note"]) else row["note"],
                 "drivers": [], "corners": [], "track": None}
        if pd.isna(row.get("reference")) or not row.get("reference"):
            out.append(entry)
            continue
        path = RAW[year]
        if path not in raw_cache:
            raw_cache[path] = pd.read_parquet(path)
        raw_session = raw_cache[path][raw_cache[path]["session_key"] == key]
        compounds = set(raw_session["compound"].dropna())
        entry["wet"] = bool(compounds & {"INTERMEDIATE", "WET"})
        entry["track"] = track_outline(raw_session, row["reference"])
        entry["track"]["length_m"] = round(float(raw_session["s_m"].max()), 0)
        for _, c in corners[corners["session_key"] == key].sort_values("s_m").iterrows():
            entry["corners"].append({"name": c["corner"], "s_m": round(float(c["s_m"]), 1), "type": c["type"],
                                     "min_speed_kmh": int(c["min_speed_kmh"]),
                                     "entry_speed_kmh": int(c["entry_speed_kmh"])})
        names = openf1_drivers(key)
        laps = lap_list(raw_session)
        for code, driver_laps in laps.groupby("driver"):
            number, full_name, team, colour = names.get(code, (0, code, driver_laps["team"].iloc[0], "#888888"))
            entry["drivers"].append({
                "code": code, "number": number, "name": full_name, "team": driver_laps["team"].iloc[0],
                "colour": colour,
                "laps": [{"lap": int(l["lap"]), "time_s": round(float(l["lap_time_s"]), 3),
                          "compound": l["compound"] if isinstance(l["compound"], str) else "",
                          "tyre_life": None if pd.isna(l["tyre_life"]) else int(l["tyre_life"]),
                          "samples": int(l["samples"])} for _, l in driver_laps.iterrows()],
            })
        entry["drivers"].sort(key=lambda d: d["laps"][0]["time_s"])
        out.append(entry)
    return out


# ---------------------------------------------------------------- hero.json

def build_hero(sessions):
    session = next(s for s in sessions if s["year"] == HERO["year"] and s["location"] == HERO["location"])
    raw = pd.read_parquet(RAW[HERO["year"]])
    raw = raw[raw["session_key"] == session["key"]]
    track = session["track"]
    cars = []
    for code in HERO["drivers"]:
        driver = next(d for d in session["drivers"] if d["code"] == code)
        best = driver["laps"][0]
        lap = raw[(raw["driver"] == code) & (raw["lap"] == best["lap"])].sort_values("time_s")
        x, y = rotate(lap["x_m"].to_numpy() - track["centre"][0], lap["y_m"].to_numpy() - track["centre"][1],
                      track["rotation_deg"])
        cars.append({"code": code, "name": driver["name"], "team": driver["team"], "colour": driver["colour"],
                     "lap": best["lap"], "lap_time_s": best["time_s"], "compound": best["compound"],
                     "t": round_list(lap["time_s"], 3), "s": round_list(lap["s_m"], 1),
                     # integrated speed: the coordinate for the live gap (see app/data.delta_time)
                     "d": round_list(lap["d_m"], 1),
                     "x": round_list(x, 1), "y": round_list(y, 1), "speed": round_list(lap["speed_kmh"], 0)})
    return {"session_key": session["key"], "year": session["year"], "location": session["location"],
            "country": session["country"], "circuit": session["circuit"], "track": track,
            "corners": session["corners"], "cars": cars}


# ---------------------------------------------------------------- headline.json

def load(relative):
    with open(RESULTS / relative, encoding="utf-8") as file:
        return json.load(file)


def build_headline(sessions):
    pilot_timing = load("01_data_pilot/summary.json")["check_1_sample_timing"]["car"]
    pilot = load("06_pilot_stats/summary.json")
    dataset = load("09_dataset/summary.json")
    repeatability = load("11_repeatability/summary.json")
    icc = repeatability["rows"]
    dev_id = load("12_identification/summary.json")["teammates"]
    dev_sig = load("13_signature_stability/summary.json")["corner_features"]
    final = load("final/summary.json")
    explore = load("15_final_exploratory/summary.json")
    raw_rows = sum(pq.ParquetFile(path).metadata.num_rows for path in set(RAW.values()))

    icc_lap = [r["icc_lap"] for r in icc]
    icc_weekend = [r["icc_weekend"] for r in icc]
    return {
        "data": {
            "sample_rate_hz": round(pilot_timing["rate_from_mean_hz"], 2),
            "sessions": len(sessions),
            "sessions_built": sum(1 for s in sessions if s["track"] is not None),
            "raw_samples": raw_rows,
            # (driver, lap, corner) rows after cleaning: 2023-2024 + 2025
            "clean_corner_passes": repeatability["cleaning"]["clean_rows"] + final["cleaning_2025"]["clean_rows"],
            "features": len(dataset["features"]),
            # along-track error of the fused lap coordinate (Phase 3, 2024 Abu Dhabi)
            "alignment_error_m": round(load("04_alignment/summary.json")["fusion_offset_noise_m"], 2),
            "drivers": len({d["code"] for s in sessions for d in s["drivers"]}),
            "source": "01_data_pilot, 09_dataset, 11_repeatability, final (summary.json)",
        },
        "hypotheses": [
            {"id": "H1", "question": "Are corner features repeatable from lap to lap?",
             "result": f"lap-level ICC {min(icc_lap):.2f}–{max(icc_lap):.2f}; "
                       f"weekend-level {min(icc_weekend):.2f}–{max(icc_weekend):.2f}",
             "detail": "Minimum speed and throttle features repeat; braking points barely persist across weekends.",
             "verdict": "partly", "data": "2023–2024", "source": "results/11_repeatability/summary.json"},
            {"id": "H2", "question": "Do teammates differ by more than the measurement error? (pilot)",
             "result": f"{pilot['discoveries']} of {len(pilot['h2'])} comparisons after correction",
             "detail": "Norris vs Piastri, 2024 Abu Dhabi: too few laps for any test to pass, as predicted in advance.",
             "verdict": "not shown", "data": "2024 Abu Dhabi", "source": "results/06_pilot_stats/summary.json"},
            {"id": "H3", "question": "Do corner features identify the driver on unseen sessions?",
             "result": (f"{final['h3']['our features | balanced_accuracy']['mean']:.3f} vs "
                        f"{final['h3']['lap time only | balanced_accuracy']['mean']:.3f} for lap time, "
                        f"p = {final['h3']['ours minus lap time only']['wilcoxon_p']:.3f}"),
             "detail": (f"Replicated on the frozen 2025 season (development: "
                        f"{dev_id['our features | balanced_accuracy']['mean']:.3f} vs "
                        f"{dev_id['lap time only | balanced_accuracy']['mean']:.3f}). Not better than whole-lap "
                        f"statistics ({final['h3']['raw lap statistics | balanced_accuracy']['mean']:.3f})."),
             "verdict": "supported" if final["h3_supported"] else "not supported", "data": "2025 (held out)",
             "source": "results/final/summary.json"},
            {"id": "H4", "question": "Does the signature follow drivers who change teams?",
             "result": (f"{final['h4']['own_closer']} of {final['h4']['changers_included']} changers, "
                        f"p = {final['h4']['sign_test_p']:.2f}"),
             "detail": (f"Drivers who stay keep their signature ({final['non_changer_check']['own_closer']} of "
                        f"{final['non_changer_check']['drivers']}; development {dev_sig['own_closer_than_teammate']} "
                        f"of {dev_sig['pairs']}). Across a team change it was not shown; control: stayers "
                        f"{explore['changers_vs_stayers']['stayers_own_closer']} (exploratory)."),
             "verdict": "supported" if final["h4_supported"] else "not supported", "data": "2025 (held out)",
             "source": "results/final/summary.json"},
        ],
        "preregistration": {"part_a": pilot["preregistration_commit"][:7],
                            "part_b": final["preregistration_commit"][:7]},
    }


# ---------------------------------------------------------------- features.json

FEATURE_TEXT = {   # label, unit, what it measures (definitions: src/apextrace/features.py)
    "brake_onset_m": ("Brake onset", "m", "Where braking starts, in metres from the corner marker (negative = before it)."),
    "braking_distance_m": ("Braking distance", "m", "From brake onset to the slowest point."),
    "mean_decel_ms2": ("Mean deceleration", "m/s²", "Average deceleration from brake onset to the slowest point."),
    "min_speed_kmh": ("Minimum speed", "km/h", "The slowest speed in the corner (a parabola through the three slowest samples)."),
    "apex_m": ("Slowest point", "m", "Where the slowest speed is reached, in metres from the corner marker."),
    "throttle_pickup_m": ("Throttle pickup", "m", "Where the throttle first passes 10 % after braking."),
    "full_throttle_m": ("Full throttle", "m", "Where the throttle first reaches 99 % after the corner."),
    "entry_speed_kmh": ("Entry speed", "km/h", "Speed 200 m before the corner marker."),
    "exit_speed_kmh": ("Exit speed", "km/h", "Speed 150 m after the corner marker."),
    "corner_time_s": ("Corner time", "s", "Time from 200 m before to 150 m after the corner marker."),
}


def number_or_none(value, digits):
    return None if value is None or not np.isfinite(value) else round(float(value), digits)


def build_features():
    """The 10 features of the lap vectors, with their error and repeatability per corner type."""
    rows = load("11_repeatability/summary.json")["rows"]
    by_key = {(r["feature"], r["corner_type"]): r for r in rows}
    group_of = {f: g for g, features in FEATURE_GROUPS.items() for f in features}
    out = []
    for feature in ALL_FEATURES:
        label, unit, meaning = FEATURE_TEXT[feature]
        per_type = {}
        for corner_type in CORNER_TYPES:
            r = by_key[(feature, corner_type)]
            per_type[corner_type] = {
                "measurement_error_per_lap": number_or_none(r["measurement_error_per_lap"], 3),
                "lap_to_lap_sd": number_or_none(r["lap_to_lap_sd"], 3),
                "icc_lap": number_or_none(r["icc_lap"], 3), "icc_lap_ci": [number_or_none(r["icc_lap_low"], 3),
                                                                          number_or_none(r["icc_lap_high"], 3)],
                "icc_weekend": number_or_none(r["icc_weekend"], 3),
                "icc_weekend_ci": [number_or_none(r["icc_weekend_low"], 3), number_or_none(r["icc_weekend_high"], 3)],
            }
        out.append({"key": feature, "label": label, "unit": unit, "meaning": meaning, "group": group_of[feature],
                    "by_corner_type": per_type})
    return {"features": out, "source": "results/11_repeatability/summary.json (ICC, H1) and "
                                       "results/03_synthetic_errors (per-lap measurement error, Phase 2)"}


# ---------------------------------------------------------------- identification.json

def build_identification():
    """Per team-season teammate identification (H3): development 2023-2024 and the frozen 2025 test."""
    columns = {"lap_time": "lap time only | balanced_accuracy", "raw": "raw lap statistics | balanced_accuracy",
               "ours": "our features | balanced_accuracy", "vote": "our features | weekend vote",
               "shuffled": "shuffled labels | balanced_accuracy"}
    teams = []
    for path in [RESULTS / "12_identification" / "teammates.csv", RESULTS / "final" / "h3_teammates_2025.csv"]:
        for _, r in pd.read_csv(path).iterrows():
            team, year = r["team_season"].rsplit(" ", 1)
            row = {"team": team, "year": int(year), "drivers": r["drivers"], "sessions": int(r["sessions"]),
                   "laps": int(r["laps"])}
            for key, column in columns.items():
                row[key] = round(float(r[column]), 4)
            teams.append(row)
    dev = load("12_identification/summary.json")["teammates"]
    final = load("final/summary.json")["h3"]

    def summary(block):
        out = {key: {"mean": round(block[c]["mean"], 4), "ci95": [round(block[c]["ci95_low"], 4),
                                                                round(block[c]["ci95_high"], 4)]}
               for key, c in columns.items()}
        test = block["ours minus lap time only"]
        out["ours_vs_lap_time"] = {"wins": test["wins"], "teams": test["team_seasons"], "p": test["wilcoxon_p"]}
        test = block["ours minus raw lap statistics"]
        out["ours_vs_raw"] = {"wins": test["wins"], "teams": test["team_seasons"], "p": test["wilcoxon_p"]}
        return out

    return {"teams": teams, "development_2023_2024": summary(dev), "final_2025": summary(final),
            "source": "results/12_identification/, results/final/"}


# ---------------------------------------------------------------- signatures.json

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def team_colours(sessions):
    """{(year, team): '#rrggbb'}, the colour the timing feed used most often for that team that year."""
    counts = {}
    for session in sessions:
        for driver in session["drivers"]:
            key = (session["year"], driver["team"])
            counts.setdefault(key, {}).setdefault(driver["colour"], 0)
            counts[key][driver["colour"]] += 1
    return {key: max(colours, key=colours.get) for key, colours in counts.items()}


def build_signatures(sessions):
    """The H4 signatures behind every point of the H4 chart, rebuilt with the exact H4 steps.

    For each driver with a 2024 signature who raced in 2025: their 2024 season
    signature, their 2025 signature on the weekends with their main 2025 team,
    and that team's other driver on the same weekends (14_final_2025.h4). All are
    z-scored with the 2024 spread. The distances are then checked against the
    frozen results files, so the picture can't drift from the numbers.
    """
    exploratory = load_module("exploratory", REPO_ROOT / "experiments" / "15_final_exploratory.py")
    final = exploratory.final
    laps_2025, laps_2024 = exploratory.load_lap_tables()
    changes = exploratory.team_changes(laps_2025, laps_2024)
    corner_columns = [c for c in laps_2024.columns if "__" in c]
    reference_raw = season_signatures(laps_2024, corner_columns, min_sessions=final.MIN_WEEKENDS).xs(2024, level="year")
    reference = standardise(reference_raw, corner_columns, reference_raw)

    def z_list(series):
        return [number_or_none(v, 3) for v in series[corner_columns]]

    colours = team_colours(sessions)
    drivers = []
    for _, change in changes.iterrows():
        driver = change["driver"]
        if driver not in reference.index:
            continue
        team, weekends = final.most_weekends_team(laps_2025, driver)
        team_laps = laps_2025[laps_2025["team"] == team]
        sessions = set(team_laps.loc[team_laps["driver"] == driver, "session_key"])
        others = team_laps[(team_laps["driver"] != driver) & team_laps["session_key"].isin(sessions)]
        if weekends < final.MIN_WEEKENDS or others.empty:
            continue
        mate = others.groupby("driver")["session_key"].nunique().idxmax()
        pair = team_laps[team_laps["driver"].isin([driver, mate]) & team_laps["session_key"].isin(sessions)]
        new_raw = season_signatures(pair, corner_columns, min_sessions=final.MIN_WEEKENDS).xs(2025, level="year")
        if driver not in new_raw.index or mate not in new_raw.index:
            continue
        new = standardise(new_raw, corner_columns, reference_raw)
        drivers.append({
            "driver": driver, "team_2024": reference_raw.loc[driver, "team"], "team_2025": team, "teammate_2025": mate,
            "colour_2024": colours.get((2024, reference_raw.loc[driver, "team"]), "#888888"),
            "colour_2025": colours.get((2025, team), "#888888"),
            "weekends_2025": int(weekends), "changed": bool(change["changed"]),
            "preregistered_changer": bool(change["preregistered_changer"]),
            "own_2024": z_list(reference.loc[driver]), "own_2025": z_list(new.loc[driver]),
            "teammate_2025_signature": z_list(new.loc[mate]),
            "distance_own_2024": round(distance(new.loc[driver, corner_columns], reference.loc[driver, corner_columns]), 4),
            "distance_teammate_2025": round(distance(new.loc[driver, corner_columns], new.loc[mate, corner_columns]), 4),
        })

    # the check: every distance must equal the frozen / exploratory results
    expected = {}
    for path in [RESULTS / "15_final_exploratory" / "h4_all_changers.csv",
                 RESULTS / "15_final_exploratory" / "h4_shape_control_non_changers.csv"]:
        for _, r in pd.read_csv(path).iterrows():
            if r["included"]:
                expected[r["driver"]] = (r["distance_own_2024"], r["distance_new_teammate_2025"])
    for _, r in pd.read_csv(RESULTS / "final" / "h4_changers.csv").iterrows():
        if r["included"]:
            assert np.isclose(expected[r["driver"]][0], r["distance_own_2024"], atol=1e-3)
    for d in drivers:
        own, mate = expected[d["driver"]]
        assert abs(d["distance_own_2024"] - own) < 1e-3 and abs(d["distance_teammate_2025"] - mate) < 1e-3, d["driver"]
    assert len(drivers) == len(expected), (len(drivers), len(expected))

    columns = []
    for column in corner_columns:
        feature_rel, corner_type = column.split("__")
        columns.append({"key": column, "feature": feature_rel.removesuffix("_rel"), "corner_type": corner_type})
    h4 = load("final/summary.json")["h4"]
    explore = load("15_final_exploratory/summary.json")
    control = explore["h4_shape_control_non_changers"]
    summary = {"changers_own_closer": h4["own_closer"], "changers": h4["changers_included"], "p": h4["sign_test_p"],
               "stayers_own_closer": control["own_closer"], "stayers": control["changers_included"],
               "stayers_p": control["sign_test_p"],
               "fisher_p": explore["changers_vs_stayers"]["fisher_exact_two_sided_p"]}
    return {"columns": columns, "drivers": drivers, "summary": summary,
            "note": "z-scores: 0 = the average 2024 driver, 1 = one 2024 standard deviation; field-relative features",
            "checked_against": ["results/final/h4_changers.csv", "results/15_final_exploratory/h4_all_changers.csv",
                                "results/15_final_exploratory/h4_shape_control_non_changers.csv"]}


# ---------------------------------------------------------------- method.json (the measurement science)

# The estimator the pipeline uses for each feature (features.py, chosen by the Phase 2 Monte Carlo),
# and the obvious "naive" one it replaced. Peak deceleration has no usable estimator (replaced by mean).
CHOSEN_ESTIMATOR = {"brake_onset_m": "speed breakpoint inside off-on interval", "apex_m": "parabola 3 points",
                    "min_speed_kmh": "parabola 3 points", "throttle_pickup_m": "interpolated crossing",
                    "full_throttle_m": "interpolated crossing", "entry_speed_kmh": "linear interpolation",
                    "exit_speed_kmh": "linear interpolation"}
NAIVE_ESTIMATOR = {"brake_onset_m": "first on sample", "apex_m": "lowest sample", "min_speed_kmh": "lowest sample",
                   "throttle_pickup_m": "first sample >= 10 %", "full_throttle_m": "first sample >= 99 %"}


def build_method(sessions):
    """Data for the Method page: sampling, filter delay, estimator errors, alignment, cleaning funnel.

    Everything is read from the Phase 1-3 results files or recomputed with the
    project's own functions (the same synthetic corner and filters as
    experiments/02_group_delay_demo.py, the same gap function as the app).
    """
    sys.path.insert(0, str(REPO_ROOT))      # so `import app` works when this file is run as a script
    from app.data import delta_time, fused_distance, increasing_distance
    from apextrace.resampling import to_uniform_grid
    from apextrace.synthetic import degrade_like_feed, load_interval_distribution, make_true_corner, random_corner_params

    out = {}

    # 1. the feed's sampling: the measured interval histogram (2024 Abu Dhabi, check 1)
    histogram = pd.read_csv(RESULTS / "01_data_pilot" / "interval_histogram.csv")
    histogram = histogram[histogram["car_count"] > 0]
    timing = load("01_data_pilot/summary.json")["check_1_sample_timing"]["car"]
    out["sampling"] = {
        "bins": [{"interval_s": round(float(r.interval_s), 2), "count": int(r.car_count)} for r in histogram.itertuples()],
        "rate_hz": round(timing["rate_from_mean_hz"], 2), "median_s": timing["median_s"], "p95_s": timing["p95_s"],
        "max_s": timing["max_s"], "clock_s": timing["clock_tick_s"], "normal_max_s": timing["normal_max_s"],
        "gaps": timing["gaps_longer_than_threshold"], "count": timing["count"],
        "source": "results/01_data_pilot (2024 Abu Dhabi, all car samples of the pilot laps)"}

    # 2. filters move events: one synthetic heavy-braking corner, exactly as 02_group_delay_demo part A (lap 0)
    demo = load_module("group_delay", REPO_ROOT / "experiments" / "02_group_delay_demo.py")
    intervals, probs = load_interval_distribution(RESULTS / "01_data_pilot" / "interval_histogram.csv")
    rng = np.random.default_rng(demo.SEED)
    truth = make_true_corner(random_corner_params("heavy_braking", rng))
    samples = degrade_like_feed(truth, intervals, probs, rng, max_interval_s=0.6)
    grid, speed, _ = to_uniform_grid(samples["time_s"], samples["speed_kmh"], demo.GRID_STEP_S)
    t0 = truth["events"]["brake_onset"]["t"]
    level = 0.5 * (truth["events"]["entry_speed_kmh"] + truth["events"]["apex"]["speed_kmh"])
    true_mid = demo.mid_braking_time(truth["time_s"], truth["speed_kmh"], level)
    window = (truth["time_s"] >= t0 - 2.0) & (truth["time_s"] <= t0 + 3.5)
    step = max(1, int(np.sum(window) / 400))                     # ~400 points are plenty for a line
    shifts = load("02_group_delay/summary.json")["A_braking_shift_heavy_braking"]
    filters = []
    for name, apply in demo.filters_to_compare().items():
        filtered = apply(speed)
        found_mid = demo.mid_braking_time(grid, filtered, level)
        shift_m = float(np.interp(found_mid, truth["time_s"], truth["distance_m"])
                        - np.interp(true_mid, truth["time_s"], truth["distance_m"]))
        keep = (grid >= t0 - 2.0) & (grid <= t0 + 3.5)
        filters.append({"name": name, "t": round_list(grid[keep] - t0, 3), "speed": round_list(filtered[keep], 2),
                        "mid_t": round(float(found_mid - t0), 3), "mid_shift_m_this_corner": round(shift_m, 1),
                        "mean_shift_m": {k: round(v, 2) for k, v in shifts[name].items()}})
    sample_window = (samples["time_s"] >= t0 - 2.0) & (samples["time_s"] <= t0 + 3.5)
    out["filters"] = {
        "truth": {"t": round_list(truth["time_s"][window][::step] - t0, 3),
                  "speed": round_list(truth["speed_kmh"][window][::step], 2)},
        "samples": {"t": round_list(samples["time_s"][sample_window] - t0, 3),
                    "speed": round_list(samples["speed_kmh"][sample_window], 0)},
        "level_kmh": round(float(level), 1), "true_mid_t": round(float(true_mid - t0), 3),
        "grid_step_s": demo.GRID_STEP_S, "corners_in_average": demo.LAPS, "filters": filters,
        "source": "experiments/02_group_delay_demo.py (part A), results/02_group_delay/summary.json"}

    # 3. estimator errors (Monte Carlo, realistic sampling): every estimator tried, per corner type
    rows = load("03_synthetic_errors/summary.json")
    estimators = []
    for r in rows["rows"]:
        if r["scenario"] != "real":
            continue
        estimators.append({"corner_type": r["corner_type"], "feature": r["feature"], "estimator": r["estimator"],
                           "bias": round(r["bias"], 2), "std": round(r["std"], 2), "rmse": round(r["rmse"], 2),
                           "chosen": CHOSEN_ESTIMATOR.get(r["feature"]) == r["estimator"],
                           "naive": NAIVE_ESTIMATOR.get(r["feature"]) == r["estimator"]})
    out["estimators"] = {"rows": estimators, "laps_per_type": rows["laps_per_type"],
                         "source": "results/03_synthetic_errors/summary.json"}

    # 4. alignment: the hero lap's projected-minus-integrated offset, and the gap from each coordinate
    hero_session = next(s for s in sessions if s["year"] == HERO["year"] and s["location"] == HERO["location"])
    raw = pd.read_parquet(RAW[HERO["year"]], filters=[("session_key", "=", hero_session["key"])])
    laps = {}
    for code in HERO["drivers"]:
        best = next(d for d in hero_session["drivers"] if d["code"] == code)["laps"][0]
        laps[code] = raw[(raw["driver"] == code) & (raw["lap"] == best["lap"])].sort_values("time_s")
        laps[code].attrs["lap_time"] = best["time_s"]
    a, b = laps[HERO["drivers"][0]], laps[HERO["drivers"][1]]
    s, d = a["s_m"].to_numpy(), a["d_m"].to_numpy()
    fused = fused_distance(s, d)
    gaps = {}
    for column in ["s_m", "d_m"]:
        g, gap = delta_time(a[column], a["time_s"], b[column], b["time_s"])
        gaps[column] = {"s": round_list(g, 0), "gap": round_list(gap, 3)}
    d_a, s_a = increasing_distance(d, fused)
    alignment = load("04_alignment/summary.json")
    out["alignment"] = {
        "driver": HERO["drivers"][0], "other": HERO["drivers"][1], "lap_time_gap": round(b.attrs["lap_time"] - a.attrs["lap_time"], 3),
        "offset": {"d": round_list(d, 1), "raw": round_list(s - d, 2), "smooth": round_list(fused - d, 2)},
        "gap_from_projected": gaps["s_m"], "gap_from_integrated": gaps["d_m"],
        "window_error_m": round(alignment["fusion_offset_noise_m"], 2),
        "source": "raw samples of the hero laps (2024 Abu Dhabi), app.data.fused_distance / delta_time; "
                  "results/04_alignment/summary.json"}

    # 5. what survives each step (the cleaning funnel), development and final test
    dataset = load("09_dataset/summary.json")
    repeat = load("11_repeatability/summary.json")["cleaning"]
    final = load("final/summary.json")["cleaning_2025"]
    out["funnel"] = {
        "development": {"rows": dataset["rows"], "usable": dataset["usable_rows"],
                        "excluded": dataset["exclusion_reasons"], "cleaning": repeat},
        "final_2025": {"usable": final["usable_rows"], "cleaning": final},
        "source": "results/09_dataset, results/11_repeatability, results/final (summary.json)"}
    return out


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sessions = build_sessions()
    hero = build_hero(sessions)
    headline = build_headline(sessions)
    outputs = [("sessions.json", sessions), ("hero.json", hero), ("headline.json", headline),
               ("features.json", build_features()), ("identification.json", build_identification()),
               ("signatures.json", build_signatures(sessions)), ("method.json", build_method(sessions))]
    for name, content in outputs:
        with open(OUT_DIR / name, "w", encoding="utf-8") as file:
            json.dump(content, file, ensure_ascii=False, separators=(",", ":"))
        print(f"{name:14s} {(OUT_DIR / name).stat().st_size / 1024:7.1f} KB")
    print(json.dumps(headline, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()

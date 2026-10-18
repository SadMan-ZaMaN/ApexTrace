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

Team colours come from the OpenF1 driver list (cached, no download).
Driver head-shot URLs in that list are deliberately NOT exported (no photos).

Run from the repo root (reads only local files):
    .venv\\Scripts\\python.exe experiments\\16_app_data.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from apextrace.openf1 import fetch

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


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sessions = build_sessions()
    hero = build_hero(sessions)
    headline = build_headline(sessions)
    for name, content in [("sessions.json", sessions), ("hero.json", hero), ("headline.json", headline)]:
        with open(OUT_DIR / name, "w", encoding="utf-8") as file:
            json.dump(content, file, ensure_ascii=False, separators=(",", ":"))
        print(f"{name:14s} {(OUT_DIR / name).stat().st_size / 1024:7.1f} KB")
    print(json.dumps(headline, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()

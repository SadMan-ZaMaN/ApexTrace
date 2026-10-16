"""OpenF1 as a data source: the same live-timing feed as FastF1, rebuilt into our tables.

Why: since 2026-10-16 the F1 live-timing archive answers 401 (unauthorized),
so FastF1 can't download new sessions. OpenF1 (api.openf1.org) serves the same
raw feed: for Norris's 2024 Abu Dhabi pole lap all 320 car samples and 323
position samples were identical (docs/decisions.md). But OpenF1 gives raw
pieces, not FastF1's ready-made lap table, so this module rebuilds it:

  FastF1 column    rebuilt from (OpenF1)
  LapTime          laps.lap_duration
  PitOutTime       laps.is_pit_out_lap
  PitInTime        "the next lap is a pit-out lap, or it's the driver's last lap"
  Stint, Compound, TyreLife   stints (lap_start, lap_end, compound, tyre_age_at_start)
  Deleted          race_control messages "CAR n (ABC) TIME m:ss.sss DELETED - reason",
                   undone by "... WILL BE REINSTATED" (matched by lap TIME, like FastF1)
  TrackStatus      race_control flags: yellow (per mini-sector, until its CLEAR),
                   red, safety car, virtual safety car, overlapping the lap
  IsAccurate       FastF1's four checks, from OpenF1 fields (see accuracy_checks)

Every request is cached as a JSON file in cache/openf1/, so each piece of
data is downloaded only once. The 2025 season is refused unless FINAL_TEST=1.
"""

import hashlib
import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from apextrace.data_loading import check_not_frozen

BASE_URL = "https://api.openf1.org/v1/"
REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / "cache" / "openf1"
PAUSE_AFTER_REQUEST_S = 0.35   # be polite to a free service


# ---------------------------------------------------------------- downloading with a cache

def cache_file(endpoint, params, cache_dir):
    """A file name that is unique for (endpoint, params)."""
    text = endpoint + "?" + "&".join(f"{key}={params[key]}" for key in sorted(params))
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()[:16]
    return Path(cache_dir) / endpoint / f"{digest}.json"


def fetch(endpoint, params, cache_dir=CACHE_DIR, retries=6):
    """GET an OpenF1 endpoint, using the local cache when possible. Returns a list of dicts.

    On "too many requests" (429) or a server error, waits and retries, each
    time twice as long (1, 2, 4, ... s: "exponential backoff").
    """
    path = cache_file(endpoint, params, cache_dir)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    wait = 1.0
    for attempt in range(retries):
        response = requests.get(BASE_URL + endpoint, params=params, timeout=120)
        if response.status_code == 200:
            data = response.json()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data), encoding="utf-8")
            time.sleep(PAUSE_AFTER_REQUEST_S)
            return data
        if response.status_code == 404:
            return []  # OpenF1 answers 404 for "no rows match"
        if response.status_code in (429, 500, 502, 503, 504) and attempt < retries - 1:
            time.sleep(wait)
            wait *= 2
            continue
        response.raise_for_status()
    return []


def to_utc_naive(series):
    """ISO date strings with time zone -> pandas datetimes in UTC without the time zone."""
    return pd.to_datetime(series, format="ISO8601", utc=True).dt.tz_localize(None)


# ---------------------------------------------------------------- sessions and drivers

def qualifying_sessions(year, cache_dir=CACHE_DIR):
    """The main qualifying session of every event in a year (no sprint qualifying)."""
    check_not_frozen(year)
    table = pd.DataFrame(fetch("sessions", {"year": year, "session_name": "Qualifying"}, cache_dir))
    table = table[table["session_type"] == "Qualifying"].copy()
    table["date_start"] = to_utc_naive(table["date_start"])
    table["date_end"] = to_utc_naive(table["date_end"])
    return table.sort_values("date_start").reset_index(drop=True)


def drivers_of(session_key, cache_dir=CACHE_DIR):
    """{driver_number: (three-letter code, team name)} for one session."""
    table = pd.DataFrame(fetch("drivers", {"session_key": session_key}, cache_dir))
    out = {}
    for _, row in table.iterrows():
        out[int(row["driver_number"])] = (row["name_acronym"], row["team_name"])
    return out


# ---------------------------------------------------------------- race control: deleted laps and flags

DELETED = re.compile(r"CAR (\d+) \((\w+)\) TIME (\d+):(\d\d\.\d{3}) DELETED - (.*?)(?: LAP \d+.*)?$")
REINSTATED = re.compile(r"CAR (\d+) \((\w+)\) TIME (\d+):(\d\d\.\d{3}) WILL BE REINSTATED")


def deleted_lap_times(race_control):
    """{(driver_number, lap time in s rounded to ms): reason} for laps deleted and not reinstated.

    Messages are read in time order; a later "WILL BE REINSTATED" with the
    same driver and time cancels the deletion.
    Example: "CAR 81 (PIA) TIME 1:22.985 DELETED - TRACK LIMITS AT TURN 1 LAP 13 18:54:15"
    -> (81, 82.985): "TRACK LIMITS AT TURN 1".
    ("LAP DELETED" messages without a time, e.g. on in-laps, can't be matched
    to a lap reliably and are ignored, as FastF1 does.)
    """
    deleted = {}
    for message in sorted(race_control, key=lambda m: m["date"]):
        text = message.get("message") or ""
        match = DELETED.search(text)
        if match:
            seconds = round(int(match.group(3)) * 60 + float(match.group(4)), 3)
            deleted[(int(match.group(1)), seconds)] = match.group(5).strip()
            continue
        match = REINSTATED.search(text)
        if match:
            seconds = round(int(match.group(3)) * 60 + float(match.group(4)), 3)
            deleted.pop((int(match.group(1)), seconds), None)
    return deleted


def flag_intervals(race_control, session_end):
    """Time intervals with a non-green track status: list of (start, end, code).

    Codes as in FastF1's track status: '2' yellow (any mini-sector),
    '4' safety car, '5' red flag, '6' virtual safety car.
      - a YELLOW / DOUBLE YELLOW in sector k lasts until "CLEAR" in sector k,
        or until a track-wide GREEN/CLEAR;
      - RED lasts until the next track-wide GREEN;
      - safety cars: "...SAFETY CAR DEPLOYED" until "...ENDING" or
        "...IN THIS LAP".
    Anything still open at the end of the session ends at session_end.
    """
    intervals = []
    open_sectors = {}
    red_start = None
    sc_start = {}
    for message in sorted(race_control, key=lambda m: m["date"]):
        when = pd.Timestamp(message["date"]).tz_convert("UTC").tz_localize(None)
        category = message.get("category")
        flag = message.get("flag")
        scope = message.get("scope")
        text = (message.get("message") or "").upper()
        if category == "Flag":
            if scope == "Sector" and flag in ("YELLOW", "DOUBLE YELLOW"):
                open_sectors.setdefault(message.get("sector"), when)
            elif scope == "Sector" and flag == "CLEAR":
                start = open_sectors.pop(message.get("sector"), None)
                if start is not None:
                    intervals.append((start, when, "2"))
            elif scope == "Track" and flag == "RED":
                red_start = red_start or when
            elif scope == "Track" and flag in ("GREEN", "CLEAR"):
                for start in open_sectors.values():
                    intervals.append((start, when, "2"))
                open_sectors = {}
                if red_start is not None and flag == "GREEN":
                    intervals.append((red_start, when, "5"))
                    red_start = None
        elif category == "SafetyCar":
            code = "6" if "VIRTUAL" in text else "4"
            if "DEPLOYED" in text:
                sc_start.setdefault(code, when)
            elif "ENDING" in text or "IN THIS LAP" in text:
                start = sc_start.pop(code, None)
                if start is not None:
                    intervals.append((start, when, code))
    for start in open_sectors.values():
        intervals.append((start, session_end, "2"))
    if red_start is not None:
        intervals.append((red_start, session_end, "5"))
    for code, start in sc_start.items():
        intervals.append((start, session_end, code))
    return intervals


def track_status(lap_start, lap_end, intervals):
    """'1' (green) plus the codes of every flag interval that overlaps the lap, e.g. '12'."""
    codes = set()
    for start, end, code in intervals:
        if start < lap_end and end > lap_start:
            codes.add(code)
    return "1" + "".join(sorted(codes))


# ---------------------------------------------------------------- the lap table

def accuracy_checks(lap, previous):
    """FastF1's IsAccurate, rebuilt (fastf1/core.py, Session._check_lap_accuracy), checks 1-3:
      1. not an in/out lap, track status green or yellow only, lap and all
         three sector times present;
      2. the three sector times add up to the lap time (within 3 ms);
      3. the previous lap was not under a safety car.
    FastF1's check 4 ("the lap starts where the previous lap ended, within
    3 ms") can't be rebuilt: OpenF1's lap start times are only accurate to
    ~0.05-0.15 s (e.g. NOR 2024 Abu Dhabi Q lap 12 -> 13: 45 ms apart), and for
    out laps they mark the pit exit. Using it would wrongly fail almost every
    push lap (found in experiments/07_openf1_validation.py).
    """
    check_1 = (pd.isna(lap["PitInTime"]) and pd.isna(lap["PitOutTime"])
               and lap["TrackStatus"] in ("1", "2", "12", "21")
               and not pd.isna(lap["LapTime"])
               and not any(pd.isna(lap[f"Sector{k}Time_s"]) for k in (1, 2, 3)))
    if not check_1:
        return False
    sector_sum = lap["Sector1Time_s"] + lap["Sector2Time_s"] + lap["Sector3Time_s"]
    check_2 = abs(sector_sum - lap["LapTime"].total_seconds()) <= 0.003
    check_3 = previous is None or "4" not in previous["TrackStatus"]
    return bool(check_2 and check_3)


def lap_table(session_key, session_end, cache_dir=CACHE_DIR):
    """All laps of one session as a table with the columns select_laps() needs (and a few more)."""
    laps = pd.DataFrame(fetch("laps", {"session_key": session_key}, cache_dir))
    stints = pd.DataFrame(fetch("stints", {"session_key": session_key}, cache_dir))
    race_control = fetch("race_control", {"session_key": session_key}, cache_dir)
    names = drivers_of(session_key, cache_dir)
    deleted = deleted_lap_times(race_control)
    intervals = flag_intervals(race_control, session_end)

    rows = []
    for driver_number, driver_laps in laps.groupby("driver_number"):
        driver_number = int(driver_number)
        code, team = names.get(driver_number, (str(driver_number), ""))
        driver_laps = driver_laps.sort_values("lap_number").reset_index(drop=True)
        driver_stints = stints[stints["driver_number"] == driver_number] if len(stints) else stints
        previous = None
        for i, lap in driver_laps.iterrows():
            lap_number = int(lap["lap_number"])
            duration = lap["lap_duration"]
            start = pd.Timestamp(lap["date_start"]).tz_convert("UTC").tz_localize(None) \
                if isinstance(lap["date_start"], str) else pd.NaT
            lap_time = pd.Timedelta(float(duration), unit="s") if not pd.isna(duration) else pd.NaT
            is_last = i == len(driver_laps) - 1
            next_is_out = (not is_last) and bool(driver_laps.loc[i + 1, "is_pit_out_lap"])

            # OpenF1 stints overlap by one lap (stint 1: laps 1-4, stint 2: laps 4-6):
            # the shared lap is the out lap of the NEW stint (as in FastF1), so
            # the latest stint that contains the lap wins.
            stint_number, compound, tyre_life = np.nan, None, np.nan
            for _, stint in driver_stints.sort_values("stint_number").iterrows():
                if stint["lap_start"] <= lap_number <= stint["lap_end"]:
                    stint_number = int(stint["stint_number"])
                    compound = stint["compound"]
                    tyre_life = np.nan
                    if not pd.isna(stint["tyre_age_at_start"]):
                        tyre_life = float(stint["tyre_age_at_start"] + (lap_number - stint["lap_start"]) + 1)

            end = start + lap_time if not pd.isna(lap_time) and not pd.isna(start) else pd.NaT
            reason = deleted.get((driver_number, round(float(duration), 3))) if not pd.isna(duration) else None
            row = {
                "Driver": code, "DriverNumber": driver_number, "Team": team, "LapNumber": lap_number,
                "Stint": stint_number, "Compound": compound, "TyreLife": tyre_life,
                "LapTime": lap_time, "LapStartDate": start,
                "PitOutTime": pd.Timedelta(0) if bool(lap["is_pit_out_lap"]) else pd.NaT,
                "PitInTime": pd.Timedelta(0) if (next_is_out or is_last) else pd.NaT,
                "Deleted": reason is not None, "DeletedReason": reason or "",
                "TrackStatus": track_status(start, end, intervals) if not pd.isna(end) else "",
                "Sector1Time_s": lap["duration_sector_1"], "Sector2Time_s": lap["duration_sector_2"],
                "Sector3Time_s": lap["duration_sector_3"],
            }
            row["IsAccurate"] = accuracy_checks(row, previous)
            rows.append(row)
            previous = row
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- one lap's samples

def lap_streams(session_key, driver_number, lap_start, lap_end, pad_s=2.0, cache_dir=CACHE_DIR):
    """Car data and position data of one lap (plus pad_s on each side), as arrays.

    Times are seconds from lap_start, the same reference for both streams.
    Brake comes as 0/100 in OpenF1; it becomes True/False here. X, Y are
    converted from decimetres to metres.
    """
    params = {"session_key": session_key, "driver_number": driver_number,
              "date>": (lap_start - pd.Timedelta(pad_s, unit="s")).isoformat(),
              "date<": (lap_end + pd.Timedelta(pad_s, unit="s")).isoformat()}
    car = pd.DataFrame(fetch("car_data", params, cache_dir))
    pos = pd.DataFrame(fetch("location", params, cache_dir))
    if car.empty or pos.empty:
        return None
    car["date"] = to_utc_naive(car["date"])
    pos["date"] = to_utc_naive(pos["date"])
    car = car.sort_values("date").drop_duplicates("date")
    pos = pos.sort_values("date").drop_duplicates("date")
    return {
        "car_time_s": (car["date"] - lap_start).dt.total_seconds().to_numpy(),
        "speed_kmh": car["speed"].to_numpy(dtype=float),
        "throttle_pct": car["throttle"].to_numpy(dtype=float),
        "brake": car["brake"].to_numpy(dtype=float) > 0,
        "gear": car["n_gear"].to_numpy(dtype=float),
        "pos_time_s": (pos["date"] - lap_start).dt.total_seconds().to_numpy(),
        "x_m": pos["x"].to_numpy(dtype=float) / 10.0,
        "y_m": pos["y"].to_numpy(dtype=float) / 10.0,
        "lap_duration_s": (lap_end - lap_start).total_seconds(),
    }


# ---------------------------------------------------------------- one lap on the track coordinate

def reference_from_lap(session_key, driver_number, lap_start, lap_time, cache_dir=CACHE_DIR):
    """Reference path (track.reference_path_from_xy) from one OpenF1 lap's positions, with exact edges."""
    from apextrace.track import clip_to_lap, reference_path_from_xy

    streams = lap_streams(session_key, driver_number, lap_start, lap_start + lap_time, cache_dir=cache_dir)
    duration = streams["lap_duration_s"]
    _, pos, _ = clip_to_lap(streams["pos_time_s"], {"x": streams["x_m"], "y": streams["y_m"]}, 0.0, duration)
    return reference_path_from_xy(pos["x"], pos["y"])


def lap_samples_on_track(session_key, driver_number, lap_start, lap_time, reference, cache_dir=CACHE_DIR):
    """One OpenF1 lap -> measured car samples on the track coordinate (track.samples_on_track).

    Times are seconds from the lap start. Returns None if OpenF1 has no data
    for the lap.
    """
    from apextrace.track import clip_to_lap, samples_on_track

    streams = lap_streams(session_key, driver_number, lap_start, lap_start + lap_time, cache_dir=cache_dir)
    if streams is None:
        return None
    duration = streams["lap_duration_s"]
    car_times, car, measured = clip_to_lap(
        streams["car_time_s"],
        {"speed": streams["speed_kmh"], "throttle": streams["throttle_pct"],
         "brake": streams["brake"], "gear": streams["gear"]},
        0.0, duration, step_channels=("brake", "gear"))
    pos_times, pos, _ = clip_to_lap(streams["pos_time_s"], {"x": streams["x_m"], "y": streams["y_m"]}, 0.0, duration)
    return samples_on_track(car_times, car["speed"], car["throttle"], car["brake"], car["gear"], measured,
                            pos_times, pos["x"], pos["y"], reference)

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
import gzip
import json
import os
import re
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from apextrace.data_loading import check_not_frozen

BASE_URL = "https://api.openf1.org/v1/"
REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / "cache" / "openf1"
# OpenF1's free tier allows ~30 requests per minute; sending them at most
# every 2.1 s (~28 per minute) avoids "429 Too Many Requests" altogether.
MIN_SECONDS_BETWEEN_REQUESTS = 2.1
_last_request_time = 0.0
# Several downloads may run at once (threads, see 08_download_openf1.py). The
# lock makes them take turns at the pacing check, so request STARTS stay at
# least 2.1 s apart however many are in flight.
_rate_lock = threading.Lock()


# ---------------------------------------------------------------- downloading with a cache

def cache_file(endpoint, params, cache_dir):
    """A file name that is unique for (endpoint, params), gzip-compressed (JSON shrinks ~10x)."""
    text = endpoint + "?" + "&".join(f"{key}={params[key]}" for key in sorted(params))
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()[:16]
    return Path(cache_dir) / endpoint / f"{digest}.json.gz"


def wait_for_rate_limit():
    """Sleep until at least MIN_SECONDS_BETWEEN_REQUESTS have passed since the last request started."""
    global _last_request_time
    with _rate_lock:
        elapsed = time.monotonic() - _last_request_time
        if elapsed < MIN_SECONDS_BETWEEN_REQUESTS:
            time.sleep(MIN_SECONDS_BETWEEN_REQUESTS - elapsed)
        _last_request_time = time.monotonic()


def fetch(endpoint, params, cache_dir=CACHE_DIR, retries=6):
    """GET an OpenF1 endpoint, using the local cache when possible. Returns a list of dicts.

    Requests are paced (wait_for_rate_limit). If the server still answers
    "too many requests" (429) or a server error, wait and retry, each time
    twice as long (10, 20, 40, ... s: "exponential backoff").
    Older cache files saved as plain .json are still read.
    """
    path = cache_file(endpoint, params, cache_dir)
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as file:
            return json.load(file)
    plain = path.with_suffix("")  # the same name without .gz (the first cache format)
    if plain.exists():
        return json.loads(plain.read_text(encoding="utf-8"))
    wait = 10.0
    for attempt in range(retries):
        wait_for_rate_limit()
        response = requests.get(BASE_URL + endpoint, params=params, timeout=180)
        if response.status_code == 200:
            data = response.json()
            path.parent.mkdir(parents=True, exist_ok=True)
            # write to a temporary file, then rename: if the program is stopped
            # mid-write, no half-written cache file is left behind
            temporary = path.with_name(path.name + f".{threading.get_ident()}.tmp")
            with gzip.open(temporary, "wt", encoding="utf-8") as file:
                json.dump(data, file)
            os.replace(temporary, path)
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


# ---------------------------------------------------------------- car and position data

def driver_streams(session_key, driver_number, span_start, span_end, cache_dir=CACHE_DIR, whole_seconds=True):
    """All car and position samples of one driver between span_start and span_end (2 requests, cached).

    Asking once per driver per session (covering all their kept laps) and
    cutting the laps out locally needs ~40 requests per session instead of
    ~160 (one per lap and stream), which matters with a ~30 requests/minute
    limit. With whole_seconds=True the span is widened to whole seconds, so
    the same span always gives the same cache file.
    Returns {"car": DataFrame, "pos": DataFrame} or None if there's no data.
    """
    if whole_seconds:
        span_start = span_start.floor("s")
        span_end = span_end.ceil("s")
    params = {"session_key": session_key, "driver_number": driver_number,
              "date>": span_start.isoformat(), "date<": span_end.isoformat()}
    car = pd.DataFrame(fetch("car_data", params, cache_dir))
    pos = pd.DataFrame(fetch("location", params, cache_dir))
    if car.empty or pos.empty:
        return None
    car["date"] = to_utc_naive(car["date"])
    pos["date"] = to_utc_naive(pos["date"])
    car = car.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    pos = pos.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    return {"car": car, "pos": pos}


def kept_laps_span(kept, margin_s=5.0):
    """(start, end) covering all of a driver's kept laps, with a margin: one download per driver."""
    starts = kept["LapStartDate"]
    ends = kept["LapStartDate"] + kept["LapTime"]
    return starts.min() - pd.Timedelta(margin_s, unit="s"), ends.max() + pd.Timedelta(margin_s, unit="s")


def slice_lap(streams, lap_start, lap_end, pad_s=2.0):
    """One lap (plus pad_s on each side) cut out of a driver's streams, as arrays.

    Times are seconds from lap_start, the same reference for both streams.
    Brake comes as 0/100 in OpenF1; it becomes True/False here. X, Y are
    converted from decimetres to metres. Returns None if the lap isn't covered.
    """
    pad = pd.Timedelta(pad_s, unit="s")
    car = streams["car"]
    pos = streams["pos"]
    car = car[(car["date"] >= lap_start - pad) & (car["date"] <= lap_end + pad)]
    pos = pos[(pos["date"] >= lap_start - pad) & (pos["date"] <= lap_end + pad)]
    if len(car) < 10 or len(pos) < 10:
        return None
    if car["date"].iloc[0] > lap_start or car["date"].iloc[-1] < lap_end:
        return None  # the lap edges must be bracketed by samples
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


def lap_streams(session_key, driver_number, lap_start, lap_end, pad_s=2.0, cache_dir=CACHE_DIR, streams=None):
    """Car and position data of one lap, as arrays (see slice_lap).

    streams: a driver's streams from driver_streams() (one download for all
    their laps). Without it, just this lap is downloaded (used by the
    validation of 2024 Abu Dhabi, whose cache files are per lap).
    """
    if streams is None:
        pad = pd.Timedelta(pad_s, unit="s")
        streams = driver_streams(session_key, driver_number, lap_start - pad, lap_end + pad,
                                 cache_dir, whole_seconds=False)
        if streams is None:
            return None
    return slice_lap(streams, lap_start, lap_end, pad_s)


# ---------------------------------------------------------------- one lap on the track coordinate

def reference_from_lap(session_key, driver_number, lap_start, lap_time, cache_dir=CACHE_DIR, streams=None):
    """Reference path (track.reference_path_from_xy) from one OpenF1 lap's positions, with exact edges."""
    from apextrace.track import clip_to_lap, reference_path_from_xy

    lap = lap_streams(session_key, driver_number, lap_start, lap_start + lap_time, cache_dir=cache_dir,
                      streams=streams)
    if lap is None:
        return None
    _, pos, _ = clip_to_lap(lap["pos_time_s"], {"x": lap["x_m"], "y": lap["y_m"]}, 0.0, lap["lap_duration_s"])
    return reference_path_from_xy(pos["x"], pos["y"])


def lap_samples_on_track(session_key, driver_number, lap_start, lap_time, reference, cache_dir=CACHE_DIR,
                         streams=None):
    """One OpenF1 lap -> measured car samples on the track coordinate (track.samples_on_track).

    Times are seconds from the lap start. Returns None if OpenF1 has no data
    for the lap.
    """
    from apextrace.track import clip_to_lap, samples_on_track

    lap = lap_streams(session_key, driver_number, lap_start, lap_start + lap_time, cache_dir=cache_dir,
                      streams=streams)
    if lap is None:
        return None
    duration = lap["lap_duration_s"]
    car_times, car, measured = clip_to_lap(
        lap["car_time_s"],
        {"speed": lap["speed_kmh"], "throttle": lap["throttle_pct"], "brake": lap["brake"], "gear": lap["gear"]},
        0.0, duration, step_channels=("brake", "gear"))
    pos_times, pos, _ = clip_to_lap(lap["pos_time_s"], {"x": lap["x_m"], "y": lap["y_m"]}, 0.0, duration)
    return samples_on_track(car_times, car["speed"], car["throttle"], car["brake"], car["gear"], measured,
                            pos_times, pos["x"], pos["y"], reference)


# ---------------------------------------------------------------- downloading a whole session

def download_session(session_key, session_end, workers=3, cache_dir=CACHE_DIR):
    """Download (into the cache) everything one qualifying session needs; returns counts.

    The lap table (laps, stints, race control, drivers), the lap selection,
    then each driver's car and position data over the span of their kept laps
    (2 requests per driver). `workers` drivers at a time: OpenF1 answers in
    3-5 s, so a few requests in flight keep the pace near the allowed ~28 per
    minute (the shared limiter in fetch() still spaces request starts 2.1 s apart).
    Returns {"laps", "kept_laps", "kept_laps_with_data"}.
    """
    from concurrent.futures import ThreadPoolExecutor

    from apextrace.data_loading import select_laps

    laps = lap_table(session_key, session_end, cache_dir)
    counts = {"laps": len(laps), "kept_laps": 0, "kept_laps_with_data": 0}
    jobs = []
    for driver in sorted(laps["Driver"].unique()) if len(laps) else []:
        kept, _ = select_laps(laps[laps["Driver"] == driver])
        if not kept.empty:
            jobs.append(kept)
            counts["kept_laps"] += len(kept)

    def download(kept):
        span_start, span_end = kept_laps_span(kept)
        streams = driver_streams(session_key, int(kept["DriverNumber"].iloc[0]), span_start, span_end, cache_dir)
        if streams is None:
            return 0
        with_data = 0
        for _, lap in kept.iterrows():
            if slice_lap(streams, lap["LapStartDate"], lap["LapStartDate"] + lap["LapTime"]) is not None:
                with_data += 1
        return with_data

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for with_data in pool.map(download, jobs):
            counts["kept_laps_with_data"] += with_data
    return counts

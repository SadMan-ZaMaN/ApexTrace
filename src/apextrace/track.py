"""A lap's samples -> samples on the shared track coordinate s (metres from the start line).

This is the bridge between the data sources (FastF1 objects, or OpenF1 arrays)
and the pure-numpy tools (alignment.py, corners.py, events.py). It is the only
place where a lap's car data and position data are combined, and it never
merges them FastF1's way (which would interpolate everything onto one time
base): car samples keep their own times; only their s is interpolated (see
alignment.py).

Structure:
  - core functions work on plain arrays (any data source):
      reference_path_from_xy, clip_to_lap, samples_on_track
  - thin wrappers for FastF1 laps: reference_path, lap_on_track
  - OpenF1 uses the core functions directly (openf1.py)
"""

import numpy as np

from apextrace.alignment import cumulative_path_length, project_onto_path, track_coordinate_at_times
from apextrace.resampling import integrate_distance


def seconds(timedeltas):
    """A pandas column of timedeltas -> numpy array of seconds."""
    return timedeltas.dt.total_seconds().to_numpy()


# ---------------------------------------------------------------- core (any data source)

def reference_path_from_xy(x_m, y_m, lap_number=None):
    """The reference path from one lap's positions (metres), with s = 0 at the first point.

    The first and last points must be exactly at the lap start and end
    (interpolated "edge" points), so s runs from the timing line to the
    full path length. Returns a dict: x, y, s, length, lap_number.
    """
    x = np.asarray(x_m, dtype=float)
    y = np.asarray(y_m, dtype=float)
    s = cumulative_path_length(x, y)
    return {"x": x, "y": y, "s": s, "length": float(s[-1]), "lap_number": lap_number}


def clip_to_lap(times_s, channels, start_s, end_s, step_channels=()):
    """Keep the samples inside [start_s, end_s] and add one interpolated sample exactly at each edge.

    This does what FastF1's interpolate_edges=True does, for any data source:
    the lap then starts and ends exactly on the timing line.
      - continuous channels (speed, X, Y, ...) are interpolated linearly;
      - step channels (brake, gear: they jump, they don't glide) take the
        value of the last sample before the edge.
    The input must include at least one sample before start_s and one after
    end_s (fetch with a little padding).

    Returns (times, channels_dict, measured) where measured is False for the
    two edge samples (they are not measurements).
    Example: samples at 9.9, 10.1, ..., 92.5 s, lap from 10.0 to 92.4 s ->
    edge samples at exactly 10.0 and 92.4 s, plus all samples in between.
    """
    times_s = np.asarray(times_s, dtype=float)
    inside = (times_s > start_s) & (times_s < end_s)
    new_times = np.concatenate([[start_s], times_s[inside], [end_s]])
    out = {}
    for name, values in channels.items():
        values = np.asarray(values)
        if name in step_channels:
            before_start = max(int(np.searchsorted(times_s, start_s, side="right")) - 1, 0)
            before_end = max(int(np.searchsorted(times_s, end_s, side="right")) - 1, 0)
            out[name] = np.concatenate([[values[before_start]], values[inside], [values[before_end]]])
        else:
            values = values.astype(float)
            edges = np.interp([start_s, end_s], times_s, values)
            out[name] = np.concatenate([[edges[0]], values[inside], [edges[1]]])
    measured = np.ones(len(new_times), dtype=bool)
    measured[0] = False
    measured[-1] = False
    return new_times, out, measured


def samples_on_track(car_times, speed_kmh, throttle_pct, brake, gear, car_measured,
                     pos_times, pos_x_m, pos_y_m, reference, search_m=200.0):
    """One lap's measured car samples, each with its track coordinate s.

    Inputs cover exactly one lap, with edge samples at the lap start and end
    (clip_to_lap). Steps:
      1. d = distance from integrating speed (trapezoid), used as a hint and
         for the fusion inside corner windows;
      2. every position sample is projected onto the reference path, searching
         only +-search_m around where d says it should be (scaled to the
         reference length), so no point snaps to another part of the track;
      3. each car sample's s = interpolation in time between position samples.
    Edge samples (car_measured False) are dropped at the end: not measurements.

    Returns a dict of arrays for the measured car samples (time_s, s_m, d_m,
    speed_kmh, throttle_pct, brake, gear) plus the position samples
    (pos_time_s, pos_s_m, pos_side_m, pos_d_m) and the lap's start/end times.
    """
    car_times = np.asarray(car_times, dtype=float)
    speed = np.asarray(speed_kmh, dtype=float)
    d = integrate_distance(car_times, speed)

    pos_times = np.asarray(pos_times, dtype=float)
    pos_d = np.interp(pos_times, car_times, d)
    expected_s = pos_d * reference["length"] / d[-1]
    pos_s, pos_side = project_onto_path(pos_x_m, pos_y_m, reference["x"], reference["y"], reference["s"],
                                        expected_s=expected_s, search_m=search_m)
    car_s = track_coordinate_at_times(car_times, pos_times, pos_s)

    measured = np.asarray(car_measured, dtype=bool)
    return {
        "time_s": car_times[measured],
        "s_m": car_s[measured],
        "d_m": d[measured],
        "speed_kmh": speed[measured],
        "throttle_pct": np.asarray(throttle_pct, dtype=float)[measured],
        "brake": np.asarray(brake, dtype=bool)[measured],
        "gear": np.asarray(gear, dtype=float)[measured],
        "pos_time_s": pos_times,
        "pos_s_m": pos_s,
        "pos_side_m": pos_side,
        "pos_d_m": pos_d,
        "lap_start_s": float(car_times[0]),
        "lap_end_s": float(car_times[-1]),
        "lap_distance_m": float(d[-1]),
    }


# ---------------------------------------------------------------- FastF1 wrappers

def reference_path(lap):
    """The X/Y path of one FastF1 lap (interpolate_edges=True: s = 0 at the start line).

    X and Y are stored by FastF1 in decimetres; we use metres.
    """
    pos = lap.get_pos_data(interpolate_edges=True)
    return reference_path_from_xy(pos["X"].to_numpy(dtype=float) / 10.0,
                                  pos["Y"].to_numpy(dtype=float) / 10.0,
                                  lap_number=int(lap["LapNumber"]))


def lap_on_track(lap, reference, search_m=200.0):
    """One FastF1 lap's measured car samples on the track coordinate (see samples_on_track).

    FastF1's interpolate_edges=True adds the edge samples; they carry
    Source 'interpolation' and are dropped as not measured.
    """
    car = lap.get_car_data(interpolate_edges=True)
    pos = lap.get_pos_data(interpolate_edges=True)
    return samples_on_track(
        seconds(car["SessionTime"]), car["Speed"].to_numpy(dtype=float),
        car["Throttle"].to_numpy(dtype=float), car["Brake"].to_numpy(dtype=bool),
        car["nGear"].to_numpy(dtype=float), (car["Source"] == "car").to_numpy(),
        seconds(pos["SessionTime"]), pos["X"].to_numpy(dtype=float) / 10.0,
        pos["Y"].to_numpy(dtype=float) / 10.0, reference, search_m=search_m)

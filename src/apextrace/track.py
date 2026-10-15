"""FastF1 lap -> samples on the shared track coordinate s (metres from the start line).

This is the bridge between FastF1 objects and the pure-numpy tools
(alignment.py, corners.py, events.py). It is the only place where a lap's
car data and position data are combined, and it never merges them FastF1's
way (which would interpolate everything onto one time base): car samples
keep their own times; only their s is interpolated (see alignment.py).
"""

import numpy as np

from apextrace.alignment import cumulative_path_length, project_onto_path, track_coordinate_at_times
from apextrace.resampling import integrate_distance


def seconds(timedeltas):
    """A pandas column of timedeltas -> numpy array of seconds."""
    return timedeltas.dt.total_seconds().to_numpy()


def reference_path(lap):
    """The X/Y path of one lap, with the distance s along it (s = 0 at the start line).

    interpolate_edges=True adds a position exactly at the lap start and end,
    so s runs from 0 (the timing line) to the full path length.
    X and Y are stored by FastF1 in decimetres; we use metres.
    Returns a dict: x, y, s (arrays), length (m), lap_number.
    """
    pos = lap.get_pos_data(interpolate_edges=True)
    x = pos["X"].to_numpy(dtype=float) / 10.0
    y = pos["Y"].to_numpy(dtype=float) / 10.0
    s = cumulative_path_length(x, y)
    return {"x": x, "y": y, "s": s, "length": float(s[-1]), "lap_number": int(lap["LapNumber"])}


def lap_on_track(lap, reference, search_m=200.0):
    """One lap's measured car samples, each with its track coordinate s.

    Steps:
      1. car data from the exact lap start to the exact lap end
         (interpolate_edges=True adds one interpolated row at each end);
      2. d = distance from integrating speed (trapezoid), used only as a hint
         and for comparison;
      3. every position sample is projected onto the reference path, with
         the search limited to +-search_m around where d says it should be
         (scaled to the reference length), so no point snaps to another part
         of the track;
      4. each car sample's s = interpolation in time between position samples.
    Interpolated rows (FastF1 Source 'interpolation') are dropped at the end:
    they are not measurements.

    Returns a dict of arrays for the measured car samples (time_s, s_m, d_m,
    speed_kmh, throttle_pct, brake, gear) plus the position samples (pos_time_s,
    pos_s_m, pos_side_m, pos_d_m) and the lap's start/end times.
    """
    car = lap.get_car_data(interpolate_edges=True)
    car_times = seconds(car["SessionTime"])
    speed = car["Speed"].to_numpy(dtype=float)
    d = integrate_distance(car_times, speed)

    pos = lap.get_pos_data(interpolate_edges=True)
    pos_times = seconds(pos["SessionTime"])
    pos_x = pos["X"].to_numpy(dtype=float) / 10.0
    pos_y = pos["Y"].to_numpy(dtype=float) / 10.0
    pos_d = np.interp(pos_times, car_times, d)
    expected_s = pos_d * reference["length"] / d[-1]
    pos_s, pos_side = project_onto_path(pos_x, pos_y, reference["x"], reference["y"], reference["s"],
                                        expected_s=expected_s, search_m=search_m)
    car_s = track_coordinate_at_times(car_times, pos_times, pos_s)

    measured = (car["Source"] == "car").to_numpy()
    return {
        "time_s": car_times[measured],
        "s_m": car_s[measured],
        "d_m": d[measured],
        "speed_kmh": speed[measured],
        "throttle_pct": car["Throttle"].to_numpy(dtype=float)[measured],
        "brake": car["Brake"].to_numpy(dtype=bool)[measured],
        "gear": car["nGear"].to_numpy(dtype=float)[measured],
        "pos_time_s": pos_times,
        "pos_s_m": pos_s,
        "pos_side_m": pos_side,
        "pos_d_m": pos_d,
        "lap_start_s": float(car_times[0]),
        "lap_end_s": float(car_times[-1]),
        "lap_distance_m": float(d[-1]),
    }

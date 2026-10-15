"""One row of numbers per (driver, lap, corner): the corner-level "driving signature".

Every feature uses the estimator chosen by the Phase 2 Monte Carlo
(docs/decisions.md), and every distance is on the fused track coordinate
(Phase 3), relative to the corner marker: negative = before the marker.

Features (PROJECT_CONTEXT §10, adjusted by Phase 2):
  brake_onset_m        where braking starts       speed breakpoint inside the brake off->on interval
  entry_speed_kmh      speed 200 m before marker  linear interpolation
  min_speed_kmh        slowest speed              parabola through the 3 lowest samples
  apex_m               where the slowest point is parabola vertex
  braking_distance_m   apex - brake onset
  mean_decel_ms2       (speed at onset - min speed) / time from onset to apex
                       (replaces peak deceleration, which can't be measured)
  throttle_pickup_m    throttle first reaches 10 % after braking   interpolated crossing
  full_throttle_m      throttle first reaches 99 %                  interpolated crossing
  exit_speed_kmh       speed 150 m after marker   linear interpolation
  corner_time_s        time from -200 m to +150 m
  min_gear             lowest gear in the window

Dropped for now (not validated on synthetic data): coast time, throttle
time constant.
"""

import numpy as np

from apextrace.events import (
    apex_parabola,
    brake_onset_breakpoint,
    crossing_interpolated,
    last_brake_on_time,
)

ENTRY_POINT_M = -200.0
EXIT_POINT_M = 150.0
THROTTLE_PICKUP_PCT = 10.0
FULL_THROTTLE_PCT = 99.0

FEATURES = ["brake_onset_m", "entry_speed_kmh", "min_speed_kmh", "apex_m", "braking_distance_m",
            "mean_decel_ms2", "throttle_pickup_m", "full_throttle_m", "exit_speed_kmh",
            "corner_time_s", "min_gear"]


def corner_features(window, fused_s, corner_s):
    """Compute every feature for one corner window.

    window:   dict of arrays for the samples in the window (time_s, speed_kmh,
              throttle_pct, brake, gear), raw measurements only
    fused_s:  track coordinate of each of those samples (corners.fuse_window_coordinate)
    corner_s: the corner marker's track coordinate

    Times of events are found on the raw samples (events.py), then turned into
    track positions by interpolating fused_s in time. Any feature that can't be
    computed (e.g. no brake transition in the window) is NaN.
    """
    t = window["time_s"]
    speed = window["speed_kmh"]
    throttle = window["throttle_pct"]
    brake = window["brake"]
    relative_s = np.asarray(fused_s, dtype=float) - corner_s

    def position(time_s):
        return float(np.interp(time_s, t, relative_s))

    def time_at(position_m):
        return float(np.interp(position_m, relative_s, t))

    features = {name: float("nan") for name in FEATURES}

    try:
        t_onset = brake_onset_breakpoint(t, speed, brake, within_brake_interval=True)
        features["brake_onset_m"] = position(t_onset)
    except ValueError:
        t_onset = float("nan")

    t_apex, v_min = apex_parabola(t, speed, points=3)
    features["min_speed_kmh"] = v_min
    features["apex_m"] = position(t_apex)

    if np.isfinite(t_onset) and t_apex > t_onset:
        features["braking_distance_m"] = features["apex_m"] - features["brake_onset_m"]
        speed_at_onset = float(np.interp(t_onset, t, speed))
        features["mean_decel_ms2"] = (speed_at_onset - v_min) / 3.6 / (t_apex - t_onset)

    after_braking = last_brake_on_time(t, brake)
    t_pickup = crossing_interpolated(t, throttle, THROTTLE_PICKUP_PCT, after_braking)
    t_full = crossing_interpolated(t, throttle, FULL_THROTTLE_PCT, after_braking)
    if np.isfinite(t_pickup):
        features["throttle_pickup_m"] = position(t_pickup)
    if np.isfinite(t_full):
        features["full_throttle_m"] = position(t_full)

    if relative_s[0] <= ENTRY_POINT_M and relative_s[-1] >= EXIT_POINT_M:
        t_entry = time_at(ENTRY_POINT_M)
        t_exit = time_at(EXIT_POINT_M)
        features["entry_speed_kmh"] = float(np.interp(t_entry, t, speed))
        features["exit_speed_kmh"] = float(np.interp(t_exit, t, speed))
        features["corner_time_s"] = t_exit - t_entry

    features["min_gear"] = float(np.min(window["gear"]))
    return features

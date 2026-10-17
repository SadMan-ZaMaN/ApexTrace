"""Corner windows on the track coordinate: where each corner is, and which samples belong to it.

A corner window runs from WINDOW_BEFORE_M before the corner marker (to
cover the whole braking zone) to WINDOW_AFTER_M after it (to cover the
exit, up to full throttle). Phase 1 checked that for T5, T6 and T9 these
windows lie inside the lap and contain one real braking zone.
"""

import numpy as np

from apextrace.alignment import project_onto_path

WINDOW_BEFORE_M = 300.0
WINDOW_AFTER_M = 200.0
GAP_S = 0.6   # a sample interval longer than this is a feed gap (Phase 1)


def corner_positions(corner_x_dm, corner_y_dm, corner_distance_m, reference):
    """Track coordinate s of each corner marker.

    FastF1's circuit info gives each corner's X/Y (decimetres) and a distance
    along the session's fastest lap. We project the X/Y onto our reference
    path, using that distance as the hint (so a marker can't snap to a
    nearby part of the track). Returns an array of s values (m).
    """
    x = np.asarray(corner_x_dm, dtype=float) / 10.0
    y = np.asarray(corner_y_dm, dtype=float) / 10.0
    s, _ = project_onto_path(x, y, reference["x"], reference["y"], reference["s"],
                             expected_s=np.asarray(corner_distance_m, dtype=float), search_m=250.0)
    return s


MIN_SPEED_DROP_KMH = 50.0     # a real braking zone (Phase 1, check 10)
DIP_HALF_WIDTH_M = 100.0      # a dip must be the slowest point within +-100 m
ENTRY_LOOKBACK_M = 500.0      # entry speed = fastest point in the 500 m before
SLOW_BELOW_KMH = 120.0        # corner types by minimum speed
FAST_FROM_KMH = 200.0


def corner_type(min_speed_kmh):
    """'slow' below 120 km/h, 'fast' from 200 km/h, 'medium' in between."""
    if min_speed_kmh < SLOW_BELOW_KMH:
        return "slow"
    if min_speed_kmh >= FAST_FROM_KMH:
        return "fast"
    return "medium"


def detect_braking_corners(s_m, speed_kmh, lap_length_m, before_m=WINDOW_BEFORE_M, after_m=WINDOW_AFTER_M):
    """Find the braking corners of a lap from its speed trace (used where no corner list exists).

    A sample is a corner's slowest point (its apex on this lap) if:
      1. it is the slowest sample within +-100 m (so a chicane's two dips
         closer than 100 m count as one corner);
      2. the speed dropped by at least 50 km/h from the fastest point in the
         500 m before it (a real braking zone, not a lift);
      3. its window [-before_m, +after_m] fits inside the lap.
    Equal speeds next to each other (a flat bottom) give one corner, not several.

    Returns a list of dicts in track order: corner ("C1", "C2", ...), s_m (the
    apex position, used as the corner reference), min_speed_kmh,
    entry_speed_kmh, speed_drop_kmh, type ("slow" / "medium" / "fast").
    Example (2024 Abu Dhabi): the Turn 6 dip, 324 -> 68 km/h, is a "slow"
    corner with a 256 km/h drop.
    """
    s_m = np.asarray(s_m, dtype=float)
    speed_kmh = np.asarray(speed_kmh, dtype=float)
    corners = []
    last_s = -np.inf
    for i in range(len(s_m)):
        near = np.abs(s_m - s_m[i]) <= DIP_HALF_WIDTH_M
        if speed_kmh[i] > np.min(speed_kmh[near]):
            continue
        if s_m[i] - last_s <= DIP_HALF_WIDTH_M:
            continue  # same dip as the corner just found (flat bottom)
        before = (s_m >= s_m[i] - ENTRY_LOOKBACK_M) & (s_m < s_m[i])
        if not before.any():
            continue
        entry = float(np.max(speed_kmh[before]))
        drop = entry - speed_kmh[i]
        if drop < MIN_SPEED_DROP_KMH:
            continue
        if s_m[i] - before_m < 0 or s_m[i] + after_m > lap_length_m:
            continue
        corners.append({"s_m": float(s_m[i]), "min_speed_kmh": float(speed_kmh[i]), "entry_speed_kmh": entry,
                        "speed_drop_kmh": float(drop), "type": corner_type(float(speed_kmh[i]))})
        last_s = s_m[i]
    for number, corner in enumerate(corners, start=1):
        corner["corner"] = f"C{number}"
    return corners


def window_bounds(corner_s, before_m=WINDOW_BEFORE_M, after_m=WINDOW_AFTER_M):
    """(start, end) of a corner window in track coordinate, e.g. T6 at 2,617 m -> (2,317, 2,817)."""
    return corner_s - before_m, corner_s + after_m


def samples_in_window(lap_samples, start_m, end_m):
    """The lap's car samples whose s lies inside [start_m, end_m], as a dict of arrays.

    One extra sample is kept on each side (if there is one), so that events
    near the window edge can still be bracketed and interpolated.
    """
    s = lap_samples["s_m"]
    inside = np.where((s >= start_m) & (s <= end_m))[0]
    if len(inside) == 0:
        return None
    first = max(inside[0] - 1, 0)
    last = min(inside[-1] + 1, len(s) - 1)
    keys = ["time_s", "s_m", "d_m", "speed_kmh", "throttle_pct", "brake", "gear"]
    return {key: lap_samples[key][first:last + 1] for key in keys}


def has_feed_gap(window_samples, gap_s=GAP_S):
    """True if any interval between consecutive samples in the window is longer than gap_s."""
    times = window_samples["time_s"]
    return bool(np.any(np.diff(times) > gap_s))


def fuse_window_coordinate(lap_samples, window_samples):
    """The track coordinate used for measurements inside one corner window (a complementary filter).

    Two ways to say where the car is, with opposite weaknesses (Phase 3):
      - d (integrated speed): very smooth over short stretches (errors of
        centimetres per sample) but it DRIFTS over a lap, and jumps at feed gaps;
      - s (X/Y projected on the reference path): no drift, but each sample has
        ~3 m of noise along the track (its timestamps jitter).
    Fusion: keep d's shape and pin it to the X/Y frame with ONE offset per
    window, the average of (s - d) over the window's position samples:
        fused(t) = d(t) + mean(s_pos - d_pos)
    Averaging ~30 position samples shrinks the 3 m noise to about
    3 / sqrt(30) = 0.6 m in theory (measured on real data: ~1.2 m, so the
    errors are not fully independent). Inside a window there is no feed gap
    (the window would have been excluded), so d has no jump there.

    Weighted average: the X/Y error looks like timestamp jitter, and a timing
    error of e seconds is a position error of speed x e. So a sample at
    70 km/h is ~4x more precise than one at 300 km/h. Each sample is weighted
    by 1 / speed^2 (inverse-variance weighting: trust each measurement in
    proportion to its precision). On the 2024 Abu Dhabi laps this lowered the
    offset noise from 1.46 m to 1.15 m (decisions.md).

    This is the same idea as fusing GPS (no drift, noisy) with an inertial
    sensor (smooth, drifts): low frequencies from one, high from the other.

    Returns (fused coordinate of each window car sample, offset, number of
    position samples used, half-split difference). The half-split difference
    = offset from the first half of the position samples minus offset from
    the second half: an internal check of how noisy the offset is.
    """
    t0 = window_samples["time_s"][0]
    t1 = window_samples["time_s"][-1]
    pos_times = lap_samples["pos_time_s"]
    inside = (pos_times >= t0) & (pos_times <= t1)
    differences = lap_samples["pos_s_m"][inside] - lap_samples["pos_d_m"][inside]
    # speed (m/s) at each position sample, from the car data; floor at 10 m/s
    speed = np.interp(pos_times[inside], lap_samples["time_s"], lap_samples["speed_kmh"]) / 3.6
    weights = 1.0 / np.maximum(speed, 10.0) ** 2
    count = len(differences)
    offset = float(np.average(differences, weights=weights))
    half = count // 2
    half_difference = float("nan")
    if half >= 2:
        first = np.average(differences[:half], weights=weights[:half])
        second = np.average(differences[half:], weights=weights[half:])
        half_difference = float(first - second)
    return window_samples["d_m"] + offset, offset, count, half_difference

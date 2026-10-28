"""Data-quality measurements: how often samples arrive, how coarse the values are, how far apart laps are.

Why this module exists: every later claim ("Norris brakes 5 m later")
depends on how the data was sampled. Before designing a filter you measure
the noise; before measuring a braking point you measure the sampling. All
functions take plain numbers (seconds, metres), so each can be tested on a
synthetic signal where the right answer is known.
"""

import math

import numpy as np


def sample_intervals(times_s):
    """Time between consecutive samples, in seconds.

    Example: samples at 0.00, 0.24, 0.40, 0.88 s -> intervals 0.24, 0.16, 0.48 s.
    """
    times_s = np.asarray(times_s, dtype=float)
    return np.diff(times_s)


def interval_summary(intervals_s):
    """Summary numbers for a set of sample intervals.

    Two different "rates" come out, and the difference matters when sampling
    is irregular:
      - rate_from_mean_hz = 1 / mean interval = samples per second on average.
        Example: mean 0.265 s -> 3.77 samples per second.
      - rate_from_median_hz = 1 / the typical single interval.
        Example: median 0.24 s -> 4.17 Hz.
    """
    intervals_s = np.asarray(intervals_s, dtype=float)
    mean = float(np.mean(intervals_s))
    median = float(np.median(intervals_s))
    return {
        "count": int(len(intervals_s)),
        "mean_s": mean,
        "median_s": median,
        "p5_s": float(np.percentile(intervals_s, 5)),
        "p95_s": float(np.percentile(intervals_s, 95)),
        "min_s": float(np.min(intervals_s)),
        "max_s": float(np.max(intervals_s)),
        "rate_from_mean_hz": 1.0 / mean,
        "rate_from_median_hz": 1.0 / median,
    }


def event_timing_error_s(intervals_s):
    """Standard deviation of the error when an event is placed at the middle of its sampling interval.

    Why: with an on/off channel (e.g. Brake) we only know that the event
    happened somewhere between the last "off" sample and the first "on"
    sample. If we report the middle of that interval and the true moment is
    equally likely anywhere inside it, the error has standard deviation
    interval / sqrt(12) (the same maths as quantisation noise, step / sqrt(12)).

    With *irregular* intervals there is a catch, the "inspection paradox":
    an event is more likely to land in a long interval than in a short one,
    simply because long intervals cover more time. So each interval is
    weighted by its own length:

        error std = sqrt( sum(T^3) / (12 * sum(T)) )

    Worked examples:
      - all intervals 0.27 s -> 0.27 / sqrt(12) = 0.078 s,
        which at 300 km/h (83.3 m/s) is 6.5 m;
      - half 0.16 s, half 0.48 s (same mean 0.32 s) -> 0.122 s, not the
        0.092 s you would get from the mean interval alone.
    """
    sum_cubes = 0.0
    sum_lengths = 0.0
    for interval in intervals_s:
        sum_cubes += interval ** 3
        sum_lengths += interval
    return math.sqrt(sum_cubes / (12.0 * sum_lengths))


def share_on_grid(values, grid, tolerance):
    """Share of values that lie within `tolerance` of a whole multiple of `grid`.

    Why: if sample intervals are all multiples of 40 ms (give or take a
    millisecond of rounding), the timestamps come from a clock that ticks
    every 40 ms, and "irregular sampling" means "a varying number of ticks".

    Example: [0.159, 0.200, 0.241, 0.300] with grid 0.04 and tolerance 0.002:
    0.159 is 1 ms from 0.16, 0.200 is on 0.20, 0.241 is 1 ms from 0.24, but
    0.300 is 20 ms from 0.28 and 0.32 -> 3 of 4 = 0.75.
    """
    on_grid = 0
    for value in values:
        nearest_multiple = round(value / grid) * grid
        if abs(value - nearest_multiple) <= tolerance:
            on_grid += 1
    return on_grid / len(values)


def find_gaps(times_s, max_interval_s):
    """Intervals longer than max_interval_s: (time of the sample before the gap, gap length).

    Example: samples every 0.24 s with the one at 1.20 s missing ->
    with max_interval_s = 0.40, one gap: (0.96, 0.48).
    """
    gaps = []
    for i in range(1, len(times_s)):
        interval = times_s[i] - times_s[i - 1]
        if interval > max_interval_s:
            gaps.append((float(times_s[i - 1]), float(interval)))
    return gaps


def smallest_step(values, decimals=6):
    """The smallest difference between two distinct values: the channel's resolution.

    Why: a channel stored in whole km/h can't show a change smaller than
    1 km/h. That step size is the quantisation, and it sets a noise floor:
    rounding error with standard deviation step / sqrt(12) (0.29 km/h for
    a 1 km/h step), which differentiation later amplifies.

    Values are rounded to `decimals` first, so floating-point dust
    (e.g. 0.30000000000000004) doesn't count as a tiny step.

    Example: speeds [100, 101, 101, 103] -> distinct 100, 101, 103 -> step 1.

    Limitation: this equals the resolution only if at least two neighbouring
    grid values occur. With few values it can overestimate (values 1.2 and
    1.5 on a 0.1 grid give 0.3). With thousands of real samples per lap,
    neighbours are practically always present.
    """
    distinct = np.unique(np.round(np.asarray(values, dtype=float), decimals))
    if len(distinct) < 2:
        return float("nan")
    return float(np.min(np.diff(distinct)))


def path_length(x, y):
    """Length of the path through the points (x[i], y[i]), joined by straight lines.

    Example: a 10 m x 10 m square, walked corner to corner and back to the
    start -> 40 m.
    """
    total = 0.0
    for i in range(1, len(x)):
        total += math.hypot(x[i] - x[i - 1], y[i] - y[i - 1])
    return total


def distance_to_path(points_x, points_y, path_x, path_y):
    """For each point, the shortest distance to a path made of straight segments.

    Why: if position data were perfect and a driver took exactly the same
    line every lap, every point of lap 2 would lie on the path of lap 1.
    The distances measure the position noise *plus* real differences in the
    line taken, so they are an upper bound on the noise.

    For each point we try every segment of the path: project the point onto
    the segment's line, clamp the projection to the segment's ends, and keep
    the smallest distance.

    Example: path (0, 0) -> (10, 0); the point (4, 3) is 3 m away; the point
    (13, 4) is 5 m from the end (10, 0).

    Note: between samples the path is a straight chord, which cuts inside a
    curve. At radius 200 m and 20 m between samples the chord is up to 0.25 m
    inside the arc, so very small distances are not meaningful.
    """
    path_x = np.asarray(path_x, dtype=float)
    path_y = np.asarray(path_y, dtype=float)
    start_x = path_x[:-1]
    start_y = path_y[:-1]
    seg_x = path_x[1:] - start_x
    seg_y = path_y[1:] - start_y
    seg_len_sq = seg_x ** 2 + seg_y ** 2
    seg_len_sq[seg_len_sq == 0] = 1e-12  # repeated points: avoid dividing by zero

    distances = np.empty(len(points_x))
    for i in range(len(points_x)):
        px = points_x[i]
        py = points_y[i]
        # position along each segment, 0 = start, 1 = end (all segments at once)
        t = ((px - start_x) * seg_x + (py - start_y) * seg_y) / seg_len_sq
        t = np.clip(t, 0.0, 1.0)
        nearest_x = start_x + t * seg_x
        nearest_y = start_y + t * seg_y
        distances[i] = np.min(np.hypot(px - nearest_x, py - nearest_y))
    return distances


def start_offset(s_m, d_m, window_m=300.0, max_abs_m=50.0):
    """The lap's position offset, measured where the true position is known best: just after the line.

    WHY: two measurements say how far along the lap the car is. Projected
    position s (X/Y snapped onto the track) is right on average but scatters
    by ~3 m per sample, and might carry an offset of its own for a whole lap
    (e.g. if the position stream's clock is a little off). Integrated speed d
    is smooth and starts at exactly 0 on the line, so in the first few hundred
    metres it has had no time to drift (0.25 % drift over 300 m is under 1 m).
    There, s - d is the position's own error: its median over the window
    (about 15 samples at race speed) averages the scatter down to about 1 m,
    so a lap-specific offset shows up as a clearly non-zero median.

    Known small bias: inside the window, integrated speed has drifted by
    drift x (distance so far), so the estimate is off by about
    -drift x (window_m / 2): at the feed's ~0.25 % that is -0.4 m, under the
    ~1 m noise of one lap's estimate (tests check both numbers).

    Samples whose difference exceeds max_abs_m are projection glitches (for
    example a point near the line snapped onto the END of the track), not an
    offset, and are ignored. Returns NaN with fewer than 3 usable samples.

    Example: samples at d = 20, 45, 70 m with s = 25.5, 49.0, 76.2 m give
    s - d = 5.5, 4.0, 6.2 m -> offset +5.5 m: the position puts the car
    5.5 m further along than integrated speed does.
    """
    differences = []
    for s, d in zip(s_m, d_m):
        if d <= window_m:
            difference = float(s) - float(d)
            if abs(difference) <= max_abs_m:
                differences.append(difference)
    if len(differences) < 3:
        return float("nan")
    return float(np.median(differences))

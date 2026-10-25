"""Putting every lap on ONE distance axis (the "track coordinate"), and checking how well it worked.

Why: to compare braking points between laps, "metre 2,520" must mean the same
spot on the track in every lap. Distance from integrating speed drifts
(Phase 1: up to 9 m on a qualifying lap with a feed gap, 19 m in FP2), and a
feed gap *before* a corner shifts the whole rest of the lap.

Two tools:
  1. Projection onto a reference path (the main method). Take the X/Y path of
     one reference lap, measure distance along it (s = 0 at the start line).
     Every position sample of every other lap is projected onto that path:
     its s is "how far along the track" it is. That doesn't depend on
     integrating anything, so a gap earlier in the lap can't shift it.
     Car samples (speed, brake...) come at different moments than position
     samples, so their s is interpolated in time between position samples.
  2. Cross-correlation (a check). Slide one lap's speed-vs-distance trace
     over the reference's, and find the shift where they match best. The
     peak is refined between grid points with a parabola, the same trick as
     Consonance's pitch detector on its autocorrelation peak.

The trap (Phase 3): alignment must not absorb the very difference
we want to measure. If we shifted each lap so its *braking zone* matched the
reference, a driver who brakes 5 m later would be "corrected" by 5 m. The
projection method uses only positions, never the speed trace, so it can't do
that; cross-correlation is used only over the whole lap (where one corner is
a small part), as a diagnostic.
"""

import numpy as np


def cumulative_path_length(x, y):
    """Distance along a path of straight segments, at each point (starts at 0).

    Example: points (0, 0), (3, 4), (3, 10) -> 0, 5, 11.
    """
    s = np.zeros(len(x))
    for i in range(1, len(x)):
        s[i] = s[i - 1] + np.hypot(x[i] - x[i - 1], y[i] - y[i - 1])
    return s


def project_onto_path(points_x, points_y, path_x, path_y, path_s, expected_s=None, search_m=200.0):
    """Track coordinate s (and sideways distance) of each point, by projecting onto the path.

    For each point: try the path's segments, find the closest point on each
    segment (projection, clamped to the segment's ends), keep the closest one,
    and read off s there: s of the segment start + fraction x segment length.

    expected_s (optional, one value per point): only segments within
    search_m of the expected s are tried. This stops a point from snapping
    to a different part of the track that happens to pass nearby.

    Returns (s, sideways_distance), both in metres.
    Example: path (0, 0) -> (10, 0) with s = [0, 10]; the point (4, 3)
    projects to s = 4, sideways distance 3.
    """
    path_x = np.asarray(path_x, dtype=float)
    path_y = np.asarray(path_y, dtype=float)
    path_s = np.asarray(path_s, dtype=float)
    start_x = path_x[:-1]
    start_y = path_y[:-1]
    seg_x = path_x[1:] - start_x
    seg_y = path_y[1:] - start_y
    seg_len_sq = seg_x ** 2 + seg_y ** 2
    seg_len_sq[seg_len_sq == 0] = 1e-12

    s_out = np.empty(len(points_x))
    side_out = np.empty(len(points_x))
    for i in range(len(points_x)):
        px = points_x[i]
        py = points_y[i]
        candidates = np.arange(len(seg_x))
        if expected_s is not None:
            near = np.abs(path_s[:-1] - expected_s[i]) <= search_m
            if near.any():
                candidates = np.where(near)[0]
        t = ((px - start_x[candidates]) * seg_x[candidates]
             + (py - start_y[candidates]) * seg_y[candidates]) / seg_len_sq[candidates]
        t = np.clip(t, 0.0, 1.0)
        nearest_x = start_x[candidates] + t * seg_x[candidates]
        nearest_y = start_y[candidates] + t * seg_y[candidates]
        distances = np.hypot(px - nearest_x, py - nearest_y)
        best = int(np.argmin(distances))
        segment = candidates[best]
        s_out[i] = path_s[segment] + t[best] * (path_s[segment + 1] - path_s[segment])
        side_out[i] = distances[best]
    return s_out, side_out


def track_coordinate_at_times(sample_times_s, position_times_s, position_s):
    """s of each car sample, interpolated in time between position samples.

    Car data and position data arrive at different moments (Phase 1), so a
    car sample's place on the track is a straight-line interpolation between
    the two position samples around it.
    Example: positions at 10.0 s (s = 1000) and 10.2 s (s = 1016); a car
    sample at 10.05 s -> s = 1004.
    """
    return np.interp(sample_times_s, position_times_s, position_s)


def normalised_cross_correlation(reference, signal, max_lag):
    """Correlation between `reference` and `signal` shifted by each lag in [-max_lag, max_lag] samples.

    Both are sequences on the same uniform grid. For each lag, the overlapping
    parts are compared after removing their means and dividing by their
    spread, so the value is between -1 and 1 (1 = identical shape). This is
    the Pearson correlation of the overlap, the "normalised" cross-correlation.

    A positive lag k means `signal` is the reference delayed by k samples:
    signal[i + k] matches reference[i].
    Returns (lags, correlations).
    """
    reference = np.asarray(reference, dtype=float)
    signal = np.asarray(signal, dtype=float)
    lags = np.arange(-max_lag, max_lag + 1)
    correlations = np.empty(len(lags))
    for j, lag in enumerate(lags):
        if lag >= 0:
            a = reference[:len(reference) - lag]
            b = signal[lag:lag + len(a)]
        else:
            a = reference[-lag:]
            b = signal[:len(a)]
        n = min(len(a), len(b))
        a = a[:n] - np.mean(a[:n])
        b = b[:n] - np.mean(b[:n])
        denominator = np.sqrt(np.sum(a * a) * np.sum(b * b))
        correlations[j] = np.sum(a * b) / denominator if denominator > 0 else 0.0
    return lags, correlations


def parabolic_peak(lags, values):
    """Refine the highest point of a sampled curve with a parabola through it and its neighbours.

    For three equally spaced points (y_-1, y_0, y_+1) around the peak, the
    vertex of the parabola through them is at
        offset = 0.5 * (y_-1 - y_+1) / (y_-1 - 2 y_0 + y_+1)
    grid steps from the middle point. Returns (peak lag, peak value).
    Example: values 0.80, 1.00, 0.90 at lags -1, 0, 1 -> peak at lag +0.167.
    """
    k = int(np.argmax(values))
    if k == 0 or k == len(values) - 1:
        return float(lags[k]), float(values[k])
    y_minus, y_0, y_plus = values[k - 1], values[k], values[k + 1]
    denominator = y_minus - 2 * y_0 + y_plus
    if denominator == 0:
        return float(lags[k]), float(y_0)
    offset = 0.5 * (y_minus - y_plus) / denominator
    step = lags[k + 1] - lags[k]
    peak_value = y_0 - 0.25 * (y_minus - y_plus) * offset
    return float(lags[k] + offset * step), float(peak_value)


def lag_metres(reference_values, values, grid_step_m, max_lag_m):
    """Shift (m) of `values` relative to `reference_values` on the same distance grid, plus peak correlation.

    Positive = `values` happen further down the road than in the reference
    (it would have to be moved back by that many metres to match).
    Example: a speed trace that is the reference moved 7.3 m later -> +7.3.
    """
    max_lag = int(round(max_lag_m / grid_step_m))
    lags, correlations = normalised_cross_correlation(reference_values, values, max_lag)
    peak_lag, peak_value = parabolic_peak(lags, correlations)
    return peak_lag * grid_step_m, peak_value

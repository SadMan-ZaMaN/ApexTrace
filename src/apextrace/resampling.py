"""Irregular samples -> uniform grids (in time or distance), and time -> distance.

Why: most filters (moving average, Butterworth, filtfilt) and the FFT assume
samples equally spaced. The feed is not (0.16-0.56 s between samples). So we
resample *once*, by linear interpolation, onto a uniform grid, and remember
which grid points sit inside a feed gap (where the "data" is pure guess).

Signals-and-systems view: linear interpolation = convolving the samples with
a triangle (the "tent" kernel), which is a crude low-pass filter. It creates
no new information: a grid point between two samples is only a straight-line
guess between them. Ideal band-limited reconstruction would use a sinc kernel,
but with irregular samples and sharp braking events, a tent is safer (it
never overshoots).
"""

import numpy as np


def to_uniform_grid(times_s, values, step_s, max_interval_s=0.6):
    """Linearly interpolate irregular samples onto a uniform time grid.

    Returns (grid_times, grid_values, in_gap), where in_gap[i] is True when
    grid point i lies inside a sample interval longer than max_interval_s
    (a feed gap: the value there is a guess across up to ~1.4 s).

    Example: samples at 0.0 and 0.48 s with values 300 and 290, step 0.04 s
    -> 13 grid points from 0.00 to 0.48, values 300, 299.17, ..., 290.
    """
    times_s = np.asarray(times_s, dtype=float)
    values = np.asarray(values, dtype=float)
    count = int(np.floor((times_s[-1] - times_s[0]) / step_s + 1e-9)) + 1
    grid = times_s[0] + step_s * np.arange(count)
    grid_values = np.interp(grid, times_s, values)

    in_gap = np.zeros(count, dtype=bool)
    for i in range(1, len(times_s)):
        if times_s[i] - times_s[i - 1] > max_interval_s:
            inside = (grid > times_s[i - 1]) & (grid < times_s[i])
            in_gap[inside] = True
    return grid, grid_values, in_gap


def integrate_distance(times_s, speed_kmh):
    """Distance travelled (m) at each sample, by the trapezoidal rule, starting at 0.

    Trapezoid: between two samples the car covers (average of the two
    speeds) x (time between them). FastF1's add_distance() instead uses the
    speed at the *end* of each interval (a rectangle), which over-counts
    while accelerating and under-counts while braking.
    Example: 0 -> 1 s at 100 then 110 km/h: (27.78 + 30.56) / 2 * 1 = 29.17 m.
    """
    times_s = np.asarray(times_s, dtype=float)
    speed_ms = np.asarray(speed_kmh, dtype=float) / 3.6
    distance = np.zeros(len(times_s))
    for i in range(1, len(times_s)):
        dt = times_s[i] - times_s[i - 1]
        distance[i] = distance[i - 1] + 0.5 * (speed_ms[i] + speed_ms[i - 1]) * dt
    return distance


def resample_by_distance(distance_m, values, step_m, start_m=None, end_m=None):
    """Linearly interpolate values onto a uniform distance grid (e.g. every 1 m).

    Used to compare laps point by point along the track. Distances must be
    increasing (they are: a car doesn't drive backwards).
    Returns (grid_distance, grid_values).
    """
    distance_m = np.asarray(distance_m, dtype=float)
    values = np.asarray(values, dtype=float)
    if start_m is None:
        start_m = distance_m[0]
    if end_m is None:
        end_m = distance_m[-1]
    count = int(np.floor((end_m - start_m) / step_m + 1e-9)) + 1
    grid = start_m + step_m * np.arange(count)
    return grid, np.interp(grid, distance_m, values)

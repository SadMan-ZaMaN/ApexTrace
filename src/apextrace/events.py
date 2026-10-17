"""Locating events BETWEEN samples: brake onset, apex (minimum speed), throttle pickup.

Why this is the DSP heart of the project: at 300 km/h there are 13-47 m
between samples, but the differences between teammates may be a few metres.
A "naive" estimator just takes the nearest sample, so its error is up to a
whole sample interval. A "refined" estimator uses the shape of the signal
around the event to place it between samples.

Each function takes the samples of ONE corner (times in seconds, values)
and returns a time. Converting that time to a distance is done separately
(time -> distance mapping), so timing errors and distance-axis errors can be
measured separately.

Naive vs refined, in one line each:
  brake onset    first "on" sample  |  middle of the off->on interval  |  speed-curve breakpoint
  apex           lowest sample      |  vertex of a parabola through the lowest samples
  throttle       first sample >= threshold  |  straight-line interpolation of the crossing
"""

import numpy as np

from apextrace.filters import butterworth_lowpass, derivative, zero_phase_filter
from apextrace.resampling import to_uniform_grid


# ---------------------------------------------------------------- brake onset

def first_brake_index(brake, before_index=None):
    """Index of the start of braking: an "on" sample that follows an "off" sample.

    Without before_index: the first such transition in the samples.
    With before_index: the LAST transition at or before that index, i.e. the
    braking that leads into a given apex. This matters when a corner window
    contains two braking zones (a chicane, or the previous corner).
    """
    end = len(brake) if before_index is None else min(before_index + 1, len(brake))
    last = None
    for i in range(1, end):
        if brake[i] and not brake[i - 1]:
            if before_index is None:
                return i
            last = i
    if last is None:
        raise ValueError("no off -> on transition of the brake channel in these samples")
    return last


def index_at_or_before(times_s, time_s):
    """Index of the last sample at or before time_s (None = no limit)."""
    if time_s is None:
        return None
    return int(np.searchsorted(np.asarray(times_s, dtype=float), time_s, side="right")) - 1


def brake_onset_first_on(times_s, brake, before_time_s=None):
    """NAIVE: the time of the first sample where the brake is on.

    Always late: the real onset was somewhere in the interval before this
    sample. Expected bias: about half an interval, weighted towards long
    intervals (~0.15 s = ~13 m at 300 km/h).
    before_time_s: use the last braking that starts at or before this time.
    """
    return float(times_s[first_brake_index(brake, index_at_or_before(times_s, before_time_s))])


def brake_onset_midpoint(times_s, brake, before_time_s=None):
    """The middle of the interval between the last "off" sample and the first "on" sample.

    If the true onset is equally likely anywhere in that interval, the middle
    is unbiased and the error spread is interval / sqrt(12) (see
    quality.event_timing_error_s).
    Example: off at 10.00 s, on at 10.32 s -> 10.16 s, error std 0.092 s.
    """
    i = first_brake_index(brake, index_at_or_before(times_s, before_time_s))
    return float(0.5 * (times_s[i - 1] + times_s[i]))


def brake_release_index(brake, onset_index):
    """Index of the last "on" sample of the braking run that starts at onset_index."""
    i = onset_index
    while i + 1 < len(brake) and brake[i + 1]:
        i += 1
    return i


def braking_event(brake, throttle_pct, apex_index, throttle_threshold=10.0):
    """(onset index, release index) of the braking event that leads into the apex.

    One braking event can show up as several "on" runs: a driver may ease off
    the brake for a moment (1-4 samples, 0.4-1.3 s, in Norris's 2024 Abu Dhabi
    FP2 long runs) and press again. Physically it is still one braking event
    as long as the throttle isn't opened in between. So:
      - start from the last "on" sample at or before the apex;
      - walk back to the start of its run; if the "off" gap before it never
        reaches throttle_threshold, the previous run belongs to the same event:
        keep walking back;
      - the same forwards for the release (the end of the event).
    Two different braking zones always have the throttle opened between them
    (even the two halves of a chicane), so they are never merged.
    Raises ValueError if the brake is never on before the apex.
    """
    brake = np.asarray(brake, dtype=bool)
    throttle_pct = np.asarray(throttle_pct, dtype=float)
    on_before_apex = np.where(brake[:apex_index + 1])[0]
    if len(on_before_apex) == 0:
        raise ValueError("the brake is never on before the apex")

    # backwards: the onset
    i = int(on_before_apex[-1])
    while True:
        while i - 1 >= 0 and brake[i - 1]:
            i -= 1
        previous_on = i - 1
        while previous_on >= 0 and not brake[previous_on]:
            previous_on -= 1
        if previous_on < 0:
            break
        gap = throttle_pct[previous_on + 1:i]
        if np.max(gap) >= throttle_threshold:
            break
        i = previous_on
    onset = i

    # forwards: the release
    j = onset
    while True:
        while j + 1 < len(brake) and brake[j + 1]:
            j += 1
        next_on = j + 1
        while next_on < len(brake) and not brake[next_on]:
            next_on += 1
        if next_on >= len(brake):
            break
        gap = throttle_pct[j + 1:next_on]
        if np.max(gap) >= throttle_threshold:
            break
        j = next_on
    return onset, j


def brake_onset_breakpoint(times_s, speed_kmh, brake, before_s=1.5, after_s=0.5,
                           step_s=0.002, within_brake_interval=False, before_time_s=None, onset_index=None):
    """REFINED: where the speed curve bends from "flat" to "falling fast".

    Model, on the samples from before_s before to after_s after the first
    brake-on sample: two straight lines joined at a breakpoint tb,
        speed(t) = c + s1 * min(t - tb, 0) + s2 * max(t - tb, 0)
    (s1 = slope on the straight, s2 = slope under braking). For every
    candidate tb on a fine grid we fit c, s1, s2 by least squares and keep
    the tb with the smallest squared error. tb is a continuous number,
    not tied to a sample.

    within_brake_interval=True only allows tb inside the off->on interval
    of the brake channel (uses both channels: the brake says *which*
    interval, the speed curve says *where* inside it).

    Known bias: braking force builds up over a short ramp (~0.05-0.25 s), so
    the fitted corner sits ~half a ramp after the true onset. The Monte Carlo
    (experiments/03) measures this.
    """
    times_s = np.asarray(times_s, dtype=float)
    speed_kmh = np.asarray(speed_kmh, dtype=float)
    i_on = onset_index if onset_index is not None else first_brake_index(brake, index_at_or_before(times_s, before_time_s))
    t_on = times_s[i_on]
    window = (times_s >= t_on - before_s) & (times_s <= t_on + after_s)
    t = times_s[window]
    v = speed_kmh[window]

    if within_brake_interval:
        low, high = times_s[i_on - 1], t_on
    else:
        low, high = t[1], t[-2]   # keep at least one sample on each side

    best_tb = None
    best_error = np.inf
    for tb in np.arange(low, high + step_s / 2, step_s):
        design = np.column_stack([np.ones(len(t)), np.minimum(t - tb, 0.0), np.maximum(t - tb, 0.0)])
        coefficients, _, _, _ = np.linalg.lstsq(design, v, rcond=None)
        residual = v - design @ coefficients
        error = float(residual @ residual)
        braking_slope = coefficients[2]
        if braking_slope < 0 and error < best_error:
            best_error = error
            best_tb = tb
    if best_tb is None:
        return float(0.5 * (times_s[i_on - 1] + times_s[i_on]))  # middle of the off->on interval
    return float(best_tb)


# ---------------------------------------------------------------- apex (minimum speed)

def apex_lowest_sample(times_s, speed_kmh):
    """NAIVE: (time, speed) of the lowest sample.

    The speed is always too high (a sample rarely lands exactly on the
    minimum) and the time is off by up to half an interval.
    """
    i = int(np.argmin(speed_kmh))
    return float(times_s[i]), float(speed_kmh[i])


def apex_parabola(times_s, speed_kmh, points=3):
    """REFINED: the vertex of a parabola fitted to the lowest samples.

    points=3: the exact parabola through the lowest sample and its two
    neighbours (the same trick Consonance used to refine an autocorrelation
    peak, here with uneven spacing). points=5: a least-squares parabola
    through 5 samples, less sensitive to 1 km/h rounding.
    The vertex time is kept inside the fitted samples' time range; if the
    parabola opens downwards (no minimum), the lowest sample is returned.
    Example: samples (0.0 s, 70), (0.24 s, 66), (0.52 s, 69) -> vertex
    near 0.25 s at about 65.9 km/h.
    """
    times_s = np.asarray(times_s, dtype=float)
    speed_kmh = np.asarray(speed_kmh, dtype=float)
    i = int(np.argmin(speed_kmh))
    half = points // 2
    # near the start or end there may not be enough neighbours: use fewer
    while half >= 1 and (i - half < 0 or i + half >= len(times_s)):
        half -= 1
    if half < 1:
        return apex_lowest_sample(times_s, speed_kmh)
    t = times_s[i - half:i + half + 1]
    v = speed_kmh[i - half:i + half + 1]
    # fit around t[0] for numerical stability: v = a (t-t0)^2 + b (t-t0) + c
    a, b, c = np.polyfit(t - t[0], v, 2)
    if a <= 0:
        return apex_lowest_sample(times_s, speed_kmh)
    vertex = -b / (2 * a)
    vertex = min(max(vertex, 0.0), t[-1] - t[0])
    return float(t[0] + vertex), float(a * vertex ** 2 + b * vertex + c)


# ---------------------------------------------------------------- threshold crossings (throttle)

def crossing_first_sample(times_s, values, threshold, start_s, end_s=float("inf")):
    """NAIVE: time of the first sample at or above threshold, between start_s and end_s."""
    for i in range(len(times_s)):
        if times_s[i] > end_s:
            break
        if times_s[i] >= start_s and values[i] >= threshold:
            return float(times_s[i])
    return float("nan")


def crossing_interpolated(times_s, values, threshold, start_s, end_s=float("inf")):
    """REFINED: where a straight line between the last sample below and the first at/above crosses.

    Only crossings between start_s and end_s count (end_s: e.g. the next
    braking, so a crossing after the NEXT corner is never taken).
    Example: throttle 4 % at 20.00 s and 34 % at 20.30 s, threshold 10 % ->
    20.00 + 0.30 * (10 - 4) / (34 - 4) = 20.06 s.
    """
    for i in range(1, len(times_s)):
        if times_s[i] > end_s:
            break
        if times_s[i] < start_s:
            continue
        if values[i] >= threshold and values[i - 1] < threshold:
            fraction = (threshold - values[i - 1]) / (values[i] - values[i - 1])
            return float(times_s[i - 1] + fraction * (times_s[i] - times_s[i - 1]))
    return float("nan")


def last_brake_on_time(times_s, brake):
    """Time of the last brake-on sample: throttle pickup is searched after it."""
    on = np.where(np.asarray(brake))[0]
    return float(times_s[on[-1]]) if len(on) else float(times_s[0])


# ---------------------------------------------------------------- deceleration

def peak_decel_naive(times_s, speed_kmh):
    """NAIVE: the largest speed drop between two consecutive samples, in m/s^2.

    Each value is an average over one interval (0.16-0.56 s), so short
    peaks are smoothed away, and the 1 km/h rounding adds noise.
    """
    speed_ms = np.asarray(speed_kmh, dtype=float) / 3.6
    rates = -np.diff(speed_ms) / np.diff(np.asarray(times_s, dtype=float))
    return float(np.max(rates))


def peak_decel_smoothed(times_s, speed_kmh, cutoff_hz=1.0, grid_step_s=0.04):
    """REFINED: resample to a 40 ms grid, zero-phase low-pass, differentiate, take the peak.

    Zero-phase so the peak stays in place; the low-pass removes the 1 km/h
    rounding steps before differentiating (differentiation amplifies them).
    The cutoff trades noise against how sharp a peak can be.
    """
    grid, speed, _ = to_uniform_grid(times_s, np.asarray(speed_kmh, dtype=float) / 3.6, grid_step_s)
    b, a = butterworth_lowpass(cutoff_hz, 1.0 / grid_step_s, order=2)
    smooth = zero_phase_filter(b, a, speed)
    return float(np.max(-derivative(smooth, grid_step_s)))

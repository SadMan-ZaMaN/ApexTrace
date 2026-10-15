"""Tests for quality.py on synthetic signals where the right answer is known."""

import math

import numpy as np
import pytest

from apextrace.quality import (
    distance_to_path,
    event_timing_error_s,
    find_gaps,
    interval_summary,
    path_length,
    sample_intervals,
    share_on_grid,
    smallest_step,
)


def test_sample_intervals_of_known_times():
    intervals = sample_intervals([0.00, 0.24, 0.40, 0.88])
    assert intervals == pytest.approx([0.24, 0.16, 0.48])


def test_interval_summary_mean_and_median_rates_differ_for_irregular_sampling():
    # The real car-data intervals sit on a 40 ms grid between 0.16 and 0.48 s
    intervals = [0.16, 0.20, 0.24, 0.24, 0.48]
    summary = interval_summary(intervals)
    assert summary["median_s"] == pytest.approx(0.24)
    assert summary["mean_s"] == pytest.approx(0.264)
    assert summary["rate_from_median_hz"] == pytest.approx(1 / 0.24)
    assert summary["rate_from_mean_hz"] == pytest.approx(1 / 0.264)
    assert summary["max_s"] == pytest.approx(0.48)


def test_event_timing_error_for_regular_sampling_is_interval_over_sqrt12():
    # 0.27 s / sqrt(12) = 0.078 s, i.e. 6.5 m at 300 km/h
    error = event_timing_error_s([0.27] * 100)
    assert error == pytest.approx(0.27 / math.sqrt(12))
    assert error * (300 / 3.6) == pytest.approx(6.5, abs=0.05)


def test_event_timing_error_matches_a_monte_carlo_experiment():
    """Drop random events onto irregular samples and measure the real error.

    Each event is reported at the middle of the interval it falls in. With
    intervals of 0.16 s and 0.48 s, the measured spread must match the
    length-weighted formula (0.122 s), not the naive mean/sqrt(12) (0.092 s).
    """
    rng = np.random.default_rng(seed=1)
    intervals = rng.choice([0.16, 0.48], size=5000)
    sample_times = np.concatenate([[0.0], np.cumsum(intervals)])

    errors = []
    for _ in range(20000):
        true_time = rng.uniform(sample_times[0], sample_times[-1])
        after = np.searchsorted(sample_times, true_time)  # first sample after the event
        middle = 0.5 * (sample_times[after - 1] + sample_times[after])
        errors.append(true_time - middle)
    measured = np.std(errors)

    predicted = event_timing_error_s(intervals)
    naive = np.mean(intervals) / math.sqrt(12)
    assert measured == pytest.approx(predicted, rel=0.03)
    assert abs(measured - naive) > 0.02  # the naive formula is clearly wrong here


def test_share_on_grid_counts_values_near_multiples_of_the_grid():
    # 0.159 and 0.241 are 1 ms off the 40 ms grid, 0.300 is 20 ms off
    assert share_on_grid([0.159, 0.200, 0.241, 0.300], grid=0.04, tolerance=0.002) == 0.75
    # a tighter tolerance rejects the 1 ms rounding too
    assert share_on_grid([0.159, 0.200, 0.241, 0.300], grid=0.04, tolerance=0.0005) == 0.25


def test_find_gaps_finds_one_missing_sample():
    times = [round(0.24 * i, 2) for i in range(10)]
    times.remove(1.20)  # drop the 6th sample
    gaps = find_gaps(times, max_interval_s=0.40)
    assert len(gaps) == 1
    assert gaps[0][0] == pytest.approx(0.96)
    assert gaps[0][1] == pytest.approx(0.48)


def test_smallest_step_finds_the_resolution():
    assert smallest_step([100, 101, 101, 103, 250]) == pytest.approx(1.0)
    assert smallest_step([0.0, 0.5, 1.5, 3.0]) == pytest.approx(0.5)
    # X/Y positions come in decimetres; in metres the step is 0.1, and
    # floating-point dust (1.3 - 1.2 = 0.10000000000000009) must not matter
    positions_m = [n * 0.1 for n in [12, 13, 15, 3, 7]]
    assert smallest_step(positions_m) == pytest.approx(0.1)
    # 0.1 * 3 is stored as 0.30000000000000004: the same value as 0.3, not a new one
    assert smallest_step([0.3, 0.1 * 3, 0.4]) == pytest.approx(0.1)


def test_smallest_step_overestimates_when_neighbours_are_missing():
    # Known limitation: on a 0.1 m grid, if no two values are neighbours,
    # the smallest gap seen (0.3 m) is larger than the resolution.
    positions_m = [n * 0.1 for n in [12, 15, 3, 7]]
    assert smallest_step(positions_m) == pytest.approx(0.3)


def test_path_length_of_a_square():
    x = [0, 10, 10, 0, 0]
    y = [0, 0, 10, 10, 0]
    assert path_length(x, y) == pytest.approx(40.0)


def test_distance_to_path_straight_segment():
    distances = distance_to_path([4, 13, 6], [3, 4, 0], [0, 10], [0, 0])
    assert distances[0] == pytest.approx(3.0)   # beside the segment
    assert distances[1] == pytest.approx(5.0)   # past the end: distance to (10, 0)
    assert distances[2] == pytest.approx(0.0)   # on the path


def test_distance_to_path_on_a_realistic_corner():
    """Two laps through a 100 m-radius corner, 1.5 m apart, sampled sparsely.

    Lap A's path is sampled every ~20 m (300 km/h at ~4 Hz). Lap B runs on a
    circle 1.5 m further out. The answer must be 1.5 m, plus at most the
    chord error R(1 - cos(half angle)) = 0.5 m, since lap A's path is made of
    straight chords that cut inside the arc.
    """
    radius = 100.0
    angles_a = np.arange(0, math.pi / 2, 0.2)  # 0.2 rad x 100 m = 20 m apart
    path_x = radius * np.cos(angles_a)
    path_y = radius * np.sin(angles_a)

    angles_b = np.linspace(0.1, 1.3, 25)  # stay inside lap A's covered arc
    points_x = (radius + 1.5) * np.cos(angles_b)
    points_y = (radius + 1.5) * np.sin(angles_b)

    distances = distance_to_path(points_x, points_y, path_x, path_y)
    chord_error = radius * (1 - math.cos(0.1))
    assert np.all(distances >= 1.5 - 1e-9)
    assert np.all(distances <= 1.5 + chord_error + 1e-9)

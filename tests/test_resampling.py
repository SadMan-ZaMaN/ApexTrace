"""Tests for resampling.py: uniform grids, gap masks, time -> distance."""

import numpy as np
import pytest

from apextrace.resampling import integrate_distance, resample_by_distance, to_uniform_grid


def test_uniform_grid_interpolates_linearly():
    grid, values, in_gap = to_uniform_grid([0.0, 0.48], [300.0, 290.0], step_s=0.04)
    assert len(grid) == 13
    assert grid[-1] == pytest.approx(0.48)
    assert values[1] == pytest.approx(300 - 10 / 12)
    assert not in_gap.any()


def test_uniform_grid_marks_points_inside_a_feed_gap():
    # a 1.2 s hole between 1.0 and 2.2 s
    times = [0.0, 0.25, 0.5, 0.75, 1.0, 2.2, 2.45]
    grid, _, in_gap = to_uniform_grid(times, np.arange(len(times)), step_s=0.05, max_interval_s=0.6)
    inside = (grid > 1.0) & (grid < 2.2)
    assert np.array_equal(in_gap, inside)
    assert in_gap.sum() == 23


def test_integrate_distance_trapezoid():
    distance = integrate_distance([0.0, 1.0], [100.0, 110.0])
    assert distance[-1] == pytest.approx((100 + 110) / 2 / 3.6)


def test_integrate_distance_constant_speed_irregular_times():
    times = np.cumsum([0.0, 0.16, 0.48, 0.24, 0.32])
    distance = integrate_distance(times, np.full(len(times), 252.0))  # 70 m/s
    assert distance[-1] == pytest.approx(70.0 * times[-1])


def test_resample_by_distance_every_metre():
    grid, values = resample_by_distance([0.0, 10.0], [100.0, 120.0], step_m=1.0)
    assert len(grid) == 11
    assert values[5] == pytest.approx(110.0)

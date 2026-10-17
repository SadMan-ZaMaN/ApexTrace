"""Tests for alignment.py: projection onto a path, and cross-correlation lags with sub-grid accuracy."""

import numpy as np
import pytest

from apextrace.alignment import (
    cumulative_path_length,
    lag_metres,
    parabolic_peak,
    project_onto_path,
    track_coordinate_at_times,
)
from apextrace.resampling import resample_by_distance
from apextrace.synthetic import make_true_corner, random_corner_params


def test_fusion_removes_drift_and_averages_position_noise():
    """Integrated distance drifts by +12 m; X/Y positions have 3 m noise. Fused error must be ~0.6 m."""
    from apextrace.corners import fuse_window_coordinate

    rng = np.random.default_rng(12)
    errors = []
    for _ in range(300):
        car_t = np.cumsum(rng.choice([0.16, 0.24, 0.32, 0.40], size=30))
        true_s_car = 2400 + 60 * car_t                    # 60 m/s along the track
        pos_t = np.sort(rng.uniform(car_t[0], car_t[-1], size=30))
        lap = {"pos_time_s": pos_t,
               "pos_s_m": 2400 + 60 * pos_t + rng.normal(0, 3.0, size=30),   # noisy, no drift
               "pos_d_m": 2400 + 60 * pos_t - 12.0,                          # smooth, drifted
               "time_s": car_t, "speed_kmh": np.full(30, 216.0)}             # constant 60 m/s
        window = {"time_s": car_t, "d_m": true_s_car - 12.0}
        fused, offset, count, _ = fuse_window_coordinate(lap, window)
        errors.append(np.mean(fused - true_s_car))
    assert abs(np.mean(errors)) < 0.15                    # the 12 m drift is gone
    assert np.std(errors) == pytest.approx(3.0 / np.sqrt(30), rel=0.2)


def test_cumulative_path_length():
    assert list(cumulative_path_length([0, 3, 3], [0, 4, 10])) == pytest.approx([0, 5, 11])


def test_projection_on_a_straight_segment():
    s, side = project_onto_path([4.0], [3.0], [0.0, 10.0], [0.0, 0.0], [0.0, 10.0])
    assert s[0] == pytest.approx(4.0)
    assert side[0] == pytest.approx(3.0)


def test_projection_recovers_position_along_a_curved_track():
    # A 100 m-radius circle sampled every ~20 m as the reference path; points
    # 0.5 m outside it at known arc lengths project back to (nearly) that arc length.
    radius = 100.0
    angles = np.arange(0, 2 * np.pi * 0.75, 0.2)
    path_x, path_y = radius * np.cos(angles), radius * np.sin(angles)
    path_s = cumulative_path_length(path_x, path_y)
    true_arc = np.array([33.0, 150.0, 301.7])
    point_angles = true_arc / radius
    px, py = (radius + 0.5) * np.cos(point_angles), (radius + 0.5) * np.sin(point_angles)
    s, side = project_onto_path(px, py, path_x, path_y, path_s)
    # chords are slightly shorter than arcs (0.17 % at 20 m spacing on R = 100 m)
    assert s == pytest.approx(true_arc, rel=0.003)
    assert np.all(side < 1.0)


def test_expected_s_stops_snapping_to_another_part_of_the_track():
    # A hairpin: two parallel straights 4 m apart. A point on the way back,
    # 1.5 m from the outbound straight, would snap to it without a hint.
    path_x = np.array([0.0, 100.0, 100.0, 0.0])
    path_y = np.array([0.0, 0.0, 4.0, 4.0])
    path_s = cumulative_path_length(path_x, path_y)   # 0, 100, 104, 204
    s_no_hint, _ = project_onto_path([50.0], [1.5], path_x, path_y, path_s)
    s_hint, _ = project_onto_path([50.0], [1.5], path_x, path_y, path_s,
                                  expected_s=np.array([150.0]), search_m=60)
    assert s_no_hint[0] == pytest.approx(50.0)     # wrong straight
    assert s_hint[0] == pytest.approx(154.0)       # right one


def test_track_coordinate_interpolates_in_time():
    assert track_coordinate_at_times([10.05], [10.0, 10.2], [1000.0, 1016.0])[0] == pytest.approx(1004.0)


def test_parabolic_peak_docstring_example():
    peak, _ = parabolic_peak(np.array([-1, 0, 1]), np.array([0.8, 1.0, 0.9]))
    assert peak == pytest.approx(1 / 6)


def test_cross_correlation_recovers_a_7_3_m_shift():
    """The roadmap's synthetic shift test: a realistic corner moved 7.3 m later.

    The grid is 1 m, so 7.3 m is between grid points: the parabolic peak
    refinement must get it to within 0.1 m.
    """
    rng = np.random.default_rng(11)
    truth = make_true_corner(random_corner_params("heavy_braking", rng))
    d, v = truth["distance_m"], truth["speed_kmh"]
    grid, reference = resample_by_distance(d, v, 1.0, start_m=100, end_m=700)
    _, shifted = resample_by_distance(d + 7.3, v, 1.0, start_m=100, end_m=700)
    shift, peak = lag_metres(reference, shifted, grid_step_m=1.0, max_lag_m=30)
    assert shift == pytest.approx(7.3, abs=0.1)
    assert peak > 0.99
    shift_back, _ = lag_metres(reference, resample_by_distance(d - 4.6, v, 1.0, 100, 700)[1], 1.0, 30)
    assert shift_back == pytest.approx(-4.6, abs=0.1)


def test_detect_braking_corners_on_a_made_up_lap():
    """A 3 km lap with three dips: 300 -> 80 km/h, 290 -> 180 km/h, and a 30 km/h lift (not a corner)."""
    from apextrace.corners import detect_braking_corners

    s = np.arange(0.0, 3000.0, 20.0)
    speed = np.full(len(s), 300.0)
    speed -= 220 * np.exp(-((s - 800) / 60) ** 2)    # heavy braking corner at 800 m
    speed -= 110 * np.exp(-((s - 1800) / 60) ** 2)   # medium corner at 1800 m
    speed -= 30 * np.exp(-((s - 2400) / 40) ** 2)    # a lift: drop < 50 km/h
    speed[(s >= 1780) & (s <= 1820)] = np.round(speed[(s >= 1780) & (s <= 1820)].min())  # a flat bottom
    corners = detect_braking_corners(s, speed, lap_length_m=3000.0)
    assert [c["corner"] for c in corners] == ["C1", "C2"]
    assert corners[0]["s_m"] == pytest.approx(800.0)
    assert corners[0]["type"] == "slow"
    assert abs(corners[1]["s_m"] - 1800.0) <= 20.0
    assert corners[1]["type"] == "medium"


def test_detect_braking_corners_skips_a_corner_whose_window_leaves_the_lap():
    from apextrace.corners import detect_braking_corners

    s = np.arange(0.0, 2000.0, 20.0)
    speed = 300.0 - 200 * np.exp(-((s - 1900) / 50) ** 2)   # window would end at 2100 m > 2000 m
    assert detect_braking_corners(s, speed, lap_length_m=2000.0) == []

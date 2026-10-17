"""Tests for events.py: each estimator alone, then the full path on realistic synthetic corners."""

import numpy as np
import pytest

from apextrace.events import (
    apex_lowest_sample,
    apex_parabola,
    brake_onset_breakpoint,
    braking_event,
    brake_onset_first_on,
    brake_onset_midpoint,
    crossing_first_sample,
    crossing_interpolated,
    last_brake_on_time,
)
from apextrace.synthetic import degrade_like_feed, make_true_corner, random_corner_params
from test_synthetic import REAL_LIKE_INTERVALS, REAL_LIKE_PROBS


def test_brake_midpoint_and_first_on():
    times = np.array([10.00, 10.32, 10.56])
    brake = np.array([False, True, True])
    assert brake_onset_first_on(times, brake) == pytest.approx(10.32)
    assert brake_onset_midpoint(times, brake) == pytest.approx(10.16)


def test_parabola_finds_the_exact_vertex_with_uneven_spacing():
    # speed = 2 (t - 0.5)^2 + 65 sampled at uneven times; lowest sample at 0.44 s
    times = np.array([0.0, 0.16, 0.44, 0.72, 0.96])
    speed = 2 * (times - 0.5) ** 2 + 65
    t, v = apex_parabola(times, speed, points=3)
    assert t == pytest.approx(0.5)
    assert v == pytest.approx(65.0)
    t5, v5 = apex_parabola(times, speed, points=5)
    assert t5 == pytest.approx(0.5)
    assert v5 == pytest.approx(65.0)


def test_parabola_uses_fewer_points_near_the_edge():
    # minimum one sample from the start: 5 points don't fit, 3 do
    times = np.array([0.0, 0.16, 0.44, 0.72, 0.96])
    speed = 2 * (times - 0.25) ** 2 + 65
    t, v = apex_parabola(times, speed, points=5)
    assert t == pytest.approx(0.25)
    assert v == pytest.approx(65.0)


def test_parabola_docstring_example():
    t, v = apex_parabola(np.array([0.0, 0.24, 0.52]), np.array([70.0, 66.0, 69.0]))
    assert 0.2 < t < 0.35
    assert 65.0 < v < 66.0


def test_lowest_sample():
    assert apex_lowest_sample(np.array([0.0, 0.2, 0.4]), np.array([70.0, 66.0, 69.0])) == (0.2, 66.0)


def test_interpolated_crossing():
    times = np.array([19.70, 20.00, 20.30])
    throttle = np.array([0.0, 4.0, 34.0])
    assert crossing_interpolated(times, throttle, 10.0, start_s=19.0) == pytest.approx(20.06)
    assert crossing_first_sample(times, throttle, 10.0, start_s=19.0) == pytest.approx(20.30)


def test_breakpoint_recovers_a_known_bend():
    # flat-ish straight, then braking at 180 km/h per second from tb = 5.137 s
    rng = np.random.default_rng(7)
    times = np.cumsum(rng.choice([0.16, 0.24, 0.32], size=40))
    true_tb = 5.137
    speed = np.where(times < true_tb, 300 + 2 * (times - true_tb), 300 - 180 * (times - true_tb))
    brake = times >= true_tb
    assert brake_onset_breakpoint(times, speed, brake) == pytest.approx(true_tb, abs=0.005)
    assert brake_onset_breakpoint(times, speed, brake, within_brake_interval=True) \
        == pytest.approx(true_tb, abs=0.005)


def test_full_path_refined_estimators_beat_naive_ones():
    """200 realistic corners -> degraded like the feed -> every estimator.

    Errors are measured in metres along the true track. The refined
    estimators must have a smaller typical error (RMS) than the naive ones.
    """
    rng = np.random.default_rng(8)
    errors = {"first_on": [], "midpoint": [], "apex_low": [], "apex_parab": [],
              "apex_speed_low": [], "apex_speed_parab": [], "thr_first": [], "thr_interp": []}
    for k in range(200):
        corner_type = ["heavy_braking", "medium", "fast"][k % 3]
        truth = make_true_corner(random_corner_params(corner_type, rng))
        s = degrade_like_feed(truth, REAL_LIKE_INTERVALS, REAL_LIKE_PROBS, rng, max_interval_s=0.6)
        ev = truth["events"]

        def to_m(time_s):
            return np.interp(time_s, truth["time_s"], truth["distance_m"])

        errors["first_on"].append(to_m(brake_onset_first_on(s["time_s"], s["brake"])) - ev["brake_onset"]["d"])
        errors["midpoint"].append(to_m(brake_onset_midpoint(s["time_s"], s["brake"])) - ev["brake_onset"]["d"])

        t_low, v_low = apex_lowest_sample(s["time_s"], s["speed_kmh"])
        t_par, v_par = apex_parabola(s["time_s"], s["speed_kmh"])
        errors["apex_low"].append(to_m(t_low) - ev["apex"]["d"])
        errors["apex_parab"].append(to_m(t_par) - ev["apex"]["d"])
        errors["apex_speed_low"].append(v_low - ev["apex"]["speed_kmh"])
        errors["apex_speed_parab"].append(v_par - ev["apex"]["speed_kmh"])

        start = last_brake_on_time(s["time_s"], s["brake"])
        errors["thr_first"].append(to_m(crossing_first_sample(s["time_s"], s["throttle_pct"], 10, start))
                                   - ev["throttle_pickup"]["d"])
        errors["thr_interp"].append(to_m(crossing_interpolated(s["time_s"], s["throttle_pct"], 10, start))
                                    - ev["throttle_pickup"]["d"])

    def rms(values):
        return float(np.sqrt(np.mean(np.square(values))))

    assert rms(errors["midpoint"]) < rms(errors["first_on"])
    assert abs(np.mean(errors["midpoint"])) < abs(np.mean(errors["first_on"]))
    assert rms(errors["apex_speed_parab"]) < rms(errors["apex_speed_low"])
    assert rms(errors["thr_interp"]) < rms(errors["thr_first"])
    # the naive brake estimate is late on average (positive error)
    assert np.mean(errors["first_on"]) > 5.0


def test_braking_event_merges_a_brief_release_without_throttle():
    # brake on, off for one sample (throttle stays 0), on again, apex at index 8
    brake = np.array([0, 0, 1, 1, 1, 0, 1, 1, 0, 0, 0], dtype=bool)
    throttle = np.array([100, 100, 0, 0, 0, 0, 0, 0, 0, 30, 80], dtype=float)
    onset, release = braking_event(brake, throttle, apex_index=8)
    assert (onset, release) == (2, 7)


def test_braking_event_keeps_two_braking_zones_apart():
    # a chicane: brake, throttle opened (40 %), brake again, apex at index 10
    brake = np.array([0, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0], dtype=bool)
    throttle = np.array([100, 0, 0, 20, 40, 10, 0, 0, 0, 0, 30, 90], dtype=float)
    onset, release = braking_event(brake, throttle, apex_index=10)
    assert (onset, release) == (6, 8)


def test_braking_event_without_brake_raises():
    with pytest.raises(ValueError):
        braking_event(np.zeros(5, dtype=bool), np.full(5, 100.0), apex_index=3)

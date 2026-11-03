"""Tests for synthetic.py: the true corners are realistic, and the degradation looks like the feed."""

import numpy as np
import pytest

from apextrace.synthetic import (
    CORNER_TYPES,
    braking_decel,
    degrade_like_feed,
    make_true_corner,
    pre_brake_accel,
    random_corner_params,
)

# The real car-data interval distribution (Phase 1, check 1), rounded:
# multiples of 40 ms from 0.16 to 0.48 s, plus one feed gap value.
REAL_LIKE_INTERVALS = np.array([0.16, 0.20, 0.24, 0.28, 0.32, 0.36, 0.40, 0.44, 0.48, 1.16])
REAL_LIKE_PROBS = np.array([18.0, 19.5, 16.6, 15.0, 11.7, 8.1, 5.8, 3.8, 1.0, 0.5])
REAL_LIKE_PROBS = REAL_LIKE_PROBS / REAL_LIKE_PROBS.sum()


@pytest.mark.parametrize("corner_type", list(CORNER_TYPES))
def test_true_corner_is_physically_realistic(corner_type):
    rng = np.random.default_rng(3)
    for _ in range(20):
        params = random_corner_params(corner_type, rng)
        events = make_true_corner(params)["events"]
        braking_m = events["apex"]["d"] - events["brake_onset"]["d"]
        assert 4.0 * 9.81 < events["peak_decel_ms2"] < 6.5 * 9.81
        assert 70 < braking_m < 160                       # real T6: ~110 m
        assert abs(events["apex"]["speed_kmh"] - params["apex_kmh"]) < 8
        assert abs(events["entry_speed_kmh"] - params["entry_kmh"]) < 4
        # events come in the right order
        assert events["brake_onset"]["t"] < events["brake_release"]["t"] \
            < events["throttle_pickup"]["t"] < events["full_throttle"]["t"]


def test_degraded_samples_look_like_the_feed():
    rng = np.random.default_rng(4)
    truth = make_true_corner(random_corner_params("heavy_braking", rng))
    samples = degrade_like_feed(truth, REAL_LIKE_INTERVALS, REAL_LIKE_PROBS, rng)

    intervals = np.diff(samples["time_s"])
    # every interval is one of the allowed values
    for interval in intervals:
        assert np.min(np.abs(REAL_LIKE_INTERVALS - interval)) < 1e-9
    assert 3.0 < 1 / np.mean(intervals) < 4.5             # ~3.8 samples per second
    assert np.array_equal(samples["speed_kmh"], np.round(samples["speed_kmh"]))  # whole km/h
    assert samples["brake"].dtype == bool
    assert samples["brake"].any() and not samples["brake"].all()


def test_max_interval_removes_feed_gaps():
    rng = np.random.default_rng(5)
    truth = make_true_corner(random_corner_params("fast", rng))
    for _ in range(20):
        samples = degrade_like_feed(truth, REAL_LIKE_INTERVALS, REAL_LIKE_PROBS, rng, max_interval_s=0.6)
        assert np.max(np.diff(samples["time_s"])) <= 0.6


def test_each_lap_gets_a_different_sampling_phase():
    rng = np.random.default_rng(6)
    truth = make_true_corner(random_corner_params("medium", rng))
    first_times = set()
    for _ in range(10):
        samples = degrade_like_feed(truth, REAL_LIKE_INTERVALS, REAL_LIKE_PROBS, rng)
        first_times.add(round(samples["time_s"][0], 6))
    assert len(first_times) == 10


# ---------------------------------------------------------------- the coasting check (2026)

def corner_with(pre_brake, pre_brake_s=0.8, harvest_kw=300.0, seed=5, **extra):
    params = random_corner_params("heavy_braking", np.random.default_rng(seed))
    params.update({"pre_brake": pre_brake, "pre_brake_s": pre_brake_s, "harvest_kw": harvest_kw, **extra})
    return params, make_true_corner(params)


def phase_samples(truth, start, end):
    t = truth["time_s"]
    return (t >= start) & (t < end)


@pytest.mark.parametrize("mode, throttle", [("lift", 0.0), ("superclip", 100.0)])
def test_pre_braking_phase_slows_the_car_with_the_brake_still_off(mode, throttle):
    """Before the brake goes on, the car already loses speed; the throttle channel shows
    0 % (lift and coast) or 100 % (superclipping), and the brake channel stays off."""
    params, truth = corner_with(mode)
    events = truth["events"]
    start = events["brake_onset"]["t"] - params["pre_brake_s"]
    window = phase_samples(truth, start, events["brake_onset"]["t"])
    assert window.sum() > 0.7 * params["pre_brake_s"] * 500       # the phase exists at 500 Hz
    assert np.all(truth["throttle_pct"][window] == throttle)
    assert not truth["brake"][window].any()
    assert np.all(truth["accel_ms2"][window] < 0)                    # slowing down
    assert events["entry_speed_kmh"] < params["entry_kmh"] - 5       # slower when the brake goes on
    # and the braking itself still happens, ending near the planned apex speed
    assert abs(events["apex"]["speed_kmh"] - params["apex_kmh"]) < 8


def test_pre_brake_physics_matches_the_worked_example():
    assert pre_brake_accel(83.0, "lift", 250.0) == pytest.approx(-12.42, abs=0.01)
    assert pre_brake_accel(83.0, "superclip", 250.0) == pytest.approx(-5.16, abs=0.01)
    # harvesting more slows the car more, in both modes
    assert pre_brake_accel(83.0, "lift", 350.0) < pre_brake_accel(83.0, "lift", 0.0)
    assert pre_brake_accel(83.0, "superclip", 350.0) < pre_brake_accel(83.0, "superclip", 100.0)
    with pytest.raises(ValueError):
        pre_brake_accel(83.0, "coast", 100.0)


def test_2026_like_aero_brakes_less_hard():
    """30 % less downforce and 55 % less drag: about 4.4 g instead of 5.9 g at 324 km/h."""
    assert braking_decel(90.0, 0.7, 0.45) / 9.81 == pytest.approx(4.44, abs=0.01)
    params = random_corner_params("heavy_braking", np.random.default_rng(6))
    default = make_true_corner(params)["events"]["peak_decel_ms2"]
    params_2026 = {**params, "aero_scale": 0.7, "drag_scale": 0.45}
    assert make_true_corner(params_2026)["events"]["peak_decel_ms2"] < 0.85 * default

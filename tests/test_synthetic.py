"""Tests for synthetic.py: the true corners are realistic, and the degradation looks like the feed."""

import numpy as np
import pytest

from apextrace.synthetic import (
    CORNER_TYPES,
    degrade_like_feed,
    make_true_corner,
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

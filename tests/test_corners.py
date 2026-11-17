"""The usable-window rule and the corner types (corners.py), at their exact boundaries.

Every corner pass in every result goes through these three functions: a window from 300 m before
to 200 m after the corner marker, one extra sample kept on each side, and the pass dropped if any
interval inside is longer than 0.6 s. tests/test_session_build.py runs them end to end; these tests
pin the edges, where an off-by-one or a ">" vs ">=" would silently change which passes count.
"""

import numpy as np
import pytest

from apextrace.corners import GAP_S, corner_type, has_feed_gap, samples_in_window, window_bounds

KEYS = ["time_s", "s_m", "d_m", "speed_kmh", "throttle_pct", "brake", "gear"]


def lap(s_values, times=None):
    s_values = np.asarray(s_values, dtype=float)
    times = np.arange(len(s_values)) * 0.25 if times is None else np.asarray(times, dtype=float)
    columns = {key: np.arange(len(s_values), dtype=float) for key in KEYS}
    columns["s_m"] = s_values
    columns["time_s"] = times
    return columns


def test_window_bounds_docstring_example():
    assert window_bounds(2617.0) == (2317.0, 2817.0)


def test_samples_in_window_keeps_one_extra_sample_on_each_side():
    samples = lap([0, 100, 200, 300, 400, 500, 600])
    window = samples_in_window(samples, 250.0, 450.0)          # inside: 300 and 400
    assert list(window["s_m"]) == [200, 300, 400, 500]
    assert set(window) == set(KEYS)


def test_samples_in_window_at_the_lap_ends_and_outside():
    samples = lap([0, 100, 200])
    assert list(samples_in_window(samples, 0.0, 100.0)["s_m"]) == [0, 100, 200]   # nothing before the first
    assert list(samples_in_window(samples, 150.0, 900.0)["s_m"]) == [100, 200]    # nothing after the last
    assert samples_in_window(samples, 210.0, 290.0) is None                       # no sample inside


def test_feed_gap_threshold_around_0_6_s():
    assert GAP_S == 0.6
    assert not has_feed_gap({"time_s": np.array([0.0, 0.28, 0.84, 1.12])})        # 0.56 s: kept
    assert has_feed_gap({"time_s": np.array([0.0, 0.28, 0.92, 1.2])})             # 0.64 s: a gap
    assert not has_feed_gap({"time_s": np.array([5.0])})                          # one sample: no interval


def test_exactly_0_6_s_is_decided_by_floating_point_rounding_frozen_behaviour():
    """Found in the 2026-11-18 code review: on the feed's 40 ms clock, 0.60 s is a real interval,
    and "longer than 0.6" then depends on how the timestamps round. 0.9 - 0.3 is
    0.6000000000000001 (a gap); 0.6 - 0.0 is 0.6 (not a gap). Every dataset, including the frozen
    2025 and 2026 tests, was built this way, so it is NOT changed; experiments/34_gap_boundary.py
    measures how many corner passes sit on this edge (docs/engineering_notes.md, 2026-11-18).
    If this test fails, the rule was changed: every dataset would be rebuilt differently."""
    assert has_feed_gap({"time_s": np.array([0.3, 0.9])})
    assert not has_feed_gap({"time_s": np.array([0.0, 0.6])})


@pytest.mark.parametrize("speed, expected", [(119.9, "slow"), (120.0, "medium"), (199.9, "medium"),
                                             (200.0, "fast"), (60.0, "slow"), (260.0, "fast")])
def test_corner_type_boundaries(speed, expected):
    assert corner_type(speed) == expected

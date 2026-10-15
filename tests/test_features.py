"""Full-path test for features.py: synthetic corner -> feed-like samples -> features vs truth."""

import numpy as np

from apextrace.features import FEATURES, corner_features
from apextrace.synthetic import degrade_like_feed, make_true_corner, random_corner_params
from test_synthetic import REAL_LIKE_INTERVALS, REAL_LIKE_PROBS


def synthetic_window(rng, corner_type):
    """A degraded synthetic corner as a window, with perfect alignment and the marker at the true apex."""
    truth = make_true_corner(random_corner_params(corner_type, rng))
    s = degrade_like_feed(truth, REAL_LIKE_INTERVALS, REAL_LIKE_PROBS, rng, max_interval_s=0.6)
    window = {"time_s": s["time_s"], "speed_kmh": s["speed_kmh"], "throttle_pct": s["throttle_pct"],
              "brake": s["brake"], "gear": np.full(len(s["time_s"]), 3.0)}
    fused = np.interp(s["time_s"], truth["time_s"], truth["distance_m"])
    return truth, window, fused, truth["events"]["apex"]["d"]


def test_features_match_the_truth_on_average():
    rng = np.random.default_rng(21)
    errors = {name: [] for name in ["brake_onset_m", "min_speed_kmh", "apex_m", "throttle_pickup_m",
                                    "entry_speed_kmh", "mean_decel_ms2"]}
    for k in range(150):
        truth, window, fused, corner_s = synthetic_window(rng, ["heavy_braking", "medium", "fast"][k % 3])
        ev = truth["events"]
        f = corner_features(window, fused, corner_s)
        assert set(f) == set(FEATURES)
        errors["brake_onset_m"].append(f["brake_onset_m"] - (ev["brake_onset"]["d"] - corner_s))
        errors["min_speed_kmh"].append(f["min_speed_kmh"] - ev["apex"]["speed_kmh"])
        errors["apex_m"].append(f["apex_m"])  # the marker IS the true apex, so the truth is 0
        errors["throttle_pickup_m"].append(f["throttle_pickup_m"] - (ev["throttle_pickup"]["d"] - corner_s))
        entry_time = np.interp(corner_s - 200, truth["distance_m"], truth["time_s"])
        errors["entry_speed_kmh"].append(f["entry_speed_kmh"] - np.interp(entry_time, truth["time_s"], truth["speed_kmh"]))
        true_decel = ((ev["entry_speed_kmh"] - ev["apex"]["speed_kmh"]) / 3.6
                      / (ev["apex"]["t"] - ev["brake_onset"]["t"]))
        errors["mean_decel_ms2"].append(f["mean_decel_ms2"] - true_decel)

    mean = {name: float(np.mean(values)) for name, values in errors.items()}
    # biases match the Phase 2 Monte Carlo (brake onset ~+3 m, others ~0)
    assert 1.0 < mean["brake_onset_m"] < 6.0
    assert abs(mean["min_speed_kmh"]) < 0.3
    assert abs(mean["apex_m"]) < 2.0
    assert abs(mean["throttle_pickup_m"]) < 4.0
    assert abs(mean["entry_speed_kmh"]) < 0.3
    assert abs(mean["mean_decel_ms2"]) < 2.0     # true mean decel is ~25-35 m/s^2


def test_braking_distance_is_apex_minus_onset():
    rng = np.random.default_rng(22)
    _, window, fused, corner_s = synthetic_window(rng, "heavy_braking")
    f = corner_features(window, fused, corner_s)
    assert f["braking_distance_m"] == f["apex_m"] - f["brake_onset_m"]
    assert f["brake_onset_m"] < 0 < f["throttle_pickup_m"] + 50

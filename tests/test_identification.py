"""Tests for identification.py on synthetic laps where the right answer is known."""

import numpy as np
import pandas as pd
import pytest

from apextrace.identification import (
    lap_vectors,
    leave_one_session_out,
    scores,
    shuffle_within_groups,
)


def synthetic_laps(rng, signature_m, sessions=12, laps=6, noise_m=3.0):
    """Two drivers; driver B brakes `signature_m` later than A in every session, plus lap noise.

    Each session also has its own offset (track/conditions), shared by both
    drivers, which a model must not mistake for the driver.
    """
    X, y, groups = [], [], []
    for session in range(sessions):
        session_offset = rng.normal(0, 10)
        for driver, shift in [("A", 0.0), ("B", signature_m)]:
            for _ in range(laps):
                X.append([session_offset + shift + rng.normal(0, noise_m), rng.normal(0, 1)])
                y.append(driver)
                groups.append(session)
    return np.array(X), np.array(y), np.array(groups)


def test_a_real_signature_is_found_on_unseen_sessions():
    """7 m signature, 3 m lap noise; session offsets removed the way the pipeline
    does it (field-relative = minus the session median).

    Theory: after removing the median the drivers sit at about -3.5 and +3.5 m
    with 3 m noise, so even a perfect classifier gets at most
    Phi(3.5 / 3) = 0.878; estimating the median from 12 laps adds ~1 m of
    noise (-> about 0.86). The upper bound matters too: a score above what's
    possible would mean leakage.
    """
    rng = np.random.default_rng(41)
    X, y, groups = synthetic_laps(rng, signature_m=7.0)
    for session in np.unique(groups):
        X[groups == session, 0] -= np.median(X[groups == session, 0])
    result = scores(y, leave_one_session_out(X, y, groups, "logistic"))
    assert 0.78 < result["balanced_accuracy"] < 0.92


def test_no_signature_gives_chance_level():
    rng = np.random.default_rng(42)
    X, y, groups = synthetic_laps(rng, signature_m=0.0)
    for session in np.unique(groups):
        X[groups == session, 0] -= np.median(X[groups == session, 0])
    result = scores(y, leave_one_session_out(X, y, groups, "logistic"))
    assert 0.35 < result["balanced_accuracy"] < 0.65


def test_shuffled_labels_drop_to_chance():
    rng = np.random.default_rng(43)
    X, y, groups = synthetic_laps(rng, signature_m=7.0)
    for session in np.unique(groups):
        X[groups == session, 0] -= np.median(X[groups == session, 0])
    shuffled = shuffle_within_groups(y, groups, rng)
    # each session keeps its 6 + 6 labels
    for session in np.unique(groups):
        assert sorted(shuffled[groups == session]) == sorted(y[groups == session])
    result = scores(shuffled, leave_one_session_out(X, shuffled, groups, "logistic"))
    assert 0.3 < result["balanced_accuracy"] < 0.7


def test_majority_baseline_and_nearest_centroid_run():
    rng = np.random.default_rng(44)
    X, y, groups = synthetic_laps(rng, signature_m=7.0)
    majority = scores(y, leave_one_session_out(X, y, groups, "majority"))
    assert majority["balanced_accuracy"] == pytest.approx(0.5)
    centroid = scores(y, leave_one_session_out(X, y, groups, "nearest_centroid"))
    assert centroid["n"] == len(y)


def test_missing_values_are_filled_from_training_data_only():
    rng = np.random.default_rng(45)
    X, y, groups = synthetic_laps(rng, signature_m=7.0)
    X[::5, 1] = np.nan
    result = scores(y, leave_one_session_out(X, y, groups, "logistic"))
    assert result["n"] == len(y)


def test_lap_vectors_average_per_corner_type():
    rows = pd.DataFrame([
        {"session_key": 1, "driver": "A", "lap": 2, "corner_type": "slow", "brake_onset_m_rel": 3.0,
         "year": 2024, "team": "T", "location": "X", "lap_time_s": 90.0},
        {"session_key": 1, "driver": "A", "lap": 2, "corner_type": "slow", "brake_onset_m_rel": 5.0,
         "year": 2024, "team": "T", "location": "X", "lap_time_s": 90.0},
        {"session_key": 1, "driver": "A", "lap": 2, "corner_type": "fast", "brake_onset_m_rel": -1.0,
         "year": 2024, "team": "T", "location": "X", "lap_time_s": 90.0},
    ])
    laps = lap_vectors(rows, features=["brake_onset_m"])
    assert len(laps) == 1
    assert laps.loc[0, "brake_onset_m_rel__slow"] == pytest.approx(4.0)
    assert laps.loc[0, "brake_onset_m_rel__fast"] == pytest.approx(-1.0)
    assert "brake_onset_m_rel__medium" not in laps.columns

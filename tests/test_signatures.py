"""Tests for signatures.py: season signatures, distances, ranks, sign test."""

import numpy as np
import pandas as pd
import pytest

from apextrace.signatures import distance, distance_table, own_rank, season_signatures, sign_test_p, standardise


def test_distance_ignores_missing_features():
    assert distance([1.0, -2.0, np.nan], [0.0, 0.0, 5.0]) == pytest.approx(np.sqrt(5 / 2))
    assert np.isnan(distance([np.nan], [1.0]))


def test_sign_test():
    assert sign_test_p(5, 5) == pytest.approx(1 / 32)
    assert sign_test_p(4, 5) == pytest.approx(6 / 32)
    assert sign_test_p(0, 5) == pytest.approx(1.0)


def test_every_session_counts_once_in_a_signature():
    # session 1: three laps at 0; session 2: one lap at 10 -> mean of session means = 5 (not 2.5)
    laps = pd.DataFrame({"year": 2024, "session_key": [1, 1, 1, 2], "driver": "A", "team": "T",
                         "f": [0.0, 0.0, 0.0, 10.0]})
    signatures = season_signatures(laps, ["f"], min_sessions=2)
    assert signatures.loc[("A", 2024), "f"] == pytest.approx(5.0)
    assert len(season_signatures(laps, ["f"], min_sessions=3)) == 0


def season_of_laps(rng, personal_offsets, noise, sessions=20):
    rows = []
    for year in (2023, 2024):
        for session in range(sessions):
            for name, offset in personal_offsets.items():
                values = offset + rng.normal(0, noise, len(offset))
                rows.append({"year": year, "session_key": year * 100 + session, "driver": name, "team": "T",
                             **{f"f{i}": values[i] for i in range(len(offset))}})
    return pd.DataFrame(rows)


def ranks(laps, columns, names):
    signatures = season_signatures(laps, columns)
    old_raw = signatures.xs(2023, level="year")
    old = standardise(old_raw, columns, old_raw)
    new = standardise(signatures.xs(2024, level="year"), columns, old_raw)
    distances = distance_table(new, old, columns)
    return [own_rank(distances, name) for name in names]


def test_a_stable_driver_signature_ranks_first():
    """20 drivers, 20 weekends a season, personal offsets with spread 1 and weekend noise 0.8:
    a season mean has noise 0.8 / sqrt(20) = 0.18, much smaller than the gaps between
    drivers, so nearly every driver's 2024 signature is closest to their own 2023 one."""
    rng = np.random.default_rng(51)
    names = [f"D{k}" for k in range(20)]
    personal = {name: rng.normal(0, 1, 6) for name in names}
    laps = season_of_laps(rng, personal, noise=0.8)
    own = ranks(laps, [f"f{i}" for i in range(6)], names)
    assert sum(rank == 1 for rank in own) >= 18


def test_without_a_personal_signature_ranks_are_random():
    """Same setup but no personal offsets: the own signature is no closer than anyone's,
    so the mean rank is near the middle, (20 + 1) / 2 = 10.5."""
    rng = np.random.default_rng(52)
    names = [f"D{k}" for k in range(20)]
    personal = {name: np.zeros(6) for name in names}
    laps = season_of_laps(rng, personal, noise=0.8)
    own = ranks(laps, [f"f{i}" for i in range(6)], names)
    assert 6.5 < np.mean(own) < 14.5

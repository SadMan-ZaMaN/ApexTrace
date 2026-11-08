"""Teammate-relative signatures (signatures.cosine_similarity ... pair_persistence), on known truths.

The claim behind them: the difference between two teammates on the same weekend cancels the
car, so it can carry over to a new season even when the car changes completely. Tested on
synthetic seasons where the car is redrawn every year (synthetic.signature_seasons):
  - with a personal offset per driver, the cosine between seasons is high, also with a big car;
  - without any personal offset, it averages 0 (no direction to carry over).
"""

import numpy as np
import pandas as pd
import pytest

from apextrace.signatures import cosine_similarity, pair_persistence, shared_weekends, weekend_differences
from apextrace.synthetic import SIGNATURE_FEATURES, signature_seasons


def same_name(team):
    return team            # synthetic teams are T0, T1, ...: each name is its own lineage


def test_cosine_worked_examples():
    assert cosine_similarity([1, 0], [1, 1]) == pytest.approx(1 / np.sqrt(2))
    assert cosine_similarity([1, 2], [-1, -2]) == pytest.approx(-1.0)
    assert cosine_similarity([1, 2], [2, 4]) == pytest.approx(1.0)
    # not centred: a difference that is the same on every feature keeps its sign
    assert cosine_similarity([1, 1, 1], [2, 2, 2]) == pytest.approx(1.0)
    # NaN-safe: only entries both vectors have
    assert cosine_similarity([1, np.nan, 0], [1, 5, 1]) == pytest.approx(1 / np.sqrt(2))
    assert np.isnan(cosine_similarity([0, 0], [1, 1]))


def test_shared_weekends_follow_the_lineage_per_session():
    laps = pd.DataFrame({"session_key": [1, 1, 2, 2, 3, 3, 3],
                         "driver": ["A", "B", "A", "B", "A", "B", "C"],
                         "team": ["T", "T", "T", "T", "T", "T", "T"]})
    assert shared_weekends(laps, same_name) == {("A", "B"): {1, 2, 3}, ("A", "C"): {3}, ("B", "C"): {3}}
    # a renamed team is one team when the lineage says so
    renamed = laps.assign(team=["Old", "Old", "Old", "Old", "New", "New", "Other"])
    assert shared_weekends(renamed, lambda team: "X" if team in ("Old", "New") else team) == {("A", "B"): {1, 2, 3}}


def test_weekend_differences_use_equal_laps():
    """The docstring's example: A 10, 10, 40 and B 14, 14 -> -4 (all laps would give +6)."""
    laps = pd.DataFrame({"session_key": [1, 1, 1, 1, 1], "driver": ["A", "A", "A", "B", "B"],
                         "lap": [1, 2, 3, 1, 2], "f0": [10.0, 10.0, 40.0, 14.0, 14.0]})
    table = weekend_differences(laps, "A", "B", {1}, ["f0"])
    assert table["f0"].tolist() == [-4.0]


def persistence_over(seed, studies, **options):
    rng = np.random.default_rng(seed)
    tables = []
    for _ in range(studies):
        laps = signature_seasons(rng, **options)
        tables.append(pair_persistence(laps, 2025, 2026, SIGNATURE_FEATURES, same_name))
    return pd.concat(tables)


def test_a_personal_difference_survives_a_completely_new_and_large_car():
    """Personal offsets SD 1, a car redrawn each year with SD 5 (five times larger), noise 1,
    2 laps per weekend, 12 weekends. The weekend difference cancels the car, so the cosine
    between seasons is close to 1 for every pair. (Comparing the raw signatures instead, the
    redrawn car would dominate and the cosine would be near 0.)"""
    table = persistence_over(seed=1, studies=10, personal_sd=1.0, car_sd=5.0)
    assert len(table) == 50                      # 5 teams x 10 studies, every pair in both seasons
    assert table["cosine"].median() > 0.9
    assert (table["cosine"] > 0).mean() > 0.95
    assert table["split_half_earlier"].median() > 0.8


def test_without_a_personal_difference_the_cosine_averages_zero():
    """Only the car (redrawn) and noise: the season differences are noise, so their cosine is
    symmetric around 0. One cosine of two random 10-feature vectors has SD about 1/sqrt(10) =
    0.32, so over 400 pairs the mean has a standard error of about 0.016 and the share above
    0 one of 0.025; both bounds are about 3 standard errors. (400 pairs, not more: the
    equal-laps step shared with H5 takes ~0.02 s per pair.)"""
    table = persistence_over(seed=2, studies=20, personal_sd=0.0, car_sd=1.0, teams=20)
    assert len(table) == 400
    assert abs(table["cosine"].mean()) < 0.05
    assert 0.42 < (table["cosine"] > 0).mean() < 0.58


def test_a_pair_that_did_not_stay_together_is_not_compared():
    """B drives only 3 of 12 reference weekends and is replaced by a newcomer in 2026: no pair
    is in both seasons."""
    laps = signature_seasons(np.random.default_rng(3), personal_sd=1.0, teammate_weekends=3)
    assert pair_persistence(laps, 2025, 2026, SIGNATURE_FEATURES, same_name).empty

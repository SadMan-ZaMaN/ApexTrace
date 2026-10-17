"""Tests for stats.py on data where the right answer is known (Phase 5 plan, step 2)."""

import numpy as np
import pytest

from apextrace.stats import (
    benjamini_hochberg,
    bootstrap_ci,
    hedges_g,
    holm,
    icc_oneway,
    min_detectable_effect,
    min_permutation_p,
    permutation_test,
)


def test_exact_permutation_small_example():
    # pooled [1, 2, 3, 4], groups of 2: 6 splits; |difference| >= 2 for 2 of them
    difference, p = permutation_test([1, 2], [3, 4])
    assert difference == pytest.approx(-2.0)
    assert p == pytest.approx(2 / 6)


def test_minimum_p_for_4_vs_4_laps():
    assert min_permutation_p(4, 4) == pytest.approx(2 / 70)
    # completely separated groups reach exactly that minimum
    _, p = permutation_test([10, 11, 12, 13], [1, 2, 3, 4])
    assert p == pytest.approx(2 / 70)


def test_minimum_p_for_unequal_groups_has_no_mirror_split():
    # 3 vs 4 laps: 35 splits, and swapping the groups is not a valid split
    assert min_permutation_p(3, 4) == pytest.approx(1 / 35)
    assert min_permutation_p(2, 4) == pytest.approx(1 / 15)
    _, p = permutation_test([10, 11, 12], [1, 2, 3, 4])
    assert p == pytest.approx(min_permutation_p(3, 4))


def test_permutation_false_positive_rate_is_about_5_percent():
    # Two groups from the SAME distribution: about 5 % of p-values below 0.05
    rng = np.random.default_rng(31)
    rejections = 0
    trials = 400
    for _ in range(trials):
        _, p = permutation_test(rng.normal(0, 1, 10), rng.normal(0, 1, 10), rng=rng, n_random=1000)
        rejections += p < 0.05
    assert 0.025 < rejections / trials < 0.085


def test_bootstrap_ci_covers_a_known_shift_about_95_percent_of_the_time():
    rng = np.random.default_rng(32)
    covered = 0
    trials = 300
    for _ in range(trials):
        a = rng.normal(3.0, 2.0, 30)
        b = rng.normal(0.0, 2.0, 30)
        low, high = bootstrap_ci(a, b, rng=rng, n_boot=1000)
        covered += low <= 3.0 <= high
    assert 0.90 < covered / trials < 0.99


def test_hedges_g_docstring_example():
    assert hedges_g([1, 2, 3], [3, 4, 5]) == pytest.approx(-1.6)


def test_holm_and_bh_docstring_examples():
    assert list(holm([0.01, 0.04, 0.03])) == pytest.approx([0.03, 0.06, 0.06])
    assert list(benjamini_hochberg([0.01, 0.04, 0.03])) == pytest.approx([0.03, 0.04, 0.04])


def test_icc_near_one_when_drivers_differ_and_near_zero_when_they_dont():
    rng = np.random.default_rng(33)
    groups = ["A"] * 20 + ["B"] * 20 + ["C"] * 20
    distinct = np.concatenate([rng.normal(m, 0.5, 20) for m in [0, 10, 20]])
    same = rng.normal(0, 1, 60)
    assert icc_oneway(distinct, groups) > 0.95
    assert abs(icc_oneway(same, groups)) < 0.15


def test_icc_matches_a_hand_computed_example():
    # groups [1, 3] and [5, 7]: grand mean 4; SSB = 2*(2-4)^2 + 2*(6-4)^2 = 16, MSB = 16
    # SSW = 2 + 2 = 4, MSW = 4 / 2 = 2; k0 = 2 -> ICC = (16 - 2) / (16 + 2) = 0.778
    assert icc_oneway([1, 3, 5, 7], ["A", "A", "B", "B"]) == pytest.approx(14 / 18)


def test_min_detectable_effect_matches_the_plan():
    # PROJECT_CONTEXT §8: ~1.8 for 6 laps per driver, ~1.3 for 10, ~0.9 for 20
    assert min_detectable_effect(6, 6) == pytest.approx(1.77, abs=0.03)
    assert min_detectable_effect(10, 10) == pytest.approx(1.32, abs=0.03)
    assert min_detectable_effect(20, 20) == pytest.approx(0.91, abs=0.03)


def test_icc_from_groups_matches_icc_oneway():
    from apextrace.stats import icc_from_groups

    rng = np.random.default_rng(34)
    groups = np.repeat(np.arange(40), rng.integers(2, 7, size=40))
    values = rng.normal(0, 1, len(groups)) + rng.normal(0, 1.5, 40)[groups]
    assert icc_from_groups(values, groups) == pytest.approx(icc_oneway(values, groups))
    assert icc_from_groups([1, 3, 5, 7], ["A", "A", "B", "B"]) == pytest.approx(14 / 18)


def test_icc_from_group_stats_matches_icc_oneway():
    from apextrace.stats import icc_from_group_stats

    rng = np.random.default_rng(35)
    groups = np.repeat(np.arange(30), rng.integers(2, 6, size=30))
    values = rng.normal(0, 1, len(groups)) + rng.normal(0, 2, 30)[groups]
    sizes, means, within = [], [], []
    for g in np.unique(groups):
        v = values[groups == g]
        sizes.append(len(v))
        means.append(v.mean())
        within.append(np.sum((v - v.mean()) ** 2))
    assert icc_from_group_stats(sizes, means, within) == pytest.approx(icc_oneway(values, groups))

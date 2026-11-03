"""Independent cross-checks: our hand-written statistics against SciPy (or a second, differently
written version), on many inputs.

Why: our functions are written out by hand so they can be explained line by line, but a
hand-written formula can hide a slip (an off-by-one, a wrong tail). A second, independent
implementation that agrees on hundreds of inputs makes that unlikely. Every result the
project reports (H2, H4, H5) goes through these functions.
"""

import math

import numpy as np
import pytest
from scipy.stats import binom, binomtest, f_oneway, false_discovery_control, permutation_test as scipy_permutation_test

from apextrace.signatures import sign_test_p, sign_test_power, sign_test_threshold
from apextrace.stats import benjamini_hochberg, holm, icc_oneway, permutation_test


def test_sign_test_p_agrees_with_scipy_binomtest():
    """Every possible count for 1-25 drivers (the H4 / H5 range)."""
    for trials in range(1, 26):
        for successes in range(trials + 1):
            expected = binomtest(successes, trials, 0.5, alternative="greater").pvalue
            assert sign_test_p(successes, trials) == pytest.approx(expected, rel=1e-9)


def test_sign_test_power_agrees_with_scipy_binomial_distribution():
    """Power = P(X >= threshold) for X ~ Binomial(n, q) = binom.sf(threshold - 1, n, q)."""
    for trials in range(1, 26):
        threshold = sign_test_threshold(trials)
        if threshold is not None:
            # the threshold itself: the first count with p < 0.05, and the one below is not
            assert binomtest(threshold, trials, 0.5, alternative="greater").pvalue < 0.05
            assert binomtest(threshold - 1, trials, 0.5, alternative="greater").pvalue >= 0.05
        for q in (0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.94):
            expected = 0.0 if threshold is None else binom.sf(threshold - 1, trials, q)
            assert sign_test_power(trials, q) == pytest.approx(expected, rel=1e-9, abs=1e-12)


def test_exact_permutation_test_agrees_with_scipy():
    """Small groups like the pilot (3-5 laps each): our exact test vs SciPy's exact
    permutation test with the same statistic, |difference of means|."""
    rng = np.random.default_rng(11)

    def absolute_mean_difference(x, y):
        return abs(np.mean(x) - np.mean(y))

    for n_a, n_b in [(4, 4), (3, 4), (5, 3), (4, 5)]:
        for _ in range(5):
            a = rng.normal(0.0, 1.0, n_a)
            b = rng.normal(rng.uniform(-1, 1), 1.0, n_b)
            _, ours = permutation_test(a, b)
            theirs = scipy_permutation_test((a, b), absolute_mean_difference, permutation_type="independent",
                                            alternative="greater", n_resamples=math.inf, vectorized=False).pvalue
            assert ours == pytest.approx(theirs, rel=1e-9)


def test_benjamini_hochberg_agrees_with_scipy():
    rng = np.random.default_rng(12)
    for size in (1, 3, 10, 27):
        for _ in range(20):
            p = rng.uniform(0, 1, size) ** 2           # some small p-values among them
            assert np.allclose(benjamini_hochberg(p), false_discovery_control(p, method="bh"), rtol=1e-12)


def test_holm_agrees_with_a_second_implementation():
    """SciPy has no Holm; a second version written from the textbook formula instead:
    adjusted p of the k-th smallest = max over j <= k of min(1, (m - j + 1) * p_(j))."""
    rng = np.random.default_rng(13)
    for size in (1, 3, 10, 27):
        for _ in range(20):
            p = rng.uniform(0, 1, size) ** 2
            order = np.argsort(p)
            expected = np.empty(size)
            for k in range(size):
                candidates = [min(1.0, (size - j) * p[order[j]]) for j in range(k + 1)]
                expected[order[k]] = max(candidates)
            assert np.allclose(holm(p), expected, rtol=1e-12)


def test_icc_agrees_with_scipy_one_way_anova():
    """ICC(1) = (F - 1) / (F + k0 - 1), with F from SciPy's one-way ANOVA (computed
    independently of our sums of squares). Unequal group sizes, like drivers with
    different numbers of laps."""
    rng = np.random.default_rng(14)
    for _ in range(30):
        sizes = rng.integers(2, 9, size=int(rng.integers(2, 8)))
        groups_values = [rng.normal(rng.normal(0, 1), 1.0, size) for size in sizes]
        values = np.concatenate(groups_values)
        labels = np.concatenate([[k] * len(g) for k, g in enumerate(groups_values)])
        f_statistic = f_oneway(*groups_values).statistic
        n_total = len(values)
        k0 = (n_total - np.sum(sizes.astype(float) ** 2) / n_total) / (len(sizes) - 1)
        expected = (f_statistic - 1) / (f_statistic + k0 - 1)
        assert icc_oneway(values, labels) == pytest.approx(expected, rel=1e-9)

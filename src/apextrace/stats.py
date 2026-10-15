"""Statistics for repeatability (H1) and driver differences (H2), written to be explainable.

Every method here answers one plain question:
  permutation_test   "If the driver label didn't matter, how often would a
                      difference this big appear just by shuffling the laps?"
  bootstrap_ci       "If we re-ran the session, how much could the difference
                      wobble?" (resample laps with replacement, many times)
  hedges_g           "How big is the difference in units of lap-to-lap spread?"
  holm / benjamini_hochberg
                     "We ran many tests; which survive the extra luck that
                      comes from running many?"
  icc_oneway         "What share of the variation is between drivers rather
                      than lap-to-lap noise?"
  min_detectable_effect
                     "With this few laps, how big must a difference be to have
                      an 80 % chance of being detected?" (statistical power)
"""

import itertools
import math

import numpy as np
from scipy import stats as scipy_stats


def mean_difference(a, b):
    return float(np.mean(a) - np.mean(b))


def permutation_test(a, b, rng=None, max_exact=20000, n_random=20000):
    """Two-sided permutation test of the difference in means. Returns (difference, p-value).

    Idea: if the driver label made no difference, any split of the pooled laps
    into groups of the same sizes would be just as likely as the real one. So
    we compute the difference for every possible split (or many random ones)
    and ask what share is at least as extreme as the real difference.

    Small groups are done exactly: 4 vs 4 laps have C(8, 4) = 70 splits, so the
    smallest possible two-sided p-value is 2/70 = 0.029 (see min_permutation_p).
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    pooled = np.concatenate([a, b])
    observed = abs(mean_difference(a, b))
    n_a = len(a)
    total = math.comb(len(pooled), n_a)
    tolerance = 1e-12 * max(1.0, observed)

    extreme = 0
    count = 0
    if total <= max_exact:
        indices = np.arange(len(pooled))
        for chosen in itertools.combinations(indices, n_a):
            mask = np.zeros(len(pooled), dtype=bool)
            mask[list(chosen)] = True
            if abs(mean_difference(pooled[mask], pooled[~mask])) >= observed - tolerance:
                extreme += 1
            count += 1
        return mean_difference(a, b), extreme / count

    rng = rng if rng is not None else np.random.default_rng(0)
    for _ in range(n_random):
        shuffled = rng.permutation(pooled)
        if abs(mean_difference(shuffled[:n_a], shuffled[n_a:])) >= observed - tolerance:
            extreme += 1
    # +1 in numerator and denominator: the real split counts as one of the shuffles
    return mean_difference(a, b), (extreme + 1) / (n_random + 1)


def min_permutation_p(n_a, n_b):
    """Smallest two-sided p-value an exact permutation test can give: 2 / C(n_a + n_b, n_a).

    Example: 4 vs 4 laps -> 2 / 70 = 0.029; 2 vs 4 -> 2 / 15 = 0.13.
    """
    return 2.0 / math.comb(n_a + n_b, n_a)


def bootstrap_ci(a, b, rng=None, n_boot=10000, level=0.95):
    """Percentile bootstrap confidence interval for mean(a) - mean(b).

    Resample each driver's laps with replacement (same group sizes), recompute
    the difference, repeat n_boot times; the middle 95 % of those differences
    is the interval. With very few laps (2-4) the bootstrap is rough: it can't
    know about variation it never saw. Say so when reporting.
    """
    rng = rng if rng is not None else np.random.default_rng(0)
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    differences = np.empty(n_boot)
    for i in range(n_boot):
        differences[i] = np.mean(rng.choice(a, size=len(a))) - np.mean(rng.choice(b, size=len(b)))
    tail = (1.0 - level) / 2.0 * 100
    return float(np.percentile(differences, tail)), float(np.percentile(differences, 100 - tail))


def hedges_g(a, b):
    """Effect size: difference of means divided by the pooled standard deviation, small-sample corrected.

    Cohen's d = (mean_a - mean_b) / pooled_sd. With few laps d is biased upward,
    so Hedges multiplies by J = 1 - 3 / (4 (n_a + n_b) - 9).
    Example: a = [1, 2, 3], b = [3, 4, 5]: d = -2 / 1 = -2.0, J = 1 - 3/15 = 0.8 -> g = -1.6.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n_a, n_b = len(a), len(b)
    pooled_var = ((n_a - 1) * np.var(a, ddof=1) + (n_b - 1) * np.var(b, ddof=1)) / (n_a + n_b - 2)
    if pooled_var == 0:
        return float("nan")
    d = mean_difference(a, b) / math.sqrt(pooled_var)
    correction = 1.0 - 3.0 / (4.0 * (n_a + n_b) - 9.0)
    return float(d * correction)


def holm(p_values):
    """Holm-adjusted p-values (controls the chance of ANY false positive among the tests).

    Sort the p-values; multiply the smallest by m, the next by m-1, ...; then
    make the sequence non-decreasing; cap at 1.
    Example: [0.01, 0.04, 0.03] -> [0.03, 0.06, 0.06].
    """
    p = np.asarray(p_values, dtype=float)
    m = len(p)
    order = np.argsort(p)
    adjusted = np.empty(m)
    running_max = 0.0
    for rank, index in enumerate(order):
        value = min(1.0, (m - rank) * p[index])
        running_max = max(running_max, value)
        adjusted[index] = running_max
    return adjusted


def benjamini_hochberg(p_values):
    """Benjamini-Hochberg adjusted p-values (controls the expected share of false discoveries).

    Sort the p-values; multiply the k-th smallest by m / k; then, from the
    largest down, make the sequence non-increasing; cap at 1.
    Example: [0.01, 0.04, 0.03] -> [0.03, 0.04, 0.04].
    """
    p = np.asarray(p_values, dtype=float)
    m = len(p)
    order = np.argsort(p)
    adjusted = np.empty(m)
    running_min = 1.0
    for rank in range(m - 1, -1, -1):
        index = order[rank]
        value = min(1.0, p[index] * m / (rank + 1))
        running_min = min(running_min, value)
        adjusted[index] = running_min
    return adjusted


def icc_oneway(values, groups):
    """ICC(1): the share of variation that is BETWEEN groups (drivers) rather than within (laps).

    One-way ANOVA:
      MSB = between-group mean square, MSW = within-group mean square,
      k0  = the "average" group size (adjusted for unequal sizes),
      ICC = (MSB - MSW) / (MSB + (k0 - 1) MSW)
    ICC near 1: drivers differ much more than their laps vary (a stable,
    distinctive feature). Near 0 (or negative): mostly lap-to-lap noise.
    With only 2 drivers this is a very rough estimate.
    """
    values = np.asarray(values, dtype=float)
    groups = np.asarray(groups)
    labels = list(dict.fromkeys(groups))
    n_total = len(values)
    grand_mean = np.mean(values)
    sizes = []
    ss_between = 0.0
    ss_within = 0.0
    for label in labels:
        group_values = values[groups == label]
        sizes.append(len(group_values))
        ss_between += len(group_values) * (np.mean(group_values) - grand_mean) ** 2
        ss_within += np.sum((group_values - np.mean(group_values)) ** 2)
    k = len(labels)
    ms_between = ss_between / (k - 1)
    ms_within = ss_within / (n_total - k)
    sizes = np.array(sizes, dtype=float)
    k0 = (n_total - np.sum(sizes ** 2) / n_total) / (k - 1)
    denominator = ms_between + (k0 - 1) * ms_within
    return float((ms_between - ms_within) / denominator) if denominator > 0 else float("nan")


def min_detectable_effect(n_a, n_b, alpha=0.05, power=0.8):
    """Smallest effect size d that a two-sided two-sample t-test detects with the given power.

    Uses the noncentral t distribution: with effect d, the t statistic is
    centred at d * sqrt(n_a n_b / (n_a + n_b)). We search (bisection) for the
    d whose rejection probability equals `power`.
    Example: 6 vs 6 laps -> d = 1.77; 10 vs 10 -> 1.32; 20 vs 20 -> 0.91.
    """
    df = n_a + n_b - 2
    t_crit = scipy_stats.t.ppf(1 - alpha / 2, df)
    scale = math.sqrt(n_a * n_b / (n_a + n_b))

    def achieved_power(d):
        nc = d * scale
        return (1 - scipy_stats.nct.cdf(t_crit, df, nc)) + scipy_stats.nct.cdf(-t_crit, df, nc)

    low, high = 0.0, 20.0
    for _ in range(100):
        middle = (low + high) / 2
        if achieved_power(middle) < power:
            low = middle
        else:
            high = middle
    return (low + high) / 2

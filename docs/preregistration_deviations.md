# Deviations from the preregistration

`docs/preregistration.md` is left exactly as committed (commit `ab2510c`,
2026-10-16). Every later correction or deviation is recorded here, with the
date and its effect on the results.

## 2026-10-17 — Part A: wrong minimum p-value for unequal group sizes (text only)

**What the preregistration said:** the smallest possible p-value is 2/35 = 0.057
for 3 vs 4 laps and 2/15 = 0.13 for 2 vs 4.

**Correct values:** 1/35 = 0.029 for 3 vs 4, and 1/15 = 0.067 for 2 vs 4.
(4 vs 4 stays 2/70 = 0.029.) The "2" counts the mirror-image split (groups
swapped), which only exists when both groups have the same size.

**How it was found:** the T9 full-throttle test (3 vs 4 laps) returned
p = 0.029, below the stated "minimum" of 0.057. `stats.min_permutation_p` was
corrected and given a test (`test_minimum_p_for_unequal_groups_has_no_mirror_split`).

**Effect on the results:** none on the tests themselves. The permutation test
always computed the right p-values; only the reported "minimum possible p"
column and the sentence in the preregistration were wrong. The preregistered
conclusion still holds: Benjamini–Hochberg over 27 tests found **0
discoveries**, and could not have found one with these lap counts.

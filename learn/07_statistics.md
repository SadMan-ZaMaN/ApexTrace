# 7. Statistics and preregistration (Phase 5)

> From plots to evidence. Code: `stats.py` (tests in `tests/test_stats.py`).
> Plan: `docs/preregistration.md`. Script: `experiments/06_pilot_stats.py`
> (it refuses to run until the preregistration is committed).

## Preregistration: why the order matters

If you run 27 tests, look at the results, and then decide which test or
correction to report, you can almost always find something "significant" by
luck. This is called p-hacking, or the garden of forking paths. A
**preregistration** fixes the plan (data, features, tests, corrections,
thresholds) in a dated document **committed to git before the tests run**. The
commit date is the proof. `06_pilot_stats.py` checks with `git` that the file is
committed and unchanged; otherwise it stops.

## The methods, each answering one question

**Permutation test** ("could shuffling the labels give a difference this big?").
Pool both drivers' laps. If the driver didn't matter, any split into groups of
the same sizes is equally likely. Compute the difference for every split (4 + 4
laps: C(8,4) = 70 splits). p = share of splits at least as extreme as the real
one. It makes no assumption of normality, which suits tiny samples.

**The minimum possible p-value:** with 70 splits, the real split and its mirror
image (groups swapped) are the most extreme possible, so p ≥ 2/70 = 0.029. With
unequal groups there is no mirror split, so the minimum is 1/C: 3 vs 4 laps →
1/35 = 0.029, 2 vs 4 → 1/15 = 0.067. (Our preregistration first wrote 2/C for
every case; the correction is in `docs/preregistration_deviations.md`. A
deviations file, instead of editing the preregistration, is how you stay honest.)

**Bootstrap confidence interval** ("how much could the difference wobble?").
Resample each driver's laps *with replacement*, recompute the difference,
repeat 10,000 times; the middle 95 % is the interval. Weakness: with 2–4 laps
it only knows the variation it has seen.

**Effect size, Hedges' g** ("how big, in units of spread?"). Cohen's d =
difference / pooled standard deviation, times a small-sample correction
J = 1 − 3/(4(n_a + n_b) − 9).

**Multiple comparisons.** With 27 tests at α = 0.05, about 1.35 false positives
are expected by luck alone.
- *Holm* controls the chance of **any** false positive (strict).
- *Benjamini–Hochberg (BH)* controls the expected **share** of false
  discoveries (less strict). Preregistered here: BH at 0.05.

**ICC(1), intraclass correlation** ("what share of the variation is between
drivers?"). From a one-way ANOVA: ICC = (MSB − MSW)/(MSB + (k₀ − 1)MSW). Near 1
= stable and distinctive; near 0 = mostly lap-to-lap noise. With 2 drivers it is
very rough; the real H1 comes with all drivers (Phase 6).

**Statistical power** ("could we even detect it?"). Power = the chance a test
detects a real effect. For a two-sample t-test at α = 0.05 and 80 % power, the
smallest detectable effect is: 4 vs 4 laps → d = 2.38; 6 vs 6 → 1.77;
10 vs 10 → 1.32; 20 vs 20 → 0.91 (`stats.min_detectable_effect`, computed with
the noncentral t distribution).

## The honest conclusion stated before running

With 4 vs 4 laps, the minimum p = 0.029, and BH over 27 tests would need 16
tests at that minimum to make even one discovery. **The pilot cannot produce a
discovery, whatever the truth.** Its value is effect sizes and intervals, and a
tested pipeline. Confirmatory tests need many sessions (Phase 6 onwards).

## How the tests were checked (`tests/test_stats.py`)

- Exact small example: [1, 2] vs [3, 4] → p = 2/6.
- Same-distribution groups: about 5 % of p-values below 0.05 (400 trials).
- Bootstrap interval covers a known shift about 95 % of the time (300 trials).
- ICC by hand: groups [1, 3] and [5, 7] → 14/18 = 0.778.
- Power: 6/10/20 laps per driver → 1.77/1.32/0.91, as the plan said.

## What the pilot tests found (`results/06_pilot_stats/`)

- **0 discoveries of 27** after Benjamini–Hochberg, exactly as stated in advance.
- Largest effects: brake onset +7.42 m at T5 (g +2.16, p = 0.057) and +7.20 m at
  T9 (g +1.92, p = 0.057); full throttle at T9 −56.7 m (g −4.43, p = 0.029,
  the minimum possible).
- **Looking at the raw data behind the biggest effect** (always do this): at
  T9 Piastri holds 80–95 % throttle for ~50–80 m and then reads 99 % for
  ~100 m, so a fixed 99 % threshold exaggerates the gap. A threshold-free
  feature would be more robust.
- **H1:** minimum speed varies from lap to lap by 2–12× its measurement error,
  so laps genuinely differ. Brake onset in qualifying is often at the
  measurement-error level. ICC with only 2 drivers has very wide intervals.
- Verdict: *consistent with* Norris braking ~7 m later at T5 and T9, *not confirmed*.

# 10. Repeatability and identification with all drivers (Phase 6, part 3)

> H1 (is a feature repeatable?) and H3 (can a model tell drivers apart on race
> weekends it never saw?) on the 2023–2024 dry qualifying data (21,493 clean
> rows, 44 sessions, 25 drivers). Code: `identification.py`, `stats.py`
> (`icc_from_group_stats`). Experiments: `11_repeatability.py`,
> `12_identification.py`.

## H1: two different repeatability questions

The **ICC** (intraclass correlation) is the share of variation that lies
*between* groups rather than *within* them. Which groups you choose decides
which question you answer:

| Level | Groups | Question |
|---|---|---|
| Lap level | (session, corner, driver) | At the same corner on the same day, do a driver's laps look like each other more than like other drivers' laps? |
| Weekend level | each driver's session mean, grouped by (driver, season) | Does a driver's offset from the field **persist from one weekend to the next**? This is the real "signature" question. |

Both include the car: drivers of different teams drive different cars.

### Results (`results/11_repeatability/`)

| | Lap level | Weekend level |
|---|---|---|
| Brake onset, slow corners | 0.45 [0.35, 0.52] | **0.04** [0.01, 0.07] |
| Minimum speed, slow / medium / fast | 0.33 / 0.43 / 0.23 | **0.23 / 0.30 / 0.40** |
| Throttle 10 %, medium corners | 0.37 | 0.38 |
| All features, overall range | 0.15–0.58 | 0.04–0.40 |

**What this means:**
- On the same day, drivers are clearly distinguishable: 15–58 % of the
  variation is between drivers.
- Across weekends, much less of it persists. **Braking points are
  distinctive on the day but hardly persist** (0.04–0.08): where a driver
  brakes relative to the field changes from track to track. **Minimum speed
  and throttle persist best.**
- **Measurement error is not the bottleneck.** Lap-to-lap variation is 5–25×
  the Phase 2 measurement error: brake onset varies 16.6 m between laps
  (error ~3 m); minimum speed 2.7 km/h (error 0.35 km/h). The variation is
  real driving and conditions, not noise from the 4 Hz feed.

### How the uncertainty was computed, and a mistake caught on the way

Laps of the same session aren't independent, so the bootstrap resamples
**whole sessions** for the lap-level ICC. For the weekend-level ICC, a first
version also resampled sessions. A session drawn twice then gave each
driver two *identical* weekend means, which looks like perfect consistency
and pushed the ICC up. The symptom: estimates fell **outside their own
intervals** (e.g. 0.04 with an interval of [0.05, 0.38]). The fix: resample the
units the ICC is built on (driver-seasons). **Lesson: resample the level at
which your observations are independent, and always check that the estimate
sits inside its interval.**

Speed: the ICC only needs each group's size, mean and within-group sum of
squares, so the bootstrap resamples rows of a small summary table
(`stats.icc_from_group_stats`). 9.6 minutes became 13 seconds, with more resamples.

## H3: identification on race weekends the model never saw (`results/12_identification/`)

**Setup.** One row per lap: the lap's mean field-relative value of each feature
per corner type (30 numbers, comparable across tracks). **Leave-one-session-out:**
train on all weekends but one, test on the held-out weekend, repeat. A lap never
helps predict its own weekend. Everything that uses labels (model weights, the
fill-in values for missing features, the scaling) is fitted on training weekends
only. The field-relative step uses the held-out weekend's own median, but no
driver names: that's available at prediction time, so it isn't leakage.

**Leakage** = test information reaching the training, which makes results look
better than they are. Our guard: an `assert` that a session is never on both
sides, plus a **shuffled-label check**: with the driver labels shuffled inside each
weekend, the model must score at chance. It does (0.500).

**Balanced accuracy** = the average of each driver's accuracy, so a driver with
more laps doesn't dominate. Chance = 0.5 for two teammates.

### Task (a): teammates (same car), 20 team-seasons

| Method | Mean balanced accuracy [95 % interval] |
|---|---|
| Majority class | 0.485 |
| Lap time only | 0.565 [0.538, 0.592] |
| **Our corner features** | **0.685** [0.654, 0.716] |
| Our features, weekend vote (a driver's laps in a held-out weekend vote) | **0.763** [0.734, 0.794] |
| Raw lap statistics (mean/max speed, mean throttle, % full throttle, % braking) | 0.729 [0.680, 0.780] |
| Shuffled labels | 0.500 [0.493, 0.507] |

- Ours beats lap time in **18 of 20** team-seasons (Wilcoxon signed-rank test
  p = 0.0001). The Wilcoxon test compares paired results (same team-season,
  two methods) without assuming normal distributions.
- Ours vs raw lap statistics: not significantly different (ours better in 8 of
  20, p = 0.14).
- **Ablation** (remove one feature group): without throttle features 0.633
  (the biggest drop); without braking 0.674; without speeds 0.707 (slightly
  better: those features add noise for teammates). **Throttle carries the
  teammate signature**, consistent with H1.

### The surprise, investigated

Each raw statistic was then tested on its own. The strongest single one is
**the share of samples with the brake flag on** (0.610 on average), and it
explains the most extreme pairs: alone, it separates Gasly and Ocon at Alpine
at 0.92 (2023) and 0.88 (2024), and their difference has the same sign in
94.7 % and 100 % of weekends. Maximum speed alone is useless (0.502), so the
first guess (wing setup) was wrong. The full baseline (0.729) comes from
combining all five statistics.

Is "share of braking" a **driving habit** (staying on the brakes longer) or a
**car property** (where each car's brake sensor switches on)? The 2023–24 data
can't tell: the regular drivers didn't change teams between those seasons. This
is exactly what the **driver-vs-car** analysis (H4) is for.

### Task (b): all drivers of a season (confounded by the car)

2023: 21 drivers, chance 0.048: our features 0.245, raw statistics 0.326, lap
time 0.079. 2024: 22 drivers, chance 0.045: ours 0.240, raw 0.287, lap time
0.087. That's about 5× chance, but much of it can be the car (two cars differ
even with identical driving), so task (a) is the main evidence.

### Honest summary of H3 (development data, 2023–24)

Corner features identify teammates on unseen weekends clearly above chance
and above lap time, but not better than simple whole-lap telemetry statistics.
Part of what any of these methods detect may be the car (sensor calibration,
setup) rather than the driver. The final, preregistered test will be on 2025, run once.

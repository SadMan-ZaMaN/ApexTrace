# 1. The big picture

## The project in one paragraph

Every F1 car sends about four readings per second to the public timing feed:
speed, throttle, brake (on/off only), gear, RPM, and position. Each one is a
**signal over time**. ApexTrace takes two teammates' laps (same car, same
session), cuts out the same few corners, lines the laps up by position on
the track, and measures things like where braking starts, the slowest speed,
and when the throttle comes back on. Then it asks, carefully:

1. Is each driver consistent from lap to lap? (**H1, repeatability**)
2. Are the two teammates measurably different, by more than our measurement
   error? (**H2, distinguishability**)
3. Can a model tell who drove a lap it has never seen, from a race weekend it
   was never trained on? (**H3, generalisation**)
4. Is the "signature" the driver's or the car's? (**H4**, using drivers who
   changed teams)

It never tries to decide who is the *better* driver.

## Why this is research, not a dashboard

Lots of people make F1 telemetry dashboards. What makes this research:

| Dashboard | ApexTrace |
|---|---|
| "Norris brakes later than Piastri at Turn 6" | "Driver A's brake point is X m later, with a 95 % confidence interval of [L, U] m; our measurement error is Y m per lap, so the difference is / isn't bigger than the error" (X, L, U, Y come from the scripts) |
| Uses the data as if it were exact | Measures how wrong the data can be (Phase 1) and how accurate each estimator is (Phase 2) |
| Looks at a few laps | Tests on whole race weekends the model never saw (Phase 6) |
| Can't say if a difference is the driver or the car | Uses drivers who changed teams (Phase 7) |

The key idea: **a number without an error bar is not a measurement.**

## The research question

> Can signal-processing techniques extract **repeatable, interpretable driving
> signatures** from low-rate public F1 telemetry, explain corner-level
> differences between drivers, and identify drivers on **unseen sessions**,
> and how much of that signature belongs to the **driver rather than the car**?

A *hypothesis* is a claim we test, not a claim we believe. "No" is a valid
answer: "corner features are not repeatable enough to identify drivers" would
be a publishable negative result, if measured carefully.

## The plan (phases)

| Phase | Question | Status |
|---|---|---|
| 0 Setup | Does the environment work? | Done |
| 1 Data pilot | What is the data, really? | Done: `docs/data_report.md` |
| 2 Measurement science | How accurately can we measure each feature? | Done: error table |
| 3 Alignment | How do we put all laps on one distance axis? | Done: complementary filter, 1.15 m |
| 4 Features | Norris vs Piastri at three corners (descriptive) | Done: `docs/writeups/norris_vs_piastri.md` |
| 5 Statistics | H1, H2 with confidence intervals | Done: preregistered, 0 of 27 (as predicted) |
| 6 Identification | H3 on all 2023–2024 qualifying sessions | Done: chapter 10 |
| 7 Driver vs car | H4; final one-time test on 2025 | Done: H3 replicated, H4 not supported (chapter 12) |
| 8 Write-up | Report, README, app | Done: `docs/report.md`, the web app |
| Extension | H5: does the signature survive the 2026 rules? | Being planned (Oct–Nov 2026) |

## The four candidate contributions (what could be new)

- **C1 Measurement:** how accurately can corner features be measured from
  ~4 Hz public telemetry? Quantified with a realistic simulation. *(Phase 2)*
- **C2 Repeatability:** which features are stable across laps and sessions?
- **C3 Identification done honestly:** held-out sessions, proper baselines
  (including "lap time only"), ablations.
- **C4 Driver vs car:** separating the two using team changers.

The closest existing work (see `docs/related_work.md`) clusters drivers from
one fastest lap each, and has no held-out test, no error analysis and no
team-change analysis. That gap is where ApexTrace sits.

## Research habits used here (and why faculty like them)

- **Research log** (`docs/research_log.md`): a dated diary of what was tried
  and what happened, including failures.
- **Decision log** (`docs/decisions.md`): every choice, with the reason and
  the date. Anyone can check that a choice was made *before* seeing a result.
- **Preregistration** (Phase 5): the statistical tests are written down and
  committed to git *before* running them. The commit date is the proof.
  This protects against "trying tests until one looks significant".
- **Frozen test set:** the 2025 season is not touched until the very end, and
  then used once. The code refuses to load it (`load_session`).
- **Tests on synthetic data with a known answer** before trusting real data.
- **Numbers come only from scripts**, never typed in by hand.

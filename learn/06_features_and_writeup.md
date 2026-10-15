# 6. Features and the first write-up (Phase 4)

> Turning aligned corner traces into numbers: one row per (driver, lap, corner).
> Code: `features.py`. Experiment: `05_pilot_features.py` → `results/05_pilot_features/`.
> Write-up (output A): `docs/writeups/norris_vs_piastri.md`.

## The features (all distances in metres from the corner marker; negative = before it)

| Feature | Meaning | How it's measured (estimator chosen in Phase 2) |
|---|---|---|
| `brake_onset_m` | where braking starts | bend of the speed curve, inside the brake off→on interval |
| `entry_speed_kmh` | speed 200 m before the marker (on the straight) | linear interpolation |
| `min_speed_kmh`, `apex_m` | slowest speed and where | parabola through the 3 lowest samples |
| `braking_distance_m` | apex − brake onset | derived |
| `mean_decel_ms2` | (speed at onset − min speed) / time from onset to apex | derived; replaces peak deceleration (not measurable) |
| `throttle_pickup_m` | throttle first reaches 10 % after braking | interpolated crossing |
| `full_throttle_m` | throttle first reaches 99 % | interpolated crossing |
| `exit_speed_kmh` | speed 150 m after the marker | linear interpolation |
| `corner_time_s` | time from −200 m to +150 m | interpolated times |
| `min_gear` | lowest gear in the window | minimum |

**Rule:** events are found in *time* on the raw samples, then turned into track
positions with the fused coordinate (chapter 5). Thresholds (10 %, 99 %) were
fixed in the original plan and never tuned to make a difference appear.

**Dropped (honestly):** peak deceleration (Phase 2: unmeasurable), and coast time
and throttle time constant (not yet validated on synthetic data).

## Uncertainty words

- **Lap-to-lap standard deviation:** how much one driver's value changes from
  lap to lap = real variation + measurement error.
- **Standard error (SE) of a mean:** std / √n, the uncertainty of the driver's
  average.
- **SE of a difference of two means:** sqrt(SE_a² + SE_b²).
- **Per-lap measurement error:** from the Monte Carlo (estimator) combined with
  the alignment noise: sqrt(estimator_std² + 1.15²) for distances.

## What the pilot shows (qualifying, descriptive only)

| Corner | Brake onset NOR vs PIA | Laps | Comment |
|---|---|---|---|
| T5 | NOR 7.42 m later (SE 2.11) | 4 vs 4, same laps | cleanest comparison |
| T9 | NOR 7.20 m later (SE 2.05) | 3 vs 4 | NOR's Q1 lap lost to a feed gap |
| T6 | NOR 3.06 m later (SE 6.22) | 4 vs 2 | PIA's 2 laps are both Q3: inconclusive |

Minimum speeds agree within 0.5 km/h; corner times within 0.03 s.

## Writing honestly for fans (output A)

The write-up separates **what we measured** from **what we can't say**: no
statistical test yet, few laps, laps from different qualifying segments
(confounders: track grip and tyre wear change from Q1 to Q3), no "better driver"
language, no racing lines (the position feed can't show them), brake is on/off.

A **confounder** is something other than the driver that changes the result.
Here: at T6, Piastri's usable laps are all from Q3 (more grip), Norris's include
Q1 and Q2. Always check who was compared with what.

## Sanity checks done by eye

`corner_events_Q.png`: brake markers (▽) sit where the speed starts to fall,
apex markers (○) at the bottom, throttle markers (□) just around the apex. At T9
the throttle comes on *before* the slowest point (partial throttle in a fast
corner), which is plausible.

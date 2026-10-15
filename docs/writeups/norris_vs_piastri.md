# Norris vs Piastri at three corners: what four laps of public telemetry can (and can't) say

*2024 Abu Dhabi GP qualifying, McLaren teammates. A descriptive pilot from the
ApexTrace project. Every number comes from `experiments/05_pilot_features.py`
(table: `results/05_pilot_features/summary.md`). Draft written 2026-10-16;
for review before sharing.*

## The question

Norris took pole by 0.209 s from Piastri. Same car, same session. Where on the
track do their driving inputs differ, and can public telemetry, which arrives
only about four times per second, even see the difference?

## How we measured

- **Data:** the public timing feed via FastF1. Speed in whole km/h, throttle
  in whole %, brake only on/off, about 3.8 samples per second. At 300 km/h
  that's one sample every 13–47 m.
- **Laps:** each driver's four push laps (one in Q1, one in Q2, two in Q3).
  A lap is skipped at a corner when the live feed paused inside that corner
  (it happened twice to Piastri at Turn 6).
- **Corners:** chosen by a fixed rule *before* comparing the drivers: Turn 6
  (the heaviest braking, 324 → 68 km/h), Turn 5 (medium, 294 → 108 km/h) and
  Turn 9 (the fastest braking corner, 320 → 181 km/h).
- **Placing events between samples:** the braking point is where the speed
  curve bends (a two-line fit), the apex is the bottom of a parabola through
  the three slowest samples, and the throttle pickup is where the throttle
  crosses 10 %.
- **Error bars first:** on 3,000 simulated laps degraded exactly like the feed,
  a single lap's braking point is accurate to about **3 m** (plus an
  alignment uncertainty of about 1 m), the minimum speed to about
  **0.35 km/h**, and the throttle pickup to **1.5–3 m**.

## What the numbers show (qualifying, mean of each driver's usable laps)

| Corner | Feature | Norris | Piastri | Difference (NOR − PIA) | Uncertainty of the difference (SE) |
|---|---|---|---|---|---|
| T5 | Braking point (m before the corner marker) | 110.7 | 118.1 | Norris **7.4 m later** | 2.1 m |
| T9 | Braking point | 157.4 | 164.6 | Norris **7.2 m later** | 2.0 m |
| T6 | Braking point | 117.3 | 120.4 | Norris 3.1 m later | 6.2 m (Piastri: 2 laps) |
| T5 | Minimum speed (km/h) | 105.5 | 105.3 | +0.2 | 1.5 |
| T6 | Minimum speed | 68.1 | 68.4 | −0.3 | 0.8 |
| T9 | Minimum speed | 178.5 | 179.0 | −0.4 | 2.7 |
| T6 | Throttle pickup (m after the marker) | 13.8 | 10.2 | Norris 3.5 m later | 1.2 m |
| T6 / T5 / T9 | Time from 200 m before to 150 m after the marker (s) | 8.49 / 7.09 / 5.66 | 8.47 / 7.08 / 5.69 | +0.02 / +0.01 / −0.03 | 0.06 / 0.06 / 0.04 |

*SE = standard error: how uncertain the difference of the two averages is,
given how much each driver's laps vary. Laps: Norris 4 at T6 and T5 and 3 at
T9; Piastri 2 at T6 and 4 at T5 and T9.*

**In plain words:**

1. **Braking:** at Turns 5 and 9, Norris's average braking point is about
   7 m later than Piastri's. That's about 3.5 times the uncertainty of the
   difference, and larger than one lap's measurement error (~3 m). Turn 5
   is the cleanest comparison: both drivers have the same four laps there.
   At Turn 6 the comparison is inconclusive, because only two of Piastri's
   laps there are usable.
2. **Minimum speed:** the two are almost identical, within half a km/h at
   every corner. Braking later did not show up as a different minimum speed.
3. **Time through the corners:** identical within 0.03 s per corner. Over
   these three corners the 0.209 s pole margin is not visible. It was made
   elsewhere on the lap, or is spread too thinly to see here.
4. **Turn 6 exit:** Norris got back on the throttle about 3.5 m later
   (but Piastri's two Turn 6 laps are both from Q3; see below).

## What we can't say (yet)

- **Nothing here is a statistical test.** With 2–4 laps per driver, only very
  large effects could be confirmed. The tests are written down (preregistered)
  *before* they are run, in the next phase.
- **Not all laps are comparable.** Q1, Q2 and Q3 laps differ in track grip
  and tyre wear. At Turn 5 both drivers have the same four laps (Q1, Q2 and
  two in Q3). At Turn 6 both usable Piastri laps are from Q3, while Norris's
  include Q1 and Q2. At Turn 9 Norris has no usable Q1 lap, while Piastri
  does. Those two comparisons are less clean.
- **"Later braking" isn't "better".** This compares driving inputs, not skill.
  A later braking point can come with a different line, which this data can't
  see: the position feed is too smooth to show racing lines.
- **The brake channel is on/off.** We can't see brake pressure or how it is released.
- **One session, one track, one pair of drivers.** Whether these differences
  are a stable "signature" is exactly what the rest of the project tests,
  over 2023–2024.

## Figures

- `results/05_pilot_features/corner_events_Q.png`: every usable lap's speed
  through the three corners, with the braking point (▽), apex (○) and throttle
  pickup (□) located between samples.
- `results/05_pilot_features/features_Q.png`: each lap as a dot, with each
  driver's mean and one lap's measurement error.
- `results/04_alignment/corners_Q.png`: all laps aligned on one distance axis.

*Data: FastF1 (unofficial, not affiliated with Formula 1). Charts are made from
timing data only.*

# 5. Alignment (Phase 3): one distance axis for every lap

> To compare braking points, "metre 2,520" must be the same spot on the track
> in every lap. Code: `alignment.py`, `track.py`, `corners.py`.
> Experiment: `04_alignment.py` → `results/04_alignment/`.

## The problem

Distance from integrating speed **drifts** (Phase 1: up to 9 m on a qualifying
lap with a feed gap), and a feed gap *before* a corner shifts everything after
it. Differences between drivers are only a few metres.

## Idea 1: project positions onto a reference path

Take the X/Y path of one lap (Norris's pole lap), measure distance along it
(s, from 0 at the timing line to 5,230.9 m). For every position sample of any
lap, find the nearest point on that path: its s says how far along the track
the car is. It doesn't integrate anything, so it can't drift.

**How projection works:** for each segment of the path, project the point onto
the segment's line (dot product), clamp to the segment's ends, measure the
distance; keep the closest segment; s = s at the segment start + fraction ×
segment length. To stop a point snapping to another part of the track that
happens to be close (a hairpin), only segments within ±200 m of where the
integrated distance says the car should be are tried.

Car samples (speed, brake, ...) come at different moments than position
samples, so a car sample's s is interpolated in time between the position
samples around it.

## The surprise: X/Y is noisy *along* the track

Over each ~0.26 s position interval, X/Y distance and integrated-speed distance
disagree by **4.5 m** (std). Integrated speed is accurate to centimetres over
0.26 s, so each position sample carries ~3 m of noise along the track. The
residual is larger for longer intervals, and there's no constant lag between
the streams, which points to **jitter in the position timestamps** (~40 ms;
at 80 m/s that's ~3 m). That's a hypothesis that fits the evidence.

## Idea 2: the complementary filter (what we actually use)

| | Short-term (metre to metre) | Long-term (over a lap) |
|---|---|---|
| Integrated speed d | excellent (cm) | drifts, jumps at feed gaps |
| X/Y projection s | noisy (~3 m) | no drift |

Take the best of each: inside each corner window, keep d's shape and pin it to
the X/Y frame with **one offset** = the average of (s − d) over the window's
~37 position samples:

    fused(t) = d(t) + mean(s_pos - d_pos)

Averaging N noisy samples shrinks noise like 1/√N. Same idea as fusing GPS
(drift-free, noisy) with an inertial sensor (smooth, drifts) in a phone or a
drone: a **complementary filter** takes low frequencies from one sensor and
high frequencies from the other.

**Inverse-variance weighting:** if the error is speed × timing jitter, a sample
at 70 km/h is ~4× more precise than one at 300 km/h. So each sample is weighted
by 1/speed²: trust each measurement in proportion to its precision. Measured
offset noise: **1.46 m → 1.15 m**.

**How do we know the offset noise without the truth?** The *half-split check*:
compute the offset from the first half of the window's position samples and
from the second half. If each half's offset has noise σ, their difference has
noise √2·σ, and the full-window offset (twice the samples) about σ/√2. So
offset noise ≈ std(half difference) / 2 = 2.29 / 2 = 1.15 m.

## Checks that it worked

- Points lie a median **0.05 m** from the reference path; s ran backwards once.
- **Sampling phase is uniform:** where a fixed track point falls inside its
  sampling interval is uniform between 0 and 1 (480 cases, Kolmogorov–Smirnov
  test p = 0.43). The KS test compares a sample's distribution with a reference
  one; a large p means "no evidence they differ". This is the assumption
  behind "averaging N laps shrinks the error like 1/√N".
- Aligned overlays (`corners_Q.png`) line up within a few metres in the braking zones.

## Cross-correlation (and why it is only a diagnostic)

Slide one lap's speed-vs-distance trace over the reference's; the shift with
the highest *normalised* correlation (Pearson correlation of the overlap, −1 to
1) is the misalignment. The peak is refined between grid points by a parabola
through the top three values (offset = 0.5(y₋ − y₊)/(y₋ − 2y₀ + y₊)), the
same trick as Consonance's autocorrelation pitch detector. Test: a 7.3 m shift
on a 1 m grid is recovered to < 0.1 m.

**The trap:** if you cross-correlate *each corner's* braking zone, a driver who
brakes 5 m later gets "corrected" by 5 m and the difference disappears. So it's
only used over whole laps, as a check.

## Errors so far, per lap at the heavy-braking corner

| Source | Size |
|---|---|
| Brake-onset estimator (Phase 2) | bias +3.2 m, std 2.7 m |
| Alignment offset (Phase 3) | std ~1.15 m |
| Combined random error | sqrt(2.7² + 1.15²) ≈ 2.9 m per lap |

The +3.2 m bias is the same for every lap (if drivers ramp the brakes alike),
so it cancels when comparing two drivers.

# 3. The data (Phase 1): what the timing feed really is

> Analogy: before you design a filter, you measure the noise. Phase 1 measures
> the data before anything is built on it. Full results: `docs/data_report.md`.
> Script: `experiments/01_data_pilot.py`. Numbers: `results/01_data_pilot/summary.json`.

## The pilot data

2024 Abu Dhabi GP, qualifying (the comparison: low fuel, soft tyres, full
push) and FP2 (practice: used only for repeatability, on matched runs,
because teammates may run different fuel and tyre programmes). Norris (NOR)
and Piastri (PIA), McLaren teammates: same car, so differences are more
likely to be the driver.

## 1. Sampling: not "3.7 Hz", but a 40 ms clock

- Car data arrives **3.77 times per second on average** (mean interval 0.265 s).
- Every interval is a whole number of **40 ms clock ticks** (100 % within 2 ms):
  usually 4 to 14 ticks (0.16–0.56 s). Position data runs on a 20 ms clock.
- At 300 km/h (83.3 m/s) that's **13 to 47 m between samples** (mean 22 m).

**Nyquist:** with ~3.8 samples/s, nothing faster than ~1.9 Hz can be seen
(vibration, steering corrections: impossible). Upsampling to 50 Hz creates no
information; it only draws straight lines between samples.

## 2. Feed gaps: the live feed pauses

36 gaps of 0.64–1.36 s in 30 laps. **Every one** happens at the same moment
in the position data, and both drivers lose data at the same session times:
the whole feed paused, not one car. A 1.36 s gap at 300 km/h = 113 m with no
data. One gap falls in Piastri's Turn 6 braking zone (295 → 139 km/h across
it). **Rule:** a lap is not used at a corner if a gap falls in that corner's
window (decisions.md).

## 3. The inspection paradox (why the naive error bar is too small)

With an on/off channel (brake), we only know the event happened somewhere
inside one sampling interval. If we report the middle of the interval, the
error is uniform over the interval, and its standard deviation is

    interval / sqrt(12)        (same maths as quantisation noise: step / sqrt(12))

With **irregular** intervals, the event is more likely to land in a *long*
interval, because long intervals cover more time. (Same reason a random bus
you wait for seems to come less often than the timetable says.) So each
interval is weighted by its length:

    error std = sqrt( sum(T^3) / (12 * sum(T)) )

Real data: 0.093 s with gaps, 0.087 s without, against 0.077 s if sampling
were regular. At 300 km/h: **7.7 m vs 6.4 m**. Code:
`quality.event_timing_error_s`; test `test_event_timing_error_matches_a_monte_carlo_experiment`
drops 20,000 random events on irregular samples and checks the formula.

## 4. Resolution (quantisation)

Speed: whole km/h. Throttle: whole %. RPM: whole rpm. X/Y/Z: whole decimetres.
Brake: `True`/`False` only (braked in 14.8 % of samples).
Rounding to 1 km/h = noise with std 1/sqrt(12) = 0.29 km/h. Harmless for speed,
but differentiation amplifies it (chapter 4).

## 5. Position data can't show racing lines

Other laps lie a median 0.06 m from a driver's own path, and *exactly as close*
to the teammate's path, and FP2 laps to the qualifying path. Real lines differ
by more than that, so the feed is probably smoothed or matched to a track
model (hypothesis). Consequence: no racing-line analysis.

Code: `quality.distance_to_path` projects each point onto each segment of the
reference path and keeps the shortest distance.

## 6. Distance drifts

Distance comes from integrating speed. Lap lengths: mean 5,219 m (official
centre line 5,281 m; a racing line cuts corners, so shorter is expected).
Lap-to-lap spread around each driver's mean: ≤ 2.0 m on gap-free qualifying
laps, up to 9.0 m with a feed gap, up to 19 m in FP2. That's as big as the
effects we want to measure, so laps must be **aligned** (Phase 3).
FastF1's `add_distance()` misses the stretch from the last sample to the line
unless `interpolate_edges=True`.

## 7. Usable laps

Qualifying: **4 push laps per driver**. At Turn 6 only 2 of Piastri's are
gap-free. FP2: a matched 7-lap medium long run each. So the pilot can only be
*descriptive*; statistics need many sessions (Phase 6).

## 8. The three corners (chosen by a rule, before comparing drivers)

On Norris's pole lap: heavy braking = biggest speed drop → **T6** (324 → 68 km/h);
fast = highest minimum speed → **T9** (320 → 181); medium = minimum speed
closest to halfway → **T5** (294 → 108). Choosing by a fixed rule, *before*
looking at driver differences, avoids picking the corners where the drivers
happen to differ (a form of cherry-picking).

## Traps found

1. FastF1 docs say interpolated rows are `'interpolated'`; the code writes `'interpolation'`.
2. Slow-lap rule against the session best is biased (chapter 2).
3. `add_distance()` without `interpolate_edges=True` misses the end of the lap.

## Code walkthrough: `src/apextrace/quality.py`

| Function | What it does | Worked example |
|---|---|---|
| `sample_intervals(times)` | `np.diff`: time between samples | 0, 0.24, 0.40 → 0.24, 0.16 |
| `interval_summary(intervals)` | mean, median, percentiles, two rates | mean 0.265 s → 3.77/s |
| `event_timing_error_s(intervals)` | the length-weighted formula above | 0.27 s regular → 0.078 s |
| `share_on_grid(values, grid, tol)` | share of values near a multiple of `grid` | finds the 40 ms clock |
| `find_gaps(times, max)` | intervals longer than `max` | |
| `smallest_step(values)` | the resolution | speeds → 1 km/h |
| `path_length(x, y)` | sum of straight segments | square 10 × 10 → 40 |
| `distance_to_path(...)` | point-to-polyline distance | (4, 3) to the x-axis → 3 |

`experiments/01_data_pilot.py` has one function per check (`check_1_...` to
`check_10_...`). Read `main()` first, then each check.

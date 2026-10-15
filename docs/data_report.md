# Data report: what 2024 Abu Dhabi telemetry can and can't tell us

*Phase 1 (data pilot), written 2026-10-16. Every number here was printed by
`experiments/01_data_pilot.py` and is stored in
`results/01_data_pilot/summary.json`. Data: 2024 Abu Dhabi GP, qualifying and
FP2, Lando Norris (NOR) and Oscar Piastri (PIA), the 30 laps kept by
`select_laps()`.*

## The short version

- **Speed, throttle and brake arrive 3.77 times per second on average, but
  irregularly:** 0.16 to 0.56 s between samples, on a 40 ms clock. At 300 km/h
  that's 13 to 47 m between samples. Any event between two samples has to be
  *estimated*, and the estimate needs an error bar.
- **The live feed sometimes pauses for 0.6–1.4 s** (36 times in 30 laps, at
  the same moments for both drivers). Up to 113 m of track can have no data.
  A corner with a pause inside it can't be measured on that lap.
- **Brake is on/off only.** Braking strength must come from the change in speed.
- **Distance must be aligned.** Integrating speed gives lap lengths that agree
  within 2 m on clean qualifying laps, but differ by up to 9 m with a feed gap
  and 19 m in FP2. That is as large as the differences we want to measure.
- **X/Y positions can't show racing lines.** Different drivers' laps lie as
  close to each other's path as to their own (median 0.06 m).
- **Qualifying gives 4 push laps per driver**, and at the heavy-braking corner
  only 2 of Piastri's are usable. The pilot can only be descriptive; real
  statistics need many sessions (Phase 6).

## Check by check

| # | Check | Measured | What it means |
|---|---|---|---|
| 1 | Sample timing (car data) | 9,755 intervals; mean 0.265 s (3.77/s); median 0.24 s; normal range 0.16–0.56 s; 100 % within 2 ms of a multiple of 40 ms | Not "3.7 Hz plus jitter": a 25 Hz clock with 4–14 ticks between samples. 13–47 m between samples at 300 km/h (mean 22 m). |
| 1 | Sample timing (position) | 9,966 intervals; mean 0.260 s (3.85/s); on a 20 ms clock (99.8 % within 2 ms) | Position samples are not at the same moments as car samples; merging them means interpolating. |
| 1 | Feed gaps (> 0.6 s) | 36 in car data, all with a position gap at the same moment; 24 distinct moments; 21 of 30 laps; longest 1.36 s | Pauses of the whole feed. Rule: drop a (lap, corner) pair when a gap falls inside the corner window (decisions.md). |
| 1 | Event timing error (one lap) | 0.093 s (0.087 s without gaps), against 0.077 s for regular sampling at the mean interval; 7.7 m vs 6.4 m at 300 km/h | Events land in long intervals more often (inspection paradox), so the naive error formula is too optimistic. The synthetic generator must use the real interval distribution (`interval_histogram.csv`). |
| 2 | Resolution | Speed: whole km/h (61–327). Throttle: whole % (0–100). RPM: whole rpm. Gear 2–8. X/Y/Z: whole decimetres. DRS codes 8, 10, 12, 14 | Speed quantisation of 1 km/h gives rounding noise of 0.29 km/h (1/√12), which differentiation amplifies (§9.4). |
| 3 | Brake | `bool`, only True/False; braking in 14.8 % of samples | No brake pressure. Braking strength comes from deceleration. |
| 4 | Position paths | Other laps vs a driver's own reference path: median 0.06 m, 95th percentile 0.54 m. Vs the *teammate's* path: the same (0.06 / 0.54 m). FP2 vs Q: 0.05 / 0.49 m | X/Y can't show differences in racing line. ⚠️ Hypothesis: the feed is smoothed or matched to a track model. X/Y may still give a good along-track position for alignment (tested in Phase 3). |
| 5 | Lap distance (integrated speed, exact lap edges) | Mean 5,219 m; official centre line 5,281 m (−62 m, −1.2 %); X/Y path 5,230 m. Spread around each driver's mean: Q gap-free laps ≤ 2.0 m, Q laps with gaps ≤ 9.0 m, FP2 ≤ 19 m. FastF1's default `add_distance()` (no end edge): range up to 43 m | A racing line is shorter than the centre line, so being short is expected. The lap-to-lap spread is as large as the effects we want, so laps must be aligned (Phase 3). Feed gaps are one clear cause. |
| 6 | Usable laps | Q: 4 push laps each (Q1, Q2, 2 × Q3), all on softs. FP2: NOR 10, PIA 12, including a matched 7-lap medium long run each (tyre age 10–16 vs 12–18) | Q is the comparison, with very small samples. FP2 long runs are for repeatability. |
| 7 | Corner info | 16 corners from `get_circuit_info()`, distances along the session's fastest lap (NOR's pole lap) | Usable for placing windows. Each distance is uncertain by about half a position-sample spacing (≲ 10 m at speed). |
| 8 | FastF1 lap filters | All exist in 3.8.3. In Q they keep the same laps as `select_laps()`. In FP2, `pick_quicklaps()` drops most of NOR's long run | We use our own rules (per-stint 107 %), see decisions.md. |
| 9 | Cost | Q: 40.4 MB, FP2: 61.3 MB, HTTP cache 17 MB. Load from cache 1–4 s; first download of Q ~19 s | All 2023–2024 qualifying sessions ≈ 2 GB. |
| 10 | Three corners | T6 heavy braking (324 → 68 km/h), T5 medium (294 → 108), T9 fast (320 → 181). Gap-free Q laps: T6 NOR 4 / PIA 2, T5 4 / 4, T9 3 / 4 | Chosen by a fixed rule before comparing drivers (decisions.md). |

## Traps found (so nobody falls into them again)

1. FastF1's docs say interpolated rows have `Source == 'interpolated'`; the
   code (3.8.3) writes `'interpolation'`.
2. A "slow lap" rule against the driver's session best treats long runs
   unfairly (bug history in CLAUDE.md).
3. `add_distance()` without `interpolate_edges=True` leaves out the stretch
   from the last sample to the finish line.
4. FastF1's own docs warn: "Expect an error of around ±10m when overlapping
   telemetry data of different laps."

## What this data can support

| Can | Can't |
|---|---|
| Braking point, minimum speed, throttle pickup, each with an error bar of several metres per lap | Brake pressure or brake modulation |
| Averages over several laps (the error shrinks roughly like 1/√N) | Anything faster than ~1.9 Hz (vibration, steering corrections) |
| Teammate comparisons where the difference is bigger than the error bar | Racing-line differences from X/Y |
| Repeatability over many sessions (Phase 6) | Strong conclusions from one session (4 laps per driver) |

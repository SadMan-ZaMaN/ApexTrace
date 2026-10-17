# 9. The multi-season dataset (Phase 6, part 2)

> From one session and two drivers to every 2023–2024 qualifying session and
> every driver. Code: `openf1.py`, `corners.py` (detection), `features.py`,
> `events.py` (braking events). Experiments: `08_download_openf1.py`,
> `09_build_dataset.py` → `results/09_dataset/`.

## Why scale up

The pilot had 2–4 laps per driver, so no statistical test could succeed
(chapter 7). Identification (H3) and a proper repeatability measure (H1, ICC
with all drivers) need many sessions. 2023 and 2024 qualifying: 47 sessions
listed by OpenF1 (2023 Imola was cancelled: no data), ~20 drivers each.
2025 stays frozen.

## Downloading politely (rate limits)

OpenF1 is free and allows about **30 requests per minute**. The first download
asked for each lap separately (~160 requests per session) and quickly got
"429 Too Many Requests". Fixes, in order:
1. **One request per driver per session** for car data and one for positions,
   covering all of that driver's kept laps; the laps are cut out locally
   (`openf1.driver_streams`, `openf1.slice_lap`). ~44 requests per session.
2. **Pacing:** request starts at least 2.1 s apart (~28 per minute), enforced
   by `openf1.wait_for_rate_limit`. A *lock* makes threads take turns at that
   check.
3. **A few requests in flight:** each answer takes 3–5 s, so with one request
   at a time the pace was only ~12 per minute. Three worker threads
   (`ThreadPoolExecutor`) keep it near 28 per minute.
4. **Caching:** every answer is stored gzip-compressed (~10× smaller) and
   written to a temporary file first, then renamed (an *atomic* step), so
   stopping the program never leaves a broken file. Restarting skips
   everything already downloaded.

## Finding corners on any track

OpenF1 has no corner list, so `corners.detect_braking_corners` finds them on
each session's reference lap (its fastest kept lap). A sample is a corner if:
1. it's the slowest sample within ±100 m (a chicane's two dips closer than
   100 m count as one corner);
2. the speed fell at least 50 km/h from the fastest point in the 500 m before
   (a real braking zone, not a lift);
3. its window [−300 m, +200 m] fits inside the lap.

The corner's reference point is the dip itself, so on the reference lap the
apex is at 0 m. Types by minimum speed: **slow < 120 km/h, medium 120–200,
fast ≥ 200**. Corner names (C1, C2, ...) are per track; only the *types* can be
compared across tracks.

## Which braking belongs to which corner (`events.braking_event`)

On other tracks, a window can contain two braking zones. So:
- **Apex:** the slowest sample within ±80 m of the corner's reference.
- **Brake onset:** the braking *event* that leads into that apex. The brake
  channel can switch off for a moment in the middle of a braking zone (Norris's
  FP2 long runs: 1–4 samples, 0.44–1.32 s). Runs separated by a gap in which
  the **throttle never reaches 10 %** count as one event, because two different
  braking zones always have the throttle opened between them.
- **Throttle:** searched from the end of that braking event to the next one.

How this was found: a first, simpler rule ("the last brake-on before the
apex") was tested with a **regression check** on the pilot. It moved some FP2
brake onsets by up to 153 m. Looking at those laps showed the brief
releases, and the rule above fixed it: the pilot is identical again (90 of 90
rows). Always re-run old results after changing shared code.

## What came out (`results/09_dataset/`)

- 47 sessions downloaded (2023 Imola: cancelled), 4,500 kept laps.
- **30,441 (lap, corner) rows, 24,496 usable** (80 %; the rest: feed gaps).
- 4,497 laps, 25 drivers, 12 team names, **314 detected corners** (5–11 per
  track). On 2023 Bahrain the detector found the T1, T8 and T10 hairpins.
- `raw_samples.parquet`: **1,443,744 raw samples** (every measured sample of
  every kept lap, with its track position and X/Y). Explore it yourself:
  ```python
  import pandas as pd
  raw = pd.read_parquet("results/09_dataset/raw_samples.parquet")
  lap = raw[(raw.location == "Yas Island") & (raw.year == 2024) & (raw.driver == "NOR")]
  ```

## EDA, the classic way (`10_eda.py` → `results/10_eda/`)

1. **Overview:** laps per driver per session: median 5 (1–14).
2. **Missing values:** full throttle 8 %, throttle pickup 5 % (the throttle
   never reaches 99 % before the next braking, or never closes).
3. **Summary statistics** per feature and corner type (`summary_statistics.csv`).
4. **Sanity checks against physical limits:** 798 values outside them. Each
   cause was understood before deciding anything:
   wet sessions (2,997 rows on intermediates/wets), broken laps (min speed
   0–40 km/h), flat-bottomed fast corners (apex > 80 m away), corner sequences
   (braking "after" the apex: the previous corner's braking was matched),
   corners taken without closing the throttle.
5. **Cleaning rules** (`apextrace/dataset.py`): dry laps only; broken rows
   dropped; impossible values become *missing* in that feature only, so the
   rest of the row survives. → **21,493 clean rows in 44 dry sessions.**
   Decided before any modelling, so they can't be tuned to a result.
6. **Field-relative features:** value − median of all drivers at the same
   corner of the same session. This removes the track, which dominates the
   raw values. The distributions are centred on 0 (`distributions_field_relative.png`).
7. **Correlations** (Spearman, robust to outliers): min speed ↔ corner time
   −0.62 (carry more speed, spend less time); apex ↔ throttle pickup +0.57.
   Features that move together carry overlapping information, which matters
   for models.
8. **Track map** (`track_map.png`): a lap drawn from the raw X/Y, coloured by
   speed, with the detected corners.

**The rule of good EDA:** understand outliers before you remove them, write
down the rule, and apply it everywhere through one function.

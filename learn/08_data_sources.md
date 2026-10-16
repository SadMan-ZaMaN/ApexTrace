# 8. When a data source breaks: FastF1 → OpenF1 (Phase 6, part 1)

> Real research projects lose data sources. What matters is noticing, proving
> the replacement is equivalent, and writing it down.
> Code: `openf1.py`, `track.py`. Experiment: `07_openf1_validation.py`.

## What happened

On 2026-10-16 the official F1 live-timing archive started answering
**401 Unauthorized** to every request, and FastF1's mirror answered 404.
FastF1 (latest version 3.8.3) could no longer download any session that
wasn't already in our cache. The 2024 Abu Dhabi sessions still worked only
because they had been downloaded on 14–15 October.

How it was found: every 2023 download "failed to load timing data". The
cause was only visible with full logging (`logging.DEBUG`), which showed the
HTTP status codes. **Lesson: when something fails silently, turn the logging up.**

## Step 1: is the replacement the same data?

OpenF1 (api.openf1.org) publishes the same live-timing feed. Before trusting it,
we compared Norris's pole lap sample by sample: all 320 car samples matched
within 1 ms, with identical speed, throttle, gear and RPM, and all 323 position
samples had identical X/Y. So every Phase 1–3 result (the 40 ms clock, the
error bars, the alignment noise) carries over.

## Step 2: rebuild what FastF1 computed for us

OpenF1 gives raw pieces; FastF1 gave a ready-made lap table. `openf1.lap_table()`
rebuilds the columns our lap selection needs:

| Column | How it's rebuilt |
|---|---|
| Out lap | `is_pit_out_lap` |
| In lap | the next lap is an out lap, or it's the driver's last lap |
| Stint, compound, tyre age | the `stints` table; a lap shared by two stints belongs to the **new** one |
| Deleted | race-control text `CAR 81 (PIA) TIME 1:22.985 DELETED - …`, undone by `… WILL BE REINSTATED`; matched by lap **time** (the lap number in the message doesn't match ours) |
| Track status | race-control flags turned into time intervals: yellow in a mini-sector until its CLEAR, red until green, (virtual) safety car until "ending"; a lap overlapping any interval is "not green" |
| Timing check | FastF1's checks 1–3 (no pit, flags OK, sector times present and adding up within 3 ms, previous lap not under safety car) |

Regular expressions (`re` module) read the race-control messages: e.g.
`CAR (\d+) \((\w+)\) TIME (\d+):(\d\d\.\d{3}) DELETED - (.*?)` captures the
car number, the code, the minutes and seconds of the lap time, and the reason.

**Caching:** every OpenF1 request is saved as a JSON file in `cache/openf1/`
(file name = a hash of the request), so nothing is downloaded twice. On "too
many requests" (HTTP 429) the code waits 1, 2, 4, ... seconds and retries:
*exponential backoff*.

## Step 3: prove it on data where we know the answer

`07_openf1_validation.py` runs both sources on 2024 Abu Dhabi Q and FP2, all 20
drivers. **The first run failed:** OpenF1 kept ~1 lap per driver instead of ~4.
Two causes, both found by printing one driver's laps side by side:

1. FastF1's 4th timing check ("the lap starts where the previous lap ended,
   within 3 ms") can't work with OpenF1's lap start times, which are only
   accurate to ~0.1 s (and mark the pit exit on out laps). It was dropped.
2. OpenF1 lists the out lap in both the old and the new stint.

After the fixes: **kept laps identical for 20 of 20 drivers in both
sessions**, and all 75 pilot features within 0.23 m.

## Step 4: one code path for both sources

`track.py` was split into a **core** that works on plain arrays
(`clip_to_lap`, `samples_on_track`, `reference_path_from_xy`) and thin
wrappers for FastF1. OpenF1 feeds the same core, so alignment and features are
computed by exactly the same code. To prove the refactor changed nothing, the
pilot features were recomputed: all 90 rows identical. This is called a
**regression check**: re-running an old result after a change to show nothing
moved.

`clip_to_lap` does what FastF1's `interpolate_edges=True` did: keep samples
inside the lap and add one interpolated sample exactly at the lap start and
end. Continuous channels (speed) are interpolated linearly; "step" channels
(brake, gear) take the last value before the edge, because a gear can't be 3.5.

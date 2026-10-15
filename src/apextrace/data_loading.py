"""Load FastF1 sessions, and choose which laps to analyse with a reason for every lap we drop.

Why this module exists:
  - One place that sets up the cache, so every script loads data the same way.
  - A guard that stops us loading the 2025 season by accident. 2025 is the
    frozen final test set (decisions.md): if we look at it while developing,
    we tune our method to it without meaning to, and the final numbers look
    better than they are.
  - Lap selection that never drops a lap silently. Each dropped lap comes
    back with the reason(s), so the data report can say exactly what was
    removed and why ("12 of 23 laps dropped: 6 out laps, 5 in laps, ...").
"""

import os
from pathlib import Path

import fastf1
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = REPO_ROOT / "cache"

FROZEN_TEST_YEAR = 2025

# A lap slower than this many times the best clean lap *of its own stint*
# (one set of tyres) is not a push lap: a cool-down lap, or a lap stuck in
# traffic. 1.07 = the 107 % rule from F1's regulations. Example: stint best
# 82.6 s -> a lap slower than 82.6 * 1.07 = 88.4 s is dropped.
SLOW_LAP_FACTOR = 1.07

# A whole stint is dropped when even its best lap is slower than this many
# times the driver's best clean lap of the session: the stint was never a
# timed run (e.g. a practice-start run at the end of FP2). Measured in 2024
# Abu Dhabi FP2: long runs on high fuel were 106-109 % of the driver's best,
# end-of-session runs 130-141 %. 1.15 sits in that gap.
TIMED_RUN_FACTOR = 1.15


def load_session(year, event, session_name, cache_dir=DEFAULT_CACHE_DIR):
    """Load one session (laps, car data, position data, messages) via FastF1's cache.

    Example: load_session(2024, "Abu Dhabi", "Q") -> 2024 Abu Dhabi qualifying.
    The first call downloads ~45 MB into cache/ (~20 s); later calls read
    the cache and are much faster.

    We load *everything* FastF1 offers (session.load() with defaults): FastF1
    cross-checks its data sources against each other, and the race-control
    messages are needed to know which laps were deleted for track limits.

    Raises PermissionError for a 2025 session unless the environment variable
    FINAL_TEST is set to "1" (only for the one-time final evaluation).
    """
    if year == FROZEN_TEST_YEAR and os.environ.get("FINAL_TEST") != "1":
        raise PermissionError(
            f"{year} is the frozen final test set. Set FINAL_TEST=1 only for "
            f"the one-time final evaluation, after docs/preregistration.md "
            f"is committed."
        )

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_dir))

    session = fastf1.get_session(year, event, session_name)
    session.load()
    return session


def lap_problems(lap):
    """Return the list of reasons why one lap is not a clean lap (empty list = clean).

    Every rule is checked on every lap, so a lap can have several reasons,
    e.g. ["in lap", "timing check failed"]. The rules:
      - no lap time:        the lap was never completed or never timed
      - out lap / in lap:   the car left or entered the pits on this lap
      - deleted:            the lap time was deleted by race control
                            (usually track limits)
      - not green:          the track status was not '1' (green) for the whole
                            lap. FastF1 writes every status seen during the lap,
                            e.g. '12' = green, then a yellow flag
      - timing check failed: FastF1's own IsAccurate check, which tests e.g.
                            that the three sector times add up to the lap time
                            (within 3 ms)
    """
    problems = []

    if pd.isna(lap["LapTime"]):
        problems.append("no lap time")

    if not pd.isna(lap["PitOutTime"]):
        problems.append("out lap")

    if not pd.isna(lap["PitInTime"]):
        problems.append("in lap")

    if lap["Deleted"] == True:  # noqa: E712  (the value may be missing, i.e. not True)
        reason = lap["DeletedReason"]
        if isinstance(reason, str) and reason != "":
            problems.append(f"deleted ({reason.lower()})")
        else:
            problems.append("deleted")

    status = lap["TrackStatus"]
    if not isinstance(status, str) or status == "":
        problems.append("track status unknown")
    elif status != "1":
        problems.append(f"not green (track status {status})")

    if lap["IsAccurate"] != True:  # noqa: E712
        problems.append("timing check failed")

    return problems


def stint_key(lap):
    """(driver, stint number) for a lap; stint -1 when FastF1 doesn't know it."""
    stint = lap["Stint"]
    if pd.isna(stint):
        stint = -1
    return (lap["Driver"], int(stint))


def select_laps(laps, slow_lap_factor=SLOW_LAP_FACTOR,
                timed_run_factor=TIMED_RUN_FACTOR):
    """Split laps into the ones we keep and the ones we drop, with reasons.

    Two passes:
      1. Find the clean laps (lap_problems() returns nothing).
      2. Pace rules, for clean laps only:
         a. "not a timed run": the best clean lap of the stint is slower than
            timed_run_factor x the driver's best clean lap of the session.
            Example: driver best 83.5 s, a stint whose best is 118.1 s
            (141 %) is a practice-start run, not a timed run.
         b. "slow lap": the lap is slower than slow_lap_factor x the best
            clean lap of its own stint. Example: stint best 82.6 s, a
            cool-down lap of 100.2 s is 121 % of it.

    Why the stint, not the whole session, is the reference for (b): in FP2 a
    driver's best lap is on soft tyres and low fuel, and a long run on
    mediums is ~6-9 % slower. Against the session best, a 107 % rule cut 6
    of Norris's 7 long-run laps but only 2 of Piastri's, just because his
    soft lap was quicker. Against the stint best, a long run is compared
    with itself. See the bug history in CLAUDE.md.

    References are per driver, so one driver's pace never decides which laps
    of another driver count.

    Args:
        laps: a FastF1 Laps table (or any DataFrame with the same columns).
              Pass one session at a time.
        slow_lap_factor: see SLOW_LAP_FACTOR.
        timed_run_factor: see TIMED_RUN_FACTOR.

    Returns:
        kept: the rows of `laps` that passed every rule (same type as `laps`).
        dropped: a DataFrame with one row per dropped lap:
                 Driver, LapNumber, LapTime, Reason.
    """
    # Pass 1: rule-based problems, lap by lap
    problems_by_row = {}
    for row_index, lap in laps.iterrows():
        problems_by_row[row_index] = lap_problems(lap)

    # References: fastest clean lap per driver, and per (driver, stint)
    best_by_driver = {}
    best_by_stint = {}
    for row_index, lap in laps.iterrows():
        if problems_by_row[row_index]:
            continue
        driver = lap["Driver"]
        stint = stint_key(lap)
        lap_time = lap["LapTime"]
        if driver not in best_by_driver or lap_time < best_by_driver[driver]:
            best_by_driver[driver] = lap_time
        if stint not in best_by_stint or lap_time < best_by_stint[stint]:
            best_by_stint[stint] = lap_time

    # Pass 2: the pace rules, only for laps that are otherwise clean
    for row_index, lap in laps.iterrows():
        if problems_by_row[row_index]:
            continue
        driver_best = best_by_driver[lap["Driver"]]
        stint_best = best_by_stint[stint_key(lap)]

        stint_ratio = stint_best / driver_best
        lap_ratio = lap["LapTime"] / stint_best
        if stint_ratio > timed_run_factor:
            problems_by_row[row_index].append(
                f"not a timed run (stint best {stint_ratio * 100:.0f} % of driver's best)")
        elif lap_ratio > slow_lap_factor:
            problems_by_row[row_index].append(
                f"slow lap ({lap_ratio * 100:.0f} % of stint best)")

    # Build the two outputs
    kept_rows = []
    dropped_records = []
    for row_index, lap in laps.iterrows():
        problems = problems_by_row[row_index]
        if problems:
            dropped_records.append({
                "Driver": lap["Driver"],
                "LapNumber": lap["LapNumber"],
                "LapTime": lap["LapTime"],
                "Reason": "; ".join(problems),
            })
        else:
            kept_rows.append(row_index)

    kept = laps.loc[kept_rows]
    dropped = pd.DataFrame(dropped_records,
                           columns=["Driver", "LapNumber", "LapTime", "Reason"])
    return kept, dropped

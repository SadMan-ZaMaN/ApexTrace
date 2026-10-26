"""Tests for data_loading.py on a hand-made lap table (no F1 data is downloaded).

The fake session below has one lap for each rule, so we know in advance
which laps must be kept and exactly why each other lap must be dropped.
Lap times are realistic for 2024 Abu Dhabi (qualifying pole was 82.595 s;
FP2 long runs on mediums were ~89-91 s).
"""

import fastf1
import pandas as pd
import pytest

from apextrace.data_loading import check_not_frozen, load_session, select_laps


def make_lap(driver, lap_number, stint, seconds, **changes):
    """One clean lap as a dict; pass keyword arguments to break one rule."""
    lap = {
        "Driver": driver,
        "LapNumber": lap_number,
        "Stint": stint,
        "LapTime": pd.Timedelta(seconds, unit="s") if seconds is not None else pd.NaT,
        "PitOutTime": pd.NaT,
        "PitInTime": pd.NaT,
        "Deleted": False,
        "DeletedReason": "",
        "TrackStatus": "1",
        "IsAccurate": True,
    }
    lap.update(changes)
    return lap


def fake_session_laps():
    rows = [
        # Driver AAA, qualifying-style runs: out lap, push lap(s), in lap
        make_lap("AAA", 1, 1, 125.0, PitOutTime=pd.Timedelta(10, unit="s")),  # out lap
        make_lap("AAA", 2, 1, 82.6),                                         # clean push lap
        make_lap("AAA", 3, 1, 100.2),                                        # cool-down: 121 %
        make_lap("AAA", 4, 1, 110.0, PitInTime=pd.Timedelta(400, unit="s")),  # in lap
        make_lap("AAA", 5, 2, 82.4, Deleted=True, DeletedReason="TRACK LIMITS AT TURN 9"),
        make_lap("AAA", 6, 2, 83.0, TrackStatus="12"),                       # yellow flag
        make_lap("AAA", 7, 2, None),                                         # never timed
        make_lap("AAA", 8, 2, 75.0, IsAccurate=False),                       # timing glitch
        make_lap("AAA", 9, 2, 83.1),                                         # clean push lap
        # Driver BBB: slower car. 90.0 s is 109 % of AAA's best, but it is
        # BBB's own best, so it must be kept.
        make_lap("BBB", 1, 1, 90.0),
        # Driver CCC, practice-style: a soft-tyre push lap, a long run on
        # mediums at 107-108 % of it, then a practice-start run at 141 %.
        make_lap("CCC", 1, 1, 83.5),
        make_lap("CCC", 2, 2, 89.3),
        make_lap("CCC", 3, 2, 89.7),
        make_lap("CCC", 4, 2, 90.0),
        make_lap("CCC", 5, 3, 118.1),
    ]
    return pd.DataFrame(rows)


def kept_lap_numbers(kept, driver):
    return list(kept[kept["Driver"] == driver]["LapNumber"])


def dropped_reasons(dropped, driver):
    """{lap number: reason} for one driver's dropped laps."""
    reasons = {}
    for _, row in dropped[dropped["Driver"] == driver].iterrows():
        reasons[row["LapNumber"]] = row["Reason"]
    return reasons


def test_keeps_only_clean_push_laps():
    kept, dropped = select_laps(fake_session_laps())

    assert kept_lap_numbers(kept, "AAA") == [2, 9]
    assert kept_lap_numbers(kept, "BBB") == [1]
    # nothing lost: every lap is either kept or dropped
    assert len(kept) + len(dropped) == len(fake_session_laps())


def test_every_dropped_lap_has_its_reason():
    _, dropped = select_laps(fake_session_laps())

    assert dropped_reasons(dropped, "AAA") == {
        1: "out lap",
        3: "slow lap (121 % of stint best)",
        4: "in lap",
        5: "deleted (track limits at turn 9)",
        6: "not green (track status 12)",
        7: "no lap time",
        8: "timing check failed",
    }


def test_a_bad_lap_never_becomes_the_reference():
    # Lap 8 has a glitched 75.0 s time. If it were used as a reference, the
    # real push laps 2 and 9 (110-111 % of 75.0) would wrongly be dropped.
    kept, _ = select_laps(fake_session_laps())
    assert kept_lap_numbers(kept, "AAA") == [2, 9]


def test_long_run_is_judged_against_its_own_stint():
    # 89.7 and 90.0 s are 107.4 % and 107.8 % of CCC's soft-tyre lap, but
    # within 1 % of their own stint's best (89.3 s), so all three are kept.
    kept, _ = select_laps(fake_session_laps())
    assert kept_lap_numbers(kept, "CCC") == [1, 2, 3, 4]


def test_stint_that_was_never_a_timed_run_is_dropped():
    # The 118.1 s lap is the best (only) lap of its stint, so the stint rule
    # alone can't catch it; it is 141 % of the driver's best.
    _, dropped = select_laps(fake_session_laps())
    assert dropped_reasons(dropped, "CCC") == {
        5: "not a timed run (stint best 141 % of driver's best)",
    }


def test_load_session_refuses_the_frozen_2025_season(monkeypatch):
    monkeypatch.delenv("FINAL_TEST", raising=False)

    def must_not_be_called(*args, **kwargs):
        raise AssertionError("FastF1 was asked for 2025 data")

    # If the guard is missing, the test fails here instead of downloading.
    monkeypatch.setattr(fastf1, "get_session", must_not_be_called)

    with pytest.raises(PermissionError):
        load_session(2025, "Abu Dhabi", "Q")


def test_2026_is_held_out_with_its_own_switch(monkeypatch):
    # The 2025 switch must NOT open 2026: each held-out season has its own.
    monkeypatch.setenv("FINAL_TEST", "1")
    monkeypatch.delenv("FINAL_TEST_2026", raising=False)
    check_not_frozen(2025)                       # opened by its switch: no error
    with pytest.raises(PermissionError, match="FINAL_TEST_2026"):
        check_not_frozen(2026)
    monkeypatch.setenv("FINAL_TEST_2026", "1")
    check_not_frozen(2026)                       # only its own switch opens it
    check_not_frozen(2024)                       # development seasons are never blocked


def test_openf1_refuses_2026_before_any_download(monkeypatch):
    from apextrace import openf1
    monkeypatch.delenv("FINAL_TEST_2026", raising=False)

    def must_not_be_called(*args, **kwargs):
        raise AssertionError("OpenF1 was asked for 2026 data")

    monkeypatch.setattr(openf1, "fetch", must_not_be_called)
    with pytest.raises(PermissionError):
        openf1.qualifying_sessions(2026)

"""Tests for openf1.py (and track.clip_to_lap) on hand-made OpenF1-style records; no network."""

import numpy as np
import pandas as pd
import pytest

from apextrace import openf1
from apextrace.openf1 import deleted_lap_times, flag_intervals, lap_table, track_status
from apextrace.track import clip_to_lap


def message(clock, text="", category="Other", flag=None, scope=None, sector=None):
    return {"date": f"2024-12-07T{clock}+00:00", "message": text, "category": category,
            "flag": flag, "scope": scope, "sector": sector}


def test_deleted_and_reinstated_laps():
    messages = [
        message("14:07:00", "CAR 11 (PER) TIME 1:23.559 DELETED - TRACK LIMITS AT TURN 1 LAP 3 18:05:38"),
        message("14:14:27", "CAR 11 (PER) TIME 1:23.559 WILL BE REINSTATED"),
        message("14:43:30", "CAR 16 (LEC) TIME 1:22.980 DELETED - TRACK LIMITS AT TURN 1 LAP 12 18:42:10"),
        message("14:19:44", "CAR 18 (STR) LAP DELETED - TRACK LIMITS AT TURN 1 LAP 9 18:17:57 (PIT)"),
    ]
    assert deleted_lap_times(messages) == {(16, 82.98): "TRACK LIMITS AT TURN 1"}


def test_sector_yellow_overlapping_a_lap_makes_it_not_green():
    end_of_session = pd.Timestamp("2024-12-07T15:10:00")
    messages = [
        message("14:20:34", category="Flag", flag="DOUBLE YELLOW", scope="Sector", sector=9),
        message("14:20:38", category="Flag", flag="CLEAR", scope="Sector", sector=9),
        message("14:30:00", category="Flag", flag="RED", scope="Track"),
        message("14:35:00", category="Flag", flag="GREEN", scope="Track"),
        message("14:50:00", "VIRTUAL SAFETY CAR DEPLOYED", category="SafetyCar"),
        message("14:51:00", "VIRTUAL SAFETY CAR ENDING", category="SafetyCar"),
    ]
    intervals = flag_intervals(messages, end_of_session)
    t = pd.Timestamp
    assert track_status(t("2024-12-07T14:19:30"), t("2024-12-07T14:20:50"), intervals) == "12"
    assert track_status(t("2024-12-07T14:21:00"), t("2024-12-07T14:22:20"), intervals) == "1"
    assert track_status(t("2024-12-07T14:34:00"), t("2024-12-07T14:36:00"), intervals) == "15"
    assert track_status(t("2024-12-07T14:50:30"), t("2024-12-07T14:52:00"), intervals) == "16"


def fake_session(monkeypatch):
    """One driver, four laps: out lap, push lap, push lap with bad sector sum, in lap."""
    laps = [
        {"driver_number": 4, "lap_number": 1, "date_start": "2024-12-07T14:05:00.000+00:00",
         "lap_duration": None, "is_pit_out_lap": True,
         "duration_sector_1": None, "duration_sector_2": 30.0, "duration_sector_3": 25.0},
        {"driver_number": 4, "lap_number": 2, "date_start": "2024-12-07T14:06:40.000+00:00",
         "lap_duration": 83.0, "is_pit_out_lap": False,
         "duration_sector_1": 17.0, "duration_sector_2": 36.0, "duration_sector_3": 30.0},
        {"driver_number": 4, "lap_number": 3, "date_start": "2024-12-07T14:08:03.000+00:00",
         "lap_duration": 82.9, "is_pit_out_lap": False,
         "duration_sector_1": 17.0, "duration_sector_2": 36.0, "duration_sector_3": 30.0},  # sums to 83.0
        {"driver_number": 4, "lap_number": 4, "date_start": "2024-12-07T14:09:25.900+00:00",
         "lap_duration": 110.0, "is_pit_out_lap": False,
         "duration_sector_1": 30.0, "duration_sector_2": 45.0, "duration_sector_3": 35.0},
    ]
    stints = [{"driver_number": 4, "stint_number": 1, "lap_start": 1, "lap_end": 4,
               "compound": "SOFT", "tyre_age_at_start": 0}]
    drivers = [{"driver_number": 4, "name_acronym": "NOR", "team_name": "McLaren"}]
    data = {"laps": laps, "stints": stints, "race_control": [], "drivers": drivers}
    monkeypatch.setattr(openf1, "fetch", lambda endpoint, params, cache_dir=None: data[endpoint])


def test_lap_table_rebuilds_fastf1_columns(monkeypatch):
    fake_session(monkeypatch)
    table = lap_table(9999, pd.Timestamp("2024-12-07T15:00:00")).set_index("LapNumber")
    assert table.loc[1, "PitOutTime"] == pd.Timedelta(0)          # out lap
    assert pd.isna(table.loc[2, "PitInTime"])
    assert table.loc[4, "PitInTime"] == pd.Timedelta(0)           # last lap = in lap
    assert list(table["TyreLife"]) == [1.0, 2.0, 3.0, 4.0]         # counts the current lap, like FastF1
    assert bool(table.loc[2, "IsAccurate"])                        # sectors add up, starts where lap 1 ended
    assert not bool(table.loc[3, "IsAccurate"])                    # sectors 83.0 vs lap 82.9
    assert table.loc[2, "LapTime"] == pd.Timedelta(83.0, unit="s")
    assert set(table.loc[[2, 3, 4], "TrackStatus"]) == {"1"}
    assert table.loc[1, "TrackStatus"] == ""                       # no lap time -> end unknown -> status unknown


def test_clip_to_lap_adds_exact_edge_samples():
    times = np.array([9.9, 10.1, 10.4, 92.2, 92.5])
    speed = np.array([250.0, 252.0, 255.0, 240.0, 244.0])
    brake = np.array([False, False, True, True, False])
    new_times, channels, measured = clip_to_lap(times, {"speed": speed, "brake": brake},
                                                10.0, 92.4, step_channels=("brake",))
    assert list(new_times) == pytest.approx([10.0, 10.1, 10.4, 92.2, 92.4])
    assert channels["speed"][0] == pytest.approx(251.0)            # halfway between 250 and 252
    assert channels["speed"][-1] == pytest.approx(240 + 4 * (0.2 / 0.3))
    assert list(channels["brake"]) == [False, False, True, True, True]   # last value before 92.4 s
    assert list(measured) == [False, True, True, True, False]


def test_overlapping_stints_give_the_shared_lap_to_the_new_stint(monkeypatch):
    # OpenF1: stint 1 = laps 1-2, stint 2 = laps 2-3 (lap 2 is the out lap of stint 2)
    laps = [{"driver_number": 4, "lap_number": n, "date_start": f"2024-12-07T14:0{n}:00.000+00:00",
             "lap_duration": 90.0, "is_pit_out_lap": n == 2,
             "duration_sector_1": 30.0, "duration_sector_2": 30.0, "duration_sector_3": 30.0} for n in (1, 2, 3)]
    stints = [{"driver_number": 4, "stint_number": 1, "lap_start": 1, "lap_end": 2,
               "compound": "SOFT", "tyre_age_at_start": 0},
              {"driver_number": 4, "stint_number": 2, "lap_start": 2, "lap_end": 3,
               "compound": "MEDIUM", "tyre_age_at_start": 3}]
    data = {"laps": laps, "stints": stints, "race_control": [],
            "drivers": [{"driver_number": 4, "name_acronym": "NOR", "team_name": "McLaren"}]}
    monkeypatch.setattr(openf1, "fetch", lambda endpoint, params, cache_dir=None: data[endpoint])
    table = lap_table(9999, pd.Timestamp("2024-12-07T15:00:00")).set_index("LapNumber")
    assert list(table["Stint"]) == [1, 2, 2]
    assert list(table["Compound"]) == ["SOFT", "MEDIUM", "MEDIUM"]
    assert list(table["TyreLife"]) == [1.0, 4.0, 5.0]


def test_session_without_laps_is_skipped_not_crashed(monkeypatch):
    # 2025 Baku qualifying: OpenF1 answers 404 for laps (fetch -> []), but has stints,
    # race control and drivers. The first final run crashed here (KeyError 'driver_number').
    from apextrace.session_build import build_session
    data = {"laps": [], "stints": [{"driver_number": 4, "stint_number": 1, "lap_start": 1, "lap_end": 4,
                                    "compound": "SOFT", "tyre_age_at_start": 0}],
            "race_control": [], "drivers": [{"driver_number": 4, "name_acronym": "NOR", "team_name": "McLaren"}]}
    monkeypatch.setattr(openf1, "fetch", lambda endpoint, params, cache_dir=None: data[endpoint])
    end = pd.Timestamp("2025-09-20T13:00:00")
    assert lap_table(9900, end).empty
    assert openf1.download_session(9900, end) == {"laps": 0, "kept_laps": 0, "kept_laps_with_data": 0}
    rows, corners, summary, raw = build_session(2025, 17, {"session_key": 9900, "date_end": end, "location": "Baku"})
    assert rows == [] and corners == [] and raw.empty
    assert summary["note"] == "no laps"

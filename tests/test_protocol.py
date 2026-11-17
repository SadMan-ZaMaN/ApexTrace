"""The H3 identification protocol (protocol.py) on synthetic lap tables with a known answer.

protocol.teammate_task produced every H3 number (development and the frozen 2025 test), but until
2026-11-18 only the experiments ran it, on real data. Here each team's two drivers differ in ONE
corner feature (throttle pickup at slow corners, by 3 lap-to-lap standard deviations) and in
nothing else, so the right answers are known:
  - our features find the driver (balanced accuracy well above 0.5);
  - lap time, the whole-lap statistics, shuffled labels, and our features WITHOUT the throttle
    group carry no driver information (about 0.5);
  - the pair is the two drivers with most laps, on the weekends both drove, at least 5 of them.
"""

import numpy as np
import pandas as pd
import pytest
from scipy import stats as scipy_stats

from apextrace import protocol
from apextrace.identification import ALL_FEATURES, CORNER_TYPES, RAW_STATS

OURS = [f"{feature}_rel__{corner_type}" for feature in ALL_FEATURES for corner_type in CORNER_TYPES]
SIGNAL = "throttle_pickup_m_rel__slow"


def team_laps(rng, team, drivers, sessions, laps_per_driver, offset=3.0):
    """Laps of one team-season: every column is noise, except SIGNAL, where the first driver is
    `offset` higher. sessions: list of session keys this team drove."""
    rows = []
    for session in sessions:
        for index, driver in enumerate(drivers):
            for lap in range(laps_per_driver):
                row = {"team_season": team, "driver": driver, "session_key": session, "lap": lap}
                for column in OURS + ["lap_time_s_rel"] + [f"{stat}_rel" for stat in RAW_STATS]:
                    row[column] = rng.normal(0.0, 1.0)
                if index == 0:
                    row[SIGNAL] += offset
                rows.append(row)
    return rows


@pytest.fixture(scope="module")
def result():
    rng = np.random.default_rng(7)
    rows = []
    for team_number in range(4):
        drivers = [f"A{team_number}", f"B{team_number}"]
        rows += team_laps(rng, f"Team {team_number} 2024", drivers, sessions=list(range(1, 7)), laps_per_driver=8)
    # a third driver with few laps in Team 0: must not be one of the pair
    rows += team_laps(rng, "Team 0 2024", ["Z0"], sessions=[1, 2], laps_per_driver=2)
    # a team whose drivers shared only 4 weekends: skipped (at least 5 needed)
    rows += team_laps(rng, "Short 2024", ["S1"], sessions=[1, 2, 3, 4, 5, 6], laps_per_driver=5)
    rows += team_laps(rng, "Short 2024", ["S2"], sessions=[3, 4, 5, 6], laps_per_driver=5)
    laps = pd.DataFrame(rows)
    table = protocol.teammate_task(laps, np.random.default_rng(1), shuffles=3, verbose=False)
    summary = protocol.summarise_teammates(table, np.random.default_rng(2))
    return laps, table, summary


def test_feature_sets_name_the_right_columns():
    laps = pd.DataFrame(columns=OURS + ["lap_time_s_rel"] + [f"{s}_rel" for s in RAW_STATS] + ["driver"])
    sets = protocol.feature_sets(laps)
    assert sets["our features"] == OURS and len(OURS) == 30
    assert sets["lap time only"] == ["lap_time_s_rel"]
    assert sets["raw lap statistics"] == [f"{s}_rel" for s in RAW_STATS]


def test_pairs_follow_the_rule(result):
    _, table, _ = result
    assert sorted(table["team_season"]) == [f"Team {k} 2024" for k in range(4)]     # "Short 2024" skipped
    team0 = table.set_index("team_season").loc["Team 0 2024"]
    assert team0["drivers"] == "A0 vs B0"                                          # Z0 has too few laps
    assert team0["sessions"] == 6 and team0["laps"] == 6 * 2 * 8


def test_only_the_planted_feature_identifies_the_driver(result):
    _, table, _ = result
    assert (table["our features | balanced_accuracy"] > 0.75).all()
    assert table["our features | weekend vote"].mean() >= table["our features | balanced_accuracy"].mean()
    for column in ["lap time only | balanced_accuracy", "raw lap statistics | balanced_accuracy",
                   "shuffled labels | balanced_accuracy", "without throttle | balanced_accuracy"]:
        assert abs(table[column].mean() - 0.5) < 0.1, column
    # removing a group that carries nothing changes little
    assert (table["without braking | balanced_accuracy"] > 0.75).all()


def test_summary_statistics_match_scipy(result):
    _, table, summary = result
    difference = table["our features | balanced_accuracy"] - table["lap time only | balanced_accuracy"]
    block = summary["ours minus lap time only"]
    assert block["wins"] == int((difference > 0).sum()) == 4
    assert block["team_seasons"] == 4
    assert block["wilcoxon_p"] == pytest.approx(scipy_stats.wilcoxon(difference).pvalue)
    assert block["wilcoxon_p"] == pytest.approx(2 / 2 ** 4)       # all four higher: the smallest two-sided p
    ours = summary["our features | balanced_accuracy"]
    assert ours["mean"] == pytest.approx(table["our features | balanced_accuracy"].mean())
    assert ours["ci95_low"] <= ours["mean"] <= ours["ci95_high"]


def test_weekend_vote_worked_example():
    """Session 1: AAA's laps vote AAA (right), BBB's laps vote AAA (wrong); session 2: both right.
    Recall AAA = 2/2, recall BBB = 1/2, so balanced accuracy = 0.75. A lap without a prediction
    (None) doesn't vote."""
    laps = pd.DataFrame({"session_key": [1, 1, 1, 1, 1, 1, 2, 2, 2],
                         "driver": ["AAA", "AAA", "AAA", "BBB", "BBB", "BBB", "AAA", "BBB", "BBB"]})
    predictions = np.array(["AAA", "AAA", "BBB", "AAA", "AAA", "BBB", "AAA", "BBB", None], dtype=object)
    assert protocol.weekend_vote(laps, predictions)["balanced_accuracy"] == pytest.approx(0.75)

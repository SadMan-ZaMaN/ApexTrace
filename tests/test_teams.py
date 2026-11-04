"""Tests for teams.py: team lineages across renames, unknown names, and team changers from data."""

import pandas as pd
import pytest

from apextrace.teams import lineage, team_changers, unknown_team_names

# Every team name in the 2023, 2024 and 2025 data (results/09_dataset, results/final)
NAMES_2023_2025 = ["Williams", "Aston Martin", "Alfa Romeo", "AlphaTauri", "Alpine", "Mercedes", "Haas F1 Team",
                   "Ferrari", "McLaren", "Red Bull Racing", "Kick Sauber", "RB", "Racing Bulls"]


def test_every_name_in_the_development_data_has_a_lineage():
    assert unknown_team_names(NAMES_2023_2025) == []
    assert len({lineage(name) for name in NAMES_2023_2025}) == 10      # ten teams in 2023-2025


@pytest.mark.parametrize("names, expected", [
    (["AlphaTauri", "RB", "Racing Bulls", "Visa Cash App Racing Bulls"], "Racing Bulls"),
    (["Alfa Romeo", "Kick Sauber", "Audi", "Audi F1 Team"], "Sauber / Audi"),
    (["Red Bull Racing", "Oracle Red Bull Racing"], "Red Bull Racing"),
    (["Haas F1 Team", "MoneyGram Haas F1 Team"], "Haas"),
])
def test_renamed_and_sponsored_names_keep_their_lineage(names, expected):
    for name in names:
        assert lineage(name) == expected


def test_the_two_red_bull_teams_never_mix():
    assert lineage("Red Bull Racing") != lineage("Racing Bulls")
    assert lineage("RB") != lineage("Red Bull Racing")


def test_an_unknown_name_is_reported_not_guessed():
    with pytest.raises(ValueError):
        lineage("Andretti")
    assert unknown_team_names(["Ferrari", "Andretti", "Cadillac"]) == ["Andretti"]


def test_team_changers_come_from_the_most_driven_team():
    """A moves team; B is renamed only (RB -> Racing Bulls); C drove 2 weekends for one team
    and 8 for another in the target year, and counts by the 8."""
    rows = []
    for weekend in range(10):
        rows.append({"year": 2024, "session_key": weekend, "driver": "A", "team": "Mercedes"})
        rows.append({"year": 2025, "session_key": 100 + weekend, "driver": "A", "team": "Ferrari"})
        rows.append({"year": 2024, "session_key": weekend, "driver": "B", "team": "RB"})
        rows.append({"year": 2025, "session_key": 100 + weekend, "driver": "B", "team": "Racing Bulls"})
        rows.append({"year": 2024, "session_key": weekend, "driver": "C", "team": "Red Bull Racing"})
        rows.append({"year": 2025, "session_key": 100 + weekend, "driver": "C",
                     "team": "Red Bull Racing" if weekend < 2 else "Racing Bulls"})
    rows.append({"year": 2024, "session_key": 0, "driver": "D", "team": "Ferrari"})      # 2 weekends only
    rows.append({"year": 2024, "session_key": 1, "driver": "D", "team": "Haas F1 Team"})
    for weekend in range(10):
        rows.append({"year": 2025, "session_key": 100 + weekend, "driver": "D", "team": "Haas F1 Team"})
    changers = team_changers(pd.DataFrame(rows), 2024, 2025).set_index("driver")
    assert changers.loc["A", "changed"]
    assert not changers.loc["B", "changed"]
    assert changers.loc["C", "changed"]                  # mostly Racing Bulls in 2025
    assert changers.loc["C", "team_target"] == "Racing Bulls"
    assert changers.loc["A", "eligible"] and changers.loc["C", "eligible"]
    assert not changers.loc["D", "eligible"]             # a 1-1 tie can't decide anything: too few weekends

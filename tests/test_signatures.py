"""Tests for signatures.py: season signatures, distances, ranks, sign test."""

import numpy as np
import pandas as pd
import pytest

from apextrace.synthetic import own_closer_share
from apextrace.signatures import (distance, distance_table, equal_laps_per_session, own_rank,
                                  own_vs_past_teammate, season_signatures,
                                  sign_test_p, sign_test_power, sign_test_threshold, standardise)


def test_distance_ignores_missing_features():
    assert distance([1.0, -2.0, np.nan], [0.0, 0.0, 5.0]) == pytest.approx(np.sqrt(5 / 2))
    assert np.isnan(distance([np.nan], [1.0]))


def test_sign_test():
    assert sign_test_p(5, 5) == pytest.approx(1 / 32)
    assert sign_test_p(4, 5) == pytest.approx(6 / 32)
    assert sign_test_p(0, 5) == pytest.approx(1.0)


def test_sign_test_threshold_is_the_fewest_significant_successes():
    assert sign_test_threshold(10) == 9      # 9 of 10: p = 0.011; 8 of 10: p = 0.055
    assert sign_test_threshold(20) == 15     # 15 of 20: p = 0.021; 14 of 20: p = 0.058
    assert sign_test_threshold(5) == 5       # only 5 of 5 (p = 1/32)
    assert sign_test_threshold(4) is None    # even 4 of 4 gives p = 1/16


def test_sign_test_power_matches_the_worked_example():
    assert sign_test_power(10, 0.8) == pytest.approx(10 * 0.8 ** 9 * 0.2 + 0.8 ** 10)
    assert sign_test_power(4, 0.99) == 0.0
    # with no signature (a coin flip per driver) "power" is the real false-positive rate
    assert sign_test_power(10, 0.5) == pytest.approx(sign_test_p(9, 10))
    assert sign_test_power(10, 0.5) < 0.05


def test_sign_test_power_agrees_with_simulated_studies():
    """The full path: simulate many studies of 16 drivers, run the sign test on each,
    count how often it is significant. That share must match the formula."""
    rng = np.random.default_rng(8)
    drivers, probability, studies = 16, 0.75, 20000
    significant = 0
    for _ in range(studies):
        successes = int(np.sum(rng.random(drivers) < probability))
        if sign_test_p(successes, drivers) < 0.05:
            significant += 1
    assert significant / studies == pytest.approx(sign_test_power(drivers, probability), abs=0.015)


def test_every_session_counts_once_in_a_signature():
    # session 1: three laps at 0; session 2: one lap at 10 -> mean of session means = 5 (not 2.5)
    laps = pd.DataFrame({"year": 2024, "session_key": [1, 1, 1, 2], "driver": "A", "team": "T",
                         "f": [0.0, 0.0, 0.0, 10.0]})
    signatures = season_signatures(laps, ["f"], min_sessions=2)
    assert signatures.loc[("A", 2024), "f"] == pytest.approx(5.0)
    assert len(season_signatures(laps, ["f"], min_sessions=3)) == 0


def season_of_laps(rng, personal_offsets, noise, sessions=20):
    rows = []
    for year in (2023, 2024):
        for session in range(sessions):
            for name, offset in personal_offsets.items():
                values = offset + rng.normal(0, noise, len(offset))
                rows.append({"year": year, "session_key": year * 100 + session, "driver": name, "team": "T",
                             **{f"f{i}": values[i] for i in range(len(offset))}})
    return pd.DataFrame(rows)


def ranks(laps, columns, names):
    signatures = season_signatures(laps, columns)
    old_raw = signatures.xs(2023, level="year")
    old = standardise(old_raw, columns, old_raw)
    new = standardise(signatures.xs(2024, level="year"), columns, old_raw)
    distances = distance_table(new, old, columns)
    return [own_rank(distances, name) for name in names]


def test_a_stable_driver_signature_ranks_first():
    """20 drivers, 20 weekends a season, personal offsets with spread 1 and weekend noise 0.8:
    a season mean has noise 0.8 / sqrt(20) = 0.18, much smaller than the gaps between
    drivers, so nearly every driver's 2024 signature is closest to their own 2023 one."""
    rng = np.random.default_rng(51)
    names = [f"D{k}" for k in range(20)]
    personal = {name: rng.normal(0, 1, 6) for name in names}
    laps = season_of_laps(rng, personal, noise=0.8)
    own = ranks(laps, [f"f{i}" for i in range(6)], names)
    assert sum(rank == 1 for rank in own) >= 18


def test_without_a_personal_signature_ranks_are_random():
    """Same setup but no personal offsets: the own signature is no closer than anyone's,
    so the mean rank is near the middle, (20 + 1) / 2 = 10.5."""
    rng = np.random.default_rng(52)
    names = [f"D{k}" for k in range(20)]
    personal = {name: np.zeros(6) for name in names}
    laps = season_of_laps(rng, personal, noise=0.8)
    own = ranks(laps, [f"f{i}" for i in range(6)], names)
    assert 6.5 < np.mean(own) < 14.5


# ---------------------------------------------------------------- H5: own past vs past teammate

def share_own_closer(seed, studies, **options):
    """The share of drivers whose own past is closer, over `studies` synthetic grids
    (synthetic.signature_seasons: car + personal offset + noise, a new car in 2026)."""
    return own_closer_share(seed, studies, **options)[0]


def test_h5_finds_a_personal_signature_through_a_new_car():
    """Personal offsets as large as the car differences, and a completely new car in 2026:
    the driver's 2026 signature is still nearer their own 2025 one than the teammate's."""
    assert share_own_closer(seed=91, studies=10, personal_sd=1.0) > 0.85


def test_h5_is_a_fair_coin_when_the_signature_is_only_the_car():
    """No personal offsets: both 2025 references are the same car plus noise, so a driver
    is closer to their own past about half the time (the sign test's null hypothesis)."""
    assert 0.40 < share_own_closer(seed=92, studies=30, personal_sd=0.0) < 0.60


FEW_WEEKENDS_TEAMMATE = {"personal_sd": 0.0, "teammate_weekends": 5, "noise": 2.0, "car_sd": 0.3}


def test_full_season_references_fake_a_yes_when_a_teammate_drove_few_weekends():
    """Only the car, but every team's second driver drove just 5 of 12 reference weekends
    and left. With full-season references the lead driver's own past (12 weekends) is less
    noisy than the teammate's (5), so "own closer" wins far too often: a fake "yes".
    (Seeds 93-98 give 0.71-0.80, experiment 22; a fair coin over 150 trials stays below
    0.61 with 99.6 %.)"""
    assert share_own_closer(seed=93, studies=30, shared_weekends_only=False, **FEW_WEEKENDS_TEAMMATE) > 0.65


def test_shared_weekends_and_leaving_the_pair_out_keep_the_coin_fair():
    """The same world with the H5 rules: both references on the 5 shared weekends, and the
    spread for the z-scores taken from the OTHER drivers. 360 trials; a fair coin lands in
    0.5 +- 0.07 (2.7 standard errors). Fails if the pair is part of the spread (0.36-0.42
    on small grids: the noisy teammate inflates the spread where it differs most) or if
    full-season references are used (about 0.7)."""
    share = share_own_closer(seed=93, studies=120, teams=3, **FEW_WEEKENDS_TEAMMATE)
    assert 0.43 < share < 0.57


def test_pair_inside_the_spread_makes_the_teammate_look_closer():
    """The second broken version, kept selectable to show the bias: with the noisy
    teammate inside the z-score spread, the teammate looks closer than it is
    (0.369 on this grid, below the fair coin's 0.43-0.57; 0.431 over 1,500 drivers in
    experiment 22)."""
    share = share_own_closer(seed=93, studies=120, teams=3, leave_pair_out=False, **FEW_WEEKENDS_TEAMMATE)
    assert share < 0.43


def test_h5_teammate_is_the_one_with_the_most_shared_weekends():
    """X drove all 10 weekends; Y the first 3, then Z the last 7 -> X's teammate is Z.
    W drove alone for another team -> left out, with the reason."""
    rows = []
    for weekend in range(10):
        drivers = [("X", "T"), ("Y" if weekend < 3 else "Z", "T"), ("W", "U")]
        for name, team in drivers:
            rows.append({"year": 2025, "session_key": weekend, "driver": name, "team": team, "lap": 1, "f0": 0.0})
    for weekend in range(6):
        for name in ("X", "W"):
            rows.append({"year": 2026, "session_key": 100 + weekend, "driver": name, "team": "T", "lap": 1, "f0": 0.0})
    table = own_vs_past_teammate(pd.DataFrame(rows), 2025, 2026, ["f0"]).set_index("driver")
    assert table.loc["X", "teammate"] == "Z"
    assert table.loc["X", "shared_weekends"] == 7
    assert not table.loc["W", "included"]
    assert "no teammate" in table.loc["W", "reason"]


FEWER_LAPS_TEAMMATE = {"personal_sd": 0.0, "noise": 2.0, "car_sd": 0.3, "laps_lead": 6, "laps_second": 2,
                       "second_continues": False}


def test_equal_laps_per_session_keeps_each_drivers_first_laps():
    """Session 1: X has laps 3, 5, 9, 12 and Y laps 4, 7 -> 2 each: X 3, 5 and Y 4, 7.
    Session 2: X has lap 2, Y laps 1, 6, 8 -> 1 each: X 2 and Y 1."""
    rows = [(1, "X", 3), (1, "X", 5), (1, "X", 9), (1, "X", 12), (1, "Y", 4), (1, "Y", 7),
            (2, "X", 2), (2, "Y", 1), (2, "Y", 6), (2, "Y", 8)]
    pair = pd.DataFrame(rows, columns=["session_key", "driver", "lap"])
    kept = equal_laps_per_session(pair, "X", "Y")
    chosen = sorted(zip(kept["session_key"], kept["driver"], kept["lap"]))
    assert chosen == [(1, "X", 3), (1, "X", 5), (1, "Y", 4), (1, "Y", 7), (2, "X", 2), (2, "Y", 1)]


def test_all_laps_fake_a_yes_when_the_driver_who_stays_had_more_laps():
    """Only the car; the driver who keeps the seat had 6 laps a weekend, the teammate 2 and then
    left. A weekend mean over 6 laps is less noisy, so the own past looks closer for no reason
    (found by the fresh-eyes review of Part C; 0.73 over 1,500 drivers in experiment 22, case E)."""
    assert share_own_closer(seed=5, studies=60, teams=3, equal_laps=False, **FEWER_LAPS_TEAMMATE) > 0.65


def test_equal_laps_keep_the_coin_fair_when_the_driver_who_stays_had_more_laps():
    """The same world with the H5 rule (the same number of laps per shared weekend): a fair
    coin, 0.5 +- 0.07 over 360 drivers (0.50 over 1,500 in experiment 22, case F)."""
    share = share_own_closer(seed=5, studies=120, teams=3, **FEWER_LAPS_TEAMMATE)
    assert 0.43 < share < 0.57

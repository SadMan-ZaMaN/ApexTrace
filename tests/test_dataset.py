"""Tests for dataset.py: the cleaning rules and field-relative features, on a tiny hand-made table."""

import numpy as np
import pandas as pd
import pytest

from apextrace.dataset import add_field_relative, clean, team_season
from apextrace.features import FEATURES


def row(**changes):
    base = {name: 1.0 for name in FEATURES}
    base.update({"usable": True, "compound": "SOFT", "session_key": 1, "corner": "C1", "team": "McLaren",
                 "year": 2024, "brake_onset_m": -140.0, "min_speed_kmh": 80.0, "mean_decel_ms2": 25.0,
                 "apex_m": 2.0, "throttle_pickup_m": 5.0, "braking_distance_m": 142.0})
    base.update(changes)
    return base


def test_cleaning_rules():
    data = pd.DataFrame([
        row(),                                   # clean
        row(compound="INTERMEDIATE"),            # wet: dropped
        row(min_speed_kmh=12.0),                 # broken data: dropped
        row(brake_onset_m=21.0),                 # braking after the apex reference: onset + derived -> NaN
        row(mean_decel_ms2=-4.0),                # impossible: only mean decel -> NaN
        row(usable=False),                       # not usable from the start
    ])
    cleaned, report = clean(data)
    assert len(cleaned) == 3
    assert report["dropped_not_dry"] == 1
    assert report["dropped_min_speed_below_40"] == 1
    onset_bad = cleaned.iloc[1]
    assert np.isnan(onset_bad["brake_onset_m"])
    assert np.isnan(onset_bad["braking_distance_m"]) and np.isnan(onset_bad["mean_decel_ms2"])
    assert onset_bad["min_speed_kmh"] == 80.0     # the row's other features are kept
    decel_bad = cleaned.iloc[2]
    assert np.isnan(decel_bad["mean_decel_ms2"]) and decel_bad["brake_onset_m"] == -140.0


def test_field_relative_subtracts_the_median_at_the_same_corner_and_session():
    data = pd.DataFrame([row(brake_onset_m=v) for v in [-150.0, -140.0, -133.0]]
                        + [row(corner="C2", brake_onset_m=-90.0)])
    relative = add_field_relative(data, features=["brake_onset_m"])
    assert list(relative["brake_onset_m_rel"]) == pytest.approx([-10.0, 0.0, 7.0, 0.0])


def test_team_season_label():
    assert list(team_season(pd.DataFrame([row(), row(team="RB", year=2023)]))) == ["McLaren 2024", "RB 2023"]

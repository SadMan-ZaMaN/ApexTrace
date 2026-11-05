"""Loading and cleaning the multi-season dataset: one place for the rules, used by every analysis.

The rules were decided during the EDA (experiments/10_eda.py, decisions.md
2026-10-17), BEFORE any modelling, so they can't be tuned to make a result
look better:
  1. dry laps only (soft / medium / hard tyres): intermediate and wet laps are
     a different driving regime;
  2. a minimum speed below 40 km/h = broken data: the whole row is dropped;
  3. any other feature outside its physical limits becomes missing (NaN) for
     that row only, so the row's other, good features are kept.
     Physical limits: brake onset in [-400, 0] m (before the corner's
     reference apex), mean deceleration in [3, 60] m/s^2, apex within +-80 m,
     throttle pickup in [-200, +200] m. Braking distance and mean
     deceleration are derived from the brake onset, so they become missing
     with it.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from apextrace.features import FEATURES

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_CSV = REPO_ROOT / "results" / "09_dataset" / "dataset.csv.gz"

DRY_COMPOUNDS = {"SOFT", "MEDIUM", "HARD"}
# Every compound label seen in 2023-2025 (OpenF1 stints): the three dry ones, the two wet ones and
# "UNKNOWN" (8 rows in 2023). A label outside this set would be dropped as "not dry" without a word,
# so the one-time 2026 script stops if it sees one (compound_check, before any feature).
KNOWN_COMPOUNDS = DRY_COMPOUNDS | {"INTERMEDIATE", "WET", "UNKNOWN"}
MAX_EMPTY_COMPOUND_SHARE = 0.05
MIN_PLAUSIBLE_SPEED_KMH = 40.0
LIMITS = {
    "brake_onset_m": (-400.0, 0.0),
    "mean_decel_ms2": (3.0, 60.0),
    "apex_m": (-80.0, 80.0),
    "throttle_pickup_m": (-200.0, 200.0),
}
# features computed from another one: if the source is out of limits, so are they
DERIVED_FROM = {"brake_onset_m": ["braking_distance_m", "mean_decel_ms2"]}
CONTINUOUS_FEATURES = [f for f in FEATURES if f != "min_gear"]


def load_dataset(path=DATASET_CSV):
    """The dataset as built by 09_build_dataset.py (all rows, usable or not)."""
    return pd.read_csv(path)


def clean(data):
    """Apply the cleaning rules; returns (clean usable dry rows, report of what was removed).

    Example: a row with brake_onset_m = +21 m (braking after the apex reference:
    the detection picked the wrong braking event) keeps its minimum speed and
    exit speed, but brake onset, braking distance and mean deceleration
    become NaN.
    """
    report = {}
    usable = data[data["usable"]].copy()
    report["usable_rows"] = int(len(usable))

    dry = usable["compound"].isin(DRY_COMPOUNDS)
    report["dropped_not_dry"] = int((~dry).sum())
    usable = usable[dry]

    broken = usable["min_speed_kmh"] < MIN_PLAUSIBLE_SPEED_KMH
    report["dropped_min_speed_below_40"] = int(broken.sum())
    usable = usable[~broken].copy()

    for feature, (low, high) in LIMITS.items():
        outside = (usable[feature] < low) | (usable[feature] > high)
        report[f"set_missing_{feature}"] = int(outside.sum())
        usable.loc[outside, feature] = np.nan
        for derived in DERIVED_FROM.get(feature, []):
            usable.loc[outside, derived] = np.nan
    report["clean_rows"] = int(len(usable))
    return usable.reset_index(drop=True), report


def add_field_relative(data, features=CONTINUOUS_FEATURES):
    """Add feature_rel = feature - median of all rows at the same (session, corner).

    A raw braking point (-140 m) mostly says which track and corner it is; the
    field-relative value says how this lap compares with everyone else at the
    same place on the same day. Example: field median -140 m, this lap
    -133 m -> brake_onset_m_rel = +7 m (braked 7 m later than the field's median).
    """
    data = data.copy()
    for feature in features:
        median = data.groupby(["session_key", "corner"])[feature].transform("median")
        data[f"{feature}_rel"] = data[feature] - median
    return data


def team_season(data):
    """A team label that survives renames within the data: team name + year.

    Teams are compared per season (a car is a season's car), so a rename
    between seasons (AlphaTauri 2023 -> RB 2024) needs no mapping.
    """
    return data["team"].astype(str) + " " + data["year"].astype(str)


def compound_check(compounds):
    """Are the tyre-compound labels the ones the cleaning rules know? Run before any feature.

    Why: `clean` keeps only SOFT, MEDIUM and HARD laps. If a new season labelled tyres
    differently (say "C3"), every lap would be dropped as "not dry" and a test would quietly
    run on nothing. Empty labels happen (48 of 2025's rows) and are dropped too, so more
    than 5 % empty also stops the run.
    Example: ["SOFT", "SOFT", None, "C3"] -> unknown ["C3"], empty share 0.25 -> not ok.
    Returns {"unknown": [...], "empty_share": float, "ok": bool}.
    """
    labels = pd.Series(list(compounds), dtype=object)
    empty = labels.isna() | (labels.astype(str).str.strip() == "")
    unknown = sorted(set(labels[~empty].astype(str)) - KNOWN_COMPOUNDS)
    empty_share = float(empty.mean()) if len(labels) else 1.0
    return {"unknown": unknown, "empty_share": empty_share,
            "ok": bool(len(labels) > 0 and not unknown and empty_share <= MAX_EMPTY_COMPOUND_SHARE)}

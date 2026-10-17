"""Driver identification on race weekends the model has never seen (H3).

The question: from a lap's corner features, can a model tell WHO drove it,
on a weekend that wasn't used for training? If the features are a real
"signature", yes; if they are mostly noise or mostly the car, no.

Pieces:
  lap_vectors          one row per lap: the mean field-relative value of each
                       feature over the lap's corners of each type (slow,
                       medium, fast), so laps from different tracks have the
                       same columns
  make_model           the classifiers, each a pipeline that fills missing
                       values and scales features using the TRAINING data only
  leave_one_session_out
                       train on all sessions but one, test on that one, repeat
  scores               balanced accuracy and macro-F1
  shuffle_within_groups the sanity check: with labels shuffled inside each
                       session, performance must drop to chance

Words:
  leakage            information from the test data reaching the training
                     (e.g. the same weekend on both sides, or a scaler fitted on
                     all data). It makes results look better than they are.
  balanced accuracy  the average of per-driver accuracy, so a driver with more
                     laps doesn't dominate. Chance = 1 / number of drivers
                     (0.5 for two teammates).
  macro-F1           the average over drivers of F1 = harmonic mean of
                     precision and recall, also treating every driver equally.
"""

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.neighbors import NearestCentroid
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

CORNER_TYPES = ("slow", "medium", "fast")
FEATURE_GROUPS = {
    "braking": ["brake_onset_m", "braking_distance_m", "mean_decel_ms2"],
    "apex": ["min_speed_kmh", "apex_m"],
    "throttle": ["throttle_pickup_m", "full_throttle_m"],
    "speeds": ["entry_speed_kmh", "exit_speed_kmh"],
    "time": ["corner_time_s"],
}
ALL_FEATURES = [feature for group in FEATURE_GROUPS.values() for feature in group]
LAP_KEYS = ["session_key", "driver", "lap"]


def lap_vectors(rows, features=ALL_FEATURES, corner_types=CORNER_TYPES):
    """One row per lap, columns "<feature>_rel__<type>": the mean over the lap's corners of that type.

    `rows` are clean dataset rows with field-relative columns (dataset.add_field_relative).
    Example: a lap with two slow corners whose brake_onset_m_rel are +3 and +5 m
    gets brake_onset_m_rel__slow = +4 m. A corner type the track doesn't have
    (or whose features were all missing) stays NaN; the model fills it from the
    training data.
    Also keeps year, team, location and lap_time_s for the baselines.
    """
    columns = [f"{feature}_rel" for feature in features]
    means = rows.groupby(LAP_KEYS + ["corner_type"])[columns].mean()
    wide = means.unstack("corner_type")
    wide.columns = [f"{feature}__{corner_type}" for feature, corner_type in wide.columns]
    ordered = [f"{c}__{t}" for c in columns for t in corner_types if f"{c}__{t}" in wide.columns]
    wide = wide[ordered]
    info = rows.groupby(LAP_KEYS)[["year", "team", "location", "lap_time_s"]].first()
    return info.join(wide).reset_index()


def make_model(kind):
    """A fresh classifier. All steps are fitted on the training data only (no leakage).

    nearest_centroid: each driver = the average of their training laps; a test
        lap goes to the closest average (after scaling). Simple and transparent.
    logistic: logistic regression, a linear model with one weight per feature
        and driver; class_weight="balanced" so drivers with fewer laps count equally.
    majority: always predicts the most common driver in training (the floor).
    """
    if kind == "majority":
        return DummyClassifier(strategy="most_frequent")
    if kind == "nearest_centroid":
        classifier = NearestCentroid()
    elif kind == "logistic":
        classifier = LogisticRegression(max_iter=5000, class_weight="balanced")
    else:
        raise ValueError(f"unknown model kind: {kind}")
    return Pipeline([("fill_missing", SimpleImputer(strategy="median")),
                     ("scale", StandardScaler()),
                     ("classify", classifier)])


def leave_one_session_out(X, y, groups, kind):
    """Predictions for every row, each made by a model that never saw that row's session.

    For each session: train on all other sessions, predict this one. A session
    whose training data has fewer than two drivers can't be predicted (None).
    The assert is a leakage guard: a session is never on both sides.
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y)
    groups = np.asarray(groups)
    predictions = np.full(len(y), None, dtype=object)
    for group in np.unique(groups):
        test = groups == group
        train = ~test
        assert not set(groups[train]) & set(groups[test]), "leakage: a session is on both sides"
        if len(np.unique(y[train])) < 2:
            continue
        model = make_model(kind)
        model.fit(X[train], y[train])
        predictions[test] = model.predict(X[test])
    return predictions


def scores(y_true, y_pred):
    """Balanced accuracy and macro-F1 over the rows that got a prediction."""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred, dtype=object)
    predicted = np.array([p is not None for p in y_pred])
    if predicted.sum() == 0:
        return {"n": 0, "balanced_accuracy": float("nan"), "macro_f1": float("nan")}
    t = y_true[predicted].astype(str)
    p = y_pred[predicted].astype(str)
    return {"n": int(predicted.sum()),
            "balanced_accuracy": float(balanced_accuracy_score(t, p)),
            "macro_f1": float(f1_score(t, p, average="macro"))}


def shuffle_within_groups(y, groups, rng):
    """Shuffle the labels inside each session: keeps how many laps each driver has per session,
    destroys any link between features and driver. A model must then score at chance level."""
    y = np.asarray(y).copy()
    groups = np.asarray(groups)
    for group in np.unique(groups):
        where = np.where(groups == group)[0]
        y[where] = rng.permutation(y[where])
    return y


# ---------------------------------------------------------------- the per-lap table used by the models

RAW_STATS = ["mean_speed", "max_speed", "mean_throttle", "share_full_throttle", "share_braking"]


def raw_lap_statistics(raw_samples):
    """Simple whole-lap telemetry summaries per lap (the "raw summary statistics" baseline).

    raw_samples: the table saved by 09_build_dataset.py (raw_samples.parquet).
    mean/max speed, mean throttle, share of samples at >= 99 % throttle,
    share of samples with the brake flag on.
    """
    grouped = raw_samples.groupby(LAP_KEYS)
    return pd.DataFrame({
        "mean_speed": grouped["speed_kmh"].mean(),
        "max_speed": grouped["speed_kmh"].max(),
        "mean_throttle": grouped["throttle_pct"].mean(),
        "share_full_throttle": grouped["throttle_pct"].apply(lambda v: float(np.mean(v >= 99))),
        "share_braking": grouped["brake"].mean(),
    }).reset_index()


def build_lap_table(clean_rows_with_rel, raw_samples):
    """One row per lap: corner features per type (lap_vectors), raw lap statistics, and
    field-relative versions of lap time and the raw statistics (minus the session median)."""
    from apextrace.dataset import team_season

    laps = lap_vectors(clean_rows_with_rel)
    laps = laps.merge(raw_lap_statistics(raw_samples), on=LAP_KEYS, how="left")
    laps["team_season"] = team_season(laps)
    for column in ["lap_time_s"] + RAW_STATS:
        laps[f"{column}_rel"] = laps[column] - laps.groupby("session_key")[column].transform("median")
    return laps

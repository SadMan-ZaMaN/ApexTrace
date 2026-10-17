"""Season signatures and how close they are: the tools for "is it the driver or the car?" (H4).

A driver's season signature = their average field-relative corner features
over a season (per corner type), with every race weekend counting equally.
Averaging ~20 weekends removes much of the weekend-to-weekend noise that made
single-weekend signatures weak (H1: weekend ICC 0.04-0.40).

The question for a driver who changed teams: is their new-season signature
closer to THEIR OWN old signature (the signature follows the driver), or to
the old signatures of the drivers of their NEW car (the signature belongs to
the car)? Development (2023 -> 2024, nobody changed teams): the same question
with the teammate in place of the new car's drivers: own old signature vs the
teammate's old signature (the same car).
"""

import numpy as np
import pandas as pd


def season_signatures(laps, feature_columns, min_sessions=5):
    """One row per (driver, year): the mean over sessions of the driver's session means.

    Each session counts once, however many laps it had (a 9-lap weekend
    shouldn't outweigh a 3-lap one). Drivers with fewer than min_sessions
    sessions in a year are left out (stand-ins: too little to average).
    Also keeps the team the driver drove for most in that year.
    """
    session_means = laps.groupby(["year", "session_key", "driver"])[feature_columns].mean().reset_index()
    sessions = session_means.groupby(["driver", "year"])["session_key"].nunique()
    signatures = session_means.groupby(["driver", "year"])[feature_columns].mean()
    teams = laps.groupby(["driver", "year"])["team"].agg(lambda t: t.value_counts().index[0])
    signatures["team"] = teams
    signatures["sessions"] = sessions
    return signatures[signatures["sessions"] >= min_sessions]


def standardise(signatures, feature_columns, reference):
    """Divide each feature by its spread across the REFERENCE signatures (z-scores).

    Why: a 10 m difference in braking point and a 10 km/h difference in
    minimum speed aren't comparable; after dividing by how much drivers
    usually differ on each feature, each feature counts in "typical driver
    differences". Mean and spread come from the reference set only.
    Example: reference brake-onset offsets with SD 4 m -> a 6 m difference = 1.5.
    """
    mean = reference[feature_columns].mean()
    spread = reference[feature_columns].std(ddof=1).replace(0, np.nan)
    out = signatures.copy()
    out[feature_columns] = (signatures[feature_columns] - mean) / spread
    return out


def distance(a, b):
    """Root-mean-square difference over the features both signatures have (NaN-safe).

    Using the mean over shared features (not the sum) keeps distances
    comparable when a feature is missing for one driver.
    Example: differences (1, -2, NaN) -> sqrt((1 + 4) / 2) = 1.58.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    both = np.isfinite(a) & np.isfinite(b)
    if not both.any():
        return float("nan")
    return float(np.sqrt(np.mean((a[both] - b[both]) ** 2)))


def distance_table(targets, references, feature_columns):
    """Distance from every target signature (rows) to every reference signature (columns)."""
    table = pd.DataFrame(index=targets.index, columns=references.index, dtype=float)
    for target_key, target in targets.iterrows():
        for reference_key, reference in references.iterrows():
            table.loc[target_key, reference_key] = distance(target[feature_columns], reference[feature_columns])
    return table


def own_rank(distances, driver):
    """Rank (1 = closest) of the driver's own reference signature among all reference drivers."""
    row = distances.loc[driver].sort_values()
    return int(list(row.index).index(driver)) + 1


def sign_test_p(successes, trials):
    """One-sided sign test: P(at least `successes` of `trials`) if each were a coin flip.

    Example: 5 of 5 -> 1/32 = 0.031; 4 of 5 -> 6/32 = 0.19.
    """
    from math import comb

    return float(sum(comb(trials, k) for k in range(successes, trials + 1)) / 2 ** trials)

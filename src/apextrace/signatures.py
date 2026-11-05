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


def most_weekends_team(laps, driver):
    """The team a driver drove for on the most weekends (alphabetically first on a tie).

    Example: 19 weekends for one team and 2 for another -> the first team.
    """
    weekends = laps[laps["driver"] == driver].groupby("team")["session_key"].nunique()
    return weekends.idxmax()


def season_or_empty(laps, feature_columns, min_sessions, year):
    """season_signatures for one year, or an empty table if no driver has min_sessions weekends
    (so a short or empty season gives "nobody to compare", not a crash)."""
    signatures = season_signatures(laps, feature_columns, min_sessions)
    if year not in set(signatures.index.get_level_values("year")):
        return signatures.iloc[0:0].droplevel("year")
    return signatures.xs(year, level="year")


def equal_laps_per_session(pair, driver, teammate):
    """Both drivers with the same number of laps in every session: k = the smaller count,
    and each driver's FIRST k laps (lowest lap numbers).

    Why: a weekend mean over fewer laps is noisier, and a noisier reference sits farther
    from everything. A driver knocked out in Q1 has ~3 push laps, one who reaches Q3 ~6;
    with all laps the Q3 driver's own past would look closer for no reason (synthetic,
    car only, 6 against 2 laps: 0.57-0.62 "own closer" instead of 0.5; review of
    2026-11-06). The first laps are used because both teammates run them at about the same
    time of the session, on a similar track, and "first" is a rule, not a choice.
    Example: own laps 3, 5, 9, 12 and teammate laps 4, 7 -> k = 2: own 3, 5; teammate 4, 7.
    """
    kept = []
    for _, session in pair.groupby("session_key"):
        own = session[session["driver"] == driver].sort_values("lap")
        mate = session[session["driver"] == teammate].sort_values("lap")
        k = min(len(own), len(mate))
        kept.append(own.head(k))
        kept.append(mate.head(k))
    return pd.concat(kept)


def own_vs_past_teammate(laps, reference_year, target_year, feature_columns, min_sessions=5,
                         shared_weekends_only=True, leave_pair_out=True, equal_laps=True):
    """H5's comparison: is a driver's target-season signature closer to their OWN
    reference-season signature than to their reference-season TEAMMATE's?

    Both references were made in the same car, so if the signature were only the
    car, the target would be equally close to both: a coin flip per driver. That
    holds for drivers who later changed team too, so everyone in both seasons can
    take part (docs/h5_design.md).

    The two references are built only on the weekends the teammates SHARED in the
    reference season (shared_weekends_only=True). Why: a signature averaged over
    fewer weekends is noisier, and a noisier reference sits farther from everything.
    With 20 weekends against 5, the teammate's noise is sqrt(20/5) = 2 times larger,
    and the driver's own past would look closer for no real reason.
    shared_weekends_only=False uses each driver's full-season signature instead;
    it exists only to show that bias in the tests.

    On each shared weekend both references use the same number of laps
    (equal_laps_per_session): the same reason one level down, since a driver out in Q1
    has fewer laps than one in Q3. equal_laps=False keeps every lap; it exists only to
    show that bias (experiments/22_h5_null_check.py, case E).

    The teammate is the other driver of the driver's most-driven reference team with
    the most shared weekends (alphabetical on a tie).

    Everything is z-scored (standardise) with the spread of the OTHER drivers'
    full-season reference signatures: the driver and the teammate are left out. Why:
    a teammate with few weekends has a noisy signature that is often far out on some
    feature. If that signature were part of the spread, it would inflate the spread of
    exactly that feature, which shrinks the distance on it: the teammate would look
    closer than it is. Found on synthetic laps with only the car (5 of 12 weekends):
    0.43 "own closer" over 1,500 trials instead of 0.5; with the pair left out, 0.5
    (experiments/22_h5_null_check.py). leave_pair_out=False keeps the pair in the
    spread; like shared_weekends_only=False, it exists only to show the bias.

    Returns one row per driver who has >= min_sessions weekends in both seasons, with
    `included` = False and a `reason` when no teammate shared >= min_sessions weekends.
    Example: distances 0.8 to the own past and 1.1 to the teammate's -> own_closer.
    """
    reference_laps = laps[laps["year"] == reference_year]
    target_laps = laps[laps["year"] == target_year]
    reference_all = season_or_empty(reference_laps, feature_columns, min_sessions, reference_year)
    targets = season_or_empty(target_laps, feature_columns, min_sessions, target_year)

    rows = []
    for driver in sorted(set(targets.index) & set(reference_all.index)):
        team = most_weekends_team(reference_laps, driver)
        row = {"driver": driver, "team_reference": team, "team_target": most_weekends_team(target_laps, driver),
               "weekends_target": int(targets.loc[driver, "sessions"])}
        team_laps = reference_laps[reference_laps["team"] == team]
        own_weekends = set(team_laps.loc[team_laps["driver"] == driver, "session_key"])
        teammate, shared = None, set()
        for other in sorted(team_laps["driver"].unique()):
            if other == driver:
                continue
            common = own_weekends & set(team_laps.loc[team_laps["driver"] == other, "session_key"])
            if len(common) > len(shared):
                teammate, shared = other, common
        if len(shared) < min_sessions:
            rows.append({**row, "included": False, "reason": f"no teammate shared {min_sessions} weekends"})
            continue

        lap_counts = {}
        if shared_weekends_only:
            pair = team_laps[team_laps["driver"].isin([driver, teammate]) & team_laps["session_key"].isin(shared)]
            lap_counts = {"laps_own_all": int((pair["driver"] == driver).sum()),
                          "laps_teammate_all": int((pair["driver"] == teammate).sum())}
            if equal_laps:
                pair = equal_laps_per_session(pair, driver, teammate)
            lap_counts["laps_each_used"] = int((pair["driver"] == driver).sum())
            references = season_or_empty(pair, feature_columns, min_sessions, reference_year)
        else:
            references = reference_all
        if teammate not in references.index:
            rows.append({**row, "included": False, "reason": f"teammate has fewer than {min_sessions} weekends"})
            continue
        others = reference_all.drop(index=[driver, teammate], errors="ignore") if leave_pair_out else reference_all
        references_z = standardise(references, feature_columns, others)
        target = standardise(targets.loc[[driver]], feature_columns, others).loc[driver, feature_columns]
        d_own = distance(target, references_z.loc[driver, feature_columns])
        d_mate = distance(target, references_z.loc[teammate, feature_columns])
        rows.append({**row, "included": True, "reason": "", "teammate": teammate, "shared_weekends": len(shared),
                     **lap_counts, "distance_own": d_own, "distance_teammate": d_mate,
                     "own_closer": bool(d_own < d_mate)})
    return pd.DataFrame(rows)


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


def sign_test_threshold(trials, alpha=0.05):
    """The fewest successes out of `trials` that the one-sided sign test calls significant (p < alpha).

    None if even all `trials` aren't enough. This is what the preregistration
    states in advance: how many drivers must go the driver's way.
    Example: 10 trials -> 9 (9 of 10: p = 11/1024 = 0.011; 8 of 10: p = 56/1024 = 0.055).
    4 trials -> None (4 of 4: p = 1/16 = 0.0625).
    """
    for successes in range(trials + 1):
        if sign_test_p(successes, trials) < alpha:
            return successes
    return None


def sign_test_power(trials, success_probability, alpha=0.05):
    """Power: the chance that the sign test comes out significant, if each driver
    independently goes the driver's way with `success_probability`.

    Power = P(at least the threshold number of successes) under a binomial with
    that probability. At success_probability = 0.5 (no signature) it equals the
    test's real false-positive rate, which is at most alpha.
    Example: 10 drivers, each 80 % likely to be closer to their own past: the test
    needs 9 of 10, P(9 or 10) = 10 * 0.8^9 * 0.2 + 0.8^10 = 0.376.
    """
    from math import comb

    threshold = sign_test_threshold(trials, alpha)
    if threshold is None:
        return 0.0
    power = 0.0
    for k in range(threshold, trials + 1):
        power += comb(trials, k) * success_probability ** k * (1 - success_probability) ** (trials - k)
    return float(power)

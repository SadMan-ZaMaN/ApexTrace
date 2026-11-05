"""The 2026 test protocol (preregistration Part C), shared by the dry runs and the one-time run.

Design and reasons: docs/h5_design.md. The one-time script (experiments/23_final_2026.py)
only downloads, checks and builds; every result comes from the functions here, so the dry
runs on 2024 and 2025 test exactly the code that will run on 2026.

  H5, primary     signatures.own_vs_past_teammate on all 30 lap-vector features: is the
                  target-season signature closer to the driver's own reference-season
                  signature than to the reference-season teammate's? One-sided sign test,
                  supported if p < 0.05.
  H5, secondary   the same with feature groups (control points / energy-sensitive) and
                  without throttle; the share with an exact 95 % interval.
  H4, secondary   team changers found by teams.team_changers: is the target signature
                  closer to the own reference signature than to the NEW teammate's (same
                  car, same weekends)? Part B's comparison, with the pair left out of the
                  z-score spread (the Day 9 lesson). The same for the drivers who stayed
                  (control) and Fisher's exact test of changers vs stayers.
"""

import numpy as np
import pandas as pd
from scipy.stats import binomtest, fisher_exact

from apextrace.dataset import add_field_relative, clean
from apextrace.identification import build_lap_table
from apextrace.signatures import (distance, own_vs_past_teammate, season_or_empty, sign_test_p,
                                  sign_test_threshold, standardise)
from apextrace.teams import lineage, team_changers

MIN_WEEKENDS = 5
CONTROL_POINTS = ["brake_onset_m", "min_speed_kmh", "apex_m", "throttle_pickup_m"]
ENERGY_SENSITIVE = ["entry_speed_kmh", "exit_speed_kmh", "full_throttle_m", "corner_time_s"]
THROTTLE = ["throttle_pickup_m", "full_throttle_m"]


# ---------------------------------------------------------------- inputs

def lap_table_from(dataset, raw_samples):
    """Dataset rows + raw samples -> the lap table (30 lap-vector columns), exactly as for H3/H4:
    clean (rules fixed in the 2023-24 EDA) -> field-relative -> lap vectors. Returns (laps, cleaning)."""
    rows, cleaning = clean(dataset)
    columns = ["session_key", "driver", "lap", "speed_kmh", "throttle_pct", "brake"]
    return build_lap_table(add_field_relative(rows), raw_samples[columns]), cleaning


def lap_vector_columns(laps):
    """The lap-vector columns: "<feature>_rel__<corner type>" (30 when all three types exist)."""
    return [column for column in laps.columns if "__" in column]


def columns_of(columns, names):
    """The lap-vector columns that belong to the named features."""
    chosen = []
    for column in columns:
        if column.split("_rel__")[0] in names:
            chosen.append(column)
    return chosen


def feature_sets(columns):
    """Primary and secondary feature sets: name -> columns.
    Example with all 30 columns: all 30 / control points 12 / energy-sensitive 12 / no throttle 24."""
    every_feature = sorted({column.split("_rel__")[0] for column in columns})
    without_throttle = [name for name in every_feature if name not in THROTTLE]
    return {"all": list(columns),
            "control points": columns_of(columns, CONTROL_POINTS),
            "energy-sensitive": columns_of(columns, ENERGY_SENSITIVE),
            "no throttle": columns_of(columns, without_throttle)}


# ---------------------------------------------------------------- counting

def sign_summary(table):
    """Count, share, exact 95 % interval and one-sided sign test for the included rows.

    Also says whether a "yes" was possible at all: with 4 or fewer drivers even all of
    them going the driver's way gives p >= 0.0625, so the result is descriptive only.
    Example: 15 of 16 -> share 0.94, interval 0.70-1.00, p = 0.0003.
    """
    included = table
    if "included" in table.columns:
        included = table[table["included"] == True]  # noqa: E712 (column of True/False)
    if "own_closer" in included.columns:
        successes, trials = int(included["own_closer"].sum()), int(len(included))
    else:
        successes, trials = 0, 0            # no driver could be compared
    summary = {"drivers": trials, "own_closer": successes, "test_possible": sign_test_threshold(trials) is not None
               if trials else False}
    if trials == 0:
        return {**summary, "share": None, "ci95_low": None, "ci95_high": None, "sign_test_p": None}
    interval = binomtest(successes, trials).proportion_ci(confidence_level=0.95, method="exact")
    return {**summary, "share": successes / trials, "ci95_low": float(interval.low),
            "ci95_high": float(interval.high), "sign_test_p": sign_test_p(successes, trials)}


# ---------------------------------------------------------------- H5

def h5_results(laps, reference_year, target_year):
    """H5 primary and secondary results. Returns (tables: name -> per-driver table, summary).

    summary["verdict"] is the preregistered decision on the primary set: "supported" (sign
    test p < 0.05), "not supported", or "not testable" (too few drivers for any p < 0.05:
    with 4 drivers even 4 of 4 gives p = 0.0625). summary["supported"] is True only for the first.
    """
    columns = lap_vector_columns(laps)
    tables, summary = {}, {"features": len(columns), "sets": {}}
    for name, set_columns in feature_sets(columns).items():
        table = own_vs_past_teammate(laps, reference_year, target_year, set_columns, MIN_WEEKENDS)
        tables[name] = table
        summary["sets"][name] = {"columns": len(set_columns), **sign_summary(table)}
    primary = summary["sets"]["all"]
    if not primary["test_possible"]:
        summary["verdict"] = "not testable"
    elif primary["sign_test_p"] < 0.05:
        summary["verdict"] = "supported"
    else:
        summary["verdict"] = "not supported"
    summary["supported"] = summary["verdict"] == "supported"
    return tables, summary


def corner_type_counts(corners):
    """How many detected corners of each type a season has, in total and per session.

    Why (docs/h5_design.md section 4): corners are typed by minimum speed, and with less
    downforce in 2026 some "fast" corners may become "medium". This is reported next to the
    result, not used in it. Example: 23 sessions with 314 corners -> 13.7 per session.
    """
    counts = {}
    sessions = max(int(corners["session_key"].nunique()), 1)
    for corner_type in ("slow", "medium", "fast"):
        total = int((corners["type"] == corner_type).sum())
        counts[corner_type] = {"corners": total, "per_session": total / sessions}
    return counts


# ---------------------------------------------------------------- H4 on team changers

def new_teammate_comparison(laps, reference_year, target_year, drivers, feature_columns, leave_pair_out=True):
    """Part B's H4 comparison for a list of drivers: is the target-season signature closer
    to the driver's OWN reference-season signature (another car, a year earlier) than to
    the NEW teammate's target-season signature (same car, same weekends)?

    As in Part B: the driver's target signature uses only the weekends with their main
    target team, and the new teammate (the other driver of that team with the most shared
    weekends) only those same weekends. z-scores use the reference-season spread; with
    leave_pair_out=True the driver and the new teammate are left out of it (Day 9: a
    signature inside the spread shrinks its own distance). leave_pair_out=False is Part B
    exactly, kept to reproduce the frozen 2025 numbers.
    """
    reference_laps = laps[laps["year"] == reference_year]
    # within the target season, teams are grouped by lineage, so a mid-season rename can't split one
    target_laps = laps[laps["year"] == target_year].copy()
    target_laps["lineage"] = [lineage(team) for team in target_laps["team"]]
    reference_raw = season_or_empty(reference_laps, feature_columns, MIN_WEEKENDS, reference_year)
    rows = []
    for driver in drivers:
        row = {"driver": driver}
        if driver not in reference_raw.index:
            rows.append({**row, "included": False, "reason": f"fewer than {MIN_WEEKENDS} weekends in {reference_year}"})
            continue
        own = target_laps[target_laps["driver"] == driver]
        per_team = own.groupby("lineage")["session_key"].nunique()
        team, weekends = per_team.idxmax(), int(per_team.max())
        team_laps = target_laps[target_laps["lineage"] == team]
        driver_sessions = set(team_laps.loc[team_laps["driver"] == driver, "session_key"])
        others = team_laps[(team_laps["driver"] != driver) & team_laps["session_key"].isin(driver_sessions)]
        if weekends < MIN_WEEKENDS or others.empty:
            rows.append({**row, "included": False, "reason": f"fewer than {MIN_WEEKENDS} weekends with the new team"})
            continue
        teammate = others.groupby("driver")["session_key"].nunique().idxmax()
        pair_laps = team_laps[team_laps["driver"].isin([driver, teammate]) & team_laps["session_key"].isin(driver_sessions)]
        target_raw = season_or_empty(pair_laps, feature_columns, MIN_WEEKENDS, target_year)
        if teammate not in target_raw.index or driver not in target_raw.index:
            rows.append({**row, "included": False, "reason": f"teammate with fewer than {MIN_WEEKENDS} shared weekends"})
            continue
        spread = reference_raw.drop(index=[driver, teammate], errors="ignore") if leave_pair_out else reference_raw
        reference_z = standardise(reference_raw, feature_columns, spread)
        target_z = standardise(target_raw, feature_columns, spread)
        d_own = distance(target_z.loc[driver, feature_columns], reference_z.loc[driver, feature_columns])
        d_mate = distance(target_z.loc[driver, feature_columns], target_z.loc[teammate, feature_columns])
        rows.append({**row, "included": True, "reason": "", "team_target": team, "weekends_target": weekends,
                     "teammate_target": teammate, "team_reference": reference_raw.loc[driver, "team"],
                     "distance_own_reference": d_own, "distance_new_teammate": d_mate,
                     "own_closer": bool(d_own < d_mate)})
    return pd.DataFrame(rows)


def h4_results(laps, reference_year, target_year, leave_pair_out=True):
    """H4 on the team changers found in the data, the stayer control, and Fisher's exact test.

    Returns (changes, changers table, stayers table, summary). Changers and stayers are the
    `eligible` drivers of teams.team_changers (>= 5 weekends in both seasons).
    Fisher's exact test asks: if changers and stayers had the same rate of "own closer",
    how likely is a split at least this uneven? Example (2025, exploratory): 2 of 5 vs 8 of
    10 -> p = 0.25.
    """
    columns = lap_vector_columns(laps)
    changes = team_changers(laps, reference_year, target_year, MIN_WEEKENDS)
    eligible = changes[changes["eligible"]]
    changers = new_teammate_comparison(laps, reference_year, target_year,
                                       sorted(eligible.loc[eligible["changed"], "driver"]), columns, leave_pair_out)
    stayers = new_teammate_comparison(laps, reference_year, target_year,
                                      sorted(eligible.loc[~eligible["changed"], "driver"]), columns, leave_pair_out)
    summary = {"changers": sign_summary(changers), "stayers": sign_summary(stayers),
               "changer_names": sorted(eligible.loc[eligible["changed"], "driver"]),
               "leave_pair_out": leave_pair_out,
               "note": "secondary (docs/h5_design.md section 5): reported, not a decision"}
    a, b = summary["changers"], summary["stayers"]
    if a["drivers"] and b["drivers"]:
        table = [[a["own_closer"], a["drivers"] - a["own_closer"]], [b["own_closer"], b["drivers"] - b["own_closer"]]]
        summary["fisher_exact_two_sided_p"] = float(fisher_exact(table).pvalue)
    else:
        summary["fisher_exact_two_sided_p"] = None
    return changes, changers, stayers, summary

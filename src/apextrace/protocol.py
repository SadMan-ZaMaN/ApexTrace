"""The identification protocol, shared by the development runs (2023-2024) and the final 2025 run.

Moved here from experiments/12_identification.py (unchanged, checked: the
development results are identical) so that the one-time 2025 evaluation
uses EXACTLY the code that produced the development numbers, as the
preregistration (Part B) requires.

  feature_sets      the baselines and our features, by name
  run               leave-one-session-out with the right model for each name
  weekend_vote      a driver's laps in a held-out weekend vote together
  teammate_task     task (a): the two drivers of each team-season
  summarise_teammates  means with bootstrap intervals, Wilcoxon tests
"""

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from apextrace.identification import FEATURE_GROUPS, RAW_STATS, leave_one_session_out, scores, shuffle_within_groups


def feature_sets(laps):
    """The inputs of each model, by name.

    "our features" are the 30 corner columns ("<feature>_rel__<type>": 10 features x slow,
    medium, fast); the baselines are lap time alone and the 5 whole-lap statistics. "majority"
    ignores its inputs (it always guesses the driver with more training laps: the floor), and
    "our features (nearest centroid)" uses the same 30 columns with the simplest classifier, to
    check that the result is not a property of logistic regression.
    Example: a lap table with the 30 corner columns gives "our features" = those 30 columns and
    "our features + lap time" = 31.
    """
    ours = [c for c in laps.columns if "__" in c]
    return {
        "majority": ours,                      # ignored by the model
        "lap time only": ["lap_time_s_rel"],
        "raw lap statistics": [f"{c}_rel" for c in RAW_STATS],
        "our features (nearest centroid)": ours,
        "our features": ours,
        "our features + lap time": ours + ["lap_time_s_rel"],
    }


MODEL_KIND = {"majority": "majority", "our features (nearest centroid)": "nearest_centroid"}


def run(laps, columns, name, labels=None, kind=None):
    """Leave-one-weekend-out predictions for one set of inputs, and their scores.

    labels replaces the true drivers (the shuffled-label control); kind overrides the model,
    which otherwise follows the name (MODEL_KIND; logistic regression by default).
    Returns (one prediction per lap, None where a weekend could not be predicted;
    {"n", "balanced_accuracy", "macro_f1"}).
    Example: a pair with 18 shared weekends -> 18 models, each trained on 17 weekends.
    """
    kind = kind or MODEL_KIND.get(name, "logistic")
    y = laps["driver"].to_numpy() if labels is None else labels
    predictions = leave_one_session_out(laps[columns].to_numpy(dtype=float), y, laps["session_key"].to_numpy(), kind)
    return predictions, scores(y, predictions)


def weekend_vote(laps, predictions):
    """Each (held-out session, driver): the most common prediction among that driver's laps."""
    frame = pd.DataFrame({"session_key": laps["session_key"].to_numpy(), "driver": laps["driver"].to_numpy(),
                          "predicted": predictions})
    frame = frame[frame["predicted"].notna()]
    votes = frame.groupby(["session_key", "driver"])["predicted"].agg(lambda v: v.value_counts().index[0]).reset_index()
    return scores(votes["driver"].to_numpy(), votes["predicted"].to_numpy(dtype=object))


def teammate_task(laps, rng, shuffles=5, verbose=True):
    """Task (a) of H3: for every team-season, can the inputs tell its two drivers apart on
    weekends the model never saw?

    The pair is the two drivers with most laps, compared on the weekends both drove; with fewer
    than 5 such weekends the team-season is skipped (a stand-in for two races can't be tested
    fairly). For each pair: every input set of feature_sets; the weekend vote; `shuffles` runs
    with the drivers' labels shuffled inside each weekend (must score about 0.5, else something
    leaks); each feature group left out in turn (an ablation: how much the score drops without
    it); and each whole-lap statistic alone, with how often the same driver is higher.
    Example: a team with drivers A (96 laps), B (90) and a stand-in C (8 laps) is compared as
    A vs B on the weekends both drove; C's laps are not used.
    Returns one row per team-season (tests/test_protocol.py checks it on planted differences).
    """
    sets = feature_sets(laps)
    ours = sets["our features"]
    rows = []
    for label, team_laps in laps.groupby("team_season"):
        top_two = team_laps["driver"].value_counts().index[:2].tolist()
        pair = team_laps[team_laps["driver"].isin(top_two)]
        both = pair.groupby("session_key")["driver"].nunique()
        pair = pair[pair["session_key"].isin(both[both == 2].index)].reset_index(drop=True)
        if pair["session_key"].nunique() < 5:
            continue
        row = {"team_season": label, "drivers": " vs ".join(sorted(top_two)),
               "sessions": int(pair["session_key"].nunique()), "laps": len(pair)}
        for name, columns in sets.items():
            predictions, result = run(pair, columns, name)
            row[f"{name} | balanced_accuracy"] = result["balanced_accuracy"]
            row[f"{name} | macro_f1"] = result["macro_f1"]
            if name == "our features":
                row["our features | weekend vote"] = weekend_vote(pair, predictions)["balanced_accuracy"]
        shuffled = []
        for _ in range(shuffles):
            labels = shuffle_within_groups(pair["driver"].to_numpy(), pair["session_key"].to_numpy(), rng)
            shuffled.append(run(pair, ours, "our features", labels=labels)[1]["balanced_accuracy"])
        row["shuffled labels | balanced_accuracy"] = float(np.mean(shuffled))
        for group, features in FEATURE_GROUPS.items():
            kept = [c for c in ours if not any(c.startswith(f"{f}_rel__") for f in features)]
            row[f"without {group} | balanced_accuracy"] = run(pair, kept, "our features")[1]["balanced_accuracy"]
        # Which raw statistic carries the raw baseline? Each one alone, and how
        # consistent the sign of the teammate difference is across sessions
        # (1.0 = the same driver is higher in every session).
        for stat in RAW_STATS:
            row[f"raw {stat} alone | balanced_accuracy"] = run(pair, [f"{stat}_rel"], "lap time only")[1]["balanced_accuracy"]
            per_session = pair.groupby(["session_key", "driver"])[f"{stat}_rel"].mean().unstack()
            difference = per_session[top_two[0]] - per_session[top_two[1]]
            row[f"raw {stat} | same sign share"] = float(max((difference > 0).mean(), (difference < 0).mean()))
        rows.append(row)
        if verbose:
            print(f"{label:28s} {row['drivers']:10s} {row['sessions']:2d} sessions {row['laps']:3d} laps | "
                  f"lap time {row['lap time only | balanced_accuracy']:.2f}  raw {row['raw lap statistics | balanced_accuracy']:.2f}  "
                  f"ours {row['our features | balanced_accuracy']:.2f}  +time {row['our features + lap time | balanced_accuracy']:.2f}  "
                  f"vote {row['our features | weekend vote']:.2f}  shuffled {row['shuffled labels | balanced_accuracy']:.2f}",
                  flush=True)
    return pd.DataFrame(rows)


def summarise_teammates(table, rng):
    """Means over team-seasons with 95 % bootstrap intervals (team-seasons resampled 5,000
    times), and our features against each baseline: the mean difference, the number of
    team-seasons where ours was higher, and a two-sided Wilcoxon signed-rank test over the
    paired differences (one per team-season).
    Example: four team-seasons, all higher with our features than with lap time -> wins 4,
    Wilcoxon p = 2 / 2^4 = 0.125, the smallest possible with four.
    """
    summary = {}
    columns = [c for c in table.columns if c.endswith("| balanced_accuracy") or c.endswith("| weekend vote")
               or c.endswith("| same sign share")]
    for column in columns:
        values = table[column].dropna().to_numpy()
        draws = [np.mean(rng.choice(values, size=len(values))) for _ in range(5000)]
        summary[column] = {"mean": float(np.mean(values)), "ci95_low": float(np.percentile(draws, 2.5)),
                           "ci95_high": float(np.percentile(draws, 97.5)), "team_seasons": int(len(values))}
    for baseline in ["lap time only | balanced_accuracy", "raw lap statistics | balanced_accuracy"]:
        difference = table["our features | balanced_accuracy"] - table[baseline]
        test = scipy_stats.wilcoxon(difference)
        summary[f"ours minus {baseline.split(' |')[0]}"] = {
            "mean_difference": float(difference.mean()), "wins": int((difference > 0).sum()),
            "team_seasons": int(len(difference)), "wilcoxon_p": float(test.pvalue)}
    return summary

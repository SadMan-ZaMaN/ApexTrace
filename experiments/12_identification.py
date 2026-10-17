"""Phase 6, H3: can a model tell who drove a lap, on a race weekend it never saw? (2023-2024 only)

Data: clean dry qualifying laps (apextrace.dataset), one row per lap
(identification.lap_vectors): the lap's mean field-relative value of each
feature per corner type (~30 numbers, comparable across tracks).

Field-relative values use the median of the SAME session's laps, including
the held-out session's own laps: that needs no labels (no driver names), only
that session's telemetry, which is available at prediction time, so it is not
leakage. Everything with labels (model weights, the fill-in values for missing
features, the scaling) is fitted on the training sessions only.

Task (a), teammates: for each team and season, the two drivers with the most
  laps, in sessions where both have laps; a binary task (chance = 0.5). Same
  car, so this is the cleanest test of a DRIVER signature. ~20 replications.
Task (b), all drivers of a season (drivers with laps in >= 5 sessions):
  multi-class. Confounded by the car: two cars look different even with the
  same driving. Reported, but not the main evidence.

Split: leave-one-session-out. Baselines, in order: majority class; lap time
only (field-relative); raw lap summary statistics (mean speed, max speed,
mean throttle, share of full throttle, share of braking; field-relative);
then our features (logistic regression, nearest centroid); our features +
lap time. Checks: shuffled labels (must give chance), ablation (remove one
feature group at a time), and a weekend-level vote (each driver's laps in the
held-out session vote).

Outputs in results/12_identification/. Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\12_identification.py
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from apextrace.dataset import add_field_relative, clean, load_dataset, team_season
from apextrace.identification import (FEATURE_GROUPS, LAP_KEYS, lap_vectors, leave_one_session_out, scores,
                                      shuffle_within_groups)
from apextrace.plots import SERIES, TEXT_SECONDARY, apply_style

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW = REPO_ROOT / "results" / "09_dataset" / "raw_samples.parquet"
OUT_DIR = REPO_ROOT / "results" / "12_identification"
SEED = 2026
SHUFFLES = 5
MIN_SESSIONS_MULTICLASS = 5
RAW_STATS = ["mean_speed", "max_speed", "mean_throttle", "share_full_throttle", "share_braking"]


# ---------------------------------------------------------------- inputs

def raw_lap_statistics():
    """Simple whole-lap telemetry summaries per lap (the 'raw summary statistics' baseline)."""
    raw = pd.read_parquet(RAW, columns=["session_key", "driver", "lap", "speed_kmh", "throttle_pct", "brake"])
    grouped = raw.groupby(LAP_KEYS)
    table = pd.DataFrame({
        "mean_speed": grouped["speed_kmh"].mean(),
        "max_speed": grouped["speed_kmh"].max(),
        "mean_throttle": grouped["throttle_pct"].mean(),
        "share_full_throttle": grouped["throttle_pct"].apply(lambda v: float(np.mean(v >= 99))),
        "share_braking": grouped["brake"].mean(),
    }).reset_index()
    return table


def build_laps():
    data, cleaning = clean(load_dataset())
    data = add_field_relative(data)
    laps = lap_vectors(data)
    laps = laps.merge(raw_lap_statistics(), on=LAP_KEYS, how="left")
    laps["team_season"] = team_season(laps)
    # field-relative lap time and raw statistics: minus the session median
    for column in ["lap_time_s"] + RAW_STATS:
        laps[f"{column}_rel"] = laps[column] - laps.groupby("session_key")[column].transform("median")
    return laps, cleaning


def feature_sets(laps):
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


# ---------------------------------------------------------------- task (a): teammates

def teammate_task(laps, rng):
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
        for _ in range(SHUFFLES):
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
        print(f"{label:28s} {row['drivers']:10s} {row['sessions']:2d} sessions {row['laps']:3d} laps | "
              f"lap time {row['lap time only | balanced_accuracy']:.2f}  raw {row['raw lap statistics | balanced_accuracy']:.2f}  "
              f"ours {row['our features | balanced_accuracy']:.2f}  +time {row['our features + lap time | balanced_accuracy']:.2f}  "
              f"vote {row['our features | weekend vote']:.2f}  shuffled {row['shuffled labels | balanced_accuracy']:.2f}",
              flush=True)
    return pd.DataFrame(rows)


def summarise_teammates(table, rng):
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


# ---------------------------------------------------------------- task (b): all drivers of a season

def season_task(laps):
    sets = feature_sets(laps)
    results, confusion = [], None
    for year, season in laps.groupby("year"):
        sessions_per_driver = season.groupby("driver")["session_key"].nunique()
        regulars = sessions_per_driver[sessions_per_driver >= MIN_SESSIONS_MULTICLASS].index
        season = season[season["driver"].isin(regulars)].reset_index(drop=True)
        row = {"year": int(year), "drivers": int(season["driver"].nunique()), "laps": len(season),
               "chance": 1.0 / season["driver"].nunique()}
        for name, columns in sets.items():
            if name == "our features (nearest centroid)":
                continue
            predictions, result = run(season, columns, name)
            row[f"{name} | balanced_accuracy"] = result["balanced_accuracy"]
            row[f"{name} | macro_f1"] = result["macro_f1"]
            if name == "our features" and year == laps["year"].max():
                confusion = pd.crosstab(season["driver"], pd.Series(predictions, name="predicted"),
                                        rownames=["driver"], colnames=["predicted"])
        results.append(row)
        print(f"{year}: {row['drivers']} drivers, {row['laps']} laps, chance {row['chance']:.3f} | "
              f"lap time {row['lap time only | balanced_accuracy']:.3f}  raw {row['raw lap statistics | balanced_accuracy']:.3f}  "
              f"ours {row['our features | balanced_accuracy']:.3f}  +time {row['our features + lap time | balanced_accuracy']:.3f}",
              flush=True)
    return pd.DataFrame(results), confusion


# ---------------------------------------------------------------- figures

def figure_teammates(table, summary):
    order = table.sort_values("our features | balanced_accuracy")
    fig, ax = plt.subplots(figsize=(10, 0.36 * len(order) + 1.8))
    y = np.arange(len(order))
    ax.axvline(0.5, color=TEXT_SECONDARY, linewidth=1, linestyle="--")
    for i, (_, r) in enumerate(order.iterrows()):
        ax.plot([r["lap time only | balanced_accuracy"], r["our features | balanced_accuracy"]], [i, i],
                color="#d8d7d2", linewidth=2, zorder=1)
    ax.plot(order["lap time only | balanced_accuracy"], y, "o", color=SERIES[1], label="lap time only")
    ax.plot(order["our features | balanced_accuracy"], y, "o", color=SERIES[0], label="our corner features")
    ax.set_yticks(y)
    ax.set_yticklabels([f"{r['team_season']} ({r['drivers']})" for _, r in order.iterrows()], fontsize=8)
    ax.set_xlim(0.2, 1.0)
    ax.set_xlabel("Balanced accuracy on held-out weekends (0.5 = chance)")
    s = summary
    ax.set_title(f"Teammates told apart on unseen weekends: ours {s['our features | balanced_accuracy']['mean']:.2f} "
                 f"vs lap time {s['lap time only | balanced_accuracy']['mean']:.2f} (mean of {len(order)} team-seasons)",
                 fontsize=10, pad=10)
    ax.legend(fontsize=9, loc="lower right")
    fig.savefig(OUT_DIR / "teammates.png", bbox_inches="tight")
    plt.close(fig)


def figure_ablation(summary):
    names = ["our features | balanced_accuracy"] + [f"without {g} | balanced_accuracy" for g in FEATURE_GROUPS] \
        + ["shuffled labels | balanced_accuracy", "lap time only | balanced_accuracy"]
    labels = ["all corner features"] + [f"without {g}" for g in FEATURE_GROUPS] + ["shuffled labels", "lap time only"]
    means = [summary[n]["mean"] for n in names]
    low = [summary[n]["mean"] - summary[n]["ci95_low"] for n in names]
    high = [summary[n]["ci95_high"] - summary[n]["mean"] for n in names]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    y = np.arange(len(names))
    ax.errorbar(means, y, xerr=[low, high], fmt="o", color=SERIES[0], capsize=3)
    ax.axvline(0.5, color=TEXT_SECONDARY, linewidth=1, linestyle="--")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Mean balanced accuracy over team-seasons, 95 % interval")
    ax.set_title("Ablation: which feature groups carry the teammate signature?", pad=10)
    fig.savefig(OUT_DIR / "ablation.png", bbox_inches="tight")
    plt.close(fig)


def figure_confusion(confusion, year):
    drivers = list(confusion.index)
    matrix = confusion.reindex(columns=drivers, fill_value=0).to_numpy(dtype=float)
    matrix = matrix / matrix.sum(axis=1, keepdims=True)
    fig, ax = plt.subplots(figsize=(9, 8))
    image = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=max(0.5, matrix.max()))
    ax.set_xticks(range(len(drivers)))
    ax.set_xticklabels(drivers, rotation=90, fontsize=8)
    ax.set_yticks(range(len(drivers)))
    ax.set_yticklabels(drivers, fontsize=8)
    ax.grid(False)
    ax.set_xlabel("Predicted driver")
    ax.set_ylabel("True driver")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04, label="share of the driver's laps")
    ax.set_title(f"{year}, all drivers, held-out weekends: who is mistaken for whom (rows sum to 1)", fontsize=10, pad=10)
    fig.savefig(OUT_DIR / f"confusion_{year}.png", bbox_inches="tight")
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    apply_style()
    rng = np.random.default_rng(SEED)
    laps, cleaning = build_laps()
    print(f"{len(laps)} laps, {laps['session_key'].nunique()} sessions, {laps['driver'].nunique()} drivers, "
          f"{len([c for c in laps.columns if '__' in c])} corner-feature columns\n")

    print("--- task (a): teammates, leave-one-session-out ---")
    teammates = teammate_task(laps, rng)
    teammates.to_csv(OUT_DIR / "teammates.csv", index=False, float_format="%.4f")
    teammate_summary = summarise_teammates(teammates, rng)
    print("\nmean balanced accuracy over team-seasons (95 % interval):")
    for name, value in teammate_summary.items():
        if "mean" in value:
            print(f"  {name:45s} {value['mean']:.3f} [{value['ci95_low']:.3f}, {value['ci95_high']:.3f}]")
        else:
            print(f"  {name:45s} mean difference {value['mean_difference']:+.3f}, ours better in "
                  f"{value['wins']} of {value['team_seasons']}, Wilcoxon p = {value['wilcoxon_p']:.4f}")

    print("\n--- task (b): all drivers of a season ---")
    seasons, confusion = season_task(laps)
    seasons.to_csv(OUT_DIR / "seasons.csv", index=False, float_format="%.4f")

    figure_teammates(teammates, teammate_summary)
    figure_ablation(teammate_summary)
    if confusion is not None:
        figure_confusion(confusion, int(laps["year"].max()))
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump({"laps": len(laps), "cleaning": cleaning, "teammates": teammate_summary,
                   "seasons": seasons.to_dict(orient="records")}, file, indent=1, default=float)
    print(f"\nSaved results to {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

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

from apextrace.dataset import add_field_relative, clean, load_dataset
from apextrace.identification import FEATURE_GROUPS, build_lap_table
from apextrace.protocol import feature_sets, run, summarise_teammates, teammate_task
from apextrace.plots import SERIES, TEXT_SECONDARY, apply_style

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW = REPO_ROOT / "results" / "09_dataset" / "raw_samples.parquet"
OUT_DIR = REPO_ROOT / "results" / "12_identification"
SEED = 2026
SHUFFLES = 5
MIN_SESSIONS_MULTICLASS = 5


# ---------------------------------------------------------------- inputs

def build_laps():
    """The per-lap table (identification.build_lap_table) from the clean dataset and the raw samples."""
    data, cleaning = clean(load_dataset())
    raw = pd.read_parquet(RAW, columns=["session_key", "driver", "lap", "speed_kmh", "throttle_pct", "brake"])
    return build_lap_table(add_field_relative(data), raw), cleaning


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
    teammates = teammate_task(laps, rng, shuffles=SHUFFLES)
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

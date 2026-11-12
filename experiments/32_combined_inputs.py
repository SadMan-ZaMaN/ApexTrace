"""Day 21, EXPLORATORY (E3 in docs/decisions.md, 2026-11-13): do corner features add anything on
top of simple whole-lap statistics? Not preregistered; rules fixed before running.

H3 found that the 30 corner features identify which teammate drove a lap better than lap time, but
not better than 5 whole-lap statistics (mean and top speed, mean throttle, share at full throttle,
share braking). Two very different stories fit that:
  a) the corner features hold the SAME information as the whole-lap statistics, in a more
     interpretable form (where a driver brakes, rather than how much of the lap they brake);
  b) they hold DIFFERENT information that just happens to be equally useful on its own.
A model given BOTH tells them apart: under (a) it does no better than the whole-lap statistics
alone; under (b) it does better. Signals analogy: two noisy sensors of the same quantity average
to little gain if their noise is shared, but to a real gain if it is independent.

Same machinery as H3 (protocol.run): the same team-season pairs, leave-one-weekend-out logistic
regression, balanced accuracy, no tuning. Three inputs: whole-lap statistics (5), corner features
(30), both (35). Development 2023-2024 first, then the saved 2025 data as a second look.

Check first: the script's runs of the two existing inputs must equal the committed H3 per-team
results (results/12_identification/teammates.csv, results/final/h3_teammates_2025.csv) to within
their 4-decimal rounding, or it stops.

Outputs results/32_combined_inputs/: summary.json, per_team.csv, combined.png.
Run from the repo root (~2 minutes; reads only results/):
    .venv\\Scripts\\python.exe experiments\\32_combined_inputs.py
"""

import importlib.util
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from apextrace.dataset import add_field_relative, clean, load_dataset
from apextrace.identification import RAW_STATS, build_lap_table
from apextrace.plots import GRID, SERIES, TEXT_SECONDARY, apply_style
from apextrace.protocol import run

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "results"
OUT_DIR = RESULTS / "32_combined_inputs"
MIN_WEEKENDS = 5
BOOTSTRAP_DRAWS = 5000
SEED = 2026
ROUNDING = 1e-4                 # the committed per-team files keep 4 decimals


def team_pairs(laps):
    """The H3 pairs (protocol.teammate_task): per team-season the two drivers with most laps, only
    on weekends where both drove, and only if that is at least 5 weekends. Yields (label, laps).
    Example: McLaren 2024 -> NOR vs PIA on the 22 weekends both drove."""
    for label, team_laps in laps.groupby("team_season"):
        top_two = team_laps["driver"].value_counts().index[:2].tolist()
        pair = team_laps[team_laps["driver"].isin(top_two)]
        both = pair.groupby("session_key")["driver"].nunique()
        pair = pair[pair["session_key"].isin(both[both == 2].index)].reset_index(drop=True)
        if pair["session_key"].nunique() >= MIN_WEEKENDS:
            yield label, pair


def inputs(laps):
    """The three inputs, by name: whole-lap statistics (5 columns), corner features (30), both (35)."""
    raw = [f"{c}_rel" for c in RAW_STATS]
    ours = [c for c in laps.columns if "__" in c]
    return {"whole-lap statistics": raw, "corner features": ours, "both": raw + ours}


def compare_inputs(laps):
    """Balanced accuracy of each input for every team-season (leave-one-weekend-out, protocol.run)."""
    rows = []
    for label, pair in team_pairs(laps):
        row = {"team_season": label, "weekends": int(pair["session_key"].nunique()), "laps": len(pair)}
        for name, columns in inputs(pair).items():
            row[name] = run(pair, columns, name)[1]["balanced_accuracy"]
        rows.append(row)
    return pd.DataFrame(rows)


def difference_summary(table, better, baseline, rng, added="corner features"):
    """Is `better` (a combined input) higher than `baseline`? Mean difference over team-seasons, a
    bootstrap 95 % interval (resampling whole team-seasons), the count of team-seasons where it was
    higher, and the words fixed in advance (docs/decisions.md, 2026-11-13), naming what was `added`.
    Example: differences +0.02, -0.01, +0.03 -> mean +0.013, higher in 2 of 3."""
    difference = (table[better] - table[baseline]).to_numpy()
    draws = []
    for _ in range(BOOTSTRAP_DRAWS):
        draws.append(np.mean(rng.choice(difference, size=len(difference))))
    low, high = float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))
    if low > 0:
        words = f"{added} add information beyond {baseline}"
    elif high < 0:
        words = f"adding {added} made it worse"
    else:
        words = f"no clear gain from adding {added} to {baseline}"
    return {"mean_difference": float(difference.mean()), "ci95": [low, high],
            "higher": int((difference > 0).sum()), "team_seasons": int(len(difference)),
            "wilcoxon_p_orientation_only": float(scipy_stats.wilcoxon(difference).pvalue), "words": words}


def check_against_h3(table, committed_path):
    """The two existing inputs must give the committed H3 per-team balanced accuracies."""
    committed = pd.read_csv(committed_path).set_index("team_season")
    largest = 0.0
    for _, row in table.iterrows():         # (itertuples would rename columns with spaces)
        for ours_name, h3_name in (("whole-lap statistics", "raw lap statistics"), ("corner features", "our features")):
            gap = abs(row[ours_name] - committed.loc[row["team_season"], f"{h3_name} | balanced_accuracy"])
            largest = max(largest, gap)
    assert len(table) == len(committed), (len(table), len(committed))
    assert largest <= ROUNDING, f"the runs differ from the committed H3 results by {largest}"
    return largest


def development_laps():
    rows, _ = clean(load_dataset())
    raw = pd.read_parquet(RESULTS / "09_dataset" / "raw_samples.parquet",
                          columns=["session_key", "driver", "lap", "speed_kmh", "throttle_pct", "brake"])
    return build_lap_table(add_field_relative(rows), raw)


def laps_2025():
    """The 2025 lap table exactly as the one-time 2025 run built it (14_final_2025.lap_tables), from the saved data."""
    spec = importlib.util.spec_from_file_location("final_2025", REPO_ROOT / "experiments" / "14_final_2025.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    dataset = pd.read_csv(RESULTS / "final" / "dataset_2025.csv.gz")
    raw = pd.read_parquet(RESULTS / "final" / "raw_samples_2025.parquet")
    laps, _, _ = script.lap_tables(dataset, raw)
    return laps


def figure(tables):
    """Per team-season: balanced accuracy of whole-lap statistics (x) against both together (y).
    Above the diagonal: adding the corner features helped that team-season."""
    fig, axes = plt.subplots(1, len(tables), figsize=(5.2 * len(tables), 5.0))
    for ax, (title, table) in zip(np.atleast_1d(axes), tables.items()):
        ax.scatter(table["whole-lap statistics"], table["both"], s=40, color=SERIES[0], zorder=3)
        low, high = 0.4, 1.0
        ax.plot([low, high], [low, high], color=TEXT_SECONDARY, linewidth=1, linestyle="--")
        ax.text(0.42, 0.97, "both better", fontsize=8, color=TEXT_SECONDARY, va="top")
        ax.text(0.98, 0.43, "whole-lap statistics better", fontsize=8, color=TEXT_SECONDARY, ha="right")
        ax.set_xlim(low, high)
        ax.set_ylim(low, high)
        ax.set_xlabel("whole-lap statistics alone (balanced accuracy)", fontsize=8)
        ax.set_ylabel("whole-lap statistics + corner features", fontsize=8)
        ax.set_title(title, fontsize=9, pad=8)
        ax.grid(color=GRID)
    fig.suptitle("EXPLORATORY: do corner features add anything on top of whole-lap statistics?", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "combined.png", bbox_inches="tight", dpi=150)
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    apply_style()
    rng = np.random.default_rng(SEED)
    datasets = {"development 2023-2024": (development_laps(), RESULTS / "12_identification" / "teammates.csv"),
                "2025 (second look)": (laps_2025(), RESULTS / "final" / "h3_teammates_2025.csv")}
    summary = {"note": "EXPLORATORY (docs/decisions.md 2026-11-13, E3); not preregistered", "data": {}}
    tables, per_team = {}, []
    for name, (laps, committed) in datasets.items():
        table = compare_inputs(laps)
        largest = check_against_h3(table, committed)
        tables[name] = table
        per_team.append(table.assign(data=name))
        means = {column: float(table[column].mean()) for column in inputs(laps)}
        summary["data"][name] = {
            "team_seasons": int(len(table)), "matches_committed_h3_within": largest, "mean_balanced_accuracy": means,
            "both_minus_whole_lap": difference_summary(table, "both", "whole-lap statistics", rng),
            "both_minus_corner": difference_summary(table, "both", "corner features", rng,
                                                    added="whole-lap statistics")}
        result = summary["data"][name]["both_minus_whole_lap"]
        print(f"{name}: whole-lap {means['whole-lap statistics']:.3f}, corner {means['corner features']:.3f}, "
              f"both {means['both']:.3f}; both - whole-lap {result['mean_difference']:+.3f} "
              f"[{result['ci95'][0]:+.3f}, {result['ci95'][1]:+.3f}], higher in {result['higher']} of "
              f"{result['team_seasons']} -> {result['words']}")
    pd.concat(per_team, ignore_index=True).to_csv(OUT_DIR / "per_team.csv", index=False, float_format="%.4f")
    figure(tables)
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)
    print(f"wrote {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

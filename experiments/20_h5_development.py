"""H5 development: the H5 comparison on two season pairs WITHOUT a rule change.

Development data only: 2023, 2024 and 2025 (2025's own test is frozen in results/final/
and is only read here, never written). Design: docs/h5_design.md.

For every driver with >= 5 dry weekends in both seasons of a pair: is the later season's
signature closer to their OWN earlier signature than to their earlier TEAMMATE's (the
same car that year)? Rules (signatures.own_vs_past_teammate): both earlier references on
the weekends the two teammates shared, z-scores from the spread of the OTHER drivers,
30 lap-vector features. Drivers who changed team are included and marked.

Pairs:
  2023 -> 2024   nobody among the regulars changed team
  2024 -> 2025   five preregistered changers (Part B) plus Colapinto
Each pair also runs once with full-season references (shared_weekends_only=False), to
show what the shared-weekend rule changes on real data.

Secondary versions (docs/h5_design.md section 4), same rules, fewer features:
  control points    brake onset, minimum speed, slowest point, throttle pickup (12 columns)
  energy-sensitive  entry speed, exit speed, full throttle, corner time (12 columns)
  no throttle       all but throttle pickup and full throttle (24 columns)
Without a rule change, they show how much of the signature each group carries; for 2026
the hypothesis is that the control points carry over better.

These are the baselines for H5: how often a signature "survives" when the rules don't
change. Power if 2026 had the same per-driver rate is computed too.

Outputs in results/20_h5_development/: summary.json, own_vs_teammate_<years>.csv,
h5_development.png. Run from the repo root (reads only local files, ~1 minute):
    .venv\\Scripts\\python.exe experiments\\20_h5_development.py
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import binomtest

from apextrace.dataset import add_field_relative, clean, load_dataset
from apextrace.identification import build_lap_table
from apextrace.plots import SERIES, TEXT_SECONDARY, apply_style
from apextrace.signatures import own_vs_past_teammate, sign_test_p, sign_test_power

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "results"
OUT_DIR = RESULTS / "20_h5_development"
RAW_COLUMNS = ["session_key", "driver", "lap", "speed_kmh", "throttle_pct", "brake"]
PAIRS = [(2023, 2024), (2024, 2025)]
MIN_WEEKENDS = 5
POWER_DRIVERS = [14, 16, 18, 20, 21]
CONTROL_POINTS = ["brake_onset_m", "min_speed_kmh", "apex_m", "throttle_pickup_m"]
ENERGY_SENSITIVE = ["entry_speed_kmh", "exit_speed_kmh", "full_throttle_m", "corner_time_s"]
THROTTLE = ["throttle_pickup_m", "full_throttle_m"]
# Only drivers below the line and team changers are labelled (the CSV has everyone);
# a label that would touch a neighbour goes to the left of its point
LABEL_LEFT = {"MAG"}
# Renamed teams are the same team (same car lineage); used only to mark team changers
SAME_TEAM_AS = {"AlphaTauri": "RB", "Racing Bulls": "RB", "Alfa Romeo": "Kick Sauber"}


def lineage(team):
    return SAME_TEAM_AS.get(team, team)


def load_laps():
    """Lap tables for 2023-2025, built exactly as for H3/H4 (clean -> field-relative -> lap vectors)."""
    development, _ = clean(load_dataset())
    raw_development = pd.read_parquet(RESULTS / "09_dataset" / "raw_samples.parquet", columns=RAW_COLUMNS)
    laps_development = build_lap_table(add_field_relative(development), raw_development)
    final, _ = clean(pd.read_csv(RESULTS / "final" / "dataset_2025.csv.gz"))
    raw_final = pd.read_parquet(RESULTS / "final" / "raw_samples_2025.parquet", columns=RAW_COLUMNS)
    laps_final = build_lap_table(add_field_relative(final), raw_final)
    return pd.concat([laps_development, laps_final], ignore_index=True)


def summarise(table):
    """Count, share, exact 95 % interval and one-sided sign-test p for the included drivers."""
    included = table[table["included"]]
    successes, trials = int(included["own_closer"].sum()), int(len(included))
    interval = binomtest(successes, trials).proportion_ci(confidence_level=0.95, method="exact")
    return {"drivers": trials, "own_closer": successes, "share": successes / trials,
            "ci95_low": float(interval.low), "ci95_high": float(interval.high),
            "sign_test_p": sign_test_p(successes, trials)}


def columns_of(features, names):
    """The lap-vector columns ("<feature>_rel__<corner type>") that belong to the named features."""
    columns = []
    for column in features:
        if column.split("_rel__")[0] in names:
            columns.append(column)
    return columns


def variants(features):
    """The secondary feature sets: name -> columns."""
    every_feature = sorted({column.split("_rel__")[0] for column in features})
    without_throttle = [name for name in every_feature if name not in THROTTLE]
    return {"control points": columns_of(features, CONTROL_POINTS),
            "energy-sensitive": columns_of(features, ENERGY_SENSITIVE),
            "no throttle": columns_of(features, without_throttle)}


def figure(tables):
    """Distance to own past (x) vs to the past teammate (y), one panel per season pair.
    Above the diagonal: the driver's own past is closer."""
    fig, axes = plt.subplots(1, len(tables), figsize=(11, 5.4), sharex=True, sharey=True)
    low, high = 0.2, 2.5
    for ax, (label, table) in zip(axes, tables.items()):
        included = table[table["included"]]
        groups = [(included[~included["changed_team"]], SERIES[0], "same team in both seasons"),
                  (included[included["changed_team"]], SERIES[1], "changed team")]
        for rows, color, group_label in groups:
            ax.scatter(rows["distance_own"], rows["distance_teammate"], s=46, color=color, zorder=3,
                       edgecolors="white", linewidths=1.0, label=group_label if len(rows) else None)
            for _, row in rows.iterrows():
                if row["own_closer"] and not row["changed_team"]:
                    continue
                left = row["driver"] in LABEL_LEFT
                ax.annotate(row["driver"], (row["distance_own"], row["distance_teammate"]),
                            xytext=(-5 if left else 4, 3), textcoords="offset points", fontsize=7.5,
                            color=TEXT_SECONDARY, ha="right" if left else "left")
        ax.plot([low, high], [low, high], color=TEXT_SECONDARY, linewidth=1, linestyle="--")
        ax.text(low + 0.05, high - 0.05, "own past closer", fontsize=8, color=TEXT_SECONDARY, va="top")
        ax.text(high - 0.05, low + 0.05, "past teammate closer", fontsize=8, color=TEXT_SECONDARY, ha="right")
        s = summarise(table)
        ax.set_title(f"{label}: {s['own_closer']} of {s['drivers']} own past closer", fontsize=9.5, pad=8)
        ax.set_xlim(low, high)
        ax.set_ylim(low, high)
        ax.set_xlabel("distance to own earlier signature")
    axes[0].set_ylabel("distance to earlier teammate's signature")
    axes[-1].legend(loc="lower right", bbox_to_anchor=(1.0, 0.1), fontsize=8, frameon=False)
    fig.suptitle("H5 development: without a rule change, does a signature stay closer to the driver's own past?\n"
                 "(labelled: drivers below the line, and team changers)", fontsize=10, y=1.04)
    fig.savefig(OUT_DIR / "h5_development.png", bbox_inches="tight")
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    apply_style()
    laps = load_laps()
    features = [c for c in laps.columns if "__" in c]
    print(f"{len(laps)} laps, {len(features)} lap-vector features")

    summary = {"features": len(features), "pairs": {}}
    tables = {}
    for reference_year, target_year in PAIRS:
        label = f"{reference_year} -> {target_year}"
        table = own_vs_past_teammate(laps, reference_year, target_year, features, MIN_WEEKENDS)
        table["changed_team"] = [lineage(a) != lineage(b) for a, b in zip(table["team_reference"], table["team_target"])]
        table.to_csv(OUT_DIR / f"own_vs_teammate_{reference_year}_{target_year}.csv", index=False, float_format="%.4f")
        tables[label] = table

        full_season = own_vs_past_teammate(laps, reference_year, target_year, features, MIN_WEEKENDS,
                                           shared_weekends_only=False)
        included = table[table["included"]]
        result = {"all": summarise(table),
                  "stayed": summarise(table[~table["changed_team"]]),
                  "changers": [str(d) for d in included.loc[included["changed_team"], "driver"]],
                  "changers_own_closer": int(included.loc[included["changed_team"], "own_closer"].sum()),
                  "excluded": table.loc[~table["included"], ["driver", "reason"]].to_dict("records"),
                  "full_season_references": summarise(full_season)}
        result["power_if_2026_had_this_rate"] = {
            str(n): round(sign_test_power(n, result["all"]["share"]), 3) for n in POWER_DRIVERS}
        result["variants"] = {}
        for name, columns in variants(features).items():
            variant = own_vs_past_teammate(laps, reference_year, target_year, columns, MIN_WEEKENDS)
            result["variants"][name] = {"columns": len(columns), **summarise(variant)}
        summary["pairs"][label] = result

        a = result["all"]
        print(f"\n{label}: own past closer for {a['own_closer']} of {a['drivers']} "
              f"({a['share']:.2f}, 95 % {a['ci95_low']:.2f}-{a['ci95_high']:.2f}), sign test p = {a['sign_test_p']:.4f}")
        print(f"  stayed in team: {result['stayed']['own_closer']} of {result['stayed']['drivers']}; "
              f"changers {result['changers']}: {result['changers_own_closer']} own closer")
        f = result["full_season_references"]
        print(f"  with full-season references instead: {f['own_closer']} of {f['drivers']}")
        if result["excluded"]:
            print(f"  excluded: {result['excluded']}")
        print("  power if 2026 had this rate:", result["power_if_2026_had_this_rate"])
        for name, v in result["variants"].items():
            print(f"  {name} ({v['columns']} columns): {v['own_closer']} of {v['drivers']} "
                  f"({v['share']:.2f}, 95 % {v['ci95_low']:.2f}-{v['ci95_high']:.2f}), p = {v['sign_test_p']:.4f}")
        print(included[["driver", "team_reference", "team_target", "teammate", "shared_weekends", "distance_own",
                        "distance_teammate", "own_closer"]].round(3).to_string(index=False))

    figure(tables)
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=1)
    print(f"\nwrote {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

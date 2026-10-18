"""Phase 7: figures of the final 2025 results + EXPLORATORY checks (not preregistered).

The preregistered decisions are in results/final/ (14_final_2025.py, run once)
and are NOT changed by anything here. This script only reads those results and
the frozen 2025 data, and adds three clearly labelled exploratory checks that
help to read the H4 result:

  1. Which drivers changed teams, derived from the data (2024 team vs the 2025
     team of most weekends). The preregistered list had 5 changers; the data
     also finds Colapinto (Williams 2024 -> Alpine 2025), who was missed.
     He is added here as a 6th changer, for completeness only.
  2. The H4 comparison run on drivers who did NOT change teams (control):
     own 2024 signature vs current 2025 teammate, the same weekends. H4 compares
     "own, one year apart" with "teammate, same season and same weekends"; this
     shows how often the driver's own signature wins when the car stays the same.
  3. The preregistered non-changer check without Colapinto (he changed teams).

Run from the repo root (reads results/final/, so FINAL_TEST is needed only
because the 2025 tables are rebuilt with the same functions):
    $env:FINAL_TEST = "1"; .venv\\Scripts\\python.exe experiments\\15_final_exploratory.py
"""

import importlib.util
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import fisher_exact

from apextrace.plots import SERIES, TEXT_SECONDARY, apply_style
from apextrace.signatures import sign_test_p

REPO_ROOT = Path(__file__).resolve().parent.parent
FINAL_DIR = REPO_ROOT / "results" / "final"
OUT_DIR = REPO_ROOT / "results" / "15_final_exploratory"
# A team renamed between 2024 and 2025 is the same team (same car lineage)
SAME_TEAM_AS = {"RB": "Racing Bulls"}

# Load the final script as a module, so the exploratory checks use exactly
# its functions (lap tables, h4). Its main() is not run.
spec = importlib.util.spec_from_file_location("final", REPO_ROOT / "experiments" / "14_final_2025.py")
final = importlib.util.module_from_spec(spec)
spec.loader.exec_module(final)


def lineage(team):
    return SAME_TEAM_AS.get(team, team)


def load_lap_tables():
    """The 2025 and 2024 lap tables, rebuilt from the saved final data with the final script's own function."""
    dataset = pd.read_csv(FINAL_DIR / "dataset_2025.csv.gz")
    raw = pd.read_parquet(FINAL_DIR / "raw_samples_2025.parquet",
                          columns=["session_key", "driver", "lap", "speed_kmh", "throttle_pct", "brake"])
    laps_2025, laps_2024, _ = final.lap_tables(dataset, raw)
    return laps_2025, laps_2024


def team_changes(laps_2025, laps_2024):
    """Every driver with >= 5 weekends in 2024: 2024 team, main 2025 team, changed or not.

    The main 2025 team is the one with the most weekends (Tsunoda: 2 weekends
    with Racing Bulls, 20 with Red Bull Racing -> Red Bull Racing).
    """
    weekends_2024 = laps_2024.groupby("driver")["session_key"].nunique()
    rows = []
    for driver in sorted(set(laps_2025["driver"])):
        if weekends_2024.get(driver, 0) < final.MIN_WEEKENDS:
            continue
        team_2024 = laps_2024.loc[laps_2024["driver"] == driver, "team"].mode().iloc[0]
        team_2025, weekends_2025 = final.most_weekends_team(laps_2025, driver)
        rows.append({"driver": driver, "team_2024": team_2024, "team_2025": team_2025,
                     "weekends_2025": weekends_2025, "changed": lineage(team_2024) != team_2025,
                     "preregistered_changer": driver in final.CHANGERS})
    return pd.DataFrame(rows)


def h4_for(drivers, laps_2025, laps_2024):
    """The preregistered H4 comparison (final.h4), run for another list of drivers."""
    preregistered = final.CHANGERS
    final.CHANGERS = list(drivers)
    try:
        table, summary = final.h4(laps_2025, laps_2024)
    finally:
        final.CHANGERS = preregistered   # never leave the module changed
    return table, summary


def figure_h3(teams):
    """Per team: balanced accuracy of lap time only, raw lap statistics and our corner features."""
    sets = [("lap time only | balanced_accuracy", "lap time only"),
            ("raw lap statistics | balanced_accuracy", "raw lap statistics"),
            ("our features | balanced_accuracy", "our corner features")]
    teams = teams.sort_values("our features | balanced_accuracy")
    fig, ax = plt.subplots(figsize=(8, 6))
    height = 0.26
    for k, (column, label) in enumerate(sets):
        positions = [i + (k - 1) * height for i in range(len(teams))]
        ax.barh(positions, teams[column], height=height, color=SERIES[k], label=label)
    ax.axvline(0.5, color=TEXT_SECONDARY, linewidth=1, linestyle="--")
    ax.text(0.505, len(teams) - 0.45, "chance", color=TEXT_SECONDARY, fontsize=8)
    ax.set_yticks(range(len(teams)))
    ax.set_yticklabels([f"{t.replace(' 2025', '')} ({d})" for t, d in zip(teams["team_season"], teams["drivers"])],
                       fontsize=8)
    ax.set_xlim(0.4, 1.0)
    ax.set_xlabel("balanced accuracy, leave-one-session-out (which teammate drove this lap?)")
    ax.set_title("2025 (frozen test): teammate identification per team", fontsize=10, pad=10)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1], loc="lower right", fontsize=8, frameon=False)  # same order as the bars
    fig.savefig(OUT_DIR / "final_h3_teams.png", bbox_inches="tight")
    plt.close(fig)


def figure_h4(changers, control):
    """Distance to own 2024 signature (x) vs to the 2025 teammate (y). Above the line: own signature closer."""
    fig, ax = plt.subplots(figsize=(7, 6.5))
    # labels that would overlap a neighbour go to the left of their point
    left_labels = {"PIA", "HUL"}
    groups = [(control, SERIES[0], "did not change team (exploratory control)"),
              (changers, SERIES[1], "changed team (preregistered H4)")]
    for table, color, label in groups:
        for _, row in table.iterrows():
            exploratory_extra = not row["preregistered_changer"] and row["changed"]
            ax.scatter(row["distance_own_2024"], row["distance_new_teammate_2025"], s=46, zorder=3,
                       color="none" if exploratory_extra else color, edgecolors=color, linewidths=1.5)
            left = row["driver"] in left_labels
            ax.annotate(row["driver"], (row["distance_own_2024"], row["distance_new_teammate_2025"]),
                        xytext=(-5 if left else 4, 3), textcoords="offset points", fontsize=8,
                        color=TEXT_SECONDARY, ha="right" if left else "left")
        # one legend entry per group, always drawn as a filled marker
        ax.scatter([], [], s=46, color=color, label=label)
    low, high = 0.3, 1.7
    ax.plot([low, high], [low, high], color=TEXT_SECONDARY, linewidth=1, linestyle="--")
    ax.text(0.35, 1.6, "own 2024 signature closer\n(signature follows the driver)", fontsize=8, color=TEXT_SECONDARY,
            va="top")
    ax.text(1.65, 0.38, "2025 teammate closer\n(signature follows the car)", fontsize=8, color=TEXT_SECONDARY,
            ha="right")
    ax.set_xlim(low, high)
    ax.set_ylim(low, high)
    ax.set_xlabel("distance: 2025 signature to own 2024 signature")
    ax.set_ylabel("distance: 2025 signature to 2025 teammate's (same weekends)")
    ax.set_title("2025 (frozen test): does the signature follow the driver? (hollow: COL, not preregistered)",
                 fontsize=9, pad=10)
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 0.2), fontsize=8, frameon=False)
    fig.savefig(OUT_DIR / "final_h4_distances.png", bbox_inches="tight")
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    apply_style()
    laps_2025, laps_2024 = load_lap_tables()

    # 1. who changed teams, from the data
    changes = team_changes(laps_2025, laps_2024)
    changes.to_csv(OUT_DIR / "team_changes.csv", index=False)
    print(changes.to_string(index=False))
    changed = changes[changes["changed"]]
    missed = sorted(set(changed["driver"]) - set(final.CHANGERS))
    print("changers found in the data but not preregistered:", missed)

    all_changers, all_changers_summary = h4_for(changed["driver"], laps_2025, laps_2024)
    all_changers = all_changers.merge(changes[["driver", "changed", "preregistered_changer"]], on="driver")
    all_changers.to_csv(OUT_DIR / "h4_all_changers.csv", index=False, float_format="%.4f")

    # 2. the same comparison for drivers who stayed (control)
    stayed = changes[~changes["changed"]]["driver"]
    control, control_summary = h4_for(stayed, laps_2025, laps_2024)
    control = control.merge(changes[["driver", "changed", "preregistered_changer"]], on="driver")
    control.to_csv(OUT_DIR / "h4_shape_control_non_changers.csv", index=False, float_format="%.4f")
    print(control[["driver", "team_2025", "teammate_2025", "distance_own_2024", "distance_new_teammate_2025",
                   "own_closer"]].to_string(index=False))

    # 3. the preregistered non-changer check without the changers it wrongly contained
    check = pd.read_csv(FINAL_DIR / "h4_non_changers.csv")
    check = check[~check["driver"].isin(changed["driver"])]
    check_wins = int(check["own_closer"].sum())

    # Is "own signature closer" rarer for the preregistered changers than for the
    # drivers who stayed? Fisher's exact test on the 2 x 2 table
    #   rows: changers / stayers,  columns: own closer / teammate closer.
    # It asks: if both groups had the same rate, how likely is a split at least
    # this uneven? (With 5 and 10 drivers, only a very large gap could be detected.)
    preregistered = pd.read_csv(FINAL_DIR / "h4_changers.csv")
    preregistered = preregistered[preregistered["included"]]
    stayers = control[control["included"]]
    changer_wins = int(preregistered["own_closer"].sum())
    stayer_wins = int(stayers["own_closer"].sum())
    table_2x2 = [[changer_wins, len(preregistered) - changer_wins], [stayer_wins, len(stayers) - stayer_wins]]
    fisher_p = float(fisher_exact(table_2x2).pvalue)

    summary = {
        "note": "EXPLORATORY, not preregistered. The preregistered decisions are in results/final/summary.json.",
        "changers_in_data": sorted(changed["driver"]),
        "changers_missed_by_preregistration": missed,
        "h4_with_all_changers": all_changers_summary,
        "h4_shape_control_non_changers": control_summary,
        "non_changer_check_without_changers": {"drivers": int(len(check)), "own_closer": check_wins,
                                               "sign_test_p": sign_test_p(check_wins, len(check))},
        "changers_vs_stayers": {"changers_own_closer": f"{changer_wins} of {len(preregistered)}",
                                "stayers_own_closer": f"{stayer_wins} of {len(stayers)}",
                                "fisher_exact_two_sided_p": fisher_p},
    }
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, default=float)
    print(json.dumps(summary, indent=2, default=float))

    figure_h3(pd.read_csv(FINAL_DIR / "h3_teammates_2025.csv"))
    figure_h4(all_changers[all_changers["included"]], control[control["included"]])
    print(f"Saved to {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

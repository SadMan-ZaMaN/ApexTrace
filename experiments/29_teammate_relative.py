"""Day 16, EXPLORATORY (E2 in docs/decisions.md, 2026-11-09): does the DIFFERENCE between two
teammates carry over to the next season, with the car removed? Written after the frozen 2026
test; nothing here can change its verdict (H5 not supported).

Idea (signals): on the same weekend, two teammates share the car, its set-up direction, the
track and the weather. Their difference cancels all of that, like a differential amplifier
that rejects the common-mode signal. If part of the remaining difference belongs to the
drivers, it should point the same way the next season, even in a new car: the same driver
still brakes later, carries more minimum speed, and so on.

For every pair of drivers who were teammates (same team lineage) on >= 5 shared weekends in
BOTH of two consecutive seasons (signatures.pair_persistence):
  - per season: the mean over shared weekends of (A's weekend mean - B's), on equal laps per
    weekend, on the 30 lap-vector columns, each divided by the SD of weekend differences of
    all teammate pairs of the earlier season;
  - the cosine between the two seasons' vectors (+1 same direction, 0 none, -1 reversed);
  - as a rough reference, the split-half cosine inside the earlier season (odd vs even weekends).
Seasons: 2023 -> 2024 and 2024 -> 2025 (same rules), 2025 -> 2026 (new rules).
Reported: per pair, the count with cosine > 0, the median, and a one-sided sign test p as
orientation only (not a decision; no correction for the three looks).

Outputs results/29_teammate_relative/: summary.json, pairs.csv, teammate_relative.png.
Run from the repo root (reads only results/, ~1-2 minutes):
    .venv\\Scripts\\python.exe experiments\\29_teammate_relative.py
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

from apextrace import h5_protocol, teams
from apextrace.dataset import add_field_relative, clean, load_dataset
from apextrace.identification import build_lap_table
from apextrace.plots import GRID, SERIES, TEXT_SECONDARY, apply_style
from apextrace.signatures import pair_persistence, sign_test_p

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "results"
OUT_DIR = RESULTS / "29_teammate_relative"
RAW_COLUMNS = ["session_key", "driver", "lap", "speed_kmh", "throttle_pct", "brake"]
COMPARISONS = [(2023, 2024, "same rules"), (2024, 2025, "same rules"), (2025, 2026, "new rules")]
MIN_WEEKENDS = 5


def load_laps():
    """Lap tables 2023-2026, built exactly as for H3/H4/H5 (clean -> field-relative -> lap vectors)."""
    development, _ = clean(load_dataset())
    raw = pd.read_parquet(RESULTS / "09_dataset" / "raw_samples.parquet", columns=RAW_COLUMNS)
    tables = [build_lap_table(add_field_relative(development), raw)]
    for year, folder in ((2025, "final"), (2026, "final_2026")):
        dataset = pd.read_csv(RESULTS / folder / f"dataset_{year}.csv.gz")
        raw = pd.read_parquet(RESULTS / folder / f"raw_samples_{year}.parquet", columns=RAW_COLUMNS)
        laps, _ = h5_protocol.lap_table_from(dataset, raw)
        tables.append(laps)
    return pd.concat(tables, ignore_index=True)


def figure(pairs):
    """One column per pair of seasons: each dot is one pair of teammates (its cosine)."""
    fig, ax = plt.subplots(figsize=(9, 5.8))
    for k, (earlier, later, rules) in enumerate(COMPARISONS):
        rows = pairs[pairs["comparison"] == f"{earlier} -> {later}"].sort_values("cosine")
        for i, row in enumerate(rows.itertuples()):
            # spread the dots sideways a little so labels don't sit on each other
            x = k + (i % 2) * 0.18 - 0.09
            ax.scatter([x], [row.cosine], s=46, color=SERIES[0] if rules == "same rules" else SERIES[1], zorder=3)
            ax.annotate(row.pair, (x, row.cosine), xytext=(6 if i % 2 else -6, -3), textcoords="offset points",
                        fontsize=7, color=TEXT_SECONDARY, ha="left" if i % 2 else "right")
        # the median of the column, drawn in ink (not a series colour)
        median = rows["cosine"].median()
        ax.plot([k - 0.3, k + 0.3], [median, median], color=TEXT_SECONDARY, linewidth=2, zorder=2)
        ax.annotate(f"median {median:.2f}", (k + 0.3, median), xytext=(3, 0), textcoords="offset points",
                    fontsize=7, color=TEXT_SECONDARY, va="center")
    ax.axhline(0, color=TEXT_SECONDARY, linewidth=1, linestyle="--")
    ax.text(0.5, 0.02, "no common direction", fontsize=8, color=TEXT_SECONDARY, ha="center")
    handles = [Line2D([], [], marker="o", linestyle="", markersize=7, color=SERIES[0], label="same rules"),
               Line2D([], [], marker="o", linestyle="", markersize=7, color=SERIES[1], label="new rules (2026)")]
    ax.legend(handles=handles, loc="lower left", fontsize=8, frameon=False)
    ax.set_xticks(range(len(COMPARISONS)))
    labels = []
    for earlier, later, rules in COMPARISONS:
        n = int((pairs["comparison"] == f"{earlier} -> {later}").sum())
        labels.append(f"{earlier} → {later}\n({rules}, {n} pairs)")
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_xlim(-0.6, len(COMPARISONS) - 0.4)
    ax.set_ylim(-1.0, 1.0)
    ax.set_ylabel("cosine between the two seasons' teammate differences", fontsize=8)
    ax.grid(axis="x", visible=False)
    ax.grid(axis="y", color=GRID)
    ax.set_title("EXPLORATORY: does the difference between two teammates point the same way next season?\n"
                 "(the car cancels in the difference; +1 = same direction, 0 = none)", fontsize=9, pad=10)
    fig.savefig(OUT_DIR / "teammate_relative.png", bbox_inches="tight", dpi=150)
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    apply_style()
    laps = load_laps()
    columns = h5_protocol.lap_vector_columns(laps)
    print(f"{len(laps)} laps, {len(columns)} lap-vector columns, years {sorted(laps['year'].unique())}")

    tables, summary = [], {"note": "EXPLORATORY (docs/decisions.md 2026-11-09, E2); not a decision",
                           "columns": len(columns), "min_weekends": MIN_WEEKENDS, "comparisons": {}}
    for earlier, later, rules in COMPARISONS:
        table = pair_persistence(laps, earlier, later, columns, teams.lineage, MIN_WEEKENDS)
        name = f"{earlier} -> {later}"
        table.insert(0, "comparison", name)
        tables.append(table)
        positive = int((table["cosine"] > 0).sum())
        summary["comparisons"][name] = {
            "rules": rules, "pairs": int(len(table)), "cosine_positive": positive,
            "median_cosine": round(float(table["cosine"].median()), 3),
            "sign_test_p_orientation_only": round(sign_test_p(positive, len(table)), 4),
            "median_split_half_earlier": round(float(table["split_half_earlier"].median()), 3),
            "pairs_list": table["pair"].tolist()}
        print(f"\n{name} ({rules}): {positive} of {len(table)} pairs with cosine > 0, "
              f"median {table['cosine'].median():.2f}; split-half median {table['split_half_earlier'].median():.2f}")
        print(table[["pair", "team_earlier", "team_later", "weekends_earlier", "weekends_later", "cosine",
                     "split_half_earlier"]].to_string(index=False, float_format="%.2f"))
    pairs = pd.concat(tables, ignore_index=True)
    pairs.to_csv(OUT_DIR / "pairs.csv", index=False, float_format="%.4f")
    figure(pairs)
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, ensure_ascii=False)
    print(f"\nwrote {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

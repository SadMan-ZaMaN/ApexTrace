"""Phase 6: exploratory data analysis (EDA) of the 2023-2024 multi-season dataset.

Classic EDA, before any modelling:
  1. overview: sessions, drivers, laps, corners, how many rows are usable and why not;
  2. missing values per feature;
  3. summary statistics per feature and corner type;
  4. sanity checks against physical limits (outliers listed, not silently removed),
     then the cleaning rules (apextrace.dataset.clean, decided here, before any
     modelling): dry laps only, broken rows dropped, impossible values -> missing;
  5. field-relative features: each value minus the median of all drivers at the
     same corner of the same session. A raw braking point (-140 m) mostly says
     which TRACK it is; the field-relative one says how this lap compares with
     everyone else at the same place on the same day;
  6. correlations between field-relative features;
  7. a track map from the raw samples, coloured by speed, with the detected corners.

Inputs: results/09_dataset/ (dataset.csv.gz, corners.csv, raw_samples.parquet).
Outputs in results/10_eda/: eda_report.md (tables), outliers.csv, figures, summary.json.

Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\10_eda.py
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from apextrace.dataset import add_field_relative, clean
from apextrace.features import FEATURES
from apextrace.plots import SERIES, SURFACE, TEXT_PRIMARY, TEXT_SECONDARY, apply_style

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "results" / "09_dataset"
OUT_DIR = REPO_ROOT / "results" / "10_eda"

CORNER_TYPES = ["slow", "medium", "fast"]
TYPE_COLORS = {"slow": SERIES[0], "medium": SERIES[1], "fast": SERIES[2]}
CONTINUOUS = [f for f in FEATURES if f != "min_gear"]
SHOWN = ["brake_onset_m", "min_speed_kmh", "throttle_pickup_m", "mean_decel_ms2", "exit_speed_kmh", "corner_time_s"]
LABELS = {"brake_onset_m": "Brake onset (m from apex ref.)", "min_speed_kmh": "Minimum speed (km/h)",
          "throttle_pickup_m": "Throttle 10 % (m)", "mean_decel_ms2": "Mean deceleration (m/s²)",
          "exit_speed_kmh": "Exit speed (km/h)", "corner_time_s": "Corner time (s)",
          "apex_m": "Apex (m)", "full_throttle_m": "Full throttle (m)", "entry_speed_kmh": "Entry speed (km/h)",
          "braking_distance_m": "Braking distance (m)"}

# Physical limits for sanity checks: values outside are listed in outliers.csv
LIMITS = {
    "brake_onset_m": (-400.0, 0.0),        # braking starts before the corner's apex reference
    "min_speed_kmh": (40.0, 330.0),
    "mean_decel_ms2": (3.0, 60.0),         # ~0.3 g to ~6 g
    "corner_time_s": (2.0, 20.0),
    "apex_m": (-80.0, 80.0),               # searched within +-80 m by construction
    "throttle_pickup_m": (-200.0, 200.0),
}


def overview(data):
    usable = data[data["usable"]]
    laps = usable[["session_key", "driver", "lap"]].drop_duplicates()
    per_driver_session = laps.groupby(["session_key", "driver"]).size()
    return {
        "rows": int(len(data)), "usable_rows": int(len(usable)),
        "usable_share": float(len(usable) / len(data)),
        "sessions_with_usable_rows": int(usable["session_key"].nunique()),
        "drivers": int(usable["driver"].nunique()), "teams": int(usable["team"].nunique()),
        "laps": int(len(laps)),
        "laps_per_driver_session_median": float(per_driver_session.median()),
        "laps_per_driver_session_min": int(per_driver_session.min()),
        "laps_per_driver_session_max": int(per_driver_session.max()),
        "usable_rows_by_corner_type": {t: int((usable["corner_type"] == t).sum()) for t in CORNER_TYPES},
        "exclusions": data.loc[~data["usable"], "reason"].value_counts().to_dict(),
    }


def outlier_table(usable):
    rows = []
    for feature, (low, high) in LIMITS.items():
        bad = usable[(usable[feature] < low) | (usable[feature] > high)]
        for _, r in bad.iterrows():
            rows.append({"feature": feature, "value": r[feature], "limit_low": low, "limit_high": high,
                         "year": r["year"], "location": r["location"], "driver": r["driver"], "lap": r["lap"],
                         "corner": r["corner"], "corner_type": r["corner_type"]})
    return pd.DataFrame(rows)


def figure_distributions(usable):
    fig, axes = plt.subplots(2, 3, figsize=(14, 7.5))
    for ax, feature in zip(axes.flat, SHOWN):
        for corner_type in CORNER_TYPES:
            values = usable.loc[usable["corner_type"] == corner_type, f"{feature}_rel"].dropna()
            low, high = np.percentile(usable[f"{feature}_rel"].dropna(), [1, 99])
            shown = values[(values >= low) & (values <= high)]   # drop the extreme 2 %, don't pile them up
            ax.hist(shown, bins=50, histtype="step", linewidth=1.6,
                    color=TYPE_COLORS[corner_type], label=f"{corner_type} ({len(values)})")
        ax.set_title(LABELS[feature], fontsize=10)
        ax.set_xlabel("difference from the field median at the same corner")
        ax.set_yticks([])
    axes[0, 0].legend(fontsize=8, title="corner type (rows)", title_fontsize=8)
    fig.suptitle("Field-relative features, 2023–2024 dry qualifying, cleaned (1st–99th percentile shown)",
                 x=0.0, ha="left", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "distributions_field_relative.png", bbox_inches="tight")
    plt.close(fig)


def figure_correlations(usable):
    names = [f"{f}_rel" for f in CONTINUOUS]
    correlation = usable[names].corr(method="spearman")
    colormap = LinearSegmentedColormap.from_list("diverging", [SERIES[0], "#e9e8e4", SERIES[1]])
    fig, ax = plt.subplots(figsize=(8.5, 7))
    image = ax.imshow(correlation.to_numpy(), cmap=colormap, vmin=-1, vmax=1)
    ticks = [LABELS.get(f, f) for f in CONTINUOUS]
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(ticks, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(ticks, fontsize=8)
    ax.grid(False)
    for i in range(len(names)):
        for j in range(len(names)):
            value = correlation.iloc[i, j]
            ax.text(j, i, f"{value:+.2f}", ha="center", va="center", fontsize=7,
                    color=TEXT_PRIMARY if abs(value) < 0.6 else SURFACE)
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04, label="Spearman correlation")
    ax.set_title("How field-relative features move together (all corners)", pad=12)
    fig.savefig(OUT_DIR / "correlations.png", bbox_inches="tight")
    plt.close(fig)
    return correlation


def figure_track_map(raw, corners):
    """The fastest lap of the last session (by date), coloured by speed, corners marked."""
    last_year = raw["year"].max()
    last_round = raw.loc[raw["year"] == last_year, "round"].max()
    last = raw[(raw["year"] == last_year) & (raw["round"] == last_round)]
    fastest = last.loc[last["lap_time_s"].idxmin()]
    lap = last[(last["driver"] == fastest["driver"]) & (last["lap"] == fastest["lap"])]
    session_corners = corners[corners["session_key"] == fastest["session_key"]]
    colormap = LinearSegmentedColormap.from_list("speed", ["#d6e4f5", SERIES[0], "#123e73"])
    fig, ax = plt.subplots(figsize=(8, 7))
    points = ax.scatter(lap["x_m"], lap["y_m"], c=lap["speed_kmh"], cmap=colormap, s=10)
    for _, corner in session_corners.iterrows():
        k = int(np.argmin(np.abs(lap["s_m"].to_numpy() - corner["s_m"])))
        ax.annotate(f"{corner['corner']} · {corner['min_speed_kmh']:.0f}", (lap["x_m"].iloc[k], lap["y_m"].iloc[k]),
                    xytext=(6, 6), textcoords="offset points", fontsize=8, color=TEXT_SECONDARY)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.colorbar(points, ax=ax, fraction=0.035, pad=0.02, label="Speed (km/h)")
    ax.set_title(f"{fastest['location']} {fastest['year']}: {fastest['driver']} lap {fastest['lap']} "
                 f"({fastest['lap_time_s']:.3f} s); detected corners · min speed", fontsize=10, pad=10)
    fig.savefig(OUT_DIR / "track_map.png", bbox_inches="tight")
    plt.close(fig)


def write_report(over, cleaning, missing, stats, outliers, correlation):
    lines = ["# EDA of the 2023–2024 qualifying dataset (generated by experiments/10_eda.py)", "",
             "## Overview", "", "| | |", "|---|---|"]
    for key, value in over.items():
        lines.append(f"| {key} | {value} |")
    lines += ["", "## Cleaning (apextrace.dataset.clean)", "", "| Step | Rows |", "|---|---|"]
    for key, value in cleaning.items():
        lines.append(f"| {key} | {value} |")
    lines += ["", "## Missing values among clean rows (share)", "", "| Feature | Missing |", "|---|---|"]
    for feature, share in missing.items():
        lines.append(f"| {feature} | {share:.3f} |")
    lines += ["", "## Summary statistics (raw values) by corner type", "",
              "| Feature | Type | n | median | 25 % | 75 % | min | max |", "|---|---|---|---|---|---|---|---|"]
    for _, r in stats.iterrows():
        lines.append(f"| {r['feature']} | {r['corner_type']} | {r['n']} | {r['median']:.2f} | {r['q25']:.2f} | "
                     f"{r['q75']:.2f} | {r['min']:.2f} | {r['max']:.2f} |")
    lines += ["", f"## Sanity checks BEFORE cleaning: {len(outliers)} values outside physical limits "
              f"(see outliers.csv)", ""]
    if len(outliers):
        for feature, count in outliers["feature"].value_counts().items():
            lines.append(f"- {feature}: {count}")
    lines += ["", "## Strongest correlations between field-relative features (|Spearman| ≥ 0.4)", ""]
    names = list(correlation.columns)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            value = correlation.iloc[i, j]
            if abs(value) >= 0.4:
                lines.append(f"- {names[i]} ↔ {names[j]}: {value:+.2f}")
    (OUT_DIR / "eda_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    apply_style()
    data = pd.read_csv(DATA_DIR / "dataset.csv.gz")
    corners = pd.read_csv(DATA_DIR / "corners.csv")
    raw = pd.read_parquet(DATA_DIR / "raw_samples.parquet")

    over = overview(data)
    outliers = outlier_table(data[data["usable"]])   # evidence, on the uncleaned rows
    outliers.to_csv(OUT_DIR / "outliers.csv", index=False)
    cleaned, cleaning = clean(data)
    usable = add_field_relative(cleaned)
    missing = usable[CONTINUOUS].isna().mean().round(4).to_dict()

    stats_rows = []
    for feature in CONTINUOUS:
        for corner_type in CORNER_TYPES:
            values = usable.loc[usable["corner_type"] == corner_type, feature].dropna()
            if len(values) == 0:
                continue
            stats_rows.append({"feature": feature, "corner_type": corner_type, "n": len(values),
                               "median": values.median(), "q25": values.quantile(0.25), "q75": values.quantile(0.75),
                               "min": values.min(), "max": values.max()})
    stats = pd.DataFrame(stats_rows)
    stats.to_csv(OUT_DIR / "summary_statistics.csv", index=False, float_format="%.3f")

    figure_distributions(usable)
    correlation = figure_correlations(usable)
    figure_track_map(raw, corners)
    write_report(over, cleaning, missing, stats, outliers, correlation)

    print("--- overview ---")
    for key, value in over.items():
        print(f"{key:34s} {value}")
    print("\n--- cleaning ---")
    print(cleaning)
    print("\n--- missing values (clean rows) ---")
    print({k: v for k, v in missing.items() if v > 0})
    print(f"\n--- sanity checks before cleaning: {len(outliers)} values outside physical limits ---")
    print(outliers["feature"].value_counts().to_dict() if len(outliers) else {})
    print(f"\nraw samples: {len(raw)} rows, {raw['session_key'].nunique()} sessions")
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump({"overview": over, "cleaning": cleaning, "missing": missing, "outliers": int(len(outliers)),
                   "outliers_by_feature": outliers["feature"].value_counts().to_dict() if len(outliers) else {},
                   "raw_sample_rows": int(len(raw))}, file, indent=2, default=int)
    print(f"Saved results to {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

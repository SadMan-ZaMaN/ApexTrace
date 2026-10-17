"""Phase 6, H1 with all drivers: how repeatable and distinctive is each corner feature?

Data: the clean 2023-2024 dry qualifying rows (apextrace.dataset.clean), with
field-relative features (value - median of all drivers at the same corner of
the same session).

Two ICCs (intraclass correlation = the share of variation that is BETWEEN
groups rather than within them), per feature and corner type:
  lap level      groups = (session, corner, driver): at the same corner on the
                 same day, do a driver's laps resemble each other more than
                 they resemble other drivers' laps?
  weekend level  each driver's mean per session; groups = (driver, season):
                 does a driver's offset from the field PERSIST from one race
                 weekend to the next? This is the "signature" question.
Both include the car: drivers of different teams drive different cars. The
teammate analysis (12_identification.py, task a) and Phase 7 deal with that.

Uncertainty: 95 % bootstrap intervals (1,000 resamples): lap level over whole
sessions; weekend level over driver-seasons (see the functions for why).

Also: within-driver lap-to-lap spread compared with the per-lap measurement
error from the Phase 2 Monte Carlo (slow -> heavy_braking type, medium ->
medium, fast -> fast; distances include the 1.15 m alignment noise).

Outputs in results/11_repeatability/: icc.csv, icc.png, summary.json.
Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\11_repeatability.py
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from apextrace.dataset import add_field_relative, clean, load_dataset
from apextrace.identification import ALL_FEATURES, CORNER_TYPES
from apextrace.plots import SERIES, TEXT_SECONDARY, apply_style
from apextrace.stats import icc_from_group_stats

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "results" / "11_repeatability"
ERROR_TABLE = REPO_ROOT / "results" / "03_synthetic_errors" / "error_table.csv"
ALIGNMENT = REPO_ROOT / "results" / "04_alignment" / "summary.json"
BOOTSTRAP = 1000
SEED = 2026
MC_TYPE = {"slow": "heavy_braking", "medium": "medium", "fast": "fast"}
MC_ROWS = {
    "brake_onset_m": "speed breakpoint inside off-on interval", "min_speed_kmh": "parabola 3 points",
    "apex_m": "parabola 3 points", "throttle_pickup_m": "interpolated crossing",
    "full_throttle_m": "interpolated crossing", "entry_speed_kmh": "linear interpolation",
    "exit_speed_kmh": "linear interpolation",
}
DISTANCE = {"brake_onset_m", "apex_m", "throttle_pickup_m", "full_throttle_m"}
NICE_LABELS = {"brake_onset_m": "brake onset (m)", "braking_distance_m": "braking distance (m)",
               "mean_decel_ms2": "mean deceleration (m/s²)", "min_speed_kmh": "minimum speed (km/h)",
               "apex_m": "apex position (m)", "throttle_pickup_m": "throttle 10 % (m)",
               "full_throttle_m": "full throttle (m)", "entry_speed_kmh": "entry speed (km/h)",
               "exit_speed_kmh": "exit speed (km/h)", "corner_time_s": "corner time (s)"}


def measurement_errors():
    table = pd.read_csv(ERROR_TABLE)
    alignment = json.loads(ALIGNMENT.read_text(encoding="utf-8"))["fusion_offset_noise_m"]
    errors = {}
    for corner_type, mc_type in MC_TYPE.items():
        for feature, estimator in MC_ROWS.items():
            row = table[(table["corner_type"] == mc_type) & (table["feature"] == feature)
                        & (table["estimator"] == estimator) & (table["scenario"] == "real")].iloc[0]
            std = float(row["std"])
            if feature in DISTANCE:
                std = float(np.sqrt(std ** 2 + alignment ** 2))
            errors[(corner_type, feature)] = std
    return errors


def group_summary(values, keys):
    """Per group: size, mean, within-group sum of squares (what the ICC needs)."""
    grouped = values.groupby(keys)
    sizes = grouped.size()
    return pd.DataFrame({"n": sizes, "mean": grouped.mean(), "ss": grouped.var(ddof=0) * sizes}).reset_index()


def lap_level(rows, column, rng):
    """ICC with groups (session, corner, driver), and a bootstrap over SESSIONS.

    Laps of one session share conditions, so whole sessions are resampled. A
    session drawn twice simply adds its groups twice (they are distinct groups
    of the same kind), which is the standard way to resample clusters.
    """
    summary = group_summary(rows[column], [rows["session_key"], rows["corner"], rows["driver"]])
    estimate = icc_from_group_stats(summary["n"], summary["mean"], summary["ss"])
    rows_by_session = [np.where(summary["session_key"] == key)[0] for key in summary["session_key"].unique()]
    draws = []
    for _ in range(BOOTSTRAP):
        picked = rng.integers(0, len(rows_by_session), size=len(rows_by_session))
        index = np.concatenate([rows_by_session[p] for p in picked])
        draws.append(icc_from_group_stats(summary["n"].to_numpy()[index], summary["mean"].to_numpy()[index],
                                          summary["ss"].to_numpy()[index]))
    return estimate, percentile_interval(draws)


def weekend_level(rows, column, rng):
    """ICC of each driver's session means, groups (driver, season), and a bootstrap over DRIVER-SEASONS.

    Resampling sessions here would be wrong: a session drawn twice gives a
    driver two identical weekend means, which looks like perfect consistency
    and pushes the ICC up (seen in a first version: estimates fell outside
    their own intervals). The groups themselves (driver-seasons) are resampled.
    """
    means = rows.groupby(["year", "session_key", "driver"])[column].mean().reset_index()
    summary = group_summary(means[column], [means["driver"], means["year"]])
    summary = summary[summary["n"] >= 2]   # a driver needs at least two weekends
    estimate = icc_from_group_stats(summary["n"], summary["mean"], summary["ss"])
    n, mean, ss = summary["n"].to_numpy(), summary["mean"].to_numpy(), summary["ss"].to_numpy()
    draws = []
    for _ in range(BOOTSTRAP):
        index = rng.integers(0, len(summary), size=len(summary))
        draws.append(icc_from_group_stats(n[index], mean[index], ss[index]))
    return estimate, percentile_interval(draws)


def percentile_interval(draws):
    draws = np.array(draws, dtype=float)
    draws = draws[np.isfinite(draws)]
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def lap_to_lap_sd(rows, column):
    """Pooled within-(session, corner, driver) standard deviation: the typical lap-to-lap spread."""
    groups = rows.groupby(["session_key", "corner", "driver"])[column]
    deviations = rows[column] - groups.transform("mean")
    counts = groups.transform("count")
    keep = counts > 1
    degrees = (keep.groupby([rows["session_key"], rows["corner"], rows["driver"]]).sum() - 1).clip(lower=0).sum()
    return float(np.sqrt(np.nansum(deviations[keep] ** 2) / degrees)) if degrees > 0 else float("nan")


def figure(table):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.8), sharey=True)
    labels = list(dict.fromkeys(table["feature"]))
    for ax, corner_type in zip(axes, CORNER_TYPES):
        subset = table[table["corner_type"] == corner_type].set_index("feature").loc[labels]
        y = np.arange(len(labels))
        for offset, (level, color) in zip([-0.15, 0.15], [("lap", SERIES[0]), ("weekend", SERIES[1])]):
            ax.errorbar(subset[f"icc_{level}"], y + offset,
                        xerr=[subset[f"icc_{level}"] - subset[f"icc_{level}_low"],
                              subset[f"icc_{level}_high"] - subset[f"icc_{level}"]],
                        fmt="o", color=color, capsize=3, markersize=5,
                        label="lap level (same corner, same day)" if level == "lap" else "weekend level (persists across weekends)")
        ax.axvline(0, color=TEXT_SECONDARY, linewidth=0.8)
        ax.set_xlim(-0.1, 1.0)
        ax.set_yticks(np.arange(len(labels)))
        ax.set_yticklabels([NICE_LABELS.get(label, label) for label in labels], fontsize=9)
        ax.invert_yaxis()
        ax.set_title(f"{corner_type} corners", fontsize=11)
        ax.set_xlabel("ICC (share of variation between drivers), 95 % interval")
    handles, legend_labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc="upper right", ncol=2, fontsize=9, bbox_to_anchor=(1.0, 1.0))
    fig.suptitle("H1: how repeatable and distinctive is each feature? 2023–2024 dry qualifying, all drivers",
                 x=0.0, ha="left", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "icc.png", bbox_inches="tight")
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    apply_style()
    rng = np.random.default_rng(SEED)
    data, cleaning = clean(load_dataset())
    data = add_field_relative(data)
    errors = measurement_errors()

    rows = []
    for corner_type in CORNER_TYPES:
        subset = data[data["corner_type"] == corner_type]
        for feature in ALL_FEATURES:
            column = f"{feature}_rel"
            part = subset.dropna(subset=[column])
            if len(part) < 50:
                continue
            row = {"corner_type": corner_type, "feature": feature, "rows": len(part)}
            row["icc_lap"], (row["icc_lap_low"], row["icc_lap_high"]) = lap_level(part, column, rng)
            row["icc_weekend"], (row["icc_weekend_low"], row["icc_weekend_high"]) = weekend_level(part, column, rng)
            row["lap_to_lap_sd"] = lap_to_lap_sd(part, column)
            row["measurement_error_per_lap"] = errors.get((corner_type, feature), np.nan)
            row["sd_over_measurement_error"] = row["lap_to_lap_sd"] / row["measurement_error_per_lap"]
            rows.append(row)
            print(f"{corner_type:6s} {feature:20s} n {len(part):5d}  ICC lap {row['icc_lap']:.2f} "
                  f"[{row['icc_lap_low']:.2f}, {row['icc_lap_high']:.2f}]  weekend {row['icc_weekend']:.2f} "
                  f"[{row['icc_weekend_low']:.2f}, {row['icc_weekend_high']:.2f}]  lap SD {row['lap_to_lap_sd']:.2f} "
                  f"(meas. error {row['measurement_error_per_lap']:.2f})", flush=True)
    table = pd.DataFrame(rows)
    table.to_csv(OUT_DIR / "icc.csv", index=False, float_format="%.4f")
    figure(table)
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump({"cleaning": cleaning, "bootstrap": BOOTSTRAP, "seed": SEED,
                   "rows": table.to_dict(orient="records")}, file, indent=1, default=float)
    print(f"Saved results to {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

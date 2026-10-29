"""Is there a per-lap offset in the position data, and does it leak into the corner features?

Design and decision rules were written down BEFORE this was run (docs/decisions.md,
2026-10-29). Development data only (2023-2025 kept laps; 2025's own test is frozen
and is not changed by anything here).

The measurement: quality.start_offset = median of (projected position s - integrated
distance d) over the first 300 m after the line, where d has had no time to drift.

  Q1  Do laps carry offsets beyond the measurement noise?
      Yes if the median within-session standard deviation of the per-lap offset is
      more than twice the synthetic noise floor (the scatter of the estimate on
      synthetic laps with NO offset, using the scatter measured on the real feed).
  Q2  Whose offset is it? Variance split: sessions / drivers within a session / laps.
  Q3  Does it explain the gap error at the line? Pairs of laps of the same driver and
      session: (gap at the line from s - official lap-time gap), in metres, against
      the difference of the two laps' offsets (expected slope -1 if offsets are real).
  Q4  Does it leak into the corner features? Slope of the lap's position-feature
      residuals (brake onset, slowest point, throttle pickup) against the lap's
      offset, both within driver and session. Slope near +1 = passes straight in.
      Control: minimum speed (km/h) should not follow a position offset.
  Consequence (fixed in advance): Q1 holds AND the pooled Q4 slope > 0.5 -> a per-lap
  offset correction becomes a preregistered secondary feature variant for 2026.

Run from the repo root (reads only local files, ~1 minute):
    .venv\\Scripts\\python.exe experiments\\18_position_offset.py
"""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from apextrace.dataset import clean
from apextrace.plots import SERIES, TEXT_SECONDARY, apply_style
from apextrace.quality import start_offset
from apextrace.synthetic import lap_with_position_offset

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))         # the gap function lives in the web app's data module
from app.data import delta_time            # noqa: E402

RESULTS = REPO_ROOT / "results"
OUT_DIR = RESULTS / "18_position_offset"
RAW_FILES = [RESULTS / "09_dataset" / "raw_samples.parquet", RESULTS / "final" / "raw_samples_2025.parquet"]
DATASETS = [RESULTS / "09_dataset" / "dataset.csv.gz", RESULTS / "final" / "dataset_2025.csv.gz"]
WINDOW_M = 300.0
NOISE_LAPS = 400
SEED = 2026
POSITION_FEATURES = ["brake_onset_m", "apex_m", "throttle_pickup_m"]
LAP_KEYS = ["session_key", "driver", "lap"]


# ---------------------------------------------------------------- per-lap offsets

def per_lap_offsets():
    """One row per kept lap: its start offset, plus the window residuals for measuring scatter."""
    rows, residuals = [], []
    for path in RAW_FILES:
        raw = pd.read_parquet(path, columns=["year", "session_key", "driver", "team", "lap", "lap_time_s",
                                             "time_s", "s_m", "d_m", "speed_kmh"])
        for (year, key, driver, lap), g in raw.groupby(["year", "session_key", "driver", "lap"]):
            g = g.sort_values("time_s")
            s, d, v = g["s_m"].to_numpy(), g["d_m"].to_numpy(), g["speed_kmh"].to_numpy()
            offset = start_offset(s, d, window_m=WINDOW_M)
            window = (d <= WINDOW_M) & (np.abs(s - d) <= 50.0)
            if np.isfinite(offset):
                residuals.extend(((s - d)[window] - offset).tolist())
            rows.append({"year": int(year), "session_key": int(key), "driver": driver, "team": g["team"].iloc[0],
                         "lap": int(lap), "lap_time_s": float(g["lap_time_s"].iloc[0]), "offset_m": offset,
                         "window_samples": int(window.sum()),
                         "start_speed_kmh": float(np.median(v[window])) if window.any() else np.nan,
                         "end_speed_ms": float(np.mean(v[-3:])) / 3.6})
    return pd.DataFrame(rows), np.array(residuals)


def noise_floor(scatter_m, rng):
    """Standard deviation of start_offset on synthetic laps with NO offset (the feed's real scatter)."""
    estimates = []
    for _ in range(NOISE_LAPS):
        s, d = lap_with_position_offset(rng, 0.0, 0.0025, scatter_m=scatter_m)
        estimates.append(start_offset(s, d, window_m=WINDOW_M))
    return float(np.std(estimates)), estimates


# ---------------------------------------------------------------- Q2 variance split

def variance_split(laps):
    """Share of the total sum of squares between sessions, between drivers within a session, and between laps."""
    x = laps["offset_m"]
    grand = x.mean()
    session_mean = laps.groupby("session_key")["offset_m"].transform("mean")
    group_mean = laps.groupby(["session_key", "driver"])["offset_m"].transform("mean")
    total = float(((x - grand) ** 2).sum())
    between_sessions = float(((session_mean - grand) ** 2).sum())
    between_drivers = float(((group_mean - session_mean) ** 2).sum())
    within = float(((x - group_mean) ** 2).sum())
    return {"sessions": between_sessions / total, "drivers_within_session": between_drivers / total,
            "laps_within_driver_session": within / total}


# ---------------------------------------------------------------- Q3 gap error at the line

def gap_errors(laps):
    """For every pair of laps of the same driver and session: gap error at the line, from s and from d."""
    keep = set(zip(laps["session_key"], laps["driver"], laps["lap"]))
    offsets = laps.set_index(LAP_KEYS)
    rows = []
    for path in RAW_FILES:
        raw = pd.read_parquet(path, columns=["session_key", "driver", "lap", "time_s", "s_m", "d_m"])
        for (key, driver), group in raw.groupby(["session_key", "driver"]):
            laps_here = {}
            for lap, g in group.groupby("lap"):
                if (key, driver, lap) in keep:
                    laps_here[lap] = g.sort_values("time_s")
            numbers = sorted(laps_here)
            for i in range(len(numbers)):
                for j in range(i + 1, len(numbers)):
                    a, b = laps_here[numbers[i]], laps_here[numbers[j]]
                    info_a, info_b = offsets.loc[(key, driver, numbers[i])], offsets.loc[(key, driver, numbers[j])]
                    official = info_b["lap_time_s"] - info_a["lap_time_s"]
                    _, gap_s = delta_time(a["s_m"], a["time_s"], b["s_m"], b["time_s"])
                    _, gap_d = delta_time(a["d_m"], a["time_s"], b["d_m"], b["time_s"])
                    speed = 0.5 * (info_a["end_speed_ms"] + info_b["end_speed_ms"])
                    rows.append({"session_key": key, "driver": driver,
                                 "error_s_projected": gap_s[-1] - official, "error_s_integrated": gap_d[-1] - official,
                                 "error_m_projected": (gap_s[-1] - official) * speed,
                                 "offset_difference_m": info_b["offset_m"] - info_a["offset_m"]})
    return pd.DataFrame(rows).dropna()


# ---------------------------------------------------------------- Q4 leakage into features

def slope_with_interval(x, y, rng, resamples=1000):
    """Least-squares slope of y on x, with a bootstrap 95 % interval (resampling rows)."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    slope = float(np.polyfit(x, y, 1)[0])
    boot = []
    for _ in range(resamples):
        pick = rng.integers(0, len(x), len(x))
        boot.append(np.polyfit(x[pick], y[pick], 1)[0])
    return slope, [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))], float(np.corrcoef(x, y)[0, 1])


def leakage(laps, rng):
    tables = [pd.read_csv(path) for path in DATASETS]
    rows, _ = clean(pd.concat(tables, ignore_index=True))
    merged = rows.merge(laps[LAP_KEYS + ["offset_m"]], on=LAP_KEYS).dropna(subset=["offset_m"])
    # within driver and session: lap-to-lap changes only
    merged["offset_resid"] = merged["offset_m"] - merged.groupby(["session_key", "driver"])["offset_m"].transform("median")
    out, pooled_x, pooled_y = {}, [], []
    for feature in POSITION_FEATURES + ["min_speed_kmh"]:
        part = merged.dropna(subset=[feature]).copy()
        part["resid"] = part[feature] - part.groupby(["session_key", "driver", "corner"])[feature].transform("median")
        slope, interval, r = slope_with_interval(part["offset_resid"], part["resid"], rng)
        out[feature] = {"slope": slope, "ci95": interval, "r": r, "rows": int(len(part))}
        if feature in POSITION_FEATURES:
            pooled_x.extend(part["offset_resid"])
            pooled_y.extend(part["resid"])
    slope, interval, r = slope_with_interval(pooled_x, pooled_y, rng)
    out["pooled_position_features"] = {"slope": slope, "ci95": interval, "r": r, "rows": len(pooled_x)}
    return out, merged


# ---------------------------------------------------------------- figure

def figure(laps, synthetic, merged):
    apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    # drivers with 3+ laps in the session, centred on their MEAN (centring on the median would
    # put the middle lap of every odd-sized group at exactly 0 and draw a false spike there)
    counts = laps.groupby(["session_key", "driver"])["offset_m"].transform("count")
    within = (laps["offset_m"] - laps.groupby(["session_key", "driver"])["offset_m"].transform("mean"))[counts >= 3].dropna()
    bins = np.linspace(-12, 12, 49)
    axes[0].hist(np.clip(within, -12, 12), bins=bins, density=True, color=SERIES[0], alpha=0.85,
                 label="real laps (offset minus the driver-session mean)")
    axes[0].hist(np.clip(np.array(synthetic) - np.mean(synthetic), -12, 12), bins=bins, density=True,
                 histtype="step", color=SERIES[1], linewidth=2, label="synthetic laps with no offset (noise only)")
    axes[0].set_xlabel("per-lap position offset, metres (beyond ±12 shown at the edge)")
    axes[0].set_ylabel("density")
    axes[0].set_title("Lap-to-lap offsets vs measurement noise", fontsize=10)
    axes[0].legend(fontsize=8, frameon=False)
    part = merged.dropna(subset=["brake_onset_m"]).copy()
    part["resid"] = part["brake_onset_m"] - part.groupby(["session_key", "driver", "corner"])["brake_onset_m"].transform("median")
    axes[1].scatter(np.clip(part["offset_resid"], -12, 12), np.clip(part["resid"], -40, 40), s=3, alpha=0.15, color=SERIES[0])
    slope = np.polyfit(part["offset_resid"], part["resid"], 1)[0]
    xs = np.array([-12, 12])
    axes[1].plot(xs, slope * xs, color=SERIES[1], linewidth=2, label=f"fit: slope {slope:.2f}")
    axes[1].plot(xs, xs, color=TEXT_SECONDARY, linewidth=1, label="slope 1 (offset passes straight in)")
    axes[1].set_xlabel("lap's offset, relative to the driver's session, m (clipped ±12)")
    axes[1].set_ylabel("brake onset, relative to the driver's corner, m (clipped ±40)")
    axes[1].set_title("Does the offset move the braking point?", fontsize=10)
    axes[1].legend(fontsize=8, frameon=False)
    fig.savefig(OUT_DIR / "position_offset.png", bbox_inches="tight", dpi=130)
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    laps, residuals = per_lap_offsets()
    measured = laps.dropna(subset=["offset_m"])
    # scatter of single samples around their lap's offset (robust: 1.4826 x median absolute deviation)
    scatter = float(1.4826 * np.median(np.abs(residuals)))
    floor, synthetic = noise_floor(scatter, rng)

    # Q1
    session_sd = measured.groupby("session_key")["offset_m"].std().dropna()
    driver_sd = measured.groupby(["session_key", "driver"])["offset_m"].std().dropna()
    q1 = {"median_within_session_sd_m": float(session_sd.median()),
          "median_within_driver_session_sd_m": float(driver_sd.median()),
          "noise_floor_m": floor, "measured_scatter_m": scatter,
          "holds": bool(session_sd.median() > 2 * floor)}
    # Q2
    q2 = variance_split(measured)
    # Q3
    pairs = gap_errors(measured)
    slope3, interval3, r3 = slope_with_interval(pairs["offset_difference_m"], pairs["error_m_projected"], rng)
    q3 = {"pairs": int(len(pairs)),
          "median_abs_error_s_projected": float(pairs["error_s_projected"].abs().median()),
          "median_abs_error_s_integrated": float(pairs["error_s_integrated"].abs().median()),
          "slope_error_m_on_offset_difference": slope3, "ci95": interval3, "r": r3}
    # Q4
    q4, merged = leakage(measured, rng)
    consequence = bool(q1["holds"] and q4["pooled_position_features"]["slope"] > 0.5)

    # EXPLORATORY (not one of the four preregistered questions): is the "offset" really a
    # lap-START TIMING error? Integrated distance d is counted from the reported lap start;
    # if that timestamp is dt early, d reads v x dt too long, so offset = -v x dt. A fixed
    # timing error then gives offsets that grow with the speed at the line, while the
    # same offsets expressed in seconds (offset / v) stay about the same at every track.
    per_session = measured.groupby("session_key").agg(sd_m=("offset_m", "std"), speed_kmh=("start_speed_kmh", "median"))
    measured_s = measured.assign(offset_s=measured["offset_m"] / (measured["start_speed_kmh"] / 3.6))
    per_session["sd_s"] = measured_s.groupby("session_key")["offset_s"].std()
    per_session = per_session.dropna()
    exploratory = {
        "sessions": int(len(per_session)),
        "corr_session_sd_m_vs_start_speed": float(per_session["sd_m"].corr(per_session["speed_kmh"])),
        "corr_session_sd_seconds_vs_start_speed": float(per_session["sd_s"].corr(per_session["speed_kmh"])),
        "median_within_driver_session_sd_s": float(
            measured_s.groupby(["session_key", "driver"])["offset_s"].std().dropna().median()),
        "note": "exploratory interpretation: offset = -(speed at the line) x (lap-start timestamp error)",
    }

    summary = {"laps": int(len(laps)), "laps_with_offset": int(len(measured)),
               "offset_m": {"mean": float(measured["offset_m"].mean()), "median": float(measured["offset_m"].median()),
                            "sd": float(measured["offset_m"].std()),
                            "p5": float(measured["offset_m"].quantile(0.05)), "p95": float(measured["offset_m"].quantile(0.95))},
               "window_samples_median": float(measured["window_samples"].median()),
               "start_speed_kmh_median": float(measured["start_speed_kmh"].median()),
               "q1_beyond_noise": q1, "q2_variance_share": q2, "q3_gap_error": q3, "q4_feature_leakage": q4,
               "consequence_secondary_variant_for_2026": consequence,
               "exploratory_timing_interpretation": exploratory}
    measured.to_csv(OUT_DIR / "lap_offsets.csv.gz", index=False, float_format="%.3f")
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)
    figure(measured, synthetic, merged)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

"""Data for the web app: small JSON exports + raw lap samples, and two lap-comparison helpers.

The app shows research results; it never computes them. Two kinds of data:

  1. results/app/*.json, written by experiments/16_app_data.py (small, committed):
     sessions, drivers, team colours, corners, track outlines, headline numbers.
  2. raw lap samples from the Parquet exports (gitignored, rebuilt by
     experiments/09_build_dataset.py and 14_final_2025.py), read one lap at a time
     for the telemetry page. Reading one lap with a filter takes ~40 ms, so no cache.

The two helpers below (delta_time, mini_sectors) are the only calculations the
app does. They are display helpers, not research results, and are tested in
tests/test_app.py.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS = REPO_ROOT / "results"

# Raw-sample files per season (both gitignored; rebuilt by the experiment scripts)
RAW_FILES = {2023: "09_dataset/raw_samples.parquet",
             2024: "09_dataset/raw_samples.parquet",
             2025: "final/raw_samples_2025.parquet"}
LAP_COLUMNS = ["time_s", "s_m", "d_m", "speed_kmh", "throttle_pct", "brake", "gear", "x_m", "y_m"]

# Corner lab: the committed datasets (one row per driver, lap, corner) and the columns it shows
DATASET_FILES = ["09_dataset/dataset.csv.gz", "final/dataset_2025.csv.gz"]
CORNER_FEATURES = ["brake_onset_m", "braking_distance_m", "mean_decel_ms2", "min_speed_kmh", "apex_m",
                   "throttle_pickup_m", "full_throttle_m", "entry_speed_kmh", "exit_speed_kmh", "corner_time_s"]
CORNER_COLUMNS = ["session_key", "driver", "team", "lap", "lap_time_s", "corner", "corner_type"] + CORNER_FEATURES

# Below this, a mini-sector gain is inside the measurement error and shown as "even".
# Alignment error per lap ~1.15 m (Phase 3); at 250 km/h (69 m/s) that is 0.017 s.
EVEN_THRESHOLD_S = 0.02

# Width of the moving average in fused_distance(): long enough to average ~20
# samples of position noise, short compared with the slow drift of integrated speed.
FUSION_WINDOW_M = 400.0


class RawSamplesMissing(Exception):
    """The raw-sample Parquet for a season hasn't been built on this computer."""


# ---------------------------------------------------------------- pure helpers (tested)

def rotate_points(x, y, centre, angle_deg):
    """Move points to the track centre and rotate them, exactly like the exported outline.

    The outline in sessions.json was centred and rotated so the track lies
    landscape (experiments/16_app_data.landscape_rotation). Lap samples must get
    the same transform, or the car markers would sit off the drawn track.
    """
    a = np.radians(angle_deg)
    x = np.asarray(x, dtype=float) - centre[0]
    y = np.asarray(y, dtype=float) - centre[1]
    return x * np.cos(a) - y * np.sin(a), x * np.sin(a) + y * np.cos(a)


def increasing_distance(s, t):
    """Keep only samples where the track distance moves forward.

    WHY: to look up "at what time was the car at distance s?" we interpolate
    time over distance, and np.interp needs strictly increasing x values. The
    aligned distance comes from projecting noisy X/Y onto the track, so once in
    a while a sample lands a few centimetres BEHIND the previous one (1 lap in
    79 at 2024 Abu Dhabi). Such a sample is dropped.
    Example: s = [10.0, 22.5, 22.3, 35.1] -> keep [10.0, 22.5, 35.1].
    """
    keep_s, keep_t = [], []
    for distance, time in zip(s, t):
        if not keep_s or distance > keep_s[-1]:
            keep_s.append(float(distance))
            keep_t.append(float(time))
    return np.array(keep_s), np.array(keep_t)


def fused_distance(s, d, window_m=FUSION_WINDOW_M):
    """A smooth track coordinate for drawing: integrated distance, corrected by position.

    Two measurements of "how far along the lap is the car", with opposite faults:
      s (projected X/Y position): right on average, but each sample scatters by
        about +-3 m (position noise), which shakes the traces sideways;
      d (integrated speed): smooth, because integrating averages the noise
        (an integrator is a low-pass filter), but it drifts: ~12 m per lap at
        2024 Abu Dhabi.
    A complementary filter keeps the good part of each: the offset s - d changes
    only slowly (drift) apart from the noise, so a moving average over
    `window_m` of track (about 20 samples) removes the noise and keeps the drift
    correction:
        fused = d + moving_average(s - d)
    Example: at 3000 m, d = 2994.0 and the averaged offset is +6.2 m -> fused = 3000.2.
    This is the same idea as corners.fuse_window_coordinate (Phase 3), over a whole lap.
    """
    s = np.asarray(s, dtype=float)
    d = np.asarray(d, dtype=float)
    offset = s - d
    smooth = np.empty(len(d))
    for i in range(len(d)):
        near = np.abs(d - d[i]) <= window_m / 2      # the samples within +-200 m of this one
        smooth[i] = np.mean(offset[near])
    return d + smooth


def delta_time(s_a, t_a, s_b, t_b, step_m=5.0):
    """Time gap of lap B relative to lap A at every point of the track.

    WHY: lap times only give the gap at the finish line. To see WHERE a driver
    gains or loses, compare the clocks of both laps at the same place: for every
    distance s on a common grid, look up when each car was there (linear
    interpolation of time over distance), and subtract.
        delta(s) = time_B(s) - time_A(s)
    Positive = B reached this point later (B is behind); a rising curve = B
    losing time over that stretch.

    Example: at s = 1000 m, A was there after 15.20 s and B after 15.32 s ->
    delta = +0.12 s. If at s = 1500 m the gap is +0.05 s, B gained 0.07 s
    between 1000 m and 1500 m.

    Which distance to pass: the integrated distance d_m, not the projected s_m.
    Measured on 2024 Abu Dhabi (NOR vs PIA, official gap +0.209 s): with s_m the
    curve jitters by 0.041 s and ends at +0.290 s (position has a lap-specific
    offset of a few metres); with d_m it jitters by 0.007 s and ends at +0.198 s.
    d_m starts at exactly 0 on the line, and its slow drift is nearly the same
    for both laps, so it cancels in the subtraction.
    Returns (grid in metres, delta in seconds), on the stretch both laps cover.
    """
    s_a, t_a = increasing_distance(s_a, t_a)
    s_b, t_b = increasing_distance(s_b, t_b)
    start = max(s_a[0], s_b[0])
    end = min(s_a[-1], s_b[-1])
    grid = np.arange(start, end, step_m)
    delta = np.interp(grid, s_b, t_b) - np.interp(grid, s_a, t_a)
    return grid, delta


def mini_sectors(grid, delta, count=24, even_threshold_s=EVEN_THRESHOLD_S):
    """Split the lap into equal stretches and say who was faster in each.

    The gain of a stretch is how much the gap changed across it:
        gain = delta(end) - delta(start)
    gain > 0: B lost time there, so A was faster; gain < 0: B was faster.
    |gain| below the measurement error (0.02 s) is reported as "even".
    Example: delta goes from +0.10 s to +0.16 s over a stretch -> gain +0.06 s,
    A faster by 0.06 s.
    This is the coloured track map of F1 TV graphics, made from the delta curve.
    """
    edges = np.linspace(grid[0], grid[-1], count + 1)
    edge_delta = np.interp(edges, grid, delta)
    sectors = []
    for i in range(count):
        gain = float(edge_delta[i + 1] - edge_delta[i])
        if abs(gain) < even_threshold_s:
            faster = "even"
        elif gain > 0:
            faster = "a"
        else:
            faster = "b"
        sectors.append({"start_m": round(float(edges[i]), 1), "end_m": round(float(edges[i + 1]), 1),
                        "gain_s": round(gain, 3), "faster": faster})
    return sectors


# ---------------------------------------------------------------- data access

class AppData:
    """Loads the exported JSON once, reads raw laps on request, and the corner table on first use."""

    def __init__(self, results_dir=DEFAULT_RESULTS):
        self.results_dir = Path(results_dir)
        app_dir = self.results_dir / "app"
        self.sessions = {}
        for session in self._load(app_dir / "sessions.json"):
            self.sessions[session["key"]] = session
        self.headline = self._load(app_dir / "headline.json")
        self.hero = self._load(app_dir / "hero.json")
        # Driver vs car / Corner lab exports (missing in old exports or tests: None)
        self.features = self._load_optional(app_dir / "features.json")
        self.identification = self._load_optional(app_dir / "identification.json")
        self.signatures = self._load_optional(app_dir / "signatures.json")
        self._corner_table = None

    @staticmethod
    def _load(path):
        with open(path, encoding="utf-8") as file:
            return json.load(file)

    def _load_optional(self, path):
        return self._load(path) if path.exists() else None

    # ---------------------------------------------------------------- corner lab

    def corner_table(self):
        """Every clean (driver, lap, corner) row of 2023-2025, cleaned with the research's own rules.

        Read from the committed datasets (09_build_dataset.py, 14_final_2025.py) and
        passed through apextrace.dataset.clean, so the Corner lab shows exactly the
        rows the analysis used. Loaded once, on the first request (~1 s).
        """
        if self._corner_table is None:
            from apextrace.dataset import clean      # imported here: only this page needs it
            tables = []
            for relative in DATASET_FILES:
                path = self.results_dir / relative
                if path.exists():
                    tables.append(pd.read_csv(path))
            if not tables:
                self._corner_table = pd.DataFrame()
            else:
                rows, _ = clean(pd.concat(tables, ignore_index=True))
                self._corner_table = rows[CORNER_COLUMNS]
        return self._corner_table

    def corner_rows(self, session_key):
        """The clean rows of one session as plain dicts (NaN -> None, so the JSON is valid)."""
        table = self.corner_table()
        if table.empty:
            return None
        rows = table[table["session_key"] == session_key]
        out = []
        for record in rows.to_dict("records"):
            clean_record = {}
            for key, value in record.items():
                if isinstance(value, float):
                    value = None if np.isnan(value) else round(value, 3)
                elif isinstance(value, np.integer):
                    value = int(value)
                clean_record[key] = value
            out.append(clean_record)
        return out

    def session_index(self):
        """One light row per session (for the pickers), newest season first."""
        rows = []
        for s in self.sessions.values():
            rows.append({"key": s["key"], "year": s["year"], "round": s["round"], "location": s["location"],
                         "country": s["country"], "circuit": s["circuit"], "date": s["date"],
                         "available": s["track"] is not None, "wet": s.get("wet", False), "note": s["note"]})
        rows.sort(key=lambda r: (-r["year"], r["round"]))
        return rows

    def raw_available(self, year):
        return (self.results_dir / RAW_FILES[year]).exists()

    def lap(self, session_key, driver, lap_number):
        """One lap's measured samples, with X/Y moved onto the drawn track outline."""
        session = self.sessions[session_key]
        path = self.results_dir / RAW_FILES[session["year"]]
        if not path.exists():
            raise RawSamplesMissing(RAW_FILES[session["year"]])
        table = pq.read_table(path, columns=LAP_COLUMNS, filters=[
            ("session_key", "=", session_key), ("driver", "=", driver), ("lap", "=", lap_number)])
        lap = table.to_pandas().sort_values("time_s")
        if lap.empty:
            return None
        track = session["track"]
        x, y = rotate_points(lap["x_m"], lap["y_m"], track["centre"], track["rotation_deg"])
        fused = fused_distance(lap["s_m"].to_numpy(), lap["d_m"].to_numpy())
        return {"t": np.round(lap["time_s"].to_numpy(), 3).tolist(),
                "s": np.round(fused, 1).tolist(),               # chart coordinate (smooth, on track)
                "d": np.round(lap["d_m"].to_numpy(), 2).tolist(),  # integrated distance (for the gap)
                "speed": lap["speed_kmh"].astype(int).tolist(),
                "throttle": lap["throttle_pct"].astype(int).tolist(),
                "brake": lap["brake"].astype(bool).tolist(),
                "gear": lap["gear"].astype(int).tolist(),
                "x": np.round(x, 1).tolist(), "y": np.round(y, 1).tolist()}

    def compare(self, session_key, a, b):
        """Two laps + their delta-time curve + mini-sector winners. a, b = (driver, lap)."""
        lap_a = self.lap(session_key, *a)
        lap_b = self.lap(session_key, *b)
        if lap_a is None or lap_b is None:
            return None
        # the gap is computed on integrated distance (see delta_time) ...
        grid, delta = delta_time(lap_a["d"], lap_a["t"], lap_b["d"], lap_b["t"])
        sectors = mini_sectors(grid, delta)
        # ... and placed on the charts' coordinate through lap A's own d -> fused relation
        d_a, s_a = increasing_distance(lap_a["d"], lap_a["s"])
        for sector in sectors:
            sector["start_m"] = round(float(np.interp(sector["start_m"], d_a, s_a)), 1)
            sector["end_m"] = round(float(np.interp(sector["end_m"], d_a, s_a)), 1)
        return {"a": lap_a, "b": lap_b,
                "delta": {"s": np.round(np.interp(grid, d_a, s_a), 1).tolist(), "d": np.round(delta, 3).tolist()},
                "mini_sectors": sectors}

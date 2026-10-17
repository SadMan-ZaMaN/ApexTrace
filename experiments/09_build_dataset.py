"""Phase 6: build the multi-season dataset, one row per (session, driver, lap, corner).

Works from the OpenF1 cache filled by 08_download_openf1.py (run that first;
anything missing would be downloaded on the fly). For each 2023/2024
qualifying session:
  1. lap table + lap selection (same rules as the pilot);
  2. reference path = the session's fastest kept lap (X/Y, s = 0 at the line);
  3. braking corners detected automatically on that lap
     (corners.detect_braking_corners: speed dips of >= 50 km/h; reference
     point = the dip, i.e. the apex on the reference lap; type by min speed);
  4. every kept lap of every driver on the track coordinate; for each corner:
     window [-300 m, +200 m], feed-gap check, fused coordinate, features
     (features.corner_features), exactly as in the validated pilot.

Outputs in results/09_dataset/:
  dataset.csv.gz       one row per (session, driver, lap, corner), usable or not (+ reason)
  corners.csv          the detected corners of every session
  sessions.csv         per session: laps, kept laps, corners, usable pairs
  summary.json
  raw_samples.parquet  every measured car sample of every kept lap, with its
                       track coordinate s and (interpolated) X/Y: the "classic"
                       flat dataset for free exploration. Local only (*.parquet
                       is gitignored); rebuilt by running this script.

Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\09_build_dataset.py
"""

import json
import time
from pathlib import Path

import pandas as pd

from apextrace.features import FEATURES
from apextrace.openf1 import qualifying_sessions
from apextrace.session_build import build_session

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "results" / "09_dataset"
YEARS = [2023, 2024]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_rows, all_corners, summaries, raw_tables = [], [], [], []
    for year in YEARS:
        sessions = qualifying_sessions(year)
        for index, session in sessions.iterrows():
            start = time.perf_counter()
            try:
                rows, corner_rows, summary, raw = build_session(year, index + 1, session)
            except Exception as exc:  # log and continue
                rows, corner_rows, raw = [], [], pd.DataFrame()
                summary = {"year": year, "round": index + 1, "location": session["location"],
                           "session_key": int(session["session_key"]), "note": f"{type(exc).__name__}: {exc}"}
            summary["seconds"] = round(time.perf_counter() - start, 1)
            all_rows.extend(rows)
            if len(raw):
                raw_tables.append(raw)
            all_corners.extend(corner_rows)
            summaries.append(summary)
            print(f"{year} R{index + 1:02d} {session['location']:20s} kept {summary.get('kept_laps', 0):3d} "
                  f"corners {summary.get('corners', 0):2d} usable {summary.get('usable_pairs', 0):4d}/"
                  f"{summary.get('pairs', 0):4d}  {summary['seconds']:5.1f} s  {summary.get('note', '')}", flush=True)

    dataset = pd.DataFrame(all_rows)
    dataset.to_csv(OUT_DIR / "dataset.csv.gz", index=False, float_format="%.3f")
    pd.DataFrame(all_corners).to_csv(OUT_DIR / "corners.csv", index=False, float_format="%.1f")
    sessions = pd.DataFrame(summaries)
    sessions.to_csv(OUT_DIR / "sessions.csv", index=False)
    raw_samples = pd.concat(raw_tables, ignore_index=True) if raw_tables else pd.DataFrame()
    raw_samples.to_parquet(OUT_DIR / "raw_samples.parquet", index=False)
    print(f"raw samples: {len(raw_samples)} rows -> {(OUT_DIR / 'raw_samples.parquet').relative_to(REPO_ROOT)} "
          f"({(OUT_DIR / 'raw_samples.parquet').stat().st_size / 1e6:.1f} MB, local only)")

    usable = dataset[dataset["usable"]] if len(dataset) else dataset
    summary = {
        "sessions": len(sessions),
        "sessions_with_data": int((sessions.get("usable_pairs", pd.Series(dtype=float)).fillna(0) > 0).sum()),
        "rows": len(dataset), "usable_rows": len(usable),
        "drivers": int(usable["driver"].nunique()) if len(usable) else 0,
        "laps": int(usable[["session_key", "driver", "lap"]].drop_duplicates().shape[0]) if len(usable) else 0,
        "corners": len(all_corners),
        "usable_by_corner_type": usable["corner_type"].value_counts().to_dict() if len(usable) else {},
        "exclusion_reasons": dataset.loc[~dataset["usable"], "reason"].value_counts().to_dict() if len(dataset) else {},
        "features": FEATURES,
    }
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, default=int)
    print(f"\n{summary['sessions']} sessions ({summary['sessions_with_data']} with data), "
          f"{summary['usable_rows']} usable rows of {summary['rows']}, {summary['drivers']} drivers, "
          f"{summary['laps']} laps, {summary['corners']} corners")
    print(f"usable rows by corner type: {summary['usable_by_corner_type']}")
    print(f"exclusions: {summary['exclusion_reasons']}")


if __name__ == "__main__":
    main()

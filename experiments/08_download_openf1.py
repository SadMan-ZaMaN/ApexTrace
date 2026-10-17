"""Phase 6: download every 2023 and 2024 qualifying session from OpenF1 (only what we need).

For each session: the lap table (laps, stints, race control, drivers), the
lap selection (select_laps, same rules as the pilot), then car and position
data for each driver over the time span of their KEPT laps: 2 requests per
driver (~44 per session), because OpenF1 allows only ~30 requests per minute
(a first version that asked per lap, ~160 requests per session, ran into
"429 Too Many Requests" and would have taken many hours).

Everything goes into cache/openf1/ (one gzip-compressed JSON file per
request), so the script can be stopped and restarted: finished requests are
never repeated. 2025 is never requested (frozen test set;
qualifying_sessions refuses it).

Run from the repo root (takes ~1.5 hours the first time):
    .venv\\Scripts\\python.exe experiments\\08_download_openf1.py
Output:
    results/08_download/download_log.csv  one row per session
"""

import time
from pathlib import Path

import pandas as pd

from apextrace.openf1 import download_session, qualifying_sessions

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "results" / "08_download"
YEARS = [2023, 2024]
WORKERS = 3


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for year in YEARS:
        sessions = qualifying_sessions(year)
        for round_index, session in sessions.iterrows():
            start = time.perf_counter()
            row = {"year": year, "round": round_index + 1, "location": session["location"],
                   "session_key": int(session["session_key"]), "laps": 0, "kept_laps": 0,
                   "kept_laps_with_data": 0, "error": ""}
            try:
                counts = download_session(row["session_key"], session["date_end"], workers=WORKERS)
                row.update(counts)
            except Exception as exc:  # log and continue with the next session
                row["error"] = f"{type(exc).__name__}: {exc}"
            row["seconds"] = round(time.perf_counter() - start, 1)
            rows.append(row)
            pd.DataFrame(rows).to_csv(OUT_DIR / "download_log.csv", index=False)
            print(f"{year} R{row['round']:02d} {row['location']:20s} laps {row['laps']:4d} kept {row['kept_laps']:3d} "
                  f"with data {row['kept_laps_with_data']:3d}  {row['seconds']:6.1f} s  {row['error']}", flush=True)
    table = pd.DataFrame(rows)
    print(f"\n{len(table)} sessions, {int(table['kept_laps'].sum())} kept laps, "
          f"{int(table['kept_laps_with_data'].sum())} with data, {int((table['error'] != '').sum())} errors")


if __name__ == "__main__":
    main()

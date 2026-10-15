"""Download (cache) every qualifying session of 2023 and 2024, for Phase 6.

Why a separate script: downloading ~46 sessions takes 15-30 minutes and
~2 GB of disk. Doing it once, up front, means every later script reads from
the cache in a second or two per session.

2025 is NOT downloaded: it is the frozen final test set, and load_session()
refuses it anyway unless FINAL_TEST=1 is set.

Only the main qualifying session ("Q") is downloaded, not sprint qualifying
(decision logged in docs/decisions.md): a sprint qualifying lap uses a
different tyre rule, and one kind of session keeps the comparison clean.

Run from the repo root (safe to re-run: cached sessions load in seconds):
    .venv\\Scripts\\python.exe experiments\\07_download_qualifying.py
Output:
    results/07_download/download_log.csv  (one row per session: ok or the error)
"""

import logging
import time
from pathlib import Path

import fastf1
import pandas as pd

from apextrace.data_loading import DEFAULT_CACHE_DIR, load_session

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "results" / "07_download"
YEARS = [2023, 2024]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # FastF1 prints a lot of INFO lines while downloading; keep only warnings
    logging.getLogger("fastf1").setLevel(logging.WARNING)
    DEFAULT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(DEFAULT_CACHE_DIR))

    rows = []
    for year in YEARS:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
        for _, event in schedule.iterrows():
            round_number = int(event["RoundNumber"])
            name = event["EventName"]
            start = time.perf_counter()
            try:
                session = load_session(year, round_number, "Q")
                status = "ok"
                drivers = len(session.drivers)
                laps = len(session.laps)
                error = ""
            except Exception as exc:  # log and carry on with the next session
                status = "failed"
                drivers = 0
                laps = 0
                error = f"{type(exc).__name__}: {exc}"
            seconds = time.perf_counter() - start
            rows.append({"Year": year, "Round": round_number, "Event": name,
                         "Status": status, "Drivers": drivers, "Laps": laps,
                         "Seconds": round(seconds, 1), "Error": error})
            print(f"{year} R{round_number:02d} {name:35s} {status:6s} "
                  f"{drivers:2d} drivers {laps:4d} laps {seconds:6.1f} s {error}", flush=True)
            # write after every session, so a crash keeps the log so far
            pd.DataFrame(rows).to_csv(OUT_DIR / "download_log.csv", index=False)

    table = pd.DataFrame(rows)
    print(f"\n{(table['Status'] == 'ok').sum()} of {len(table)} sessions ok")


if __name__ == "__main__":
    main()

# Where the data and the facts come from

One page that answers "where did this come from?" for everything in ApexTrace: the
telemetry, how it was turned into the dataset, and every outside fact (papers,
statistics methods, the 2026 rules). Numbers are copied from the files named
next to them, so they can be checked.

## Quick answers

| Question | Answer |
|---|---|
| Where does the telemetry come from? | Formula 1's live timing feed, read through two free, **unofficial** tools: **FastF1** (pilot) and **OpenF1** (everything after). Neither is associated with Formula 1. |
| Which sessions? | Main **qualifying** sessions of 2023, 2024 and 2025 (plus 2024 Abu Dhabi FP2 in the pilot). No races, no sprint qualifying. |
| What is measured? | Per car, about 3.7 times a second: speed (km/h), throttle (%), brake (on/off), gear, rpm, and X/Y/Z position. |
| Where is it on this computer? | `cache/` (raw downloads) and `results/09_dataset/`, `results/final/` (built files). |
| Is the raw data on GitHub? | No. Raw downloads and raw-sample files are gitignored; only small derived results (CSV/JSON, figures) are committed. |
| Can it be rebuilt? | Yes, with the scripts below (section 4), as long as OpenF1 stays online. |

---

## 1. The two data tools

| Tool | What it is | Used for | Status |
|---|---|---|---|
| **FastF1** 3.8.3 (Python library, <https://github.com/theOehrly/Fast-F1>) | Reads the F1 live-timing archive (`livetiming.formula1.com`) and adds helpers (lap table, distance) | Phases 0–5: the 2024 Abu Dhabi pilot | Since 2026-10-16 the archive answers **401 Unauthorized**; only sessions cached before that still load (`docs/decisions.md`, 2026-10-16) |
| **OpenF1** (free web API, <https://api.openf1.org/v1/>, docs <https://openf1.org/docs>) | Serves the same timing feed as JSON | Phase 6 on: 2023–2025, the final test, the web app | Checked to be the same data as FastF1 on 2024 Abu Dhabi: identical kept laps for 20 of 20 drivers, features within 0.23 m (`experiments/07_openf1_validation.py`, `results/07_openf1_validation/`) |

### What is taken from OpenF1

| Endpoint | Fields used | What for |
|---|---|---|
| `sessions` | session key, date, location (qualifying only) | the list of sessions per season |
| `drivers` | driver number, three-letter code, team name | labels (`headshot_url` is never exported) |
| `laps` | lap start time, lap duration, pit-out flag | the lap table |
| `stints` | stint, compound, tyre age | lap selection (a slow lap is judged against its own stint) |
| `race_control` | deleted lap times, flags | lap selection (deleted or flagged laps are dropped) |
| `car_data` | speed, throttle, brake, gear, rpm | every corner feature |
| `location` | X, Y, Z position | the track coordinate (alignment) |

The code is `src/apextrace/openf1.py`. Every answer is stored once in
`cache/openf1/` as a gzip-compressed JSON file, so nothing is downloaded twice.
OpenF1 allows about 30 requests a minute, so the download asks for each driver's car
data and position once per session, covering all their kept laps, instead of once per
lap (`docs/decisions.md`, 2026-10-17).

---

## 2. What was downloaded, when, and where it is

| Data | Tool | Sessions | Downloaded | Script | Stored (local only) |
|---|---|---|---|---|---|
| Pilot: 2024 Abu Dhabi qualifying + FP2 | FastF1 | 2 | 2026-10-14/15 | `00_hello_lap.py`, `01_data_pilot.py` | `cache/2024/`, `cache/fastf1_http_cache.sqlite` |
| Development: all 2023 and 2024 qualifying sessions | OpenF1 | 47 listed, 46 with data (2023 Imola: the weekend was cancelled) | 2026-10-17 | `08_download_openf1.py` | `cache/openf1/` |
| Final test: all 2025 qualifying sessions | OpenF1 | 24 listed, 23 with data (Baku has no lap rows) | 2026-10-18, once | `14_final_2025.py` | `cache/openf1/` |
| 2026 | — | **not downloaded**: held out by the code (switch `FINAL_TEST_2026`) until its test plan is committed | — | — | — |

Sizes on 2026-10-31: `cache/openf1/` 226 MB, `cache/2024/` 98 MB.

Laps (from `results/08_download/download_log.csv` and `results/final/sessions_2025.csv`):

| Season | Laps in the sessions | Laps kept by the lap-selection rules |
|---|---|---|
| 2023 | 7,423 | 2,234 |
| 2024 | 7,598 | 2,266 |
| 2025 | 7,129 | 2,092 |

A lap is kept if it has a lap time, is not an out lap or in lap, was not deleted, ran
under green flag only, and is within 107 % of the best lap of its own stint (one set of
tyres). The full rules and why are in `docs/decisions.md` (2026-10-15); the code is
`select_laps` in `src/apextrace/data_loading.py`.

---

## 3. From download to results

```
OpenF1 API ──> cache/openf1/*.json.gz              raw answers, one file per request
          ──> experiments/09_build_dataset.py
                ├─ results/09_dataset/raw_samples.parquet   every measured sample of every kept lap (local only)
                └─ results/09_dataset/dataset.csv.gz        one row per (session, driver, lap, corner)
          ──> apextrace.dataset.clean (rules fixed in experiments/10_eda.py)
          ──> experiments/11–13  H1 repeatability, H3 identification, H4 development (2023–2024)
          ──> experiments/14_final_2025.py ──> results/final/   the one-time 2025 test (frozen)
```

| Step | 2023–2024 | 2025 | File |
|---|---|---|---|
| Rows (driver, lap, corner) | 30,441 | | `results/09_dataset/summary.json` |
| Usable (car data present, no feed gap in the corner window) | 24,496 | 9,272 | `results/10_eda/summary.json`, `results/final/summary.json` |
| Dropped: not dry | 2,997 | 400 | same |
| **Clean rows used** | **21,493** | **8,871** | same |

What the data can and can't support (sampling, gaps, resolution, why position can't
show racing lines) is in `docs/data_report.md`.

---

## 4. Rebuilding the data

```powershell
.venv\Scripts\python.exe experiments\08_download_openf1.py   # 2023-2024 from OpenF1, ~1.5 h the first time
.venv\Scripts\python.exe experiments\09_build_dataset.py     # dataset + raw samples
.venv\Scripts\python.exe experiments\10_eda.py               # cleaning rules + EDA figures
```

The 2025 data is downloaded only by `14_final_2025.py`, which has already been run
and must not be run again (its results are frozen). The tests never download
anything; they use synthetic signals.

---

## 5. Every other source

| What | Where it is listed |
|---|---|
| Research papers (driver identification, F1 driver vs car, sim racing, reviews) | `docs/related_work.md`: search log, what each paper did, how ApexTrace differs |
| All references used in the report, including statistics methods (ICC: Shrout & Fleiss 1979; bootstrap: Efron & Tibshirani 1993; multiple testing: Holm 1979, Benjamini & Hochberg 1995; effect size: Hedges 1981; preregistration: Nosek et al. 2018) | `docs/report.md`, section "References" |
| The 2026 car rules (FIA Sections B and C, the FIA's 2024 announcement) | `docs/regulations_2026.md`, section "Sources" |
| Software versions | `requirements.txt` (pinned); the web app bundles D3 7.9.0 (ISC licence) and the Barlow typeface (SIL Open Font License) |

## Notices

ApexTrace is an independent, non-commercial student project. It is unofficial and
is not associated in any way with the Formula 1 companies. FastF1 and OpenF1 are
unofficial as well. Raw data stay on the local computer; the repository holds only
small derived results and charts drawn from them.

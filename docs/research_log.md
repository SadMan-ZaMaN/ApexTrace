# Research log

Newest entry at the bottom. Each entry: what I tried, what happened (numbers,
not impressions), and what's next. Negative results count as results. If I
stop in the middle of a step, write "stopped at … / next: …".

---

## 2026-10-14 — Phase 0: setup

**Did**
- Split `CLAUDE.md` into a short working file (242 lines) plus
  `docs/PROJECT_CONTEXT.md` (the full plan, original section numbers kept).
  Deleted the chat reply that had been pasted at the end of the file by accident.
- Recorded the answers to the open questions (PROJECT_CONTEXT §19): solo; time;
  repo ApexTrace with package `apextrace`; 2025 frozen as the final test set;
  no faculty member yet.
- Created `docs/decisions.md`, this log, and `docs/related_work.md` (seeded
  from §12.2).
- Environment: `.venv` with Python 3.13.2, `requirements.txt` (pinned with
  `pip freeze`), `pyproject.toml`, `.gitignore`, folder structure, and
  `tests/test_smoke.py`.

**Versions:** Python 3.13.2 · FastF1 3.8.3 · NumPy 2.5.4 · SciPy 1.18.1 ·
pandas 2.3.3 · Matplotlib 3.11.2 · pytest 9.1.1.

**Result**
- FastF1 3.8.3 installs and imports on Python 3.13, so the fallback to 3.12 isn't needed.
- Smoke test: fails with `ModuleNotFoundError: No module named 'apextrace'`
  before `pip install -e .` (good: it catches a missing install), and passes after it.
- No F1 data has been downloaded yet.

**Next**
- `experiments/00_hello_lap.py`: load 2024 Abu Dhabi Q, plot Norris's fastest
  lap, speed vs distance → `results/figures/00_hello_lap.png`. Check the
  FastF1 method names (`pick_drivers`, `pick_fastest`, `get_car_data`,
  `add_distance`) against 3.8.3.
- Phase 1: `src/apextrace/data_loading.py` (`load_session`, `select_laps`, which
  returns the kept laps plus a table of dropped laps with reasons), then the
  NOR/PIA lap table for Q and FP2 (§7 checklist items 6 and 8).

---

## 2026-10-15 — Phase 0 finished, Phase 1 started (checks 6 and 8)

**Did**
- `experiments/00_hello_lap.py` → `results/figures/00_hello_lap.png`:
  Norris's pole lap, speed vs distance, one dot per car-data sample.
- `src/apextrace/data_loading.py`: `load_session()` (cache, plus a guard
  that refuses 2025) and `select_laps()` (kept laps + dropped laps with reasons).
- `src/apextrace/plots.py`: shared figure style, fixed colours per driver.
- `tests/test_data_loading.py`: 6 tests on a hand-made lap table. Each one was
  checked to fail when the code is deliberately broken (5 deliberate bugs,
  all caught).
- `experiments/01_data_pilot.py` → `results/01_data_pilot/lap_table.csv`
  (checks 6 and 8).

**Results (all numbers printed by the scripts)**
- Hello lap: 1:22.595 (matches the official pole time). 320 car-data samples
  in 82.595 s = 3.87 samples/s on average. Speed 68–324 km/h. Distance from
  integrating speed: 5,211 m. ⚠️ The official Yas Marina lap length is
  ~5.28 km (from memory, not checked), so integration may come out ~70 m
  short. Measure properly in check 5.
- First download of a session: ~19 s and 45.5 MB of cache (a first number for check 9).
- FastF1's own docs (`Session.load`) warn: *"Expect an error of around ±10m
  when overlapping telemetry data of different laps."* That is the size of the
  alignment problem for Phase 3.
- **Check 6, usable laps:**
  - Q: **4 push laps per driver** (one in Q1, one in Q2, two in Q3), all on
    soft tyres. Piastri's best 82.804 − Norris's 82.595 = 0.209 s, which
    matches the official gap.
  - FP2: NOR keeps 10 of 25 laps and PIA 12 of 28. Both have a **7-lap
    medium long run** (NOR laps 15–21, tyre age 10–16; PIA laps 18–24,
    tyre age 12–18). Those are matched runs for the FP2 repeatability check.
  - `timing check failed` (FastF1 `IsAccurate`) never drops a lap on its own:
    it only ever appears together with out lap, in lap or no lap time.
- **Check 8, FastF1 helpers:** all of these exist in 3.8.3: `pick_wo_box`,
  `pick_not_deleted`, `pick_track_status`, `pick_accurate`, `pick_quicklaps`
  (plus `split_qualifying_sessions`). In Q, chaining them keeps the same laps
  as `select_laps()`. In FP2 they differ, as expected (see the problem below).

**Problem found and fixed: the first slow-lap rule was biased**
The first version dropped laps slower than 107 % of the driver's *session*
best. In FP2 that best lap was on soft tyres, and the medium long run sits at
106–109 % of it. Result: 6 of Norris's 7 long-run laps were dropped
(threshold 83.517 × 1.07 = 89.36 s) but only 2 of Piastri's (83.751 × 1.07 =
89.61 s). The same kind of lap was treated differently just because one
driver's soft lap was 0.23 s quicker. Fix: compare each lap with the best lap
of its own stint, plus a rule that drops stints that were never timed runs
(decisions.md, 2026-10-15). Lesson: a threshold measured against a single
extreme value (the best lap) carries that value's noise and its confounders.

**Next (Phase 1, checks 1–5, 7, 9)**
- `src/apextrace/quality.py`: sample-interval statistics, a gap finder, and a
  quantisation check.
- Extend `01_data_pilot.py`: timing histogram (check 1), channel resolution (2),
  brake values (3), position data rate and noise (4), distance drift on the 4 Q
  laps per driver (5), `get_circuit_info()` corners (7), cache size and load time (9).

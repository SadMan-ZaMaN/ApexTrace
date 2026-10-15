# 2. Setup and tools (Phase 0), and `data_loading.py`

## The environment

| Thing | What it is | Why we use it |
|---|---|---|
| `.venv/` | A *virtual environment*: a private copy of Python and its libraries for this project only | Different projects need different library versions; a venv keeps them apart |
| `requirements.txt` | Every library with its **exact** version (`fastf1==3.8.3`), made with `pip freeze` | Anyone can rebuild the identical environment: `pip install -r requirements.txt` |
| `pyproject.toml` | Says "this folder is a Python package called `apextrace`" and lists the libraries it needs (no exact versions) | Two jobs: pyproject = *what* the package needs; requirements = *exactly which versions* we used |
| `pip install -e .` | Installs our package in "editable" mode: Python finds `src/apextrace/` from anywhere, and edits apply immediately | So `import apextrace` works in `experiments/`, `tests/`, notebooks, without path hacks |
| `src/` layout | The package lives in `src/apextrace/`, not at the top | Tests can only import the installed package, never a stray copy |
| pytest | Runs every function named `test_...` in `tests/` | Automatic proof that the code still does what it should |

Rebuild from scratch (PowerShell):
```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
python -m pytest
```

## The testing rule: a test must fail on the broken version

A test that passes on broken code is useless. So for each important test we
broke the code on purpose (removed the 2025 guard, used the old slow-lap
rule, ...), checked the test **failed**, then restored the code. This is
called *mutation testing* (done by hand here). If you change a function,
re-run `python -m pytest`.

## Git workflow (you commit, Claude never does)

Review the changed files in GitHub Desktop → write a message in the
imperative ("Add zero-phase filter and group-delay demo") → commit → push.
Files that are **not** committed: `.venv/`, `cache/` (FastF1 data, ~2 GB),
`CLAUDE.md` and `docs/PROJECT_CONTEXT.md` (local notes), anything in
`private/`, and `roadmap.md` (hidden through `.git/info/exclude`).

## FastF1 in five lines

```python
import fastf1
fastf1.Cache.enable_cache("cache")                 # downloads are kept in cache/
session = fastf1.get_session(2024, "Abu Dhabi", "Q")
session.load()                                      # laps, car data, positions, messages
lap = session.laps.pick_drivers("NOR").pick_fastest()
car = lap.get_car_data()                            # Speed, Throttle, Brake, nGear, RPM, DRS, times
```

- `session.laps` is a table (pandas DataFrame) with one row per lap:
  `LapTime`, `Compound`, `TyreLife`, `Stint`, `PitInTime`, `PitOutTime`,
  `Deleted`, `TrackStatus`, `IsAccurate`, ...
- Times are *timedeltas* (`0 days 00:01:22.595`); `.total_seconds()` gives a float.
- `get_car_data()` = the raw car channels for that lap; `get_pos_data()` =
  raw X/Y/Z positions (in **decimetres**). Never merge them before quality
  checks: merging interpolates.

## pandas you need

`df["Speed"]` (a column), `df.loc[rows]`, `df[df["Kept"]]` (filter rows),
`df.groupby(["Session", "Driver"])` (split into groups), `df.iterrows()`
(loop over rows: slow but explainable), `pd.concat([...])` (stack tables),
`df.to_csv(path)`.

## Code walkthrough: `src/apextrace/data_loading.py`

### `load_session(year, event, session_name)`
1. **The 2025 guard.** If `year == 2025` and the environment variable
   `FINAL_TEST` isn't `"1"`, it raises `PermissionError`. 2025 is the frozen
   test set: looking at it during development would tune the method to it
   by accident.
2. Creates `cache/` and turns on FastF1's cache.
3. `session.load()` loads *everything*: FastF1 cross-checks its sources, and
   the race-control messages say which laps were deleted.

### `lap_problems(lap)` → list of reasons
Each rule is checked on every lap, so a lap can have several reasons:
no lap time · out lap · in lap · deleted (track limits) · not green (track
status other than `'1'`; FastF1 writes every status seen during the lap, e.g.
`'12'` = green then yellow) · timing check failed (`IsAccurate`).

### `select_laps(laps)` → (kept, dropped)
Two passes:
1. The clean laps (no problems).
2. Pace rules, for clean laps only:
   - **"not a timed run"**: the stint's best lap is > 115 % of the driver's
     best (e.g. a practice-start run at the end of FP2);
   - **"slow lap"**: > 107 % of the best lap *of its own stint* (cool-down laps).

**The bug we found (bug history in CLAUDE.md):** the first version compared
laps with the driver's best lap of the *session*. In FP2 that best lap was on
soft tyres, and the long run on mediums is 6–9 % slower, so the 107 % rule cut
6 of Norris's 7 long-run laps but only 2 of Piastri's, just because his soft
lap was 0.23 s quicker. A threshold measured against a single extreme value
(the best lap) carries that value's noise and its confounders.

*Confounder* = something other than the thing you study that changes the
result (here: which tyre the best lap was on).

### Tests: `tests/test_data_loading.py`
A hand-made table of fake laps, one for each rule, with realistic times. The
test knows which laps must be kept and exactly which reason each other lap
must get. `test_load_session_refuses_the_frozen_2025_season` replaces
FastF1's download function with one that fails the test, so a missing guard
can never trigger a real download.

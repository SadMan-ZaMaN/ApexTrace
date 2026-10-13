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

# Decisions

One entry per decision: the date, what we chose, and why. Add new entries at
the bottom. Decisions made before this repo existed (the project direction,
the pilot, the corrections to the first plan) are in PROJECT_CONTEXT §4.

---

## 2026-10-14 — Working solo
Sadman works on ApexTrace alone. Consequence: no `CONTRACTS.md` and no module
split between people. If a faculty member or collaborator joins later, agree
on authorship early (PROJECT_CONTEXT §12.8).

## 2026-10-14 — Names: repo ApexTrace, package `apextrace`
The Python package is `apextrace` (the original plan said `f1sig`).
**Why:** code that matches the repo name is easier to find and explain.

## 2026-10-14 — 2025 season = frozen final test set
Confirmed. Develop everything on 2023–2024. Write `docs/preregistration.md`
and commit it **before** any 2025 session is loaded. Then run the final
H3/H4 evaluation on 2025 once.
**Why:** if we look at the test data while developing, we will (without
meaning to) tune the method to it, and the final numbers will look better
than they really are.
**Open issue (decide in Phase 6):** every planned team changer (Hamilton,
Sainz, Ocon, Hülkenberg, Lawson ↔ Tsunoda) changed teams *for 2025*, so the
H4 method can't be developed on them. Options: develop H4 on a "same driver,
same car, new year" check (2023 → 2024), or add the 2022 season to get
earlier team changers.

## 2026-10-14 — Python 3.13 + FastF1 3.8.3
FastF1 3.8.3 installed and imported without problems on Python 3.13.2, so we
stay on 3.13 (no need for 3.12). Exact versions of everything are pinned in
`requirements.txt` (made with `pip freeze`).

## 2026-10-14 — Package layout: `src/` + `pyproject.toml` + editable install
Code lives in `src/apextrace/`, installed with `pip install -e .`.
**Why:** `import apextrace` then works from `experiments/`, `tests/` and
`notebooks/` without editing `sys.path`, and code edits take effect without
reinstalling. The `src/` folder means tests always use the installed
package, never a stray copy. `pyproject.toml` lists the libraries we need;
`requirements.txt` records the exact versions we used.

## 2026-10-14 — CLAUDE.md split
`CLAUDE.md` (loaded in every Claude session) was cut from ~950 to under 250
lines. The long reference parts moved word for word to
`docs/PROJECT_CONTEXT.md`, which **keeps the original section numbers**, so
"§9.7" still means the same thing everywhere. The chat reply that had been
pasted by accident at the end of the file was deleted.

## 2026-10-15 — Lap selection rules (`select_laps`)
A lap is kept only if it has a lap time, is not an out lap or in lap, was not
deleted, ran under green flag only (track status `1`), and passed FastF1's
timing check (`IsAccurate`). Then two pace rules:
- **Slow lap:** slower than **107 % of the best clean lap of its own stint**
  (one set of tyres). Removes cool-down laps.
- **Not a timed run:** the stint's best lap is slower than **115 % of the
  driver's best clean lap** of the session. Removes runs that were never
  timed, such as practice starts at the end of FP2.

Every dropped lap is logged with its reason(s).
**Why per stint, not per session:** with the session best as reference, the
107 % rule cut 6 of Norris's 7 FP2 long-run laps but only 2 of Piastri's,
only because his soft-tyre lap was quicker (details in the research log of
2026-10-15). **Why 115 %:** in 2024 Abu Dhabi FP2, long runs were 106–109 %
of the driver's best and end-of-session runs 130–141 %; 115 % sits in that gap.
Re-check this gap when more sessions are loaded (Phase 6).
**Consequence:** we don't use FastF1's `pick_quicklaps()`, which compares
with the session best. In qualifying it keeps the same laps as our rules.

## 2026-10-15 — 2025 guard in code
`load_session()` refuses any 2025 session unless the environment variable
`FINAL_TEST=1` is set. It was added now rather than in Phase 6, because one
accidental look at 2025 can't be undone.

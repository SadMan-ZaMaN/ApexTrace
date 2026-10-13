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

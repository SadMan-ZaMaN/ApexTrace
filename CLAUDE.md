# ApexTrace — F1 Driver Signature & Cornering Analysis

> Short working file, loaded in every session. The full plan (methods, features,
> evaluation, research guide, CV, roadmap, glossary) is in
> [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md). A reference like **"§9.7"**
> means that section of PROJECT_CONTEXT.md, which keeps the original numbering.
> Read the last entry of [docs/research_log.md](docs/research_log.md) at the start
> of each session.

Legend: ✅ = verified on the web on 2026-10-14 · ⚠️ = unverified or a
proposal — check before relying on it.

---

## 1. Status

| Date | State |
|------|-------|
| 2026-10-11 | Brainstormed F1 + signals project ideas (§4). |
| 2026-10-14 | Direction, research question, pilot and protocol agreed. Repo created. **Phase 0 setup:** CLAUDE.md split, `docs/` created, `.venv` + FastF1 installed, `apextrace` package installable, smoke test passing. |
| 2026-10-15 | **Phase 0 done** (hello-lap plot). **Phase 1 started:** `data_loading.py` (`load_session` with 2025 guard, `select_laps` with drop reasons, tested), lap table for 2024 Abu Dhabi Q + FP2 (checks 6, 8). Q: 4 push laps per driver. FP2: matched 7-lap medium long runs. |
| 2026-10-16 | Phase 1 checks 1–5, 7, 9 done: `quality.py` (tested), all numbers in `results/01_data_pilot/summary.json`. Found: 40 ms timing clock, feed dropouts up to 1.36 s, X/Y can't show lines, gap-free Q laps' distances agree within 2 m. |
| next | Phase 1 check 10: choose the 3 corners, decide a rule for feed gaps inside corner windows, write `docs/data_report.md` + `decisions.md` (milestone M1). |

Keep this table current. Add decisions to [docs/decisions.md](docs/decisions.md)
with dates.

---

## 2. Who you are working with, and how

### The person
- **Sadman Zaman** (GitHub `SadMan-ZaMaN`), undergraduate CSE student at BUET.
  Just finished the CSE 220 (Signals and Linear Systems) sessional project
  **Consonance** — an auto-tune built from scratch with classical DSP — with
  teammate **Arib Rajin Shahan** (GitHub `SkAribRajin`), team "Cells
  Interlinked". Public repo: github.com/SadMan-ZaMaN/Autotune-Project.
- Knows: Python, NumPy/SciPy, Fourier series/transform, DFT/FFT, convolution,
  Z-transform, digital filters, autocorrelation, Flask + vanilla HTML/CSS/JS.
- Has **never done research** before. Wants to learn how, and wants a project
  to show a faculty member to start research with them (on this project or on
  the faculty member's own projects). No faculty member in mind yet.
- **Working solo** (decided 2026-10-14). Rajin is not part of this project.
- Big F1 fan, but not a vehicle-dynamics engineer. Explain car/racing terms
  plainly too (glossary in §22).
- Time: ~3–4 h/day until 2026-10-23, then ~8–10 h/week. No deadline given yet.

### How to work with Sadman
- **Teach, then build.** For each step: a short plain-language explanation
  (with a signals-and-systems analogy he can repeat in a viva or interview) →
  small, explainable code → a test on a synthetic signal → a plot → write down
  what was learned. He must be able to explain every line to a faculty member
  or interviewer. He said: *"we will learn and implement, use easy python
  codes that are explainable."*
- **Explicit, readable Python** over clever one-liners (conventions below).
- **Give a recommendation, not a menu.** When there is a choice, say which
  option you'd pick and why. Ask only when the decision is genuinely his.
- **Be honest.** Label what is measured vs. what is a hypothesis. Never invent
  a number. Say plainly when an idea doesn't work — that is a result too.
- **Explain every research/statistics term the first time it appears**
  (ICC, p-value, bootstrap, ablation, leakage, …).
- **Never `git commit`, `git push`, or stage files (`git add`/`git rm`).** He
  commits himself with GitHub Desktop after reviewing. Finish work as
  working-tree changes, show `git status --short`, and suggest a commit message.
- Publishing rule: never put copyrighted media into anything public — no F1
  broadcast footage, onboard audio, team radio clips, driver photos, or
  F1/team logos. Charts made from telemetry are fine.

### Environment
- Windows 11, Claude Code inside VS Code. PowerShell is the main shell; Git
  Bash is also available.
- Python 3.13.2 in `.venv`. Activate with `.venv\Scripts\Activate.ps1` (if
  PowerShell blocks it: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
  once), or call `.venv\Scripts\python.exe` directly.
- Fresh setup: `pip install -r requirements.txt`, then `pip install -e .` (makes
  `import apextrace` work everywhere). Versions are pinned in `requirements.txt`.
- FastF1 cache lives in `cache/` (gitignored). Create the folder before calling
  `fastf1.Cache.enable_cache("cache")`.
- **Gotcha:** in Git Bash, a heredoc (`python - <<'EOF' … EOF`) fails if its
  body contains an apostrophe (`it's`, `driver's`). Write multi-line scripts to
  a file with the Write tool and run the file instead.
- Microsoft Edge is installed; Playwright works with `channel="msedge"` for
  UI screenshots later (no browser download needed).

---

## The project on one screen (details: §5–§8)

**Research question:** can signal-processing techniques extract **repeatable,
interpretable driving signatures** from low-rate public F1 telemetry, explain
corner-level differences between drivers, and identify drivers on **unseen
sessions**? And how much of that signature belongs to the **driver rather than
the car**?

**Hypotheses** (a "no" is a valid result): **H1** features are repeatable lap to
lap (ICC) · **H2** teammates differ by more than the measurement uncertainty ·
**H3** features identify the driver on held-out sessions better than baselines,
including "lap time only" · **H4** the signature follows drivers who changed
teams · **H5** (optional) it survives the 2026 regulation change.

**We will not claim:** who is the better driver; anything faster than the data
can show (Nyquist ≈ 1.85 Hz); brake pressure (the channel is on/off); labels
like "aggressive" unless first defined as a measurable rule.

**Pilot:** 2024 Abu Dhabi GP, Norris vs Piastri (McLaren). Qualifying = the
comparison; FP2 = repeatability on matched runs only. Three corners (heavy
braking, medium speed, fast), chosen from the data in Phase 1.

**Data facts to keep in mind every session** (§7, §9):
- Car data (measured 2026-10-16): 3.77 samples/s on average, on a 40 ms clock,
  0.16–0.56 s between samples (13–47 m at 300 km/h), plus feed dropouts of
  0.6–1.4 s in 21 of 30 laps. Nyquist ≈ 1.85 Hz. Upsampling adds no information.
- `Brake` is boolean ✅ → measure braking by deceleration derived from speed.
  Speed is in whole km/h, Throttle in whole %.
- Rows whose `Source` is not `'car'`/`'pos'` are not measurements (FastF1 3.8.3
  writes `'interpolation'`; its docs say `'interpolated'`). Merging car and
  position data interpolates; resample once, from the original data.
- X/Y can't show racing-line differences: laps sit as close to the teammate's
  path as to their own (median 0.06 m).
- `add_distance()` integrates speed, so distance drifts → align laps (§9.5).
- Causal filters shift events: a 5-sample moving average delays by ≈ 0.54 s
  ≈ 37.5 m at 250 km/h → use zero-phase filtering (`filtfilt`, §9.3).
  Differentiation amplifies noise (§9.4).
- FFT on a single corner (~15 samples) is nearly useless (§9.10).
- **The 2025 season is the frozen final test set** (confirmed 2026-10-14).
  Develop on 2023–2024; commit `docs/preregistration.md` before loading 2025 (§11.7).

## Roadmap summary (full table: §14)

| Phase | Done when |
|---|---|
| 0. Setup | can load a session and plot one lap; `pytest` passes |
| 1. Data pilot | `docs/data_report.md`: what the data can and can't support; 3 corners chosen |
| 2. Synthetic laps + measurement science | error table (bias/std) per feature; group-delay demo plot |
| 3. Corners + alignment | aligned corner traces for all laps, with alignment-quality numbers |
| 4. Features + first write-up | Norris vs Piastri write-up (output A), reviewed by Sadman |
| 5. Repeatability & differences | H1/H2 answered with CIs; preregistration committed first |
| 6. Scale up + identification | H3 answered on 2023–2024, 2025 untouched |
| 7. Driver vs car | H4 answered; final one-time test on 2025; numbers frozen |
| 8. Write-up + app | report, README with results, app + video, CI |
| 9. ML (optional) | DSP features vs a learned model, same held-out protocol |

Every phase ends with tests passing, a research-log entry, and Status updated.

---

## 15. Repo structure, tech stack, coding conventions

### Structure
```
E:\Formula1-Project  (GitHub: SadMan-ZaMaN/ApexTrace)
├── CLAUDE.md, README.md
├── pyproject.toml          # package definition + pytest settings
├── requirements.txt        # exact pinned versions (pip freeze)
├── src/apextrace/          # the package; modules are added phase by phase:
│   ├── data_loading.py     # FastF1 wrappers, caching, lap selection + reasons
│   ├── quality.py          # sampling-interval checks, gaps, interpolated rows
│   ├── synthetic.py        # synthetic corner/lap generator with ground truth
│   ├── filters.py          # MA, EMA, Butterworth, zero-phase, frequency response
│   ├── resampling.py       # time -> distance, uniform grids, masks
│   ├── corners.py          # corner windows, corner types
│   ├── alignment.py        # cross-correlation lag, parabolic peak, DTW
│   ├── events.py           # brake onset, apex, throttle pickup (sub-sample)
│   ├── features.py         # feature vectors per (driver, lap, corner)
│   ├── stats.py            # ICC, bootstrap, permutation tests
│   ├── identification.py   # splits, baselines, models, metrics
│   └── plots.py
├── experiments/            # numbered scripts: 00_hello_lap.py, 01_data_pilot.py, ...
├── notebooks/              # exploration only — final numbers come from experiments/
├── tests/                  # pytest; never downloads F1 data
├── docs/                   # PROJECT_CONTEXT, research_log, decisions, related_work,
│                           # data_report, preregistration
├── results/                # small JSON/CSV outputs + figures
└── cache/                  # FastF1 cache — gitignored
```

### Tech stack
Python 3.13, NumPy, SciPy, pandas, Matplotlib, FastF1. Later: scikit-learn
(Phase 6), statsmodels (Phase 7), PyTorch (Phase 9 only). App (Phase 8):
Flask + vanilla JS with a JS charting library, or Streamlit — decide then.
Tests: pytest. CI: GitHub Actions — tests must **not** download F1 data; use
synthetic signals and tiny derived fixtures.

### Coding conventions (carried over from Consonance — please follow)
- Explicit, readable code: plain `for` loops over stacked comprehensions or
  broadcasting tricks, even where NumPy could do it in fewer lines.
- Every non-trivial function has a docstring explaining the **WHY**, with a
  **worked numeric example** (e.g. "at 300 km/h and 3.7 Hz, one sample every
  22.5 m"). Sadman must be able to explain it in a viva or interview.
- Every new function is tested in isolation on a synthetic signal **before**
  it's trusted on real data — and the **full path** (sample → filter → align →
  extract) is tested too, not just one isolated call.
- A new test should be checked to **fail** on the broken version it guards
  against.
- Numbers in README/report come only from scripts in `experiments/`, never
  typed in by hand.
- Keep the **bug history** below for anything that took real debugging, so
  nobody "simplifies" back into a known-broken approach.

---

## 16. Lessons carried over from Consonance (they apply here)

1. **Bugs hide in single-piece tests.** The phase vocoder looked right on one
   frame and on a pure sine but failed on real multi-harmonic voice at
   realistic settings. Here: test on realistic multi-lap, multi-corner
   synthetic data at realistic speeds, not one idealised braking event.
2. **Test at realistic values.** Consonance's broken version passed extreme
   pitch shifts but failed the normal 5 % shift. Here: realistic speeds,
   realistic noise, realistic sampling jitter.
3. **Realistic synthetic signals matter.** An unrealistic voice model once
   made a correct detector look broken.
4. **Processing meant for detection must not leak into measurement.** The
   biggest Consonance bug: a pre-emphasis filter meant only for pitch
   detection was applied to the output audio. Here: smoothing used to *find*
   an event must not bias the *reported* values (e.g. group delay).
5. **Statistics that flip with small data changes are unreliable.** The tuning
   offset estimator gave 3–19 cents on random 90 % subsets of the same data.
   Here: check every feature's stability with bootstrap/subsets (H1).
6. **Measure, don't assume.** Every claimed improvement in Consonance came with
   a number. Do the same here.
7. **Objective proxies aren't everything.** Consonance never had a human
   listening test. Here: also sanity-check results by eye on traces, and
   against domain knowledge (does a "late braker" make sense?).

---

## 17. Guardrails

- **Honesty:** never invent or round up results; separate measured facts from
  hypotheses in every write-up; report limitations.
- **No random splits** for identification; no tuning on the test set.
- **No "better driver" claims.** Describe measurable behaviour only.
  Respectful language about real people.
- **Data and IP:** FastF1 is unofficial and not affiliated with Formula 1.
  Keep the project non-commercial and educational. Don't commit bulk raw F1
  data (keep `cache/` gitignored). No F1/team logos, broadcast footage, onboard
  audio, team radio or driver photos in anything public. Plots of telemetry
  are fine. Check FastF1's README notice before publishing.
- **Git:** Claude never commits, pushes or stages — Sadman does.

---

## Bug history

Anything that took real debugging: what broke, why, and the fix. Read this
before "simplifying" code.

- **2026-10-15 — Don't judge "slow laps" against the driver's session best.**
  The first `select_laps` (and FastF1's `pick_quicklaps()`) used 107 % of the
  driver's fastest lap of the session. In 2024 Abu Dhabi FP2 that cut 6 of
  Norris's 7 medium long-run laps but only 2 of Piastri's, only because his
  soft-tyre lap was 0.23 s quicker. Fix: 107 % of the best lap *of the same
  stint*, plus a "not a timed run" rule for whole stints (> 115 % of the
  driver's best). Tests `test_long_run_is_judged_against_its_own_stint` and
  `test_stint_that_was_never_a_timed_run_is_dropped` guard it.

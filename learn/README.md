# Learn ApexTrace, A to Z

This folder teaches you the whole project: the idea, the research method, the
signal processing, the statistics, and every file of code. It was written
while the project was being built (October 2026), so you can study it after
your exams and then explain any part to a faculty member or an interviewer.

## Reading order

| # | Chapter | What you'll understand | Time |
|---|---|---|---|
| 1 | [01_big_picture.md](01_big_picture.md) | The research question, the hypotheses, the plan, and why this is research and not a dashboard | 30 min |
| 2 | [02_setup_and_tools.md](02_setup_and_tools.md) | venv, `pip install -e .`, pytest, git workflow, FastF1 and pandas basics; `data_loading.py` | 1 h |
| 3 | [03_the_data.md](03_the_data.md) | What the F1 timing feed really is (Phase 1): sampling, gaps, resolution, distance drift; `quality.py` | 1.5 h |
| 4 | [04_measurement_science.md](04_measurement_science.md) | Phase 2: synthetic laps, filters and group delay, the inspection paradox, naive vs refined estimators, Monte Carlo | 3 h |
| 5 | [05_alignment.md](05_alignment.md) | Phase 3: projection onto a path, why X/Y is noisy along the track, the complementary filter, cross-correlation | 1.5 h |
| 6 | [06_features_and_writeup.md](06_features_and_writeup.md) | Phase 4: the 11 features, uncertainty words, the Norris vs Piastri pilot, writing honestly | 1 h |
| 7 | [07_statistics.md](07_statistics.md) | Phase 5: preregistration, permutation tests, bootstrap, effect sizes, multiple comparisons, ICC, power | 2 h |
| 8 | [08_data_sources.md](08_data_sources.md) | Phase 6 part 1: the F1 archive closed (401); proving OpenF1 is the same data; rebuilding the lap table; regression checks | 1 h |
| 9 | [09_multi_season_dataset.md](09_multi_season_dataset.md) | Phase 6 part 2: rate limits, corner detection, braking events, the dataset, classic EDA and cleaning | 1.5 h |
| 10 | [10_repeatability_and_identification.md](10_repeatability_and_identification.md) | Phase 6 part 3: ICC at lap and weekend level, cluster bootstrap, leave-one-session-out identification, baselines, leakage checks, ablation | 2 h |
| 11 | [11_driver_vs_car.md](11_driver_vs_car.md) | Phase 7: season signatures, own vs teammate, sign tests, how a one-time final test is protected | 1 h |
| 12 | [12_final_results.md](12_final_results.md) | The one-time 2025 test: a crash and how it was handled, H3 replicated, H4 not supported, a missed changer, reading a "no" with a control, what the project can claim | 1 h |
| 13 | [13_web_app.md](13_web_app.md) | Phase 8: the Flask + D3 web app, the design rules, D3 basics, the signals lesson behind the lap-gap chart (integration as a low-pass filter, common-mode drift), the Corner lab and the Driver vs car page | 1.5 h |
| 14 | [14_presenting_and_next_steps.md](14_presenting_and_next_steps.md) | The demo-video shot list, a two-minute pitch, the faculty email, CV lines, the update loop, what you are most likely to break, and future work | 45 min |
| — | [viva_questions.md](viva_questions.md) | Practice questions with answers, per chapter | |
| — | [exercises.md](exercises.md) | Hands-on: change a number, predict, run, check | |

## How to study each chapter

1. Read the chapter once, quickly.
2. Open the code files it names, and read them with the chapter beside you.
   Every function has a docstring with the *why* and a worked number.
3. Run the experiment script the chapter names, and look at the figures in
   `results/`.
4. Do one or two exercises from `exercises.md`.
5. Answer the viva questions out loud without looking. Check yourself.

## Running everything (PowerShell, in the project folder)

```powershell
.venv\Scripts\Activate.ps1                       # once per terminal
python -m pytest                                 # all tests (takes ~10 s)
python experiments\00_hello_lap.py               # first plot
python experiments\01_data_pilot.py              # Phase 1 data checks
python experiments\02_group_delay_demo.py        # Phase 2 filter demo
python experiments\03_synthetic_errors.py        # Phase 2 Monte Carlo (~2 min)
```

Every number in the docs comes from one of these scripts. If you change
code, re-run the script and the numbers update.

## Where things are

| Folder | What's in it |
|---|---|
| `src/apextrace/` | The Python package: the reusable code (one module per job) |
| `experiments/` | Numbered scripts that produce every result and figure |
| `tests/` | Automatic checks (pytest), all on synthetic data |
| `results/` | Outputs: CSV, JSON, PNG figures |
| `docs/` | The research record: `research_log.md` (diary), `decisions.md` (every choice and why), `data_report.md`, `related_work.md` |
| `learn/` | This guide |

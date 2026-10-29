# 14. Presenting the project, and working on it alone

> The build is finished (Phases 0–8). This chapter is for what comes next: the demo video,
> talking to a faculty member, your CV, and keeping the project healthy without help.

## 1. The demo video (60–90 seconds)

Record the screen of the running app (`python run.py`, browser full screen, 1440 px wide or more). Windows:
**Win + Alt + R** starts and stops the Xbox Game Bar recorder (or use OBS). No music with lyrics, no F1 footage,
no team radio, no logos: only the app.

| Time | Screen | What you say (or show as a caption) |
|---|---|---|
| 0–8 s | Overview, hero playing | "ApexTrace: can you recognise a Formula 1 driver from public telemetry, sampled under four times a second?" |
| 8–15 s | Scroll to the results board | "Four hypotheses, tested on a season I locked away until the end. Two came out yes or partly, one no." |
| 15–35 s | Lap compare: NOR vs PIA, click C3, hover | "Any two laps on one track coordinate. Zoom into a corner: each dot is a real sample. Piastri brakes earlier here, and the gap curve shows where time moves; the page checks it against the official lap times." |
| 35–50 s | Corner lab, brake onset at C1 | "Every driver, every lap at one braking zone. The bar at the top is how precisely one lap can be measured, so you can see which differences are real." |
| 50–75 s | Driver vs car: H3 chart, then click HAM in the scatter | "Corner features tell teammates apart on unseen weekends. But when Hamilton moved to Ferrari, his 2025 style ended up slightly closer to Leclerc's than to his own Mercedes year, and 3 of 5 drivers who moved went the same way." |
| 75–90 s | Back to the overview | "Measured errors, a preregistered test, and honest negatives. Code and report on GitHub." |

Tips: zoom the browser to 110 % so text is readable in a small video; rehearse once; keep the cursor slow.

## 2. The two-minute pitch (viva, interview, faculty meeting)

1. **Question.** "Can signal processing recover a driver's style from public F1 telemetry, which arrives about
   3.8 times a second with gaps, and is that style the driver's or the car's?"
2. **Measurement first.** "Before any claim, I simulated laps with a known truth. The obvious way to find a
   braking point, the first brake-on sample, is 12.5 m late; my estimator has 4.2 m error. A normal moving
   average shifts events by 25 m, so I never smooth before locating an event."
3. **Method.** "Every lap goes onto one track coordinate with a complementary filter, 1.15 m error. Eleven corner
   features per lap and corner, made relative to the field."
4. **Results.** "Corner features tell teammates apart on unseen weekends: 0.66 balanced accuracy against 0.58 for
   lap time, replicated on a held-out season with a preregistered test. But simple whole-lap statistics do as well,
   and for drivers who changed teams, the style didn't clearly follow them: 2 of 5."
5. **What I'd do next.** "Teammate-relative features to remove the car, more team changes as seasons pass, and a
   learned model under the same protocol."

## 3. Talking to a faculty member

**Who:** BUET faculty in signal processing, machine learning, data science or time series. Read their recent
papers first; ask seniors who have published.

**In the meeting:** open the app's **Method** page first (the feed's 40 ms comb, the filter that moves a braking point by 25 m, the estimator table): it shows the signals work in two minutes. Then a Corner lab chart and Lap compare zoomed into one corner (real samples, real errors).

**Bring (or attach):** `docs/report.md` exported to PDF (VS Code: "Markdown PDF" extension, or print from the
GitHub page), the repo link, and three figures:
- `results/02_group_delay/braking_shift.png`: filters move events (the measurement-science result),
- `results/15_final_exploratory/final_h3_teams.png`: teammate identification on 2025,
- `results/15_final_exploratory/final_h4_distances.png`: the driver-vs-car test.

**Email draft** (short; one clear ask):

> Subject: Request for 15 minutes of advice: signal processing on Formula 1 telemetry
>
> Dear Sir/Madam,
>
> I am Sadman Zaman, a CSE student at BUET. Over the last weeks I built a research project that asks whether
> Formula 1 drivers' cornering styles can be measured and identified from public telemetry sampled under four
> times a second, using signal-processing methods from CSE 220. I quantified the measurement error with
> simulated laps, and ran a preregistered test on a season held out until the end: the features identify
> teammates on unseen weekends better than lap time, but a driver's style did not clearly follow them to a new
> team.
>
> I have attached a short report and the code is public at github.com/SadMan-ZaMaN/ApexTrace. I would be
> grateful for 15 minutes of your advice on whether this could become a paper and what I should improve. I would
> also be glad to help with any of your ongoing projects where these skills (signal conditioning, feature
> extraction, careful evaluation, Python pipelines) are useful.
>
> Sincerely,
> Sadman Zaman

**Be ready for:** "Why not deep learning?" (Phase 9, same protocol; the point here was knowing the error of every
number). "Is 5 changers enough?" (No, and it was said in advance.) "What is new?" (Do the literature search in
section 6 before claiming novelty.)

## 4. CV lines (real numbers only)

- Built a tested Python pipeline that extracts corner-level driving features from 3.8 Hz public F1 telemetry
  (2.09 M samples from 69 qualifying sessions), with per-feature error bars validated on simulated laps.
- Designed a leakage-free leave-one-weekend-out identification protocol with baselines; corner features identified
  teammates at 0.66 balanced accuracy vs 0.58 for lap time on a held-out season (preregistered, p = 0.027).
- Tested whether driving style follows drivers who change teams (negative result, reported with an exploratory control).
- Flask + D3 web app for lap comparison and corner analysis; GitHub Actions CI; generated, number-checked report.

## 5. Keeping the project healthy alone

**The update loop** (after you change any analysis):
1. re-run the experiment script that produces the result;
2. `python experiments/16_app_data.py` (the web app's data);
3. `python experiments/17_write_docs.py` (README and report);
4. `python -m pytest` (a test fails if the README/report are stale);
5. research log entry, then commit.

**What you are most likely to break, and how to avoid it:**
- **Editing README.md or docs/report.md directly.** They are generated; edit `docs/templates/*.j2`. The test
  `test_generated_documents_match_the_results` will catch it.
- **Touching `results/final/`.** It is the frozen 2025 test. Never rerun `14_final_2025.py` into it; if you find a
  bug, rerun into a new folder and report both (preregistration Part B).
- **Using 2025 to choose anything.** Any new feature or threshold must be developed on 2023–2024 only.
- **Smoothing before finding an event** (brake onset, apex): it shifts or smears the event (Phase 2). Locate events
  on raw samples; smooth only for display.
- **Computing a time gap from projected position** `s_m`: use integrated distance `d_m` (chapter 13).
- **Random train/test splits** for identification: always leave whole weekends out.
- **Committing raw data:** `*.parquet` and `cache/` are gitignored; keep it that way (and no logos or photos).
- **"Simplifying" code listed in the CLAUDE.md bug history** (slow-lap rule, permutation minimum p, OpenF1 lap
  table, sessions without laps, the gap curve): each was a real bug.

## 6. Future work, in order of value

1. **Literature search** (Scholar, Semantic Scholar, arXiv): "Formula 1 telemetry driving style", "driver
   identification telemetry", "driver fingerprinting vehicle data". Read Enev et al. 2016 and Bell et al. 2016
   (both verified, in `docs/related_work.md`). Needed before claiming anything is new.
2. **The position-offset check** (open question in the research log): over many lap pairs, compare the gap at the
   line computed from projected position with the official lap-time gap. If position carries a lap-specific offset,
   the position features have extra noise.
3. **Teammate-relative features** to remove the car: per weekend, subtract the teammate's mean. Then re-ask H4 on
   development data first.
4. **H5, 2026 regulations**: when the 2026 season is available, does the signature survive a new car generation?
   Preregister first.
5. **Phase 9, a learned model** (for example a 1-D CNN on the raw corner traces) under exactly the same
   leave-one-weekend-out protocol and baselines.

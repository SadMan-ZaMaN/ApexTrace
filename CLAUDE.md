# F1 Driver Signature & Cornering Analysis — Project Context (handoff file)

> Exported on 2026-10-14 from a Claude Code session in the **Consonance**
> (auto-tune) repo. That conversation is NOT available in the new repo, so
> everything needed to continue is written down here: who we are, how we
> decided on this project, the research plan, the methods, the roadmap and
> the rules. Read it top to bottom before doing anything.

Legend used below: ✅ = verified on the web on 2026-10-14 ·
⚠️ = unverified or a proposal — check before relying on it.

---

## 0. How to use this file

**For Sadman:**
1. Create the new project folder (e.g. `D:\f1-driver-signature`) and a new
   GitHub repo for it.
2. Copy this file into the new folder and **rename it to `CLAUDE.md`**.
   Claude Code loads `CLAUDE.md` automatically at the start of every session,
   so the new Claude will "remember" all of this.
3. Open Claude Code in the new folder and say:
   *"Read CLAUDE.md fully, then do the first-session checklist (section 18)."*
4. Do **not** commit this file to the autotune repo (that repo is public and
   about a different project). Delete it from the autotune folder once copied.

**For Claude (new session):**
- This is a **living document**. Keep section 1 ("Status") up to date as work
  progresses, and add decisions to section 4 with dates.
- In the first session, split it: keep `CLAUDE.md` short (who we are, how to
  work, rules, status, roadmap summary — under ~250 lines) and move the long
  reference parts (sections 9–12, 20–22) into `docs/PROJECT_CONTEXT.md`, with
  a link from `CLAUDE.md`. Nothing in here should be lost, only moved.
- Treat ⚠️ items as things to verify in the data pilot, not facts.

---

## 1. Status

| Date | State |
|------|-------|
| 2026-10-11 | Brainstormed F1 + signals project ideas (section 4). |
| 2026-10-14 | Direction, research question, pilot session and protocol agreed in chat. **No code yet, no repo yet.** |
| next | Phase 0 (setup) + Phase 1 (data pilot) — see section 14. |

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
  he can show a faculty member to start research with them (on this project
  or on the faculty member's own projects).
- Big F1 fan, but not a vehicle-dynamics engineer. Explain car/racing terms
  plainly too (glossary in section 22).
- ⚠️ Whether Rajin joins this project is undecided — ask.

### How to work with him (carried over from the Consonance sessions)
- **Teach, then build.** For each step: a short plain-language explanation
  (with a signals-and-systems analogy he can repeat in a viva or interview) →
  small, explainable code → a test on a synthetic signal → a plot → write down
  what was learned. He must be able to explain every line to a faculty member
  or interviewer. He said: *"we will learn and implement, use easy python
  codes that are explainable."*
- **Explicit, readable Python** over clever one-liners (section 15).
- **Give a recommendation, not a menu.** When there is a choice, say which
  option you'd pick and why. Ask only when the decision is genuinely his.
- **Be honest.** Label what is measured vs. what is a hypothesis. Never invent
  a number. Say plainly when an idea doesn't work — that is a result too.
- **Explain every research/statistics term the first time it appears**
  (ICC, p-value, bootstrap, ablation, leakage, …).
- **Never `git commit`, `git push`, or stage files (`git add`/`git rm`).** He
  commits himself with GitHub Desktop after reviewing. Finish work as
  working-tree changes, show `git status --short`, and suggest a commit message.
- Publishing rule (from Consonance, adapted): never put copyrighted media into
  anything public — no F1 broadcast footage, onboard audio, team radio clips,
  driver photos, or F1/team logos. Charts made from telemetry are fine.

### Environment
- Windows 11, Claude Code inside VS Code. PowerShell is the main shell; Git
  Bash is also available.
- **Gotcha:** in Git Bash, a heredoc (`python - <<'EOF' … EOF`) fails if its
  body contains an apostrophe (`it's`, `driver's`). Write multi-line scripts to
  a file with the Write tool and run the file instead.
- Python 3.13 was used for Consonance (venv in `.venv`). ⚠️ Check that the
  FastF1 version we install supports 3.13; if not, use 3.12.
- Microsoft Edge is installed; Playwright works with `channel="msedge"` for
  UI screenshots later (no browser download needed).

---

## 3. Goals (in his words, then sharpened)

*"I want to make this for fun, a serious project that I can learn from, that
can help with projects or internships and strengthen my CV… also focus on
research scope, if somehow I can publish anything from it."*

1. **Learn properly**: deepen Signals & Systems, and pick up new topics
   (statistics, experiment design, ML evaluation) by building something real.
2. **CV / internship value**: an end-to-end, tested, well-documented project
   with honest, measured results — useful for ML/data, software, and
   automotive/motorsport-adjacent internships.
3. **Research experience**: a clear research question, a careful method, and
   written-up findings good enough to discuss with a faculty member — and
   possibly to publish (section 12).
4. **Fun**: it's about F1.

Agreed priorities: **technical depth + CV value**, **public data only**,
**DSP first, ML later**.

---

## 4. How we got here — decision log

**2026-10-11 — brainstorm (Claude's first list of ideas):**
1. *Acoustic telemetry* — estimate RPM/gear/speed from onboard engine audio
   (a 4-stroke V6 fires 6 × RPM / 120 times per second → 600 Hz at 12,000 rpm),
   validated against FastF1 RPM. Claude's original top pick.
2. *Telemetry → engine-sound synthesizer* (Fourier synthesis, convolution
   environments like the Monaco tunnel, Doppler for a trackside listener).
3. *Doppler speed gun* (a car passing at 300 km/h drops pitch by a ratio of
   ≈1.64 ≈ 8.6 semitones).
4. *Porpoising detector* from onboard video (optical flow → FFT,
   mass-spring-damper model).
5. *Driver DNA* — driver comparison from telemetry.
6. *Team-radio stress meter*.

**Then:** Sadman refined the direction with another AI assistant and chose
**#5, driver comparison + signal analysis**, because of the priorities above
(technical depth, CV value, public data). Claude's earlier worry about #5 —
"lots of FastF1 dashboards exist, hard to stand out" — is answered by making
it a **measurement + evaluation research project, not a dashboard**.

**Choices made (by Sadman):**
- Goal: **both** corner-level driving analysis (main, done first) **and**
  driver identification (second; it tests whether the features are real).
- Initial scope: **a few corners, analysed deeply**.
- Seasons: **2023–2025**.
- Drivers: **teammates first**, cross-team later.
- Corners: **a mix of heavy-braking, medium-speed and fast corners**.
- Pilot: **2024 Abu Dhabi GP, McLaren — Lando Norris vs Oscar Piastri**.

**2026-10-14 — Claude's corrections to the earlier plan (adopted):**
1. The brake channel is **on/off (boolean) in FastF1 too**, not only in
   OpenF1 ✅. So "who brakes more progressively" (brake pressure) cannot be
   measured. Use **deceleration derived from speed** instead.
2. At ~3.7 Hz and 300 km/h there is one sample every **~22.5 m**. Teammates'
   braking points may differ by only a few metres → **estimating events
   between samples, with honest error bars, is the core DSP challenge**.
3. A normal (causal) smoothing filter **delays** the signal and shifts braking
   points by tens of metres → use **zero-phase** filtering (section 9.3).
4. **FFT on a single corner is nearly useless** (~15 samples). Use
   frequency-domain thinking where it belongs (filter design, sampling,
   noise analysis), not forced into every feature.
5. **FP2 is risky for comparing drivers**: teammates often run different fuel
   loads and tyre programmes. Use FP2 only for consistency checks on matched
   runs; use **qualifying for the comparison**.
6. One qualifying session gives only ~4–7 push laps per driver ⚠️ — too few to
   test identification. **Identification needs many sessions** (a season).
7. **Research hook:** drivers who **changed teams** (e.g. Hamilton
   Mercedes→Ferrari, Sainz Ferrari→Williams in 2025). If a driver's signature
   follows them into a different car, it's the driver, not the car.
   The **2026 regulation change** is a second "natural experiment".

**New proposals written into this file (⚠️ confirm with Sadman):**
- Keep the **2025 season as a frozen final test set** (develop on 2023–2024).
- Build a **synthetic-lap generator** to measure how accurate our estimators
  are (lesson from Consonance: test against known truth).
- Always include a **"lap time only" baseline** in identification.

---

## 5. The project in plain words

Every F1 car sends about **4 readings per second** to the public timing feed:
speed, throttle %, brake (on/off), gear, RPM, and position on track. Each of
those is a **signal over time**.

We take two teammates' laps (same car, same session), cut out the **same few
corners**, line the laps up by **position on track** (not by time), clean the
signals properly, and measure things like:
- where braking starts, and how hard the car slows down,
- the slowest speed in the corner and where it happens,
- when and how quickly the driver gets back on the throttle,
- exit speed and time spent in the corner.

Then we test, carefully:
1. **Is each driver consistent** from lap to lap? (repeatability)
2. **Are the two drivers measurably different** — by more than our
   measurement error? (distinguishability)
3. **Can a model tell who drove a lap it has never seen**, from a session it
   was never trained on? (generalisation)
4. **Is it the driver or the car?** — using drivers who changed teams.

It does **not** try to decide who is the "better" driver.

### Pipeline at a glance

```
FastF1 session
  -> choose clean laps (no in/out laps, no yellow flags, no deleted laps)
  -> per lap: Speed, Throttle, Brake, nGear, RPM, X/Y  (~3.7 Hz, irregular)
  -> data-quality checks (gaps, timing jitter, quantisation, interpolated rows)
  -> time -> track distance; fix distance drift by aligning to a reference lap
  -> cut a window around each chosen corner
  -> zero-phase filtering; derivative of speed -> deceleration
  -> events located BETWEEN samples (brake onset, apex, throttle pickup) + error bars
  -> one feature vector per (driver, lap, corner)
  -> statistics: repeatability (H1), driver differences (H2)
  -> identification on held-out sessions (H3); driver vs car (H4)
```

---

## 6. Research question and hypotheses

**Main research question:**
> Can signal-processing techniques extract **repeatable, interpretable
> driving signatures** from low-rate public F1 telemetry, explain corner-level
> differences between drivers, and identify drivers on **unseen sessions** —
> and how much of that signature belongs to the **driver rather than the car**?

**Hypotheses** (to test, not to assume — a "no" is a valid result):
- **H1 — Repeatability:** a driver's corner features are stable across
  comparable laps (measured with ICC, section 11.3).
- **H2 — Distinguishability:** teammates differ in braking, minimum speed and
  throttle application by **more than the measurement uncertainty**.
- **H3 — Generalisation:** the features identify the driver on **entire
  held-out sessions** better than simple baselines, including "lap time only".
- **H4 — Driver vs car:** for drivers who changed teams, the signature follows
  the driver into the new car.
- **H5 — (optional, later):** signatures survive the 2025 → 2026 regulation
  change.

**What we will NOT claim:**
- who is the better or more skilled driver;
- anything about effects faster than the data can show (vibration,
  suspension, fine steering corrections — Nyquist ≈ 1.85 Hz);
- brake pressure or brake modulation (the channel is on/off);
- labels like "aggressive" unless defined as a measurable rule first.

---

## 7. Data

### Sources
- **FastF1** (primary) ✅ — unofficial, MIT-licensed Python library
  (docs: https://docs.fastf1.dev/, code: https://github.com/theOehrly/Fast-F1).
  - Car data ✅: `Speed` (km/h), `RPM`, `nGear` (int), `Throttle` (0–100 %),
    `Brake` (**bool**), `DRS` (int). About **3.7 Hz**.
  - Position data ✅: `X`, `Y`, `Z` (units of 1/10 m), `Status` (on/off track).
  - Both have `Time`, `SessionTime`, `Date`, and `Source` = `'car'`, `'pos'`
    or `'interpolated'`. **Rows marked `interpolated` are not measurements** —
    keep track of them.
  - Merging car + position data ✅ interpolates: linear for continuous
    channels (Speed, RPM), forward-fill for discrete ones (Gear, DRS). Docs
    warn: resample only once, always from the original data.
  - `add_distance()` ✅ builds distance by **integrating speed**; docs warn
    about integration error and say not to apply it across many laps at once.
    → distance drifts; we must correct it (section 9.5).
- **OpenF1** (secondary / cross-check) — https://openf1.org/docs/ — historical
  data from 2023, similar rate (~3.7 Hz), brake also binary.

### Known limitations (write these in the report, too)

| Limitation | Consequence |
|---|---|
| ~3.7 Hz car data, irregular timing | Nyquist ≈ 1.85 Hz; events known only to within one sample interval unless we estimate between samples |
| Brake is on/off | no brake pressure; use deceleration from speed |
| Speed probably integer km/h ⚠️ | quantisation noise, amplified by differentiation (section 9.4) |
| Distance = integrated speed | drift of metres to tens of metres per lap ⚠️ measure it |
| No steering, no tyre temperature, no fuel load | can't measure steering style; fuel/tyres are confounders |
| Car and position streams have different timestamps | merging interpolates; report what is measured vs interpolated |

### Verify in the data pilot (Phase 1 checklist)
- [ ] Histogram of time between raw car-data samples (median, spread, gaps).
- [ ] Is `Speed` integer-valued? What resolution does `Throttle` have?
- [ ] Is `Brake` boolean in our sessions?
- [ ] Position-data rate and X/Y noise level.
- [ ] Spread of total lap distance for the same driver (size of drift).
- [ ] Number of usable push laps per driver in Q and FP2; tyre compound and
      tyre age per lap; deleted laps; track status (yellow flags).
- [ ] ⚠️ `session.get_circuit_info()` — does it give corner numbers and
      positions/distances we can use to place corner windows?
- [ ] ⚠️ Lap-filter helpers in FastF1 (`pick_quicklaps`, `pick_wo_box`,
      `pick_track_status`, `pick_not_deleted`, … — check exact names in docs).
- [ ] Cache size and load time per session.

### Lap selection rules (proposal ⚠️, finalise in Phase 1)
Keep: timed laps, green track status, not deleted, not in/out laps, no pit
stop. Record for every lap: compound, tyre life, session, lap number, whether
it was a push lap. Never silently drop a lap — log why.

---

## 8. Pilot experiment specification

- **Event:** 2024 Abu Dhabi Grand Prix (Yas Marina) — final round of 2024.
- **Drivers:** Lando Norris vs Oscar Piastri (McLaren teammates).
- ✅ Qualifying: McLaren front-row lockout — Norris pole (1:22.595), Piastri
  P2, +0.209 s.
- **Qualifying = main comparison** (push laps, low fuel, soft tyres).
  ⚠️ Expect only ~4–7 push laps per driver.
- **FP2 = repeatability only**, and only within matched runs (same compound,
  similar tyre age; separate short runs from long runs). Teammates may run
  different programmes — check before comparing.
- **Three corners:** one heavy-braking corner (end of a long straight), one
  medium-speed corner, one fast corner — chosen from the data in Phase 1.
  Write down why each was chosen in `docs/decisions.md`.
- **Pilot success** = measurements we can trust, with error bars and honest
  limits. **Not** a target accuracy number.

**Small-sample warning (explain this to Sadman):** with ~6 laps per driver,
a standard two-group test at 80 % power can only detect differences of about
**1.8 standard deviations** (≈ effect size d = 1.8). With 10 laps per group
it's ≈ 1.3, with 20 ≈ 0.9. One session can only reveal big differences — this
is why the project later scales to whole seasons.

---

## 9. Signal-processing methods — and WHY each one is here

The project should explain *why* each tool is appropriate. Don't use a
technique just because it's in the syllabus. (Example: Z-transforms are the
right tool for **designing and analysing filters**; they do not by themselves
"identify a driving style".)

### 9.1 Sampling and Nyquist
At 3.7 Hz, the sample period is T ≈ 0.27 s and Nyquist ≈ 1.85 Hz.
Distance travelled between samples:

| Speed | m/s | metres per sample (3.7 Hz) |
|---|---|---|
| 300 km/h | 83.3 | **22.5 m** |
| 200 km/h | 55.6 | 15.0 m |
| 100 km/h | 27.8 | 7.5 m |
| 60 km/h | 16.7 | 4.5 m |

Upsampling to 50 or 100 Hz creates **no new information** — it only
interpolates. Every claim must respect this.

### 9.2 Irregular sampling and resampling
Timestamps are not perfectly uniform. Most filters assume uniform samples,
so: resample once onto a uniform grid (time or distance), and keep a mask of
which grid points are close to a real sample. Teaching point: **linear
interpolation = convolution with a triangle kernel** (a crude low-pass
filter); ideal band-limited reconstruction would use a sinc kernel.

### 9.3 Filtering, the Z-transform, and the group-delay trap
Compare, on synthetic data where the truth is known:
- **Moving average** of N samples: H(z) = (1/N)(1 + z⁻¹ + … + z⁻⁽ᴺ⁻¹⁾);
  zeros on the unit circle; delay (N−1)/2 samples.
- **Exponential moving average**: y[n] = α·x[n] + (1−α)·y[n−1],
  H(z) = α / (1 − (1−α)z⁻¹), one pole at z = 1−α.
- **Butterworth low-pass** (`scipy.signal.butter`), analysed with a
  pole-zero plot and `freqz`.

**The trap (worked example):** a causal 5-sample moving average delays the
signal by 2 samples = 2 / 3.7 ≈ **0.54 s**. At 250 km/h (69.4 m/s) that moves
the apparent braking point by **≈ 37.5 m** — bigger than the differences we
want to measure. **Fix:** zero-phase filtering — run the filter forward, then
backward (`scipy.signal.filtfilt`). The result has magnitude |H|² and **zero
phase**, so no shift. Choose the cutoff by looking at the spectrum of the
residual (raw − smoothed), not by eye.

### 9.4 Differentiation is a high-pass filter
The first difference H(z) = 1 − z⁻¹ has |H(e^{jω})| = 2|sin(ω/2)| — it grows
with frequency, so it **amplifies noise**. Worked example: if speed is
quantised to 1 km/h (= 0.278 m/s ⚠️ verify), one quantisation step over
0.27 s looks like **≈ 1.0 m/s² (≈ 0.1 g)** of fake deceleration. Peak F1
braking is roughly 4–6 g ⚠️ (typical published figure), so peak deceleration
is fine, but finding the *start* of braking needs smoothing first. Options:
derivative of the zero-phase-smoothed signal, or **Savitzky–Golay** (local
polynomial fit, which is itself an FIR filter).

### 9.5 Time → distance, and aligning laps
Integrate speed over time (trapezoidal rule) to get distance per lap. Because
this drifts, align each lap to a **reference lap**: compute the normalised
**cross-correlation** of speed-vs-distance over a window and find the lag of
the peak. Get a lag finer than the grid with **parabolic interpolation of the
correlation peak** — the exact trick Consonance's pitch detector uses on its
autocorrelation peak. Alignment quality = remaining lag + correlation value.
Alternative ⚠️: project each X/Y sample onto the reference lap's path (nearest
point) — depends on X/Y quality, check in Phase 1.

### 9.6 Dynamic Time Warping (DTW)
DTW stretches one trace against another to match shapes. Useful as a
**diagnostic** ("where do the two laps progress differently?"). Warning: DTW
can **warp away the very differences we want to measure**. Constrain it
(Sakoe–Chiba band), and never compute features on warped traces without
thinking about what was removed.

### 9.7 Locating events between samples (the DSP heart of the project)
- **Brake onset from the on/off channel:** we only know it happened somewhere
  between the last "off" and the first "on" sample. If equally likely
  anywhere in that gap, the error has standard deviation
  **spacing / √12** → at 300 km/h: 22.5 / 3.46 ≈ **6.5 m**.
- **Refinement:** fit the speed trace around braking with a piecewise model
  (roughly constant speed, then a straight-line decrease) and solve for the
  **breakpoint** as a continuous number.
- **Averaging across laps works like dithering:** the sampling grid lands at
  a random offset each lap, so the error is random and averages down by √N —
  9 laps → 6.5 / 3 ≈ **2.2 m**. ⚠️ Verify that the sampling phase really is
  random relative to track position.
- **Apex (minimum speed):** parabolic interpolation through the three samples
  around the minimum (same idea as Consonance).
- **Throttle pickup:** first crossing of a threshold, with linear
  interpolation between the two samples either side.

### 9.8 Matched filtering (optional)
Detect braking zones by correlating the deceleration signal with a template
of a typical braking event — a classic convolution/correlation detector.

### 9.9 System identification (candidate feature ⚠️)
Model throttle application after the apex as a first-order step response,
throttle(t) ≈ 100·(1 − e^{−t/τ}), and fit τ — a "throttle time constant" per
driver. Only ~5 samples per ramp, so report the fit's uncertainty.

### 9.10 Where the FFT does and doesn't fit
- A 4-second corner ≈ 15 samples → about 8 frequency bins, 0.25 Hz apart, up
  to 1.85 Hz. **Not useful on single corners.**
- **Useful for:** designing and checking filters, inspecting the noise
  spectrum of residuals, checking for aliasing, and *maybe* whole-lap or
  long-run features (e.g. high-frequency throttle energy as "smoothness").
  Treat the latter as an experiment and keep it only if an ablation shows it
  helps. "I tested it and it didn't help, here's why" is a strong answer.

### 9.11 Synthetic-lap generator (the measurement-science core)
Build a realistic continuous "true" corner (at e.g. 1 kHz): straight →
braking (deceleration that depends on speed ⚠️ approximate model) → apex →
acceleration, plus throttle and brake. Then **degrade it like the real
feed**: sample at ~3.7 Hz with a random start offset, add timing jitter,
quantise speed to 1 km/h, make brake on/off. Run our pipeline and measure
**bias and spread of every feature**, for naive vs refined estimators.
This gives the "±" we quote on real data, and is itself a potential research
contribution (section 12.3). Make it realistic — in Consonance, an
unrealistic test signal once looked like a detector bug.

---

## 10. Features (per driver, lap and corner)

Thresholds marked ⚠️ are proposals to tune in Phase 4.

| Feature | Definition | Main source |
|---|---|---|
| `brake_onset_dist` | distance of braking start, relative to a fixed corner reference point | Brake + speed breakpoint (9.7) |
| `entry_speed` | speed at a fixed distance before the corner reference | Speed |
| `braking_distance` | from brake onset to minimum-speed point | derived |
| `peak_decel`, `mean_decel` | max / mean deceleration while braking (m/s²) | derivative of smoothed speed |
| `min_speed`, `apex_dist` | minimum speed and where it occurs | parabolic interpolation |
| `coast_time` | time with brake off AND throttle < 5 % ⚠️ | Brake + Throttle |
| `throttle_pickup_dist` | first throttle > 10 % ⚠️ after the apex | Throttle, interpolated crossing |
| `full_throttle_dist` | first throttle ≥ 99 % ⚠️ after the apex | Throttle |
| `throttle_tau` | time constant of throttle application (9.9) ⚠️ | Throttle fit |
| `exit_speed` | speed at a fixed distance after the corner reference | Speed |
| `corner_time` | time from entry reference to exit reference | Time |
| `min_gear` | lowest gear in the window | nGear |

Plus, at driver level: **lap-to-lap spread** of each feature (consistency).

Normalised versions:
- **Teammate-relative:** feature − teammate's mean in the same session
  (largely cancels the car).
- **Field-relative:** z-score within (session, corner) across all drivers.

---

## 11. Evaluation protocol — how we know it works

### 11.1 Measurement validation (synthetic)
For each feature and estimator: bias and standard deviation of the error on
synthetic laps (9.11). No real-data claim smaller than this error.

### 11.2 Alignment quality
Remaining lag and correlation after alignment, per lap. Flag bad alignments.

### 11.3 H1 — Repeatability
Within-driver spread across laps, and **ICC** (intraclass correlation).
Plain meaning: of all the variation in a feature, what share comes from
*differences between drivers* rather than *lap-to-lap noise*?
ICC ≈ 1 → stable and distinctive; ICC ≈ 0 → mostly noise. Give bootstrap
confidence intervals.

### 11.4 H2 — Driver differences
Difference of means with a **bootstrap 95 % confidence interval**,
**permutation test** p-value, effect size (Cohen's d), and a comparison with
the measurement error from 11.1. Many features × corners = many tests →
correct for multiple comparisons (Holm or Benjamini–Hochberg) and explain why.

### 11.5 H3 — Driver identification
- **Tasks:** (a) teammate pairs — a binary task per team, repeated for all
  10 teams (10 replications instead of one); (b) all drivers in a season —
  multi-class, but strongly confounded by the car (say so).
- **Splits:** **leave-one-session-out** (group by event). Never split
  individual samples or laps of the same session between train and test.
  Fit scalers/normalisation on training data only.
- **Baselines:** majority class; **lap time only**; raw summary statistics
  (mean speed, etc.); then our features.
- **Models (interpretable first):** nearest centroid, logistic regression;
  random forest optional.
- **Metrics:** balanced accuracy, macro-F1, confusion matrix, results per
  corner type.
- **Ablation:** remove one feature group at a time. Permutation importance.
- **Sanity check:** shuffle the labels → performance must drop to chance.

### 11.6 H4 — Driver vs car (the team-change experiment)
Candidate drivers ⚠️ (verify line-ups and dates):
- Hamilton: Mercedes (2024) → Ferrari (2025)
- Sainz: Ferrari (2024) → Williams (2025)
- Ocon: Alpine (2024) → Haas (2025); Hülkenberg: Haas (2024) → Sauber (2025)
- **Lawson ↔ Tsunoda**: swapped between Red Bull and Racing Bulls early in
  2025 (after round 2) — a within-season car swap, the cleanest case.

Approaches:
1. **Signature similarity:** is a driver's 2025 (new car) signature closer to
   their own 2024 signature than to anyone else's? Rank-based test.
2. **Additive model:** feature = driver effect + team-season effect +
   session×corner effect + noise. Team changers are what make driver and car
   effects separable. Related idea in the literature: multilevel models of
   driver vs constructor *results* (Bell et al., 2016 ⚠️ verify). Our twist:
   apply it to corner-level *style* features. (New topic to learn: regression
   with categorical variables / mixed models, `statsmodels`.)

### 11.7 Frozen test set ⚠️ (proposal)
Develop everything on 2023–2024. Write the analysis plan into
`docs/preregistration.md` (dated) **before** touching 2025. Run the final
H3/H4 evaluation on 2025 **once**. This protects us from fooling ourselves.

### 11.8 Leakage and confounder checklist
Same-lap or same-session data on both sides of the split · normalisation fitted
on everything · picking features by looking at test results · tyre compound
and age · fuel load · track evolution · traffic and slipstream · wind ·
setup differences · engine modes · DRS · yellow flags · deleted laps.

---

## 12. Research scope — a first-timer's guide

### 12.1 Three levels (from the chat)
1. **Analytical project** — plots, metrics, dashboard. Good practice, not novel.
2. **Experimental engineering project** — hypotheses, methods compared,
   errors measured, generalisation tested. **← our baseline target.**
3. **Research contribution** — a clear gap in prior work, a defensible method,
   rigorous experiments, a new finding. **← reachable if results are interesting.**

### 12.2 Related work found so far (✅ checked 2026-10-14)
- **IJMO 2026:** "Can Unsupervised Learning Methods Reveal Distinct Driving
  Styles Among Formula 1 Drivers?" (https://ojs.ejournal.net/index.php/ijmo/article/view/22205).
  FastF1 data, but **race-level** features (relative lap time, lap-time
  consistency via MAD, tyre-degradation slope, overtaking efficiency, sector
  averages); K-Means / hierarchical / DBSCAN / GMM + PCA; finds 3–5 clusters.
  → Not corner-level signals, no driver identification.
- **GitHub `roeeam9/F1-Clustering-Project`** (closest to us):
  https://github.com/roeeam9/F1-Clustering-Project. OpenF1, four 2023
  qualifying sessions (Monza, Spa, Singapore, Suzuka), **fastest lap per
  driver only**; 12 per-corner features (entry/apex/exit speed, braking %,
  trail-braking %, coasting %, throttle after apex, min gear, …); z-score per
  (track, corner); PCA + two-stage K-Means → 3 "archetypes".
  **No held-out evaluation, no supervised identification, no team-change
  analysis, no measurement-uncertainty analysis.** → cite and differentiate.
- **Frontiers in AI, 2025** (doi 10.3389/frai.2025.1673148): deep sequence
  models (BiLSTM/GRU/TCN/CNN-BiLSTM) on F1 telemetry 2020–2024. ⚠️ Read to see
  exactly what task they solve.
- Road-car **driver identification** (a big field — good framing for H3):
  arXiv 1911.08030 (LSTM on telematics); Enev et al., 2016, "Automobile
  Driver Fingerprinting" (PoPETs) ⚠️ verify.
- Bell et al., 2016, multilevel modelling of F1 driver vs constructor
  performance (Journal of Quantitative Analysis in Sports) ⚠️ verify.

### 12.3 Our candidate contributions (the "gap")
- **C1 — Measurement:** how accurately can corner features be measured from
  ~3.7 Hz public telemetry? Quantified with a realistic simulation, plus
  better estimators (sub-sample events, zero-phase filtering).
- **C2 — Repeatability:** which corner features are stable across laps and
  sessions (ICC), and which are noise?
- **C3 — Identification done honestly:** held-out *sessions*, proper
  baselines (including lap-time-only), ablations.
- **C4 — Driver vs car:** separating the two using team changers.

One solid contribution might support a short paper; C1 + C2 + C3 make a good
student paper; C4 is the most interesting if the data allows it. Before
claiming novelty, do a proper literature search (12.5) — especially for C4.

### 12.4 Working titles (not final)
- "How Stable Are F1 Driver Signatures? A Signal-Processing Study of
  Corner-Level Telemetry and Cross-Session Generalisation"
- "Driver or Car? Separating Driving Style from Machinery with Low-Rate
  Public F1 Telemetry"

### 12.5 Research habits to build from day one
- **Research log** — `docs/research_log.md`: date, what was tried, what
  happened, what's next. Faculty love seeing this.
- **Preregistration** — write hypotheses + analysis plan before running the
  final tests (11.7).
- **Reproducibility** — results come from scripts (not notebook cells), fixed
  random seeds, pinned library versions (including FastF1), data cached.
- **Negative results are results.** Report what didn't work and why.
- **Literature tracker** — `docs/related_work.md`: paper, what they did, data,
  how we differ. Read papers with Keshav's "three-pass method".
- Search Google Scholar / Semantic Scholar / arXiv for: "Formula 1
  telemetry driving style", "driver identification telemetry", "racing driver
  behaviour", "driver fingerprinting vehicle data", "driver constructor
  multilevel".

### 12.6 Talking to a faculty member
- **When:** after Phase 4–5, when there is something concrete (the 3-corner
  analysis + the measurement-error result). Asking for advice earlier is fine.
- **Whom:** BUET faculty working on signal processing, ML, data science or
  time series — check department pages; ask seniors who have published.
- **Bring:** a 1-page summary, 3 strong figures, one clear question, what has
  been done, and a specific ask ("Is C1/C3 publishable? Which venue? Would you
  supervise?"). Also mention Consonance.
- **Offer help on their projects:** the skills transfer — signal conditioning,
  feature extraction, honest evaluation, clean Python pipelines.
- **Email sketch:** *"Dear Sir/Madam, I'm Sadman Zaman (CSE, BUET). I've been
  studying whether F1 drivers' corner-level driving signatures can be
  measured and identified from public telemetry, using signal-processing
  methods from CSE 220. I've attached a one-page summary with initial results.
  I'd be grateful for 15 minutes of your advice on whether this could become
  a research paper, and I'd also be glad to help with any of your ongoing
  projects where these skills are useful."*

### 12.7 Venues (⚠️ ask the faculty member; check deadlines)
arXiv preprint (first-time submitters may need an endorsement — a faculty
co-author helps); IEEE conferences held in Bangladesh (the faculty member will
know which fit, e.g. ⚠️ ICECE at BUET); sports-analytics journals such as the
Journal of Quantitative Analysis in Sports (harder). Even without a paper, a
public technical report + repo is valuable.

### 12.8 Authorship
If Rajin or a faculty member joins, agree on authorship early.

---

## 13. CV and internship value

### Positioning
- **ML/AI internships:** feature engineering, baselines, held-out evaluation,
  error analysis, DSP-vs-ML comparison. What matters: knowing *why* a model
  works and where it fails, not a high accuracy number.
- **Software internships:** a tested, modular Python package, reproducible
  pipeline, CI, a deployed app.
- **Research internships / undergraduate research:** hypotheses, protocol,
  ablations, limitations, a written report.
- **Automotive / motorsport / sensor-data roles:** telemetry processing,
  time-series analysis, honest interpretation of what sensors can reveal.
- Reality check: F1 teams mostly hire students through Formula Student and
  UK/EU programmes, and use far richer internal data. This project is a great
  talking point there, but its main value is for ML/data/software internships
  in general — and the methods transfer to industrial sensor monitoring and
  predictive maintenance.

### Illustrative CV entry (fill in numbers ONLY after measuring)
**F1 Driver Signature & Cornering Analysis** | Python, NumPy, SciPy, FastF1
- Built a signal-processing pipeline that aligns low-rate (~3.7 Hz) F1
  telemetry by track distance and locates braking/apex/throttle events between
  samples, with error bars validated on simulated laps (±X m).
- Measured the repeatability of corner-level driving features (ICC) and
  identified drivers on held-out race weekends (macro-F1 = X vs Y for a
  lap-time-only baseline).
- Separated driver from car effects using drivers who changed teams.
- Reproducible experiments, automated tests, CI, interactive telemetry explorer.

### Shareable outputs (the same project, three audiences)
- **A. Fan-readable analysis** (after Phase 4): "Norris vs Piastri at three
  corners" — for LinkedIn / r/F1Technical / seniors. 5-minute read.
- **B. Technical report** (Phase 8): maths, methods, experiments, limits —
  for faculty and research applications. LaTeX/Overleaf (a research skill).
- **C. Interactive app + 2-minute video** (Phase 8): pick circuit, corner,
  drivers → aligned traces, features, what can and can't be concluded.

### Interview story
Consonance (classical DSP, audio) → this project (DSP on sensor data +
statistics + honest ML evaluation) = "a signal-processing person who tests
his claims properly."

---

## 14. Roadmap

Rough durations assume ~8–10 hours/week ⚠️ — adjust once Sadman confirms.
Every phase ends with: tests passing, a research-log entry, and this file's
Status updated.

| Phase | Learn | Build | Done when |
|---|---|---|---|
| **0. Setup** (week 1) | git basics refresher, pandas basics, FastF1 tutorial | repo, venv, requirements, FastF1 cache, folder structure, pytest | can load a session and plot one lap |
| **1. Data pilot** (weeks 1–2) | sampling in practice, data quality | `experiments/01_data_pilot.py`: section-7 checklist on 2024 Abu Dhabi Q + FP2; choose 3 corners | `docs/data_report.md` filled: what the data can and can't support |
| **2. Synthetic laps + measurement science** (weeks 2–4) | Z-transform for filters, group delay, quantisation, differentiation as a filter | synthetic generator; MA / EMA / Butterworth / zero-phase; naive vs refined event estimators | error table (bias/std) per feature; group-delay demo plot |
| **3. Corners + alignment on real data** (weeks 4–6) | cross-correlation, sub-sample peaks, DTW | time→distance, drift correction, corner windows, alignment-quality metric | aligned corner traces for all laps of both drivers, with quality numbers |
| **4. Features + first shareable analysis** (weeks 6–8) | feature design, uncertainty propagation | feature extraction with error bars; Norris vs Piastri write-up | output A published (after Sadman reviews) |
| **5. Repeatability & differences** (weeks 8–9) | ICC, bootstrap, permutation tests, multiple comparisons | stats module; preregistration written first | H1/H2 answered for the pilot, with CIs |
| **6. Scale up + identification** (weeks 9–12) | cross-validation, leakage, baselines, ablation | pipeline over 2023–2024 qualifying, all teams; corner selection generalised (by min speed); leave-one-session-out ID | H3 answered on 2023–2024 (2025 still untouched) |
| **7. Driver vs car** (weeks 12–14) | regression with categorical effects / mixed models | team-change experiment; final one-time test on 2025 | H4 answered; final numbers frozen |
| **8. Write-up + app** (weeks 14–17) | LaTeX, technical writing, app deployment | report (output B), README with results, app + video (output C), CI | repo is presentable; faculty contact made (if not earlier) |
| **9. ML later** (optional) | 1D CNNs on sequences, PyTorch | learned model on aligned corner traces vs our features, same held-out protocol | honest DSP-vs-ML comparison |

Faculty contact: ideally after Phase 4–5 (section 12.6).

---

## 15. Repo structure, tech stack, coding conventions

### Proposed structure (adjust as needed)
```
f1-driver-signature/            # name TBD — e.g. "apex-signature", "cornerprint"
├── CLAUDE.md                   # this file (trimmed in session 1)
├── README.md
├── requirements.txt
├── src/f1sig/
│   ├── data_loading.py         # FastF1 wrappers, caching, lap selection + reasons
│   ├── quality.py              # sampling-interval checks, gaps, interpolated rows
│   ├── synthetic.py            # synthetic corner/lap generator with ground truth
│   ├── filters.py              # MA, EMA, Butterworth, zero-phase, frequency response
│   ├── resampling.py           # time -> distance, uniform grids, masks
│   ├── corners.py              # corner windows, corner types
│   ├── alignment.py            # cross-correlation lag, parabolic peak, DTW
│   ├── events.py               # brake onset, apex, throttle pickup (sub-sample)
│   ├── features.py             # feature vectors per (driver, lap, corner)
│   ├── stats.py                # ICC, bootstrap, permutation tests
│   ├── identification.py       # splits, baselines, models, metrics
│   └── plots.py
├── experiments/                # numbered scripts: 01_data_pilot.py, 02_synthetic_errors.py ...
├── notebooks/                  # exploration only — final numbers come from experiments/
├── tests/
├── docs/                       # PROJECT_CONTEXT.md, research_log.md, decisions.md,
│                               # data_report.md, preregistration.md, related_work.md
├── results/                    # small JSON/CSV outputs + figures
└── cache/                      # FastF1 cache — gitignored
```

### Tech stack
Python 3.13 (or 3.12 ⚠️), NumPy, SciPy, pandas, Matplotlib, FastF1. Later:
scikit-learn (Phase 6), statsmodels (Phase 7), PyTorch (Phase 9 only).
App (Phase 8): Flask + vanilla JS with a JS charting library, or Streamlit —
decide then. Tests: pytest. CI: GitHub Actions — tests must **not** download
F1 data; use synthetic signals and tiny derived fixtures.

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
- Keep a **bug history** section in CLAUDE.md for anything that took real
  debugging, so nobody "simplifies" back into a known-broken approach.
- If Rajin joins: keep a `CONTRACTS.md` of agreed function signatures.

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

## 18. First-session checklist (for the new Claude)

1. Read this whole file.
2. Ask Sadman the open questions in section 19 (hours/week, solo or with
   Rajin, repo name, any deadline).
3. Split this file as described in section 0 (short `CLAUDE.md` +
   `docs/PROJECT_CONTEXT.md`); create empty `docs/research_log.md`,
   `docs/decisions.md`, `docs/related_work.md` (seed it from 12.2).
4. Phase 0: create `.venv`, `requirements.txt`, `.gitignore` (cache/, .venv/,
   `__pycache__/`, large results), folder structure, pytest set-up; install
   FastF1 and confirm it works on this Python version.
5. Start Phase 1: load 2024 Abu Dhabi Qualifying + FP2 for NOR and PIA, work
   through the section-7 checklist, and write `docs/data_report.md`.
   Explain each finding to Sadman in plain words as you go.
6. Update section 1 (Status). Show `git status --short` and suggest a commit
   message. Do not commit.

---

## 19. Open questions (ask early)

- How many hours per week? Any deadline (internship applications, semester)?
- Solo, or with Rajin? (If with Rajin: split modules, `CONTRACTS.md`, authorship.)
- Repo name? (Descriptive names are easier to find on a CV, e.g.
  `f1-driver-signature`.)
- Approve the frozen-2025-test-set plan (11.7)?
- Any faculty member already in mind?

---

## 20. Parked ideas (future projects or later extensions)

From the 2026-10-11 brainstorm — not part of this project, kept for later:
acoustic telemetry from engine audio (RPM via harmonic tracking, validated
against FastF1 RPM; reuses Consonance's pitch-detection skills),
telemetry-to-engine-sound synthesizer (Fourier synthesis + convolution +
Doppler), Doppler speed gun with own street recordings, porpoising from
onboard video (optical flow + mass-spring-damper model), team-radio stress
meter. Also for Consonance itself: Docker + Hugging Face Spaces deployment
was the next planned step there (a live demo link helps a CV).

---

## 21. Learning resources

- FastF1 docs (https://docs.fastf1.dev/) and examples gallery; OpenF1 docs.
- Course textbook for signals and systems (Oppenheim & Willsky style) —
  Z-transform, sampling, filters.
- *Think DSP* by Allen Downey (free, Python) — practical spectra and filters.
- *Understanding Digital Signal Processing* by Richard Lyons — filters,
  group delay, differentiators.
- SciPy `signal` docs: `butter`, `filtfilt`, `freqz`, `savgol_filter`,
  `correlate`.
- *An Introduction to Statistical Learning* (free, Python edition) —
  cross-validation, logistic regression, model evaluation.
- scikit-learn user guide: cross-validation with groups (`GroupKFold`,
  `LeaveOneGroupOut`).
- S. Keshav, "How to Read a Paper" (the three-pass method).
- Sakoe & Chiba (1978) for DTW, if going deep on alignment.

---

## 22. Glossary (plain words)

- **Apex** — the inside point of a corner; usually near the slowest point.
- **Braking point / brake onset** — where the driver starts braking.
- **Trail braking** — still braking while starting to turn in (hard to see
  with an on/off brake channel).
- **Push lap** — a lap at full speed (as opposed to out-laps, in-laps, cool-down).
- **Stint / run** — consecutive laps on one set of tyres.
- **Compound** — tyre type (soft / medium / hard); softer = faster but wears quicker.
- **FP1/FP2/FP3** — practice sessions; **Q1/Q2/Q3** — qualifying stages.
- **DRS** — a flap on the rear wing opened on straights to reduce drag.
- **Telemetry** — sensor data sent from the car.
- **Nyquist frequency** — half the sampling rate; nothing faster can be seen.
- **Group delay** — how much a filter delays a signal (here: shifts events in distance).
- **Zero-phase filtering** — filter forward then backward so nothing is shifted.
- **Cross-correlation** — slide one signal over another; the best-matching lag is the offset.
- **DTW** — dynamic time warping; stretches signals to match shapes.
- **ICC** — intraclass correlation; share of variation due to real differences
  between drivers vs lap-to-lap noise.
- **Bootstrap** — resample your data many times to see how much a result wobbles.
- **Permutation test** — shuffle labels many times to see how often a
  difference this big appears by chance.
- **Effect size (Cohen's d)** — difference between groups in units of spread.
- **Multiple comparisons** — testing many things at once makes some look
  significant by luck; corrections (Holm, Benjamini–Hochberg) fix that.
- **Leakage** — test information sneaking into training, making results look too good.
- **Leave-one-session-out** — train on all sessions but one, test on that one, repeat.
- **Baseline** — the simple method any new method must beat.
- **Ablation** — remove one part and see how much performance drops.
- **Macro-F1 / balanced accuracy** — classification scores that treat every
  class fairly, even if one class has more examples.
- **Preregistration** — writing the plan before seeing the final results.
- **Natural experiment** — a real-world change (like a driver switching teams)
  that works like a controlled experiment.

















Written for: a fresh Claude session in your new repo that has no memory of this chat (and for you to read too).

The handoff file is ready: F1_PROJECT_CONTEXT.md, about 900 lines.

How to use it:

Create the new folder and repo. Copy this file into it and rename it to CLAUDE.md. Claude Code loads that file automatically in every session.
Open Claude there and say: "Read CLAUDE.md fully, then do the first-session checklist (section 18)."
Don't commit it to the autotune repo. It's untracked there (?? F1_PROJECT_CONTEXT.md), so just delete it after copying.
What's inside:

About you and how to work with you: teach first, then build; explainable Python; Claude never commits; your Windows setup quirks.
The decision log: every idea we considered, what you chose, and the corrections to the other assistant's plan.
The research plan: the research question and hypotheses H1–H5, data sources and their limits, and the Abu Dhabi 2024 pilot.
Every method with its reason and a worked example: the 22.5 m sample gap, the filter delay that shifts braking points by about 37.5 m, why FFT doesn't work on single corners, and locating events between samples.
How results will be tested and checked: testing on whole held-out race weekends, comparing against simple methods, and the team-change experiment.
A first-timer's guide to research: what already exists, what our new contribution could be, how to approach a faculty member (with an email draft), and venues.
CV and internship framing, a 10-phase roadmap, the folder structure, the coding rules carried over from Consonance, and a glossary of plain-English terms.
Things I found or added that weren't in the chat:

I checked the facts against the web. Brake is on/off and car data arrives at about 3.7 Hz. Norris was on pole by 0.209 s.
The closest existing work is a GitHub project that clusters drivers by corner. It only uses each driver's fastest lap and never tests on unseen data, never tries to identify drivers, and never looks at team changes. Those gaps are exactly where our project is different.
Three new proposals for you to approve:
Keep the whole 2025 season untouched as a final test, used only once at the end.
Build a synthetic-lap generator to measure how accurate our measurements are.
Always compare against a "lap time only" baseline.
Facts I couldn't verify are marked ⚠️ so the new session checks them first.
Sources:

FastF1 telemetry docs
OpenF1 docs
IJMO 2026 paper
roeeam9/F1-Clustering-Project
Formula 1: 2024 Abu Dhabi qualifying
Frontiers in AI 2025
arXiv 1911.08030
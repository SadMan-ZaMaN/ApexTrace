# 13. The web app (Phase 8, part 1)

> A local website that shows the research: an overview with the results, and a
> lap-compare tool for any two qualifying laps of 2023–2025.
> Code: `app/` (Flask + plain JavaScript + D3). Data export: `experiments/16_app_data.py`.
> Tests: `tests/test_app.py`.

## Run it

```powershell
.venv\Scripts\python.exe experiments\16_app_data.py   # only after results change
.venv\Scripts\python.exe -m app                       # then open http://127.0.0.1:5000
```

The lap-compare page needs the raw-sample Parquet files, which are gitignored
(`results/09_dataset/raw_samples.parquet`, `results/final/raw_samples_2025.parquet`).
On a fresh clone they're rebuilt by `experiments/09_build_dataset.py`. Without
them the page still shows lap times and a clear message.

## 1. How the pieces fit

```
browser                                      Flask (Python)
───────                                      ──────────────
GET /            ───────────────────────────► routes.home()      -> templates/index.html (+ headline.json)
GET /telemetry   ───────────────────────────► routes.telemetry() -> templates/telemetry.html
telemetry.js: GET /api/sessions  ───────────► AppData.session_index()      (sessions.json)
              GET /api/sessions/9658 ───────► one session: drivers, laps, corners, track outline
              GET /api/compare/9658?a=NOR:15&b=PIA:15
                                 ───────────► AppData.compare(): reads 2 laps from Parquet,
                                              gap curve + mini-sectors  -> JSON
D3 draws the charts and the map from that JSON.
```

- **Application factory** (`app/__init__.py`, `create_app`): builds the Flask
  object and loads the data once. Tests call `create_app(tmp_path)` with a fake
  results folder, which is why it takes the folder as an argument.
- **Blueprints** (`routes.py`): `pages` (HTML) and `api` (JSON, under `/api`).
- **Templates** (Jinja2): `base.html` has the header, nav and footer; each page
  fills `{% block content %}`.
- **Python serves data, the browser draws.** Same split as Consonance's Flask
  app.

**Why a separate export script?** The rule "every number comes from an
experiment script" also applies to the website. `16_app_data.py` reads the
results files and writes three small JSON files (`results/app/`). The app only
displays them. If a result changes, rerun the export.

**Safety:** URL inputs are checked (a session key and lap must be whole
numbers, a driver code three capital letters; anything else gets 400).
Data reaches Parquet only through filters, never as built strings. JavaScript
puts data on the page with `textContent`, never as HTML. The server listens
on 127.0.0.1 only (this computer).

## 2. The design: a timing screen, not a template

- **Colours:** dark asphalt base, white condensed type, hairline rules. **One
  red accent** for the interface: the active tab, the primary button, focus.
  **Team colours only where they identify a driver.** Timing semantics: **purple**
  = session best (as on F1 timing screens), green = supported, yellow = partly.
- **Second driver of the same team:** a lighter shade of the team colour, and
  **always dashed**. Two cues, so colour is never the only one (colour-blind safe).
- **Type:** Barlow and Barlow Condensed (SIL Open Font License), stored in
  `app/static/fonts/` so the app works offline. Not the official F1 font, which
  is proprietary.
- **The chamfer:** buttons, chips and the H1–H4 boxes have one corner cut at
  45°, like broadcast timing graphics (`.cut` in `app.css`, a CSS `clip-path`).
- **Imagery = data:** the only "pictures" are track outlines drawn from the
  timing feed's own X/Y, and the hero replays two real laps. No logos, no
  photos (the OpenF1 driver list has head-shot URLs; the export drops them on
  purpose).
- **Start lights:** while a comparison loads, five red lights come on one by
  one. With "reduce motion" switched on, nothing moves.
- **Licences:** D3 (ISC) and Barlow (OFL) are stored in the repo with their
  licence files.

## 3. D3 in five minutes

D3 doesn't draw charts for you. It gives you the parts:

- **Scale:** a function from data to pixels. `x = d3.scaleLinear().domain([0, 5230]).range([52, 900])`
  turns 2,615 m into the pixel in the middle. All five charts share **one** x
  scale, so a vertical line is the same place on track in every chart.
- **Axis:** `d3.axisLeft(y)` draws ticks and labels for a scale.
- **Line generator:** `d3.line().x(...).y(...)` turns an array of samples into
  an SVG path string. `d3.curveStepAfter` makes a gear hold its value until the
  next sample, as gear really does.
- **Zoom** here is just a new x domain (`[s − 300, s + 200]` for a braking zone,
  the same window the features use), followed by a redraw.

## 4. The signals lesson: drawing the gap honestly

The "gap" chart shows how far B is behind A at every point of the lap:
`gap(s) = time_B(s) − time_A(s)`, where `time(s)` is when the car was at
distance `s` (time interpolated over distance).

**The first version drew noise.** It used the projected track position `s_m`
and showed a ±0.1 s sawtooth. The measurement (2024 Abu Dhabi, NOR vs PIA,
official gap +0.209 s):

| Distance used | Jitter | Gap at the line |
|---|---|---|
| projected position `s_m` | 0.041 s | +0.290 s |
| integrated speed `d_m` | **0.007 s** | **+0.198 s** |
| fused (400 m window) | 0.005 s | +0.281 s |

**Why integrated speed wins:**
- **Integration is a low-pass filter** (in the frequency domain, 1/jω): it
  averages away sample-to-sample noise. The projected position scatters by
  about 3 m per sample, which is 0.04 s at 270 km/h.
- **Its error is a slow drift** (~12 m per lap), and that drift is nearly the
  same on both laps, so it **cancels in the subtraction**. This is common-mode
  rejection, like a differential amplifier rejecting noise that is common to
  both inputs.
- It is exactly 0 on the line (it starts at the start of the lap).
- The projected position has a lap-specific offset of a few metres. That
  doesn't cancel, and 5 m at the line is 0.08 s.

**What the charts' x axis uses:** the Phase 3 complementary filter over a whole
lap, `fused = d + moving_average(s − d)`. Integrated speed gives the fast detail,
and position gives the slow correction, so traces are smooth *and* corners sit
where they are on the track (`app/data.fused_distance`).

**The built-in check:** the notes under the map show where the gap curve ends
and the official lap-time gap, e.g. +0.198 s vs +0.209 s. If those disagreed
badly, the curve would be wrong, and you'd see it.

**Mini-sectors** ("who is faster where"): the lap is cut into 24 equal pieces,
and the gain in each is `gap(end) − gap(start)`. Gains below 0.02 s are shown
as "even": the alignment error (1.15 m) at 250 km/h is 0.017 s, so smaller
gains can't be told from noise. On 2024 Abu Dhabi, 12 of 24 pieces are even.
That's honest, not a failure.

## 5. Tests (no F1 data)

- **Synthetic laps with a known answer:** A drives 60 m/s everywhere, B drops to
  50 m/s from 800 to 1,100 m, so B loses exactly 300/50 − 300/60 = 1.0 s. Laps
  are sampled irregularly (~3.8 Hz on a 40 ms clock). Projected position gets
  a 5 m lap offset and 3 m scatter; integrated distance gets drift.
- **Full path:** a fake `results/` folder (one session, two laps, a tiny
  Parquet file) is served by the real Flask app, and `/api/compare` must return
  a gap of 1.0 s ± 0.02. **Checked to fail** when the gap is computed from
  projected position (the first version).
- **API behaviour:** bad input → 400, unknown session or lap → 404, missing raw
  files → 503 with a hint, and every page carries the "unofficial" notice.

## Viva soundbite

"The site is Flask serving JSON and D3 drawing it, with every number exported
by a script. The most interesting bit was the lap-gap chart. My first version
used track position and drew a ±0.1 s sawtooth of noise. Integrating speed is a
low-pass filter, and its drift is common to both laps, so it cancels. That
version matches the official gap within about 0.01 s, and the page shows that
check next to the chart."

---

# Part 2 (2026-10-19): Corner lab and Driver vs car

## 6. Corner lab (`/corners`)

One braking zone, every driver, every lap. Rows are drivers (team-colour bar,
code, team); **each dot is one lap**; the **white tick is the driver's median**;
the grey line is the field median. Order by value, or by team (teammates next
to each other).

- **Data:** the committed datasets (`results/09_dataset/dataset.csv.gz`,
  `results/final/dataset_2025.csv.gz`), passed through the research's own
  `dataset.clean`. The page shows exactly the rows the analysis used: a wet lap
  is gone, and an impossible braking point (after the marker) is empty (tested).
- **The error bar at the top** is the per-lap measurement error from the Phase 2
  simulation (e.g. ±2.5 m for brake onset at medium corners), drawn on the
  same axis. **Rule of thumb when reading it:** two drivers whose medians differ
  by less than that bar can't be told apart from one lap each. With 4 laps each,
  the error of a median shrinks (roughly by √4 = 2). But the driver's own
  lap-to-lap variation is bigger than the measurement error in every measured
  case, 2.9 to 28 times bigger (H1, `sd_over_measurement_error`), so the spread
  of the dots, not the instrument, usually limits what you can conclude.
- **The side panel** shows what the measurement means and how repeatable it is
  for that corner type (H1): lap-level ICC ("how much of the lap-to-lap spread is
  between drivers") and weekend-level ICC ("does a driver's place carry over to
  the next weekend"). Brake onset: lap ICC 0.45 at slow corners, but weekend ICC
  0.04, so "who brakes later" barely carries over between weekends.

## 7. Driver vs car (`/signatures`)

- **H3 chart:** per team, three marks on one accuracy axis: lap time only
  (grey ring, the baseline), raw lap statistics (orange diamond), corner features
  (blue dot). The line joins them, so you see the gain over lap time. Tabs switch
  between the 2025 test and the development seasons. Ferrari 2025 (HAM vs LEC)
  is the extreme case: raw lap statistics 0.87, corner features 0.62.
- **H4 scatter:** x = distance from a driver's 2025 signature to their own 2024
  signature, y = distance to their 2025 teammate's. **Above the diagonal = own
  past closer.** Changers are orange; drivers who stayed are blue (the
  exploratory control); Colapinto is hollow (not preregistered).
- **Fingerprint (heat strip):** click a driver. Three rows: their 2024
  signature, their 2025 signature, their 2025 teammate's. 30 cells = 10
  measurements × 3 corner types, each a z-score against the 2024 field (blue =
  below the average driver, red = above). For Hamilton the 2025 row looks a bit
  more like Leclerc's than like his own 2024 row: distance 0.99 vs 1.04.
- **The pictures can't drift from the numbers:** the export script rebuilds
  these signatures with the exact H4 steps and **refuses to write the file**
  unless every distance matches the frozen results (to 0.001).

## 8. Colours, checked

The chart colours were checked with a colour-blindness validator (the dataviz
palette checker): blue `#3987e5` and orange `#d95926` on the dark background
pass every check, including separation under colour-vision deficiency. Grey is
reserved for the baseline (lap time), and each series also has its own
**shape** (ring, diamond, dot), so nothing relies on colour alone.

---

# Part 3 (2026-10-20): the replay, and making every chart readable

## 9. Replay (overview and Lap compare)

`app/static/js/replay.js` is a small clock: `t` (seconds into the lap) advances with
real elapsed time × the speed (×1, ×2, ×4), and every change redraws the cars.
Seeking just sets `t`: the timeline slider, a click on the track (the nearest sample
of car A, then its time), or a click on a chart (the time car A was at that distance).

On Lap compare the replay also draws a vertical line in every chart at each car's
position (A solid, B dashed). The space between the two lines is how far B is behind
**in metres**; the readout gives the same gap **in seconds**. Both are useful: at
300 km/h, 0.1 s is about 8 m, but in a slow corner it is only 2–3 m.

**Honesty note:** positions arrive about four times a second; between samples the car
moves in a straight line at constant speed (interpolation). The replay shows the
measured positions joined smoothly, not a frame-by-frame recording.

**Reduced motion:** if the viewer's system asks for less motion (Windows: Accessibility
→ Visual effects → Animation effects off), nothing starts by itself; the button offers
the replay.

**A bug found while building it:** the overview's live gap still used the projected
position `s` (the mistake fixed on Lap compare in Part 1), so it read +0.05 to +0.47 s
during the lap instead of −0.06 to +0.22 s, and never showed Piastri briefly ahead at
C3. It now uses integrated distance `d`, like everything else.

## 10. Readability checklist (what every chart now has)

A professor will look at a chart for ten seconds. In that time it must answer: what is
on each axis (with units), which mark is which (a legend, never colour alone), how many
data points, and how precise. Added in this part: a line legend on Lap compare (solid =
A, dashed = B, and whether dots are measured samples), a key on the Corner lab (dot,
median tick, field median, error bar), and on the results board a link from every
hypothesis to the page that shows its data.

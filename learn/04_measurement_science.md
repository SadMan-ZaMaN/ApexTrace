# 4. Measurement science (Phase 2): how accurate is each number?

> On real data we never know where the braking point *really* was, so we can't
> know our error. On a synthetic corner we do. Phase 2 builds realistic fake
> corners with a known truth, degrades them exactly like the feed, and measures
> each estimator's **bias** (average error) and **spread** (standard deviation
> of the error). This is contribution **C1**.
>
> Analogy from Consonance: you test a pitch detector on a sine of known
> frequency before trusting it on a voice.

Code: `synthetic.py`, `resampling.py`, `filters.py`, `events.py`.
Experiments: `02_group_delay_demo.py`, `03_synthetic_errors.py`.

## 4.1 The synthetic corner (`synthetic.py`)

`make_true_corner(params)` simulates one corner every 2 ms (500 Hz):

1. **Straight:** full throttle. Acceleration = min(traction limit 1.3 g,
   power/(mass × speed)) − drag. At 324 km/h the car still gains ~1.6 m/s².
2. **Brake ramp:** braking force builds up over 0.05–0.25 s.
3. **Full braking:** deceleration = 1.8 g + downforce term (∝ v²) + drag:
   5.9 g at 324 km/h, ~2.2 g at 100 km/h. A 324 → 68 km/h stop takes
   ~110–125 m, like the real Turn 6.
4. **Taper:** brake force eases off linearly (brake still "on").
5. **Coast:** brake off, throttle closed.
6. **Throttle:** throttle(t) = 100 × (1 − e^(−t/τ)), a first-order step
   response (an RC circuit charging), τ ≈ 0.3–0.45 s.
7. **Exit:** keep accelerating.

The truth stores the exact time and distance of each event. `random_corner_params`
varies the driver behaviour from lap to lap (entry ± 4 km/h, apex ± 3 km/h,
ramp, taper, coast, τ ± 20 %), so we never test at one exact setting
(Consonance lesson: test at realistic, varied values).

`degrade_like_feed(truth, intervals, probabilities, rng)` samples it like the
feed: a random start offset, then intervals drawn from **the real interval
distribution** (`results/01_data_pilot/interval_histogram.csv`), speed rounded
to 1 km/h, throttle to 1 %, brake on/off. Each call is a new "lap" with a new
sampling phase.

## 4.2 Filters, the Z-transform and group delay (`filters.py`)

| Filter | Difference equation | H(z) | Poles / zeros | Delay |
|---|---|---|---|---|
| Moving average, N = 5 | y[k] = (x[k] + ... + x[k−4]) / 5 | (1/5)(1 + z⁻¹ + ... + z⁻⁴) | 4 zeros on the unit circle, no poles | (N−1)/2 = 2 samples |
| EMA | y[k] = αx[k] + (1−α)y[k−1] | α / (1 − (1−α)z⁻¹) | one pole at z = 1 − α | (1−α)/α samples at DC |
| Butterworth (order 2) | `scipy.signal.butter` | two complex poles | maximally flat passband | ~0.46 s at 0.5 Hz, 4 Hz grid |

**Group delay** = how long each frequency is delayed (−dφ/dω). A causal filter
only sees the past, so it lags. **Zero-phase filtering** (`filtfilt`): filter
forward, then backward. The backward pass cancels the delay: response |H|²,
phase 0.

**What the demo found (`results/02_group_delay/`):**
- In mid-braking, causal filters shift the braking point by **+14 to +25 m**;
  zero-phase only +2 to +3 m. Delay × speed: 0.46 s × ~55 m/s ≈ 25 m.
- **But:** at the *onset* of braking (a sharp kink in the speed curve),
  zero-phase smoothing still moves a threshold detector **23–36 m early**. It
  removes the delay, not the *smearing* of a sharp event: the smoothed curve
  starts dropping before the true onset, because it averages in future samples.
- **Lesson** (Consonance lesson 4): smoothing used to *find* an event must not
  bias the *measured* value. So events are located on the raw samples with
  model-based estimators (4.4), not by thresholding smoothed signals.

## 4.3 Differentiation amplifies noise

The first difference H(z) = 1 − z⁻¹ has |H(e^{jω})| = 2|sin(ω/2)|: 0 at DC,
largest at Nyquist, so it is a **high-pass filter**. Speed rounding error has
std 0.278/√12 = 0.080 m/s; a difference over 0.27 s therefore has noise
√2 × 0.080 / 0.27 = **0.42 m/s²** (0.04 g), even if the true deceleration is
constant. Measured on synthetic laps: 0.49 m/s².

**Cutoff from the real spectrum:** the spectrum of real speed (30 laps, 4 Hz
grid) falls steeply, then flattens at 14× the rounding floor above a **knee at
1.19 Hz**. A flat spectrum behaves like noise: here, interpolation and
aliasing errors from irregular sampling, not rounding. → Deceleration traces
for figures are smoothed zero-phase at **1 Hz**.

## 4.4 Locating events between samples (`events.py`)

| Event | Naive | Refined | Idea |
|---|---|---|---|
| Brake onset | first "on" sample | **breakpoint of the speed curve, inside the off→on interval** | fit two straight lines (flat, then falling) with a continuous joint at tb; try tb on a 2 ms grid; keep the least-squares best |
| Apex / min speed | lowest sample | **parabola through the 3 lowest samples** | vertex of the exact parabola (uneven spacing is fine), like Consonance's parabolic peak |
| Throttle 10 %, 99 % | first sample above | **linear interpolation of the crossing** | where the straight line between the two samples crosses the threshold |
| Entry/exit speed | — | linear interpolation at a fixed point | |

## 4.5 The Monte Carlo (`03_synthetic_errors.py`)

*Monte Carlo* = answer a question by simulating it many times with random
inputs. 1,000 laps per corner type, every estimator, error = estimate − truth,
in metres along the true track.

| Feature | Naive | Refined (chosen) |
|---|---|---|
| Brake onset | bias **+12.5 m** (always late), std 8.1 | breakpoint in interval: bias +3.2, std **2.7 m** |
| Brake onset, middle of interval | — | unbiased, std 7.7 m (= the 7.7 m predicted in Phase 1) |
| Minimum speed | +0.3 to +0.4 km/h (always too high) | parabola: bias ~0.05, std 0.35 km/h |
| Apex position | std 1.8–4.3 m | parabola 3: ~1 m |
| Throttle pickup | bias +2.6 to +6.9 m | interpolated: bias −0.9 to −3.1, std 1.0–2.8 m |
| Peak deceleration | **all estimators −6 to −20 m/s² too low** | dropped; use mean deceleration instead |

(Heavy braking unless a range is given; full table in `error_table.csv`.)

Why is the breakpoint biased +3 m? The brake force ramps up over 0.05–0.25 s,
so the "bend" in the speed curve sits about half a ramp after the true onset.
If both drivers ramp alike, it cancels in their difference.

**Averaging (dithering):** the sampling grid lands at a random place each lap,
so errors are independent between laps, and averaging N laps shrinks the
spread like 1/√N: measured 2.70 m (1 lap) → 0.68 m (16 laps), matching
2.71/√16 = 0.68. The bias does not shrink.

**Irregular vs regular sampling:** irregular sampling costs ~11 % more error
than regular sampling at the same mean rate (the inspection paradox again).

**Negative result:** peak deceleration can't be measured from this feed. The
true peak lasts a fraction of a second, too short for ~4 samples/s, and
smoothing makes it worse. Reporting this is part of the contribution.

## Words used

- **Bias:** average error (systematic: doesn't shrink by averaging).
- **Standard deviation (std, spread):** typical size of the random error.
- **RMSE:** sqrt(bias² + std²): overall typical error.
- **Estimator:** a rule that turns data into a number (e.g. "middle of the interval").
- **Monte Carlo:** many random simulations to measure a distribution.

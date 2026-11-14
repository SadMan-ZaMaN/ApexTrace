# A learned model on the corner traces: a plan

**Status: a plan, written 2026-11-15. Nothing here has been built or run.** It is the optional
last phase of the project, postponed on purpose (`docs/decisions.md`, 2026-11-13): no unused test
season is left, the data are small for a neural network, and the author wants to learn machine
learning first, so that every line of the model can be explained. This page fixes the design now,
so that the later work starts from a plan and not from the results.

## 1. The question

H3 asked: on a weekend the model never saw, which of the two teammates drove this lap? It was
answered with hand-designed measurements (30 corner features) and a simple model (logistic
regression). This plan asks the same question with a model that reads the traces around each
braking zone and finds its own patterns:

> Does a small neural network on the corner traces identify teammates better than the corner
> features, the whole-lap statistics, and both together, under exactly the same held-out protocol?

## 2. The model, in signals terms

A one-dimensional convolutional neural network (CNN) is a stack of **learned FIR filters**. Each
layer convolves its input with a few short filters, applies a simple non-linearity (ReLU: negative
values become 0) and keeps the strongest response in each small neighbourhood (max pooling). Our
features are measured with rules designed by hand (for example, brake onset is where the speed
curve bends from flat to falling fast); a CNN learns its filter coefficients from labelled examples
instead. The plan keeps it tiny:

| Part | What it does | Weights |
|---|---|---|
| Convolution 1 | 8 filters, 5 grid points long (20 m), over the 4 input channels | 8 × 4 × 5 + 8 = 168 |
| Convolution 2 | 16 filters, 5 grid points long, over the 8 outputs of layer 1 | 16 × 8 × 5 + 16 = 656 |
| Average over the window | one number per filter: a 16-number summary of the corner | 0 |
| Lap summary | the mean corner summary per corner type (slow, medium, fast): 48 numbers | 0 |
| Decision | logistic regression on the 48 numbers, as in H3 | 48 + 1 = 49 |
| **Total** | | **873** |

The lap summary copies how the 30 corner features become one row per lap (the mean over the lap's
corners of each type). If a lap has no usable corner of a type, those 16 numbers are filled with the
training median, as H3 does for a missing feature. A few hundred laps per team can train a model
with a few hundred weights; a model with millions of weights would only memorise them.

## 3. The input

Only the corner passes that the features use: the same "usable" rule (no interval longer than
0.6 s between samples inside the window) and the same cleaning (dry tyres only, minimum speed at
least 40 km/h). For each pass, four channels on a grid from 300 m before to 200 m after the corner
marker, every 5 m (101 points), on the same position-corrected track coordinate as the features:

- speed and throttle, interpolated linearly between the measured samples;
- gear and the brake flag (on/off), each held from one sample to the next (a gear of 4.5 means
  nothing).

Then the same field-relative step as the features: from each channel, subtract the median of all
drivers at that grid point, corner and session. Without it the network would mostly learn which
track it is looking at. (This step uses no driver labels, so it does not leak the answer.)

The feed delivers about 3.77 samples per second, roughly one every 22 m at 300 km/h. A 5 m grid
**adds no information**: interpolating between samples can't create detail the samples don't have.
It only gives every corner the same shape, which a CNN needs. A 2023–2024 session has 5–11 braking
zones, so a lap gives 5–11 corner inputs.

## 4. The protocol: unchanged from H3

- **Pairs:** per team-season, the two drivers with most laps, on the weekends both drove, at least
  5 weekends. Development has 20 team-seasons, with 72–249 laps and 8–22 weekends each. (A weekend
  here is its one qualifying session.)
- **Held out by weekend:** train on all weekends but one, predict the one left out, repeat for
  every weekend. Never a random split of laps: laps of the same weekend share the track, weather
  and set-up, so a random split would let the model recognise the weekend, not the driver.
- **Everything learned from training weekends only:** the channel scaling, the missing-value
  medians, the stopping point and the weights.
- **Score:** balanced accuracy (0.5 = guessing), per team-season, then the mean over team-seasons.
- **Shuffled labels** (the two drivers' labels shuffled within each weekend) must score about 0.5,
  or something leaks.

## 5. The baselines it has to beat

Balanced accuracy, mean over team-seasons. Development: `results/12_identification/summary.json`;
2025: `results/final/summary.json`; "both together" for both: `results/32_combined_inputs/summary.json`.

| Input | Development 2023–2024 (20 team-seasons) | 2025 (10 teams) |
|---|---|---|
| Lap time only | 0.565 | 0.575 |
| Corner features (30) | 0.685 | 0.662 |
| Whole-lap statistics (5) | 0.729 | 0.680 |
| Both together (35) | 0.750 | 0.705 |

The strongest is "both together". A learned model is only interesting if it beats that.

## 6. Settings fixed before any result

Chosen now, on principle. They may be changed only on development data, and every change is
written in `docs/decisions.md` before the next run:

- Adam optimiser, learning rate 0.001, weight decay 0.001, batches of 32 laps;
- at most 200 passes over the training data; one training weekend (chosen with the seed) is held
  back, and training stops when its score has not improved for 20 passes; the weights from its
  best pass are kept;
- 5 random seeds per team-season, results averaged; the spread over seeds is reported;
- CPU only; PyTorch at a pinned version.

## 7. A fair test: the next unseen season

2025 and 2026 have both been used once. The confirmatory test needs a season nobody has looked at,
handled exactly like 2025 and 2026:

1. develop on 2023–2024 and freeze everything; 2025 and 2026 may then be used as exploratory checks
   (2026 has the same rules as 2027; its baselines would be computed first, in the same way);
2. write the test plan as preregistration Part D (the comparison, the decision rule, what happens
   if a session has no data) and commit it;
3. lock 2027 in the code with its own switch, as 2025 and 2026 are locked (`FROZEN_SEASONS` in
   `src/apextrace/data_loading.py`);
4. after the season, run once on the 2027 qualifying sessions.

**Decision rule (to go into Part D):** the CNN is better if its mean balanced accuracy is higher
than "both together" and a one-sided Wilcoxon signed-rank test over team-seasons gives p < 0.05.
One season gives only about 10 team pairs (2025 had 10), so only a clear gain can pass; a small
one would read "not shown", which is not the same as "no gain".

## 8. What each outcome would mean

- **The CNN is not better than "both together".** What identifies a teammate in this feed is
  already in the hand-made measurements and the simple statistics. That supports the project's
  main message: measure carefully, and simple, explainable features go a long way.
- **The CNN is better.** The trace shapes hold driver information our measurements miss. The next
  step is to find out where: which metres of the window change the decision most (a saliency map),
  checked against what the feed can resolve (nothing faster than about 1.9 Hz).
- **The CNN is worse than its own inputs summarised by hand.** Too little data per team for even a
  tiny network; reported as it is.

## 9. Risks and how they are handled

- **Overfitting** (72–249 laps per team-season): the 873-weight model, early stopping on a
  held-back weekend, and the gap between training and test scores reported for every team-season.
- **Leakage:** every scaling, filling and stopping decision is learned on training weekends only;
  the shuffled-label check must stay near 0.5.
- **Gaps in the data:** the same 0.6 s rule as the features. The 2026 feed has longer gaps (up to
  23 s, `docs/engineering_notes.md`), so more corner passes drop out there; the count is reported.
- **Randomness:** seeds fixed and reported; a result that appears for one seed only is not a result.
- **A heavy dependency:** PyTorch is installed only for this phase; the main tests keep running
  without it (the model's own tests are skipped when it is missing).

## 10. Steps, in order

1. Export the corner traces (a new experiment): one row per usable clean corner pass, the 4 × 101
   grid, built from the saved raw samples (they include gear) with the features' own coordinate
   code, saved locally like the raw samples.
2. A known-truth test on synthetic laps: plant a driver-specific shape (one driver lifts 20 m
   earlier at fast corners) and check that the CNN finds it, and scores about 0.5 with shuffled
   labels.
3. The model and its training loop, in plain PyTorch, every function with a docstring and a worked
   example, like the rest of the code.
4. The leave-one-weekend-out harness on the same pairs as H3, checked first to reproduce the H3
   baselines (as `experiments/32_combined_inputs.py` does).
5. The development run, the comparison table, a write-up labelled exploratory.
6. Preregistration Part D, the 2027 lock, the one-time run.

## 11. What to learn first

In this order, each step building on the last: logistic regression (the model H3 already uses) and
how gradient descent fits it; overfitting, validation, and why splits must follow the weekends; a
small fully connected network; convolutional layers, which are the convolution and FIR filters of
a signals course with learned coefficients; then PyTorch (its official tutorials at pytorch.org).
With that, every line of steps 1–6 can be written and explained.

# Viva questions, with answers

Cover the answer, say yours out loud, then check. Grouped by chapter.

## Chapter 1: the big picture

**Q: What is your research question, in one sentence?**
Whether signal-processing methods can extract repeatable, interpretable
corner-level driving signatures from low-rate public F1 telemetry, identify
drivers on unseen race weekends, and separate the driver from the car.

**Q: Why isn't this just another F1 dashboard?**
Because every number has a measured error bar (Phase 2), the statistics are
written down before they are run (preregistration), identification is tested
on whole race weekends the model never saw, and team changers are used to
separate driver from car.

**Q: What would count as a negative result, and would it still be useful?**
E.g. "corner features are not repeatable enough to identify drivers better than
lap time alone". Yes: if measured carefully, it tells others not to over-read
public telemetry. We already have one: peak deceleration can't be measured.

**Q: Why freeze the 2025 season?**
If you look at test data while developing, you tune the method to it without
meaning to, and the final number is too optimistic. The code refuses to load
2025 unless `FINAL_TEST=1`.

## Chapter 2: setup

**Q: Why does pyproject.toml list `fastf1` without a version, but requirements.txt with `==3.8.3`?**
pyproject says what the package needs; requirements records exactly what we
used, so the results can be reproduced.

**Q: What does `pip install -e .` do?**
Installs the package in editable mode: `import apextrace` works from any
folder, and code changes apply without reinstalling.

**Q: Why do tests never download F1 data?**
So they run offline, fast and identically on any computer (including CI),
and test the logic, not the internet.

**Q: What bug did the real data reveal in the lap selection?**
Comparing laps with the driver's session-best (soft-tyre) lap cut 6 of Norris's
7 medium long-run laps but only 2 of Piastri's, because his soft lap was
0.23 s quicker. Fix: compare with the best lap of the same stint.

## Chapter 3: the data

**Q: What is the sampling rate of FastF1 car data?**
3.77 samples per second on average, but irregular: intervals of 4–14 ticks of a
40 ms clock (0.16–0.56 s), plus occasional feed pauses of 0.6–1.4 s.

**Q: How far apart are samples at 300 km/h?**
13 to 47 m, 22 m on average. Up to 113 m across a feed gap.

**Q: What's the Nyquist frequency, and what does it rule out?**
About 1.9 Hz. Anything faster (vibration, steering corrections, brake
modulation) can't be seen.

**Q: If an event is uniform inside a 0.27 s interval and you report the middle, what's the error?**
0.27/√12 = 0.078 s; at 300 km/h, 6.5 m.

**Q: Why is the real error larger than that (7.7 m)?**
The inspection paradox: with irregular intervals, an event is more likely to
fall in a long interval, so the error is weighted by interval length:
sqrt(Σ T³ / (12 Σ T)).

**Q: Can you analyse racing lines from the X/Y positions?**
No. Laps lie as close to the teammate's path as to their own (median 0.06 m),
so the feed is probably smoothed or matched to a track model.

**Q: How did you choose the three corners, and why that way?**
By a fixed rule on the pole lap before comparing drivers: biggest speed drop
(T6), highest minimum speed (T9), and minimum speed closest to halfway (T5).
A rule chosen in advance can't cherry-pick corners where the drivers differ.

## Chapter 4: measurement science

**Q: Why build synthetic laps at all?**
On real data the truth is unknown, so error can't be measured. On synthetic
laps degraded exactly like the feed, it can.

**Q: What is group delay, and how big is it for a 5-sample moving average on a 4 Hz grid?**
How long a filter delays each frequency. (N−1)/2 = 2 samples = 0.5 s, which is
~35 m at 250 km/h.

**Q: Where are the poles and zeros of an EMA with α = 0.3?**
One pole at z = 0.7 (no zeros apart from the origin). Inside the unit circle, so stable.

**Q: What does filtfilt do, and what doesn't it fix?**
Filters forward then backward: zero phase, so no delay, response |H|². It
doesn't fix smearing: a sharp event still spreads both ways, so a threshold
detector at the braking onset fires 23–36 m early.

**Q: Why does differentiation need care?**
The first difference is a high-pass filter (|H| = 2|sin(ω/2)|), so it amplifies
noise. 1 km/h rounding gives ~0.42 m/s² of fake deceleration noise.

**Q: Which brake-onset estimator did you choose, and how accurate is it?**
The breakpoint of a two-line fit to speed, constrained to the brake off→on
interval: bias +3.2 m, std 2.7 m per lap at the heavy-braking corner (the
naive first-on sample: +12.5 m bias, 8.1 m std).

**Q: Why is the breakpoint biased, and does it matter for teammate comparisons?**
Brake pressure builds up over ~0.05–0.25 s, so the bend in speed appears half a
ramp late. If both drivers ramp alike, the bias cancels in the difference; if
not, it's a real style difference we can't separate.

**Q: What happens to the error when you average N laps?**
The random part shrinks like 1/√N (2.70 m → 0.68 m for 16 laps), because the
sampling phase is random from lap to lap (dithering). The bias doesn't shrink.

**Q: Which feature could you NOT measure, and why?**
Peak deceleration: the true peak is too short-lived for ~4 samples/s; every
estimator reads 6–20 m/s² too low. We use mean deceleration instead.

## Chapter 5: alignment

**Q: Why not just use the distance FastF1 gives you?**
It comes from integrating speed, so it drifts (up to ~13 m relative to X/Y
at Turn 9) and jumps at feed gaps, which is as big as the effects we measure.

**Q: How does projecting onto a reference path work?**
For each position sample, find the nearest point on the reference lap's X/Y
polyline (project onto each segment, clamp, keep the closest) and read off the
distance along the path there.

**Q: Then why fuse with integrated speed?**
Projected positions have ~3 m of noise along the track (likely timestamp
jitter), while integrated speed is smooth over short stretches but drifts. The
complementary filter keeps the smooth shape of integrated speed and pins it with
one weighted-average offset per corner window: noise ~1.15 m.

**Q: Why weight by 1/speed²?**
If the error is speed × timing error, its variance grows with speed²;
inverse-variance weighting trusts the precise (slow) samples more. It cut the
offset noise from 1.46 to 1.15 m.

**Q: How did you measure the offset noise without knowing the truth?**
Half-split: offsets from the first and second half of the window's samples;
std(difference)/2 ≈ the noise of the full-window offset.

**Q: Why not align each corner by cross-correlating the braking zones?**
It would absorb the very braking-point differences we want to measure.

## Chapter 6: features

**Q: Why mean deceleration instead of peak deceleration?**
The Monte Carlo showed peak deceleration reads 6–20 m/s² too low with every
estimator (the peak is too short for ~4 samples/s). Mean deceleration comes
from two well-measured events.

**Q: What's the cleanest comparison in the pilot, and what does it show?**
Turn 5: both drivers have the same 4 laps. Norris's mean brake onset is
7.42 m later (SE 2.11 m). That's descriptive, not a tested claim.

**Q: What is a confounder in your pilot?**
Qualifying segment: Piastri's usable Turn 6 laps are both from Q3 (more grip),
Norris's include Q1 and Q2.

## Chapter 7: statistics

**Q: What is a preregistration and how do you prove it came first?**
The dated analysis plan, committed to git before running the tests; the commit
date is the proof, and the script refuses to run otherwise.

**Q: Why can't the pilot produce a significant result?**
With 4 vs 4 laps an exact permutation test has 70 splits, so p ≥ 2/70 = 0.029;
after Benjamini–Hochberg over 27 tests, 16 tests would need that minimum.

**Q: Holm vs Benjamini–Hochberg?**
Holm controls the probability of any false positive; BH controls the expected
share of false discoveries among the discoveries (less strict).

**Q: What does ICC tell you?**
The share of total variation that is between drivers rather than lap to lap.
Near 1: stable, distinctive; near 0: noise.

**Q: What is statistical power and what did it tell you?**
The chance to detect a real effect. With 4 vs 4 laps, only effects of
d ≥ 2.38 have 80 % power; 20 laps per driver would bring it down to 0.91.

## Chapter 8: data sources

**Q: Your main data source stopped working mid-project. What did you do?**
Turned on debug logging to see the real HTTP errors (401 from the F1 archive),
checked the alternative (OpenF1) serves the same feed sample by sample (320/320
car samples identical on the pole lap), rebuilt the lap table, and validated
end to end against the cached FastF1 data: identical kept laps for 20/20
drivers, features within 0.23 m.

**Q: Why match deleted laps by lap time and not lap number?**
Race control's lap number in the message doesn't match the timing feed's
numbering (PIA's deleted 1:22.985 is his lap 12, the message says "LAP 13");
the lap time is unambiguous.

**Q: What is a regression check?**
Re-running an existing result after changing code, to show it didn't change
(the pilot features were identical, 90 of 90 rows, after splitting track.py).

## Chapter 9: the multi-season dataset

**Q: Why not download a ready-made F1 CSV?**
Public F1 datasets have results and lap times, not within-corner telemetry.
Lap-time data only supports the "lap time only" baseline; the research question
needs features from raw ~4 Hz signals, so the dataset is built from them.

**Q: How do you find corners on a track you've never seen?**
On the session's fastest lap: speed dips that are the slowest point within
±100 m, at least 50 km/h below the fastest point in the 500 m before, and whose
analysis window fits inside the lap. Types by minimum speed (< 120, 120–200,
≥ 200 km/h).

**Q: What are field-relative features and why use them?**
Value minus the median of all drivers at the same corner and session. Raw values
mostly encode the track; field-relative values compare the lap with everyone
else at the same place on the same day.

**Q: What did you do with outliers?**
Listed them, found the causes (wet laps, broken data, corner sequences,
flat-bottomed corners), and wrote cleaning rules before any modelling:
dry only, broken rows dropped, impossible values set to missing per feature.

## Chapter 10: repeatability and identification

**Q: What's the difference between your lap-level and weekend-level ICC?**
Lap level: groups are (session, corner, driver), so it asks whether laps of one
driver at one corner on one day resemble each other more than other drivers'.
Weekend level: groups are each driver's session means within a season, so it asks
whether the driver's offset persists across weekends. Braking points: 0.45
vs 0.04 (slow corners), distinctive on the day but not persistent.

**Q: How did you bootstrap the ICC, and what went wrong first?**
Resample the independent units: whole sessions for the lap level,
driver-seasons for the weekend level. Resampling sessions for the weekend level
duplicated identical driver means, inflating the ICC; estimates fell outside
their own intervals, which revealed the mistake.

**Q: How do you know your identification has no leakage?**
Leave-one-session-out with an assert that no session is on both sides,
pipelines fitted on training data only, and a shuffled-label check that gives
0.500, i.e. chance.

**Q: Did your features beat the baselines?**
Teammates: 0.685 vs 0.565 for lap time only (18 of 20 team-seasons, Wilcoxon
p = 0.0001), but not the raw-statistics baseline (0.729, p = 0.14), whose power
comes mostly from the share of time with the brake flag on: either a driving
habit or the car's brake-sensor threshold; H4 is needed to tell.

**Q: Which features carry the signature?**
Throttle features (removing them drops accuracy most, 0.685 → 0.633), and
minimum speed and throttle persist best across weekends (H1).

## Chapter 11: driver vs car

**Q: How can you tell a driver's signature from the car's?**
Compare a driver's signature with their own from another season and with their
teammate's (same car). In 2023 → 2024 the own signature was closer for 17 of 20
drivers (sign test p = 0.0013). The strongest test is drivers who changed teams
(2025): own previous signature (different car) vs new teammate (same car).

**Q: Why can H4 only succeed with all five changers?**
A one-sided sign test with 5 drivers has a smallest p of 1/32 = 0.031; 4 of 5
gives 0.19. Stated in the preregistration before the test.

**Q: How did you make sure the final test used the same method as development?**
Shared code moved into the package with regression checks (identical results),
a dry run of the final script on development data, and guards that refuse to run
without the committed preregistration, FINAL_TEST=1, or if it has run before.

## Chapter 12: the final test on 2025

**Q: What happened in the final test?**
H3 replicated: corner features identified which teammate drove a lap better
than lap time (0.662 vs 0.575, 8 of 10 teams, Wilcoxon p = 0.027), but still not
better than whole-lap statistics (0.680). H4 was not supported: only 2 of 5 team
changers stayed closer to their own 2024 signature than to their new teammate
(sign test p = 0.81).

**Q: The final run crashed the first time. Isn't rerunning cheating?**
Not here, because no result had been produced: it crashed while downloading
(OpenF1 has no laps for 2025 Baku). The fix was the smallest possible (skip a
session without laps), a test was added, and the deviation was written down
before the rerun. Both logs are kept. A rerun after seeing results would need
to be reported as a second result next to the first.

**Q: You forgot a team changer in your preregistration. What did you do?**
Kept the primary test exactly as preregistered (5 drivers), recorded the
mistake as a deviation, and showed its effect separately: with Colapinto 3 of 6,
and with 2 of 5 already known it could only have been 2 or 3 of 6, so the
conclusion couldn't change. Lesson: derive such lists from the data with a rule.

**Q: Does "H4 not supported" mean the signature is the car?**
No, and that was written in the preregistration. Drivers can adapt to a new
car. Also, the comparison isn't symmetric (own signature one year apart vs
teammate on the same weekends). A control on drivers who stayed shows their own
signature still wins 8 of 10 times; changers 2 of 5; Fisher's exact p = 0.25,
too few changers to tell.

**Q: What is Fisher's exact test?**
A test for a 2 × 2 table of counts (here: changers/stayers × own closer/teammate
closer). It asks: if both groups had the same success rate, how likely is a
split at least this uneven? It is exact (no large-sample approximation), which
suits small counts like 5 and 10.

## Chapter 13: the web app

**Q: How is the web app built?**
Flask serves HTML pages and a small JSON API; plain JavaScript with D3 draws the
charts in the browser. Every number shown comes from results files, gathered by
an export script (`experiments/16_app_data.py`), so the app never computes a
research result itself.

**Q: Your lap-gap chart: why integrate speed instead of using track position?**
Projected position scatters by about 3 m per sample and has a lap-specific
offset of a few metres, so the gap came out as a 0.04 s sawtooth and ended 0.08 s
off at the line. Integrated speed is smooth (integration is a low-pass filter),
and its slow drift is almost the same on both laps, so it cancels in the
difference (common-mode rejection). It ended within about 0.01 s of the official
lap-time gap, and the page shows that check.

**Q: What is the complementary filter doing on the charts' x axis?**
fused = d + moving_average(s - d): integrated speed for the fast detail,
position for the slow correction of its drift. Same idea as Phase 3, over a whole lap.

**Q: Why do 12 of 24 mini-sectors say "even"?**
A gain smaller than 0.02 s can't be told from the measurement error (1.15 m
alignment at 250 km/h is 0.017 s), so it is shown as even rather than invented.

**Q: In the Corner lab, how do you know whether two drivers really brake at different points?**
Compare the gap between their medians with the measurement-error bar at the top
of the chart (the per-lap error from the Phase 2 simulation) and with how much
each driver varies lap to lap. And check the weekend-level ICC: for brake onset
it is about 0.04, so even a real difference this weekend says little about the next.

**Q: How do you make sure the Driver vs car charts show the frozen results?**
The export script rebuilds the signatures with the same steps as the final test
and stops with an error unless every distance matches the frozen results files
to 0.001. The page never recomputes a test.

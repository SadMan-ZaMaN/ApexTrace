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

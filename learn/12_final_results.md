# 12. The final test on 2025, and what the project found (Phase 7)

> The one-time, preregistered test of H3 and H4 on the frozen 2025 season.
> Code: `experiments/14_final_2025.py` (the test), `experiments/15_final_exploratory.py`
> (figures + exploratory checks). Results: `results/final/` (frozen),
> `results/15_final_exploratory/`. Plan: `docs/preregistration.md`, Part B.
> Deviations: `docs/preregistration_deviations.md`.

## 1. What a "frozen test set" run looks like in practice

For two years of data (2023–2024) we were allowed to try things, tune things
and make mistakes. 2025 was locked from the first day. The final run:

1. Sadman committed the preregistration (commit `225385c`), which fixed the
   data, the features, the models, the tests and the decision rules.
2. The script refused to run unless that file was committed and unchanged,
   `FINAL_TEST=1` was set, and `results/final/` didn't exist.
3. It downloaded the 2025 qualifying sessions, built them with exactly the
   development code, and ran the two primary tests. The numbers are now
   frozen: nothing about them may be changed or tuned.

**Analogy:** a sealed exam paper. You can practise on old papers as much as you
like, but you open the real one once, and you hand it in as it is.

## 2. Something went wrong, and how it was handled

The first attempt **crashed** at session 17 of 24 (2025 Baku). OpenF1 simply
has no lap rows for that session: the server answers 404, "No results found",
although it has the tyre stints, race-control messages and driver list. Every
one of the 47 development sessions had laps, so the code never met this case.

**Was any result seen?** No. The crash happened while downloading, before
any model or test ran, and `results/final/` was empty. That matters: if a
result had been seen, a "fix and rerun" could be a hidden second chance.

**What was done, in this order:**
1. Found the cause (the 404) and made the smallest possible fix: `lap_table`
   returns an empty table, and the session is skipped. The committed code
   already had a "no laps → skip" branch one step later; it just never got
   that far.
2. Wrote a test that **fails on the old code** with the same error.
3. **Wrote the deviation down before rerunning** (dated, with what was and
   wasn't seen). Order matters: written after the results, it would be much
   less convincing.
4. Downloaded all remaining sessions first (download only, no analysis), so
   any other data surprise would show up there and not as a third attempt.
5. Reran (attempt 2). Both logs are kept in `results/final/`.

**Lesson for any one-time run:** download everything first, check it, and
only then analyse. That is now in the CLAUDE.md bug history.

**Data in the end:** 23 of 24 sessions built; Las Vegas was wet and removed by
the dry-only rule (as in development), leaving **22 dry sessions**, 8,871 clean
(driver, lap, corner) rows, 1,984 laps and 10 teams.

## 3. H3 on 2025: replicated

**Question:** given one qualifying lap, which of the two teammates drove it?
Train on all 2025 weekends but one, test on the held-out weekend, repeat for
every weekend (leave-one-session-out, chapter 10).

| Feature set (mean of 10 teams) | Balanced accuracy | 95 % interval |
|---|---|---|
| Majority (always guess one driver) | 0.498 | |
| Lap time only | 0.575 | 0.527–0.626 |
| **Our corner features** | **0.662** | 0.634–0.694 |
| Raw lap statistics (whole-lap telemetry summaries) | 0.680 | 0.621–0.745 |
| Our features, weekend vote | 0.746 | |
| Shuffled labels (should be ≈ 0.5) | 0.507 | |

- **Primary test:** our features beat lap time in 8 of 10 teams; Wilcoxon
  signed-rank p = 0.027 < 0.05. **H3 is replicated** on a season the method
  never saw. (Development: 0.685 vs 0.565.)
- **The same limitation as in development:** our features don't beat simple
  whole-lap statistics (ours − raw = −0.018, 5 of 10 teams, p = 1.0). Corner
  features are *interpretable* (they say where a driver brakes and opens the
  throttle), but they don't add identification power over simple summaries.
- **Shuffled labels at 0.507:** the pipeline doesn't leak information. If it
  did, even random labels would score above 0.5.
- **Ablation:** removing the throttle features costs the most (0.592), as in
  development. The brake-flag share alone scores 0.610, the same as in 2023–24.

Figure: `results/15_final_exploratory/final_h3_teams.png`.

## 4. H4 on 2025: not supported

**Question:** for the five drivers who changed teams, is their 2025 signature
closer to **their own 2024 signature** (another car) or to **their new
teammate's 2025 signature** (the same car)?

| Driver | 2024 → 2025 | Distance to own 2024 | Distance to new teammate | Closer to |
|---|---|---|---|---|
| Hülkenberg | Haas → Kick Sauber (BOR) | 0.69 | 1.40 | **own** |
| Tsunoda | RB → Red Bull Racing (VER) | 0.84 | 1.01 | **own** |
| Hamilton | Mercedes → Ferrari (LEC) | 1.04 | 0.99 | teammate (nearly equal) |
| Ocon | Alpine → Haas (BEA) | 1.35 | 0.96 | teammate |
| Sainz | Ferrari → Williams (ALB) | 1.26 | 0.73 | teammate |

**2 of 5 → one-sided sign test p = 0.81. H4 is not supported.**

Secondary (reported, not decisions):
- **Brake-flag share** stayed closer to the driver's own for 4 of 5 (p = 0.19).
  It hints at a habit that travels with the driver, but it isn't significant.
- **Own rank among all 22 signatures of 2024:** HUL 1st, TSU 2nd, HAM 4th,
  OCO 12th, SAI 15th. For three drivers the old signature is still
  recognisable; for Ocon and Sainz it is gone.
- **Drivers who stayed** (own 2024 vs old teammate 2024): own closer for
  10 of 11 (p = 0.006), replicating development (17 of 20).

## 5. A mistake in the preregistration: the missed changer

Franco Colapinto drove for Williams in 2024 and Alpine in 2025, so he changed
teams too, but he was missing from the preregistered list. Nobody noticed
until he appeared in the "drivers who stayed" check.

**How a preregistration mistake is handled:**
- The primary test stays **exactly as preregistered** (5 drivers). You don't
  change the test after seeing the result, even to correct it.
- The mistake is written in the deviations file.
- Its effect is shown separately: with Colapinto, 3 of 6 (p = 0.66). With 2 of 5
  already known, adding one driver could only give 2 or 3 of 6, so the
  conclusion couldn't change either way.

**Lesson:** derive lists like "who changed teams" **from the data with a rule**,
not by hand from memory. `15_final_exploratory.py` now does that, and finds
exactly the five plus Colapinto.

## 6. Reading a "no": the control

A "no" needs careful reading. Here is one weakness of the H4 design itself:

- "own 2024" is **one year away** (a different season, a different car
  version, different weekends);
- "new teammate 2025" is **the same season and the very same weekends**.

So even with no car effect, the teammate might be closer, simply because they
were measured under the same conditions. **How strong is that pull?**

**The control** (exploratory): run the identical comparison for the 10 drivers
who **stayed** in their team. Own 2024 vs current 2025 teammate, same weekends.

| Group | Own 2024 signature closer than the 2025 teammate's |
|---|---|
| Drivers who stayed (control) | **8 of 10** (p = 0.055) |
| Drivers who changed teams (H4) | **2 of 5** |

So with the car unchanged, the driver's own signature usually wins despite the
one-year gap. For changers it won less often. Is that difference real? **Fisher's
exact test** (it asks: if both groups had the same success rate, how likely is a
split at least this uneven?) gives p = 0.25. There are too few changers to tell.

(The two stayers whose own signature lost are Albon, whose new teammate is
Sainz, and Lawson, who had only 6 weekends in 2024, so his 2024 signature is
noisy.)

## 7. Two readings, both still open

The preregistration said in advance: "a 'no' doesn't prove the signature is
the car." Two explanations fit what we see:

1. **The car shapes the signature.** Corner features like braking point and
   throttle pickup depend on the car's downforce, brakes and setup, so in a new
   car a driver's numbers move toward the car's.
2. **The driver adapts.** A driver changes their style to suit a new car. The
   signature is still "theirs", but it isn't fixed.

Our data can't separate these. That needs more changers (every season adds a
few), or features that subtract the car's effect (e.g. relative to the
teammate, weekend by weekend), or a regulation change (H5, 2026).

## 8. What the project can now claim (and can't)

**Can claim (measured):**
- Public F1 telemetry at ~3.7 samples/s supports corner features with known
  error bars (Phase 2 Monte Carlo, Phase 3 alignment at 1.15 m).
- Some features are repeatable lap to lap and weekend to weekend (H1: ICC up
  to 0.58 lap level, 0.40 weekend level), mostly minimum speed and throttle;
  braking points much less.
- Within a team, corner features identify which teammate drove a lap on
  **unseen weekends of an unseen season** better than lap time (H3, replicated
  on 2025), though not better than simple whole-lap statistics.
- A driver's season signature persists from one year to the next in the same
  team (17 of 20 in development, 10 of 11 in 2025).

**Can't claim:**
- That the signature belongs to the driver independently of the car (H4 not
  supported, and too weak to show the opposite either).
- Anything about who is the better driver, brake pressure, or events faster
  than the data can show (Nyquist ≈ 1.85 Hz).

## Viva soundbite

"I preregistered the final test and ran it once on a season I never touched.
The teammate-identification result replicated (p = 0.027), but my strongest
hypothesis — that the signature follows a driver into a new car — did not:
only 2 of 5 team changers stayed closer to their old self than to their new
teammate. A control showed that drivers who stayed usually do (8 of 10), but
with five changers I can't tell whether the difference is real. I report that
as it is: a clear yes, and an honest 'not shown'."

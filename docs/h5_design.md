# H5 design: does a driver's signature survive the 2026 car generation?

**Status:** design, 2026-11-02. After the checks planned for the next days (section 7),
this becomes preregistration Part C, which is committed **before any 2026 data is
loaded**. Everything here was decided on development data (2023–2025). The only
things read about 2026 are the rule texts (`docs/regulations_2026.md`).

Numbers in this file come from `experiments/19_h5_power.py`
(`results/19_h5_power/summary.json`).

---

## 1. The question

In 2026 every team got a new kind of car: smaller, lighter, with much less drag, active
wings, and about half its power from the battery (`docs/regulations_2026.md`). If a
driver's corner-level signature is mostly the driver, it should still be recognisable
after that change. If it is mostly the car, the new car should wipe it out.

## 2. The primary test (H5)

**Drivers.** Everyone with at least 5 dry qualifying weekends in 2025 and in 2026, whose
2025 team had another driver sharing at least 5 of those weekends. Drivers who changed
team for 2026 are included: the comparison below doesn't need the same team.
2025 gives an upper bound of **21** such drivers. In 2026 the number can only be lower.

**Signatures.** Built exactly as for H4 (`signatures.season_signatures`): the mean of
the 30 lap-vector features (10 field-relative corner features × slow/medium/fast
corners), each weekend counted once.
- **2026 (the target):** all of the driver's dry 2026 weekends.
- **2025 (the two references):** the driver and their 2025 teammate, **both built only
  on the weekends they shared in 2025**, and on each of those weekends from the same number
  of laps: the smaller count, each driver's first laps of the session (added 2026-11-06,
  after the fresh-eyes review: a reference with more laps is less noisy and looks closer;
  in a car-only world with 6 against 2 laps, all laps gave 0.73 "own closer" instead of
  0.5). The teammate is the other driver of the
  driver's most-driven 2025 team with the most shared weekends (alphabetical on a tie).
- Everything is z-scored with the spread of the **other** drivers' 2025 full-season
  signatures: the driver and the teammate are left out. Distance = root-mean-square
  difference over the features both signatures have. (Changed on 2026-11-03: with the
  pair inside the spread, a car-only synthetic world gave 0.43 instead of 0.5; see
  section 3 and `docs/engineering_notes.md`.)
- Code: `signatures.own_vs_past_teammate`, tested on synthetic laps
  (`tests/test_signatures.py`).

**Test.** A driver counts as a success if their 2026 signature is closer to their own
2025 signature than to their 2025 teammate's. One-sided sign test; **H5 is supported if
p < 0.05.**

## 3. Why this comparison

**The null hypothesis is a fair coin.** The null hypothesis is the claim we try to reject:
here, "the signature is only the car". Both references were made in the same 2025 car, on
the same weekends. If the signature were only the car, the 2026 signature would be equally
close to both, so each driver would be a coin flip (p = 0.5). That is exactly what the sign
test assumes.

**Why "the weekends they shared".** A signature averaged over fewer weekends is noisier,
and a noisier reference sits farther from everything. Example: if the driver had 22
weekends and the teammate only 6, the teammate's signature noise is √(22/6) ≈ 1.9 times
larger. The driver's own past would then look closer for a reason that has nothing to do
with style. Building both references on the same weekends gives them the same noise and
the same tracks, which keeps the coin fair. (H4's Part B did the same for the target
season.)

**Why the pair is left out of the spread.** Each feature is divided by how much drivers
usually differ on it. If the teammate's own noisy signature helps set that spread, it
inflates the spread of exactly the feature where it is farthest out. That shrinks the
distance on that feature, so the teammate looks closer than they are. On synthetic laps
where the signature is only the car and the teammate drove 5 of 12 weekends, this gave
0.43 "own closer" over 1,500 drivers (5 standard errors below 0.5). Leaving the pair out
gave 0.49, and with full-season teammates 0.50.

**What the 2026 car can and can't do to this test.**
- Anything **common to all cars** (less downforce, everyone braking earlier) is removed
  by the field-relative features.
- Anything **common to a team** shifts the driver's 2026 signature by the same amount
  relative to both references. That covers the new car, the team's energy plan, a
  change in what the throttle channel means, and corners changing type. Both distances
  grow, the comparison moves towards 50/50, and **a "no" becomes more likely**. It can't
  manufacture a "yes", unless a team's change happened to point from the teammate's
  2025 style towards the driver's own. There is no reason to expect that, but it can't
  be ruled out.

**Why not the Part B comparison.** H4 in Part B compared the driver's own past (another
car, a year earlier) with the new teammate (the same car, the same weekends). That
comparison is lopsided towards the teammate. Here both references are a year earlier
and in the same car, so neither side has a built-in advantage.

## 4. Decisions on the open questions in `regulations_2026.md` §4

| Question | Decision | Why |
|---|---|---|
| Baseline without a rule change | **Measured with exactly this procedure (`experiments/20_h5_development.py`, re-run on 2026-11-06 with equal laps per shared weekend):** 2023 → 2024: 16 of 20 (0.80, exact 95 % interval 0.56–0.94); 2024 → 2025: 14 of 16 (0.88, 0.62–0.98), team changers included. Before the equal-laps rule, 2024 → 2025 gave one driver more. The earlier H4-style numbers were 17 of 20 and 10 of 11 | The bar a "survives" result is compared with |
| Which features | **Primary: all 30**, unchanged. Secondary: "control points" (brake onset, minimum speed, slowest point, throttle pickup: 12 columns) vs "energy-sensitive" (entry speed, exit speed, full throttle, corner time: 12 columns), side by side. Braking distance and mean deceleration are in neither group (mostly the car) | The split is a hypothesis from the rules. With about 20 drivers the difference between the groups can't be tested, only shown |
| Corner types in 2026 | **The same rule as before** (slow < 120 km/h, fast ≥ 200 km/h, per session). Report how many corners of each type 2025 and 2026 have | Changing the method for unseen data would be tuning on the test set. A corner that changes type is a team-common shift: it can only dilute |
| The throttle caveat | Throttle features stay in the primary. Secondary: the same test without them (24 columns) | If `throttle` means power demand in 2026, the change is shared by teammates: it can only dilute |
| Brake onset when cars coast | Synthetic check on Day 10. If its error with a coasting phase stays at or below 8.4 m (twice the 4.2 m measured in Phase 2), nothing changes. If larger, Part C adds a secondary variant without the three braking features. **The primary stays as above either way.** **Result (2026-11-04, `experiments/21_coasting_check.py`): worst case 4.89 m (2026-like car with lift and coast, medium corners), so nothing changes.** Caveat: with lift and coast the estimator's bias moves from +2.3…+3.4 m (estimate late) to −0.8…−2.4 m (early), so a lap with coasting and one without differ by 3.9–4.7 m in measured brake onset for the same true brake point. Coasting that a whole team does only dilutes (section 3); a difference between teammates in coasting would show up as a brake-onset difference | Fixed now, before the check is run |
| Which statistic | **Sign test**, as in H4 | Simple, makes no assumption about the size of distances, and directly comparable with the 17 of 20 and 10 of 11 baselines |

## 5. Secondary analyses (reported, not decisions)

1. **H4 again, on the 2026 team changers.** Part B's comparison and rules (own 2025 vs
   the new teammate's 2026, on the same weekends), with one change learned on Day 9: the
   driver and the new teammate are left out of the z-score spread. Run with Part B's
   spread on 2025, the code reproduces the frozen distances of all 16 drivers to the last
   stored decimal; with the pair left out, no driver's verdict changes
   (`results/final_2026_dry_run/2025/`). Changers are found by the script from
   team names, not typed in by hand: in 2025, Colapinto was missed from a hand-typed
   list. A fixed map of renamed teams goes into Part C, and a 2026 team name outside the
   map stops the script before any result. With fewer than 5 changers the sign test
   can't reach p < 0.05, so the result is descriptive only. **Caveat:** for these drivers
   the team and the rules change at once, so this can't separate the two.
2. **The stayer control, preregistered this time.** The same comparison for drivers who
   stayed, plus Fisher's exact test of changers vs stayers. In 2025 this was exploratory:
   8 of 10 against 2 of 5, p = 0.25.
3. The two feature groups, and the version without throttle (section 4).
4. ~~Each driver's rank of their own 2025 signature among all 2025 signatures.~~ Dropped
   on 2026-11-06, before Part C: it was never built into `h5_protocol.py`, it adds no
   decision, and the sign test already asks the same question.
5. The share of successes with an exact 95 % interval, next to the two baselines.

## 6. Power: what the test can detect

Power is the chance that the test says "yes" when the effect is really there. It
depends on how many drivers take part (n) and on how likely each driver is to stay
closer to their own past (q). Without a rule change, q was about 0.85–0.91.

| Drivers (n) | Successes needed | q = 0.6 | q = 0.7 | q = 0.8 | q = 0.85 | q = 0.9 |
|---|---|---|---|---|---|---|
| 14 | 11 | 0.12 | 0.36 | 0.70 | 0.85 | 0.96 |
| 16 | 12 | 0.17 | 0.45 | 0.80 | 0.92 | 0.98 |
| 18 | 13 | 0.21 | 0.53 | 0.87 | 0.96 | 0.99 |
| 20 | 15 | 0.13 | 0.42 | 0.80 | 0.93 | 0.99 |

In words:
- If the signature survives **as well as it does without a rule change** (q ≈ 0.85), the
  test will very likely find it (85–96 %).
- If it survives **only partly** (q ≈ 0.7), the test finds it only about half the time
  or less. **A "no" therefore can't tell "weakened" from "gone"**, and the write-up has
  to say so.
- Power doesn't always grow with n. With 18 drivers, 13 successes give p = 0.048; with
  20 drivers, 14 give p = 0.058, so 15 are needed. The sign test can only take whole
  numbers of drivers, so some n are luckier than others.
- For the secondary H4 test: 3 or 4 changers can never reach p < 0.05; 5 or 6 need all
  of them; 8 need 7.
- **At the measured baselines** (section 4): if 2026 had the 2023 → 2024 rate (0.80), the
  test with 14–21 drivers would find it 70–89 % of the time; at the 2024 → 2025 rate
  (0.88), 91–99 %.

## 6b. Development results (no rule change)

`experiments/20_h5_development.py`, figure `results/20_h5_development/h5_development.png`.

| Features | 2023 → 2024 | 2024 → 2025 |
|---|---|---|
| **All 30 (primary)** | **16 of 20** (0.80, 0.56–0.94), p = 0.006 | **14 of 16** (0.88, 0.62–0.98), p = 0.002 |
| Control points (12 columns) | 15 of 20 (0.75), p = 0.021 | 11 of 16 (0.69), p = 0.105 |
| Energy-sensitive (12 columns) | 14 of 20 (0.70), p = 0.058 | 12 of 16 (0.75), p = 0.038 |
| No throttle (24 columns) | 16 of 20 (0.80), p = 0.006 | 12 of 16 (0.75), p = 0.038 |
| Full-season references (not the H5 rule) | 16 of 20 | 14 of 16 |

All rows use equal laps per shared weekend (re-run on 2026-11-06 after the fresh-eyes
review). Before that rule, the 2024 → 2025 primary count was one driver higher and the
no-throttle count three higher (the older numbers are in the research log of 2026-11-03):
some of that came from the lap-count imbalance the review found.

- Each 12-column group is weaker than all 30: fewer features, noisier distances. This is
  why the primary keeps all 30.
- The two groups have no consistent order (control points ahead in 2023 → 2024, behind in
  2024 → 2025), and the intervals overlap almost completely. For 2026 they are reported side
  by side, with no test of the difference.
- Without the throttle features the count stays the same in 2023 → 2024 and drops in
  2024 → 2025 (12 instead of 14 of 16): the throttle features carry part of the signature, so
  the no-throttle version is a check, not a replacement.
- **Team changers, 2024 → 2025 (development observation, not a test):** 5 of 6 changers
  stayed closer to their own 2024 signature than to their *old* teammate's. Hamilton is
  the exception. The frozen H4 test (2 of 5) compared them with their *new* teammate.
  Both can be true at once: a changer's style moves towards the new car, but keeps more
  of their own past than of their old teammate's. This doesn't change the frozen H4
  result.

## 7. Before Part C: the checks still to do

| Day | Check | Output |
|---|---|---|
| 9 | **Done (2026-11-03):** the H5 comparison as a tested function, run on 2023 → 2024 and 2024 → 2025 (section 6b). The synthetic tests also found the spread bias (section 3) | development baselines |
| 10 | **Done (2026-11-04):** synthetic brake-onset check with a coasting phase: all 18 cells at or below 4.89 m, under the 8.4 m threshold (section 4) | estimator error with coasting |
| 11 | **Done (2026-11-05):** `experiments/23_final_2026.py` with all results from `h5_protocol.py`. Guards: Part C committed and unchanged, the code committed, never run; phases download → checks → build → analyse. Dry runs reproduce experiment 20 (16 of 20 and 14 of 16 after the equal-laps rule of 2026-11-06) and the frozen 2025 H4 distances; the rebuilt 2024 dataset is bit-identical | the script, tested |
| 12 | Part C written from this file → **Sadman commits it**; only then may 2026 be loaded | preregistration Part C |

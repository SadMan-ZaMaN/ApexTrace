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
  on the weekends they shared in 2025**. The teammate is the other driver of the
  driver's most-driven 2025 team with the most shared weekends (alphabetical on a tie).
- Everything is z-scored with the spread of all 2025 full-season signatures; distance =
  root-mean-square difference over the features both signatures have.

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
| Baseline without a rule change | 2023 → 2024: 17 of 20 (0.85, exact 95 % interval 0.62–0.97). 2024 → 2025 stayers: 10 of 11 (0.91, 0.59–1.00). Recomputed on Day 9 with exactly this procedure (shared weekends, changers included) | The bar a "survives" result is compared with |
| Which features | **Primary: all 30**, unchanged. Secondary: "control points" (brake onset, minimum speed, slowest point, throttle pickup: 12 columns) vs "energy-sensitive" (entry speed, exit speed, full throttle, corner time: 12 columns), side by side. Braking distance and mean deceleration are in neither group (mostly the car) | The split is a hypothesis from the rules. With about 20 drivers the difference between the groups can't be tested, only shown |
| Corner types in 2026 | **The same rule as before** (slow < 120 km/h, fast ≥ 200 km/h, per session). Report how many corners of each type 2025 and 2026 have | Changing the method for unseen data would be tuning on the test set. A corner that changes type is a team-common shift: it can only dilute |
| The throttle caveat | Throttle features stay in the primary. Secondary: the same test without them (24 columns) | If `throttle` means power demand in 2026, the change is shared by teammates: it can only dilute |
| Brake onset when cars coast | Synthetic check on Day 10. If its error with a coasting phase stays at or below 8.4 m (twice the 4.2 m measured in Phase 2), nothing changes. If larger, Part C adds a secondary variant without the three braking features. **The primary stays as above either way** | Fixed now, before the check is run |
| Which statistic | **Sign test**, as in H4 | Simple, makes no assumption about the size of distances, and directly comparable with the 17 of 20 and 10 of 11 baselines |

## 5. Secondary analyses (reported, not decisions)

1. **H4 again, on the 2026 team changers.** Part B's comparison and rules (own 2025 vs
   the new teammate's 2026, on the same weekends). Changers are found by the script from
   team names, not typed in by hand: in 2025, Colapinto was missed from a hand-typed
   list. A fixed map of renamed teams goes into Part C, and a 2026 team name outside the
   map stops the script before any result. With fewer than 5 changers the sign test
   can't reach p < 0.05, so the result is descriptive only. **Caveat:** for these drivers
   the team and the rules change at once, so this can't separate the two.
2. **The stayer control, preregistered this time.** The same comparison for drivers who
   stayed, plus Fisher's exact test of changers vs stayers. In 2025 this was exploratory:
   8 of 10 against 2 of 5, p = 0.25.
3. The two feature groups, and the version without throttle (section 4).
4. Each driver's rank of their own 2025 signature among all 2025 signatures.
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

## 7. Before Part C: the checks still to do

| Day | Check | Output |
|---|---|---|
| 9 | The H5 comparison as a tested function (shared-weekend references), run on 2023 → 2024 and 2024 → 2025. It gives the real baselines for this exact procedure and the feature-group and no-throttle numbers | development baselines |
| 10 | Synthetic brake-onset check with a coasting phase (rule in section 4) | estimator error with coasting |
| 11 | The one-time 2026 script: guards (Part C committed, unchanged, never run), download first and then analyse (the Baku lesson), a sampling check and the team map before any feature. Dry run with 2025 standing in for 2026 | the script, tested |
| 12 | Part C written from this file → **Sadman commits it**; only then may 2026 be loaded | preregistration Part C |

# 11. Driver or car? (Phase 7)

> H4: does a driving "signature" follow the driver into a different car?
> Code: `signatures.py`. Experiments: `13_signature_stability.py`
> (development, 2023 → 2024), `14_final_2025.py` (the one-time final test).
> Plan: `docs/preregistration.md`, Part B.

## Why this is hard

A driver always drives some car. If Norris and Piastri differ, is it the
drivers or tiny setup differences? Within a team, the car is (almost) the same,
which is why the teammate tasks were the main evidence so far. The cleanest test
of all: drivers who **changed teams**. If the signature follows them into the new
car, it's theirs.

## Season signatures

A **season signature** = a driver's average field-relative corner features over
a season (30 numbers: 10 features × 3 corner types), each race weekend counted
once. Averaging ~20 weekends removes much of the weekend-to-weekend noise that
made single-weekend signatures weak (H1).

**Distance between two signatures:** first divide each feature by how much drivers
usually differ on it (a z-score with the reference season's spread, so metres and
km/h become comparable), then take the root-mean-square difference.

## Development: 2023 → 2024 (nobody changed teams)

| Check | Result |
|---|---|
| Is a driver's 2024 signature closest to their own 2023 one? | mean rank **3.05 of 21** (chance 11.0); first for 12 of 20; permutation p = 0.0001 |
| Closer to their own 2023 signature than to their 2023 **teammate's** (same car)? | **17 of 20**, sign test p = 0.0013 |
| Brake-flag share, same question | 15 of 20, p = 0.021 (and 0.95 correlation between years) |

**The sign test:** if the car were everything, "own closer than teammate" would be
a coin flip for each driver. The chance of 17 or more heads in 20 flips is
0.0013. So the signature is more than the car.

**A correction made during the run** (and logged): renamed teams (AlphaTauri →
RB, Alfa Romeo → Kick Sauber) first weren't recognised as the same team, so four
drivers had no teammate (14 of 16 then). Mapping the renames is a factual
correction, not a choice made after seeing a result, and both numbers are in
the research log.

## The final test (2025, run once)

Five drivers changed teams for 2025: Hamilton (Mercedes → Ferrari), Sainz
(Ferrari → Williams), Ocon (Alpine → Haas), Hülkenberg (Haas → Sauber),
Tsunoda (RB → Red Bull). For each: is the 2025 signature closer to
**their own 2024 signature** (another car) or to **their new teammate's 2025
signature** (the same car)? If the car dominated, the teammate would win.

**Power, stated before the test:** with 5 drivers the smallest possible p is
1/32 = 0.031, so the test can only succeed if **all five** go the driver's way.
That's a demanding test, and its weakness is written down in advance.

## How the one-time test is protected

1. **The 2025 guard** (`data_loading.check_not_frozen`) has refused 2025 since
   the first day, for both data sources.
2. **The preregistration** (Part B) fixes the data, features, models, tests and
   decision rules, and is committed before 2025 is loaded.
3. **The final script** checks that the preregistration is committed and
   unchanged, that `FINAL_TEST=1` is set, and that it hasn't run before.
4. **Same code:** everything the final run uses was moved into the package and
   checked to reproduce the development results exactly (regression checks).
5. **A dry run** on development data exercised every code path beforehand.

If a bug is found after the run: fix it, rerun into a new folder, and report
**both** results. Never quietly replace a result.

**The outcome** (run on 2026-10-18): H3 replicated, H4 not supported (2 of 5).
The full story, including a crash on the first attempt and a changer missing
from the list, is in [chapter 12](12_final_results.md).

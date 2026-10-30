# The 2026 car rules, and what they could do to our features

Written 2026-10-31 to prepare H5 ("does a driver's signature survive a new car
generation?") and a second H4 test on the 2026 team changes. Nothing here is a
result: it lists what changed in the cars, checked against the FIA's own texts, and
what each change *could* do to each feature, so that the 2026 test can be planned
and preregistered (Part C) before any 2026 data is loaded.

**Source rule.** This note was written from the rule texts and the FIA's 2024
announcement only. No 2026 session data, results, lap times or telemetry analyses
were looked at, so that what we expect can't be shaped by what 2026 looked like
(the same reason the 2025 test was designed before 2025 was loaded). Explainer
articles were used only for the meaning of informal words ("superclipping", "lift
and coast"), and where an explainer and the FIA text disagree, the FIA text wins.

✅ = checked in the FIA text named in the row (2026-10-31) · ⚠️ = our reading of
the rules, or a hypothesis: not checked on data.

---

## 1. What changed in the cars

### Size, mass, tyres

| What | 2022–2025 | 2026 | Source |
|---|---|---|---|
| Wheelbase | ≤ 3600 mm | ≤ 3400 mm | ✅ Section C, Art. C2.3.3; FIA 2024 |
| Width | 2000 mm | 1900 mm | ✅ FIA 2024 (C2.3.1: no part except wheels more than 950 mm from the centreline) |
| Floor width | | 150 mm narrower | ✅ FIA 2024 |
| Minimum mass | 798 kg | 768 kg announced (722 kg car + driver, plus about 46 kg of tyres); in the current text 726 kg plus the nominal tyre mass in qualifying, 724 kg plus tyres in other sessions | ✅ FIA 2024; Section C, Art. C4.1 |
| Wheels and tyres | 18-inch | still 18-inch; front tyres 25 mm narrower, rear 30 mm | ✅ FIA 2024 |
| Gears | 8 forward | still 8 forward | ✅ Section C, Art. C9.6.1 |

### Aerodynamics

- **Less downforce and much less drag:** "Downforce has been reduced by 30% and drag
  by 55%" (FIA 2024). These are the FIA's design targets, not measurements. ✅
- **Active wings replace DRS.** The front-wing flaps and the rear-wing flap each have
  two positions: **Corner Mode** (normal, high downforce) and **Straight Mode** (less
  wing angle, less drag). The 2024 announcement called them Z-mode and X-mode. ✅
  - The switch between the two positions takes at most **400 ms** (C3.10.10(o),
    C3.11.6(d)). ✅ At 300 km/h that is up to 33 m of track.
  - Straight Mode is allowed only inside **Activation Zones** that the FIA defines for
    each circuit (C3.10.10(w), C3.11.6(j), B7.1.1(e)), and it is "commanded by direct
    driver input" (definition of "State of Deployment"; B7.1.1(c), B7.1.2(a)). ✅
    One explainer says the switch is automatic; the FIA text says the driver commands it.
  - If the system fails, the wings return to Corner Mode. In low-grip conditions only the
    front wing may open ("partial activation", B7.1.2(b)). ✅

### Power unit and energy

| What | 2022–2025 | 2026 | Source |
|---|---|---|---|
| Engine (ICE) power | 550–560 kW | about 400 kW | ✅ FIA 2024 |
| Electric motor (MGU-K) power | 120 kW | 350 kW | ✅ C5.2.7; FIA 2024 |
| MGU-H (turbo generator) | yes | removed | ✅ FIA 2024 |
| Energy recovered per lap | | at most 8.5 MJ; in qualifying the FIA may lower it (not below 5 MJ) at up to 12 events | ✅ C5.2.10, B7.2.1(c) |
| Battery charge window | | at most 4 MJ between fullest and emptiest | ✅ C5.2.9 |
| Fuel | | limited by energy flow (3000 MJ/h), 100 % sustainable | ✅ C5.2.3; FIA 2024 |
| MGU-K torque | | at most 500 Nm | ✅ C5.2.11 |

**Electric power falls with speed** (C5.2.8). Without Overtake, the power allowed to
drive the car is P = 1800 − 5·v kW (v in km/h) below 340 km/h, then falls steeply to
zero at 345 km/h. With **Overtake** active it is P = 7100 − 20·v kW, zero at 355 km/h.
Both are also capped at 350 kW. ✅ Worked numbers:

| Speed | Without Overtake | With Overtake |
|---|---|---|
| 290 km/h | 350 kW | 350 kW |
| 300 km/h | 300 kW | 350 kW |
| 320 km/h | 200 kW | 350 kW |
| 340 km/h | 100 kW | 300 kW |
| 345 km/h | 0 | 200 kW |
| 355 km/h | 0 | 0 |

**In qualifying, Overtake is on all the time.** Qualifying is a "Lap Time Classified
Session". In those sessions Overtake is enabled before the session starts (B7.2.2(a))
and "activated at all times when it is enabled" (B7.2.3(b)). In the race it needs
the car to be within the Detection Gap of the car ahead (B7.2.3(c)). ✅ for the
text; ⚠️ that this means every qualifying lap runs on the Overtake curve is our
reading of those two articles.

**Power can be cut back when energy runs short.** C5.12.4–C5.12.7 limit how fast
the "driver maximum power demand" may be reduced in "power limited" periods. For
example, at most 150 kW at the start of such a period, held for at least 1 s. **Boost**
is a driver-selected mode that "maintains or increases the ERS-K power demand"
(definitions). ✅ for the text; ⚠️ how teams use it on a qualifying lap is not known
to us. In explainers, **superclipping** means harvesting energy while the driver
stays at full throttle, usually at the end of straights, which slows the car slightly.
**Lift and coast** means lifting off the throttle and coasting before the braking zone.

**The accelerator pedal sets a torque demand** through a map that must increase with
pedal position (C5.12.1). ✅

### The rules kept changing

The 2024 announcement said that the leading car's electric deployment "reaches zero
at 355 kph". The April 2026 text says 345 km/h without Overtake and 355 km/h with
it. Section C went from Issue 09 (October 2024) to Issue 17 (28 April 2026, after
the season had started), and Section B reached Issue 07 on 25 June 2026. Any number
taken from the rules must therefore name the issue it came from. Which events ran
under which issue was not checked.

---

## 2. What could move each feature

Four kinds of effect, which our method treats differently:

- **(a) The same for every car at a corner**, such as less downforce lowering every
  car's minimum speed. *Removed* by field-relative features: each value is compared
  with the median of all cars at the same corner in the same session.
- **(b) Different from car to car** (chassis, power unit, a team's energy plan).
  *Kept* by field-relative features, but *cancelled* when two teammates are
  compared, because they share a car. H3 (teammates) and the H4/H5 own-vs-teammate
  comparisons are built on that.
- **(c) The driver's own choices.** This is what we want to measure.
- **(d) Measurement:** a change that makes one of our estimators less accurate.

| Feature | What in the 2026 rules could move it | Kind | ⚠️ Expectation |
|---|---|---|---|
| `brake_onset_m` | Less drag and downforce at braking speed (longer braking, earlier for everyone); up to 350 kW of regenerative braking; the wings closing (≤ 400 ms); lift and coast before the zone | a, b, c, d | Earlier braking for the field (removed). If cars already slow down before the brake goes on, the kink in the speed trace that our estimator finds is weaker, so expect more scatter (section 3) |
| `braking_distance_m`, `mean_decel_ms2` | Lighter car, narrower tyres, less downforce, how much braking the motor does | a, b | Mostly car and field effects |
| `min_speed_kmh`, `apex_m` | Less downforce in Corner Mode, narrower tyres | a, b, c | The minimum-speed shift is shared by the field; where the slowest point sits stays a driver choice |
| `throttle_pickup_m` | The pedal-to-torque map; much more electric torque out of slow corners (500 Nm cap) | b, c | Still the driver's first input. Likely the throttle feature least tied to energy management |
| `full_throttle_m` | The same, plus traction limits with 350 kW available at low speed | b, c | More car than before? |
| `entry_speed_kmh` (200 m before the corner) | Speed at the end of a straight now depends on the speed-dependent power cap, a team's energy plan (superclipping, power-limited periods), and when Straight Mode is closed | b, c | **The feature most likely to become "car"**: the energy plan is a team decision |
| `exit_speed_kmh` (150 m after) | Electric deployment out of the corner | b, c | Partly energy plan |
| `corner_time_s` | Everything above | a, b, c | |
| `min_gear` | Still 8 gears; the ratios are a team choice | b | Not used in the lap vectors |

**Corner types may change.** Corners are typed by minimum speed: slow below 120 km/h,
fast from 200 km/h (`corners.py`). With less downforce, a corner that was "fast" in 2025
can fall below 200 km/h in 2026 and become "medium". A corner taken flat out in 2025
may also need braking in 2026 (and appear as a new braking zone), or the reverse.
Because the lap vectors average over corner types, the H5 plan has to fix in advance
how 2026 corners are typed (section 4).

---

## 3. Measurement questions for 2026

1. **The feed.** The OpenF1 documentation (checked 2026-10-31) lists the same
   `car_data` fields at "about 3.7 Hz": brake 0/100, `drs`, gear 1–8, rpm, speed,
   throttle. There is no note about 2026. We don't use `drs` (there is no DRS in 2026).
   Whether the 2026 sampling really matches can't be checked without loading 2026, so
   the one-time 2026 script must measure the sampling first (`quality.py`), and Part C
   must say beforehand what happens if it differs.
2. **What "throttle" means.** OpenF1 describes it as "Percentage of maximum engine
   power being used"; the project has treated it as pedal position. We assumed the
   difference didn't matter in 2022–2025 (⚠️ never checked). In 2026, power can be cut
   while the pedal stays down (superclipping). If the channel is power demand, the throttle features would
   pick up the energy plan. ⚠️ Open; Part C should report throttle features separately
   from the others so this can't decide the overall result.
3. **Brake onset when the car is already slowing.** The estimator looks for the kink in
   speed inside the interval where the brake signal switches on, so its error stays
   within one sample spacing (about 22 m at 300 km/h). Lift and coast or superclipping
   makes the kink smaller: deceleration changes from "already slowing" to "braking"
   instead of from "accelerating" to "braking". How much this adds to the 4.2 m
   error measured on synthetic laps in Phase 2 can be measured on synthetic laps with
   a coasting phase, before Part C.
4. **Unchanged by the new rules:** the car's dimensions don't enter any feature, and the
   track coordinate comes from X/Y position and integrated speed (Phase 3). Experiment
   18 found that the per-lap position offset does not reach the corner features, so no
   correction is planned.

---

## 4. Questions for the H5 design (Day 8)

- **The baseline without a rule change.** How much does a signature carry over from
  2024 to 2025 (same rules)? That is the development analogue, and the bar 2025 → 2026
  is compared with.
- **Which features.** A preregistered split is proposed (⚠️ to decide on Day 8): features
  tied to energy management (entry speed, exit speed, full throttle, corner time) vs
  features at the driver's own control points (brake onset, minimum speed and its
  position, throttle pickup). The hypothesis would be that the second group carries
  over better.
- **Corner types in 2026.** Either type each corner with the same km/h rule as before,
  or keep each track's 2025 types. Decide before loading 2026.
- **Qualifying energy limits differ by event** (5–8.5 MJ). Shared by everyone at an
  event, so field-relative features remove most of it. Different power units may
  still react differently, which only matters between teams.
- **Measurement checks first:** item 3 above on synthetic laps; the sampling check and
  the throttle caveat written into Part C.

---

## Sources (all accessed 2026-10-31)

1. FIA, *2026 Formula 1 Regulations, Section C: Technical*, Issue 17, 28 April 2026.
   <https://api.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_c_technical_-_iss_17_-_2026-04-28.pdf>
2. FIA, *2026 Formula 1 Regulations, Section B: Sporting*, Issue 07, 25 June 2026.
   <https://api.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_b_sporting_-_iss_07_-_2026-06-25.pdf>
3. FIA, "A New Era of Competition: FIA showcases future-focused Formula 1 regulations
   for 2026 and beyond", 6 June 2024 (cited as "FIA 2024"). <https://fia.com/node/51855>
4. OpenF1 API documentation, `car_data`. <https://openf1.org/docs>
5. For terms only: Motorsport Magazine, "Explained: active aero, overtake mode and the
   new F1 2026 terminology" (17 December 2025, updated 25 March 2026); Speedcafe, "2026
   Formula 1 terminology explained" (5 March 2026).

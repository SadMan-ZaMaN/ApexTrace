"""Synthetic corners with a known truth, then degraded exactly like the real timing feed.

Why this module exists (the measurement-science core of the project):
on real data we never know where the braking point *really* was, so we
can't know how wrong our estimate is. On a synthetic corner we do. We
simulate a corner very finely (500 times per second = the "truth"), then
sample it the way the live feed does (irregular, ~3.8 samples per second,
speed rounded to whole km/h, brake only on/off). Running our estimators on
thousands of such corners tells us their bias and spread: the "± X m"
we quote on real data.

Signals-and-systems analogy: this is like testing a pitch detector on a
sine wave of known frequency before trusting it on a voice (Consonance).

The physics is deliberately simple but realistic in size (checked against
the 2024 Abu Dhabi data in Phase 1):
  - braking deceleration grows with speed (aerodynamic downforce gives more
    grip at high speed): about 5.9 g at 324 km/h, about 2.2 g at 100 km/h;
    a 324 -> 68 km/h stop then takes ~110 m, close to the real Turn 6;
  - acceleration is limited by traction at low speed (1.3 g) and by engine
    power at high speed (P/m = 940 W/kg), minus air drag;
  - the driver: full throttle -> brake (pressure builds up over a short ramp)
    -> full braking -> eases off the brake (taper) -> coasts briefly ->
    opens the throttle progressively (first-order response with time
    constant tau).
"""

import math

import numpy as np

G = 9.81                  # m/s^2
TRUTH_RATE_HZ = 500       # the "continuous" truth is computed every 2 ms
DT = 1.0 / TRUTH_RATE_HZ

# Vehicle model (rough F1 numbers)
POWER_PER_MASS = 940.0    # W/kg: ~750 kW for ~800 kg
TRACTION_LIMIT = 1.3 * G  # most forward acceleration the tyres allow at low speed
DRAG_COEFF = 0.00109      # air drag deceleration = DRAG_COEFF * v^2 (m/s^2, v in m/s)
COAST_DECEL = 1.0         # engine braking + rolling resistance with throttle closed (m/s^2)
BRAKE_BASE = 1.8 * G      # braking grip without downforce
BRAKE_AERO = 0.003876     # extra braking grip from downforce, times v^2

# Thresholds from the feature definitions (PROJECT_CONTEXT §10)
THROTTLE_PICKUP_PCT = 10.0
FULL_THROTTLE_PCT = 99.0

# The three pilot corners (decisions.md, 2026-10-16), speeds from NOR's pole lap.
# Driver/timing values are plausible guesses; random_corner_params() varies
# them from lap to lap so we never test at one exact setting.
CORNER_TYPES = {
    "heavy_braking": {"entry_kmh": 324.0, "apex_kmh": 68.0, "taper_s": 0.5,
                      "coast_s": 0.20, "throttle_tau_s": 0.45},   # like T6
    "medium": {"entry_kmh": 294.0, "apex_kmh": 108.0, "taper_s": 0.5,
               "coast_s": 0.20, "throttle_tau_s": 0.40},          # like T5
    "fast": {"entry_kmh": 320.0, "apex_kmh": 181.0, "taper_s": 0.4,
             "coast_s": 0.15, "throttle_tau_s": 0.30},            # like T9
}


def braking_decel(v):
    """Deceleration (m/s^2, positive) with the brake fully on, at speed v (m/s).

    Example: v = 90 m/s (324 km/h): 1.8 g + 0.003876 * 8100 + drag 8.8
    = 17.7 + 31.4 + 8.8 = 57.9 m/s^2 = 5.9 g. At 28 m/s (100 km/h): 2.2 g.
    """
    return BRAKE_BASE + BRAKE_AERO * v * v + DRAG_COEFF * v * v


def drive_accel(v, throttle_pct):
    """Forward acceleration (m/s^2, can be negative) at speed v with a given throttle.

    Engine force is limited by traction at low speed and by power at high
    speed (power = force x speed, so force = P / v). Drag and engine braking
    always pull back.
    Example: full throttle at 90 m/s: min(12.8, 940/90 = 10.4) - drag 8.8
    = +1.6 m/s^2 (still accelerating slowly at 324 km/h).
    """
    available = min(TRACTION_LIMIT, POWER_PER_MASS / max(v, 1.0))
    resist = DRAG_COEFF * v * v + COAST_DECEL * (1.0 - throttle_pct / 100.0)
    return available * throttle_pct / 100.0 - resist


def random_corner_params(corner_type, rng):
    """One lap's driver behaviour: the corner type's values, varied a little.

    Variation per lap (so tests never run at one exact setting):
      entry speed +-4 km/h, apex speed +-3 km/h, brake ramp 0.05-0.25 s,
      taper/coast/throttle time constant +-20 %.
    """
    base = CORNER_TYPES[corner_type]
    return {
        "entry_kmh": base["entry_kmh"] + rng.uniform(-4, 4),
        "apex_kmh": base["apex_kmh"] + rng.uniform(-3, 3),
        "brake_ramp_s": rng.uniform(0.05, 0.25),
        "taper_s": base["taper_s"] * rng.uniform(0.8, 1.2),
        "coast_s": base["coast_s"] * rng.uniform(0.8, 1.2),
        "throttle_tau_s": base["throttle_tau_s"] * rng.uniform(0.8, 1.2),
        "straight_s": rng.uniform(2.5, 3.5),  # time on the straight before braking
        "exit_s": 3.0,                        # time simulated after full throttle
    }


def start_speed_for_entry(entry_ms, straight_s):
    """The speed to start the straight at, so that full throttle for straight_s ends at entry_ms.

    Simulates the straight and corrects the starting guess by the miss,
    a few times over. Example: to reach 90 m/s (324 km/h) after 3 s the car
    must start at about 84 m/s, because it still gains ~1.5-2.5 m/s^2.
    """
    start = entry_ms
    for _ in range(5):
        v = start
        for _ in range(int(round(straight_s / DT))):
            v += drive_accel(v, 100.0) * DT
        start -= v - entry_ms
    return start


def make_true_corner(params):
    """Simulate one corner at 500 Hz and return the truth.

    Phases, in order:
      1. straight:   full throttle for straight_s seconds
      2. brake ramp: deceleration builds up linearly over brake_ramp_s
      3. braking:    full braking until the speed is low enough that easing
                     off over taper_s lands near the target apex speed
      4. taper:      brake force falls linearly to zero (brake still "on")
      5. coast:      brake off, throttle closed, for coast_s
      6. throttle:   throttle(t) = 100 * (1 - exp(-t / tau)), the response of
                     a first-order system (like an RC circuit charging)
      7. exit:       keep accelerating for exit_s after reaching 99 %

    The speed minimum (the "apex" for us) falls just after the throttle
    opens, when forward acceleration overtakes drag and engine braking.

    Returns a dict of numpy arrays (time_s, distance_m, speed_kmh,
    throttle_pct, brake, accel_ms2) and a dict "events" with the true time
    and distance of each event (see below).
    """
    entry = params["entry_kmh"] / 3.6
    apex = params["apex_kmh"] / 3.6
    ramp = params["brake_ramp_s"]
    taper = params["taper_s"]

    # Speed at which to start easing off: during a linear taper from full
    # decel to zero the car loses (decel x taper / 2) of speed, and the coast
    # loses a bit more. The decel depends on the release speed itself, so we
    # solve release = apex + loss(release) by repeating the formula a few
    # times (fixed-point iteration; it settles within ~5 rounds).
    coast_loss = (COAST_DECEL + DRAG_COEFF * apex * apex) * params["coast_s"]
    release_speed = apex
    for _ in range(10):
        release_speed = apex + braking_decel(release_speed) * taper / 2 + coast_loss

    v = start_speed_for_entry(entry, params["straight_s"])
    t = 0.0
    x = 0.0

    times, distances, speeds, throttles, brakes, accels = [], [], [], [], [], []
    phase = "straight"
    phase_start = 0.0
    full_brake_decel = 0.0
    events_t = {}

    while True:
        # --- decide throttle, brake and acceleration for this phase
        if phase == "straight":
            throttle, brake = 100.0, False
            a = drive_accel(v, throttle)
            if t - phase_start >= params["straight_s"]:
                phase, phase_start = "ramp", t
                events_t["brake_onset"] = t
                continue
        elif phase == "ramp":
            throttle, brake = 0.0, True
            fraction = min((t - phase_start) / ramp, 1.0)
            a = -fraction * braking_decel(v)
            if t - phase_start >= ramp:
                phase, phase_start = "braking", t
                continue
        elif phase == "braking":
            throttle, brake = 0.0, True
            a = -braking_decel(v)
            if v <= release_speed:
                phase, phase_start = "taper", t
                full_brake_decel = braking_decel(v)
                continue
        elif phase == "taper":
            throttle, brake = 0.0, True
            fraction = 1.0 - (t - phase_start) / taper
            a = -fraction * full_brake_decel - DRAG_COEFF * v * v
            if t - phase_start >= taper:
                phase, phase_start = "coast", t
                events_t["brake_release"] = t
                continue
        elif phase == "coast":
            throttle, brake = 0.0, False
            a = drive_accel(v, 0.0)
            if t - phase_start >= params["coast_s"]:
                phase, phase_start = "throttle", t
                events_t["throttle_start"] = t
                continue
        else:  # "throttle"
            throttle = 100.0 * (1.0 - math.exp(-(t - phase_start) / params["throttle_tau_s"]))
            brake = False
            a = drive_accel(v, throttle)
            if "full_throttle" not in events_t and throttle >= FULL_THROTTLE_PCT:
                events_t["full_throttle"] = t
            if "full_throttle" in events_t and t - events_t["full_throttle"] >= params["exit_s"]:
                break

        # --- store this instant, then step forward 2 ms (Euler integration)
        times.append(t)
        distances.append(x)
        speeds.append(v * 3.6)
        throttles.append(throttle)
        brakes.append(brake)
        accels.append(a)
        x += v * DT
        v = max(v + a * DT, 1.0)
        t += DT

    truth = {
        "time_s": np.array(times),
        "distance_m": np.array(distances),
        "speed_kmh": np.array(speeds),
        "throttle_pct": np.array(throttles),
        "brake": np.array(brakes),
        "accel_ms2": np.array(accels),
        "params": dict(params),
    }
    truth["events"] = true_events(truth, events_t)
    return truth


def true_events(truth, events_t):
    """True time (s), distance (m) and value of each event we try to measure.

      brake_onset      the moment braking starts (brake switches on)
      apex             the minimum speed (time, distance, speed in km/h)
      throttle_pickup  throttle first reaches 10 % after the apex region
      full_throttle    throttle first reaches 99 %
      peak_decel       largest deceleration (m/s^2)
      coast_time_s     time with brake off and throttle below 5 %
    """
    t = truth["time_s"]
    d = truth["distance_m"]
    speed = truth["speed_kmh"]
    throttle = truth["throttle_pct"]

    def at(time_value):
        return float(np.interp(time_value, t, d))

    lowest = int(np.argmin(speed))
    after_start = t >= events_t["throttle_start"]
    pickup_index = np.where(after_start & (throttle >= THROTTLE_PICKUP_PCT))[0][0]

    coasting = (~truth["brake"]) & (throttle < 5.0)
    # count only the coast between braking and throttle (not the straight)
    between = (t >= events_t["brake_onset"]) & (t <= t[pickup_index])
    coast_time = float(np.sum(coasting & between) * DT)

    return {
        "brake_onset": {"t": events_t["brake_onset"], "d": at(events_t["brake_onset"])},
        "brake_release": {"t": events_t["brake_release"], "d": at(events_t["brake_release"])},
        "apex": {"t": float(t[lowest]), "d": float(d[lowest]), "speed_kmh": float(speed[lowest])},
        "throttle_pickup": {"t": float(t[pickup_index]), "d": float(d[pickup_index])},
        "full_throttle": {"t": events_t["full_throttle"], "d": at(events_t["full_throttle"])},
        "peak_decel_ms2": float(-np.min(truth["accel_ms2"])),
        "coast_time_s": coast_time,
        "entry_speed_kmh": float(np.interp(events_t["brake_onset"], t, speed)),
    }


def load_interval_distribution(histogram_csv, column="car_count"):
    """Real sample intervals and how often each occurred, from check 1's histogram.

    Returns (intervals_s, probabilities). Example: if 0.16 s occurred 1752
    times out of 9755, its probability is 0.18.
    """
    import pandas as pd  # only needed here

    table = pd.read_csv(histogram_csv)
    table = table[table[column] > 0]
    values = table["interval_s"].to_numpy(dtype=float)
    counts = table[column].to_numpy(dtype=float)
    return values, counts / counts.sum()


def degrade_like_feed(truth, intervals_s, probabilities, rng, max_interval_s=None):
    """Sample a true corner the way the live timing feed does.

    Steps:
      1. sample times: a random start offset, then intervals drawn at random
         from the real interval distribution (0.16-0.56 s on a 40 ms clock,
         optionally without feed gaps: max_interval_s=0.6);
      2. speed rounded to whole km/h, throttle to whole %, brake on/off.

    Each call gives a different sampling "phase" relative to the corner,
    which is exactly what happens from lap to lap on real data.

    Assumptions (stated, not verified): intervals are independent of each
    other; the feed rounds speed (rather than truncating); timestamps have
    no delay relative to the physical moment (a constant delay would be the
    same for both drivers and cancel in comparisons).

    Returns a dict of arrays: time_s, speed_kmh, throttle_pct, brake.
    """
    values = np.asarray(intervals_s, dtype=float)
    probs = np.asarray(probabilities, dtype=float)
    if max_interval_s is not None:
        keep = values <= max_interval_s
        values = values[keep]
        probs = probs[keep] / probs[keep].sum()

    t_end = truth["time_s"][-1]
    sample_times = [rng.uniform(0.0, float(np.max(values)))]
    while True:
        next_time = sample_times[-1] + rng.choice(values, p=probs)
        if next_time > t_end:
            break
        sample_times.append(next_time)
    sample_times = np.array(sample_times)

    true_speed = np.interp(sample_times, truth["time_s"], truth["speed_kmh"])
    true_throttle = np.interp(sample_times, truth["time_s"], truth["throttle_pct"])
    # brake is on/off: take the value at the last 2 ms truth step before each sample
    brake_index = np.searchsorted(truth["time_s"], sample_times, side="right") - 1
    return {
        "time_s": sample_times,
        "speed_kmh": np.round(true_speed),
        "throttle_pct": np.round(true_throttle),
        "brake": truth["brake"][brake_index],
    }


def lap_with_position_offset(rng, offset_m, drift, scatter_m=3.0, length_m=5000.0):
    """A whole lap sampled like the feed, where the position stream has a known offset.

    Used to test and calibrate quality.start_offset (the per-lap position-offset
    check). True distance x(t) comes from a speed that swings between ~30 and
    ~80 m/s every 800 m (corners and straights), sampled at irregular
    0.16-0.44 s intervals like the feed. Then:
      integrated distance d = x * (1 + drift)          (a speed-scale error)
      projected position  s = x + offset_m + scatter   (the error under test)
    Example: drift 0.0025 puts d 12.5 m long after 5 km; offset_m 5 puts every
    s 5 m ahead of where the car really is. Returns (s, d).
    """
    step = 0.01
    t, x, true = 0.0, 0.0, []
    next_sample = rng.uniform(0.0, 0.2)
    while x < length_m:
        speed = 55.0 + 25.0 * np.cos(2 * np.pi * x / 800.0)
        if t >= next_sample:
            true.append(x)
            next_sample = t + rng.choice([0.16, 0.2, 0.24, 0.28, 0.32, 0.36, 0.4, 0.44])
        x += speed * step
        t += step
    true = np.array(true)
    d = true * (1.0 + drift)
    s = true + offset_m + rng.normal(0.0, scatter_m, len(true))
    return s, d

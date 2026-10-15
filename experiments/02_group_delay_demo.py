"""Phase 2 demo: why causal smoothing moves braking points, and why zero-phase filtering doesn't.

Four parts, each writes a figure and numbers to results/02_group_delay/:
  A. Braking-point shift caused by each filter, averaged over 200 synthetic
     heavy-braking corners (the truth is known, so the shift is measurable).
  B. Frequency response (magnitude and group delay) and pole-zero plots of
     the moving average, the EMA and a Butterworth low-pass.
  C. Derivative noise: deceleration from the raw rounded speed vs smoothed.
  D. Choosing the smoothing cutoff from the spectrum of REAL laps: where does
     the speed spectrum stop falling and flatten into noise?

Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\02_group_delay_demo.py
"""

import json
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import signal

from apextrace.data_loading import load_session, select_laps
from apextrace.filters import (
    butterworth_lowpass,
    causal_filter,
    derivative,
    ema_coefficients,
    frequency_response,
    moving_average_coefficients,
    poles_and_zeros,
    zero_phase_filter,
)
from apextrace.plots import SERIES, TEXT_SECONDARY, apply_style
from apextrace.resampling import to_uniform_grid
from apextrace.synthetic import (
    degrade_like_feed,
    load_interval_distribution,
    make_true_corner,
    random_corner_params,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "results" / "02_group_delay"
HISTOGRAM = REPO_ROOT / "results" / "01_data_pilot" / "interval_histogram.csv"

GRID_STEP_S = 0.25          # a uniform grid close to the feed's typical spacing (4 Hz)
DETECT_DROP_KMH = 10.0      # "braking detected" = speed 10 km/h below its pre-braking peak
LAPS = 200
SEED = 2026


def filters_to_compare():
    """name -> function(speed on the 4 Hz grid) -> smoothed speed."""
    fs = 1.0 / GRID_STEP_S
    b_ma, a_ma = moving_average_coefficients(5)
    b_ema, a_ema = ema_coefficients(0.5)
    b_bw, a_bw = butterworth_lowpass(0.5, fs, order=2)
    return {
        "no filter": lambda x: x,
        "moving average 5, causal": lambda x: causal_filter(b_ma, a_ma, x),
        "EMA alpha 0.5, causal": lambda x: causal_filter(b_ema, a_ema, x),
        "Butterworth 0.5 Hz, causal": lambda x: causal_filter(b_bw, a_bw, x),
        "moving average 5, zero-phase": lambda x: zero_phase_filter(b_ma, a_ma, x),
        "Butterworth 0.5 Hz, zero-phase": lambda x: zero_phase_filter(b_bw, a_bw, x),
    }


def detection_time(times, speed):
    """First time the speed is DETECT_DROP_KMH below its running maximum (braking detected)."""
    peak = -np.inf
    for i in range(len(times)):
        peak = max(peak, speed[i])
        if speed[i] <= peak - DETECT_DROP_KMH:
            # interpolate the crossing between samples i-1 and i
            level = peak - DETECT_DROP_KMH
            fraction = (speed[i - 1] - level) / (speed[i - 1] - speed[i])
            return times[i - 1] + fraction * (times[i] - times[i - 1])
    return np.nan


def mid_braking_time(times, speed, level):
    """First time the speed falls through `level` (used halfway down the braking zone)."""
    for i in range(1, len(times)):
        if speed[i - 1] > level >= speed[i]:
            fraction = (speed[i - 1] - level) / (speed[i - 1] - speed[i])
            return times[i - 1] + fraction * (times[i] - times[i - 1])
    return np.nan


def part_a_braking_shift(intervals, probs):
    """Two detectors, because the answer depends on WHERE on the event you look:
      onset: speed 10 km/h below its running peak (the very start of braking,
             a sharp kink in the speed curve);
      mid:   speed halfway between the entry and minimum speeds (the middle of
             the braking zone, where the speed curve is nearly straight).
    """
    rng = np.random.default_rng(SEED)
    filters = filters_to_compare()
    shifts = {"onset": {name: [] for name in filters}, "mid": {name: [] for name in filters}}
    example = None
    for lap in range(LAPS):
        truth = make_true_corner(random_corner_params("heavy_braking", rng))
        samples = degrade_like_feed(truth, intervals, probs, rng, max_interval_s=0.6)
        grid, speed, _ = to_uniform_grid(samples["time_s"], samples["speed_kmh"], GRID_STEP_S)
        events = truth["events"]
        level = 0.5 * (events["entry_speed_kmh"] + events["apex"]["speed_kmh"])
        true_times = {"onset": detection_time(truth["time_s"], truth["speed_kmh"]),
                      "mid": mid_braking_time(truth["time_s"], truth["speed_kmh"], level)}
        for name, apply in filters.items():
            filtered = apply(speed)
            found = {"onset": detection_time(grid, filtered), "mid": mid_braking_time(grid, filtered, level)}
            for detector in ["onset", "mid"]:
                shift = (np.interp(found[detector], truth["time_s"], truth["distance_m"])
                         - np.interp(true_times[detector], truth["time_s"], truth["distance_m"]))
                shifts[detector][name].append(shift)
        if lap == 0:
            example = (truth, grid, speed)

    table = {}
    print("\n--- A. Braking-point shift caused by each filter (heavy braking, "
          f"{LAPS} synthetic laps, 4 Hz grid) ---")
    print(f"{'':32s} {'onset detector':>22s} {'mid-braking detector':>24s}")
    for name in filters:
        onset = shifts["onset"][name]
        mid = shifts["mid"][name]
        table[name] = {"onset_mean_shift_m": float(np.mean(onset)), "onset_std_m": float(np.std(onset)),
                       "mid_mean_shift_m": float(np.mean(mid)), "mid_std_m": float(np.std(mid))}
        print(f"{name:32s} {np.mean(onset):+8.1f} m (+-{np.std(onset):4.1f})"
              f"   {np.mean(mid):+8.1f} m (+-{np.std(mid):4.1f})")

    # Figure: one example lap, zoomed on the braking zone
    truth, grid, speed = example
    t0 = truth["events"]["brake_onset"]["t"]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.plot(truth["time_s"] - t0, truth["speed_kmh"], color=TEXT_SECONDARY, linewidth=2.2,
            label="truth (500 Hz)")
    styles = [("moving average 5, causal", SERIES[1], "-"),
              ("Butterworth 0.5 Hz, causal", SERIES[1], "--"),
              ("Butterworth 0.5 Hz, zero-phase", SERIES[0], "-")]
    for name, color, linestyle in styles:
        ax.plot(grid - t0, filters_to_compare()[name](speed), color=color, linestyle=linestyle,
                linewidth=1.6, label=f"{name} (onset {table[name]['onset_mean_shift_m']:+.0f} m, "
                                      f"mid-braking {table[name]['mid_mean_shift_m']:+.0f} m)")
    ax.set_xlim(-2.0, 3.5)
    ax.set_xlabel("Time from the true brake onset (s)")
    ax.set_ylabel("Speed (km/h)")
    ax.set_title("Causal smoothing delays braking; zero-phase smoothing doesn't delay it, but smears its start",
                 pad=12)
    ax.legend(fontsize=9, loc="lower left")
    fig.savefig(OUT_DIR / "braking_shift.png", bbox_inches="tight")
    plt.close(fig)
    return table


def part_b_frequency_responses():
    fs = 1.0 / GRID_STEP_S
    designs = {
        "moving average 5": moving_average_coefficients(5),
        "EMA alpha 0.5": ema_coefficients(0.5),
        "Butterworth 0.5 Hz (order 2)": butterworth_lowpass(0.5, fs, order=2),
    }
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.5))
    summary = {}
    for column, (name, (b, a)) in enumerate(designs.items()):
        freqs, magnitude, delay_s = frequency_response(b, a, fs)
        zeros, poles = poles_and_zeros(b, a)
        low = freqs < 0.3
        summary[name] = {"group_delay_at_low_freq_s": float(np.median(delay_s[low])),
                         "poles": [str(np.round(p, 3)) for p in poles],
                         "zeros": [str(np.round(z, 3)) for z in zeros]}

        ax = axes[0, column]
        ax.plot(freqs, 20 * np.log10(np.maximum(magnitude, 1e-4)), color=SERIES[0])
        ax.plot(freqs, 20 * np.log10(np.maximum(magnitude ** 2, 1e-4)), color=SERIES[0],
                linestyle="--", linewidth=1.2)
        ax.set_ylim(-60, 5)
        ax.set_title(name, fontsize=11)
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("Gain (dB)")
        ax2 = ax.twinx()
        ax2.plot(freqs, delay_s, color=SERIES[1], linewidth=1.2)
        ax2.set_ylim(-0.2, 2.0)
        ax2.set_ylabel("Group delay (s)", color=SERIES[1])
        ax2.grid(False)

        ax = axes[1, column]
        circle = np.linspace(0, 2 * np.pi, 200)
        ax.plot(np.cos(circle), np.sin(circle), color=TEXT_SECONDARY, linewidth=0.8)
        ax.plot(np.real(zeros), np.imag(zeros), "o", markerfacecolor="none", markersize=9,
                color=SERIES[0], label="zeros")
        ax.plot(np.real(poles), np.imag(poles), "x", markersize=9, color=SERIES[1], label="poles")
        ax.set_aspect("equal")
        ax.set_xlim(-1.4, 1.4)
        ax.set_ylim(-1.4, 1.4)
        ax.set_xlabel("Real part")
        ax.set_ylabel("Imaginary part")
        ax.legend(fontsize=8, loc="lower left")
    fig.suptitle("Gain (solid: forward only, dashed: zero-phase = |H|²), group delay (orange), "
                 "and pole-zero plots, on a 4 Hz grid", x=0.0, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "frequency_responses.png", bbox_inches="tight")
    plt.close(fig)

    print("\n--- B. Group delay at low frequency (forward filtering) ---")
    for name, values in summary.items():
        print(f"{name:30s} {values['group_delay_at_low_freq_s']:.3f} s   poles {values['poles']}")
    return summary


def part_c_derivative_noise(intervals, probs):
    rng = np.random.default_rng(SEED + 1)
    truth = make_true_corner(random_corner_params("medium", rng))
    samples = degrade_like_feed(truth, intervals, probs, rng, max_interval_s=0.6)
    times = samples["time_s"]
    speed_ms = samples["speed_kmh"] / 3.6
    raw = -np.diff(speed_ms) / np.diff(times)
    raw_times = 0.5 * (times[1:] + times[:-1])

    grid, grid_speed, _ = to_uniform_grid(times, speed_ms, 0.04)
    b, a = butterworth_lowpass(1.0, 25.0, order=2)
    smooth = -derivative(zero_phase_filter(b, a, grid_speed), 0.04)

    fig, ax = plt.subplots(figsize=(10, 4.4))
    ax.plot(truth["time_s"], -truth["accel_ms2"] / 9.81, color=TEXT_SECONDARY, linewidth=2.2,
            label="truth")
    ax.plot(raw_times, raw / 9.81, "o-", color=SERIES[1], markersize=4, linewidth=1.0,
            label="raw: speed difference / time difference")
    ax.plot(grid, smooth / 9.81, color=SERIES[0], linewidth=1.6,
            label="resampled to 40 ms, zero-phase 1 Hz low-pass, then differentiated")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Deceleration (g)")
    ax.set_title("Deceleration from speed rounded to 1 km/h, synthetic medium corner", pad=12)
    ax.legend(fontsize=9, loc="upper left")
    fig.savefig(OUT_DIR / "derivative_noise.png", bbox_inches="tight")
    plt.close(fig)

    straight = raw_times < truth["events"]["brake_onset"]["t"] - 0.5
    true_on_straight = np.interp(raw_times[straight], truth["time_s"], -truth["accel_ms2"])
    noise = float(np.std(raw[straight] - true_on_straight))
    print("\n--- C. Derivative noise on the straight before braking ---")
    print(f"raw first-difference deceleration: error std {noise:.2f} m/s^2 ({noise / 9.81:.3f} g)")
    return {"raw_decel_error_std_on_straight_ms2": noise}


def part_d_cutoff_from_real_spectrum():
    """Welch spectrum of real speed (Abu Dhabi Q + FP2 kept laps) on a 4 Hz grid.

    The rounding noise is (nearly) white with variance 1/12 (km/h)^2, so its
    one-sided spectral density is (1/12) / (fs/2) = 0.042 (km/h)^2/Hz at
    fs = 4 Hz. The signal's spectrum falls steeply with frequency; the cutoff
    is where it meets that floor: above it, the "signal" is mostly rounding noise.
    """
    logging.getLogger("fastf1").setLevel(logging.WARNING)
    fs = 1.0 / GRID_STEP_S
    spectra = []
    for session_name in ["Q", "FP2"]:
        session = load_session(2024, "Abu Dhabi", session_name)
        for driver in ["NOR", "PIA"]:
            kept, _ = select_laps(session.laps.pick_drivers(driver))
            for _, lap in kept.iterrows():
                car = lap.get_car_data()
                times = car["SessionTime"].dt.total_seconds().to_numpy()
                _, speed, _ = to_uniform_grid(times, car["Speed"].to_numpy(dtype=float), GRID_STEP_S)
                freqs, psd = signal.welch(speed - np.mean(speed), fs=fs, nperseg=128)
                spectra.append(psd)
    mean_psd = np.mean(spectra, axis=0)
    floor = (1.0 / 12.0) / (fs / 2.0)
    above = np.where(mean_psd > floor)[0]
    crossing_hz = float(freqs[above[-1]]) if len(above) else float("nan")
    # The spectrum flattens out at high frequency, and a flat spectrum behaves
    # like noise. Plateau = median level from 1.5 Hz to Nyquist; knee = the
    # first frequency where the spectrum is within 2x of that plateau.
    plateau = float(np.median(mean_psd[freqs >= 1.5]))
    knee_hz = float(freqs[np.where(mean_psd <= 2 * plateau)[0][0]])

    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.semilogy(freqs, mean_psd, color=SERIES[0], linewidth=1.8,
                label=f"real speed, mean of {len(spectra)} laps")
    ax.axhline(floor, color=SERIES[1], linestyle="--", linewidth=1.2,
               label="white noise from 1 km/h rounding")
    ax.axhline(plateau, color=TEXT_SECONDARY, linestyle=":", linewidth=1.0)
    ax.axvline(knee_hz, color=TEXT_SECONDARY, linestyle=":", linewidth=1.0)
    ax.text(knee_hz, ax.get_ylim()[1], f" flattens out (knee) at {knee_hz:.2f} Hz",
            va="top", fontsize=9, color=TEXT_SECONDARY)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Power spectral density ((km/h)²/Hz)")
    ax.set_title("Spectrum of real speed (2024 Abu Dhabi, NOR + PIA), 4 Hz grid", pad=12)
    ax.legend(fontsize=9)
    fig.savefig(OUT_DIR / "real_speed_spectrum.png", bbox_inches="tight")
    plt.close(fig)

    print("\n--- D. Cutoff from the spectrum of real laps ---")
    print(f"{len(spectra)} laps; rounding-noise floor {floor:.4f} (km/h)^2/Hz; "
          f"the speed spectrum stays above it up to {crossing_hz:.2f} Hz (the grid's Nyquist limit)")
    print(f"high-frequency plateau {plateau:.3f} (km/h)^2/Hz = {plateau / floor:.0f} x the rounding floor; "
          f"knee at {knee_hz:.2f} Hz")
    return {"laps": len(spectra), "noise_floor": floor, "signal_meets_floor_hz": crossing_hz,
            "plateau": plateau, "plateau_over_floor": plateau / floor, "knee_hz": knee_hz,
            "frequencies_hz": [float(f) for f in freqs], "mean_psd": [float(p) for p in mean_psd]}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    apply_style()
    intervals, probs = load_interval_distribution(HISTOGRAM)
    summary = {
        "A_braking_shift_heavy_braking": part_a_braking_shift(intervals, probs),
        "B_frequency_responses": part_b_frequency_responses(),
        "C_derivative_noise": part_c_derivative_noise(intervals, probs),
        "D_cutoff_from_real_spectrum": part_d_cutoff_from_real_spectrum(),
    }
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)
    print(f"\nSaved results to {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

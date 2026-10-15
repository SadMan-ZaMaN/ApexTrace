"""Smoothing filters, their frequency response, and the group-delay trap.

Why this module exists: speed comes in whole km/h, so its derivative
(deceleration) is noisy, and noise must be smoothed before finding events.
But a normal ("causal") smoothing filter only looks at the past, so its
output lags behind the input. That lag is the group delay. At 250 km/h a
lag of 0.5 s moves an apparent braking point by ~35 m, more than the
differences between drivers we want to see.

The fix is zero-phase filtering (scipy's filtfilt): run the filter forward,
then run it again backward over the reversed output. The backward pass
undoes the forward pass's delay exactly. The result has magnitude |H|^2
and zero phase: smoothing with no shift.

All filters here assume a uniform grid (see resampling.to_uniform_grid).
"""

import numpy as np
from scipy import signal


def moving_average(x, n):
    """Causal moving average of n samples: y[k] = mean of x[k-n+1 .. k].

    Transfer function: H(z) = (1/n)(1 + z^-1 + ... + z^-(n-1)): n-1 zeros
    spread around the unit circle (all n-th roots of unity except z = 1).
    Delay: (n-1)/2 samples. Example: n = 5 on a 0.25 s grid -> 2 samples
    = 0.5 s late.
    The first n-1 outputs average over fewer samples (the start is padded
    with the first value, so a constant input gives a constant output).
    """
    x = np.asarray(x, dtype=float)
    padded = np.concatenate([np.full(n - 1, x[0]), x])
    y = np.empty(len(x))
    for k in range(len(x)):
        y[k] = np.mean(padded[k:k + n])
    return y


def moving_average_coefficients(n):
    """(b, a) of the n-sample moving average, for frequency-response plots."""
    return np.ones(n) / n, np.array([1.0])


def ema(x, alpha):
    """Exponential moving average: y[k] = alpha * x[k] + (1 - alpha) * y[k-1].

    Transfer function: H(z) = alpha / (1 - (1 - alpha) z^-1): one pole at
    z = 1 - alpha (inside the unit circle, so stable for 0 < alpha <= 1).
    Small alpha = heavy smoothing = long memory = more delay. Its delay at
    low frequency is (1 - alpha) / alpha samples: alpha = 0.5 -> 1 sample.
    """
    x = np.asarray(x, dtype=float)
    y = np.empty(len(x))
    y[0] = x[0]
    for k in range(1, len(x)):
        y[k] = alpha * x[k] + (1.0 - alpha) * y[k - 1]
    return y


def ema_coefficients(alpha):
    """(b, a) of the EMA, for frequency-response and pole-zero plots."""
    return np.array([alpha]), np.array([1.0, -(1.0 - alpha)])


def butterworth_lowpass(cutoff_hz, sample_rate_hz, order=2):
    """(b, a) of a Butterworth low-pass filter.

    Butterworth = as flat as possible in the passband (no ripple), then a
    smooth roll-off. Order 2 falls by 12 dB per octave above the cutoff.
    Example: cutoff 1 Hz on a 25 Hz grid -> passes the slow speed changes
    of braking (< 1 Hz), suppresses the fast steps of 1 km/h rounding.
    """
    nyquist = sample_rate_hz / 2.0
    return signal.butter(order, cutoff_hz / nyquist, btype="low")


def causal_filter(b, a, x):
    """Apply a filter forward only (like a real-time system). This output LAGS.

    The filter starts in its steady state for the first value (lfilter_zi),
    so a constant input gives a constant output from the start instead of
    rising from zero.
    """
    x = np.asarray(x, dtype=float)
    initial_state = signal.lfilter_zi(b, a) * x[0]
    y, _ = signal.lfilter(b, a, x, zi=initial_state)
    return y


def zero_phase_filter(b, a, x):
    """Apply a filter forward and then backward (scipy filtfilt): no lag.

    The effective response is |H|^2 (twice the attenuation) with zero phase,
    so events stay where they are. Can only be done offline, on recorded
    data, which is exactly our situation.
    """
    return signal.filtfilt(b, a, np.asarray(x, dtype=float))


def frequency_response(b, a, sample_rate_hz, points=512):
    """(frequencies in Hz, |H| magnitude, group delay in seconds).

    Group delay = -d(phase)/d(omega): how long each frequency is delayed.
    For a symmetric FIR filter like the moving average it is the same for
    all frequencies: (n-1)/2 samples.
    """
    freqs, response = signal.freqz(b, a, worN=points, fs=sample_rate_hz)
    _, delay_samples = signal.group_delay((b, a), w=points, fs=sample_rate_hz)
    return freqs, np.abs(response), delay_samples / sample_rate_hz


def poles_and_zeros(b, a):
    """Zeros (roots of b) and poles (roots of a) of H(z) = B(z) / A(z)."""
    return np.roots(b), np.roots(a)


def derivative(x, step_s):
    """Rate of change on a uniform grid (central differences; one-sided at the ends).

    The first difference H(z) = 1 - z^-1 has |H| = 2|sin(w/2)|: zero at
    DC, largest at Nyquist. It is a high-pass filter, so it amplifies noise.
    Example: speed rounded to 1 km/h (0.278 m/s). One rounding step over
    0.27 s looks like 1.0 m/s^2 (0.1 g) of fake acceleration. On average:
    each rounding error has std 0.278/sqrt(12) = 0.080 m/s, so a first
    difference over 0.27 s has noise std sqrt(2) * 0.080 / 0.27 = 0.42 m/s^2
    (0.04 g), even when the true deceleration is perfectly constant.
    (np.gradient uses central differences over two intervals, which
    roughly halves this.)
    """
    return np.gradient(np.asarray(x, dtype=float), step_s)

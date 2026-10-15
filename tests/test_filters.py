"""Tests for filters.py: delays of causal filters, no delay with zero-phase filtering."""

import numpy as np
import pytest

from apextrace.filters import (
    butterworth_lowpass,
    causal_filter,
    derivative,
    ema,
    ema_coefficients,
    frequency_response,
    moving_average,
    moving_average_coefficients,
    poles_and_zeros,
    zero_phase_filter,
)


def half_crossing(x):
    """Index (with linear interpolation) where x first falls through 0.5."""
    for i in range(1, len(x)):
        if x[i - 1] >= 0.5 > x[i]:
            return (i - 1) + (x[i - 1] - 0.5) / (x[i - 1] - x[i])
    return None


def braking_step(length=100, at=50):
    """1 before index `at`, 0 from `at` on: a sudden drop, like speed at a brake point."""
    x = np.ones(length)
    x[at:] = 0.0
    return x


def test_moving_average_of_5_is_2_samples_late():
    x = braking_step()
    delay = half_crossing(moving_average(x, 5)) - half_crossing(x)
    assert delay == pytest.approx(2.0)


def test_zero_phase_filter_does_not_shift_the_step():
    x = braking_step()
    b, a = butterworth_lowpass(cutoff_hz=1.0, sample_rate_hz=4.0, order=2)
    causal_delay = half_crossing(causal_filter(b, a, x)) - half_crossing(x)
    zero_phase_delay = half_crossing(zero_phase_filter(b, a, x)) - half_crossing(x)
    assert causal_delay > 0.5               # the causal filter lags
    assert abs(zero_phase_delay) < 0.05     # filtfilt doesn't


def test_moving_average_group_delay_is_constant():
    b, a = moving_average_coefficients(5)
    freqs, _, delay_s = frequency_response(b, a, sample_rate_hz=4.0, points=64)
    low = freqs < 0.6  # stay away from the zeros at 0.8 and 1.6 Hz
    assert np.allclose(delay_s[low], 2 / 4.0, atol=1e-6)  # 2 samples at 4 Hz = 0.5 s


def test_ema_has_one_pole_at_one_minus_alpha():
    b, a = ema_coefficients(0.3)
    _, poles = poles_and_zeros(b, a)
    assert poles == pytest.approx([0.7])


def test_ema_matches_its_difference_equation():
    y = ema([0.0, 10.0, 10.0], alpha=0.5)
    assert list(y) == pytest.approx([0.0, 5.0, 7.5])


def test_causal_filter_starts_in_steady_state():
    b, a = butterworth_lowpass(1.0, 4.0)
    y = causal_filter(b, a, np.full(20, 300.0))
    assert np.allclose(y, 300.0)


def test_derivative_of_a_ramp():
    step = 0.04
    x = 90.0 - 50.0 * np.arange(0, 2, step)  # braking at 50 m/s^2
    assert np.allclose(derivative(x, step), -50.0)


def test_derivative_amplifies_rounding_noise():
    # A gentle real deceleration of 0.8 m/s^2, speed rounded to 1 km/h,
    # sampled every 0.27 s. Theory: rounding error std 0.278/sqrt(12) = 0.080
    # m/s per sample; a first difference over 0.27 s has noise std
    # sqrt(2) * 0.080 / 0.27 = 0.42 m/s^2, although the true value is constant.
    t = np.arange(0, 20, 0.27)
    speed_ms = np.round(200.0 - 0.8 * 3.6 * t) / 3.6
    first_difference = np.diff(speed_ms) / 0.27
    assert np.std(first_difference) == pytest.approx(0.42, abs=0.1)
    b, a = butterworth_lowpass(0.5, 1 / 0.27)
    smooth = derivative(zero_phase_filter(b, a, speed_ms), 0.27)
    assert np.std(smooth[10:-10]) < np.std(first_difference) / 5

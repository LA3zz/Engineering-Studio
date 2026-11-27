"""E10 tests: engine.transforms against analytic transforms and definitions."""

from __future__ import annotations

import numpy as np
import pytest

from engstudio.core.errors import DimensionError, ValidationError
from engstudio.engine.transforms import (
    WINDOWS,
    SpectrumResult,
    amplitude_spectrum,
    butter_filter,
    convolve,
    fft,
    fftfreq,
    ifft,
    irfft,
    psd,
    rfft,
    rfftfreq,
    window,
)


def _dft(x):
    """Textbook definition X[k] = sum_n x[n] exp(-2 pi i k n / N), O(N^2)."""
    n = len(x)
    k = np.arange(n).reshape(-1, 1)
    return np.exp(-2j * np.pi * k * np.arange(n) / n) @ np.asarray(x)


# -- transforms ----------------------------------------------------------------------
def test_fft_matches_definition_real_and_complex():
    rng = np.random.default_rng(1)
    x = rng.standard_normal(16)
    z = x + 1j * rng.standard_normal(16)
    assert np.allclose(fft(x), _dft(x), atol=1e-12)
    assert np.allclose(fft(z), _dft(z), atol=1e-12)


def test_fft_known_pairs():
    """Impulse -> flat spectrum; constant -> N at DC; cos at bin k -> N/2 at k and N-k."""
    n = 16
    delta = np.zeros(n)
    delta[0] = 1.0
    assert np.allclose(fft(delta), np.ones(n), atol=1e-14)
    assert np.allclose(fft(np.full(n, 2.0)), [2.0 * n] + [0.0] * (n - 1), atol=1e-12)
    spec = fft(np.cos(2 * np.pi * 3 * np.arange(n) / n))
    expected = np.zeros(n)
    expected[3] = expected[n - 3] = n / 2
    assert np.allclose(spec, expected, atol=1e-12)


def test_ifft_roundtrip_and_parseval():
    """Parseval: sum |x|^2 = (1/N) sum |X|^2."""
    rng = np.random.default_rng(2)
    z = rng.standard_normal(33) + 1j * rng.standard_normal(33)
    big = fft(z)
    assert np.allclose(ifft(big), z, atol=1e-12)
    assert np.sum(np.abs(z) ** 2) == pytest.approx(np.sum(np.abs(big) ** 2) / 33, rel=1e-12)


def test_fft_zero_pad_and_truncate():
    x = [1.0, 2.0, 3.0, 4.0]
    assert np.allclose(fft(x, 8), _dft(x + [0.0] * 4), atol=1e-12)
    assert np.allclose(fft(x, 2), _dft([1.0, 2.0]), atol=1e-12)


@pytest.mark.parametrize("n", [8, 9])
def test_rfft_irfft(n):
    rng = np.random.default_rng(3)
    x = rng.standard_normal(n)
    r = rfft(x)
    assert r.size == n // 2 + 1
    assert np.allclose(r, fft(x)[: n // 2 + 1], atol=1e-12)
    assert np.allclose(irfft(r, n), x, atol=1e-12)


def test_irfft_default_length_is_even():
    x = np.array([1.0, -2.0, 0.5, 3.0, 1.0, -1.0])
    assert np.allclose(irfft(rfft(x)), x, atol=1e-12)
    with pytest.raises(ValidationError, match="single element"):
        irfft([1.0])
    assert irfft([2.0], 1)[0] == pytest.approx(2.0)


def test_frequency_axes():
    """Bin spacing 1/(n d); negative frequencies in the upper half."""
    assert np.allclose(fftfreq(8, 0.5), np.array([0, 1, 2, 3, -4, -3, -2, -1]) * 0.25)
    assert np.allclose(rfftfreq(8, 0.5), [0.0, 0.25, 0.5, 0.75, 1.0])


def test_inputs_not_mutated():
    x = np.array([1.0, 2.0, 3.0, 4.0])
    keep = x.copy()
    fft(x)
    amplitude_spectrum(x, 10.0, window="hann")
    butter_filter(np.tile(x, 50), 100.0, 10.0)
    assert np.array_equal(x, keep)


# -- windows -------------------------------------------------------------------------
def test_window_values():
    """Hann 0.5-0.5cos, Hamming 0.54-0.46cos (periodic: denominator N; symmetric: N-1)."""
    assert np.allclose(window("hann", 4), [0.0, 0.5, 1.0, 0.5], atol=1e-15)
    assert np.allclose(window("hann", 5, periodic=False), [0, 0.5, 1, 0.5, 0], atol=1e-15)
    assert np.allclose(window("hamming", 4), [0.08, 0.54, 1.0, 0.54], atol=1e-15)
    assert np.array_equal(window("rect", 5), np.ones(5))
    assert np.array_equal(window("boxcar", 3), np.ones(3))
    assert window("hann", 1)[0] == 1.0


@pytest.mark.parametrize("name", WINDOWS)
def test_all_windows_have_requested_length_and_peak_one(name):
    # flattop: SciPy's published coefficients are rounded to 9 digits and sum to 1.000000003
    w = window(name, 64)
    assert w.shape == (64,) and np.max(w) == pytest.approx(1.0, abs=1e-8)


# -- spectra -------------------------------------------------------------------------
@pytest.mark.parametrize("win", ["rect", "hann", "hamming", "blackman", "flattop"])
def test_amplitude_spectrum_recovers_bin_centred_sine(win):
    """A sine of amplitude 3 on an exact bin shows amplitude 3 (window gain corrected)."""
    fs, n, k0 = 200.0, 400, 20
    f0 = k0 * fs / n
    t = np.arange(n) / fs
    res = amplitude_spectrum(3.0 * np.sin(2 * np.pi * f0 * t), fs, window=win)
    assert isinstance(res, SpectrumResult) and res.kind == "amplitude"
    assert res.freq[k0] == pytest.approx(f0, rel=1e-12)
    assert res.values[k0] == pytest.approx(3.0, rel=1e-9)
    assert int(np.argmax(res.values)) == k0


def test_amplitude_spectrum_rect_has_no_leakage_and_dc_nyquist_not_doubled():
    n, fs = 64, 64.0
    t = np.arange(n) / fs
    x = 2.0 + 3.0 * np.sin(2 * np.pi * 5 * t) + 1.5 * np.cos(np.pi * np.arange(n))
    res = amplitude_spectrum(x, fs)
    assert res.values[0] == pytest.approx(2.0, abs=1e-12)
    assert res.values[5] == pytest.approx(3.0, abs=1e-12)
    assert res.values[-1] == pytest.approx(1.5, abs=1e-12) and res.freq[-1] == 32.0
    other = np.delete(res.values, [0, 5, n // 2])
    assert np.max(other) < 1e-12


def test_amplitude_spectrum_odd_length_and_zero_padding():
    n, fs = 9, 9.0
    t = np.arange(n) / fs
    x = 3.0 * np.sin(2 * np.pi * 2 * t)
    odd = amplitude_spectrum(x, fs)
    assert odd.values[2] == pytest.approx(3.0, abs=1e-12) and odd.freq.size == 5
    padded = amplitude_spectrum(x, fs, n=4 * n)
    assert padded.freq.size == 2 * n + 1
    assert padded.values[8] == pytest.approx(3.0, abs=1e-12)  # same frequency, 4x finer grid
    assert padded.freq[8] == pytest.approx(2.0, abs=1e-12)


def test_psd_parseval_rect_no_detrend():
    """With a rectangular window the one-sided density integrates to the mean square."""
    rng = np.random.default_rng(4)
    x = rng.standard_normal(256)
    for fs in (1.0, 250.0):
        res = psd(x, fs, window="rect", detrend=False)
        df = res.freq[1] - res.freq[0]
        assert np.sum(res.values) * df == pytest.approx(np.mean(x**2), rel=1e-10)


def test_psd_sine_power_hann():
    """Bin-centred sine of amplitude A carries power A^2/2 (integral of the density)."""
    fs, n, k0, amp = 100.0, 200, 30, 2.0
    t = np.arange(n) / fs
    res = psd(amp * np.sin(2 * np.pi * (k0 * fs / n) * t), fs, window="hann", detrend=False)
    df = fs / n
    assert np.sum(res.values) * df == pytest.approx(amp**2 / 2, rel=1e-9)
    assert res.kind == "psd" and res.freq[-1] == fs / 2


def test_psd_detrend_removes_offset():
    t = np.arange(200) / 100.0
    x = 5.0 + np.sin(2 * np.pi * 10 * t)
    assert psd(x, 100.0, detrend=True).values[0] < 1e-20
    assert psd(x, 100.0, detrend=False).values[0] > 1.0


# -- convolution ---------------------------------------------------------------------
def test_convolve_modes_hand_computed():
    a, b = [1.0, 2.0, 3.0], [0.0, 1.0, 0.5]
    assert np.allclose(convolve(a, b), [0.0, 1.0, 2.5, 4.0, 1.5])
    assert np.allclose(convolve(a, b, "same"), [1.0, 2.5, 4.0])
    assert np.allclose(convolve(a, b, "valid"), [2.5])


def test_convolve_polynomial_product_and_theorem():
    """(1+x)^2 = 1+2x+x^2; convolution theorem: fft(a*b) = fft(a) fft(b) (zero-padded)."""
    assert np.allclose(convolve([1, 1], [1, 1]), [1, 2, 1])
    rng = np.random.default_rng(5)
    a, b = rng.standard_normal(7), rng.standard_normal(5)
    c = convolve(a, b)
    assert np.allclose(fft(c), fft(a, c.size) * fft(b, c.size), atol=1e-12)
    za = convolve([1 + 1j, 2], [1j])
    assert np.allclose(za, [1j * (1 + 1j), 2j])


# -- Butterworth ---------------------------------------------------------------------
def _tones(fs, n, freqs):
    t = np.arange(n) / fs
    return t, [np.sin(2 * np.pi * f * t) for f in freqs]


def test_lowpass_zero_phase_removes_high_tone():
    """|H|^2 = 1/(1+(f/fc)^(2n)): 200 Hz through a 50 Hz order-4 filter is ~1.5e-5."""
    t, (lo, hi) = _tones(1000.0, 4000, (5.0, 200.0))
    y = butter_filter(lo + hi, 1000.0, 50.0, order=4)
    assert y.shape == lo.shape
    assert np.max(np.abs(y[500:-500] - lo[500:-500])) < 1e-3


def test_cutoff_is_minus_3db_single_pass():
    """Butterworth gain at the cutoff is 1/sqrt(2) (single pass, steady state)."""
    fs, fc = 1000.0, 50.0
    _, (tone,) = _tones(fs, 4000, (fc,))
    y = butter_filter(tone, fs, fc, order=4, zero_phase=False)
    res = amplitude_spectrum(y[2000:], fs)  # 100 whole cycles, transient gone
    assert np.max(res.values) == pytest.approx(1 / np.sqrt(2), abs=0.01)


def test_highpass_removes_dc_and_bandpass_selects():
    fs = 1000.0
    t, (a, b, c) = _tones(fs, 4000, (10.0, 100.0, 400.0))
    hp = butter_filter(5.0 + b, fs, 20.0, btype="high", order=4)
    assert abs(np.mean(hp[500:-500])) < 1e-3
    bp = butter_filter(a + b + c, fs, [60.0, 160.0], btype="band", order=4)
    assert np.max(np.abs(bp[500:-500] - b[500:-500])) < 0.02
    bs = butter_filter(a + b + c, fs, [60.0, 160.0], btype="bandstop", order=4)
    assert np.max(np.abs(bs[500:-500] - (a + c)[500:-500])) < 0.05


# -- validation ----------------------------------------------------------------------
@pytest.mark.parametrize("bad", [[], [np.nan, 1.0], [np.inf], ["a"], "xy"])
def test_fft_rejects_bad_input(bad):
    with pytest.raises(ValidationError):
        fft(bad)


def test_shape_and_n_errors():
    with pytest.raises(DimensionError):
        fft(np.ones((3, 3)))
    for n in (0, -4, 2.5, True, "8"):
        with pytest.raises(ValidationError, match="n"):
            fft([1.0, 2.0], n)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        rfft([1 + 1j, 2])
    with pytest.raises(ValidationError):
        fftfreq(0)
    with pytest.raises(ValidationError):
        fftfreq(8, -1.0)
    with pytest.raises(ValidationError):
        rfftfreq(8, 0.0)


@pytest.mark.parametrize("name,n", [("kaiser", 8), ("Hann", 8), (3, 8), ("hann", 0)])
def test_window_errors(name, n):
    with pytest.raises(ValidationError):
        window(name, n)  # type: ignore[arg-type]


def test_spectrum_errors():
    x = np.ones(8)
    for fs in (0.0, -1.0, np.nan, np.inf, "a"):
        with pytest.raises(ValidationError):
            amplitude_spectrum(x, fs)  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            psd(x, fs)  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="zero-padding"):
        amplitude_spectrum(x, 1.0, n=4)
    with pytest.raises(ValidationError, match="at least 2"):
        amplitude_spectrum([1.0], 1.0)
    with pytest.raises(ValidationError, match="at least 2"):
        psd([1.0], 1.0)
    with pytest.raises(ValidationError, match="window"):
        psd(x, 1.0, window="nope")
    with pytest.raises(ValidationError):
        amplitude_spectrum([1 + 1j, 2.0], 1.0)


def test_convolve_and_filter_errors():
    with pytest.raises(ValidationError, match="mode"):
        convolve([1.0], [1.0], "circular")
    with pytest.raises(ValidationError):
        convolve([], [1.0])
    x = np.ones(500)
    for kwargs in ({"btype": "notch"}, {"order": 0}, {"order": 21}, {"order": 2.5}):
        with pytest.raises(ValidationError):
            butter_filter(x, 100.0, 10.0, **kwargs)
    for cutoff in (0.0, -5.0, 50.0, 60.0, np.nan, [10.0, 20.0]):
        with pytest.raises(ValidationError):
            butter_filter(x, 100.0, cutoff)
    for cutoff in (10.0, [20.0, 10.0], [10.0, 10.0], [10.0, 50.0], [10.0, 20.0, 30.0]):
        with pytest.raises(ValidationError):
            butter_filter(x, 100.0, cutoff, btype="band")
    with pytest.raises(ValidationError, match="too short"):
        butter_filter(np.ones(5), 100.0, 10.0)
    with pytest.raises(ValidationError):
        butter_filter(x, 0.0, 10.0)

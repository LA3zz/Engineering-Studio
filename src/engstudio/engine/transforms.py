"""Fourier transforms, spectra, convolution and Butterworth filtering (E10).

Conventions:
- ``fft`` / ``ifft`` / ``rfft`` / ``irfft`` use the standard unnormalised forward transform
  X[k] = sum_n x[n] exp(-2j*pi*k*n/N) and the 1/N inverse (same as NumPy and MATLAB).
  Inputs are validated 1-D copies (scalar, row or column accepted; NaN/Inf rejected).
  ``n`` zero-pads or truncates. ``irfft`` without ``n`` assumes an even output length 2*(m-1).
- ``amplitude_spectrum``: single-sided, window-gain corrected so a bin-centred sine of
  amplitude A shows A (DC and, for even length, Nyquist are not doubled). The window is
  periodic (DFT-even). ``n`` may only zero-pad.
- ``psd``: one-sided periodogram (SciPy ``periodogram``, scaling "density", units x^2/Hz); with
  ``detrend=True`` the mean is removed first.
- ``butter_filter``: Butterworth in second-order sections; ``zero_phase=True`` runs forward and
  backward (squared magnitude, no phase shift, needs a signal longer than the filter padding).
  Cutoffs are in Hz and must lie in (0, fs/2).
- Sampling is assumed uniform; nothing here can detect uneven sampling.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import signal

from engstudio.core.diagnostics import Diagnostic
from engstudio.core.errors import ValidationError
from engstudio.engine.validation import as_vector

__all__ = [
    "SpectrumResult", "WINDOWS", "amplitude_spectrum", "butter_filter", "convolve", "fft",
    "fftfreq", "ifft", "irfft", "psd", "rfft", "rfftfreq", "window",
]

_SCIPY_WINDOW = {"rect": "boxcar", "boxcar": "boxcar", "hann": "hann", "hamming": "hamming",
                 "blackman": "blackman", "bartlett": "bartlett", "flattop": "flattop"}
WINDOWS = tuple(_SCIPY_WINDOW)
_BTYPES = ("low", "high", "band", "bandstop")


@dataclass(frozen=True, eq=False)
class SpectrumResult:
    freq: NDArray
    values: NDArray
    kind: str
    window: str
    fs: float
    diagnostics: tuple[Diagnostic, ...] = ()


# -- helpers -------------------------------------------------------------------------
def _positive_int(v: object, name: str) -> int:
    if isinstance(v, bool) or not isinstance(v, (int, np.integer)) or v < 1:
        raise ValidationError(f"{name}: must be a positive integer")
    return int(v)


def _positive_real(v: object, name: str) -> float:
    arr = np.asarray(v)
    if arr.size != 1 or arr.dtype.kind not in "biuf":
        raise ValidationError(f"{name}: expected a positive real scalar")
    x = float(arr.reshape(-1)[0])
    if not np.isfinite(x) or x <= 0:
        raise ValidationError(f"{name}: must be positive and finite (got {x})")
    return x


def _window_name(name: str) -> str:
    if not isinstance(name, str) or name not in _SCIPY_WINDOW:
        raise ValidationError(f"window: must be one of {', '.join(WINDOWS)} (got {name!r})")
    return _SCIPY_WINDOW[name]


# -- transforms ----------------------------------------------------------------------
def fft(x: ArrayLike, n: int | None = None) -> NDArray:
    """Discrete Fourier transform (complex128), zero-padded or truncated to ``n``."""
    xv = as_vector(x, "x")
    return np.fft.fft(xv, None if n is None else _positive_int(n, "n"))


def ifft(X: ArrayLike, n: int | None = None) -> NDArray:
    """Inverse DFT (complex128), 1/N normalised."""
    xv = as_vector(X, "X")
    return np.fft.ifft(xv, None if n is None else _positive_int(n, "n"))


def rfft(x: ArrayLike, n: int | None = None) -> NDArray:
    """DFT of a real signal, non-negative frequencies only (n//2 + 1 values)."""
    xv = as_vector(x, "x", allow_complex=False)
    return np.fft.rfft(xv, None if n is None else _positive_int(n, "n"))


def irfft(X: ArrayLike, n: int | None = None) -> NDArray:
    """Inverse of ``rfft``; ``n`` is the output length (default 2*(len(X)-1), even)."""
    xv = as_vector(X, "X")
    if n is None:
        if xv.size < 2:
            raise ValidationError("irfft: give n when X has a single element")
        return np.fft.irfft(xv)
    return np.fft.irfft(xv, _positive_int(n, "n"))


def fftfreq(n: int, d: float = 1.0) -> NDArray:
    """Frequencies of ``fft`` bins for sample spacing ``d`` seconds (cycles per second)."""
    return np.fft.fftfreq(_positive_int(n, "n"), _positive_real(d, "d"))


def rfftfreq(n: int, d: float = 1.0) -> NDArray:
    """Frequencies of ``rfft`` bins (0 to Nyquist)."""
    return np.fft.rfftfreq(_positive_int(n, "n"), _positive_real(d, "d"))


# -- windows and spectra -------------------------------------------------------------
def window(name: str, n: int, *, periodic: bool = True) -> NDArray:
    """Window of length ``n``: periodic (spectral analysis) or symmetric (filter design)."""
    key = _window_name(name)
    return np.array(signal.get_window(key, _positive_int(n, "n"), fftbins=bool(periodic)),
                    dtype=float)


def amplitude_spectrum(
    x: ArrayLike, fs: float, *, window: str = "rect", n: int | None = None,
) -> SpectrumResult:
    """Single-sided amplitude spectrum of a real signal sampled at ``fs`` Hz."""
    xv = as_vector(x, "x", allow_complex=False)
    if xv.size < 2:
        raise ValidationError("x: need at least 2 samples")
    rate = _positive_real(fs, "fs")
    npts = xv.size if n is None else _positive_int(n, "n")
    if npts < xv.size:
        raise ValidationError("n: must be >= len(x) (zero-padding only)")
    w = np.array(signal.get_window(_window_name(window), xv.size, fftbins=True), dtype=float)
    amp = np.abs(np.fft.rfft(xv * w, npts)) / float(np.sum(w))
    amp[1:] *= 2.0
    if npts % 2 == 0:
        amp[-1] /= 2.0
    return SpectrumResult(np.fft.rfftfreq(npts, 1.0 / rate), amp, "amplitude", window, rate)


def psd(x: ArrayLike, fs: float, *, window: str = "hann", detrend: bool = True) -> SpectrumResult:
    """One-sided power spectral density (periodogram), units of x^2 per Hz."""
    xv = as_vector(x, "x", allow_complex=False)
    if xv.size < 2:
        raise ValidationError("x: need at least 2 samples")
    rate = _positive_real(fs, "fs")
    freq, pxx = signal.periodogram(
        xv, fs=rate, window=_window_name(window), detrend="constant" if detrend else False,
        return_onesided=True, scaling="density")
    return SpectrumResult(np.asarray(freq, dtype=float), np.asarray(pxx, dtype=float), "psd",
                          window, rate)


# -- convolution and filtering --------------------------------------------------------
def convolve(a: ArrayLike, b: ArrayLike, mode: str = "full") -> NDArray:
    """Discrete convolution. ``same`` has the size of ``a``; ``valid`` has no edge effects."""
    if mode not in ("full", "same", "valid"):
        raise ValidationError("mode: must be 'full', 'same' or 'valid'")
    av, bv = as_vector(a, "a"), as_vector(b, "b")
    return np.asarray(signal.convolve(av, bv, mode=mode, method="auto"))


def butter_filter(
    x: ArrayLike, fs: float, cutoff: float | ArrayLike, *, btype: str = "low", order: int = 4,
    zero_phase: bool = True,
) -> NDArray:
    """Butterworth filter of a real signal. ``band``/``bandstop`` take ``(low, high)`` in Hz."""
    xv = as_vector(x, "x", allow_complex=False)
    rate = _positive_real(fs, "fs")
    if btype not in _BTYPES:
        raise ValidationError(f"btype: must be one of {', '.join(_BTYPES)}")
    ordr = _positive_int(order, "order")
    if ordr > 20:
        raise ValidationError("order: must be <= 20")
    edges = as_vector(cutoff, "cutoff", allow_complex=False)
    need = 1 if btype in ("low", "high") else 2
    if edges.size != need:
        raise ValidationError(f"cutoff: {btype} needs {need} frequency value(s), got {edges.size}")
    if np.any(edges <= 0) or np.any(edges >= rate / 2):
        raise ValidationError(f"cutoff: must lie in (0, fs/2) = (0, {rate / 2:g}) Hz")
    if need == 2 and not edges[0] < edges[1]:
        raise ValidationError("cutoff: low edge must be below high edge")
    sos = signal.butter(ordr, edges if need == 2 else edges[0], btype=btype, fs=rate,
                        output="sos")
    try:
        out = signal.sosfiltfilt(sos, xv) if zero_phase else signal.sosfilt(sos, xv)
    except ValueError as exc:
        raise ValidationError(f"x: signal too short for this filter ({exc})") from exc
    if not np.all(np.isfinite(out)):
        raise ValidationError("filter output is not finite (check cutoff and order)")
    return np.asarray(out, dtype=float)

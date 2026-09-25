"""Sonify Mandelbrot orbits.

The core idea: for a point ``c``, compute its orbit under
``z -> z**2 + c`` and treat the sequence of ``z`` values as a (very
short) wavetable. Resampling that wavetable up to audio length gives a
waveform whose character reflects the orbit's dynamics:

* points **inside** the set settle onto a fixed point or a short cycle,
  which resample into a tone (or a chord of a few tones, for a cycle);
* points near the **boundary** wander chaotically before either
  settling or escaping, which resample into noise-like textures;
* points that **escape quickly** produce a short, few-sample "chirp".

``Re(z_n)`` and ``Im(z_n)`` are used as the left/right stereo channels.
"""

from __future__ import annotations

import numpy as np
from numba import njit


@njit(cache=True)
def compute_orbit(
    creal: float, cimag: float, maxiter: int
) -> tuple[np.ndarray, np.ndarray, bool]:
    """Compute the orbit of ``c = creal + cimag*i`` under ``z -> z**2 + c``.

    Returns ``(real, imag, escaped)``, where ``real``/``imag`` hold the
    orbit's real/imaginary parts (length ``maxiter`` if the point never
    escapes, shorter if it does), and ``escaped`` is True if ``|z| > 2``
    was reached within ``maxiter`` iterations.
    """
    real = np.empty(maxiter)
    imag = np.empty(maxiter)
    zr = 0.0
    zi = 0.0
    count = maxiter
    escaped = False
    for n in range(maxiter):
        real[n] = zr
        imag[n] = zi
        if zr * zr + zi * zi > 4.0:
            escaped = True
            count = n + 1
            break
        zr, zi = zr * zr - zi * zi + creal, 2 * zr * zi + cimag
    return real[:count], imag[:count], escaped


def orbit_to_audio(
    x: float,
    y: float,
    duration: float = 3.0,
    sr: int = 44100,
    maxiter: int = 2000,
    fade: float = 0.02,
) -> np.ndarray:
    """Sonify the orbit of ``c = x + y*i`` into a stereo audio buffer.

    Returns a ``(num_samples, 2)`` float32 array in ``[-1, 1]``, with the
    real part of the orbit on the left channel and the imaginary part on
    the right.
    """
    real, imag, _escaped = compute_orbit(x, y, maxiter)
    n = len(real)
    if n < 2:
        # A single-point orbit (shouldn't normally happen, but guard
        # against a degenerate maxiter=1 call) can't be interpolated.
        real = np.array([real[0], real[0]])
        imag = np.array([imag[0], imag[0]])
        n = 2

    num_samples = max(int(duration * sr), 2)
    src_index = np.linspace(0, n - 1, num_samples)
    orig_index = np.arange(n)
    left = np.interp(src_index, orig_index, real)
    right = np.interp(src_index, orig_index, imag)
    stereo = np.stack([left, right], axis=1)

    peak = np.max(np.abs(stereo))
    if peak > 0:
        stereo = stereo / peak * 0.9

    fade_samples = int(fade * sr)
    if 0 < fade_samples < num_samples // 2:
        window = np.ones(num_samples)
        window[:fade_samples] = np.linspace(0, 1, fade_samples)
        window[-fade_samples:] = np.linspace(1, 0, fade_samples)
        stereo *= window[:, None]

    return stereo.astype(np.float32)


def save_wav(path: str, samples: np.ndarray, sr: int = 44100) -> None:
    """Write a ``(num_samples, channels)`` float array to a WAV file."""
    import soundfile as sf

    sf.write(path, samples, sr)

"""Perturbation-theory deep zoom, past float64 precision limits.

Standard escape-time iteration (see ``mandel_audio.fractal``) loses
precision once the viewport half-width approaches float64's ~15-16
significant decimal digits (``scale`` beyond ``MAX_SAFE_SCALE``, about
45). Perturbation theory works around this:

1. Compute one **reference orbit** ``Z_n`` at arbitrary precision
   (via ``mpmath``) for a single point ``c_ref`` (typically the view
   center).
2. For every other pixel, track only the small **delta** ``dz_n``
   between its true orbit and the reference orbit:

   ``dz_{n+1} = 2*Z_n*dz_n + dz_n**2 + dc``

   where ``dc = c_pixel - c_ref``. Both ``dz_n`` and ``dc`` stay tiny
   (roughly the size of the viewport), so they're fully representable
   in float64 *even when the viewport itself is 1e-300 wide* — the
   precision problem only ever applied to the absolute coordinates,
   which perturbation avoids adding together in low precision.

This lets the expensive per-pixel loop run at ordinary float64 (and be
numba-jitted), with only the cheap, single reference orbit computed at
high precision.

**Known limitation:** this implementation does not do "glitch
correction" (rebasing pixels whose orbit diverges too far from the
reference). Deep, off-center zooms may show small visual artifacts.
Choosing a reference point that does not escape quickly (near the
zoom target, ideally inside or slow-escaping) minimizes this.
"""

from __future__ import annotations

import math

import mpmath
import numpy as np
from numba import njit, prange

from mandel_audio.fractal import MAX_SAFE_SCALE  # noqa: F401  (re-exported for callers)


def required_precision(scale: float, margin: int = 15) -> int:
    """Decimal digits of precision needed for a given log2 zoom ``scale``."""
    return int(scale * math.log10(2)) + margin


def reference_orbit(cx, cy, maxiter: int, dps: int) -> tuple[np.ndarray, np.ndarray, bool]:
    """Compute a high-precision reference orbit, downcast to float64.

    ``cx``/``cy`` may be Python floats, strings, or ``mpmath.mpf`` —
    strings are recommended once you need more digits than a float can
    hold. Returns ``(real, imag, escaped)`` like
    ``mandel_audio.audio.compute_orbit``.
    """
    with mpmath.workdps(dps):
        c = mpmath.mpc(mpmath.mpf(cx), mpmath.mpf(cy))
        z = mpmath.mpc(0, 0)
        real = np.empty(maxiter)
        imag = np.empty(maxiter)
        count = maxiter
        escaped = False
        for n in range(maxiter):
            zr = float(z.real)
            zi = float(z.imag)
            real[n] = zr
            imag[n] = zi
            if zr * zr + zi * zi > 4.0:
                escaped = True
                count = n + 1
                break
            z = z * z + c
    return real[:count], imag[:count], escaped


@njit(cache=True, parallel=True)
def _perturbation_grid(
    ref_real: np.ndarray,
    ref_imag: np.ndarray,
    dcr: np.ndarray,
    dci: np.ndarray,
) -> np.ndarray:
    width = len(dcr)
    height = len(dci)
    ref_len = len(ref_real)
    out = np.empty((width, height))
    for i in prange(width):
        dc_r = dcr[i]
        for j in range(height):
            dc_i = dci[j]
            dzr = 0.0
            dzi = 0.0
            result = -1.0
            for n in range(ref_len):
                Zr = ref_real[n]
                Zi = ref_imag[n]
                zr = Zr + dzr
                zi = Zi + dzi
                mag2 = zr * zr + zi * zi
                if mag2 > 4.0:
                    log_zn = math.log(mag2) / 2.0
                    nu = math.log(log_zn / math.log(2.0)) / math.log(2.0)
                    result = n + 1 - nu
                    break
                new_dzr = 2.0 * (Zr * dzr - Zi * dzi) + (dzr * dzr - dzi * dzi) + dc_r
                new_dzi = 2.0 * (Zr * dzi + Zi * dzr) + (2.0 * dzr * dzi) + dc_i
                dzr, dzi = new_dzr, new_dzi
            out[i, j] = result
    return out


def deepzoom_set(
    cx,
    cy,
    unscaled_width: float = 2.5,
    N: int = 1000,
    maxiter: int = 2000,
    scale: float = 0.0,
    dps: int | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Perturbation-based analogue of ``mandel_audio.fractal.mandelbrot_set``.

    ``cx``/``cy`` should be strings (or ``mpmath.mpf``) once ``scale``
    exceeds ``MAX_SAFE_SCALE`` — a Python float only carries ~15-17
    significant digits itself, which defeats the point.

    Returns ``(dcr, dci, grid)``: ``dcr``/``dci`` are the pixel offsets
    *from the center* (not absolute coordinates, since those may not
    be representable in float64 at extreme zoom), and ``grid`` is the
    smoothed escape-time field, matching ``mandelbrot_set``'s
    convention of ``-1`` for points that don't escape.
    """
    if dps is None:
        dps = required_precision(scale)

    ref_real, ref_imag, escaped = reference_orbit(cx, cy, maxiter, dps)
    if escaped and len(ref_real) < maxiter // 4:
        import warnings

        warnings.warn(
            f"reference point escaped after only {len(ref_real)} iterations; "
            "pick a reference nearer the set (or inside it) for a cleaner "
            "deep zoom.",
            stacklevel=2,
        )

    half_width = unscaled_width * (2.0**-scale) / 2.0
    dcr = np.linspace(-half_width, half_width, N)
    dci = np.linspace(-half_width, half_width, N)
    grid = _perturbation_grid(ref_real, ref_imag, dcr, dci)
    return dcr, dci, grid

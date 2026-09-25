"""Core Mandelbrot-set computation.

The escape-time algorithm below is numba-jitted and parallelized across rows,
so a 1000x1000 / maxiter=1000 frame renders in well under a second on a
handful of cores.

Points that never escape (i.e. are inside the set) are reported as ``-1.0``
so callers can tell them apart from points that escape almost immediately,
which used to both come back as ``0`` in the original implementation.
Points that do escape get a *smooth* iteration count (a fractional value)
instead of an integer one, which removes the banding you get from coloring
by raw iteration count.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
from numba import njit, prange

# 64-bit floats keep roughly 15-16 significant decimal digits. Once the
# half-width of the viewport (``L`` below) gets close to the smallest
# representable gap near the center coordinate, neighboring pixels start
# mapping to the same float and the image degrades into blocks. This caps
# ``scale`` comfortably below that point.
MAX_SAFE_SCALE = 45


@njit(cache=True)
def mandelbrot(creal: float, cimag: float, maxiter: int) -> float:
    """Escape time for a single point ``c = creal + cimag*i``.

    Returns ``-1.0`` if the point appears to be in the Mandelbrot set
    (i.e. did not escape within ``maxiter`` iterations), otherwise a
    smoothed escape count (see module docstring).
    """
    real = creal
    imag = cimag
    for n in range(maxiter):
        real2 = real * real
        imag2 = imag * imag
        if real2 + imag2 > 4.0:
            # Smooth/continuous coloring, see:
            # https://linas.org/art-gallery/escape/escape.html
            log_zn = math.log(real2 + imag2) / 2.0
            nu = math.log(log_zn / math.log(2.0)) / math.log(2.0)
            return n + 1 - nu
        imag = 2 * real * imag + cimag
        real = real2 - imag2 + creal
    return -1.0


@njit(cache=True, parallel=True)
def mandelbrot_set_grid(
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
    width: int,
    height: int,
    maxiter: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Evaluate the escape time on a ``width`` x ``height`` grid."""
    r1 = np.linspace(xmin, xmax, width)
    r2 = np.linspace(ymin, ymax, height)
    n3 = np.empty((width, height))
    for i in prange(width):
        for j in range(height):
            n3[i, j] = mandelbrot(r1[i], r2[j], maxiter)
    return r1, r2, n3


def mandelbrot_set(
    x: float,
    y: float,
    unscaled_width: float = 2.5,
    N: int = 1000,
    maxiter: int = 100,
    scale: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Evaluate an ``N`` x ``N`` grid centered on ``(x, y)``.

    ``scale`` is a log2 zoom factor: each +1 halves the viewport width.
    """
    if scale > MAX_SAFE_SCALE:
        warnings.warn(
            f"scale={scale} exceeds float64 precision limits "
            f"(~{MAX_SAFE_SCALE}); the image will degrade into blocks. "
            "Use perturbation-based deep zoom for higher scales.",
            stacklevel=2,
        )

    half_width = unscaled_width * (2.0**-scale) / 2.0
    return mandelbrot_set_grid(
        x - half_width, x + half_width, y - half_width, y + half_width, N, N, maxiter
    )

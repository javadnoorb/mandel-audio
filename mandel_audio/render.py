"""Matplotlib-based rendering of Mandelbrot escape-time grids."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import colors
from matplotlib.figure import Figure

from mandel_audio.fractal import mandelbrot_set


def render_grid_image(
    z: np.ndarray,
    width: float = 7,
    height: float = 7,
    cmap: str = "hot",
    dpi: int = 72,
) -> Figure:
    """Render an escape-time grid ``z`` (as returned by ``mandelbrot_set``
    or ``deepzoom_set``) to a matplotlib Figure.

    Points inside the set (escape time of ``-1``) are drawn in black,
    regardless of ``cmap``.
    """
    inside = z < 0
    z_display = np.where(inside, np.nan, z)

    fig, ax = plt.subplots(figsize=(width, height), dpi=dpi)
    ax.set_facecolor("black")
    ax.axis("off")
    norm = colors.PowerNorm(0.3, vmin=0, vmax=np.nanmax(z_display) or 1)
    cmap_obj = plt.get_cmap(cmap).with_extremes(bad="black")
    ax.imshow(z_display.T, cmap=cmap_obj, origin="lower", norm=norm)
    return fig


def mandelbrot_image(
    x: float,
    y: float,
    width: float = 7,
    height: float = 7,
    unscaled_width: float = 2.5,
    N: int = 1000,
    maxiter: int = 100,
    scale: float = 0.0,
    cmap: str = "hot",
    dpi: int = 72,
) -> Figure:
    """Render a Mandelbrot view centered on ``(x, y)`` and return the Figure.

    Points inside the set (escape time of ``-1``) are drawn in black,
    regardless of ``cmap``.
    """
    _, _, z = mandelbrot_set(
        x, y, unscaled_width=unscaled_width, N=N, maxiter=maxiter, scale=scale
    )
    return render_grid_image(z, width=width, height=height, cmap=cmap, dpi=dpi)

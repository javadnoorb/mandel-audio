"""mandel-audio: explore the Mandelbrot set, visually and (soon) sonically."""

from mandel_audio.fractal import mandelbrot, mandelbrot_set, mandelbrot_set_grid
from mandel_audio.render import mandelbrot_image

__all__ = [
    "mandelbrot",
    "mandelbrot_set",
    "mandelbrot_set_grid",
    "mandelbrot_image",
]

__version__ = "0.2.0"

"""mandel-audio: explore the Mandelbrot set, visually and (soon) sonically."""

from mandel_audio.audio import compute_orbit, orbit_to_audio, save_wav
from mandel_audio.audio_analysis import AudioFeatures, analyze, analyze_file, load_audio
from mandel_audio.deepzoom import deepzoom_set
from mandel_audio.fractal import mandelbrot, mandelbrot_set, mandelbrot_set_grid
from mandel_audio.reactive import render_reactive_video
from mandel_audio.render import mandelbrot_image
from mandel_audio.video import render_zoom_video

__all__ = [
    "mandelbrot",
    "mandelbrot_set",
    "mandelbrot_set_grid",
    "mandelbrot_image",
    "compute_orbit",
    "orbit_to_audio",
    "save_wav",
    "deepzoom_set",
    "render_zoom_video",
    "AudioFeatures",
    "analyze",
    "analyze_file",
    "load_audio",
    "render_reactive_video",
]

__version__ = "0.2.0"

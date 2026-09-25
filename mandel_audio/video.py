"""Render a zoom-in video, with an orbit-sonification soundtrack.

Uses ``mandel_audio.fractal.mandelbrot_set`` for frames within float64
precision (``scale <= MAX_SAFE_SCALE``) and transparently switches to
``mandel_audio.deepzoom.deepzoom_set`` for deeper frames, so a single
call can zoom from the full view down past float64's limits.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from matplotlib import colormaps

from mandel_audio.audio import orbit_to_audio, save_wav
from mandel_audio.deepzoom import deepzoom_set
from mandel_audio.fractal import MAX_SAFE_SCALE, mandelbrot_set


def grid_to_rgb(z: np.ndarray, cmap: str = "gnuplot2", gamma: float = 0.3) -> np.ndarray:
    """Colorize an escape-time grid into a top-down uint8 RGB image.

    Matches the coloring convention of ``mandel_audio.render.mandelbrot_image``
    (PowerNorm(gamma) over escaped points, black for points inside the
    set), but returns a plain array instead of a matplotlib Figure —
    much cheaper per-frame for video rendering.
    """
    zt = z.T  # (height, width), row 0 = ymin
    inside = zt < 0
    escaped_vals = np.where(inside, 0.0, zt)
    vmax = escaped_vals.max()
    if vmax <= 0:
        vmax = 1.0
    norm = np.clip(escaped_vals / vmax, 0.0, 1.0) ** gamma

    cmap_obj = colormaps[cmap]
    rgb = (cmap_obj(norm)[..., :3] * 255).astype(np.uint8)
    rgb[inside] = 0

    # flip so row 0 = top = ymax, standard image/video convention
    return np.flipud(rgb)


def render_frame(
    x, y, scale: float, N: int = 400, maxiter: int = 500, cmap: str = "gnuplot2"
) -> np.ndarray:
    """Render a single frame at the given center/scale as an RGB array."""
    if scale <= MAX_SAFE_SCALE:
        _, _, z = mandelbrot_set(float(x), float(y), N=N, maxiter=maxiter, scale=scale)
    else:
        _, _, z = deepzoom_set(x, y, N=N, maxiter=maxiter, scale=scale)
    return grid_to_rgb(z, cmap=cmap)


def render_zoom_video(
    x,
    y,
    output_path: str,
    start_scale: float = 0.0,
    end_scale: float = 20.0,
    num_frames: int = 60,
    fps: int = 24,
    N: int = 400,
    maxiter: int = 500,
    cmap: str = "gnuplot2",
    with_audio: bool = True,
    sr: int = 44100,
) -> str:
    """Render a zoom-in video from ``start_scale`` to ``end_scale``.

    ``x``/``y`` should be strings (or ``mpmath.mpf``) if ``end_scale``
    exceeds ``MAX_SAFE_SCALE``. If ``with_audio``, the soundtrack is
    the target point's orbit sonification (see
    ``mandel_audio.audio.orbit_to_audio``), stretched to the video's
    duration and muxed in with ffmpeg.

    Returns ``output_path``.
    """
    scales = np.linspace(start_scale, end_scale, num_frames)

    with tempfile.TemporaryDirectory() as tmp:
        video_only = str(Path(tmp) / "video_only.mp4")
        writer = imageio.get_writer(
            video_only, fps=fps, codec="libx264", quality=8, macro_block_size=None
        )
        try:
            for s in scales:
                frame = render_frame(x, y, float(s), N=N, maxiter=maxiter, cmap=cmap)
                writer.append_data(frame)
        finally:
            writer.close()

        if not with_audio:
            shutil.move(video_only, output_path)
            return output_path

        duration = num_frames / fps
        audio = orbit_to_audio(float(x), float(y), duration=duration, sr=sr, maxiter=2000)
        audio_path = str(Path(tmp) / "audio.wav")
        save_wav(audio_path, audio, sr=sr)

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg_exe,
            "-y",
            "-i", video_only,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg mux failed:\n{result.stderr}")

    return output_path

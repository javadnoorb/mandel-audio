"""Render a fractal zoom video that reacts to music.

Ties ``mandel_audio.audio_analysis`` (music -> per-frame bass/mid/
treble/loudness/beat) to the fractal renderer: color is a blend of
three palettes weighted by the band energies (so a bass-heavy passage
skews warm, a treble-heavy one skews cool, etc.), overall brightness
tracks loudness, and detected beats punch a brief extra zoom-in.

If no audio file is given, a procedural soundtrack is generated (via
``mandel_audio.audio.orbit_to_audio``, sonifying the target point's own
orbit) and then analyzed the same way real music would be -- so the
same reactive pipeline drives the visuals either way.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from matplotlib import colormaps

from mandel_audio.audio import orbit_to_audio, save_wav
from mandel_audio.audio_analysis import AudioFeatures, analyze, analyze_file
from mandel_audio.fractal import MAX_SAFE_SCALE, mandelbrot_set

# Band -> palette. Each is sampled the same way matplotlib samples a
# colormap (input in [0, 1]) and blended by that band's energy weight.
BAND_CMAPS = {"bass": "inferno", "mid": "viridis", "treble": "cool"}

# YouTube's recommended H.264 video bitrate (kbps) by frame height, for
# standard (<=30fps) SDR uploads:
# https://support.google.com/youtube/answer/1722171
YOUTUBE_VIDEO_BITRATE_KBPS = {
    360: 1000,
    480: 2500,
    720: 5000,
    1080: 8000,
    1440: 16000,
    2160: 40000,
}
YOUTUBE_AUDIO_BITRATE_KBPS = 384
YOUTUBE_AUDIO_SAMPLE_RATE = 48000


def youtube_video_bitrate(height: int) -> int:
    """Recommended H.264 video bitrate in kbps for a frame of this height.

    Falls back to the nearest tier at or below ``height`` (or the
    lowest tier, for anything smaller than 360p).
    """
    tiers = sorted(YOUTUBE_VIDEO_BITRATE_KBPS)
    chosen = tiers[0]
    for tier in tiers:
        if height >= tier:
            chosen = tier
    return YOUTUBE_VIDEO_BITRATE_KBPS[chosen]


def zoom_schedule(
    features: AudioFeatures,
    start_scale: float = 0.0,
    end_scale: float = 15.0,
    beat_punch: float = 0.6,
) -> np.ndarray:
    """Per-frame log2 zoom: a smooth ramp plus short punches on beats."""
    n = features.num_frames
    base = np.linspace(start_scale, end_scale, n)
    # A beat punch decays into the ramp rather than stacking
    # indefinitely, so the zoom keeps moving forward on-beat without
    # runaway jumps.
    return base + beat_punch * features.beat


def maxiter_schedule(scales: np.ndarray, max_maxiter: int, min_maxiter: int = 100) -> np.ndarray:
    """Per-frame max-iteration count, ramping with zoom depth.

    Iteration count is the single largest lever on render time (linear
    in ``maxiter``), but wide/shallow-zoom frames resolve correctly
    with far fewer iterations than deep zoom needs to render fine
    boundary detail -- using a fixed high ``maxiter`` for every frame
    spends most of that budget on frames that don't need it. This
    scales linearly from ``min_maxiter`` at ``scale=0`` up to
    ``max_maxiter`` at the deepest scale actually reached (so a video
    with a shallow ``end_scale`` doesn't unnecessarily hit the ceiling
    early).
    """
    min_maxiter = min(min_maxiter, max_maxiter)
    peak = max(float(scales.max()), 1e-9)
    fraction = np.clip(scales, 0, None) / peak
    values = min_maxiter + fraction * (max_maxiter - min_maxiter)
    return np.maximum(min_maxiter, values.astype(np.int64))


def blend_frame_color(
    z: np.ndarray,
    bass: float,
    mid: float,
    treble: float,
    loudness: float,
    gamma: float = 0.3,
) -> np.ndarray:
    """Colorize one escape-time grid, blending band palettes by weight.

    ``z`` uses the ``-1`` = inside-the-set convention. Returns a
    top-down uint8 RGB image.
    """
    zt = z.T
    inside = zt < 0
    escaped_vals = np.where(inside, 0.0, zt)
    vmax = escaped_vals.max()
    if vmax <= 0:
        vmax = 1.0
    t = np.clip(escaped_vals / vmax, 0.0, 1.0) ** gamma

    weights = np.array([bass, mid, treble], dtype=float)
    total = weights.sum()
    weights = weights / total if total > 0 else np.array([1 / 3, 1 / 3, 1 / 3])

    rgb = np.zeros((*t.shape, 3), dtype=float)
    for band, w in zip(("bass", "mid", "treble"), weights, strict=True):
        cmap_obj = colormaps[BAND_CMAPS[band]]
        rgb += w * cmap_obj(t)[..., :3]

    # Loudness modulates overall brightness (never fully to black, so
    # quiet passages dim rather than vanish).
    brightness = 0.4 + 0.6 * loudness
    rgb *= brightness

    rgb_u8 = np.clip(rgb * 255, 0, 255).astype(np.uint8)
    rgb_u8[inside] = 0
    return np.flipud(rgb_u8)


def render_frame(x, y, scale: float, N: int = 400, maxiter: int = 500) -> np.ndarray:
    """Render one escape-time grid at float64 precision.

    ``scale`` beyond ``mandel_audio.fractal.MAX_SAFE_SCALE`` (~45) will
    degrade into blocks -- there is no deep-zoom fallback here; that's
    a separate follow-up (perturbation-based rendering past float64
    limits).
    """
    _, _, z = mandelbrot_set(float(x), float(y), N=N, maxiter=maxiter, scale=scale)
    return z


def render_reactive_video(
    x,
    y,
    output_path: str,
    audio_path: str | None = None,
    start_scale: float = 0.0,
    end_scale: float = 15.0,
    beat_punch: float = 0.6,
    fps: int = 24,
    N: int = 400,
    maxiter: int = 500,
    min_maxiter: int = 100,
    max_duration: float | None = None,
    sr: int = 44100,
    youtube: bool = False,
) -> str:
    """Render a music-reactive zoom video.

    If ``audio_path`` is given, that track supplies both the analysis
    driving the visuals and the video's soundtrack. Otherwise a
    soundtrack is generated from the target point's own orbit
    (``mandel_audio.audio.orbit_to_audio``) and analyzed the same way.

    ``maxiter`` is the iteration count at the *deepest* frame reached;
    earlier, shallower frames use progressively fewer iterations down
    to ``min_maxiter`` (see ``maxiter_schedule``), since they don't
    need the full count to render correctly. Pass ``min_maxiter =
    maxiter`` to disable this and use a fixed count for every frame.

    ``end_scale`` beyond ``mandel_audio.fractal.MAX_SAFE_SCALE`` (~45)
    is not supported here (see ``render_frame``); a deep-zoom renderer
    is a separate follow-up.

    ``youtube``: re-encode the final mux at YouTube's recommended
    bitrate for the render's resolution (``youtube_video_bitrate``),
    384 kbps AAC audio at 48 kHz, and a closed GOP every 2 seconds --
    instead of the default, which copies the (much higher-bitrate,
    larger-than-necessary for delivery) intermediate video stream
    through untouched and muxes audio at ffmpeg's default AAC bitrate.
    """
    if end_scale > MAX_SAFE_SCALE:
        import warnings

        warnings.warn(
            f"end_scale={end_scale} exceeds float64 precision limits "
            f"(~{MAX_SAFE_SCALE}); late frames will degrade into blocks.",
            stacklevel=2,
        )

    with tempfile.TemporaryDirectory() as tmp:
        if audio_path is not None:
            features = analyze_file(audio_path, fps=fps, sr=sr)
            track_path = audio_path
        else:
            # Generative fallback: sonify the target orbit, then feed
            # that signal through the same analysis pipeline used for
            # real music.
            gen_duration = max_duration or 8.0
            audio = orbit_to_audio(float(x), float(y), duration=gen_duration, sr=sr, maxiter=2000)
            track_path = str(Path(tmp) / "generated.wav")
            save_wav(track_path, audio, sr=sr)
            mono = audio.mean(axis=1)
            features = analyze(mono, sr, fps=fps)

        if max_duration is not None:
            max_frames = int(max_duration * fps)
            if max_frames < features.num_frames:
                features = AudioFeatures(
                    bass=features.bass[:max_frames],
                    mid=features.mid[:max_frames],
                    treble=features.treble[:max_frames],
                    loudness=features.loudness[:max_frames],
                    beat=features.beat[:max_frames],
                    tempo=features.tempo,
                    fps=features.fps,
                    sr=features.sr,
                    duration=max_frames / fps,
                )

        scales = zoom_schedule(features, start_scale, end_scale, beat_punch)
        maxiters = maxiter_schedule(scales, max_maxiter=maxiter, min_maxiter=min_maxiter)

        video_only = str(Path(tmp) / "video_only.mp4")
        writer = imageio.get_writer(
            video_only, fps=fps, codec="libx264", quality=8, macro_block_size=None
        )
        try:
            for i in range(features.num_frames):
                z = render_frame(x, y, float(scales[i]), N=N, maxiter=int(maxiters[i]))
                frame = blend_frame_color(
                    z,
                    float(features.bass[i]),
                    float(features.mid[i]),
                    float(features.treble[i]),
                    float(features.loudness[i]),
                )
                writer.append_data(frame)
        finally:
            writer.close()

        # Trim the audio track to the (possibly max_duration-capped)
        # video length, then mux.
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        video_duration = features.num_frames / fps
        cmd = [ffmpeg_exe, "-y", "-i", video_only, "-i", track_path, "-t", str(video_duration)]

        if youtube:
            bitrate = youtube_video_bitrate(N)
            gop = fps * 2  # closed GOP every 2s, per YouTube's guidance
            cmd += [
                "-c:v", "libx264",
                "-b:v", f"{bitrate}k",
                "-maxrate", f"{int(bitrate * 1.15)}k",
                "-bufsize", f"{bitrate * 2}k",
                "-pix_fmt", "yuv420p",
                "-g", str(gop),
                "-keyint_min", str(gop),
                "-sc_threshold", "0",
                "-c:a", "aac",
                "-b:a", f"{YOUTUBE_AUDIO_BITRATE_KBPS}k",
                "-ar", str(YOUTUBE_AUDIO_SAMPLE_RATE),
            ]
        else:
            cmd += ["-c:v", "copy", "-c:a", "aac"]

        cmd += ["-shortest", output_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg mux failed:\n{result.stderr}")

    return output_path

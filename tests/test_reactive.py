import re
import subprocess

import imageio_ffmpeg
import numpy as np
import pytest

from mandel_audio.audio_analysis import AudioFeatures
from mandel_audio.fractal import mandelbrot_set_grid
from mandel_audio.reactive import (
    YOUTUBE_AUDIO_BITRATE_KBPS,
    YOUTUBE_AUDIO_SAMPLE_RATE,
    blend_frame_color,
    maxiter_schedule,
    render_reactive_video,
    youtube_video_bitrate,
    zoom_schedule,
)


def _features(n=10, beat_at=None):
    beat = np.zeros(n)
    if beat_at is not None:
        beat[beat_at] = 1.0
    return AudioFeatures(
        bass=np.linspace(0, 1, n),
        mid=np.full(n, 0.5),
        treble=np.linspace(1, 0, n),
        loudness=np.full(n, 0.8),
        beat=beat,
        tempo=120.0,
        fps=10,
        sr=22050,
        duration=1.0,
    )


def test_zoom_schedule_is_monotonic_without_beats():
    feats = _features()
    scales = zoom_schedule(feats, start_scale=0.0, end_scale=10.0, beat_punch=0.0)
    assert scales[0] == pytest.approx(0.0)
    assert scales[-1] == pytest.approx(10.0)
    assert np.all(np.diff(scales) >= 0)


def test_zoom_schedule_beat_adds_a_punch():
    feats = _features(beat_at=5)
    no_beat = zoom_schedule(feats, 0.0, 10.0, beat_punch=0.0)
    with_beat = zoom_schedule(feats, 0.0, 10.0, beat_punch=2.0)
    assert with_beat[5] > no_beat[5]
    # frames without a beat pulse are unaffected
    assert with_beat[0] == pytest.approx(no_beat[0])


def test_maxiter_schedule_ramps_from_min_to_max():
    scales = np.linspace(0, 10, 11)
    schedule = maxiter_schedule(scales, max_maxiter=1000, min_maxiter=100)
    assert schedule[0] == 100
    assert schedule[-1] == 1000
    assert np.all(np.diff(schedule) >= 0)


def test_maxiter_schedule_uses_peak_scale_not_a_fixed_end_scale():
    # A video whose zoom never gets very deep shouldn't have its early
    # frames pay for iterations only needed at scale=45.
    shallow_scales = np.linspace(0, 3, 11)
    schedule = maxiter_schedule(shallow_scales, max_maxiter=1000, min_maxiter=100)
    assert schedule[-1] == 1000  # still reaches the ceiling at its own peak
    assert schedule[0] == 100


def test_maxiter_schedule_handles_constant_scale():
    # No divide-by-zero when every frame is at the same (e.g. zero) scale.
    scales = np.zeros(5)
    schedule = maxiter_schedule(scales, max_maxiter=500, min_maxiter=100)
    assert np.all(np.isfinite(schedule))
    assert np.all(schedule >= 100)


def test_maxiter_schedule_min_greater_than_max_is_clamped():
    scales = np.linspace(0, 5, 6)
    schedule = maxiter_schedule(scales, max_maxiter=200, min_maxiter=800)
    assert np.all(schedule <= 200)


def test_blend_frame_color_inside_is_black():
    z = np.full((8, 8), -1.0)
    rgb = blend_frame_color(z, bass=1.0, mid=0.0, treble=0.0, loudness=1.0)
    assert np.all(rgb == 0)


def test_blend_frame_color_shape_and_dtype():
    _, _, z = mandelbrot_set_grid(-2.0, 0.5, -1.25, 1.25, 20, 16, 100)
    rgb = blend_frame_color(z, bass=0.3, mid=0.3, treble=0.4, loudness=0.9)
    assert rgb.shape == (16, 20, 3)
    assert rgb.dtype == np.uint8


def test_blend_frame_color_loudness_dims_brightness():
    _, _, z = mandelbrot_set_grid(-2.0, 0.5, -1.25, 1.25, 20, 16, 200)
    bright = blend_frame_color(z, bass=0.5, mid=0.5, treble=0.0, loudness=1.0).astype(int)
    dim = blend_frame_color(z, bass=0.5, mid=0.5, treble=0.0, loudness=0.0).astype(int)
    assert bright.sum() >= dim.sum()


def test_render_reactive_video_generative_fallback_smoke(tmp_path):
    out = tmp_path / "reactive.mp4"
    result = render_reactive_video(
        -0.5,
        0.0,
        str(out),
        audio_path=None,
        start_scale=0.0,
        end_scale=2.0,
        fps=4,
        N=24,
        maxiter=80,
        max_duration=1.0,
    )
    assert result == str(out)
    assert out.exists()
    assert out.stat().st_size > 0


@pytest.mark.parametrize(
    ("height", "expected_kbps"),
    [
        (360, 1000),
        (480, 2500),
        (720, 5000),
        (1080, 8000),
        (1440, 16000),
        (2160, 40000),
        (1000, 5000),  # between tiers -> falls back to the tier below (720p's)
        (100, 1000),  # smaller than the lowest tier -> still returns the lowest tier
    ],
)
def test_youtube_video_bitrate_table(height, expected_kbps):
    assert youtube_video_bitrate(height) == expected_kbps


def _probe_streams(path):
    # imageio_ffmpeg bundles ffmpeg but not ffprobe; ffmpeg -i with no
    # output prints the same stream info to stderr before erroring, so
    # that's what we parse instead of shelling out to a separate tool.
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run([ffmpeg, "-i", path], capture_output=True, text=True)
    text = result.stderr

    video_bitrate = None
    video_match = re.search(r"Video:.*?(\d+) kb/s", text)
    if video_match:
        video_bitrate = int(video_match.group(1)) * 1000

    audio_match = re.search(r"Audio:\s*(\w+).*?(\d+) Hz.*?(\d+) kb/s", text)
    audio_codec = audio_match.group(1) if audio_match else None
    audio_sample_rate = int(audio_match.group(2)) if audio_match else None
    audio_bitrate = int(audio_match.group(3)) * 1000 if audio_match else None

    video_codec_match = re.search(r"Video:\s*(\w+)", text)
    video_codec = video_codec_match.group(1) if video_codec_match else None

    return {
        "video_codec": video_codec,
        "video_bitrate": video_bitrate,
        "audio_codec": audio_codec,
        "audio_sample_rate": audio_sample_rate,
        "audio_bitrate": audio_bitrate,
    }


def test_render_reactive_video_youtube_preset(tmp_path):
    out = tmp_path / "youtube.mp4"
    N = 360  # smallest YouTube tier, to keep this test fast
    render_reactive_video(
        -0.5,
        0.0,
        str(out),
        audio_path=None,
        start_scale=0.0,
        end_scale=2.0,
        fps=4,
        N=N,
        maxiter=80,
        max_duration=1.0,
        youtube=True,
    )
    assert out.exists()

    info = _probe_streams(str(out))
    assert info["video_codec"] == "h264"
    # actual encoded bitrate varies a bit around the -b:v target; a 40%
    # band is generous enough to not be flaky while still catching a
    # completely wrong bitrate (e.g. the untouched high-bitrate default).
    target = youtube_video_bitrate(N) * 1000
    assert info["video_bitrate"] is not None
    assert info["video_bitrate"] < target * 1.4

    assert info["audio_codec"] == "aac"
    assert info["audio_sample_rate"] == YOUTUBE_AUDIO_SAMPLE_RATE
    assert info["audio_bitrate"] < YOUTUBE_AUDIO_BITRATE_KBPS * 1000 * 1.2

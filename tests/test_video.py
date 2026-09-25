import numpy as np
import pytest

from mandel_audio.fractal import mandelbrot_set_grid
from mandel_audio.video import grid_to_rgb, render_frame, render_zoom_video


def test_grid_to_rgb_shape_and_dtype():
    _, _, z = mandelbrot_set_grid(-2.0, 0.5, -1.25, 1.25, 40, 30, 100)
    rgb = grid_to_rgb(z)
    assert rgb.shape == (30, 40, 3)  # (height, width, channels)
    assert rgb.dtype == np.uint8


def test_grid_to_rgb_inside_is_black():
    z = np.full((10, 10), -1.0)
    rgb = grid_to_rgb(z)
    assert np.all(rgb == 0)


def test_render_frame_shallow_and_deep_paths_agree_in_shape():
    frame_shallow = render_frame(-0.5, 0.0, scale=5.0, N=20, maxiter=100)
    frame_deep = render_frame("-0.5", "0.0", scale=50.0, N=20, maxiter=100)
    assert frame_shallow.shape == frame_deep.shape == (20, 20, 3)


@pytest.mark.parametrize("with_audio", [False, True])
def test_render_zoom_video_smoke(tmp_path, with_audio):
    out = tmp_path / "zoom.mp4"
    result = render_zoom_video(
        -0.5,
        0.0,
        str(out),
        start_scale=0.0,
        end_scale=2.0,
        num_frames=4,
        fps=4,
        N=24,
        maxiter=80,
        with_audio=with_audio,
    )
    assert result == str(out)
    assert out.exists()
    assert out.stat().st_size > 0

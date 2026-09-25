import numpy as np
import pytest

from mandel_audio.fractal import MAX_SAFE_SCALE, mandelbrot, mandelbrot_set, mandelbrot_set_grid


def test_origin_is_inside_the_set():
    # c = 0 never escapes.
    assert mandelbrot(0.0, 0.0, 1000) == -1.0


def test_far_point_escapes_immediately():
    # |c| = |2+2i| is already outside |z|>2 on the first check, so the
    # smoothed escape count should be small and positive.
    result = mandelbrot(2.0, 2.0, 1000)
    assert result >= 0
    assert result < 2


def test_known_bulb_member_is_inside():
    # Center of the period-2 bulb.
    assert mandelbrot(-1.0, 0.0, 1000) == -1.0


def test_grid_shape():
    r1, r2, grid = mandelbrot_set_grid(-2.0, 0.5, -1.25, 1.25, 50, 40, 100)
    assert r1.shape == (50,)
    assert r2.shape == (40,)
    assert grid.shape == (50, 40)


def test_grid_is_deterministic():
    args = (-2.0, 0.5, -1.25, 1.25, 30, 30, 100)
    g1 = mandelbrot_set_grid(*args)[2]
    g2 = mandelbrot_set_grid(*args)[2]
    np.testing.assert_array_equal(g1, g2)


def test_mandelbrot_set_centers_on_xy():
    x, y = mandelbrot_set(-0.5, 0.0, N=10, maxiter=50)[:2]
    assert x.min() < -0.5 < x.max()
    assert y.min() < 0.0 < y.max()


def test_mandelbrot_set_warns_above_safe_scale():
    with pytest.warns(UserWarning, match="precision"):
        mandelbrot_set(-0.5, 0.0, N=5, maxiter=10, scale=MAX_SAFE_SCALE + 1)

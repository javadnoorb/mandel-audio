import math

import numpy as np
import pytest

from mandel_audio.fractal import MAX_SAFE_SCALE, mandelbrot, mandelbrot_set, mandelbrot_set_grid


def _naive_grid(xmin, xmax, ymin, ymax, width, height, maxiter):
    """A plain, non-parallel, non-scattered reference implementation."""
    r1 = np.linspace(xmin, xmax, width)
    r2 = np.linspace(ymin, ymax, height)
    n3 = np.empty((width, height))
    for i in range(width):
        for j in range(height):
            real = r1[i]
            imag = r2[j]
            n3[i, j] = -1.0
            for n in range(maxiter):
                real2 = real * real
                imag2 = imag * imag
                if real2 + imag2 > 4.0:
                    log_zn = math.log(real2 + imag2) / 2.0
                    nu = math.log(log_zn / math.log(2.0)) / math.log(2.0)
                    n3[i, j] = n + 1 - nu
                    break
                imag = 2 * real * imag + r2[j]
                real = real2 - imag2 + r1[i]
    return n3


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


def test_grid_matches_naive_reference():
    # mandelbrot_set_grid visits pixels in a scattered order internally
    # (for parallel load balancing, see fractal._scatter_order) -- this
    # checks the *values* still land in the right (i, j) slots by
    # comparing against a plain sequential reference implementation.
    #
    # Uses a tolerance, not exact equality: numba/LLVM-compiled and
    # plain-interpreted Python arithmetic can differ at the ULP level
    # (e.g. from FMA instruction use) even for identical code computing
    # identical values in identical order -- confirmed by comparing
    # this same naive reference against an *unscattered* run of the
    # numba kernel, which shows the same ~1e-11 divergence. That's a
    # property of compiled vs. interpreted float math, not something
    # introduced by the scattered visitation order.
    args = (-2.0, 0.5, -1.25, 1.25, 25, 20, 80)
    expected = _naive_grid(*args)
    actual = mandelbrot_set_grid(*args)[2]
    np.testing.assert_allclose(actual, expected, rtol=1e-9, atol=1e-9)


def test_scatter_order_is_a_valid_permutation():
    from mandel_audio.fractal import _scatter_order

    width, height = 17, 23  # deliberately not a round number
    order = _scatter_order(width, height)
    assert order.shape == (width * height,)
    np.testing.assert_array_equal(np.sort(order), np.arange(width * height))


def test_scatter_order_is_cached_and_deterministic():
    from mandel_audio.fractal import _scatter_order

    a = _scatter_order(30, 30)
    b = _scatter_order(30, 30)
    assert a is b  # same object: lru_cache hit, not just equal values

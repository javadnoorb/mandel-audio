import numpy as np
import pytest

from mandel_audio.deepzoom import deepzoom_set, reference_orbit, required_precision
from mandel_audio.fractal import mandelbrot, mandelbrot_set_grid


def test_required_precision_grows_with_scale():
    assert required_precision(0) < required_precision(100) < required_precision(1000)


def test_reference_orbit_matches_double_precision_mandelbrot():
    # At ordinary precision, the high-precision reference orbit should
    # agree with the plain float64 escape-time function.
    for cx, cy in [(-0.5, 0.0), (-1.0, 0.0), (2.0, 2.0), (-0.74529, 0.113075)]:
        real, imag, escaped = reference_orbit(cx, cy, maxiter=500, dps=30)
        expected = mandelbrot(cx, cy, 500)
        if expected < 0:
            assert not escaped
            assert len(real) == 500
        else:
            assert escaped
            # len(real) is the smoothed escape count rounded up
            assert abs(len(real) - math_ceil(expected)) <= 1


def math_ceil(x):
    import math

    return math.ceil(x)


def test_deepzoom_matches_standard_grid_at_shallow_zoom():
    # At scale=0 (no zoom), perturbation should reproduce the same
    # inside/outside classification as the direct float64 computation.
    x, y = -0.5, 0.0
    N, maxiter = 40, 200

    _, _, z_direct = mandelbrot_set_grid(x - 1.25, x + 1.25, y - 1.25, y + 1.25, N, N, maxiter)
    _, _, z_deep = deepzoom_set(x, y, N=N, maxiter=maxiter, scale=0.0, dps=30)

    inside_direct = z_direct < 0
    inside_deep = z_deep < 0
    # Allow a handful of boundary pixels to disagree due to different
    # floating-point round-off paths; the classification should mostly
    # match.
    mismatch_fraction = np.mean(inside_direct != inside_deep)
    assert mismatch_fraction < 0.02


def test_deepzoom_runs_at_extreme_scale():
    # Exercise the actual high-precision code path (can't be done in
    # float64). Using a simple rational center means the "extra" digits
    # are trailing zeros, but this still verifies the pipeline doesn't
    # break at deep scale.
    dcr, dci, grid = deepzoom_set("-0.5", "0.0", N=20, maxiter=300, scale=200)
    assert dcr.shape == (20,)
    assert dci.shape == (20,)
    assert grid.shape == (20, 20)
    assert np.all(np.isfinite(grid))


def test_deepzoom_warns_on_escaping_reference():
    with pytest.warns(UserWarning, match="reference point escaped"):
        deepzoom_set(2.0, 2.0, N=5, maxiter=100, scale=10)

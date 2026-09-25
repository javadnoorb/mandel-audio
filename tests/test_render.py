import matplotlib

matplotlib.use("Agg")

from matplotlib.figure import Figure

from mandel_audio.render import mandelbrot_image


def test_mandelbrot_image_returns_figure():
    fig = mandelbrot_image(-0.5, 0.0, N=20, maxiter=50)
    assert isinstance(fig, Figure)

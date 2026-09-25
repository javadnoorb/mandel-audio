"""Command-line entry point: render a Mandelbrot view to a PNG file."""

from __future__ import annotations

import argparse

from mandel_audio.render import mandelbrot_image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mandel-audio",
        description="Render a Mandelbrot set view to an image file.",
    )
    parser.add_argument("-x", type=float, default=-0.74529, help="center real part")
    parser.add_argument("-y", type=float, default=0.113075, help="center imaginary part")
    parser.add_argument(
        "--scale", type=float, default=0.0, help="log2 zoom factor (0 = full view)"
    )
    parser.add_argument("--maxiter", type=int, default=1000, help="max iterations")
    parser.add_argument("-N", type=int, default=1000, help="grid resolution (N x N)")
    parser.add_argument("--cmap", type=str, default="gnuplot2", help="matplotlib colormap")
    parser.add_argument(
        "-o", "--output", type=str, default="mandelbrot.png", help="output file path"
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    fig = mandelbrot_image(
        args.x,
        args.y,
        scale=args.scale,
        maxiter=args.maxiter,
        N=args.N,
        cmap=args.cmap,
    )
    fig.savefig(args.output, bbox_inches="tight", pad_inches=0)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

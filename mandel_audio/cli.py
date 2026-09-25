"""Command-line entry point.

Two subcommands:

* ``mandel-audio render`` — render a Mandelbrot view to a PNG.
* ``mandel-audio sonify`` — sonify a point's orbit to a WAV file.
"""

from __future__ import annotations

import argparse

from mandel_audio.audio import orbit_to_audio, save_wav
from mandel_audio.render import mandelbrot_image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mandel-audio",
        description="Explore the Mandelbrot set, visually and sonically.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    render_p = sub.add_parser("render", help="Render a Mandelbrot view to a PNG.")
    render_p.add_argument("-x", type=float, default=-0.74529, help="center real part")
    render_p.add_argument("-y", type=float, default=0.113075, help="center imaginary part")
    render_p.add_argument(
        "--scale", type=float, default=0.0, help="log2 zoom factor (0 = full view)"
    )
    render_p.add_argument("--maxiter", type=int, default=1000, help="max iterations")
    render_p.add_argument("-N", type=int, default=1000, help="grid resolution (N x N)")
    render_p.add_argument("--cmap", type=str, default="gnuplot2", help="matplotlib colormap")
    render_p.add_argument(
        "-o", "--output", type=str, default="mandelbrot.png", help="output file path"
    )

    sonify_p = sub.add_parser("sonify", help="Sonify a point's orbit to a WAV file.")
    sonify_p.add_argument("-x", type=float, default=-0.74529, help="orbit seed real part")
    sonify_p.add_argument("-y", type=float, default=0.113075, help="orbit seed imaginary part")
    sonify_p.add_argument("--duration", type=float, default=3.0, help="output duration, seconds")
    sonify_p.add_argument("--sr", type=int, default=44100, help="sample rate")
    sonify_p.add_argument("--maxiter", type=int, default=2000, help="max orbit iterations")
    sonify_p.add_argument(
        "-o", "--output", type=str, default="orbit.wav", help="output file path"
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    if args.command == "render":
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

    elif args.command == "sonify":
        audio = orbit_to_audio(
            args.x, args.y, duration=args.duration, sr=args.sr, maxiter=args.maxiter
        )
        save_wav(args.output, audio, sr=args.sr)
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

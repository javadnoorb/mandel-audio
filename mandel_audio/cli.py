"""Command-line entry point.

Subcommands:

* ``mandel-audio render`` — render a Mandelbrot view to a PNG.
* ``mandel-audio sonify`` — sonify a point's orbit to a WAV file.
* ``mandel-audio deepzoom`` — render a view past float64 zoom limits.
* ``mandel-audio video`` — render a zoom-in video with a soundtrack.
"""

from __future__ import annotations

import argparse

from mandel_audio.audio import orbit_to_audio, save_wav
from mandel_audio.deepzoom import deepzoom_set
from mandel_audio.fractal import MAX_SAFE_SCALE
from mandel_audio.render import mandelbrot_image, render_grid_image
from mandel_audio.video import render_zoom_video


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

    deepzoom_p = sub.add_parser(
        "deepzoom", help="Render a view past float64 zoom limits (perturbation theory)."
    )
    deepzoom_p.add_argument(
        "-x", type=str, required=True, help="center real part (string, for full precision)"
    )
    deepzoom_p.add_argument(
        "-y", type=str, required=True, help="center imaginary part (string, for full precision)"
    )
    deepzoom_p.add_argument("--scale", type=float, required=True, help="log2 zoom factor")
    deepzoom_p.add_argument("--maxiter", type=int, default=2000, help="max iterations")
    deepzoom_p.add_argument("-N", type=int, default=1000, help="grid resolution (N x N)")
    deepzoom_p.add_argument("--cmap", type=str, default="gnuplot2", help="matplotlib colormap")
    deepzoom_p.add_argument(
        "-o", "--output", type=str, default="deepzoom.png", help="output file path"
    )

    video_p = sub.add_parser("video", help="Render a zoom-in video with an orbit soundtrack.")
    video_p.add_argument("-x", type=str, default="-0.74529", help="center real part")
    video_p.add_argument("-y", type=str, default="0.113075", help="center imaginary part")
    video_p.add_argument("--start-scale", type=float, default=0.0, help="starting log2 zoom")
    video_p.add_argument("--end-scale", type=float, default=20.0, help="ending log2 zoom")
    video_p.add_argument("--frames", type=int, default=120, help="number of frames")
    video_p.add_argument("--fps", type=int, default=24, help="frames per second")
    video_p.add_argument("-N", type=int, default=400, help="grid resolution (N x N)")
    video_p.add_argument("--maxiter", type=int, default=500, help="max iterations per frame")
    video_p.add_argument("--cmap", type=str, default="gnuplot2", help="matplotlib colormap")
    video_p.add_argument("--no-audio", action="store_true", help="skip the audio soundtrack")
    video_p.add_argument(
        "-o", "--output", type=str, default="zoom.mp4", help="output file path"
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

    elif args.command == "deepzoom":
        if args.scale <= MAX_SAFE_SCALE:
            print(
                f"note: scale={args.scale} is within float64 precision "
                f"(<= {MAX_SAFE_SCALE}); `render` would work equally well here."
            )
        _, _, z = deepzoom_set(args.x, args.y, N=args.N, maxiter=args.maxiter, scale=args.scale)
        fig = render_grid_image(z, cmap=args.cmap)
        fig.savefig(args.output, bbox_inches="tight", pad_inches=0)
        print(f"wrote {args.output}")

    elif args.command == "video":
        render_zoom_video(
            args.x,
            args.y,
            args.output,
            start_scale=args.start_scale,
            end_scale=args.end_scale,
            num_frames=args.frames,
            fps=args.fps,
            N=args.N,
            maxiter=args.maxiter,
            cmap=args.cmap,
            with_audio=not args.no_audio,
        )
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

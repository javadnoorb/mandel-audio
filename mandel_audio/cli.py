"""Command-line entry point.

Subcommands:

* ``mandel-audio render`` — render a Mandelbrot view to a PNG.
* ``mandel-audio video`` — render a music-reactive zoom video.
* ``mandel-audio sonify`` — sonify a point's orbit to a WAV file.
"""

from __future__ import annotations

import argparse

from mandel_audio.audio import orbit_to_audio, save_wav
from mandel_audio.reactive import render_reactive_video
from mandel_audio.render import mandelbrot_image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mandel-audio",
        description="A fractal zoom video renderer that reacts to music.",
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

    video_p = sub.add_parser(
        "video", help="Render a zoom-in video that reacts to music (color + beat-synced zoom)."
    )
    video_p.add_argument("-x", type=str, default="-0.74529", help="center real part")
    video_p.add_argument("-y", type=str, default="0.113075", help="center imaginary part")
    video_p.add_argument(
        "--audio-file",
        type=str,
        default=None,
        help="a music file to react to and use as the soundtrack; if omitted, a "
        "soundtrack is generated from the target point's own orbit",
    )
    video_p.add_argument("--start-scale", type=float, default=0.0, help="starting log2 zoom")
    video_p.add_argument("--end-scale", type=float, default=15.0, help="ending log2 zoom")
    video_p.add_argument(
        "--beat-punch", type=float, default=0.6, help="extra zoom-in added on detected beats"
    )
    video_p.add_argument("--fps", type=int, default=24, help="frames per second")
    video_p.add_argument("-N", type=int, default=400, help="grid resolution (N x N)")
    video_p.add_argument("--maxiter", type=int, default=500, help="max iterations per frame")
    video_p.add_argument(
        "--max-duration",
        type=float,
        default=None,
        help="cap the video length in seconds (default: full track length, or 8s generated)",
    )
    video_p.add_argument(
        "-o", "--output", type=str, default="zoom.mp4", help="output file path"
    )

    sonify_p = sub.add_parser(
        "sonify", help="Sonify a point's orbit to a WAV file (standalone, not video-related)."
    )
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

    elif args.command == "video":
        render_reactive_video(
            args.x,
            args.y,
            args.output,
            audio_path=args.audio_file,
            start_scale=args.start_scale,
            end_scale=args.end_scale,
            beat_punch=args.beat_punch,
            fps=args.fps,
            N=args.N,
            maxiter=args.maxiter,
            max_duration=args.max_duration,
        )
        print(f"wrote {args.output}")

    elif args.command == "sonify":
        audio = orbit_to_audio(
            args.x, args.y, duration=args.duration, sr=args.sr, maxiter=args.maxiter
        )
        save_wav(args.output, audio, sr=args.sr)
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

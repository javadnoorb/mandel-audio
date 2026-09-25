# mandel-audio

Explore the Mandelbrot set — visually, and (in upcoming PRs) sonically.

This is a numba-accelerated Mandelbrot renderer. Points inside the set
return `-1` (distinct from points that escape immediately); points that
escape get a smoothed, continuous escape count for banding-free coloring.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
# render a PNG
mandel-audio render -x -0.74529 -y 0.113075 --scale 8 --maxiter 2000 -o zoom.png

# sonify a point's orbit to a WAV file
mandel-audio sonify -x -0.74529 -y 0.113075 --duration 5 -o orbit.wav

# render past float64 zoom limits (note the quoted, high-precision coordinates)
mandel-audio deepzoom -x "-0.342071683454700989522671970850" \
                       -y "-0.616557516977488490462311059437" \
                       --scale 60 -o deepzoom.png

# render a zoom-in video with an orbit-sonification soundtrack
mandel-audio video -x -0.74529 -y 0.113075 --end-scale 20 --frames 120 -o zoom.mp4

# library
python -c "
from mandel_audio.render import mandelbrot_image
fig = mandelbrot_image(-0.5, 0.0, scale=0, maxiter=1000, cmap='gnuplot2')
fig.savefig('mandelbrot.png')
"
```

### Sonification

`mandel-audio sonify` computes the orbit of `c = x + y*i` under
`z -> z**2 + c` and resamples it into an audio buffer (real part on the
left channel, imaginary part on the right):

- points **inside** the set settle onto a fixed point or short cycle →
  a tone or a small chord;
- points near the **boundary** wander chaotically → noise-like textures;
- points that **escape quickly** → a short chirp.

Try a boundary point like `-0.74529, 0.113075` (near the "seahorse
valley") versus a deep interior point like `-1.0, 0.0` (center of the
period-2 bulb) to hear the difference.

`scale` is a log2 zoom factor (each +1 halves the viewport). Float64
precision caps useful zoom at roughly `scale=45`.

### Deep zoom

Past `scale=45`, `mandel-audio deepzoom` switches to perturbation
theory: one high-precision reference orbit (via `mpmath`), plus a
float64 delta per pixel — see `mandel_audio/deepzoom.py` for the
math. Pass `x`/`y` as **quoted strings** with enough digits for your
target scale (a plain float only carries ~15-17 significant digits,
which defeats the point).

This implementation does not do glitch correction/rebasing, so very
deep or off-center zooms may show speckled artifacts; picking a
reference point that doesn't escape quickly (near the zoom target,
ideally just inside the set) keeps them minimal.

### Video

`mandel-audio video` renders a zoom-in sequence (via `ffmpeg`, bundled
through `imageio-ffmpeg` — no system install needed) from `--start-scale`
to `--end-scale`, automatically switching to the deep-zoom renderer once
`--end-scale` exceeds float64 limits. By default the soundtrack is the
target point's orbit sonification, stretched to the video's duration.

## Development

```bash
pytest
ruff check .
```

## Project layout

```
mandel_audio/
  fractal.py    # numba-jitted escape-time computation (float64)
  deepzoom.py   # perturbation-based deep zoom, past float64 limits
  audio.py      # orbit sonification (WAV)
  render.py     # matplotlib rendering
  video.py      # zoom-in video rendering + soundtrack muxing
  cli.py        # `mandel-audio` command
tests/
web/            # WebGL + Web Audio interactive explorer
```

## Roadmap

This repo is being revamped across several PRs:

1. **Foundation**: fixed bugs, package restructure, tests, CI,
   notebook removed.
2. **Audio**: sonify orbits (escape trajectories) to WAV.
3. **Web app**: a WebGL + Web Audio interactive explorer.
4. **Deep zoom & video** (this PR): perturbation-based deep zoom and
   rendered zoom videos with a generated soundtrack.

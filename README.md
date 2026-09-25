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
# CLI: render a PNG
mandel-audio -x -0.74529 -y 0.113075 --scale 8 --maxiter 2000 -o zoom.png

# library
python -c "
from mandel_audio.render import mandelbrot_image
fig = mandelbrot_image(-0.5, 0.0, scale=0, maxiter=1000, cmap='gnuplot2')
fig.savefig('mandelbrot.png')
"
```

`scale` is a log2 zoom factor (each +1 halves the viewport). Float64
precision caps useful zoom at roughly `scale=45`; a deep-zoom
(perturbation-based) renderer is planned as a follow-up.

## Development

```bash
pytest
ruff check .
```

## Project layout

```
mandel_audio/
  fractal.py   # numba-jitted escape-time computation
  render.py    # matplotlib rendering
  cli.py       # `mandel-audio` command
tests/
```

## Roadmap

This repo is being revamped across several PRs:

1. **Foundation** (this PR): fixed bugs, package restructure, tests, CI,
   notebook removed.
2. **Audio**: sonify orbits (escape trajectories) to WAV.
3. **Web app**: a WebGL + Web Audio interactive explorer.
4. **Deep zoom & video**: perturbation-based deep zoom and rendered
   zoom videos with a generated soundtrack.

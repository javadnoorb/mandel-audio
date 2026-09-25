# mandel-audio

Render a Mandelbrot zoom video that **reacts to music**: color blends
shift with the track's bass/mid/treble balance, brightness tracks
loudness, and detected beats punch the zoom forward.

This is a numba-accelerated Mandelbrot renderer under the hood. Points
inside the set return `-1` (distinct from points that escape
immediately); points that escape get a smoothed, continuous escape
count for banding-free coloring.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
# the main event: a zoom video that reacts to a music file
mandel-audio video -x -0.74529 -y 0.113075 --audio-file song.mp3 \
                    --end-scale 15 -o zoom.mp4

# no music? a soundtrack is generated from the target point's own
# orbit, and the video reacts to that instead
mandel-audio video -x -0.74529 -y 0.113075 --end-scale 8 -o zoom.mp4

# render a single PNG
mandel-audio render -x -0.74529 -y 0.113075 --scale 8 --maxiter 2000 -o zoom.png

# library
python -c "
from mandel_audio.render import mandelbrot_image
fig = mandelbrot_image(-0.5, 0.0, scale=0, maxiter=1000, cmap='gnuplot2')
fig.savefig('mandelbrot.png')
"
```

### Music-reactive video

`mandel-audio video` is the core feature. Give it `--audio-file` and it:

1. Analyzes the track (`mandel_audio/audio_analysis.py`, via
   `librosa`) into per-frame **bass/mid/treble energy**, **loudness**,
   and **beat** pulses, aligned to the video's `--fps`.
2. Colors each frame as a blend of three palettes — `inferno` (bass),
   `viridis` (mid), `cool` (treble) — weighted by that frame's band
   energies, so a bass-heavy passage skews warm and a treble-heavy one
   skews cool. Brightness tracks loudness.
3. Adds a short extra zoom-in (`--beat-punch`) on every detected beat,
   on top of a steady `--start-scale` → `--end-scale` ramp.
4. Muxes the original track back in as the soundtrack (via `ffmpeg`,
   bundled through `imageio-ffmpeg` — no system install needed).

Without `--audio-file`, a soundtrack is generated from the target
point's own orbit (`mandel_audio.audio.orbit_to_audio`, sonifying the
orbit's real/imaginary parts as left/right audio channels) and fed
through the *same* analysis pipeline, so the video is still reactive —
just to a fractal-generated track instead of a real song. That same
sonification is also available on its own:

```bash
mandel-audio sonify -x -0.74529 -y 0.113075 --duration 5 -o orbit.wav
```

- points **inside** the set settle onto a fixed point or short cycle →
  a tone or a small chord;
- points near the **boundary** wander chaotically → noise-like textures;
- points that **escape quickly** → a short chirp.

`scale` is a log2 zoom factor (each +1 halves the viewport). Float64
precision caps `--end-scale` at roughly `45`; a perturbation-based
deep-zoom renderer that goes past that is a planned follow-up (see
Roadmap).

## Development

```bash
pytest
ruff check .
```

## Project layout

```
mandel_audio/
  fractal.py         # numba-jitted escape-time computation (float64)
  audio.py            # orbit sonification (generative soundtrack fallback)
  audio_analysis.py   # music -> per-frame bass/mid/treble/loudness/beat
  reactive.py          # ties audio analysis to fractal color + zoom
  render.py            # matplotlib rendering (single-frame PNGs)
  cli.py               # `mandel-audio` command
tests/
```

## Roadmap

This is the core music-reactive video feature, plus the standalone
`sonify` command. A couple of things are still deferred to smaller,
separate follow-up PRs so they don't block reviewing this one:

- **Deep zoom**: perturbation-based rendering past float64's
  `scale≈45` limit, for extreme zooms.
- **Web explorer**: an interactive WebGL/Web Audio browser version.

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

# render past float64 zoom limits (note the quoted, high-precision coordinates)
mandel-audio deepzoom -x "-0.342071683454700989522671970850" \
                       -y "-0.616557516977488490462311059437" \
                       --scale 60 -o deepzoom.png

# sonify a point's orbit to a WAV file (a fun side effect, not the main feature)
mandel-audio sonify -x -0.74529 -y 0.113075 --duration 5 -o orbit.wav

# library
python -c "
from mandel_audio.render import mandelbrot_image
fig = mandelbrot_image(-0.5, 0.0, scale=0, maxiter=1000, cmap='gnuplot2')
fig.savefig('mandelbrot.png')
"
```

### Music-reactive video

`mandel-audio video` is the core feature. Give it `--audio-file` and
it:

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
point's own orbit (`mandel_audio.audio.orbit_to_audio`) and fed
through the *same* analysis pipeline, so the video is still reactive —
just to a fractal-generated track instead of a real song.

`--end-scale` can go past float64 zoom limits (`scale=45`); frames
automatically switch to the perturbation-based deep-zoom renderer once
needed (see below).

### Deep zoom

Past `scale=45`, rendering switches to perturbation theory: one
high-precision reference orbit (via `mpmath`), plus a float64 delta
per pixel — see `mandel_audio/deepzoom.py` for the math. Use
`mandel-audio deepzoom` directly for a single deep frame; pass `x`/`y`
as **quoted strings** with enough digits for your target scale (a
plain float only carries ~15-17 significant digits, which defeats the
point).

This implementation does not do glitch correction/rebasing, so very
deep or off-center zooms may show speckled artifacts; picking a
reference point that doesn't escape quickly (near the zoom target,
ideally just inside the set) keeps them minimal.

### Sonification

`mandel-audio sonify` computes the orbit of `c = x + y*i` under
`z -> z**2 + c` and resamples it into an audio buffer (real part on the
left channel, imaginary part on the right):

- points **inside** the set settle onto a fixed point or short cycle →
  a tone or a small chord;
- points near the **boundary** wander chaotically → noise-like textures;
- points that **escape quickly** → a short chirp.

This started as its own feature but is now mainly the generative
fallback for `mandel-audio video` when no `--audio-file` is given.

## Development

```bash
pytest
ruff check .
```

## Project layout

```
mandel_audio/
  fractal.py         # numba-jitted escape-time computation (float64)
  deepzoom.py         # perturbation-based deep zoom, past float64 limits
  audio.py             # orbit sonification (generative soundtrack fallback)
  audio_analysis.py    # music -> per-frame bass/mid/treble/loudness/beat
  reactive.py           # ties audio analysis to fractal color + zoom
  render.py             # matplotlib rendering (single-frame PNGs)
  cli.py                # `mandel-audio` command
tests/
web/                    # WebGL interactive explorer (visual engine; not yet
                         # wired up to live audio reactivity)
```

## Roadmap

This repo is being revamped across several PRs. The core goal is a
**music-reactive fractal zoom video** — that reshaped the plan
partway through:

1. **Foundation**: fixed bugs, package restructure, tests, CI,
   notebook removed.
2. **Orbit sonification**: sonify orbits (escape trajectories) to WAV.
   Originally framed as the audio feature; now the generative
   soundtrack fallback for video (see below).
3. **Web app**: a WebGL interactive explorer. The rendering engine
   carries forward; live audio reactivity in the browser (matching
   the video renderer) is a follow-up.
4. **Deep zoom**: perturbation-based zoom past float64 limits.
5. **Music-reactive video** (this PR): the actual goal — a zoom video
   whose color and zoom react to a music track, replacing the earlier
   plain orbit-soundtrack video renderer.

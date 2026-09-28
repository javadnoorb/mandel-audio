# CLAUDE.md

Music-reactive Mandelbrot zoom videos. See README.md for usage; this file
covers what isn't obvious from the code.

## Setup and checks

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/ruff check .
```

`ruff format` isn't enforced (several existing files don't match it); don't
reformat files you aren't otherwise changing.

Re-run the `pip install` after pulling: dependencies get added (e.g. `tqdm`).

## Direction

- The fractal computation is moving to Fraktaler 3 + zoomasm (README,
  "Fraktaler 3 + zoomasm workflow"; `tools/`). This repo's distinctive value
  is the music analysis and the music -> visuals mapping, not the renderer.
  Don't invest in `fractal.py`/`deepzoom.py` performance without asking.
- That workflow is unproven end to end: keyframes rendered fine, but zoomasm
  hasn't produced a video yet, and the Z calibration in
  `tools/song_to_zoomasm.py` is on paper only.
- Known weak spot: librosa's `beat_track` reported 90 bpm on a ~136 bpm techno
  track, so beat punches may be off. Planned replacement: beat_this (CPJKU).

## Rendering cost (8-core laptop, CPU only)

- `mandel-audio video -N 720 --maxiter 1500 --workers 8`: ~4 s per video second.
- `-N 1080 --maxiter 3000 --end-scale 28 --workers 8`: ~15 s per video second
  (a 4-minute track took 60 min).
- Fraktaler 3 keyframes, 6144x680, 48 frames: 20 min.

Long renders pin every core: say how long before starting one, and prefer a
short `--max-duration`/low `-N` test first.

## Music

- Only use tracks whose license allows derivatives (CC0, BY, BY-SA, BY-NC,
  BY-NC-SA). No "ND". "NC" is only for non-monetized videos.
- Every CC BY* track needs a credit line in the video description.
- Good sources: incompetech.com (Kevin MacLeod, CC BY 4.0) and Free Music
  Archive (`/track/<slug>/stream/` URLs download without login; licenses on
  track pages).
- Don't use archive.org's "darktechno" collection: it's labeled CC0 but is
  commercial releases (Steve Rachmad, Rodhad, ...) uploaded without rights.

## zoomasm gotchas

- Always generate sessions muted (the script does): zoomasm's realtime audio
  player makes loud scratching noises through the speakers when rendering
  can't keep up, even in `--record` mode. Muting doesn't affect the
  soundtrack in the output video.
- zoomasm is built for a real GPU. The one attempt with Mesa's software
  renderer (llvmpipe) sat mostly idle for 10 minutes without writing a frame.

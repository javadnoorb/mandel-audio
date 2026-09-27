# mandel-audio web explorer

An interactive Mandelbrot explorer: WebGL2 for real-time rendering in
the browser. No build step — plain HTML/CSS/JS modules.

## Run locally

```bash
cd web
python3 -m http.server 8000
# open http://localhost:8000
```

Any static file server works (serving over `file://` will not, since
`app.js` is loaded as an ES module).

## Controls

- **scroll / pinch** — zoom, centered on the cursor
- **drag** — pan
- **palette** — pick a color scheme
- **max iter** — detail level of the fractal render
- **deep zoom (beta)** — switch to a perturbation-based renderer past
  the ordinary GPU precision limit (see below)
- **copy link** — the URL always reflects the current view
  (`?x=&y=&scale=&maxiter=&palette=`, plus `deep=1` and dd-precision
  `xhi`/`xlo`/`yhi`/`ylo` params when deep zoom is on), so any view is
  shareable

## Notes

- The default renderer uses 32-bit floats on the GPU, which run out of
  precision far short of true deep zoom and well short of the float64
  (`scale=45`) limit on the Python side. Its zoom cap and the
  "approaching precision limits" warning are computed dynamically from
  the canvas resolution and the current view center (see
  `maxScaleForPrecision` in `app.js`) rather than a fixed scale, since
  where pixels start visibly quantizing depends on both.
- Checking **deep zoom** switches to a perturbation-theory renderer
  (`deepzoom.js`/`bignum.js`), the same technique
  `mandel_audio.deepzoom` uses on the Python side, but built on a small
  self-contained double-double (dd) arithmetic module instead of
  mpmath (no bignum library or build step). It computes one
  high-precision reference orbit and tracks only the small per-pixel
  delta from it in the shader, which stays representable in float32
  however small the actual viewport is. This pushes the usable zoom
  out to roughly `scale=90` (dd's ~31-32 decimal digits of precision),
  re-baselining the reference orbit automatically as you pan/zoom
  deeper so it never drifts far enough from the view to reintroduce
  the same precision problem one level up.
- **Known limitation** (shared with the Python version): no "glitch
  correction" for pixels whose true orbit diverges too far from the
  reference orbit — a fast-escaping reference point shows a warning
  and may leave visible artifacts. Deeper zooms also need higher
  **max iter** to resolve detail, same as the Python renderer; a
  minibrot's exact center can render as flat black at low iteration
  counts even though detail is there at higher counts.

## Deploying

This is a static site — any static host works. It's deployed
automatically to GitHub Pages by `.github/workflows/pages.yml` on
every push to `master` that touches `web/`. See the repo's Pages URL
under Settings → Pages once the first deployment completes.

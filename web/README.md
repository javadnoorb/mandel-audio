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
- **copy link** — the URL always reflects the current view
  (`?x=&y=&scale=&maxiter=&palette=`), so any view is shareable

## Notes

- Rendering uses 32-bit floats on the GPU, which run out of precision
  far short of true deep zoom and well short of the float64
  (`scale=45`) limit on the Python side. The zoom cap and the
  "approaching precision limits" warning are computed dynamically from
  the canvas resolution and the current view center (see
  `maxScaleForPrecision` in `app.js`) rather than a fixed scale, since
  where pixels start visibly quantizing depends on both. A
  perturbation-based deep-zoom renderer is planned as a follow-up.

## Deploying

This is a static site — any static host works. It's deployed
automatically to GitHub Pages by `.github/workflows/pages.yml` on
every push to `master` that touches `web/`. See the repo's Pages URL
under Settings → Pages once the first deployment completes.

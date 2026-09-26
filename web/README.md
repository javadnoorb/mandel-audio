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

- Rendering uses 32-bit floats on the GPU, so zoom is capped around
  `scale=22` — well short of the float64 (`scale=45`) limit on the
  Python side, and far short of true deep zoom. A perturbation-based
  deep-zoom renderer is planned as a follow-up.

## Deploying

This is a static site — any static host works (GitHub Pages, Netlify,
etc.). For GitHub Pages: Settings → Pages → deploy from the `web/`
folder on this branch (or copy `web/` contents to a `gh-pages` branch).

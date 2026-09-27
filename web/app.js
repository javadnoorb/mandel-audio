import { VERTEX_SRC, FRAGMENT_SRC, DEEP_FRAGMENT_SRC, MAX_ITER_CAP } from "./shaders.js";
import { ddAdd, ddSub, ddMul, ddFromNumber, ddToNumber, ddcFromNumbers } from "./bignum.js";
import { findGoodReference, MAX_REF_ITER, DEEP_MAX_SCALE } from "./deepzoom.js";

// GPU fragment shaders here run on 32-bit floats (~24-bit mantissa),
// far less precision than the float64 used on the Python/numba side.
// The shader computes c = u_center + uv * (2*halfWidth) in highp
// float; that addition rounds to the ULP of |u_center|'s magnitude,
// not of the (tiny, deeply-zoomed) offset. Once the per-pixel step in
// the complex plane drops below that ULP, screen pixels start
// collapsing onto the same float32 value ("pixelation"). Where that
// happens depends on canvas resolution and how far the view center is
// from zero, not on scale alone — so compute it dynamically instead
// of using one fixed constant (see mandel_audio.fractal.MAX_SAFE_SCALE
// for the analogous, also-resolution-dependent, float64 cliff).
const FLOAT32_MANTISSA_BITS = 24;

// Largest zoom `scale` at which a screen pixel's step in the complex
// plane is still at least `marginUlps` float32 ULPs (of the view
// center's magnitude) — i.e. still resolvable as distinct pixels.
function maxScaleForPrecision(marginUlps, cx, cy) {
  const mag = Math.max(Math.abs(cx), Math.abs(cy), 0.25);
  const ulp = Math.pow(2, -FLOAT32_MANTISSA_BITS) * mag;
  const pixelHeight = canvas.height || window.innerHeight;
  // pixelStep(scale) = 2*halfWidth(scale)/pixelHeight = 2.5*2^-scale/pixelHeight
  // solve pixelStep(scale) == marginUlps * ulp for scale:
  return -Math.log2((marginUlps * ulp * pixelHeight) / 2.5);
}
const HARD_CAP_MARGIN_ULPS = 1; // beyond this, pixels are provably indistinguishable
const WARNING_MARGIN_ULPS = 8; // warn with some headroom before that cliff

// The "deep zoom" checkbox only means "allowed to use the perturbation
// renderer past the float32 cliff" -- it should stay a no-op while the
// direct renderer can still show the current view exactly. Otherwise
// panning around at an ordinary, shallow zoom can land the view center
// on some unrelated fast-escaping point and spuriously trigger the
// perturbation path's reference-orbit machinery (and its "reference
// escaped" warning) for a view that never needed it.
function usingDeepRenderer() {
  return state.deepZoom && state.scale > maxScaleForPrecision(HARD_CAP_MARGIN_ULPS, state.x, state.y);
}

const canvas = document.getElementById("fractal");
const gl = canvas.getContext("webgl2");
if (!gl) {
  document.body.innerHTML =
    '<p style="color:#eee;font-family:sans-serif;padding:2em">WebGL2 is not available in this browser.</p>';
  throw new Error("WebGL2 unavailable");
}

// ---- state, seeded from URL query params for shareable links ----
const params = new URLSearchParams(location.search);
const state = {
  x: parseFloat(params.get("x") ?? "-0.5"),
  y: parseFloat(params.get("y") ?? "0.0"),
  scale: parseFloat(params.get("scale") ?? "0"),
  maxiter: parseInt(params.get("maxiter") ?? "500", 10),
  palette: parseInt(params.get("palette") ?? "0", 10),
  deepZoom: params.get("deep") === "1",
};
const DEFAULT_STATE = { x: -0.5, y: 0.0, scale: 0, maxiter: 500, palette: 0 };

// ---- shader setup: one program for the direct float32 renderer, one
// for the perturbation-based deep-zoom renderer (see shaders.js) ----
function compile(type, src) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, src);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    throw new Error(gl.getShaderInfoLog(shader));
  }
  return shader;
}

function createProgram(vertexSrc, fragmentSrc) {
  const program = gl.createProgram();
  gl.attachShader(program, compile(gl.VERTEX_SHADER, vertexSrc));
  gl.attachShader(program, compile(gl.FRAGMENT_SHADER, fragmentSrc));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    throw new Error(gl.getProgramInfoLog(program));
  }
  return program;
}

const directProgram = createProgram(VERTEX_SRC, FRAGMENT_SRC);
const deepProgram = createProgram(VERTEX_SRC, DEEP_FRAGMENT_SRC);

const quad = new Float32Array([-1, -1, 1, -1, -1, 1, 1, -1, 1, 1, -1, 1]);
const buf = gl.createBuffer();
gl.bindBuffer(gl.ARRAY_BUFFER, buf);
gl.bufferData(gl.ARRAY_BUFFER, quad, gl.STATIC_DRAW);
// Both programs declare a_position at explicit location 0 (see
// shaders.js), so this attribute setup applies to either.
gl.enableVertexAttribArray(0);
gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

const uResolution = gl.getUniformLocation(directProgram, "u_resolution");
const uCenter = gl.getUniformLocation(directProgram, "u_center");
const uScale = gl.getUniformLocation(directProgram, "u_scale");
const uMaxiter = gl.getUniformLocation(directProgram, "u_maxiter");
const uPalette = gl.getUniformLocation(directProgram, "u_palette");

const uResolutionDeep = gl.getUniformLocation(deepProgram, "u_resolution");
const uCenterDelta = gl.getUniformLocation(deepProgram, "u_centerDelta");
const uHalfWidthDeep = gl.getUniformLocation(deepProgram, "u_halfWidth");
const uRefOrbit = gl.getUniformLocation(deepProgram, "u_refOrbit");
const uRefLen = gl.getUniformLocation(deepProgram, "u_refLen");
const uMaxiterDeep = gl.getUniformLocation(deepProgram, "u_maxiter");
const uPaletteDeep = gl.getUniformLocation(deepProgram, "u_palette");

// Reference-orbit texture: one RG32F texel per iteration (real, imag),
// sampled with texelFetch (no filtering) in the deep-zoom shader.
const refOrbitTexture = gl.createTexture();
gl.bindTexture(gl.TEXTURE_2D, refOrbitTexture);
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
gl.texStorage2D(gl.TEXTURE_2D, 1, gl.RG32F, MAX_REF_ITER, 1);

function resize() {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.floor(window.innerWidth * dpr);
  canvas.height = Math.floor(window.innerHeight * dpr);
  gl.viewport(0, 0, canvas.width, canvas.height);
  render();
}

function render() {
  if (usingDeepRenderer()) {
    rebaseReferenceIfNeeded(); // lazily build/refresh the reference orbit only once actually needed
    gl.useProgram(deepProgram);
    gl.uniform2f(uResolutionDeep, canvas.width, canvas.height);
    const [dxr, dyr] = centerDeltaFloat();
    gl.uniform2f(uCenterDelta, dxr, dyr);
    gl.uniform1f(uHalfWidthDeep, halfWidth());
    gl.uniform1i(uMaxiterDeep, Math.min(state.maxiter, MAX_ITER_CAP));
    gl.uniform1i(uPaletteDeep, state.palette);
    gl.uniform1i(uRefLen, refOrbitData ? refOrbitData.count : 0);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, refOrbitTexture);
    gl.uniform1i(uRefOrbit, 0);
  } else {
    gl.useProgram(directProgram);
    gl.uniform2f(uResolution, canvas.width, canvas.height);
    gl.uniform2f(uCenter, state.x, state.y);
    gl.uniform1f(uScale, state.scale);
    gl.uniform1i(uMaxiter, Math.min(state.maxiter, MAX_ITER_CAP));
    gl.uniform1i(uPalette, state.palette);
  }
  gl.drawArrays(gl.TRIANGLES, 0, 6);
}

// ---- screen <-> complex-plane mapping (mirrors the shader) ----
function halfWidth() {
  return 1.25 * Math.pow(2, -state.scale);
}
function screenToComplex(px, py) {
  const dpr = canvas.width / window.innerWidth;
  const x = px * dpr;
  const y = py * dpr;
  const uvx = (x - 0.5 * canvas.width) / canvas.height;
  const uvy = (canvas.height - y - 0.5 * canvas.height) / canvas.height; // flip: canvas y grows down
  const hw = halfWidth();
  return [state.x + uvx * 2 * hw, state.y + uvy * 2 * hw];
}
// Deep-zoom analogue: the per-pixel offset from the view center stays
// small (float64-safe) even at extreme zoom, so it's added to the
// dd-precision view center with ordinary dd arithmetic rather than the
// shallow version's plain float64 addition (which is exactly what
// breaks down at depth).
function screenToComplexDeep(px, py) {
  const dpr = canvas.width / window.innerWidth;
  const x = px * dpr;
  const y = py * dpr;
  const uvx = (x - 0.5 * canvas.width) / canvas.height;
  const uvy = (canvas.height - y - 0.5 * canvas.height) / canvas.height;
  const hw = halfWidth();
  const offRe = uvx * 2 * hw;
  const offIm = uvy * 2 * hw;
  return {
    re: ddAdd(viewCenterDD.re, ddFromNumber(offRe)),
    im: ddAdd(viewCenterDD.im, ddFromNumber(offIm)),
  };
}

// ---- deep-zoom bookkeeping: a dd-precision view center, and a
// perturbation reference orbit re-baselined to it whenever the two
// drift far enough apart to risk the same precision loss this whole
// feature exists to avoid (see rebaseReferenceIfNeeded) ----
let viewCenterDD = null;
let refCenterDD = null;
let refOrbitData = null;
let refEscapedEarly = false;

function centerDeltaFloat() {
  if (!refCenterDD) return [0, 0];
  return [
    ddToNumber(ddSub(viewCenterDD.re, refCenterDD.re)),
    ddToNumber(ddSub(viewCenterDD.im, refCenterDD.im)),
  ];
}

function uploadRefOrbitTexture(orbit) {
  const n = orbit.count;
  const interleaved = new Float32Array(n * 2);
  for (let i = 0; i < n; i++) {
    interleaved[2 * i] = orbit.real[i];
    interleaved[2 * i + 1] = orbit.imag[i];
  }
  gl.bindTexture(gl.TEXTURE_2D, refOrbitTexture);
  gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, n, 1, gl.RG, gl.FLOAT, interleaved);
}

function rebaseReference() {
  const maxiter = Math.min(state.maxiter, MAX_REF_ITER);
  // Every pixel's iteration budget in the deep shader is capped by
  // however long the reference orbit itself survives, so an unlucky
  // view center that happens to escape early would otherwise truncate
  // detail for the *entire* view, not just itself. Search a small ring
  // of nearby candidates (within the rebase drift tolerance below) for
  // one that survives longer.
  const searchRadius = 0.5 * halfWidth();
  const found = findGoodReference(viewCenterDD.re, viewCenterDD.im, maxiter, searchRadius);
  refCenterDD = { re: found.re, im: found.im };
  refOrbitData = found.orbit;
  uploadRefOrbitTexture(refOrbitData);
  refEscapedEarly = refOrbitData.escaped && refOrbitData.count < maxiter / 4;
}

// Keep the reference orbit within half a viewport-width of the actual
// view center, so the shader's `u_centerDelta + pixel offset` addition
// always combines two similarly-tiny float32 values -- never a large
// drifted delta and a tiny offset, which would just reintroduce the
// float32 cancellation problem one level up.
function rebaseReferenceIfNeeded() {
  if (!refOrbitData) {
    rebaseReference();
    return;
  }
  const [dxr, dyr] = centerDeltaFloat();
  if (Math.hypot(dxr, dyr) > 0.5 * halfWidth()) {
    rebaseReference();
  }
}

// ---- HUD ----
// Looked up defensively: GitHub Pages cache-busts app.js/shaders.js/style.css
// on every deploy (unique ?v=<sha> URL each time), but index.html itself has
// no such versioning, so a browser can pair a stale cached index.html with
// the current app.js if a feature added new elements since that page was
// cached. Missing elements degrade that piece of the HUD instead of
// throwing and halting the whole script before it ever draws the canvas.
const coordsEl = document.getElementById("coords");
const warningEl = document.getElementById("precision-warning");
const deepWarningEl = document.getElementById("deepzoom-warning");
function updateHud() {
  if (usingDeepRenderer()) {
    if (coordsEl) {
      coordsEl.textContent =
        `x: ${state.x.toFixed(10)}, y: ${state.y.toFixed(10)}, scale: ${state.scale.toFixed(2)} (deep)`;
    }
    warningEl?.classList.add("hidden");
    deepWarningEl?.classList.toggle("hidden", !refEscapedEarly);
  } else {
    if (coordsEl) {
      coordsEl.textContent = `x: ${state.x.toFixed(6)}, y: ${state.y.toFixed(6)}, scale: ${state.scale.toFixed(2)}`;
    }
    const warnScale = maxScaleForPrecision(WARNING_MARGIN_ULPS, state.x, state.y);
    warningEl?.classList.toggle("hidden", state.scale < warnScale);
    deepWarningEl?.classList.add("hidden");
  }
}

let urlTimer = null;
function syncUrl() {
  clearTimeout(urlTimer);
  urlTimer = setTimeout(() => {
    const p = new URLSearchParams({
      scale: state.scale.toFixed(4),
      maxiter: String(state.maxiter),
      palette: String(state.palette),
    });
    if (state.deepZoom && viewCenterDD) {
      // Round-trip full dd precision (hi+lo) rather than a single
      // float64's ~17 digits, so a shared deep-zoom link doesn't lose
      // the extra depth this feature exists to provide.
      p.set("deep", "1");
      p.set("xhi", String(viewCenterDD.re[0]));
      p.set("xlo", String(viewCenterDD.re[1]));
      p.set("yhi", String(viewCenterDD.im[0]));
      p.set("ylo", String(viewCenterDD.im[1]));
    } else {
      p.set("x", state.x.toFixed(10));
      p.set("y", state.y.toFixed(10));
    }
    history.replaceState(null, "", `?${p.toString()}`);
  }, 250);
}

function redraw() {
  render();
  updateHud();
  syncUrl();
}

// Restore a deep-zoom view from URL params (full dd precision if
// present), or bootstrap one from the current shallow x/y otherwise.
// The reference orbit itself is built lazily by render() the first
// time it's actually needed (see usingDeepRenderer/rebaseReferenceIfNeeded).
if (state.deepZoom) {
  const xhi = params.get("xhi");
  const yhi = params.get("yhi");
  if (xhi !== null && yhi !== null) {
    viewCenterDD = {
      re: [parseFloat(xhi), parseFloat(params.get("xlo") ?? "0")],
      im: [parseFloat(yhi), parseFloat(params.get("ylo") ?? "0")],
    };
  } else {
    viewCenterDD = ddcFromNumbers(state.x, state.y);
  }
  state.x = ddToNumber(viewCenterDD.re);
  state.y = ddToNumber(viewCenterDD.im);
}

// Draw the initial view now, before wiring up optional controls below --
// so the canvas renders even if a stale cached index.html (see the HUD
// comment above) is missing an element some later control-wiring expects.
window.addEventListener("resize", resize);
resize();
updateHud();

// ---- interaction: wheel to zoom, drag to pan, pinch to zoom+pan ----
function zoomAt(cx, cy, newScale) {
  const cap = maxScaleForPrecision(HARD_CAP_MARGIN_ULPS, cx, cy);
  newScale = Math.min(Math.max(newScale, 0), cap);
  const oldHw = halfWidth();
  state.scale = newScale;
  const newHw = halfWidth();
  // keep the point under the cursor/pinch-midpoint fixed
  state.x = cx - (cx - state.x) * (newHw / oldHw);
  state.y = cy - (cy - state.y) * (newHw / oldHw);
}

function zoomAtDeep(targetDD, newScale) {
  newScale = Math.min(Math.max(newScale, 0), DEEP_MAX_SCALE);
  const oldHw = halfWidth();
  state.scale = newScale;
  const newHw = halfWidth();
  const ratio = ddFromNumber(newHw / oldHw);
  // newCenter = target - (target - oldCenter) * ratio, all in dd, so
  // the "recenter on the zoomed-in point" step never loses the bits
  // that matter at extreme depth the way plain float64 subtraction/
  // multiplication would.
  const diffRe = ddSub(targetDD.re, viewCenterDD.re);
  const diffIm = ddSub(targetDD.im, viewCenterDD.im);
  viewCenterDD = {
    re: ddSub(targetDD.re, ddMul(diffRe, ratio)),
    im: ddSub(targetDD.im, ddMul(diffIm, ratio)),
  };
  // Reference orbit is (re)built lazily in render() -- see usingDeepRenderer.
  state.x = ddToNumber(viewCenterDD.re);
  state.y = ddToNumber(viewCenterDD.im);
}

canvas.addEventListener("wheel", (e) => {
  e.preventDefault();
  stopAutoZoom();
  if (state.deepZoom) {
    const target = screenToComplexDeep(e.clientX, e.clientY);
    zoomAtDeep(target, state.scale - e.deltaY * 0.0025);
  } else {
    const [cx, cy] = screenToComplex(e.clientX, e.clientY);
    zoomAt(cx, cy, state.scale - e.deltaY * 0.0025);
  }
  redraw();
}, { passive: false });

let dragging = false;
let dragged = false;
let lastX = 0, lastY = 0;

// Pointer Events report each touch as its own pointerId, so a single
// map covers both mouse/single-finger drag and two-finger pinch.
const activePointers = new Map();
let pinchDist = null;

function pointDistance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}
function pointMidpoint(a, b) {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

canvas.addEventListener("pointerdown", (e) => {
  stopAutoZoom();
  canvas.setPointerCapture(e.pointerId);
  activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

  if (activePointers.size === 2) {
    dragging = false;
    const [a, b] = activePointers.values();
    pinchDist = pointDistance(a, b);
  } else if (activePointers.size === 1) {
    dragging = true;
    dragged = false;
    lastX = e.clientX;
    lastY = e.clientY;
  }
});

canvas.addEventListener("pointermove", (e) => {
  if (!activePointers.has(e.pointerId)) return;
  activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

  if (activePointers.size >= 2) {
    const [a, b] = activePointers.values();
    const newDist = pointDistance(a, b);
    const mid = pointMidpoint(a, b);
    if (pinchDist) {
      const newScale = state.scale + Math.log2(newDist / pinchDist);
      if (state.deepZoom) {
        zoomAtDeep(screenToComplexDeep(mid.x, mid.y), newScale);
      } else {
        const [cx, cy] = screenToComplex(mid.x, mid.y);
        zoomAt(cx, cy, newScale);
      }
      redraw();
    }
    pinchDist = newDist;
    return;
  }

  if (!dragging) return;
  const dx = e.clientX - lastX;
  const dy = e.clientY - lastY;
  if (Math.abs(dx) > 2 || Math.abs(dy) > 2) dragged = true;
  if (!dragged) return;
  const dpr = canvas.width / window.innerWidth;
  const hw = halfWidth();
  const deltaXc = (dx * dpr / canvas.height) * 2 * hw;
  const deltaYc = (dy * dpr / canvas.height) * 2 * hw;
  if (state.deepZoom) {
    viewCenterDD = {
      re: ddSub(viewCenterDD.re, ddFromNumber(deltaXc)),
      im: ddAdd(viewCenterDD.im, ddFromNumber(deltaYc)),
    };
    // Reference orbit is (re)built lazily in render() -- see usingDeepRenderer.
    state.x = ddToNumber(viewCenterDD.re);
    state.y = ddToNumber(viewCenterDD.im);
  } else {
    state.x -= deltaXc;
    state.y += deltaYc;
  }
  lastX = e.clientX;
  lastY = e.clientY;
  redraw();
});

function endPointer(e) {
  activePointers.delete(e.pointerId);
  pinchDist = null;
  dragging = false;
  if (activePointers.size === 1) {
    // one finger still down after a pinch ends: resume single-finger pan
    const [remaining] = activePointers.values();
    dragging = true;
    dragged = true;
    lastX = remaining.x;
    lastY = remaining.y;
  }
}

canvas.addEventListener("pointerup", endPointer);
canvas.addEventListener("pointercancel", endPointer);

// ---- controls ----
// Each control is wired defensively (see the HUD comment above): a stale
// cached index.html missing one of these elements should only disable
// that one control, never take down the rest of the page.
const maxiterInput = document.getElementById("maxiter");
const maxiterVal = document.getElementById("maxiter-val");
if (maxiterInput) {
  maxiterInput.value = state.maxiter;
  if (maxiterVal) maxiterVal.textContent = state.maxiter;
  maxiterInput.addEventListener("input", () => {
    state.maxiter = parseInt(maxiterInput.value, 10);
    if (maxiterVal) maxiterVal.textContent = state.maxiter;
    // Reference orbit length depends on maxiter; render()'s lazy rebase only
    // triggers on view-center drift, so force it explicitly here when a
    // stale orbit is actually in use.
    if (usingDeepRenderer()) rebaseReference();
    redraw();
  });
}

const paletteSelect = document.getElementById("palette");
if (paletteSelect) {
  paletteSelect.value = state.palette;
  paletteSelect.addEventListener("change", () => {
    state.palette = parseInt(paletteSelect.value, 10);
    redraw();
  });
}

const deepzoomCheckbox = document.getElementById("deepzoom");
if (deepzoomCheckbox) {
  deepzoomCheckbox.checked = state.deepZoom;
  deepzoomCheckbox.addEventListener("change", () => {
    stopAutoZoom();
    state.deepZoom = deepzoomCheckbox.checked;
    if (state.deepZoom) {
      viewCenterDD = ddcFromNumbers(state.x, state.y);
      refOrbitData = null;
      refCenterDD = null;
      // Reference orbit is only built once actually needed (see
      // usingDeepRenderer) -- at ordinary zoom this is a no-op until you
      // zoom in past what the direct renderer can show.
    } else {
      // the direct float32 shader can't usefully render past its own
      // precision cliff -- drop back to a scale it can actually show.
      state.scale = Math.min(state.scale, maxScaleForPrecision(HARD_CAP_MARGIN_ULPS, state.x, state.y));
    }
    redraw();
  });
}

// ---- auto zoom: continuously zoom in on the current view center,
// automatically crossing into deep zoom once the direct renderer's own
// precision cap is reached, until the deep-zoom cap is hit or the user
// interacts manually (wheel/drag/pinch/checkbox/reset all stop it).
const AUTO_ZOOM_RATE = 1.2; // log2 zoom factor per second
let autoZoomActive = false;
let autoZoomFrame = null;
let autoZoomLastTs = null;
const autoZoomBtn = document.getElementById("autozoom");

function autoZoomStep(ts) {
  if (!autoZoomActive) return;
  if (autoZoomLastTs === null) autoZoomLastTs = ts;
  const dt = (ts - autoZoomLastTs) / 1000;
  autoZoomLastTs = ts;
  const targetScale = state.scale + AUTO_ZOOM_RATE * dt;

  if (state.deepZoom) {
    zoomAtDeep({ re: viewCenterDD.re, im: viewCenterDD.im }, targetScale);
  } else {
    zoomAt(state.x, state.y, targetScale);
  }
  redraw();

  const shallowCap = maxScaleForPrecision(HARD_CAP_MARGIN_ULPS, state.x, state.y);
  if (!state.deepZoom && state.scale >= shallowCap - 1e-6) {
    // Hit the direct renderer's precision cliff -- cross it automatically
    // (next frame's zoomAtDeep) instead of just stalling here.
    state.deepZoom = true;
    if (deepzoomCheckbox) deepzoomCheckbox.checked = true;
    viewCenterDD = ddcFromNumbers(state.x, state.y);
    refOrbitData = null;
    refCenterDD = null;
  } else if (state.deepZoom && state.scale >= DEEP_MAX_SCALE - 1e-6) {
    stopAutoZoom();
    return;
  }
  autoZoomFrame = requestAnimationFrame(autoZoomStep);
}

function startAutoZoom() {
  if (autoZoomActive) return;
  autoZoomActive = true;
  autoZoomLastTs = null;
  if (autoZoomBtn) autoZoomBtn.textContent = "stop zoom";
  autoZoomFrame = requestAnimationFrame(autoZoomStep);
}

function stopAutoZoom() {
  autoZoomActive = false;
  if (autoZoomFrame !== null) cancelAnimationFrame(autoZoomFrame);
  autoZoomFrame = null;
  if (autoZoomBtn) autoZoomBtn.textContent = "auto zoom";
}

autoZoomBtn?.addEventListener("click", () => {
  if (autoZoomActive) stopAutoZoom();
  else startAutoZoom();
});

document.getElementById("reset")?.addEventListener("click", () => {
  stopAutoZoom();
  Object.assign(state, DEFAULT_STATE);
  if (maxiterInput) maxiterInput.value = state.maxiter;
  if (maxiterVal) maxiterVal.textContent = state.maxiter;
  if (paletteSelect) paletteSelect.value = state.palette;
  if (state.deepZoom) {
    viewCenterDD = ddcFromNumbers(state.x, state.y);
    refOrbitData = null;
    refCenterDD = null;
  }
  redraw();
});

document.getElementById("share")?.addEventListener("click", async () => {
  syncUrl();
  try {
    await navigator.clipboard.writeText(location.href);
    const btn = document.getElementById("share");
    if (btn) {
      const original = btn.textContent;
      btn.textContent = "copied!";
      setTimeout(() => (btn.textContent = original), 1200);
    }
  } catch {
    // clipboard API unavailable (e.g. insecure context) — no-op, the
    // URL bar already reflects the current view via history.replaceState.
  }
});

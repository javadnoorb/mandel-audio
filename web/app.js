import { VERTEX_SRC, FRAGMENT_SRC } from "./shaders.js";

// GPU fragment shaders here run on 32-bit floats, which have far less
// precision than the float64 used on the Python/numba side. This caps
// out well before mandel_audio.fractal.MAX_SAFE_SCALE (45).
const MAX_SAFE_SCALE_WEB = 22;
const PRECISION_WARNING_SCALE = 18;

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
};
const DEFAULT_STATE = { x: -0.5, y: 0.0, scale: 0, maxiter: 500, palette: 0 };

// ---- shader setup ----
function compile(type, src) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, src);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    throw new Error(gl.getShaderInfoLog(shader));
  }
  return shader;
}

const program = gl.createProgram();
gl.attachShader(program, compile(gl.VERTEX_SHADER, VERTEX_SRC));
gl.attachShader(program, compile(gl.FRAGMENT_SHADER, FRAGMENT_SRC));
gl.linkProgram(program);
if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
  throw new Error(gl.getProgramInfoLog(program));
}
gl.useProgram(program);

const quad = new Float32Array([-1, -1, 1, -1, -1, 1, 1, -1, 1, 1, -1, 1]);
const buf = gl.createBuffer();
gl.bindBuffer(gl.ARRAY_BUFFER, buf);
gl.bufferData(gl.ARRAY_BUFFER, quad, gl.STATIC_DRAW);
const posLoc = gl.getAttribLocation(program, "a_position");
gl.enableVertexAttribArray(posLoc);
gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0);

const uResolution = gl.getUniformLocation(program, "u_resolution");
const uCenter = gl.getUniformLocation(program, "u_center");
const uScale = gl.getUniformLocation(program, "u_scale");
const uMaxiter = gl.getUniformLocation(program, "u_maxiter");
const uPalette = gl.getUniformLocation(program, "u_palette");

function resize() {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.floor(window.innerWidth * dpr);
  canvas.height = Math.floor(window.innerHeight * dpr);
  gl.viewport(0, 0, canvas.width, canvas.height);
  render();
}

function render() {
  gl.uniform2f(uResolution, canvas.width, canvas.height);
  gl.uniform2f(uCenter, state.x, state.y);
  gl.uniform1f(uScale, state.scale);
  gl.uniform1i(uMaxiter, state.maxiter);
  gl.uniform1i(uPalette, state.palette);
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

// ---- HUD ----
const coordsEl = document.getElementById("coords");
const warningEl = document.getElementById("precision-warning");
function updateHud() {
  coordsEl.textContent = `x: ${state.x.toFixed(6)}, y: ${state.y.toFixed(6)}, scale: ${state.scale.toFixed(2)}`;
  warningEl.classList.toggle("hidden", state.scale < PRECISION_WARNING_SCALE);
}

let urlTimer = null;
function syncUrl() {
  clearTimeout(urlTimer);
  urlTimer = setTimeout(() => {
    const p = new URLSearchParams({
      x: state.x.toFixed(10),
      y: state.y.toFixed(10),
      scale: state.scale.toFixed(4),
      maxiter: String(state.maxiter),
      palette: String(state.palette),
    });
    history.replaceState(null, "", `?${p.toString()}`);
  }, 250);
}

function redraw() {
  render();
  updateHud();
  syncUrl();
}

// ---- interaction: wheel to zoom, drag to pan, pinch to zoom+pan ----
function zoomAt(cx, cy, newScale) {
  newScale = Math.min(Math.max(newScale, 0), MAX_SAFE_SCALE_WEB);
  const oldHw = halfWidth();
  state.scale = newScale;
  const newHw = halfWidth();
  // keep the point under the cursor/pinch-midpoint fixed
  state.x = cx - (cx - state.x) * (newHw / oldHw);
  state.y = cy - (cy - state.y) * (newHw / oldHw);
}

canvas.addEventListener("wheel", (e) => {
  e.preventDefault();
  const [cx, cy] = screenToComplex(e.clientX, e.clientY);
  zoomAt(cx, cy, state.scale - e.deltaY * 0.0025);
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
    const [cx, cy] = screenToComplex(mid.x, mid.y);
    if (pinchDist) {
      zoomAt(cx, cy, state.scale + Math.log2(newDist / pinchDist));
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
  state.x -= (dx * dpr / canvas.height) * 2 * hw;
  state.y += (dy * dpr / canvas.height) * 2 * hw;
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
const maxiterInput = document.getElementById("maxiter");
const maxiterVal = document.getElementById("maxiter-val");
maxiterInput.value = state.maxiter;
maxiterVal.textContent = state.maxiter;
maxiterInput.addEventListener("input", () => {
  state.maxiter = parseInt(maxiterInput.value, 10);
  maxiterVal.textContent = state.maxiter;
  redraw();
});

const paletteSelect = document.getElementById("palette");
paletteSelect.value = state.palette;
paletteSelect.addEventListener("change", () => {
  state.palette = parseInt(paletteSelect.value, 10);
  redraw();
});

document.getElementById("reset").addEventListener("click", () => {
  Object.assign(state, DEFAULT_STATE);
  maxiterInput.value = state.maxiter;
  maxiterVal.textContent = state.maxiter;
  paletteSelect.value = state.palette;
  redraw();
});

document.getElementById("share").addEventListener("click", async () => {
  syncUrl();
  try {
    await navigator.clipboard.writeText(location.href);
    const btn = document.getElementById("share");
    const original = btn.textContent;
    btn.textContent = "copied!";
    setTimeout(() => (btn.textContent = original), 1200);
  } catch {
    // clipboard API unavailable (e.g. insecure context) — no-op, the
    // URL bar already reflects the current view via history.replaceState.
  }
});

window.addEventListener("resize", resize);
resize();
updateHud();

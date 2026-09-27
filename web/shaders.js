// GLSL sources for the Mandelbrot renderer.
//
// The viewport math mirrors mandel_audio.fractal.mandelbrot_set on the
// Python side: `scale` is a log2 zoom factor (each +1 halves the
// viewport width), and the unscaled full-view half-width is 1.25
// (matching Python's unscaled_width=2.5 default).

// Explicit location so the direct and deep-zoom programs (compiled from
// this same source) agree on the attribute index without querying it
// separately per program.
export const VERTEX_SRC = `#version 300 es
layout(location = 0) in vec2 a_position;
void main() {
  gl_Position = vec4(a_position, 0.0, 1.0);
}
`;

// The iteration loop bound must be a compile-time constant in GLSL ES;
// we cap it generously and break out early via u_maxiter. Must match
// mandel_audio.deepzoom.MAX_REF_ITER on the JS side (deepzoom.js).
export const MAX_ITER_CAP = 4000;

// Cosine-based palettes, see Inigo Quilez:
// https://iquilezles.org/articles/palettes/
// Shared between both fragment shaders so the two color paths can't drift.
const PALETTE_GLSL = `
vec3 palette(float t, int which) {
  vec3 a, b, c, d;
  if (which == 0) {
    // fire
    a = vec3(0.55, 0.35, 0.25); b = vec3(0.55, 0.45, 0.35);
    c = vec3(1.0, 0.8, 0.6); d = vec3(0.0, 0.15, 0.30);
  } else if (which == 1) {
    // ocean
    a = vec3(0.35, 0.45, 0.55); b = vec3(0.35, 0.45, 0.55);
    c = vec3(0.8, 1.0, 1.2); d = vec3(0.45, 0.55, 0.70);
  } else if (which == 2) {
    // electric
    a = vec3(0.5, 0.5, 0.5); b = vec3(0.6, 0.5, 0.7);
    c = vec3(2.0, 1.0, 0.0); d = vec3(0.5, 0.2, 0.25);
  } else {
    // gnuplot-ish
    a = vec3(0.5, 0.5, 0.5); b = vec3(0.5, 0.5, 0.5);
    c = vec3(1.0, 0.7, 0.4); d = vec3(0.0, 0.15, 0.20);
  }
  return a + b * cos(6.28318 * (c * t + d));
}
`;

export const FRAGMENT_SRC = `#version 300 es
precision highp float;

uniform vec2 u_resolution;
uniform vec2 u_center;
uniform float u_scale;
uniform int u_maxiter;
uniform int u_palette;

out vec4 outColor;
${PALETTE_GLSL}
void main() {
  vec2 uv = (gl_FragCoord.xy - 0.5 * u_resolution) / u_resolution.y;
  float halfWidth = 1.25 * pow(2.0, -u_scale);
  vec2 c = u_center + uv * (2.0 * halfWidth);

  vec2 z = vec2(0.0);
  float smoothIter = -1.0;
  for (int n = 0; n < ${MAX_ITER_CAP}; n++) {
    if (n >= u_maxiter) break;
    float zr2 = z.x * z.x;
    float zi2 = z.y * z.y;
    if (zr2 + zi2 > 4.0) {
      float logZn = log(zr2 + zi2) * 0.5;
      float nu = log(logZn / log(2.0)) / log(2.0);
      smoothIter = float(n) + 1.0 - nu;
      break;
    }
    z = vec2(zr2 - zi2, 2.0 * z.x * z.y) + c;
  }

  if (smoothIter < 0.0) {
    outColor = vec4(0.0, 0.0, 0.0, 1.0);
  } else {
    float t = sqrt(smoothIter) * 0.15;
    outColor = vec4(palette(t, u_palette), 1.0);
  }
}
`;

// Perturbation-theory renderer for deep zoom, mirroring
// mandel_audio.deepzoom._perturbation_grid: only the reference orbit
// Z_n (uploaded as a texture, computed at dd precision in deepzoom.js)
// needs full range; every pixel just tracks a small delta dz from it,
// which stays representable in float32 however small the viewport is.
//
// u_centerDelta is (current view center - reference point), kept small
// by re-baselining the reference orbit whenever it grows too large
// relative to the viewport (see app.js) -- so this addition never
// combines a huge and a tiny float32 value the way the direct shader's
// `u_center + uv * 2*halfWidth` does.
export const DEEP_FRAGMENT_SRC = `#version 300 es
precision highp float;
precision highp sampler2D;

uniform vec2 u_resolution;
uniform vec2 u_centerDelta;
uniform float u_halfWidth;
uniform sampler2D u_refOrbit;
uniform int u_refLen;
uniform int u_maxiter;
uniform int u_palette;

out vec4 outColor;
${PALETTE_GLSL}
void main() {
  vec2 uv = (gl_FragCoord.xy - 0.5 * u_resolution) / u_resolution.y;
  vec2 dc = u_centerDelta + uv * (2.0 * u_halfWidth);

  vec2 dz = vec2(0.0);
  float smoothIter = -1.0;
  int refLen = min(u_refLen, u_maxiter);
  for (int n = 0; n < ${MAX_ITER_CAP}; n++) {
    if (n >= refLen) break;
    vec2 Z = texelFetch(u_refOrbit, ivec2(n, 0), 0).rg;
    vec2 z = Z + dz;
    float mag2 = dot(z, z);
    if (mag2 > 4.0) {
      float logZn = log(mag2) * 0.5;
      float nu = log(logZn / log(2.0)) / log(2.0);
      smoothIter = float(n) + 1.0 - nu;
      break;
    }
    vec2 twoZdz = 2.0 * vec2(Z.x * dz.x - Z.y * dz.y, Z.x * dz.y + Z.y * dz.x);
    vec2 dz2 = vec2(dz.x * dz.x - dz.y * dz.y, 2.0 * dz.x * dz.y);
    dz = twoZdz + dz2 + dc;
  }

  // Ran out of reference orbit (it escaped, or hit u_refLen) without
  // this pixel escaping: same "no glitch correction" limitation as
  // the Python deepzoom module -- render as inside rather than guess.
  if (smoothIter < 0.0) {
    outColor = vec4(0.0, 0.0, 0.0, 1.0);
  } else {
    float t = sqrt(smoothIter) * 0.15;
    outColor = vec4(palette(t, u_palette), 1.0);
  }
}
`;

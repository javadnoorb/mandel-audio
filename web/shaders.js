// GLSL sources for the Mandelbrot renderer.
//
// The viewport math mirrors mandel_audio.fractal.mandelbrot_set on the
// Python side: `scale` is a log2 zoom factor (each +1 halves the
// viewport width), and the unscaled full-view half-width is 1.25
// (matching Python's unscaled_width=2.5 default).

export const VERTEX_SRC = `#version 300 es
in vec2 a_position;
void main() {
  gl_Position = vec4(a_position, 0.0, 1.0);
}
`;

// The iteration loop bound must be a compile-time constant in GLSL ES;
// we cap it generously and break out early via u_maxiter.
export const MAX_ITER_CAP = 4000;

export const FRAGMENT_SRC = `#version 300 es
precision highp float;

uniform vec2 u_resolution;
uniform vec2 u_center;
uniform float u_scale;
uniform int u_maxiter;
uniform int u_palette;

out vec4 outColor;

// Cosine-based palettes, see Inigo Quilez:
// https://iquilezles.org/articles/palettes/
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

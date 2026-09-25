// Sonify a Mandelbrot orbit in the browser via the Web Audio API.
//
// Mirrors mandel_audio.audio.orbit_to_audio on the Python side: the
// orbit of c under z -> z^2 + c is resampled up to audio length, with
// the real part on the left channel and imaginary part on the right.

export function computeOrbit(cr, ci, maxiter) {
  const real = new Float64Array(maxiter);
  const imag = new Float64Array(maxiter);
  let zr = 0, zi = 0;
  let count = maxiter;
  for (let n = 0; n < maxiter; n++) {
    real[n] = zr;
    imag[n] = zi;
    const zr2 = zr * zr;
    const zi2 = zi * zi;
    if (zr2 + zi2 > 4.0) {
      count = n + 1;
      break;
    }
    const nzr = zr2 - zi2 + cr;
    const nzi = 2 * zr * zi + ci;
    zr = nzr;
    zi = nzi;
  }
  return { real: real.subarray(0, count), imag: imag.subarray(0, count) };
}

function interp(srcIndex, origIndex, values) {
  // Linear interpolation, equivalent to numpy.interp for our monotonic
  // integer origIndex = 0..n-1 case.
  const n = values.length;
  const out = new Float32Array(srcIndex.length);
  for (let i = 0; i < srcIndex.length; i++) {
    const x = srcIndex[i];
    let lo = Math.floor(x);
    if (lo >= n - 1) {
      out[i] = values[n - 1];
      continue;
    }
    if (lo < 0) lo = 0;
    const frac = x - lo;
    out[i] = values[lo] * (1 - frac) + values[lo + 1] * frac;
  }
  return out;
}

export function orbitToAudioBuffer(audioCtx, x, y, { duration = 2.0, maxiter = 2000, fade = 0.02 } = {}) {
  const sr = audioCtx.sampleRate;
  let { real, imag } = computeOrbit(x, y, maxiter);
  let n = real.length;
  if (n < 2) {
    real = Float64Array.of(real[0], real[0]);
    imag = Float64Array.of(imag[0], imag[0]);
    n = 2;
  }

  const numSamples = Math.max(Math.floor(duration * sr), 2);
  const srcIndex = new Float32Array(numSamples);
  for (let i = 0; i < numSamples; i++) {
    srcIndex[i] = (i / (numSamples - 1)) * (n - 1);
  }
  const left = interp(srcIndex, null, real);
  const right = interp(srcIndex, null, imag);

  let peak = 0;
  for (let i = 0; i < numSamples; i++) {
    peak = Math.max(peak, Math.abs(left[i]), Math.abs(right[i]));
  }
  if (peak > 0) {
    const g = 0.9 / peak;
    for (let i = 0; i < numSamples; i++) {
      left[i] *= g;
      right[i] *= g;
    }
  }

  const fadeSamples = Math.floor(fade * sr);
  if (fadeSamples > 0 && numSamples > 2 * fadeSamples) {
    for (let i = 0; i < fadeSamples; i++) {
      const g = i / fadeSamples;
      left[i] *= g;
      right[i] *= g;
      left[numSamples - 1 - i] *= g;
      right[numSamples - 1 - i] *= g;
    }
  }

  const buffer = audioCtx.createBuffer(2, numSamples, sr);
  buffer.copyToChannel(left, 0);
  buffer.copyToChannel(right, 1);
  return buffer;
}

export function playOrbit(audioCtx, x, y, opts) {
  const buffer = orbitToAudioBuffer(audioCtx, x, y, opts);
  const source = audioCtx.createBufferSource();
  source.buffer = buffer;
  source.connect(audioCtx.destination);
  source.start();
  return source;
}

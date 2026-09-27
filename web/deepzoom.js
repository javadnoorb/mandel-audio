// Perturbation-theory deep zoom for the WebGL explorer, mirroring
// mandel_audio.deepzoom on the Python side but using double-double (dd)
// arithmetic (bignum.js) in place of mpmath, since there's no bignum
// library or build step here.
//
// One reference orbit is computed at high (dd) precision for a fixed
// point c_ref. Every pixel then only tracks a small delta dz from that
// orbit (dz_{n+1} = 2*Z_n*dz_n + dz_n^2 + dc), which stays within
// float32 range even when the absolute viewport is far too small for
// float32 (or even float64) to address directly -- see shaders.js for
// the fragment-shader side of this recurrence.
//
// Known limitation (same as the Python version): no "glitch
// correction" for pixels whose true orbit diverges too far from the
// reference. Picking a reference near the view center (the default)
// keeps this manageable for interactive use.

import { ddAdd, ddcSquare, ddFromNumber, ddToNumber } from "./bignum.js";

export const MAX_REF_ITER = 4000; // must match shaders.js MAX_ITER_CAP

// Double-double arithmetic carries ~31-32 decimal digits; leave margin
// for the per-pixel float32 delta math on top of that.
export const DEEP_MAX_SCALE = 90;

// cRe/cIm are dd values ([hi, lo]), not plain numbers -- callers that
// already hold a dd-precision view center (e.g. re-baselining deep
// into a zoom session) must pass it through directly rather than
// round-tripping via a plain float64, or the whole point of dd
// arithmetic is lost at the call boundary.
export function referenceOrbit(cRe, cIm, maxiter) {
  maxiter = Math.min(maxiter, MAX_REF_ITER);
  const c = { re: cRe, im: cIm };
  let z = { re: ddFromNumber(0), im: ddFromNumber(0) };
  const real = new Float32Array(maxiter);
  const imag = new Float32Array(maxiter);
  let count = maxiter;
  let escaped = false;
  for (let n = 0; n < maxiter; n++) {
    const zr = ddToNumber(z.re);
    const zi = ddToNumber(z.im);
    real[n] = zr;
    imag[n] = zi;
    if (zr * zr + zi * zi > 4.0) {
      escaped = true;
      count = n + 1;
      break;
    }
    const z2 = ddcSquare(z);
    z = { re: ddAdd(z2.re, c.re), im: ddAdd(z2.im, c.im) };
  }
  return { real: real.subarray(0, count), imag: imag.subarray(0, count), escaped, count };
}

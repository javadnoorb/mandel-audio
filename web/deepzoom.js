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
// reference. findGoodReference (below) mitigates the common case --
// an unlucky view center that happens to escape early -- by sampling
// nearby candidates, but a genuinely bad neighborhood (e.g. deep in
// open exterior, far from any boundary) still degrades gracefully via
// the "reference escaped early" warning rather than being corrected.

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

// Small ring of candidate offsets (as fractions of searchRadius) tried
// around the requested center when it escapes early. Every pixel's
// iteration budget in the deep-zoom shader is capped by however long
// the *reference* orbit itself survives (see DEEP_FRAGMENT_SRC), so a
// reference that escapes well before maxiter silently truncates detail
// for the entire view, not just pixels far from it -- an unlucky view
// center (e.g. just outside the set) otherwise degrades the whole
// render, not only itself.
const CANDIDATE_OFFSETS = [
  [1, 0], [-1, 0], [0, 1], [0, -1],
  [0.7, 0.7], [-0.7, 0.7], [0.7, -0.7], [-0.7, -0.7],
];

// Below this fraction of maxiter, a reference is considered "genuinely
// bad" and worth searching around. Above it, the center is used as-is
// even though it technically escaped -- see findGoodReference.
const GOOD_ENOUGH_FRACTION = 0.5;

// Picks a reference point near (centerRe, centerIm) whose orbit survives
// as long as possible (ideally the full maxiter), searching a small ring
// of nearby candidates when the center itself escapes early. Returns
// { re, im, orbit } -- re/im are dd values, possibly different from the
// input if a nearby candidate did better.
//
// Deliberately conservative about switching away from the center: almost
// every point near the Mandelbrot boundary escapes *eventually* (even a
// perfectly fine one might just escape very late, close to maxiter), so
// treating "escaped at all" as the trigger for searching meant nearly
// every rebase searched, and "whichever candidate has the highest count"
// could jump to a wildly different nearby point for a marginal gain --
// causing visibly discontinuous jumps (color/black-region flicker)
// between rebases during otherwise-smooth continuous zooming, even
// though each individual frame looked reasonable in isolation. Only
// searching when the center falls below a real quality bar keeps most
// rebases using the center directly (deterministic, continuous), and
// only accepts a candidate that's clearly better, not just numerically
// higher, when a search does happen.
export function findGoodReference(centerRe, centerIm, maxiter, searchRadius) {
  let bestRe = centerRe;
  let bestIm = centerIm;
  let best = referenceOrbit(centerRe, centerIm, maxiter);
  const goodEnough = maxiter * GOOD_ENOUGH_FRACTION;
  if (!best.escaped || best.count >= goodEnough) return { re: bestRe, im: bestIm, orbit: best };

  for (const [dx, dy] of CANDIDATE_OFFSETS) {
    const candRe = ddAdd(centerRe, ddFromNumber(dx * searchRadius));
    const candIm = ddAdd(centerIm, ddFromNumber(dy * searchRadius));
    const orbit = referenceOrbit(candRe, candIm, maxiter);
    if (!orbit.escaped || orbit.count > best.count) {
      bestRe = candRe;
      bestIm = candIm;
      best = orbit;
      if (!best.escaped || best.count >= goodEnough) break; // good enough, stop searching
    }
  }
  return { re: bestRe, im: bestIm, orbit: best };
}

// Minimal double-double (dd) arithmetic: pairs of float64 [hi, lo] that
// together carry ~106 bits (~31-32 decimal digits) of precision, using
// only plain IEEE754 double operations (Dekker/Knuth's algorithms). No
// external dependency, unlike mandel_audio.deepzoom's use of mpmath.
//
// This isn't arbitrary precision -- it tops out around 31-32 decimal
// digits -- but that's enough to push the web explorer's zoom far past
// its float64 (view-center bookkeeping) and float32 (GPU shader) walls,
// without a bignum library or build step.
//
// A dd value is represented as a 2-element array [hi, lo] where the
// true value is hi + lo and |lo| <= ulp(hi)/2.

const SPLITTER = 134217729; // 2^27 + 1, splits a double's 53-bit mantissa in half

function split(a) {
  const t = SPLITTER * a;
  const hi = t - (t - a);
  const lo = a - hi;
  return [hi, lo];
}

// Error-free transformation of a+b: s is the rounded sum, e the exact
// rounding error, so a+b === s+e exactly (Knuth's two-sum).
function twoSum(a, b) {
  const s = a + b;
  const bb = s - a;
  const err = (a - (s - bb)) + (b - bb);
  return [s, err];
}

// Cheaper two-sum, valid only when |a| >= |b|.
function quickTwoSum(a, b) {
  const s = a + b;
  const err = b - (s - a);
  return [s, err];
}

// Error-free transformation of a*b (Dekker's two-prod, via splitting).
function twoProd(a, b) {
  const p = a * b;
  const [ahi, alo] = split(a);
  const [bhi, blo] = split(b);
  const err = ((ahi * bhi - p) + ahi * blo + alo * bhi) + alo * blo;
  return [p, err];
}

export function ddFromNumber(x) {
  return [x, 0];
}

export function ddToNumber(a) {
  return a[0] + a[1];
}

export function ddAdd(a, b) {
  let [s, e] = twoSum(a[0], b[0]);
  e += a[1] + b[1];
  return quickTwoSum(s, e);
}

export function ddSub(a, b) {
  return ddAdd(a, [-b[0], -b[1]]);
}

export function ddMul(a, b) {
  let [p, e] = twoProd(a[0], b[0]);
  e += a[0] * b[1] + a[1] * b[0];
  return quickTwoSum(p, e);
}

// dd complex number: { re: dd, im: dd }
export function ddcAdd(a, b) {
  return { re: ddAdd(a.re, b.re), im: ddAdd(a.im, b.im) };
}

export function ddcSub(a, b) {
  return { re: ddSub(a.re, b.re), im: ddSub(a.im, b.im) };
}

export function ddcSquare(z) {
  // (re + i*im)^2 = (re^2 - im^2) + i*(2*re*im)
  const re2 = ddMul(z.re, z.re);
  const im2 = ddMul(z.im, z.im);
  const reim = ddMul(z.re, z.im);
  return { re: ddSub(re2, im2), im: ddAdd(reim, reim) };
}

export function ddcFromNumbers(re, im) {
  return { re: ddFromNumber(re), im: ddFromNumber(im) };
}

export function ddcToNumbers(z) {
  return [ddToNumber(z.re), ddToNumber(z.im)];
}

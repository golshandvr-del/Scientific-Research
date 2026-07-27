// ============================================================================
// indicators/bank/statistical.ts — دستهٔ آماری/فراکتالی (Statistical / Fractal)
// ----------------------------------------------------------------------------
// منابع: EN/deep-web (ریاضی‌محورِ کمیاب). شاملِ FRAMA (میانگینِ فراکتالِ اِهلرز که
// دستهٔ trend دارد ولی منطقش فراکتالی است). همه بدونِ look-ahead و active:false.
// ============================================================================

import { makeKit, closes, highs, lows, NaNArr, asSeries, highest, lowest } from './kit'

const K = makeKit()
const { def } = K

// Rolling Skewness
def('skew', 'statistical', 'EN', { period: 20 }, ['period'], 'چولگیِ غلتان', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) {
    let m = 0; for (let k = 0; k < p.period; k++) m += x[i - k]; m /= p.period
    let s2 = 0, s3 = 0
    for (let k = 0; k < p.period; k++) { const d = x[i - k] - m; s2 += d * d; s3 += d * d * d }
    const sd = Math.sqrt(s2 / p.period)
    out[i] = sd ? (s3 / p.period) / (sd * sd * sd) : 0
  }
  return asSeries(out)
})

// Rolling Kurtosis (excess)
def('kurt', 'statistical', 'EN', { period: 20 }, ['period'], 'کشیدگیِ غلتان (excess)', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) {
    let m = 0; for (let k = 0; k < p.period; k++) m += x[i - k]; m /= p.period
    let s2 = 0, s4 = 0
    for (let k = 0; k < p.period; k++) { const d = x[i - k] - m; s2 += d * d; s4 += d * d * d * d }
    const v = s2 / p.period
    out[i] = v ? (s4 / p.period) / (v * v) - 3 : 0
  }
  return asSeries(out)
})

// Rolling Pearson correlation (price vs time) — قدرتِ روندِ خطی
def('corr_t', 'statistical', 'EN', { period: 20 }, ['period'], 'همبستگیِ قیمت با زمان', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) {
    let sx = 0, sy = 0, sxy = 0, sxx = 0, syy = 0
    for (let k = 0; k < p.period; k++) { const t = k, y = x[i - (p.period - 1 - k)]; sx += t; sy += y; sxy += t * y; sxx += t * t; syy += y * y }
    const num = p.period * sxy - sx * sy
    const den = Math.sqrt((p.period * sxx - sx * sx) * (p.period * syy - sy * sy))
    out[i] = den ? num / den : 0
  }
  return asSeries(out)
})

// R² of linear regression (goodness of trend fit)
def('r2', 'statistical', 'EN', { period: 20 }, ['period'], 'ضریبِ تعیینِ رگرسیون (R²)', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) {
    let sx = 0, sy = 0, sxy = 0, sxx = 0, syy = 0
    for (let k = 0; k < p.period; k++) { const t = k, y = x[i - (p.period - 1 - k)]; sx += t; sy += y; sxy += t * y; sxx += t * t; syy += y * y }
    const num = p.period * sxy - sx * sy
    const den = (p.period * sxx - sx * sx) * (p.period * syy - sy * sy)
    const r = den ? num / Math.sqrt(den) : 0
    out[i] = r * r
  }
  return asSeries(out)
})

// Hurst Exponent (rescaled range R/S) — پایداری/برگشت‌به‌میانگین
def('hurst', 'statistical', 'deep-web', { period: 64 }, ['period'], 'نمای هرست (R/S)', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  const ret = NaNArr(n); for (let i = 1; i < n; i++) ret[i] = x[i - 1] ? Math.log(x[i] / x[i - 1]) : 0
  for (let i = p.period; i < n; i++) {
    const w: number[] = []; for (let k = 0; k < p.period; k++) w.push(ret[i - k] || 0)
    const m = w.reduce((a, b) => a + b, 0) / p.period
    let cum = 0, mn = Infinity, mx = -Infinity, s2 = 0
    for (let k = 0; k < p.period; k++) { cum += w[k] - m; if (cum < mn) mn = cum; if (cum > mx) mx = cum; s2 += (w[k] - m) * (w[k] - m) }
    const sd = Math.sqrt(s2 / p.period), R = mx - mn
    out[i] = (sd && R > 0) ? Math.log(R / sd) / Math.log(p.period) : 0.5
  }
  return asSeries(out)
})

// Shannon Entropy of returns (بی‌نظمیِ بازار)
def('entropy', 'statistical', 'deep-web', { period: 20, bins: 8 }, ['period', 'bins'], 'آنتروپیِ شانونِ بازده', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  const ret = NaNArr(n); for (let i = 1; i < n; i++) ret[i] = x[i - 1] ? (x[i] - x[i - 1]) / x[i - 1] : 0
  for (let i = p.period; i < n; i++) {
    const w: number[] = []; for (let k = 0; k < p.period; k++) w.push(ret[i - k] || 0)
    const mn = Math.min(...w), mx = Math.max(...w), rng = mx - mn || 1e-10
    const hist = new Array(p.bins).fill(0)
    for (const v of w) { const b = Math.min(p.bins - 1, Math.floor(((v - mn) / rng) * p.bins)); hist[b]++ }
    let h = 0; for (const cnt of hist) { if (cnt) { const pr = cnt / p.period; h -= pr * Math.log2(pr) } }
    out[i] = h
  }
  return asSeries(out)
})

// FRAMA — Fractal Adaptive MA (Ehlers) — دستهٔ trend، منطقِ فراکتالی
def('frama', 'trend', 'deep-web', { period: 16 }, ['period'], 'میانگینِ تطبیقیِ فراکتالِ اِهلرز', (c, p) => {
  const h = highs(c), l = lows(c), x = closes(c), n = x.length, out = NaNArr(n)
  const per = p.period % 2 === 0 ? p.period : p.period + 1, half = per / 2
  let prev = NaN
  for (let i = 0; i < n; i++) {
    if (i < per) { out[i] = x[i]; prev = x[i]; continue }
    const n1 = (highest(h, i - half, half) - lowest(l, i - half, half)) / half
    const n2 = (highest(h, i, half) - lowest(l, i, half)) / half
    const n3 = (highest(h, i, per) - lowest(l, i, per)) / per
    let D = 1
    if (n1 > 0 && n2 > 0 && n3 > 0) D = (Math.log(n1 + n2) - Math.log(n3)) / Math.log(2)
    const a = Math.exp(-4.6 * (D - 1)); const alpha = Math.max(0.01, Math.min(1, a))
    prev = Number.isFinite(prev) ? alpha * x[i] + (1 - alpha) * prev : x[i]
    out[i] = prev
  }
  return asSeries(out)
})

// FDI — Fractal Dimension Index
def('fdi', 'statistical', 'deep-web', { period: 30 }, ['period'], 'شاخصِ بُعدِ فراکتال', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) {
    const hh = highest(x, i, p.period), ll = lowest(x, i, p.period), rng = hh - ll || 1e-10
    let L = 0
    for (let k = 1; k < p.period; k++) {
      const d1 = (x[i - k + 1] - x[i - k]) / rng
      L += Math.sqrt(d1 * d1 + 1 / (p.period * p.period))
    }
    out[i] = 1 + (Math.log(L) + Math.log(2)) / Math.log(2 * p.period)
  }
  return asSeries(out)
})

export const STATISTICAL_ITEMS = K.items

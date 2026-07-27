// ============================================================================
// indicators/bank/volatility.ts — دستهٔ نوسان و حجم (Volatility + Volume)
// ----------------------------------------------------------------------------
// منابع: EN/deep-web/CN. اندیکاتورهای حجمی از volume (tick-volume) به‌عنوان پروکسیِ
// XAU استفاده می‌کنند. همه بدونِ look-ahead و active:false.
// ============================================================================

import { makeKit, closes, highs, lows, emaArr, smaArr, rmaArr, stdArr, NaNArr, asSeries, highest, lowest, trArr, vols } from './kit'

const K = makeKit()
const { def } = K

// ---- Volatility -----------------------------------------------------------
// NATR — Normalized ATR (%)
def('natr', 'volatility', 'EN', { period: 14 }, ['period'], 'ATR نرمال‌شده (درصد)', (c, p) => {
  const x = closes(c), a = rmaArr(trArr(c), p.period)
  return asSeries(a.map((v, i) => (x[i] ? (100 * v) / x[i] : NaN)))
})

// RVI — Relative Volatility Index (RSI روی std)
def('rvi_vol', 'volatility', 'deep-web', { period: 14 }, ['period'], 'شاخصِ نوسانِ نسبی', (c, p) => {
  const x = closes(c), n = x.length, sd = stdArr(x, p.period)
  const up = NaNArr(n), dn = NaNArr(n)
  for (let i = 1; i < n; i++) { if (x[i] > x[i - 1]) { up[i] = sd[i]; dn[i] = 0 } else { up[i] = 0; dn[i] = sd[i] } }
  const eu = emaArr(up, p.period), ed = emaArr(dn, p.period)
  return asSeries(eu.map((v, i) => ((v + ed[i]) ? (100 * v) / (v + ed[i]) : NaN)))
})

// Ulcer Index — عمقِ افتِ نرمال‌شده
def('ulcer', 'volatility', 'EN', { period: 14 }, ['period'], 'شاخصِ زخم (عمقِ افت)', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) {
    let s = 0
    for (let k = 0; k < p.period; k++) {
      const hh = highest(x, i, p.period)
      const dd = hh ? (100 * (x[i - k] - hh)) / hh : 0
      s += dd * dd
    }
    out[i] = Math.sqrt(s / p.period)
  }
  return asSeries(out)
})

// Choppiness Index — روند در برابرِ رنج
def('chop', 'volatility', 'EN', { period: 14 }, ['period'], 'شاخصِ چاپینس (روند/رنج)', (c, p) => {
  const n = c.length, tr = trArr(c), h = highs(c), l = lows(c), out = NaNArr(n)
  for (let i = p.period; i < n; i++) {
    let sumTr = 0
    for (let k = 0; k < p.period; k++) sumTr += tr[i - k] || 0
    const hh = highest(h, i, p.period), ll = lowest(l, i, p.period)
    const rng = hh - ll
    out[i] = rng > 0 ? (100 * Math.log10(sumTr / rng)) / Math.log10(p.period) : NaN
  }
  return asSeries(out)
})

// Mass Index — 梅斯线
def('mass', 'volatility', 'CN', { ema: 9, sum: 25 }, ['ema', 'sum'], 'شاخصِ مِیس (梅斯线)', (c, p) => {
  const n = c.length, rng = c.map(k => k.high - k.low)
  const e1 = emaArr(rng, p.ema), e2 = emaArr(e1, p.ema)
  const ratio = e1.map((v, i) => (e2[i] ? v / e2[i] : NaN)), out = NaNArr(n)
  for (let i = p.sum - 1; i < n; i++) { let s = 0, ok = true; for (let k = 0; k < p.sum; k++) { if (!Number.isFinite(ratio[i - k])) { ok = false; break } s += ratio[i - k] } if (ok) out[i] = s }
  return asSeries(out)
})

// ATR-percentile — رتبهٔ درصدیِ ATR (رژیمِ نوسان)
def('atr_pct', 'volatility', 'composite', { period: 14, lookback: 100 }, ['period', 'lookback'], 'صدکِ ATR (رژیمِ نوسان)', (c, p) => {
  const a = rmaArr(trArr(c), p.period), n = a.length, out = NaNArr(n)
  for (let i = p.lookback; i < n; i++) {
    if (!Number.isFinite(a[i])) continue
    let below = 0, cnt = 0
    for (let k = 0; k < p.lookback; k++) { const v = a[i - k]; if (Number.isFinite(v)) { cnt++; if (v <= a[i]) below++ } }
    out[i] = cnt ? (100 * below) / cnt : NaN
  }
  return asSeries(out)
})

// ---- Volume (tick-volume proxy برای XAU) ----------------------------------
// OBV — On-Balance Volume
def('obv', 'volume', 'EN', {}, [], 'حجمِ تعادلی (proxy تیک برای XAU)', (c) => {
  const x = closes(c), v = vols(c), n = x.length, out = NaNArr(n)
  let acc = 0; out[0] = 0
  for (let i = 1; i < n; i++) { acc += x[i] > x[i - 1] ? v[i] : x[i] < x[i - 1] ? -v[i] : 0; out[i] = acc }
  return asSeries(out)
})

// AD — Accumulation/Distribution Line (Chaikin)
def('ad', 'volume', 'EN', {}, [], 'خطِ انباشت/توزیع (proxy تیک)', (c) => {
  const n = c.length, out = NaNArr(n)
  let acc = 0
  for (let i = 0; i < n; i++) {
    const rng = c[i].high - c[i].low
    const mfm = rng ? ((c[i].close - c[i].low) - (c[i].high - c[i].close)) / rng : 0
    acc += mfm * c[i].volume; out[i] = acc
  }
  return asSeries(out)
})

// ADOSC — Chaikin A/D Oscillator
def('adosc', 'volume', 'EN', { fast: 3, slow: 10 }, ['fast', 'slow'], 'اسیلاتورِ A/D چایکین', (c, p) => {
  const n = c.length, adl = NaNArr(n); let acc = 0
  for (let i = 0; i < n; i++) { const rng = c[i].high - c[i].low; const mfm = rng ? ((c[i].close - c[i].low) - (c[i].high - c[i].close)) / rng : 0; acc += mfm * c[i].volume; adl[i] = acc }
  const f = emaArr(adl, p.fast), s = emaArr(adl, p.slow)
  return asSeries(f.map((v, i) => v - s[i]))
})

// EFI — Elder Force Index
def('efi', 'volume', 'EN', { period: 13 }, ['period'], 'شاخصِ نیروی الدر', (c, p) => {
  const x = closes(c), v = vols(c), n = x.length, raw = NaNArr(n)
  for (let i = 1; i < n; i++) raw[i] = (x[i] - x[i - 1]) * v[i]
  return asSeries(emaArr(raw, p.period))
})

// MFI — Money Flow Index (RSI حجمی)
def('mfi', 'volume', 'EN', { period: 14 }, ['period'], 'شاخصِ جریانِ پول (proxy تیک)', (c, p) => {
  const n = c.length, tp = c.map(k => (k.high + k.low + k.close) / 3), out = NaNArr(n)
  for (let i = p.period; i < n; i++) {
    let pos = 0, neg = 0
    for (let k = 0; k < p.period; k++) {
      const mf = tp[i - k] * c[i - k].volume
      if (tp[i - k] > tp[i - k - 1]) pos += mf; else if (tp[i - k] < tp[i - k - 1]) neg += mf
    }
    out[i] = neg === 0 ? 100 : (100 - 100 / (1 + pos / neg))
  }
  return asSeries(out)
})

// WVAD — 威廉变异离散量
def('wvad', 'volume', 'CN', { period: 24 }, ['period'], 'واریانسِ پخشِ ویلیامز (威廉变异离散量)', (c, p) => {
  const n = c.length, raw = NaNArr(n)
  for (let i = 0; i < n; i++) { const rng = c[i].high - c[i].low; raw[i] = rng ? ((c[i].close - c[i].open) / rng) * c[i].volume : 0 }
  return asSeries(smaArr(raw, p.period))
})

// VPT — 量价曲线 Volume-Price Trend
def('vpt', 'volume', 'CN', {}, [], 'روندِ حجم-قیمت (量价曲线)', (c) => {
  const x = closes(c), v = vols(c), n = x.length, out = NaNArr(n)
  let acc = 0; out[0] = 0
  for (let i = 1; i < n; i++) { acc += x[i - 1] ? v[i] * ((x[i] - x[i - 1]) / x[i - 1]) : 0; out[i] = acc }
  return asSeries(out)
})

// EMV — Ease of Movement (Arms)
def('emv', 'volume', 'EN', { period: 14 }, ['period'], 'سهولتِ حرکت (آرمز)', (c, p) => {
  const n = c.length, raw = NaNArr(n)
  for (let i = 1; i < n; i++) {
    const mid = (c[i].high + c[i].low) / 2 - (c[i - 1].high + c[i - 1].low) / 2
    const rng = c[i].high - c[i].low
    const boxRatio = (c[i].volume && rng) ? (c[i].volume / 1e6) / rng : 0
    raw[i] = boxRatio ? mid / boxRatio : 0
  }
  return asSeries(smaArr(raw, p.period))
})

export const VOLATILITY_ITEMS = K.items

// ============================================================================
// indicators/bank/trend.ts — دستهٔ روند/میانگین‌های متحرکِ پیشرفته (Overlap)
// ----------------------------------------------------------------------------
// منابع: EN/deep-web (pandas-ta, TA-Lib, Tillson, Kaufman, Hull, Arnaud Legoux).
// همه بدونِ look-ahead و active:false. مصرف‌کننده: کاوشگرِ P8 و لایه‌های استراتژی.
// ============================================================================

import { makeKit, closes, emaArr, rmaArr, wmaArr, smaArr, NaNArr, asSeries } from './kit'

const K = makeKit()
const { def } = K

// DEMA — Double EMA = 2·EMA − EMA(EMA)
def('dema', 'trend', 'EN', { period: 20 }, ['period'], 'میانگینِ متحرکِ نماییِ دوگانه', (c, p) => {
  const e1 = emaArr(closes(c), p.period), e2 = emaArr(e1, p.period)
  return asSeries(e1.map((v, i) => 2 * v - e2[i]))
})

// TEMA — Triple EMA = 3·EMA − 3·EMA² + EMA³
def('tema', 'trend', 'EN', { period: 20 }, ['period'], 'میانگینِ متحرکِ نماییِ سه‌گانه', (c, p) => {
  const e1 = emaArr(closes(c), p.period), e2 = emaArr(e1, p.period), e3 = emaArr(e2, p.period)
  return asSeries(e1.map((v, i) => 3 * v - 3 * e2[i] + e3[i]))
})

// ZLEMA — Zero-Lag EMA (de-lag با پیش‌بینیِ خطی روی داده گذشته)
def('zlema', 'trend', 'EN', { period: 20 }, ['period'], 'EMA بدونِ تأخیر (Zero-Lag)', (c, p) => {
  const x = closes(c), lag = Math.floor((p.period - 1) / 2)
  const dl = x.map((v, i) => (i - lag >= 0 ? 2 * v - x[i - lag] : NaN))
  return asSeries(emaArr(dl, p.period))
})

// HMA — Hull MA = WMA(2·WMA(p/2) − WMA(p), sqrt(p))
def('hma', 'trend', 'EN', { period: 21 }, ['period'], 'میانگینِ متحرکِ هال', (c, p) => {
  const x = closes(c)
  const half = wmaArr(x, Math.max(1, Math.floor(p.period / 2)))
  const full = wmaArr(x, p.period)
  const diff = half.map((v, i) => 2 * v - full[i])
  return asSeries(wmaArr(diff, Math.max(1, Math.floor(Math.sqrt(p.period)))))
})

// RMA / WWMA — Wilder MA
def('rma', 'trend', 'EN', { period: 14 }, ['period'], 'میانگینِ متحرکِ وایلدر (RMA)', (c, p) =>
  asSeries(rmaArr(closes(c), p.period)))

// WMA — Weighted MA
def('wma', 'trend', 'EN', { period: 20 }, ['period'], 'میانگینِ متحرکِ وزنی', (c, p) =>
  asSeries(wmaArr(closes(c), p.period)))

// TRIMA — Triangular MA = SMA(SMA)
def('trima', 'trend', 'EN', { period: 20 }, ['period'], 'میانگینِ متحرکِ مثلثی', (c, p) => {
  const h = Math.ceil((p.period + 1) / 2)
  return asSeries(smaArr(smaArr(closes(c), h), Math.floor(p.period / 2) + 1))
})

// T3 — Tillson T3 (شش‌بار EMA با ضریبِ حجم)
def('t3', 'trend', 'EN', { period: 20, vfactor: 0.7 }, ['period', 'vfactor'], 'میانگینِ T3 تیلسون', (c, p) => {
  const b = p.vfactor, c1 = -b * b * b, c2 = 3 * b * b + 3 * b * b * b, c3 = -6 * b * b - 3 * b - 3 * b * b * b, c4 = 1 + 3 * b + b * b * b + 3 * b * b
  const e1 = emaArr(closes(c), p.period), e2 = emaArr(e1, p.period), e3 = emaArr(e2, p.period)
  const e4 = emaArr(e3, p.period), e5 = emaArr(e4, p.period), e6 = emaArr(e5, p.period)
  return asSeries(e6.map((v, i) => c1 * v + c2 * e5[i] + c3 * e4[i] + c4 * e3[i]))
})

// KAMA — Kaufman Adaptive MA
def('kama', 'trend', 'EN', { period: 10, fast: 2, slow: 30 }, ['period', 'fast', 'slow'], 'میانگینِ تطبیقیِ کافمن', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  const fastSC = 2 / (p.fast + 1), slowSC = 2 / (p.slow + 1)
  let prev = NaN
  for (let i = 0; i < n; i++) {
    if (i < p.period) { out[i] = NaN; continue }
    const change = Math.abs(x[i] - x[i - p.period])
    let vol = 0
    for (let k = 0; k < p.period; k++) vol += Math.abs(x[i - k] - x[i - k - 1])
    const er = vol === 0 ? 0 : change / vol
    const sc = Math.pow(er * (fastSC - slowSC) + slowSC, 2)
    prev = Number.isFinite(prev) ? prev + sc * (x[i] - prev) : x[i]
    out[i] = prev
  }
  return asSeries(out)
})

// VIDYA — Chande Variable Index Dynamic Average (CMO-محور)
def('vidya', 'trend', 'CN', { period: 14, cmoPeriod: 9 }, ['period', 'cmoPeriod'], 'میانگینِ پویا با شاخصِ متغیر (چاند)', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  const a = 2 / (p.period + 1)
  let prev = NaN
  for (let i = 0; i < n; i++) {
    if (i < p.cmoPeriod) continue
    let up = 0, dn = 0
    for (let k = 0; k < p.cmoPeriod; k++) {
      const d = x[i - k] - x[i - k - 1]
      if (d > 0) up += d; else dn -= d
    }
    const cmo = (up + dn) === 0 ? 0 : Math.abs((up - dn) / (up + dn))
    prev = Number.isFinite(prev) ? a * cmo * x[i] + (1 - a * cmo) * prev : x[i]
    out[i] = prev
  }
  return asSeries(out)
})

// McGinley Dynamic
def('mcgd', 'trend', 'EN', { period: 14 }, ['period'], 'مک‌گینلی داینامیک', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  let prev = NaN
  for (let i = 0; i < n; i++) {
    if (!Number.isFinite(prev)) { prev = x[i]; out[i] = prev; continue }
    const r = x[i] / prev
    prev = prev + (x[i] - prev) / (p.period * Math.pow(r, 4))
    out[i] = prev
  }
  return asSeries(out)
})

// ALMA — Arnaud Legoux MA
def('alma', 'trend', 'EN', { period: 21, offset: 0.85, sigma: 6 }, ['period', 'offset', 'sigma'], 'میانگینِ آرنو لگو', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  const m = p.offset * (p.period - 1), s = p.period / p.sigma
  const w: number[] = []; let wsum = 0
  for (let k = 0; k < p.period; k++) { const ww = Math.exp(-((k - m) * (k - m)) / (2 * s * s)); w.push(ww); wsum += ww }
  for (let i = p.period - 1; i < n; i++) {
    let acc = 0
    for (let k = 0; k < p.period; k++) acc += x[i - (p.period - 1 - k)] * w[k]
    out[i] = acc / wsum
  }
  return asSeries(out)
})

// FWMA — Fibonacci Weighted MA
def('fwma', 'trend', 'EN', { period: 10 }, ['period'], 'میانگینِ وزنیِ فیبوناچی', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  const fib: number[] = [1, 1]; for (let k = 2; k < p.period; k++) fib.push(fib[k - 1] + fib[k - 2])
  const wsum = fib.reduce((a, b) => a + b, 0)
  for (let i = p.period - 1; i < n; i++) {
    let acc = 0
    for (let k = 0; k < p.period; k++) acc += x[i - (p.period - 1 - k)] * fib[k]
    out[i] = acc / wsum
  }
  return asSeries(out)
})

// SINWMA — Sine Weighted MA
def('sinwma', 'trend', 'EN', { period: 14 }, ['period'], 'میانگینِ وزنیِ سینوسی', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  const w: number[] = []; let wsum = 0
  for (let k = 1; k <= p.period; k++) { const ww = Math.sin((k * Math.PI) / (p.period + 1)); w.push(ww); wsum += ww }
  for (let i = p.period - 1; i < n; i++) {
    let acc = 0
    for (let k = 0; k < p.period; k++) acc += x[i - (p.period - 1 - k)] * w[k]
    out[i] = acc / wsum
  }
  return asSeries(out)
})

// DMA — 平均差 = SMA(fast) − SMA(slow)  [CN، دستهٔ trend]
def('dma', 'trend', 'CN', { fast: 10, slow: 50 }, ['fast', 'slow'], 'تفاضلِ میانگین‌ها (平均差)', (c, p) => {
  const x = closes(c), f = smaArr(x, p.fast), s = smaArr(x, p.slow)
  return asSeries(f.map((v, i) => v - s[i]))
})

// BBI — 多空均线 = میانگینِ SMA(3,6,12,24)  [CN، دستهٔ trend]
def('bbi', 'trend', 'CN', { p1: 3, p2: 6, p3: 12, p4: 24 }, ['p1', 'p2', 'p3', 'p4'], 'خطِ چندنرخیِ گاو-خرس (多空均线)', (c, p) => {
  const x = closes(c)
  const a = smaArr(x, p.p1), b = smaArr(x, p.p2), d = smaArr(x, p.p3), e = smaArr(x, p.p4)
  return asSeries(x.map((_, i) => (a[i] + b[i] + d[i] + e[i]) / 4))
})

export const TREND_ITEMS = K.items

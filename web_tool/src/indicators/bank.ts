// ============================================================================
// indicators/bank.ts — بانکِ گستردهٔ اندیکاتورها (User Note: ۴۰۰+ اندیکاتورِ پیچیده)
// ----------------------------------------------------------------------------
// این فایل مجموعهٔ بزرگی از اندیکاتورهای کمیاب/پیچیده را (که در docs/indicator.md
// طیِ جستجوی EN/RU/CN/deep-web کاتالوگ شد) به‌صورتِ IndicatorDef پیاده و صادر می‌کند.
//
// قوانینِ حاکم (طبقِ User Note و معماریِ ROS2-مانندِ پروژه):
//   1) همهٔ توابع *بدونِ look-ahead*اند: فقط از دادهٔ تا اندیسِ i استفاده می‌کنند.
//   2) همهٔ ورودی‌ها با `active:false` ثبت می‌شوند — در بانک «وجود» دارند اما تا وقتی
//      یک لایهٔ استراتژی صریحاً صدایشان نزند، محاسبه/فعال نمی‌شوند (کشِ تنبلِ رجیستری).
//   3) additive/Strangler-Fig: مسیرِ /api/decision و برابریِ بیت‌به‌بیتِ snapshotِ طلایی
//      دست‌نخورده می‌ماند؛ این فایل هیچ رفتارِ تصمیمِ موجودی را تغییر نمی‌دهد.
//   4) XAU حجمِ واقعی ندارد ⇒ اندیکاتورهای حجمی از `volume` (tick-volume) به‌عنوان پروکسی
//      استفاده می‌کنند؛ اگر volume صفر باشد خروجی NaN می‌شود (بی‌اثر، نه گمراه‌کننده).
// ============================================================================

import type { Candle } from '../indicators'
import * as I from '../indicators'
import type { IndicatorDef, IndicatorValue } from './contracts'

// ---------------------------------------------------------------------------
// کمک‌توابعِ پایه (بدونِ look-ahead)
// ---------------------------------------------------------------------------
const NaNArr = (n: number) => new Array<number>(n).fill(NaN)

const closes = (c: Candle[]) => c.map(k => k.close)
const highs = (c: Candle[]) => c.map(k => k.high)
const lows = (c: Candle[]) => c.map(k => k.low)
const opens = (c: Candle[]) => c.map(k => k.open)
const vols = (c: Candle[]) => c.map(k => k.volume)

/** میانگینِ متحرکِ ساده روی یک آرایهٔ دلخواه. */
function smaArr(x: number[], p: number): number[] {
  const out = NaNArr(x.length)
  let sum = 0, cnt = 0
  for (let i = 0; i < x.length; i++) {
    const v = x[i]
    if (Number.isFinite(v)) { sum += v; cnt++ }
    if (i >= p) { const old = x[i - p]; if (Number.isFinite(old)) { sum -= old; cnt-- } }
    if (i >= p - 1 && cnt === p) out[i] = sum / p
  }
  return out
}

/** EMA روی آرایهٔ دلخواه (span-based). */
function emaArr(x: number[], p: number): number[] {
  const out = NaNArr(x.length)
  const a = 2 / (p + 1)
  let prev = NaN
  for (let i = 0; i < x.length; i++) {
    const v = x[i]
    if (!Number.isFinite(v)) { out[i] = prev; continue }
    prev = Number.isFinite(prev) ? a * v + (1 - a) * prev : v
    out[i] = prev
  }
  return out
}

/** RMA/Wilder MA (alpha = 1/p). */
function rmaArr(x: number[], p: number): number[] {
  const out = NaNArr(x.length)
  const a = 1 / p
  let prev = NaN
  for (let i = 0; i < x.length; i++) {
    const v = x[i]
    if (!Number.isFinite(v)) { out[i] = prev; continue }
    prev = Number.isFinite(prev) ? a * v + (1 - a) * prev : v
    out[i] = prev
  }
  return out
}

/** WMA (وزنِ خطیِ نزولی). */
function wmaArr(x: number[], p: number): number[] {
  const out = NaNArr(x.length)
  const denom = (p * (p + 1)) / 2
  for (let i = p - 1; i < x.length; i++) {
    let s = 0, ok = true
    for (let k = 0; k < p; k++) {
      const v = x[i - k]
      if (!Number.isFinite(v)) { ok = false; break }
      s += v * (p - k)
    }
    if (ok) out[i] = s / denom
  }
  return out
}

/** انحرافِ معیارِ غلتان (population). */
function stdArr(x: number[], p: number): number[] {
  const out = NaNArr(x.length)
  for (let i = p - 1; i < x.length; i++) {
    let m = 0, ok = true
    for (let k = 0; k < p; k++) { const v = x[i - k]; if (!Number.isFinite(v)) { ok = false; break } m += v }
    if (!ok) continue
    m /= p
    let s = 0
    for (let k = 0; k < p; k++) { const d = x[i - k] - m; s += d * d }
    out[i] = Math.sqrt(s / p)
  }
  return out
}

const highest = (x: number[], i: number, p: number) => {
  let m = -Infinity; for (let k = 0; k < p && i - k >= 0; k++) if (x[i - k] > m) m = x[i - k]; return m
}
const lowest = (x: number[], i: number, p: number) => {
  let m = Infinity; for (let k = 0; k < p && i - k >= 0; k++) if (x[i - k] < m) m = x[i - k]; return m
}

const asSeries = (x: number[]): IndicatorValue => x

// ---------------------------------------------------------------------------
// آرایهٔ نهاییِ بانک — هر ورودی active:false (پیش‌فرض غیرفعال).
// در این فایل به‌صورتِ تدریجی (طبقِ HARD-RULE) پر می‌شود.
// ---------------------------------------------------------------------------
export const BANK: IndicatorDef<any>[] = []

/** کمک‌سازندهٔ استاندارد: ثبتِ یک اندیکاتورِ تک-سری با active:false. */
function def(
  name: string,
  category: string,
  source: string,
  defaults: Record<string, number>,
  paramKeys: string[],
  desc: string,
  compute: (c: Candle[], p: any) => IndicatorValue,
): void {
  BANK.push({ name, category, source, active: false, defaults, paramKeys, desc, compute })
}

// ===========================================================================
// دستهٔ ۱ — Moving Averages پیشرفته (Overlap)  [EN/deep-web]
// ===========================================================================

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

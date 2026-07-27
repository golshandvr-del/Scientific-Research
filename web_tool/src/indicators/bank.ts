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

// ===========================================================================
// دستهٔ ۲ — Momentum / Oscillators  [EN/deep-web/pandas-ta]
// ===========================================================================

// AO — Awesome Oscillator = SMA5(median) − SMA34(median)
def('ao', 'momentum', 'EN', { fast: 5, slow: 34 }, ['fast', 'slow'], 'اسیلاتورِ عالی (بیل ویلیامز)', (c, p) => {
  const med = c.map(k => (k.high + k.low) / 2)
  const f = smaArr(med, p.fast), s = smaArr(med, p.slow)
  return asSeries(f.map((v, i) => v - s[i]))
})

// AC — Accelerator Oscillator = AO − SMA5(AO)
def('ac', 'momentum', 'EN', { fast: 5, slow: 34, smooth: 5 }, ['fast', 'slow', 'smooth'], 'اسیلاتورِ شتاب‌دهنده', (c, p) => {
  const med = c.map(k => (k.high + k.low) / 2)
  const ao = smaArr(med, p.fast).map((v, i) => v - smaArr(med, p.slow)[i])
  const sm = smaArr(ao, p.smooth)
  return asSeries(ao.map((v, i) => v - sm[i]))
})

// APO — Absolute Price Oscillator = EMA(fast) − EMA(slow)
def('apo', 'momentum', 'EN', { fast: 12, slow: 26 }, ['fast', 'slow'], 'اسیلاتورِ مطلقِ قیمت', (c, p) => {
  const x = closes(c), f = emaArr(x, p.fast), s = emaArr(x, p.slow)
  return asSeries(f.map((v, i) => v - s[i]))
})

// PPO — Percentage Price Oscillator = 100·(EMAf − EMAs)/EMAs
def('ppo', 'momentum', 'EN', { fast: 12, slow: 26 }, ['fast', 'slow'], 'اسیلاتورِ درصدیِ قیمت', (c, p) => {
  const x = closes(c), f = emaArr(x, p.fast), s = emaArr(x, p.slow)
  return asSeries(f.map((v, i) => (s[i] ? (100 * (v - s[i])) / s[i] : NaN)))
})

// CMO — Chande Momentum Oscillator
def('cmo', 'momentum', 'EN', { period: 14 }, ['period'], 'اسیلاتورِ مومنتومِ چاند', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period; i < n; i++) {
    let up = 0, dn = 0
    for (let k = 0; k < p.period; k++) { const d = x[i - k] - x[i - k - 1]; if (d > 0) up += d; else dn -= d }
    out[i] = (up + dn) === 0 ? 0 : (100 * (up - dn)) / (up + dn)
  }
  return asSeries(out)
})

// TSI — True Strength Index
def('tsi', 'momentum', 'EN', { long: 25, short: 13 }, ['long', 'short'], 'شاخصِ قدرتِ حقیقی', (c, p) => {
  const x = closes(c), n = x.length
  const mom = NaNArr(n); for (let i = 1; i < n; i++) mom[i] = x[i] - x[i - 1]
  const abs = mom.map(v => Math.abs(v))
  const d1 = emaArr(mom, p.long), d2 = emaArr(d1, p.short)
  const a1 = emaArr(abs, p.long), a2 = emaArr(a1, p.short)
  return asSeries(d2.map((v, i) => (a2[i] ? (100 * v) / a2[i] : NaN)))
})

// ROC — Rate of Change (%)
def('roc', 'momentum', 'EN', { period: 10 }, ['period'], 'نرخِ تغییر (درصد)', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period; i < n; i++) out[i] = x[i - p.period] ? (100 * (x[i] - x[i - p.period])) / x[i - p.period] : NaN
  return asSeries(out)
})

// MOM — Momentum (خام)
def('mom', 'momentum', 'EN', { period: 10 }, ['period'], 'مومنتومِ خام', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period; i < n; i++) out[i] = x[i] - x[i - p.period]
  return asSeries(out)
})

// BOP — Balance of Power = (close−open)/(high−low)
def('bop', 'momentum', 'EN', { smooth: 14 }, ['smooth'], 'توازنِ قدرت', (c, p) => {
  const raw = c.map(k => (k.high - k.low) ? (k.close - k.open) / (k.high - k.low) : 0)
  return asSeries(smaArr(raw, p.smooth))
})

// CFO — Chande Forecast Oscillator (انحراف از رگرسیونِ خطی، درصد)
def('cfo', 'momentum', 'EN', { period: 14 }, ['period'], 'اسیلاتورِ پیش‌بینیِ چاند', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) {
    let sx = 0, sy = 0, sxy = 0, sxx = 0
    for (let k = 0; k < p.period; k++) { const xi = k, yi = x[i - (p.period - 1 - k)]; sx += xi; sy += yi; sxy += xi * yi; sxx += xi * xi }
    const m = (p.period * sxy - sx * sy) / (p.period * sxx - sx * sx)
    const b = (sy - m * sx) / p.period
    const fc = m * (p.period - 1) + b
    out[i] = x[i] ? (100 * (x[i] - fc)) / x[i] : NaN
  }
  return asSeries(out)
})

// PGO — Pretty Good Oscillator = (close − SMA)/EMA(ATR)
def('pgo', 'momentum', 'deep-web', { period: 14 }, ['period'], 'اسیلاتورِ نسبتاً خوب', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  const sma = smaArr(x, p.period)
  const tr = NaNArr(n)
  for (let i = 1; i < n; i++) tr[i] = Math.max(c[i].high - c[i].low, Math.abs(c[i].high - c[i - 1].close), Math.abs(c[i].low - c[i - 1].close))
  const eatr = emaArr(tr, p.period)
  for (let i = 0; i < n; i++) out[i] = eatr[i] ? (x[i] - sma[i]) / eatr[i] : NaN
  return asSeries(out)
})

// Fisher Transform (روی نرمال‌شدهٔ median در کانالِ period)
def('fisher', 'momentum', 'EN', { period: 9 }, ['period'], 'تبدیلِ فیشرِ اِهلرز', (c, p) => {
  const med = c.map(k => (k.high + k.low) / 2), n = med.length, out = NaNArr(n)
  let v = 0, prevF = 0
  for (let i = p.period - 1; i < n; i++) {
    const hh = highest(med, i, p.period), ll = lowest(med, i, p.period)
    const rng = hh - ll || 1e-10
    v = 0.66 * ((2 * (med[i] - ll) / rng) - 1) + 0.67 * v
    const vv = Math.max(-0.999, Math.min(0.999, v))
    const f = 0.5 * Math.log((1 + vv) / (1 - vv)) + 0.5 * prevF
    out[i] = f; prevF = f
  }
  return asSeries(out)
})

// Inverse Fisher of RSI
def('ifish_rsi', 'momentum', 'EN', { period: 14 }, ['period'], 'فیشرِ معکوسِ RSI', (c, p) => {
  const rsi = I.rsi(closes(c), p.period) as unknown as number[]
  return asSeries(rsi.map(r => {
    if (!Number.isFinite(r)) return NaN
    const v = 0.1 * (r - 50)
    return (Math.exp(2 * v) - 1) / (Math.exp(2 * v) + 1)
  }))
})

// RVGI — Relative Vigor Index
def('rvgi', 'momentum', 'EN', { period: 10 }, ['period'], 'شاخصِ سرزندگیِ نسبی', (c, p) => {
  const n = c.length, num = NaNArr(n), den = NaNArr(n)
  const co = c.map(k => k.close - k.open), hl = c.map(k => k.high - k.low)
  for (let i = 3; i < n; i++) {
    num[i] = (co[i] + 2 * co[i - 1] + 2 * co[i - 2] + co[i - 3]) / 6
    den[i] = (hl[i] + 2 * hl[i - 1] + 2 * hl[i - 2] + hl[i - 3]) / 6
  }
  const sn = smaArr(num, p.period), sd = smaArr(den, p.period)
  return asSeries(sn.map((v, i) => (sd[i] ? v / sd[i] : NaN)))
})

// ===========================================================================
// دستهٔ ۳ — اندیکاتورهای بومیِ چینی (通达信/同花顺)  [CN — قلبِ اشتباهِ رایج #۳]
// ===========================================================================

// KDJ — تصادفیِ چینی (K/D/J). خروجی J = 3K − 2D (حساس‌ترین خط).
def('kdj_j', 'momentum', 'CN', { period: 9, k: 3, d: 3 }, ['period', 'k', 'd'], 'خطِ J از KDJ چینی (3K−2D)', (c, p) => {
  const h = highs(c), l = lows(c), x = closes(c), n = x.length
  const rsv = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) {
    const hh = highest(h, i, p.period), ll = lowest(l, i, p.period)
    rsv[i] = (hh - ll) ? (100 * (x[i] - ll)) / (hh - ll) : 50
  }
  // K = SMA وایلدرِ سادهٔ چینی (میانگینِ متحرکِ نمایی با alpha=1/k روی RSV)
  const kSer = NaNArr(n); let kPrev = 50
  for (let i = 0; i < n; i++) { if (!Number.isFinite(rsv[i])) continue; kPrev = (rsv[i] + (p.k - 1) * kPrev) / p.k; kSer[i] = kPrev }
  const dSer = NaNArr(n); let dPrev = 50
  for (let i = 0; i < n; i++) { if (!Number.isFinite(kSer[i])) continue; dPrev = (kSer[i] + (p.d - 1) * dPrev) / p.d; dSer[i] = dPrev }
  return asSeries(kSer.map((k, i) => (Number.isFinite(dSer[i]) ? 3 * k - 2 * dSer[i] : NaN)))
})

// BIAS — 乖离率 = 100·(close − SMA)/SMA
def('bias', 'momentum', 'CN', { period: 6 }, ['period'], 'نرخِ انحراف (乖离率)', (c, p) => {
  const x = closes(c), s = smaArr(x, p.period)
  return asSeries(x.map((v, i) => (s[i] ? (100 * (v - s[i])) / s[i] : NaN)))
})

// WR — Williams %R چینی (0..100 معکوس)
def('wr_cn', 'momentum', 'CN', { period: 14 }, ['period'], 'ویلیامز %R چینی (威廉)', (c, p) => {
  const h = highs(c), l = lows(c), x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) {
    const hh = highest(h, i, p.period), ll = lowest(l, i, p.period)
    out[i] = (hh - ll) ? (100 * (hh - x[i])) / (hh - ll) : 50
  }
  return asSeries(out)
})

// PSY — 心理线 = 100·(تعدادِ روزهای صعودی در N)/N
def('psy', 'momentum', 'CN', { period: 12 }, ['period'], 'خطِ روانی (心理线)', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period; i < n; i++) {
    let up = 0
    for (let k = 0; k < p.period; k++) if (x[i - k] > x[i - k - 1]) up++
    out[i] = (100 * up) / p.period
  }
  return asSeries(out)
})

// BR — 意愿指标 (بخشی از BRAR): جمعِ (H−prevClose)/جمعِ (prevClose−L)
def('br', 'momentum', 'CN', { period: 26 }, ['period'], 'شاخصِ اراده BR (情绪)', (c, p) => {
  const n = c.length, out = NaNArr(n)
  for (let i = p.period; i < n; i++) {
    let num = 0, den = 0
    for (let k = 0; k < p.period; k++) {
      const pc = c[i - k - 1].close
      num += Math.max(0, c[i - k].high - pc); den += Math.max(0, pc - c[i - k].low)
    }
    out[i] = den ? (100 * num) / den : 100
  }
  return asSeries(out)
})

// AR — 人气指标 (بخشی از BRAR): جمعِ (H−O)/جمعِ (O−L)
def('ar', 'momentum', 'CN', { period: 26 }, ['period'], 'شاخصِ محبوبیت AR (人气)', (c, p) => {
  const n = c.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) {
    let num = 0, den = 0
    for (let k = 0; k < p.period; k++) { num += c[i - k].high - c[i - k].open; den += c[i - k].open - c[i - k].low }
    out[i] = den ? (100 * num) / den : 100
  }
  return asSeries(out)
})

// CR — 带状能量线 (Energy) = 100·ΣMax(0,H−M)/ΣMax(0,M−L)، M=median روزِ قبل
def('cr', 'momentum', 'CN', { period: 26 }, ['period'], 'خطِ انرژیِ نواری CR (带状能量)', (c, p) => {
  const n = c.length, out = NaNArr(n)
  for (let i = p.period; i < n; i++) {
    let num = 0, den = 0
    for (let k = 0; k < p.period; k++) {
      const m = (c[i - k - 1].high + c[i - k - 1].low + c[i - k - 1].close) / 3
      num += Math.max(0, c[i - k].high - m); den += Math.max(0, m - c[i - k].low)
    }
    out[i] = den ? (100 * num) / den : 100
  }
  return asSeries(out)
})

// DMA — 平均差 = SMA(fast) − SMA(slow)
def('dma', 'trend', 'CN', { fast: 10, slow: 50 }, ['fast', 'slow'], 'تفاضلِ میانگین‌ها (平均差)', (c, p) => {
  const x = closes(c), f = smaArr(x, p.fast), s = smaArr(x, p.slow)
  return asSeries(f.map((v, i) => v - s[i]))
})

// TRIX — 三重指数平滑 نرخِ تغییرِ سه‌بار EMA (درصد)
def('trix', 'momentum', 'CN', { period: 12 }, ['period'], 'تریکس (三重指数平滑)', (c, p) => {
  const e1 = emaArr(closes(c), p.period), e2 = emaArr(e1, p.period), e3 = emaArr(e2, p.period), n = e3.length
  const out = NaNArr(n)
  for (let i = 1; i < n; i++) out[i] = e3[i - 1] ? (100 * (e3[i] - e3[i - 1])) / e3[i - 1] : NaN
  return asSeries(out)
})

// DPO — 区间震荡线 Detrended Price Oscillator
def('dpo', 'momentum', 'CN', { period: 20 }, ['period'], 'اسیلاتورِ بدونِ‌روند (区间震荡)', (c, p) => {
  const x = closes(c), s = smaArr(x, p.period), n = x.length, out = NaNArr(n)
  const shift = Math.floor(p.period / 2) + 1
  for (let i = 0; i < n; i++) if (i - shift >= 0 && Number.isFinite(s[i - shift])) out[i] = x[i] - s[i - shift]
  return asSeries(out)
})

// MTM — 动量线 (Momentum خطِ چینی) + قابلیتِ صاف‌سازی
def('mtm', 'momentum', 'CN', { period: 12, smooth: 6 }, ['period', 'smooth'], 'خطِ مومنتومِ چینی (动量)', (c, p) => {
  const x = closes(c), n = x.length, raw = NaNArr(n)
  for (let i = p.period; i < n; i++) raw[i] = x[i] - x[i - p.period]
  return asSeries(smaArr(raw, p.smooth))
})

// ADTM — 动态买卖气 (بازهٔ −1..+1)
def('adtm', 'momentum', 'CN', { period: 23, smooth: 8 }, ['period', 'smooth'], 'انرژیِ پویای خرید/فروش (动态买卖气)', (c, p) => {
  const n = c.length, dtm = NaNArr(n), dbm = NaNArr(n)
  for (let i = 1; i < n; i++) {
    if (c[i].open <= c[i - 1].open) dtm[i] = 0
    else dtm[i] = Math.max(c[i].high - c[i].open, c[i].open - c[i - 1].open)
    if (c[i].open >= c[i - 1].open) dbm[i] = 0
    else dbm[i] = Math.max(c[i].open - c[i].low, c[i].open - c[i - 1].open)
  }
  const out = NaNArr(n)
  for (let i = p.period; i < n; i++) {
    let sd = 0, sb = 0
    for (let k = 0; k < p.period; k++) { sd += dtm[i - k] || 0; sb += dbm[i - k] || 0 }
    const stm = Math.max(sd, sb)
    out[i] = stm ? (sd - sb) / stm : 0
  }
  return asSeries(smaArr(out, p.smooth))
})

// BBI — 多空均线 = میانگینِ SMA(3,6,12,24)
def('bbi', 'trend', 'CN', { p1: 3, p2: 6, p3: 12, p4: 24 }, ['p1', 'p2', 'p3', 'p4'], 'خطِ چندنرخیِ گاو-خرس (多空均线)', (c, p) => {
  const x = closes(c)
  const a = smaArr(x, p.p1), b = smaArr(x, p.p2), d = smaArr(x, p.p3), e = smaArr(x, p.p4)
  return asSeries(x.map((_, i) => (a[i] + b[i] + d[i] + e[i]) / 4))
})

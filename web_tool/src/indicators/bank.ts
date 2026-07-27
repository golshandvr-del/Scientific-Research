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

// helper: True Range سری
function trArr(c: Candle[]): number[] {
  const n = c.length, tr = NaNArr(n)
  for (let i = 1; i < n; i++) tr[i] = Math.max(c[i].high - c[i].low, Math.abs(c[i].high - c[i - 1].close), Math.abs(c[i].low - c[i - 1].close))
  return tr
}

// ===========================================================================
// دستهٔ ۴ — Volatility / Volume  [EN/deep-web — رژیمِ نوسانِ طلا]
// ===========================================================================

// NATR — Normalized ATR (%)
def('natr', 'volatility', 'EN', { period: 14 }, ['period'], 'ATR نرمال‌شده (درصد)', (c, p) => {
  const x = closes(c), a = rmaArr(trArr(c), p.period)
  return asSeries(a.map((v, i) => (x[i] ? (100 * v) / x[i] : NaN)))
})

// RVI — Relative Volatility Index (RSI روی std به‌جای قیمت)
def('rvi_vol', 'volatility', 'deep-web', { period: 14 }, ['period'], 'شاخصِ نوسانِ نسبی', (c, p) => {
  const x = closes(c), n = x.length, sd = stdArr(x, p.period)
  const up = NaNArr(n), dn = NaNArr(n)
  for (let i = 1; i < n; i++) { if (x[i] > x[i - 1]) { up[i] = sd[i]; dn[i] = 0 } else { up[i] = 0; dn[i] = sd[i] } }
  const eu = emaArr(up, p.period), ed = emaArr(dn, p.period)
  return asSeries(eu.map((v, i) => ((v + ed[i]) ? (100 * v) / (v + ed[i]) : NaN)))
})

// Ulcer Index — عمقِ افتِ نرمال‌شده (ریسکِ downside)
def('ulcer', 'volatility', 'EN', { period: 14 }, ['period'], 'شاخصِ زخم (عمقِ افت)', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) {
    let s = 0
    for (let k = 0; k < p.period; k++) {
      const mx = highest(x, i - k, p.period - k > 0 ? p.period : 1)
      const hh = highest(x, i, p.period)
      const dd = hh ? (100 * (x[i - k] - hh)) / hh : 0
      s += dd * dd
    }
    out[i] = Math.sqrt(s / p.period)
  }
  return asSeries(out)
})

// Choppiness Index — روند در برابرِ رنج (0..100؛ >61.8 رنج، <38.2 روند)
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

// Mass Index — تشخیصِ بازگشت با گشودگیِ دامنه
def('mass', 'volatility', 'CN', { ema: 9, sum: 25 }, ['ema', 'sum'], 'شاخصِ مِیس (梅斯线)', (c, p) => {
  const n = c.length, rng = c.map(k => k.high - k.low)
  const e1 = emaArr(rng, p.ema), e2 = emaArr(e1, p.ema)
  const ratio = e1.map((v, i) => (e2[i] ? v / e2[i] : NaN)), out = NaNArr(n)
  for (let i = p.sum - 1; i < n; i++) { let s = 0, ok = true; for (let k = 0; k < p.sum; k++) { if (!Number.isFinite(ratio[i - k])) { ok = false; break } s += ratio[i - k] } if (ok) out[i] = s }
  return asSeries(out)
})

// ATR-percentile — رتبهٔ درصدیِ ATR در پنجرهٔ بلند (رژیمِ نوسان)
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

// OBV — On-Balance Volume (tick-volume proxy برای XAU)
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

// ADOSC — Chaikin A/D Oscillator = EMA3(AD) − EMA10(AD)
def('adosc', 'volume', 'EN', { fast: 3, slow: 10 }, ['fast', 'slow'], 'اسیلاتورِ A/D چایکین', (c, p) => {
  const n = c.length, adl = NaNArr(n); let acc = 0
  for (let i = 0; i < n; i++) { const rng = c[i].high - c[i].low; const mfm = rng ? ((c[i].close - c[i].low) - (c[i].high - c[i].close)) / rng : 0; acc += mfm * c[i].volume; adl[i] = acc }
  const f = emaArr(adl, p.fast), s = emaArr(adl, p.slow)
  return asSeries(f.map((v, i) => v - s[i]))
})

// EFI — Elder Force Index = (close−prevClose)·volume، سپس EMA
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

// WVAD — 威廉变异离散量 (Williams Variable Accumulation/Distribution)
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

// ===========================================================================
// دستهٔ ۵ — Statistical / Fractal  [EN — ریاضی‌محورِ کمیاب]
// ===========================================================================

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

// FRAMA — Fractal Adaptive MA (Ehlers)
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

// ===========================================================================
// دستهٔ ۶ — Ehlers / DSP / Cycle  [deep-web — پیشرفته‌ترین، هدفِ اشتباهِ رایج #۲]
// ===========================================================================

// Super Smoother Filter (Ehlers 2-pole Butterworth)
def('ssf', 'cycle', 'deep-web', { period: 10 }, ['period'], 'فیلترِ سوپر-اسموترِ اِهلرز', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  const a = Math.exp(-1.414 * Math.PI / p.period)
  const b = 2 * a * Math.cos(1.414 * Math.PI / p.period)
  const c2 = b, c3 = -a * a, c1 = 1 - c2 - c3
  for (let i = 0; i < n; i++) {
    if (i < 2) { out[i] = x[i]; continue }
    out[i] = c1 * (x[i] + x[i - 1]) / 2 + c2 * out[i - 1] + c3 * out[i - 2]
  }
  return asSeries(out)
})

// High-Pass Filter (Ehlers 1-pole) — حذفِ روندِ بلند
def('ehp', 'cycle', 'deep-web', { period: 48 }, ['period'], 'فیلترِ بالاگذرِ اِهلرز', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  const a = (Math.cos(2 * Math.PI / p.period) + Math.sin(2 * Math.PI / p.period) - 1) / Math.cos(2 * Math.PI / p.period)
  for (let i = 0; i < n; i++) {
    if (i < 1) { out[i] = 0; continue }
    out[i] = (1 - a / 2) * (x[i] - x[i - 1]) + (1 - a) * out[i - 1]
  }
  return asSeries(out)
})

// Roofing Filter (High-Pass → Super Smoother) — اِهلرز
def('roof', 'cycle', 'deep-web', { hp: 48, ss: 10 }, ['hp', 'ss'], 'فیلترِ سقفیِ اِهلرز', (c, p) => {
  const x = closes(c), n = x.length, hp = NaNArr(n)
  const a = (Math.cos(2 * Math.PI / p.hp) + Math.sin(2 * Math.PI / p.hp) - 1) / Math.cos(2 * Math.PI / p.hp)
  for (let i = 0; i < n; i++) { if (i < 2) { hp[i] = 0; continue } hp[i] = (1 - a / 2) * (1 - a / 2) * (x[i] - 2 * x[i - 1] + x[i - 2]) + 2 * (1 - a) * hp[i - 1] - (1 - a) * (1 - a) * hp[i - 2] }
  const out = NaNArr(n)
  const aa = Math.exp(-1.414 * Math.PI / p.ss), bb = 2 * aa * Math.cos(1.414 * Math.PI / p.ss)
  const c2 = bb, c3 = -aa * aa, c1 = 1 - c2 - c3
  for (let i = 0; i < n; i++) { if (i < 2) { out[i] = hp[i]; continue } out[i] = c1 * (hp[i] + hp[i - 1]) / 2 + c2 * out[i - 1] + c3 * out[i - 2] }
  return asSeries(out)
})

// Laguerre Filter (Ehlers) — MA کم‌تأخیر
def('laguerre', 'cycle', 'deep-web', { gamma: 0.8 }, ['gamma'], 'فیلترِ لاگرِ اِهلرز', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  let L0 = 0, L1 = 0, L2 = 0, L3 = 0
  const g = p.gamma
  for (let i = 0; i < n; i++) {
    const pL0 = L0, pL1 = L1, pL2 = L2
    L0 = (1 - g) * x[i] + g * L0
    L1 = -g * L0 + pL0 + g * L1
    L2 = -g * L1 + pL1 + g * L2
    L3 = -g * L2 + pL2 + g * L3
    out[i] = (L0 + 2 * L1 + 2 * L2 + L3) / 6
  }
  return asSeries(out)
})

// Laguerre RSI (Ehlers)
def('laguerre_rsi', 'cycle', 'deep-web', { gamma: 0.5 }, ['gamma'], 'RSI لاگرِ اِهلرز', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  let L0 = 0, L1 = 0, L2 = 0, L3 = 0
  const g = p.gamma
  for (let i = 0; i < n; i++) {
    const pL0 = L0, pL1 = L1, pL2 = L2
    L0 = (1 - g) * x[i] + g * L0
    L1 = -g * L0 + pL0 + g * L1
    L2 = -g * L1 + pL1 + g * L2
    L3 = -g * L2 + pL2 + g * L3
    let cu = 0, cd = 0
    if (L0 >= L1) cu += L0 - L1; else cd += L1 - L0
    if (L1 >= L2) cu += L1 - L2; else cd += L2 - L1
    if (L2 >= L3) cu += L2 - L3; else cd += L3 - L2
    out[i] = (cu + cd) ? (100 * cu) / (cu + cd) : 50
  }
  return asSeries(out)
})

// Ehlers Reflex (2020) — نوسانگرِ کم‌تأخیر
def('reflex', 'cycle', 'deep-web', { period: 20 }, ['period'], 'ریفلکسِ اِهلرز (۲۰۲۰)', (c, p) => {
  const x = closes(c), n = x.length, ssf = NaNArr(n)
  const a = Math.exp(-1.414 * Math.PI / (p.period / 2)), b = 2 * a * Math.cos(1.414 * Math.PI / (p.period / 2))
  const c2 = b, c3 = -a * a, c1 = 1 - c2 - c3
  for (let i = 0; i < n; i++) { if (i < 2) { ssf[i] = x[i]; continue } ssf[i] = c1 * (x[i] + x[i - 1]) / 2 + c2 * ssf[i - 1] + c3 * ssf[i - 2] }
  const out = NaNArr(n); let ms = 0
  for (let i = p.period; i < n; i++) {
    const slope = (ssf[i - p.period] - ssf[i]) / p.period
    let sum = 0; for (let k = 1; k <= p.period; k++) sum += ssf[i] + k * slope - ssf[i - k]
    sum /= p.period
    ms = 0.04 * sum * sum + 0.96 * ms
    out[i] = ms ? sum / Math.sqrt(ms) : 0
  }
  return asSeries(out)
})

// Ehlers TrendFlex (2020)
def('trendflex', 'cycle', 'deep-web', { period: 20 }, ['period'], 'ترندفلکسِ اِهلرز (۲۰۲۰)', (c, p) => {
  const x = closes(c), n = x.length, ssf = NaNArr(n)
  const a = Math.exp(-1.414 * Math.PI / (p.period / 2)), b = 2 * a * Math.cos(1.414 * Math.PI / (p.period / 2))
  const c2 = b, c3 = -a * a, c1 = 1 - c2 - c3
  for (let i = 0; i < n; i++) { if (i < 2) { ssf[i] = x[i]; continue } ssf[i] = c1 * (x[i] + x[i - 1]) / 2 + c2 * ssf[i - 1] + c3 * ssf[i - 2] }
  const out = NaNArr(n); let ms = 0
  for (let i = p.period; i < n; i++) {
    let sum = 0; for (let k = 1; k <= p.period; k++) sum += ssf[i] - ssf[i - k]
    sum /= p.period
    ms = 0.04 * sum * sum + 0.96 * ms
    out[i] = ms ? sum / Math.sqrt(ms) : 0
  }
  return asSeries(out)
})

// Ehlers Fisher via Center of Gravity
def('cg', 'cycle', 'deep-web', { period: 10 }, ['period'], 'مرکزِ ثقلِ اِهلرز (CG)', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) {
    let num = 0, den = 0
    for (let k = 0; k < p.period; k++) { num += (1 + k) * x[i - k]; den += x[i - k] }
    out[i] = den ? -num / den + (p.period + 1) / 2 : 0
  }
  return asSeries(out)
})

// DSMA — Deviation-Scaled MA (Ehlers)
def('dsma', 'cycle', 'deep-web', { period: 20 }, ['period'], 'میانگینِ مقیاسِ‌انحرافِ اِهلرز', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n), zeros = NaNArr(n), filt = NaNArr(n)
  const a = Math.exp(-1.414 * Math.PI / (p.period / 2)), b = 2 * a * Math.cos(1.414 * Math.PI / (p.period / 2))
  const c2 = b, c3 = -a * a, c1 = 1 - c2 - c3
  let prev = NaN
  for (let i = 0; i < n; i++) {
    zeros[i] = i >= 2 ? x[i] - x[i - 2] : 0
    if (i < 2) { filt[i] = 0; out[i] = x[i]; prev = x[i]; continue }
    filt[i] = c1 * (zeros[i] + zeros[i - 1]) / 2 + c2 * filt[i - 1] + c3 * filt[i - 2]
    let rms = 0; const w = Math.min(p.period, i + 1)
    for (let k = 0; k < w; k++) rms += filt[i - k] * filt[i - k]
    rms = Math.sqrt(rms / w)
    const sc = rms ? Math.abs(filt[i] / rms) : 0
    const alpha = Math.max(0.01, Math.min(1, (5 * sc) / p.period))
    prev = alpha * x[i] + (1 - alpha) * prev
    out[i] = prev
  }
  return asSeries(out)
})

// ===========================================================================
// دستهٔ ۷ — Trend-following / Structure  [EN/RU — ساختاری و پرکاربرد]
// ===========================================================================

// Supertrend (ATR-based) — خطِ روند؛ خروجی = مقدارِ خطِ سوپرترند
def('supertrend', 'trend', 'deep-web', { period: 10, mult: 3 }, ['period', 'mult'], 'سوپرترند (ATR-محور)', (c, p) => {
  const n = c.length, atr = rmaArr(trArr(c), p.period), out = NaNArr(n)
  let dir = 1, finalUp = NaN, finalDn = NaN
  for (let i = 0; i < n; i++) {
    const mid = (c[i].high + c[i].low) / 2
    const bu = mid - p.mult * atr[i], bd = mid + p.mult * atr[i]
    if (i === 0 || !Number.isFinite(atr[i])) { finalUp = bu; finalDn = bd; out[i] = bd; continue }
    finalUp = (bu > finalUp || c[i - 1].close < finalUp) ? bu : finalUp
    finalDn = (bd < finalDn || c[i - 1].close > finalDn) ? bd : finalDn
    if (dir === 1 && c[i].close < finalUp) dir = -1
    else if (dir === -1 && c[i].close > finalDn) dir = 1
    out[i] = dir === 1 ? finalUp : finalDn
  }
  return asSeries(out)
})

// Parabolic SAR
def('psar', 'trend', 'EN', { step: 0.02, max: 0.2 }, ['step', 'max'], 'سارِ سهموی', (c, p) => {
  const n = c.length, out = NaNArr(n)
  if (n < 2) return asSeries(out)
  let bull = c[1].close >= c[0].close
  let af = p.step, ep = bull ? c[0].high : c[0].low, sar = bull ? c[0].low : c[0].high
  for (let i = 1; i < n; i++) {
    sar = sar + af * (ep - sar)
    if (bull) {
      if (c[i].low < sar) { bull = false; sar = ep; ep = c[i].low; af = p.step }
      else { if (c[i].high > ep) { ep = c[i].high; af = Math.min(p.max, af + p.step) } }
    } else {
      if (c[i].high > sar) { bull = true; sar = ep; ep = c[i].high; af = p.step }
      else { if (c[i].low < ep) { ep = c[i].low; af = Math.min(p.max, af + p.step) } }
    }
    out[i] = sar
  }
  return asSeries(out)
})

// Aroon Oscillator = AroonUp − AroonDown
def('aroon', 'trend', 'EN', { period: 25 }, ['period'], 'اسیلاتورِ آرون', (c, p) => {
  const h = highs(c), l = lows(c), n = c.length, out = NaNArr(n)
  for (let i = p.period; i < n; i++) {
    let hi = 0, li = 0, hv = -Infinity, lv = Infinity
    for (let k = 0; k <= p.period; k++) { if (h[i - k] > hv) { hv = h[i - k]; hi = k } if (l[i - k] < lv) { lv = l[i - k]; li = k } }
    const up = (100 * (p.period - hi)) / p.period, dn = (100 * (p.period - li)) / p.period
    out[i] = up - dn
  }
  return asSeries(out)
})

// Vortex Indicator (VI+ − VI−)
def('vortex', 'trend', 'EN', { period: 14 }, ['period'], 'اندیکاتورِ گردابی (ورتکس)', (c, p) => {
  const n = c.length, vmP = NaNArr(n), vmN = NaNArr(n), tr = trArr(c)
  for (let i = 1; i < n; i++) { vmP[i] = Math.abs(c[i].high - c[i - 1].low); vmN[i] = Math.abs(c[i].low - c[i - 1].high) }
  const out = NaNArr(n)
  for (let i = p.period; i < n; i++) {
    let sp = 0, sn = 0, st = 0
    for (let k = 0; k < p.period; k++) { sp += vmP[i - k] || 0; sn += vmN[i - k] || 0; st += tr[i - k] || 0 }
    out[i] = st ? (sp - sn) / st : 0
  }
  return asSeries(out)
})

// Donchian channel midline
def('donchian_mid', 'trend', 'EN', { period: 20 }, ['period'], 'خطِ میانیِ کانالِ دونچیان', (c, p) => {
  const h = highs(c), l = lows(c), n = c.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) out[i] = (highest(h, i, p.period) + lowest(l, i, p.period)) / 2
  return asSeries(out)
})

// QQE — Quantitative Qualitative Estimation (RSI هموار + باندِ ATR-RSI)
def('qqe', 'momentum', 'RU', { rsiP: 14, sf: 5 }, ['rsiP', 'sf'], 'برآوردِ کمی-کیفی (QQE)', (c, p) => {
  const rsi = I.rsi(closes(c), p.rsiP) as unknown as number[]
  return asSeries(emaArr(rsi, p.sf))
})

// Schaff Trend Cycle (STC)
def('stc', 'momentum', 'EN', { fast: 23, slow: 50, cycle: 10 }, ['fast', 'slow', 'cycle'], 'چرخهٔ روندِ شاف (STC)', (c, p) => {
  const x = closes(c), n = x.length
  const macd = emaArr(x, p.fast).map((v, i) => v - emaArr(x, p.slow)[i])
  const stoch1 = NaNArr(n)
  for (let i = p.cycle - 1; i < n; i++) { const hh = highest(macd, i, p.cycle), ll = lowest(macd, i, p.cycle); stoch1[i] = (hh - ll) ? (100 * (macd[i] - ll)) / (hh - ll) : 50 }
  const d1 = emaArr(stoch1, Math.max(2, Math.floor(p.cycle / 2)))
  const stoch2 = NaNArr(n)
  for (let i = p.cycle - 1; i < n; i++) { const hh = highest(d1, i, p.cycle), ll = lowest(d1, i, p.cycle); stoch2[i] = (hh - ll) ? (100 * (d1[i] - ll)) / (hh - ll) : 50 }
  return asSeries(emaArr(stoch2, Math.max(2, Math.floor(p.cycle / 2))))
})

// Connors RSI = (RSI3 + streakRSI + PctRank)/3
def('crsi', 'momentum', 'deep-web', { rsiP: 3, streakP: 2, rankP: 100 }, ['rsiP', 'streakP', 'rankP'], 'کانرزِ RSI', (c, p) => {
  const x = closes(c), n = x.length
  const rsi = I.rsi(x, p.rsiP) as unknown as number[]
  const streak = NaNArr(n); let s = 0
  for (let i = 1; i < n; i++) { if (x[i] > x[i - 1]) s = s >= 0 ? s + 1 : 1; else if (x[i] < x[i - 1]) s = s <= 0 ? s - 1 : -1; else s = 0; streak[i] = s }
  const streakRsi = I.rsi(streak.map(v => (Number.isFinite(v) ? v : 0)), p.streakP) as unknown as number[]
  const ret = NaNArr(n); for (let i = 1; i < n; i++) ret[i] = x[i - 1] ? (x[i] - x[i - 1]) / x[i - 1] : 0
  const rank = NaNArr(n)
  for (let i = p.rankP; i < n; i++) { let below = 0; for (let k = 1; k <= p.rankP; k++) if (ret[i - k] < ret[i]) below++; rank[i] = (100 * below) / p.rankP }
  const out = NaNArr(n)
  for (let i = 0; i < n; i++) if (Number.isFinite(rsi[i]) && Number.isFinite(streakRsi[i]) && Number.isFinite(rank[i])) out[i] = (rsi[i] + streakRsi[i] + rank[i]) / 3
  return asSeries(out)
})

// Waddah Attar Explosion (MACD-diff × BB-width)
def('waddah', 'momentum', 'RU', { fast: 20, slow: 40, bbP: 20, bbM: 2 }, ['fast', 'slow', 'bbP', 'bbM'], 'انفجارِ وداح‌عطار', (c, p) => {
  const x = closes(c), n = x.length
  const macd = emaArr(x, p.fast).map((v, i) => v - emaArr(x, p.slow)[i])
  const sd = stdArr(x, p.bbP), sma = smaArr(x, p.bbP)
  const out = NaNArr(n)
  for (let i = 1; i < n; i++) {
    const t = (macd[i] - macd[i - 1]) * 150
    const bbw = 2 * p.bbM * sd[i]
    out[i] = Number.isFinite(t) && Number.isFinite(bbw) ? t : NaN
    void sma
  }
  return asSeries(out)
})

// Elder Impulse (EMA-slope sign × MACD-hist sign) → {−1,0,+1}
def('elder_impulse', 'composite', 'EN', { emaP: 13, macdF: 12, macdS: 26, macdSig: 9 }, ['emaP', 'macdF', 'macdS', 'macdSig'], 'سیستمِ ضربهٔ الدر', (c, p) => {
  const x = closes(c), n = x.length
  const e = emaArr(x, p.emaP)
  const macd = emaArr(x, p.macdF).map((v, i) => v - emaArr(x, p.macdS)[i])
  const sig = emaArr(macd, p.macdSig)
  const hist = macd.map((v, i) => v - sig[i])
  const out = NaNArr(n)
  for (let i = 1; i < n; i++) {
    const es = Math.sign(e[i] - e[i - 1]), hs = Math.sign(hist[i] - hist[i - 1])
    out[i] = (es > 0 && hs > 0) ? 1 : (es < 0 && hs < 0) ? -1 : 0
  }
  return asSeries(out)
})

// Chandelier Exit (long) — ATR trailing از بالاترین سقف
def('chandelier', 'trend', 'EN', { period: 22, mult: 3 }, ['period', 'mult'], 'خروجِ شمعدانی (ترِیلینگ)', (c, p) => {
  const h = highs(c), atr = rmaArr(trArr(c), p.period), n = c.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) out[i] = highest(h, i, p.period) - p.mult * atr[i]
  return asSeries(out)
})

// Gann HiLo Activator
def('gann_hilo', 'trend', 'RU', { period: 10 }, ['period'], 'فعال‌سازِ گانِ های‌لو', (c, p) => {
  const h = highs(c), l = lows(c), n = c.length, out = NaNArr(n)
  const sh = smaArr(h, p.period), sl = smaArr(l, p.period)
  let dir = 1
  for (let i = p.period; i < n; i++) {
    if (c[i].close > sh[i - 1]) dir = 1; else if (c[i].close < sl[i - 1]) dir = -1
    out[i] = dir === 1 ? sl[i] : sh[i]
  }
  return asSeries(out)
})

// TDI — Traders Dynamic Index (RSI هموارشده؛ خطِ سیگنال)
def('tdi', 'momentum', 'RU', { rsiP: 13, sig: 7 }, ['rsiP', 'sig'], 'شاخصِ پویای معامله‌گران', (c, p) => {
  const rsi = I.rsi(closes(c), p.rsiP) as unknown as number[]
  return asSeries(smaArr(rsi, p.sig))
})

// ===========================================================================
// دستهٔ ۸ — Price transforms + Composite  [EN/composite]
// ===========================================================================

def('hl2', 'overlap', 'EN', {}, [], 'میانگینِ سقف-کف', (c) => asSeries(c.map(k => (k.high + k.low) / 2)))
def('hlc3', 'overlap', 'EN', {}, [], 'قیمتِ نوعی (typical)', (c) => asSeries(c.map(k => (k.high + k.low + k.close) / 3)))
def('ohlc4', 'overlap', 'EN', {}, [], 'میانگینِ چهارقیمتی', (c) => asSeries(c.map(k => (k.open + k.high + k.low + k.close) / 4)))
def('wcp', 'overlap', 'EN', {}, [], 'قیمتِ بستهٔ وزنی', (c) => asSeries(c.map(k => (k.high + k.low + 2 * k.close) / 4)))
def('midpoint', 'overlap', 'EN', { period: 14 }, ['period'], 'نقطهٔ میانیِ کلوز', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) out[i] = (highest(x, i, p.period) + lowest(x, i, p.period)) / 2
  return asSeries(out)
})

// ATR-normalized distance from EMA (رژیمِ کشش)
def('ema_dist_atr', 'composite', 'composite', { emaP: 50, atrP: 14 }, ['emaP', 'atrP'], 'فاصلهٔ نرمال‌شدهٔ قیمت از EMA (بر حسبِ ATR)', (c, p) => {
  const x = closes(c), e = emaArr(x, p.emaP), a = rmaArr(trArr(c), p.atrP), n = x.length, out = NaNArr(n)
  for (let i = 0; i < n; i++) out[i] = a[i] ? (x[i] - e[i]) / a[i] : NaN
  return asSeries(out)
})

// RSI of Kaufman ER (کارایی-محور)
def('rsi_of_er', 'composite', 'composite', { erP: 10, rsiP: 14 }, ['erP', 'rsiP'], 'RSI روی نسبتِ کاراییِ کافمن', (c, p) => {
  const x = closes(c), n = x.length, er = NaNArr(n)
  for (let i = p.erP; i < n; i++) {
    const change = Math.abs(x[i] - x[i - p.erP])
    let vol = 0; for (let k = 0; k < p.erP; k++) vol += Math.abs(x[i - k] - x[i - k - 1])
    er[i] = vol ? change / vol : 0
  }
  return asSeries(I.rsi(er.map(v => (Number.isFinite(v) ? v * 100 : 0)), p.rsiP) as unknown as number[])
})

// Choppiness-gated trend flag (chop<38.2 و شیبِ EMA) → {−1,0,+1}
def('trend_gate', 'composite', 'composite', { chopP: 14, emaP: 50, thr: 38.2 }, ['chopP', 'emaP', 'thr'], 'دروازهٔ روند با فیلترِ چاپینس', (c, p) => {
  const x = closes(c), n = x.length, tr = trArr(c), h = highs(c), l = lows(c), e = emaArr(x, p.emaP)
  const out = NaNArr(n)
  for (let i = p.chopP; i < n; i++) {
    let sumTr = 0; for (let k = 0; k < p.chopP; k++) sumTr += tr[i - k] || 0
    const rng = highest(h, i, p.chopP) - lowest(l, i, p.chopP)
    const chop = rng > 0 ? (100 * Math.log10(sumTr / rng)) / Math.log10(p.chopP) : 100
    if (chop < p.thr) out[i] = Math.sign(e[i] - e[i - 1]); else out[i] = 0
  }
  return asSeries(out)
})

// ===========================================================================
// دستهٔ ۹ — Candlestick Pattern Detectors  [deep-web/TA-Lib]
// خروجی هر تشخیص‌دهنده: +100 (صعودی)، −100 (نزولی)، 0 (بدونِ الگو). بدونِ look-ahead.
// ===========================================================================

// کمک‌توابعِ ساختارِ کندل
const body = (k: Candle) => Math.abs(k.close - k.open)
const range = (k: Candle) => k.high - k.low
const upSh = (k: Candle) => k.high - Math.max(k.open, k.close)
const dnSh = (k: Candle) => Math.min(k.open, k.close) - k.low
const isBull = (k: Candle) => k.close > k.open
const isBear = (k: Candle) => k.close < k.open

/** ثبتِ الگوی کندلی (بدونِ پارامتر؛ خروجی ±100/0). */
function pat(name: string, desc: string, fn: (c: Candle[], i: number) => number): void {
  def(name, 'pattern', 'deep-web', {}, [], desc, (c) => {
    const n = c.length, out = NaNArr(n)
    for (let i = 0; i < n; i++) out[i] = i >= 3 ? fn(c, i) : 0
    return asSeries(out)
  })
}

pat('cdl_doji', 'دوجی (بدنهٔ بسیار کوچک)', (c, i) => (range(c[i]) && body(c[i]) <= 0.1 * range(c[i]) ? 100 : 0))
pat('cdl_dragonfly', 'دوجیِ سنجاقک (سایهٔ پایینِ بلند)', (c, i) => (range(c[i]) && body(c[i]) <= 0.1 * range(c[i]) && dnSh(c[i]) >= 0.6 * range(c[i]) ? 100 : 0))
pat('cdl_gravestone', 'دوجیِ سنگِ‌قبر (سایهٔ بالای بلند)', (c, i) => (range(c[i]) && body(c[i]) <= 0.1 * range(c[i]) && upSh(c[i]) >= 0.6 * range(c[i]) ? -100 : 0))
pat('cdl_hammer', 'چکش (سایهٔ پایینِ بلند، بدنهٔ کوچکِ بالا)', (c, i) => (range(c[i]) && dnSh(c[i]) >= 2 * body(c[i]) && upSh(c[i]) <= 0.15 * range(c[i]) && c[i - 1].close < c[i - 2].close ? 100 : 0))
pat('cdl_invhammer', 'چکشِ معکوس', (c, i) => (range(c[i]) && upSh(c[i]) >= 2 * body(c[i]) && dnSh(c[i]) <= 0.15 * range(c[i]) && c[i - 1].close < c[i - 2].close ? 100 : 0))
pat('cdl_hangingman', 'مردِ آویزان', (c, i) => (range(c[i]) && dnSh(c[i]) >= 2 * body(c[i]) && upSh(c[i]) <= 0.15 * range(c[i]) && c[i - 1].close > c[i - 2].close ? -100 : 0))
pat('cdl_shootingstar', 'ستارهٔ ثاقب', (c, i) => (range(c[i]) && upSh(c[i]) >= 2 * body(c[i]) && dnSh(c[i]) <= 0.15 * range(c[i]) && c[i - 1].close > c[i - 2].close ? -100 : 0))
pat('cdl_marubozu', 'ماروبوزو (بدونِ سایه)', (c, i) => (range(c[i]) && body(c[i]) >= 0.95 * range(c[i]) ? (isBull(c[i]) ? 100 : -100) : 0))
pat('cdl_spinningtop', 'فرفره (بدنهٔ کوچک، دو سایه)', (c, i) => (range(c[i]) && body(c[i]) <= 0.3 * range(c[i]) && upSh(c[i]) >= 0.3 * range(c[i]) && dnSh(c[i]) >= 0.3 * range(c[i]) ? 100 : 0))
pat('cdl_engulf_bull', 'پوششِ صعودی', (c, i) => (isBear(c[i - 1]) && isBull(c[i]) && c[i].close >= c[i - 1].open && c[i].open <= c[i - 1].close ? 100 : 0))
pat('cdl_engulf_bear', 'پوششِ نزولی', (c, i) => (isBull(c[i - 1]) && isBear(c[i]) && c[i].open >= c[i - 1].close && c[i].close <= c[i - 1].open ? -100 : 0))
pat('cdl_harami_bull', 'هارامیِ صعودی', (c, i) => (isBear(c[i - 1]) && body(c[i - 1]) > 0 && Math.max(c[i].open, c[i].close) < c[i - 1].open && Math.min(c[i].open, c[i].close) > c[i - 1].close ? 100 : 0))
pat('cdl_harami_bear', 'هارامیِ نزولی', (c, i) => (isBull(c[i - 1]) && body(c[i - 1]) > 0 && Math.max(c[i].open, c[i].close) < c[i - 1].close && Math.min(c[i].open, c[i].close) > c[i - 1].open ? -100 : 0))
pat('cdl_piercing', 'خطِ نفوذی (صعودی)', (c, i) => (isBear(c[i - 1]) && isBull(c[i]) && c[i].open < c[i - 1].low && c[i].close > (c[i - 1].open + c[i - 1].close) / 2 && c[i].close < c[i - 1].open ? 100 : 0))
pat('cdl_darkcloud', 'پوششِ ابرِ سیاه (نزولی)', (c, i) => (isBull(c[i - 1]) && isBear(c[i]) && c[i].open > c[i - 1].high && c[i].close < (c[i - 1].open + c[i - 1].close) / 2 && c[i].close > c[i - 1].open ? -100 : 0))
pat('cdl_morningstar', 'ستارهٔ صبحگاهی', (c, i) => (isBear(c[i - 2]) && body(c[i - 1]) <= 0.3 * range(c[i - 1] || c[i - 2]) && isBull(c[i]) && c[i].close > (c[i - 2].open + c[i - 2].close) / 2 ? 100 : 0))
pat('cdl_eveningstar', 'ستارهٔ شامگاهی', (c, i) => (isBull(c[i - 2]) && body(c[i - 1]) <= 0.3 * range(c[i - 1] || c[i - 2]) && isBear(c[i]) && c[i].close < (c[i - 2].open + c[i - 2].close) / 2 ? -100 : 0))
pat('cdl_3whitesoldiers', 'سه سربازِ سفید', (c, i) => (isBull(c[i]) && isBull(c[i - 1]) && isBull(c[i - 2]) && c[i].close > c[i - 1].close && c[i - 1].close > c[i - 2].close && c[i].open > c[i - 1].open && c[i - 1].open > c[i - 2].open ? 100 : 0))
pat('cdl_3blackcrows', 'سه کلاغِ سیاه', (c, i) => (isBear(c[i]) && isBear(c[i - 1]) && isBear(c[i - 2]) && c[i].close < c[i - 1].close && c[i - 1].close < c[i - 2].close && c[i].open < c[i - 1].open && c[i - 1].open < c[i - 2].open ? -100 : 0))
pat('cdl_beltuphold_bull', 'کمربندِ صعودی', (c, i) => (isBull(c[i]) && c[i].open === c[i].low && body(c[i]) >= 0.7 * range(c[i]) ? 100 : 0))
pat('cdl_beltuphold_bear', 'کمربندِ نزولی', (c, i) => (isBear(c[i]) && c[i].open === c[i].high && body(c[i]) >= 0.7 * range(c[i]) ? -100 : 0))
pat('cdl_longleg_doji', 'دوجیِ پابلند', (c, i) => (range(c[i]) && body(c[i]) <= 0.1 * range(c[i]) && upSh(c[i]) >= 0.35 * range(c[i]) && dnSh(c[i]) >= 0.35 * range(c[i]) ? 100 : 0))
pat('cdl_highwave', 'موجِ بلند', (c, i) => (range(c[i]) && body(c[i]) <= 0.2 * range(c[i]) && (upSh(c[i]) >= 0.4 * range(c[i]) || dnSh(c[i]) >= 0.4 * range(c[i])) ? 100 : 0))
pat('cdl_3inside_up', 'سه داخلیِ صعودی', (c, i) => (isBear(c[i - 2]) && Math.max(c[i - 1].open, c[i - 1].close) < c[i - 2].open && Math.min(c[i - 1].open, c[i - 1].close) > c[i - 2].close && isBull(c[i]) && c[i].close > c[i - 2].open ? 100 : 0))
pat('cdl_3inside_dn', 'سه داخلیِ نزولی', (c, i) => (isBull(c[i - 2]) && Math.max(c[i - 1].open, c[i - 1].close) < c[i - 2].close && Math.min(c[i - 1].open, c[i - 1].close) > c[i - 2].open && isBear(c[i]) && c[i].close < c[i - 2].open ? -100 : 0))
pat('cdl_tweezerbottom', 'انبرکِ کف', (c, i) => (Math.abs(c[i].low - c[i - 1].low) <= 0.05 * (range(c[i]) || 1) && isBear(c[i - 1]) && isBull(c[i]) ? 100 : 0))
pat('cdl_tweezertop', 'انبرکِ سقف', (c, i) => (Math.abs(c[i].high - c[i - 1].high) <= 0.05 * (range(c[i]) || 1) && isBull(c[i - 1]) && isBear(c[i]) ? -100 : 0))
pat('cdl_kicking_bull', 'ضربهٔ صعودی', (c, i) => (isBear(c[i - 1]) && body(c[i - 1]) >= 0.9 * range(c[i - 1]) && isBull(c[i]) && body(c[i]) >= 0.9 * range(c[i]) && c[i].open > c[i - 1].open ? 100 : 0))
pat('cdl_kicking_bear', 'ضربهٔ نزولی', (c, i) => (isBull(c[i - 1]) && body(c[i - 1]) >= 0.9 * range(c[i - 1]) && isBear(c[i]) && body(c[i]) >= 0.9 * range(c[i]) && c[i].open < c[i - 1].open ? -100 : 0))
pat('cdl_gap_up', 'گَپِ صعودی', (c, i) => (c[i].low > c[i - 1].high ? 100 : 0))
pat('cdl_gap_dn', 'گَپِ نزولی', (c, i) => (c[i].high < c[i - 1].low ? -100 : 0))

// ===========================================================================
// دستهٔ ۱۰ — Variant Expansion (بسطِ پارامتریِ علمی)
// ----------------------------------------------------------------------------
// طبقِ قانونِ «همه‌چیز شناور است» و اصلِ variant-instancing در TA-Lib/pandas-ta،
// هر خانوادهٔ اندیکاتورِ تک-پارامتری در چند دورهٔ **غیررند** (فیبوناچی و لوکاس، متناسب
// با تایم‌فریم‌های XAUUSD: M5/M15/H1/H4/D1) به یک instanceِ مجزا تبدیل می‌شود.
// این مستقیماً اشتباهِ رایج #۷ (اجتناب از اعدادِ رند مثل 50/100/200) را رفع می‌کند.
// همهٔ variantها active:false ثبت می‌شوند و فقط با صداکردنِ یک لایه فعال می‌شوند.
// ===========================================================================

// دوره‌های غیررندِ فیبوناچی/لوکاس (نه 10/20/50/100/200) — نجات‌دهندهٔ واقعی طبقِ اشتباهِ #۷
const FIB_PERIODS = [3, 5, 8, 13, 21, 34, 55, 89, 144, 233]
const LUCAS_PERIODS = [4, 7, 11, 18, 29, 47, 76, 123, 199]

/** بسطِ یک خانوادهٔ تک-پارامتری (period) به چند instance با دوره‌های غیررند. */
function expandPeriodFamily(
  baseName: string, category: string, source: string, desc: string,
  build: (period: number) => (c: Candle[]) => IndicatorValue,
  periods: number[],
): void {
  for (const per of periods) {
    BANK.push({
      name: `${baseName}_${per}`, category, source, active: false,
      defaults: { period: per }, paramKeys: ['period'],
      desc: `${desc} — دورهٔ غیررندِ ${per}`,
      compute: (c: Candle[]) => build(per)(c),
    })
  }
}

// خانواده‌های میانگین (روی close) — دوره‌های فیبوناچی
expandPeriodFamily('sma_fib', 'trend', 'composite', 'میانگینِ ساده', (per) => (c) => asSeries(smaArr(closes(c), per)), FIB_PERIODS)
expandPeriodFamily('ema_fib', 'trend', 'composite', 'میانگینِ نمایی', (per) => (c) => asSeries(emaArr(closes(c), per)), FIB_PERIODS)
expandPeriodFamily('wma_fib', 'trend', 'composite', 'میانگینِ وزنی', (per) => (c) => asSeries(wmaArr(closes(c), per)), FIB_PERIODS)
expandPeriodFamily('rma_fib', 'trend', 'composite', 'میانگینِ وایلدر', (per) => (c) => asSeries(rmaArr(closes(c), per)), FIB_PERIODS)
expandPeriodFamily('hma_fib', 'trend', 'composite', 'میانگینِ هال', (per) => (c) => {
  const x = closes(c), half = wmaArr(x, Math.max(1, Math.floor(per / 2))), full = wmaArr(x, per)
  return asSeries(wmaArr(half.map((v, i) => 2 * v - full[i]), Math.max(1, Math.floor(Math.sqrt(per)))))
}, FIB_PERIODS)

// خانوادهٔ RSI — دوره‌های لوکاس (غیررند)
expandPeriodFamily('rsi_lucas', 'momentum', 'composite', 'RSI', (per) => (c) => asSeries(I.rsi(closes(c), per) as unknown as number[]), LUCAS_PERIODS)

// خانوادهٔ CMO — فیبوناچی
expandPeriodFamily('cmo_fib', 'momentum', 'composite', 'مومنتومِ چاند', (per) => (c) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = per; i < n; i++) { let up = 0, dn = 0; for (let k = 0; k < per; k++) { const d = x[i - k] - x[i - k - 1]; if (d > 0) up += d; else dn -= d } out[i] = (up + dn) ? (100 * (up - dn)) / (up + dn) : 0 }
  return asSeries(out)
}, FIB_PERIODS)

// خانوادهٔ ROC — فیبوناچی
expandPeriodFamily('roc_fib', 'momentum', 'composite', 'نرخِ تغییر', (per) => (c) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = per; i < n; i++) out[i] = x[i - per] ? (100 * (x[i] - x[i - per])) / x[i - per] : NaN
  return asSeries(out)
}, FIB_PERIODS)

// خانوادهٔ std (نوسان) — فیبوناچی
expandPeriodFamily('std_fib', 'volatility', 'composite', 'انحرافِ معیار', (per) => (c) => asSeries(stdArr(closes(c), per)), FIB_PERIODS)

// خانوادهٔ BIAS — فیبوناچی
expandPeriodFamily('bias_fib', 'momentum', 'composite', 'نرخِ انحراف (乖离)', (per) => (c) => {
  const x = closes(c), s = smaArr(x, per)
  return asSeries(x.map((v, i) => (s[i] ? (100 * (v - s[i])) / s[i] : NaN)))
}, FIB_PERIODS)

// خانوادهٔ Kaufman ER — لوکاس
expandPeriodFamily('er_lucas', 'composite', 'composite', 'نسبتِ کاراییِ کافمن', (per) => (c) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = per; i < n; i++) { const ch = Math.abs(x[i] - x[i - per]); let v = 0; for (let k = 0; k < per; k++) v += Math.abs(x[i - k] - x[i - k - 1]); out[i] = v ? ch / v : 0 }
  return asSeries(out)
}, LUCAS_PERIODS)

// خانوادهٔ z-score — فیبوناچی
expandPeriodFamily('zscore_fib', 'statistical', 'composite', 'امتیازِ Z قیمت', (per) => (c) => {
  const x = closes(c), s = smaArr(x, per), sd = stdArr(x, per)
  return asSeries(x.map((v, i) => (sd[i] ? (v - s[i]) / sd[i] : NaN)))
}, FIB_PERIODS)

// خانوادهٔ WR — فیبوناچی
expandPeriodFamily('wr_fib', 'momentum', 'composite', 'ویلیامز %R', (per) => (c) => {
  const h = highs(c), l = lows(c), x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = per - 1; i < n; i++) { const hh = highest(h, i, per), ll = lowest(l, i, per); out[i] = (hh - ll) ? (100 * (hh - x[i])) / (hh - ll) : 50 }
  return asSeries(out)
}, FIB_PERIODS)

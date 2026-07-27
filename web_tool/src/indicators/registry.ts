// ============================================================================
// indicators/registry.ts — رجیستریِ اندیکاتور + کشِ تنبل + سازندهٔ IndicatorSnapshot@v1
// ----------------------------------------------------------------------------
// گره ۲ در webplan §۳. اینجا اندیکاتورهای موجودِ پروژه (indicators.ts) و اندیکاتورهای
// پیچیدهٔ کمیاب (complex.ts — Alligator/GMMA/Ichimoku، علیهِ اشتباهِ رایجِ #۳) در یک
// رجیستریِ واحد ثبت می‌شوند. سپس buildSnapshot() یک IndicatorSnapshot@v1 می‌سازد که:
//   • هر اندیکاتور را حداکثر یک‌بار برای یک (asset,tf,lastBarTime) حساب می‌کند (کشِ تنبل)،
//   • دو راهِ دسترسی می‌دهد: series()/last() عمومی + میدان‌های آمادهٔ پرکاربرد.
//
// ⚠️ Strangler Fig: این فایل *افزودنی* است. هیچ لایه‌ای هنوز مجبور نیست از آن استفاده
//    کند؛ مسیرِ /api/decision دست‌نخورده می‌ماند (برابریِ بیت‌به‌بیت با snapshot طلایی).
// ============================================================================

import type { Candle } from '../indicators'
import * as I from '../indicators'
import * as CX from './complex'
import { BANK } from './bank'
import {
  INDICATOR_SNAPSHOT_VERSION,
  type IndicatorDef,
  type IndicatorValue,
  type IndicatorSnapshot,
} from './contracts'

// ----------------------------------------------------------------------------
// ۱) تعریفِ اندیکاتورها. هر compute کلِ سری (یا ساختار) را برمی‌گرداند — بدون look-ahead
//    (چون همهٔ توابعِ زیرین فقط از دادهٔ گذشته/جاری استفاده می‌کنند).
// ----------------------------------------------------------------------------

function closesOf(c: Candle[]): number[] { return c.map(k => k.close) }

/** رجیستریِ سراسری: name → IndicatorDef. */
const REGISTRY = new Map<string, IndicatorDef<any>>()

function register<P extends Record<string, number>>(def: IndicatorDef<P>): void {
  REGISTRY.set(def.name, def as IndicatorDef<any>)
}

// --- اندیکاتورهای تک-سری روی close ---
register({ name: 'sma', defaults: { period: 20 }, paramKeys: ['period'], desc: 'میانگین متحرک ساده',
  compute: (c, p) => I.sma(closesOf(c), p.period) })
register({ name: 'ema', defaults: { period: 20 }, paramKeys: ['period'], desc: 'میانگین متحرک نمایی',
  compute: (c, p) => I.ema(closesOf(c), p.period) })
register({ name: 'rsi', defaults: { period: 14 }, paramKeys: ['period'], desc: 'شاخص قدرت نسبی',
  compute: (c, p) => I.rsi(closesOf(c), p.period) })
register({ name: 'zscore', defaults: { period: 20 }, paramKeys: ['period'], desc: 'Z-Score غلتان',
  compute: (c, p) => I.zscore(closesOf(c), p.period) })
register({ name: 'slope', defaults: { period: 20 }, paramKeys: ['period'], desc: 'شیبِ رگرسیونِ غلتان',
  compute: (c, p) => I.rollingSlope(closesOf(c), p.period) })
register({ name: 'kaufmanER', defaults: { period: 10 }, paramKeys: ['period'], desc: 'نسبتِ کاراییِ کافمن',
  compute: (c, p) => I.kaufmanER(closesOf(c), p.period) })

// --- اندیکاتورهای مبتنی بر کندل (OHLC) ---
register({ name: 'atr', defaults: { period: 14 }, paramKeys: ['period'], desc: 'میانگین دامنهٔ واقعی',
  compute: (c, p) => I.atr(c, p.period) })

// --- اندیکاتورهای چند-سری (ساختار) ---
register({ name: 'bollinger', defaults: { period: 20, mult: 2.0 }, paramKeys: ['period', 'mult'], desc: 'باندهای بولینگر',
  compute: (c, p) => {
    const b = I.bollinger(closesOf(c), p.period, p.mult)
    return { mid: b.mid, upper: b.upper, lower: b.lower } as Record<string, number[]>
  } })
register({ name: 'macd', defaults: { fast: 12, slow: 26, signal: 9 }, paramKeys: ['fast', 'slow', 'signal'], desc: 'MACD',
  compute: (c, p) => {
    const m = I.macd(closesOf(c), p.fast, p.slow, p.signal)
    return { macd: m.macd, signal: m.signal, hist: m.hist } as Record<string, number[]>
  } })
register({ name: 'stoch', defaults: { kPeriod: 14, dPeriod: 3 }, paramKeys: ['kPeriod', 'dPeriod'], desc: 'استوکاستیک',
  compute: (c, p) => {
    const s = I.stoch(c, p.kPeriod, p.dPeriod)
    return { k: s.k, d: s.d } as Record<string, number[]>
  } })
register({ name: 'adx', defaults: { period: 14 }, paramKeys: ['period'], desc: 'شاخصِ جهت‌دار میانگین',
  compute: (c, p) => {
    const a = I.adx(c, p.period)
    return { adx: a.adx, plusDI: a.plusDI, minusDI: a.minusDI } as Record<string, number[]>
  } })
register({ name: 'vortex', defaults: { period: 14 }, paramKeys: ['period'], desc: 'اندیکاتورِ ورتکس',
  compute: (c, p) => {
    const vo = I.vortex(c, p.period)
    return { viPlus: vo.viPlus, viMinus: vo.viMinus } as Record<string, number[]>
  } })

// --- اندیکاتورهای پیچیدهٔ کمیاب (complex.ts) — علیهِ اشتباهِ رایجِ #۳ ---
register({ name: 'alligator', defaults: {}, paramKeys: [], desc: 'الیگیتورِ بیل ویلیامز (SMMA شیفت‌دار)',
  compute: (c) => {
    const a = CX.alligator(c)
    return { jaw: a.jaw, teeth: a.teeth, lips: a.lips } as Record<string, number[]>
  } })
register({ name: 'ichimoku', defaults: {}, paramKeys: [], desc: 'ابرِ ایچیموکو',
  compute: (c) => {
    const k = CX.ichimoku(c)
    return { tenkan: k.tenkan, kijun: k.kijun, cloudTop: k.cloudTop, cloudBot: k.cloudBot } as Record<string, number[]>
  } })

// --- بانکِ گستردهٔ ۴۰۰+ اندیکاتور (bank.ts) — همه active:false (User Note) ---------
// ⚠️ ثبتِ این‌ها هزینهٔ محاسباتی ندارد: کشِ رجیستری «تنبل» است (خطِ seriesRaw) — تا وقتی
//    یک لایهٔ استراتژی صریحاً series(name)/last(name) را صدا نزند، compute اجرا نمی‌شود.
//    بنابراین مسیرِ /api/decision و برابریِ بیت‌به‌بیتِ snapshotِ طلایی دست‌نخورده می‌ماند.
//    این دقیقاً معنای «وجود دارند اما غیرفعال‌اند» را پیاده می‌کند.
// اگر نامی از قبل در رجیستریِ هسته باشد (مثلِ vortex)، نسخهٔ هسته حفظ می‌شود (بدونِ بازنویسی).
let bankRegistered = 0
for (const d of BANK) {
  if (REGISTRY.has(d.name)) continue // برخوردِ نام → نسخهٔ هستهٔ موجود اولویت دارد
  REGISTRY.set(d.name, d as IndicatorDef<any>)
  bankRegistered++
}
void bankRegistered

// ----------------------------------------------------------------------------
// ۲) سازندهٔ IndicatorSnapshot@v1 با کشِ تنبل (کلید = name+params+lastBarTime).
// ----------------------------------------------------------------------------

function paramKeyOf(def: IndicatorDef<any>, params: Record<string, number>): string {
  const merged = { ...def.defaults, ...params }
  return def.paramKeys.map(k => `${String(k)}=${merged[k as string]}`).join(',')
}

/** آخرین مقدارِ یک سری (number[]) با پرش از NaNهای انتها. */
function lastFinite(arr: number[]): number {
  for (let i = arr.length - 1; i >= 0; i--) {
    if (Number.isFinite(arr[i])) return arr[i]
  }
  return NaN
}

/**
 * ساختِ IndicatorSnapshot@v1 برای یک بُرشِ کندل.
 * کش تنبل است: تا وقتی series(name) صدا زده نشود، آن اندیکاتور حساب نمی‌شود.
 */
export function buildSnapshot(asset: string, tf: string, candles: Candle[]): IndicatorSnapshot {
  const n = candles.length
  const lastBarTime = n > 0 ? candles[n - 1].time : 0
  // کشِ محلیِ این snapshot (چون کلیدِ lastBarTime ثابت است، کلید فقط name+params لازم دارد).
  const cache = new Map<string, IndicatorValue>()

  function seriesRaw(name: string, params: Record<string, number> = {}): IndicatorValue | null {
    const def = REGISTRY.get(name)
    if (!def) return null
    const key = `${name}|${paramKeyOf(def, params)}`
    const hit = cache.get(key)
    if (hit !== undefined) return hit
    const merged = { ...def.defaults, ...params }
    const val = def.compute(candles, merged)
    cache.set(key, val)
    return val
  }

  function lastRaw(name: string, params: Record<string, number> = {}): number | null {
    const v = seriesRaw(name, params)
    if (v == null) return null
    if (typeof v === 'number') return v
    if (Array.isArray(v)) return lastFinite(v)
    // ساختار چند-سری: last() برای آن معنا ندارد → null (باید subseries گرفت).
    return null
  }

  /** آخرین مقدارِ یک زیرسریِ ساختاری (مثلِ adx.adx یا macd.hist). */
  function lastSub(name: string, sub: string, params: Record<string, number> = {}): number {
    const v = seriesRaw(name, params)
    if (v == null || typeof v === 'number' || Array.isArray(v)) return NaN
    const arr = (v as Record<string, number[]>)[sub]
    return Array.isArray(arr) ? lastFinite(arr) : NaN
  }

  const price = n > 0 ? candles[n - 1].close : NaN

  const snap: IndicatorSnapshot = {
    v: INDICATOR_SNAPSHOT_VERSION,
    asset, tf, lastBarTime, barCount: n,
    series: (name, params) => seriesRaw(name, params),
    last: (name, params) => lastRaw(name, params),
    price,
    get atr() { return lastRaw('atr') ?? NaN },
    get ema20() { return lastRaw('ema', { period: 20 }) ?? NaN },
    get ema50() { return lastRaw('ema', { period: 50 }) ?? NaN },
    get ema100() { return lastRaw('ema', { period: 100 }) ?? NaN },
    get ema200() { return lastRaw('ema', { period: 200 }) ?? NaN },
    get rsi14() { return lastRaw('rsi', { period: 14 }) ?? NaN },
    get adx() { return lastSub('adx', 'adx') },
    get macdHist() { return lastSub('macd', 'hist') },
  }
  return snap
}

/** فهرستِ نام‌های رجیستری‌شده (برای کاوشگرِ اندیکاتور P8 و مستندات). */
export function listIndicators(): {
  name: string; defaults: Record<string, number>; desc?: string
  active?: boolean; category?: string; source?: string
}[] {
  return Array.from(REGISTRY.values()).map(d => ({
    name: d.name, defaults: d.defaults, desc: d.desc,
    // اندیکاتورهای هستهٔ قدیمی فیلدِ active ندارند ⇒ فعال تلقی می‌شوند (لایه‌ها مصرفشان می‌کنند).
    active: d.active === undefined ? true : d.active,
    category: d.category, source: d.source,
  }))
}

/** شمارشِ رجیستری برای گزارش/تستِ سلامت. */
export function registrySize(): number { return REGISTRY.size }

/** آیا اندیکاتوری با این نام در رجیستری وجود دارد؟ (برای فعال‌سازیِ لایه‌محور) */
export function hasIndicator(name: string): boolean { return REGISTRY.has(name) }

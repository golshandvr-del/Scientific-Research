// ============================================================================
// scanner/scanner.ts — موتورِ کاوشگرِ اندیکاتور  [webplan P8 · ایدهٔ #۶]
// ----------------------------------------------------------------------------
// گرهِ پژوهشیِ مستقل. روی تاریخچهٔ کندلِ ذخیره‌شده اجرا می‌شود و برای هر اندیکاتورِ
// رجیستری‌شده (شاملِ اندیکاتورهای پیچیدهٔ کمیاب مثل Alligator/Ichimoku) می‌سنجد که
// آیا مقدارِ آن اندیکاتور در بارِ t، «حرکتِ بعدیِ قیمت» (بازدهِ t→t+horizon) را
// پیش‌بینی می‌کند یا نه — با دو سنجهٔ مکمل:
//   1) همبستگیِ رتبه‌ایِ اسپیرمن (مقاوم به outlier) + p-value آماری،
//   2) تفاوتِ میانگینِ بازدهِ صدکِ بالا و پایینِ اندیکاتور (spread) — سنجهٔ عملیِ «فیلترِ احیا».
//
// خروجی ScanReport@v1 است و «فقط برای AI/تحقیق». هیچ تصمیمِ سایتی را عوض نمی‌کند.
// این مستقیماً علیهِ اشتباهِ رایجِ #۳ است: به‌جای حدسِ چند اندیکاتورِ ساده، همهٔ
// رجیستری به‌طورِ سیستماتیک روی داده آزموده می‌شوند تا کاندیدِ فیلترِ نجاتِ لایه پیدا شود.
// ============================================================================

import type { Candle } from '../indicators'
import { buildSnapshot, listIndicators } from '../indicators/registry'
import {
  SCAN_REPORT_VERSION,
  SCAN_P_THRESHOLD,
  SCAN_MIN_SAMPLES,
  SCAN_MIN_SPREAD_PCT,
  SCAN_TOP_PCT,
  SCAN_BOT_PCT,
  type IndicatorEdge,
  type ScanReport,
  type EdgeDirection,
} from './contracts'

// ----------------------------------------------------------------------------
// ابزارهای آماریِ خالص (بدونِ وابستگی؛ سازگارِ Cloudflare/Termux).
// ----------------------------------------------------------------------------

/** رتبه‌بندیِ اسپیرمن با میانگینِ رتبهٔ گره‌ها (ties). */
function ranks(x: number[]): number[] {
  const idx = x.map((v, i) => [v, i] as [number, number])
  idx.sort((a, b) => a[0] - b[0])
  const r = new Array<number>(x.length)
  let i = 0
  while (i < idx.length) {
    let j = i
    while (j + 1 < idx.length && idx[j + 1][0] === idx[i][0]) j++
    const avgRank = (i + j) / 2 + 1 // میانگینِ رتبه برای گره‌ها (۱-مبنا)
    for (let k = i; k <= j; k++) r[idx[k][1]] = avgRank
    i = j + 1
  }
  return r
}

/** پیرسونِ روی رتبه‌ها = اسپیرمن. */
function pearson(a: number[], b: number[]): number {
  const n = a.length
  if (n < 3) return 0
  let ma = 0, mb = 0
  for (let i = 0; i < n; i++) { ma += a[i]; mb += b[i] }
  ma /= n; mb /= n
  let num = 0, da = 0, db = 0
  for (let i = 0; i < n; i++) {
    const xa = a[i] - ma, xb = b[i] - mb
    num += xa * xb; da += xa * xa; db += xb * xb
  }
  const den = Math.sqrt(da * db)
  return den > 0 ? num / den : 0
}

function spearman(x: number[], y: number[]): number {
  return pearson(ranks(x), ranks(y))
}

/**
 * p-value دو-دامنهٔ تقریبی برای ضریبِ همبستگی از راهِ t-stat و تقریبِ نرمالِ دم.
 * t = r·sqrt(n-2)/sqrt(1-r²)؛ برای n بزرگ، توزیعِ t به نرمالِ استاندارد میل می‌کند.
 */
function corrPValue(r: number, n: number): number {
  if (n < 4 || !Number.isFinite(r)) return 1
  const rr = Math.min(0.999999, Math.max(-0.999999, r))
  const t = Math.abs(rr) * Math.sqrt((n - 2) / (1 - rr * rr))
  // تقریبِ دمِ نرمال (Zelen & Severo) — دو-دامنه.
  const z = t
  const p1 = normalTail(z)
  return Math.min(1, 2 * p1)
}

/** دمِ راستِ نرمالِ استاندارد P(Z>z) با تقریبِ Abramowitz-Stegun 26.2.17. */
function normalTail(z: number): number {
  if (z < 0) return 1 - normalTail(-z)
  const t = 1 / (1 + 0.2316419 * z)
  const d = 0.3989422804014327 * Math.exp(-z * z / 2)
  const p = d * t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
  return p
}

/** میانگینِ ساده. */
function mean(a: number[]): number {
  if (a.length === 0) return 0
  let s = 0; for (const v of a) s += v
  return s / a.length
}

/** صدکِ q (۰..۱) از یک آرایهٔ مرتب‌نشده (کپیِ داخلی می‌سازد). */
function quantile(a: number[], q: number): number {
  if (a.length === 0) return NaN
  const s = a.slice().sort((x, y) => x - y)
  const pos = (s.length - 1) * q
  const lo = Math.floor(pos), hi = Math.ceil(pos)
  if (lo === hi) return s[lo]
  return s[lo] + (s[hi] - s[lo]) * (pos - lo)
}

// ----------------------------------------------------------------------------
// استخراجِ سریِ عددیِ یک اندیکاتور (تک-سری یا یک زیرسریِ مشخص) از snapshot.
// ----------------------------------------------------------------------------
function extractSeries(
  snap: ReturnType<typeof buildSnapshot>,
  name: string,
  params: Record<string, number>,
  sub?: string,
): number[] | null {
  const v = snap.series(name, params)
  if (v == null) return null
  if (Array.isArray(v)) return v as number[]
  if (typeof v === 'object') {
    const rec = v as Record<string, number[]>
    if (sub && Array.isArray(rec[sub])) return rec[sub]
    return null
  }
  return null // اسکالر — برای کاوشِ سری بی‌فایده
}

/** زیرسری‌های شناخته‌شدهٔ اندیکاتورهای چند-سری (تا کاوشگر آن‌ها را هم بسنجد). */
const MULTI_SUBS: Record<string, string[]> = {
  bollinger: ['mid', 'upper', 'lower'],
  macd: ['macd', 'signal', 'hist'],
  stoch: ['k', 'd'],
  adx: ['adx', 'plusDI', 'minusDI'],
  vortex: ['viPlus', 'viMinus'],
  alligator: ['jaw', 'teeth', 'lips'],
  ichimoku: ['tenkan', 'kijun', 'cloudTop', 'cloudBot'],
}

// ----------------------------------------------------------------------------
// کاوشِ یک سریِ اندیکاتور در برابرِ بازدهِ آینده.
// ----------------------------------------------------------------------------
function scanOne(
  indicator: string,
  params: Record<string, number>,
  values: number[],
  fwdRet: number[], // fwdRet[i] = بازدهِ بار i تا i+horizon (٪)؛ هم‌طول با values
  sub: string | undefined,
): IndicatorEdge | null {
  // جفت‌های معتبر (هر دو Finite).
  const xs: number[] = [], ys: number[] = []
  for (let i = 0; i < values.length; i++) {
    const xv = values[i], yv = fwdRet[i]
    if (Number.isFinite(xv) && Number.isFinite(yv)) { xs.push(xv); ys.push(yv) }
  }
  const n = xs.length
  if (n < SCAN_MIN_SAMPLES) return null

  const rho = spearman(xs, ys)
  const p = corrPValue(rho, n)

  // سطل‌های صدکِ بالا/پایینِ اندیکاتور.
  const topThr = quantile(xs, SCAN_TOP_PCT)
  const botThr = quantile(xs, SCAN_BOT_PCT)
  const topRets: number[] = [], botRets: number[] = []
  for (let i = 0; i < n; i++) {
    if (xs[i] >= topThr) topRets.push(ys[i])
    if (xs[i] <= botThr) botRets.push(ys[i])
  }
  const topBucketRet = mean(topRets)
  const botBucketRet = mean(botRets)
  const spread = topBucketRet - botBucketRet

  let direction: EdgeDirection = 'NEUTRAL'
  if (p < SCAN_P_THRESHOLD && Math.abs(spread) >= SCAN_MIN_SPREAD_PCT) {
    direction = spread > 0 ? 'BULLISH' : 'BEARISH'
  }
  const isCandidate = direction !== 'NEUTRAL'

  return {
    indicator, sub, params,
    spearman: round(rho, 4),
    pValue: round(p, 5),
    n,
    topBucketRet: round(topBucketRet, 4),
    botBucketRet: round(botBucketRet, 4),
    spread: round(spread, 4),
    direction,
    isCandidate,
  }
}

function round(x: number, d: number): number {
  if (!Number.isFinite(x)) return x
  const m = Math.pow(10, d)
  return Math.round(x * m) / m
}

// ----------------------------------------------------------------------------
// نقطهٔ ورودِ عمومی: کاوشِ کاملِ رجیستری روی یک مجموعهٔ کندل.
// ----------------------------------------------------------------------------
/**
 * @param asset  نامِ دارایی (فقط برای گزارش).
 * @param tf     تایم‌فریم (فقط برای گزارش).
 * @param candles تاریخچهٔ کندلِ بسته‌شده (به ترتیبِ زمانی صعودی).
 * @param horizon افقِ بازدهِ آینده (چند کندل جلوتر). پیش‌فرض ۵.
 */
export function scanIndicators(
  asset: string,
  tf: string,
  candles: Candle[],
  horizon = 5,
): ScanReport {
  const n = candles.length
  const snap = buildSnapshot(asset, tf, candles)

  // بازدهِ آینده به ٪: از close بارِ i تا close بارِ i+horizon. بارهای انتهایی NaN.
  const fwdRet = new Array<number>(n)
  for (let i = 0; i < n; i++) {
    const fut = i + horizon
    if (fut < n && candles[i].close > 0) {
      fwdRet[i] = ((candles[fut].close - candles[i].close) / candles[i].close) * 100
    } else {
      fwdRet[i] = NaN
    }
  }

  const edges: IndicatorEdge[] = []
  for (const def of listIndicators()) {
    const subs = MULTI_SUBS[def.name]
    if (subs) {
      for (const sub of subs) {
        const series = extractSeries(snap, def.name, def.defaults, sub)
        if (!series) continue
        const e = scanOne(def.name, def.defaults, series, fwdRet, sub)
        if (e) edges.push(e)
      }
    } else {
      const series = extractSeries(snap, def.name, def.defaults, undefined)
      if (!series) continue
      const e = scanOne(def.name, def.defaults, series, fwdRet, undefined)
      if (e) edges.push(e)
    }
  }

  // مرتب‌سازیِ نزولی بر اساسِ «قدرتِ عملیِ فیلتر» = |spread| با اولویتِ معناداری.
  edges.sort((a, b) => {
    const sa = Math.abs(a.spread) * (a.isCandidate ? 1 : 0.001)
    const sb = Math.abs(b.spread) * (b.isCandidate ? 1 : 0.001)
    return sb - sa
  })

  const candidates = edges.filter(e => e.isCandidate)
  const note = candidates.length > 0
    ? `${candidates.length} کاندیدِ فیلترِ احیا یافت شد؛ قوی‌ترین: ${candidates[0].indicator}` +
      `${candidates[0].sub ? '.' + candidates[0].sub : ''} (spread=${candidates[0].spread}٪, p=${candidates[0].pValue}).`
    : `هیچ کاندیدِ معناداری در افقِ ${horizon} کندل یافت نشد (n=${n}). داده کافی است اما لبه‌ای دیده نشد.`

  return {
    v: SCAN_REPORT_VERSION,
    asset, tf, horizon, barCount: n,
    generatedAt: Date.now(),
    edges, candidates, note,
  }
}

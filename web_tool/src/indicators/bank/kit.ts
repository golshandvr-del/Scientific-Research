// ============================================================================
// indicators/bank/kit.ts — کیتِ مشترکِ بانکِ اندیکاتور (helperها + factoryِ ثبت)
// ----------------------------------------------------------------------------
// این ماژول تمامِ کمک‌توابعِ ریاضیِ *بدونِ look-ahead* و یک factory به‌نامِ makeKit()
// را صادر می‌کند. هر فایلِ دسته (trend/momentum/…) یک kit مستقل می‌گیرد، اندیکاتورهای
// خودش را ثبت می‌کند و آرایهٔ حاصل را export می‌کند؛ سپس bank.ts همه را concat می‌کند.
//
// چرا factory؟ تا def/pat/expandPeriodFamily روی «آرایهٔ محلیِ همان فایل» ببندند و
// هر دسته کاملاً مستقل و قابلِ‌تست باشد، بدونِ حالتِ سراسریِ مشترک.
// ============================================================================

import type { Candle } from '../../indicators'
import type { IndicatorDef, IndicatorValue } from '../contracts'

// ---------------------------------------------------------------------------
// کمک‌توابعِ پایه (بدونِ look-ahead) — فقط از دادهٔ تا اندیسِ i استفاده می‌کنند.
// ---------------------------------------------------------------------------
export const NaNArr = (n: number): number[] => new Array<number>(n).fill(NaN)

export const closes = (c: Candle[]): number[] => c.map(k => k.close)
export const highs = (c: Candle[]): number[] => c.map(k => k.high)
export const lows = (c: Candle[]): number[] => c.map(k => k.low)
export const opens = (c: Candle[]): number[] => c.map(k => k.open)
export const vols = (c: Candle[]): number[] => c.map(k => k.volume)

/** میانگینِ متحرکِ ساده روی یک آرایهٔ دلخواه. */
export function smaArr(x: number[], p: number): number[] {
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
export function emaArr(x: number[], p: number): number[] {
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
export function rmaArr(x: number[], p: number): number[] {
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
export function wmaArr(x: number[], p: number): number[] {
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
export function stdArr(x: number[], p: number): number[] {
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

export const highest = (x: number[], i: number, p: number): number => {
  let m = -Infinity; for (let k = 0; k < p && i - k >= 0; k++) if (x[i - k] > m) m = x[i - k]; return m
}
export const lowest = (x: number[], i: number, p: number): number => {
  let m = Infinity; for (let k = 0; k < p && i - k >= 0; k++) if (x[i - k] < m) m = x[i - k]; return m
}

export const asSeries = (x: number[]): IndicatorValue => x

/** True Range سری (بدونِ look-ahead؛ نیازمندِ بستهٔ قبلی). */
export function trArr(c: Candle[]): number[] {
  const n = c.length, tr = NaNArr(n)
  for (let i = 1; i < n; i++) tr[i] = Math.max(c[i].high - c[i].low, Math.abs(c[i].high - c[i - 1].close), Math.abs(c[i].low - c[i - 1].close))
  return tr
}

// کمک‌توابعِ ساختارِ کندل (برای دستهٔ الگوهای کندلی)
export const body = (k: Candle): number => Math.abs(k.close - k.open)
export const range = (k: Candle): number => k.high - k.low
export const upSh = (k: Candle): number => k.high - Math.max(k.open, k.close)
export const dnSh = (k: Candle): number => Math.min(k.open, k.close) - k.low
export const isBull = (k: Candle): boolean => k.close > k.open
export const isBear = (k: Candle): boolean => k.close < k.open

// دوره‌های غیررندِ فیبوناچی/لوکاس (رفعِ اشتباهِ رایج #۷ — پرهیز از اعدادِ رند)
export const FIB_PERIODS = [3, 5, 8, 13, 21, 34, 55, 89, 144, 233]
export const LUCAS_PERIODS = [4, 7, 11, 18, 29, 47, 76, 123, 199]

// ---------------------------------------------------------------------------
// factoryِ کیتِ ثبت: هر دسته یک نمونهٔ مستقل می‌گیرد.
// ---------------------------------------------------------------------------
export interface BankKit {
  /** آرایهٔ اندیکاتورهای ثبت‌شده در این دسته. */
  items: IndicatorDef<any>[]
  /** ثبتِ یک اندیکاتورِ تک-سری با active:false. */
  def: (
    name: string, category: string, source: string,
    defaults: Record<string, number>, paramKeys: string[], desc: string,
    compute: (c: Candle[], p: any) => IndicatorValue,
  ) => void
  /** ثبتِ یک الگوی کندلی (بدونِ پارامتر؛ خروجی ±100/0). */
  pat: (name: string, desc: string, fn: (c: Candle[], i: number) => number) => void
  /** بسطِ یک خانوادهٔ تک-پارامتری (period) به چند instance با دوره‌های غیررند. */
  expandPeriodFamily: (
    baseName: string, category: string, source: string, desc: string,
    build: (period: number) => (c: Candle[]) => IndicatorValue,
    periods: number[],
  ) => void
}

/** یک kit تازه با آرایهٔ محلیِ خودش می‌سازد. */
export function makeKit(): BankKit {
  const items: IndicatorDef<any>[] = []
  return {
    items,
    def(name, category, source, defaults, paramKeys, desc, compute) {
      items.push({ name, category, source, active: false, defaults, paramKeys, desc, compute })
    },
    pat(name, desc, fn) {
      items.push({
        name, category: 'pattern', source: 'deep-web', active: false,
        defaults: {}, paramKeys: [], desc,
        compute: (c: Candle[]) => {
          const n = c.length, out = NaNArr(n)
          for (let i = 0; i < n; i++) out[i] = i >= 3 ? fn(c, i) : 0
          return asSeries(out)
        },
      })
    },
    expandPeriodFamily(baseName, category, source, desc, build, periods) {
      for (const per of periods) {
        items.push({
          name: `${baseName}_${per}`, category, source, active: false,
          defaults: { period: per }, paramKeys: ['period'],
          desc: `${desc} — دورهٔ غیررندِ ${per}`,
          compute: (c: Candle[]) => build(per)(c),
        })
      }
    },
  }
}

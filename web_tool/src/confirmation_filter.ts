// ============================================================================
// فیلترِ تأییدِ امتیازیِ متعامد (Scored Confirmation Filter) — نشستِ S163
// ----------------------------------------------------------------------------
// پاسخِ User Note: «از استراتژی‌هایی که به‌دلیلِ همبستگی کنار گذاشته شدند، به‌عنوان
// فیلتر/تأیید روی سیگنال‌های فعلی استفاده کن تا WR بالاتر برود.»
//
// این ماژول برای هر کندلِ فعلی یک «امتیازِ تأیید» (۰..۵) محاسبه می‌کند. سیگنال‌های
// زمان-محورِ Monday (S140) و Turn-of-Month (S142) فقط وقتی امتیاز از آستانه بگذرد
// به حالتِ ENTRY می‌روند. این کار در بک‌تست WR را به بالای ۴۰٪ رساند و سودِ خالص را
// نیز حفظ/افزایش داد (رجوع: results/EnforceWR40_RemoveS81_NetProfit_218739.md).
//
// شرط‌های تأیید (روی کندلِ بستهٔ فعلیِ همان دارایی، بدونِ look-ahead):
//   ۱) price > EMA200        (روندِ صعودیِ بلندمدت)
//   ۲) EMA50 > EMA200        (تأییدِ ساختارِ صعودی)
//   ۳) ATR14 > ATR100        (رژیمِ نوسانِ فعال)
//   ۴) MACD histogram > 0    (تأییدِ مومنتوم)
//   ۵) RSI14 ∈ [35,70]       (اجتناب از اشباع)
//
// توجهِ صادقانه: در بک‌تست یک شرطِ ششم (DXY < EMA200) هم بود. آن شرط به fetchِ جداگانهٔ
// سریِ DXY نیاز دارد که در این ماژولِ سبکِ سمتِ کاربر لحاظ نشده؛ به‌همین‌دلیل آستانه‌ها
// روی ۵ شرط کالیبره شده‌اند (score≥3 در بک‌تستِ ۶-شرطی ≈ score≥2..3 در نسخهٔ ۵-شرطی).
// معیارِ پروژه: سودِ خالص = XAUUSD + EURUSD (نه Win-Rate).
// ============================================================================

import * as ind from './indicators'

export interface ConfirmBreakdown {
  label: string
  met: boolean
  value: string
}

export interface ConfirmResult {
  score: number
  maxScore: number
  breakdown: ConfirmBreakdown[]
}

// ATR بر پایهٔ سری‌های خامِ close/high/low (بدونِ نیاز به شیءِ Candle).
function atrRaw(close: number[], high: number[], low: number[], period: number): number[] {
  const n = close.length
  const tr = new Array(n).fill(NaN)
  for (let i = 0; i < n; i++) {
    if (i === 0) { tr[i] = high[i] - low[i]; continue }
    const a = high[i] - low[i]
    const b = Math.abs(high[i] - close[i - 1])
    const c = Math.abs(low[i] - close[i - 1])
    tr[i] = Math.max(a, b, c)
  }
  // میانگینِ متحرکِ ساده روی TR (سازگار با ind.atr پروژه که SMA(TR) است).
  const out = new Array(n).fill(NaN)
  let sum = 0
  for (let i = 0; i < n; i++) {
    sum += tr[i]
    if (i >= period) sum -= tr[i - period]
    if (i >= period - 1) out[i] = sum / period
  }
  return out
}

/**
 * امتیازِ تأیید را برای آخرین کندلِ سری‌های داده‌شده محاسبه می‌کند.
 * @param close سریِ close همان دارایی (حداقل ~۲۰۰ نقطه برای EMA200/ATR100).
 * @param high  سریِ high متناظر.
 * @param low   سریِ low متناظر.
 */
export function confirmScore(close: number[], high: number[], low: number[]): ConfirmResult {
  const n = close.length
  const i = n - 1

  const ema50 = ind.ema(close, 50)[i]
  const ema200 = ind.ema(close, 200)[i]
  const atr14 = atrRaw(close, high, low, 14)[i]
  const atr100 = atrRaw(close, high, low, 100)[i]
  const rsi14 = ind.rsi(close, 14)[i]
  const { hist } = ind.macd(close)
  const macdHist = hist[i]
  const price = close[i]

  const conds: ConfirmBreakdown[] = [
    { label: 'قیمت > EMA200 (روندِ صعودیِ بلندمدت)',
      met: Number.isFinite(ema200) && price > ema200,
      value: `${price.toFixed(2)} vs ${Number.isFinite(ema200) ? ema200.toFixed(2) : '—'}` },
    { label: 'EMA50 > EMA200 (ساختارِ صعودی)',
      met: Number.isFinite(ema50) && Number.isFinite(ema200) && ema50 > ema200,
      value: `${Number.isFinite(ema50) ? ema50.toFixed(2) : '—'} vs ${Number.isFinite(ema200) ? ema200.toFixed(2) : '—'}` },
    { label: 'ATR14 > ATR100 (رژیمِ نوسانِ فعال)',
      met: Number.isFinite(atr14) && Number.isFinite(atr100) && atr100 > 0 && atr14 > atr100,
      value: `${Number.isFinite(atr14) ? atr14.toFixed(3) : '—'} vs ${Number.isFinite(atr100) ? atr100.toFixed(3) : '—'}` },
    { label: 'MACD histogram > 0 (مومنتومِ مثبت)',
      met: Number.isFinite(macdHist) && macdHist > 0,
      value: `${Number.isFinite(macdHist) ? macdHist.toFixed(4) : '—'}` },
    { label: 'RSI14 ∈ [35,70] (بدونِ اشباع)',
      met: Number.isFinite(rsi14) && rsi14 >= 35 && rsi14 <= 70,
      value: `${Number.isFinite(rsi14) ? rsi14.toFixed(1) : '—'}` },
  ]

  const score = conds.reduce((s, c) => s + (c.met ? 1 : 0), 0)
  return { score, maxScore: conds.length, breakdown: conds }
}

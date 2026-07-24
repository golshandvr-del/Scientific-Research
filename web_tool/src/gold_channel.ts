// ============================================================================
// XAUUSD Channels — position-in-channel (S219) — ماژولِ مشترکِ ماژولار
// ----------------------------------------------------------------------------
// منبعِ کشف: strategies/s219_brooks_channels.py + strategies/s219_finalize.py +
//   results/S219_BrooksChannels_Xauusd_M5M15M30H4_293236_46.md
//   (فصلِ ۱۵ کتابِ Al Brooks: «Channels»)
//
// تزِ محوریِ فصلِ ۱۵ (Al Brooks):
//   «A channel is bounded by a trend line and a parallel trend channel line…
//    You should look to BUY NEAR THE BOTTOM OF THE CHANNEL, buy below the lows
//    of bars, at the moving average where the entry is not too close to the top
//    of the channel. Bull channels usually have at least three pushes up.»
//   ⇒ بُعدِ نو نسبت به S215 (خطِ روند): «موقعیتِ نسبیِ قیمت داخلِ کانالِ موازی».
//     در روندِ صعودی فقط در نیمهٔ پایینِ کانال (pos≤posMax) + pullback خرید می‌کنیم؛
//     نزدیکِ سقفِ کانال خرید نمی‌کنیم (micro sell vacuum).
//
// ⚠️ ماژولار: این فایل فقط «موتورِ خالصِ» position-in-channel را می‌دهد. هر کارت
//    (M5/M15/M30/H4) پیکربندیِ اثبات‌شدهٔ مخصوصِ خودش را (سهمِ مستقلِ WF-4/4 از
//    s219_finalize) می‌گیرد؛ افزودن/تغییرِ یک کارت بقیه را دست نمی‌زند.
//
// 🎯 قانونِ شمارهٔ ۱ پروژه: هدف فقط «سودِ خالصِ بیشتر». این لایه فقط XAUUSD LONG
//    است (بک‌تست روی EURUSD صفر لبه، و SHORT هیچ گیت‌پاسی نداد ⇒ مختصِ طلا/صعودی).
// ============================================================================

import * as ind from './indicators'
import type { Candle } from './indicators'

// ---------------------------------------------------------------------------
// پیکربندیِ اثبات‌شدهٔ هر تایم‌فریم (برندهٔ سهمِ مستقلِ WF-4/4 در s219_finalize).
//   منبع: results/_s219_finalize.json + _s219_channels_xau.json
//   H1 عمداً نیست (پنجرهٔ walk-forwardِ سهمِ مستقلش منفی شد ⇒ رد).
// ---------------------------------------------------------------------------
export interface ChannelConfig {
  id: string
  tfFa: string
  emaFast: number
  emaSlow: number
  k: number                  // نیم-پنجرهٔ swing-pivot
  posMax: number             // سقفِ موقعیتِ نسبیِ مجاز برای خرید (0.5 = فقط نیمهٔ پایین)
  maxGap: number             // حداکثر فاصلهٔ دو pivotِ سازندهٔ خط (کندل)
  slPip: number
  tpPip: number
  maxHoldBars: number
  indepNet: number           // سهمِ مستقلِ اثبات‌شده ($) — مستندسازیِ داخلی
  indepWr: number            // WR سهمِ مستقل (٪)
}

export const CHANNEL_CFG: Record<string, ChannelConfig> = {
  'XAUUSD-M5':  { id: 'XAUUSD-M5',  tfFa: 'M5 (پنج‌دقیقه‌ای)',   emaFast: 10, emaSlow: 30, k: 5, posMax: 0.6, maxGap: 40, slPip: 150, tpPip: 300, maxHoldBars: 96, indepNet: 3015, indepWr: 45.8 },
  'XAUUSD-M15': { id: 'XAUUSD-M15', tfFa: 'M15 (پانزده‌دقیقه‌ای)', emaFast: 20, emaSlow: 50, k: 3, posMax: 0.4, maxGap: 80, slPip: 200, tpPip: 400, maxHoldBars: 48, indepNet: 4028, indepWr: 50.1 },
  'XAUUSD-M30': { id: 'XAUUSD-M30', tfFa: 'M30 (سی‌دقیقه‌ای)',   emaFast: 10, emaSlow: 30, k: 3, posMax: 0.4, maxGap: 80, slPip: 150, tpPip: 300, maxHoldBars: 32, indepNet: 4457, indepWr: 47.6 },
  'XAUUSD-H4':  { id: 'XAUUSD-H4',  tfFa: 'H4 (چهارساعته)',      emaFast: 10, emaSlow: 30, k: 5, posMax: 0.6, maxGap: 40, slPip: 200, tpPip: 400, maxHoldBars: 16, indepNet: 2911, indepWr: 58.3 },
}

const PIP = 0.1              // طلا: ۱ pip = ۰.۱ واحدِ قیمت

export type ChannelState = 'ENTRY' | 'APPROACHING' | 'NEUTRAL'

export interface ChannelResult {
  state: ChannelState
  hasChannel: boolean
  lowerLine: number          // خطِ روندِ پایینِ کانال در t
  upperLine: number          // خطِ کانالِ موازیِ بالا در t
  posInChannel: number       // موقعیتِ نسبیِ close داخلِ کانال [0..1]
  slope: number
  pivot1Idx: number
  pivot2Idx: number
  gapBars: number
  regimeUp: boolean
  atr: number
  bullBar: boolean
  pullback: boolean          // low[t] < low[t-1]
  isRange: boolean
  slDist: number
  tpDist: number
  reason: string
}

// swing_pivots — بازتولیدِ دقیقِ نسخهٔ پایتونِ s172 (اکیداً بزرگ‌تر/کوچک‌تر از k همسایه).
export function swingPivots(high: number[], low: number[], k: number): { sh: boolean[]; sl: boolean[] } {
  const n = high.length
  const sh = new Array<boolean>(n).fill(false)
  const sl = new Array<boolean>(n).fill(false)
  for (let i = k; i < n - k; i++) {
    let isHigh = true, isLow = true
    for (let j = 1; j <= k; j++) {
      if (!(high[i] > high[i - j] && high[i] > high[i + j])) isHigh = false
      if (!(low[i] < low[i - j] && low[i] < low[i + j])) isLow = false
      if (!isHigh && !isLow) break
    }
    sh[i] = isHigh
    sl[i] = isLow
  }
  return { sh, sl }
}

/** قیدِ ضدِ رنج (Brooks): ۳ کندلِ اخیر «large and almost entirely overlapping». */
function isRange(high: number[], low: number[], t: number, lb = 3): boolean {
  if (t < lb) return false
  let hiMax = -Infinity, loMin = Infinity, indiv = 0
  for (let i = t - lb + 1; i <= t; i++) {
    hiMax = Math.max(hiMax, high[i]); loMin = Math.min(loMin, low[i])
    indiv += (high[i] - low[i])
  }
  const span = hiMax - loMin
  if (span <= 0) return true
  return (indiv / span) >= 2.3
}

// ---------------------------------------------------------------------------
// computeChannel — موتورِ خالصِ تشخیصِ «خرید در نیمهٔ پایینِ کانالِ صعودی» (LONG).
//   ارزیابی روی آخرین کندلِ بسته‌شده (t=n-1)؛ ورودِ واقعی next-open (معادلِ shift(1)).
// ---------------------------------------------------------------------------
export function computeChannel(
  open: number[], high: number[], low: number[], close: number[],
  cfg: ChannelConfig,
): ChannelResult {
  const n = close.length
  const empty: ChannelResult = {
    state: 'NEUTRAL', hasChannel: false, lowerLine: NaN, upperLine: NaN,
    posInChannel: NaN, slope: NaN, pivot1Idx: -1, pivot2Idx: -1, gapBars: 0,
    regimeUp: false, atr: NaN, bullBar: false, pullback: false, isRange: false,
    slDist: cfg.slPip * PIP, tpDist: cfg.tpPip * PIP,
    reason: 'دادهٔ کافی برای ساختِ کانال نیست.',
  }
  if (n < cfg.emaSlow + cfg.k + 5) return empty

  const candles: Candle[] = close.map((cl, i) => ({
    time: i, open: open[i], high: high[i], low: low[i], close: cl, volume: 0,
  }))
  const atrArr = ind.atr(candles, 14)
  const ef = ind.ema(close, cfg.emaFast)
  const es = ind.ema(close, cfg.emaSlow)
  const { sl: slPiv } = swingPivots(high, low, cfg.k)

  const piv: number[] = []
  for (let i = 0; i < n; i++) if (slPiv[i]) piv.push(i)

  const t = n - 1
  const confirmed = piv.filter(p => p + cfg.k <= t)
  if (confirmed.length < 2) return { ...empty, reason: 'هنوز دو کفِ ساختاریِ تأییدشده برای رسمِ کانال نداریم.' }

  const i1 = confirmed[confirmed.length - 2]
  const i2 = confirmed[confirmed.length - 1]
  const gap = i2 - i1
  const atr = atrArr[t]
  const regimeUp = ef[t] > es[t]

  if (gap <= 0 || gap > cfg.maxGap || !isFinite(atr) || atr <= 0) {
    return {
      ...empty, gapBars: gap, regimeUp, atr,
      reason: gap > cfg.maxGap
        ? `دو کفِ اخیر خیلی دور از هم‌اند (${gap} کندل > سقفِ ${cfg.maxGap})؛ کانال دیگر «تازه» نیست.`
        : 'شرایطِ ساختِ کانالِ معتبر فراهم نیست.',
    }
  }

  // خطِ پایینِ کانال از دو کف؛ خطِ بالا موازی به بالاترین high بینِ دو pivot.
  const m = (low[i2] - low[i1]) / (i2 - i1)
  const lowerT = low[i2] + m * (t - i2)
  let hiMax = -Infinity
  for (let i = i1; i <= i2; i++) hiMax = Math.max(hiMax, high[i])
  // فاصلهٔ عمودیِ کانال = بیشینهٔ (high − خطِ پایین) روی بازهٔ دو pivot.
  let chWidth = 0
  for (let i = i1; i <= i2; i++) {
    const lineI = low[i2] + m * (i - i2)
    chWidth = Math.max(chWidth, high[i] - lineI)
  }
  const upperT = lowerT + chWidth
  const pos = chWidth > 0 ? (close[t] - lowerT) / chWidth : NaN

  const validUpChannel = low[i2] > low[i1] && m > 0 && regimeUp && chWidth > 0
  const bullBar = close[t] >= open[t]
  const pullback = t >= 1 && low[t] < low[t - 1]
  const rng = isRange(high, low, t)

  const base: ChannelResult = {
    ...empty, hasChannel: validUpChannel, lowerLine: lowerT, upperLine: upperT,
    posInChannel: pos, slope: m, pivot1Idx: i1, pivot2Idx: i2, gapBars: gap,
    regimeUp, atr, bullBar, pullback, isRange: rng,
  }

  if (!validUpChannel) {
    return {
      ...base, state: 'NEUTRAL',
      reason: !regimeUp
        ? 'روندِ کلان صعودی نیست (EMAِ تند زیرِ EMAِ کند)؛ ستاپِ «خرید در کفِ کانالِ صعودی» غیرفعال است.'
        : 'دو کفِ اخیر یک کانالِ صعودیِ معتبر (کفِ بالاتر + شیبِ مثبت + عرضِ مثبت) نمی‌سازند.',
    }
  }

  const posPct = (pos * 100)
  // ---- ماشهٔ ENTRY: نیمهٔ پایینِ کانال + pullback + کندلِ صعودی + غیرِرنج ----
  if (pos <= cfg.posMax && pullback && bullBar && !rng) {
    return {
      ...base, state: 'ENTRY',
      reason: `قیمت در نیمهٔ پایینِ کانالِ صعودی است (موقعیت ${posPct.toFixed(0)}٪ از کف؛ کف=${lowerT.toFixed(2)}$، سقف=${upperT.toFixed(2)}$) ` +
        `و یک pullback رخ داد و کندلِ صعودی بست. طبقِ فصلِ ۱۵ کتابِ Al Brooks، بهترین خرید «near the bottom of the channel» است ` +
        `(نه نزدیکِ سقف). ورودِ خرید در بازشدنِ کندلِ بعد.`,
    }
  }

  // ---- APPROACHING: در نیمهٔ پایین هست ولی هنوز pullback/کندلِ صعودی کامل نشده ----
  const inLowerHalf = pos <= cfg.posMax
  if (inLowerHalf && !rng) {
    return {
      ...base, state: 'APPROACHING',
      reason: `قیمت به نیمهٔ پایینِ کانالِ صعودی رسیده است (موقعیت ${posPct.toFixed(0)}٪ از کف). ` +
        `برای سیگنالِ ورود، منتظرِ یک pullback (شکستِ کفِ کندلِ قبل) و سپس بسته‌شدنِ کندلِ صعودی بمانید. ` +
        `طبقِ Brooks نزدیکِ کفِ کانال خرید معتبر است، نه نزدیکِ سقف.`,
    }
  }

  return {
    ...base, state: 'NEUTRAL',
    reason: `کانالِ صعودی فعال است (کف=${lowerT.toFixed(2)}$، سقف=${upperT.toFixed(2)}$) اما قیمت در نیمهٔ بالای کانال است ` +
      `(موقعیت ${posPct.toFixed(0)}٪). طبقِ فصلِ ۱۵ نزدیکِ سقفِ کانال خرید نمی‌کنیم (micro sell vacuum)؛ منتظرِ بازگشتِ قیمت به کفِ کانال می‌مانیم.`,
  }
}

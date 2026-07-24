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

// ===========================================================================
// channelDecision — تابعِ سطح‌بالای مشترکِ ماژولار (منبعِ واحد برای کارت‌های S219).
// ---------------------------------------------------------------------------
// خروجیِ خامِ computeChannel را به یک RouterDecisionِ کاملِ ۴-حالته (شاملِ بخشِ
// مدیریتِ معامله) ترجمه می‌کند. کارت‌های طلا (M5/M15/M30/H4) دقیقاً همین تابع را با
// پیکربندیِ اثبات‌شدهٔ خودشان صدا می‌زنند ⇒ صفر تکرارِ کد؛ افزودن/تغییرِ یک کارت بقیه
// را دست نمی‌زند (ماژولار).
//
// `fallback`: اگر ماشهٔ position-in-channel فعال نبود، تصمیمِ «حالتِ پایه»ی همان کارت
//   را می‌گیرد و فقط شاخص‌ها/توضیحِ کانال را رویش سوار می‌کند. اگر fallback ندهیم، یک
//   تصمیمِ NEUTRAL/APPROACHINGِ خودبسنده می‌سازد.
// ===========================================================================
import type { RouterDecision, RegimeInfo } from './router'
import { computeLots, assetSpec } from './router'

/** رژیمِ سبکِ مبتنی بر کانال (برای سازگاریِ ساختاری با RouterDecision). */
function channelRegime(ch: ChannelResult): RegimeInfo {
  return {
    regime: ch.regimeUp ? 'trend_up' : 'range',
    efficiencyRatio: 0,
    trendy: ch.regimeUp,
    adx: 0,
    activeStream: ch.regimeUp ? 'bull' : 'none',
    bucket: ch.regimeUp ? 'channel' : 'none',
  }
}

export function channelDecision(
  cfg: ChannelConfig, a: { price: number; adx?: number },
  open: number[], high: number[], low: number[], close: number[],
  capital = 10000, riskPct = 1.0,
  fallback?: () => RouterDecision,
): RouterDecision {
  const ch = computeChannel(open, high, low, close, cfg)
  const reg = channelRegime(ch)
  const spec = assetSpec('XAUUSD')
  const posPct = isFinite(ch.posInChannel) ? ch.posInChannel * 100 : NaN

  // شاخص‌های شفافِ کاربر (طبقِ قانونِ طراحی: فقط مفید، بدونِ آمارِ داخلیِ تحقیق).
  const chInd: RouterDecision['indicators'] = [
    { name: 'تایم‌فریم', value: cfg.tfFa, status: 'neutral' },
    { name: 'کفِ کانالِ صعودی (خطِ روند)',
      value: ch.hasChannel && isFinite(ch.lowerLine) ? ch.lowerLine.toFixed(2) + '$' : '—',
      status: ch.hasChannel ? 'ok' : 'neutral' },
    { name: 'سقفِ کانالِ موازی',
      value: ch.hasChannel && isFinite(ch.upperLine) ? ch.upperLine.toFixed(2) + '$' : '—',
      status: ch.hasChannel ? 'ok' : 'neutral' },
    { name: 'موقعیتِ قیمت داخلِ کانال',
      value: isFinite(posPct) ? `${posPct.toFixed(0)}٪ از کف` : '—',
      status: ch.state === 'ENTRY' ? 'ok' : (isFinite(posPct) && posPct <= cfg.posMax * 100 ? 'warn' : 'neutral') },
    { name: `روندِ کلان (EMA${cfg.emaFast}/${cfg.emaSlow})`,
      value: ch.regimeUp ? 'صعودی ✓' : 'نه‌صعودی', status: ch.regimeUp ? 'ok' : 'neutral' },
    { name: 'پولبک (شکستِ کفِ کندلِ قبل)',
      value: ch.pullback ? 'بله ✓' : 'خیر', status: ch.state === 'ENTRY' ? 'ok' : 'neutral' },
    { name: 'ATR', value: isFinite(ch.atr) ? ch.atr.toFixed(2) + '$' : '—', status: 'neutral' },
    { name: 'قیمتِ فعلی', value: a.price ? a.price.toFixed(2) : '—', status: 'neutral' },
  ]

  // --------- حالتِ ۳: ورود (خرید در نیمهٔ پایینِ کانال + pullback + کندلِ صعودی) ---------
  if (ch.state === 'ENTRY') {
    const entry = a.price
    const sl = entry - ch.slDist
    const tp = entry + ch.tpDist
    const { lots, riskDollars, effRiskPct } = computeLots(capital, riskPct, ch.slDist, 1.0, spec)
    const rd = Math.round(riskDollars * 100) / 100
    return {
      state: 'ENTRY', regime: reg,
      headline: `ورود خرید (LONG) — خرید در کفِ کانالِ صعودی (طلا ${cfg.tfFa})`,
      reason: ch.reason,
      sourceLayer: {
        code: 'S219', name: `کانالِ Al Brooks (Position-in-Channel) — ${cfg.tfFa}`, kind: 'price-action',
        filters: [`گیتِ روندِ صعودی EMA${cfg.emaFast}>EMA${cfg.emaSlow}`,
          `خرید فقط در نیمهٔ پایینِ کانال (موقعیت ≤ ${(cfg.posMax * 100).toFixed(0)}٪ از کف)`,
          'پولبک + کندلِ صعودی', 'قیدِ ضدِ رنج (کندل‌های غیرِ هم‌پوش)'],
        manage: {
          style: 'structural-trail', beTriggerR: 1.0,
          trailDistPrice: ch.slDist, maxHoldBars: cfg.maxHoldBars,
          note: `مدیریتِ ساختاری (کانال): SL اولیه زیرِ کفِ کانال (${ch.slDist.toFixed(2)}$). پس از ۱R سود، SL را ` +
            `به بریک‌ایون ببر؛ سپس زیرِ کفِ هر پولبکِ جدید یا زیرِ خطِ پایینِ کانال بالا بیاور — تا سقفِ ${cfg.maxHoldBars} ` +
            `کندلِ ${cfg.tfFa}. هدفِ منطقی سقفِ کانال است؛ اگر قیمت قاطعانه زیرِ کفِ کانال بست (شکستِ کانال)، فوراً خارج شو حتی قبل از TP.`,
        },
      },
      direction: 'LONG', entry, tp, sl,
      rr: `SL ${cfg.slPip}pip (${ch.slDist.toFixed(2)}$) / TP ${cfg.tpPip}pip (${ch.tpDist.toFixed(2)}$) — ` +
        `R:R ≈ ۱:${(cfg.tpPip / cfg.slPip).toFixed(1)} (بگذار بردها بدوند تا سقفِ کانال)`,
      probability: Math.round(cfg.indepWr),
      sizing: {
        lotMultiplier: 1.0, label: `کانالِ Al Brooks (${cfg.tfFa})`,
        note: `ورودِ open کندلِ بعد؛ اسپردِ واقعیِ طلا لحاظ می‌شود. این لبه فقط روی طلا و فقط در روندِ صعودی کار می‌کند ` +
          `(روی EURUSD بی‌اثر بود، SHORT گیت‌پاس نداد) و سهمِ مستقلِ اثبات‌شده نسبت به سایرِ لایه‌ها دارد ⇒ سودِ خالصِ کل را بالا می‌برد.`,
        lots: lots ?? undefined, riskDollars: rd, capital, riskPct,
        capitalNote: `با سرمایهٔ ${capital.toLocaleString('en-US')}$ و ریسکِ ${riskPct}% ` +
          `(ریسکِ مؤثر ${effRiskPct.toFixed(2)}%)، حجمِ پیشنهادی ${lots?.toFixed(2) ?? '—'} ${spec.lotUnitFa}. ` +
          `اگر SL (فاصلهٔ ${ch.slDist.toFixed(2)}$) بخورد، حدودِ ${rd.toLocaleString('en-US')}$ ضرر می‌کنید.`,
      },
      tpPlan: { multiplier: cfg.tpPip,
        note: `TP دورِ ${cfg.tpPip}pip (هدفِ ساختاری = سقفِ کانالِ موازی). طبقِ فصلِ ۱۵، کانالِ صعودی معمولاً ` +
          `دستِ‌کم سه push بالا دارد؛ TP دور اجازه می‌دهد حرکت به سمتِ سقفِ کانال کامل استخراج شود. تا ${cfg.maxHoldBars} کندلِ ${cfg.tfFa} نگه دارید یا تا برخورد به TP/SL.` },
      slPlan: { multiplier: cfg.slPip,
        note: `SL ${cfg.slPip}pip (${ch.slDist.toFixed(2)}$) زیرِ کفِ کانال. اگر کانالِ صعودی واقعاً شکست، این SL ضرر را محدود می‌کند.` },
      indicators: chInd,
    }
  }

  // --------- حالتِ ۲: نزدیک‌شدن (در نیمهٔ پایینِ کانال، منتظرِ pullback/کندلِ صعودی) ---------
  if (ch.state === 'APPROACHING') {
    return {
      state: 'APPROACHING', regime: reg,
      headline: `نزدیک‌شدن به سیگنالِ خرید (LONG) — قیمت به کفِ کانالِ صعودی رسید (طلا ${cfg.tfFa})`,
      reason: ch.reason,
      sourceLayer: { code: 'S219', name: `کانالِ Al Brooks (Position-in-Channel) — ${cfg.tfFa}`, kind: 'price-action' },
      confirmations: [
        { label: `قیمت در نیمهٔ پایینِ کانال باشد (موقعیت ≤ ${(cfg.posMax * 100).toFixed(0)}٪ از کف)`,
          met: isFinite(posPct) && posPct <= cfg.posMax * 100,
          detail: isFinite(posPct) ? `اکنون ${posPct.toFixed(0)}٪ از کف است.` : '—' },
        { label: 'پولبک: شکستِ کفِ کندلِ قبل', met: ch.pullback,
          detail: ch.pullback ? 'رخ داد ✓' : 'هنوز پولبکِ تازه‌ای شکل نگرفته.' },
        { label: 'کندلِ صعودی (close ≥ open)', met: ch.bullBar,
          detail: ch.bullBar ? 'برقرار ✓' : 'کندلِ فعلی نزولی است.' },
      ],
      indicators: chInd,
    }
  }

  // --------- ماشه فعال نیست ---------
  if (fallback) {
    const base = fallback()
    base.reason = `این کارت لایهٔ «کانالِ Al Brooks — position-in-channel» (S219) را روی افقِ ${cfg.tfFa} پایش می‌کند. ` + ch.reason +
      ` وقتی قیمت به نیمهٔ پایینِ کانالِ صعودی برگردد و یک pullback با کندلِ صعودی شکل بگیرد، سیگنالِ ورودِ خرید صادر می‌شود.`
    base.sourceLayer = { code: 'S219', name: `کانالِ Al Brooks (Position-in-Channel) — ${cfg.tfFa}`, kind: 'price-action' }
    base.indicators = chInd
    base.headline = `طلا ${cfg.tfFa} — پایشِ کانالِ صعودی (فعلاً بدونِ سیگنال)`
    return base
  }
  return {
    state: 'NEUTRAL', regime: reg,
    headline: `طلا ${cfg.tfFa} — پایشِ کانالِ صعودی (فعلاً بدونِ سیگنال)`,
    reason: ch.reason + ` وقتی قیمت به نیمهٔ پایینِ کانالِ صعودی برگردد و یک pullback با کندلِ صعودی شکل بگیرد، ` +
      `سیگنالِ ورودِ خرید (LONG) صادر می‌شود. این لایه فقط در روندِ صعودی و فقط روی طلا فعال است.`,
    sourceLayer: { code: 'S219', name: `کانالِ Al Brooks (Position-in-Channel) — ${cfg.tfFa}`, kind: 'price-action' },
    indicators: chInd,
  }
}

// ============================================================================
// XAUUSD Trend-Line Failed-Breakout Continuation — ماژولِ مشترکِ ماژولار (S215)
// ----------------------------------------------------------------------------
// منبعِ کشف: strategies/s215_brooks_trend_line.py + results/S215_BrooksTrendLine_
//            Xauusd_M5M15M30H1H4_16306_53.md  (فصلِ ۱۳ کتابِ Al Brooks: Trend Lines)
//
// تزِ محوریِ فصلِ ۱۳ (Al Brooks):
//   «As a trend progresses, countertrend moves break the trend lines and USUALLY
//    THE BREAKOUTS FAIL, setting up WITH-TREND entries. While beginners are shorting
//    on those strong sell-offs near the bull trend line, experienced traders have
//    limit orders to BUY at and JUST BELOW the trend line…»
//   ⇒ در روندِ صعودی، هر بار sell-offِ تند قیمت را به/کمی‌زیرِ خطِ روندِ صعودی
//     (وصل‌کنندهٔ دو کفِ اخیر) می‌رساند و قیمت به بالای خط بازمی‌گردد (failed
//     breakout) ⇒ ستاپِ LONGِ ادامهٔ روند.
//
// ⚠️ ماژولار بودن: این فایل فقط «موتورِ خالصِ» تشخیصِ trend-line را می‌دهد. هر کارت
//    (M5/M15/M30/H1/H4) پیکربندیِ اثبات‌شدهٔ مخصوصِ خودش را (از بک‌تستِ S215b)
//    به computeTrendLine می‌دهد؛ افزودن/تغییرِ یک کارت بقیه را دست نمی‌زند.
//
// 🎯 قانونِ شمارهٔ ۱ پروژه: هدف فقط «سودِ خالصِ بیشتر» است، نه Win-Rate.
//    این لایه فقط XAUUSD LONG است (بک‌تست: روی EURUSD صفر ⇒ مختصِ طلا).
// ============================================================================

import * as ind from './indicators'
import type { Candle } from './indicators'

// ---------------------------------------------------------------------------
// پیکربندیِ اثبات‌شدهٔ هر تایم‌فریم (برندهٔ بک‌تستِ S215b — سهمِ مستقلِ WF-4/4).
//   منبع: results/_s215b_independent_scan.json
//   هر ردیف: پارامترهای سیگنال + SL/TP (به pip؛ طلا ۱pip=۰.۱$) + سهمِ مستقل ($).
// ---------------------------------------------------------------------------
export interface TrendLineConfig {
  id: string                 // شناسهٔ کارت (XAUUSD-M5 …)
  tfFa: string               // نامِ فارسیِ تایم‌فریم
  emaFast: number
  emaSlow: number
  k: number                  // نیم-پنجرهٔ swing-pivot
  pen: number                // عمقِ نفوذِ مجاز (ضریبِ ATR)
  maxGap: number             // حداکثر فاصلهٔ دو pivot سازندهٔ خط (کندل)
  slPip: number              // حدِ ضرر (pip)
  tpPip: number              // حدِ سود (pip)
  maxHoldBars: number        // سقفِ نگه‌داری (کندلِ همین TF)
  indepNet: number           // سهمِ مستقلِ اثبات‌شده ($) — فقط برای مستندسازیِ داخلی
  indepWr: number            // WR سهمِ مستقل (٪)
}

// پارامترهای دقیقِ برندهٔ هر TF (عیناً از _s215b_independent_scan.json).
export const TREND_LINE_CFG: Record<string, TrendLineConfig> = {
  'XAUUSD-M5':  { id: 'XAUUSD-M5',  tfFa: 'M5 (پنج‌دقیقه‌ای)',  emaFast: 10, emaSlow: 30, k: 5, pen: 0.6, maxGap: 40, slPip: 250, tpPip: 500, maxHoldBars: 96, indepNet: 3361, indepWr: 52.4 },
  'XAUUSD-M15': { id: 'XAUUSD-M15', tfFa: 'M15 (پانزده‌دقیقه‌ای)', emaFast: 20, emaSlow: 50, k: 5, pen: 1.0, maxGap: 80, slPip: 300, tpPip: 450, maxHoldBars: 48, indepNet: 2714, indepWr: 57.1 },
  'XAUUSD-M30': { id: 'XAUUSD-M30', tfFa: 'M30 (سی‌دقیقه‌ای)',  emaFast: 10, emaSlow: 30, k: 5, pen: 1.0, maxGap: 40, slPip: 150, tpPip: 300, maxHoldBars: 32, indepNet: 5599, indepWr: 52.4 },
  'XAUUSD-H1':  { id: 'XAUUSD-H1',  tfFa: 'H1 (یک‌ساعته)',      emaFast: 20, emaSlow: 50, k: 3, pen: 1.0, maxGap: 40, slPip: 150, tpPip: 300, maxHoldBars: 24, indepNet: 3217, indepWr: 47.6 },
  'XAUUSD-H4':  { id: 'XAUUSD-H4',  tfFa: 'H4 (چهارساعته)',    emaFast: 20, emaSlow: 50, k: 5, pen: 1.0, maxGap: 80, slPip: 250, tpPip: 500, maxHoldBars: 16, indepNet: 1415, indepWr: 48.9 },
}

const PIP = 0.1              // طلا: ۱ pip = ۰.۱ واحدِ قیمت

export type TrendLineState = 'ENTRY' | 'APPROACHING' | 'NEUTRAL'

export interface TrendLineResult {
  state: TrendLineState
  // خطِ روندِ صعودیِ فعال (اگر ساخته شد):
  hasLine: boolean
  lineValue: number          // مقدارِ خط در کندلِ جاری (line(t))
  slope: number              // شیبِ خط (m)
  pivot1Idx: number
  pivot2Idx: number
  gapBars: number            // فاصلهٔ دو pivot
  regimeUp: boolean          // ema_fast > ema_slow
  atr: number
  tol: number                // pen × ATR
  // فاصلهٔ نسبیِ قیمت تا خط (٪) — برای «نزدیک‌شدن»
  distToLinePct: number
  penetrated: boolean        // low[t] < line(t)
  closedBack: boolean        // close[t] > line(t) - tol
  bullBar: boolean           // close[t] >= open[t]
  isRange: boolean           // قیدِ ضدِ رنج
  // خروجی‌های ورود:
  slDist: number             // فاصلهٔ SL (واحدِ قیمت)
  tpDist: number
  reason: string
}

// ---------------------------------------------------------------------------
// swing_pivots — بازتولیدِ دقیقِ نسخهٔ پایتونِ s172 (اکیداً بزرگ‌تر از k همسایهٔ دوطرف).
//   pivot در i علامت می‌خورد ولی تنها از i+k «قابلِ مشاهده» است (تأخیرِ تأییدِ k کندل).
// ---------------------------------------------------------------------------
export function swingPivots(high: number[], low: number[], k: number): { sh: boolean[]; sl: boolean[] } {
  const n = high.length
  const sh = new Array<boolean>(n).fill(false)
  const sl = new Array<boolean>(n).fill(false)
  for (let i = k; i < n - k; i++) {
    let isHigh = true, isLow = true
    for (let j = 1; j <= k; j++) {
      // همسایه‌های چپ و راست (اکیداً کوچک‌تر/بزرگ‌تر)
      if (!(high[i] > high[i - j] && high[i] > high[i + j])) isHigh = false
      if (!(low[i] < low[i - j] && low[i] < low[i + j])) isLow = false
      if (!isHigh && !isLow) break
    }
    sh[i] = isHigh
    sl[i] = isLow
  }
  return { sh, sl }
}

/** قیدِ ضدِ رنج (Brooks Fig 13.7): ۳ کندلِ اخیر «large and almost entirely overlapping». */
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
// computeTrendLine — موتورِ خالصِ تشخیصِ «تستِ ناموفقِ خطِ روندِ صعودی» (LONG).
//   ارزیابی روی «آخرین کندلِ بسته‌شده» (t = n-1)؛ ورودِ واقعی next-open (کاربر روی
//   کندلِ بعد وارد می‌شود). این دقیقاً معادلِ shift(1) در بک‌تست است.
// ---------------------------------------------------------------------------
export function computeTrendLine(
  open: number[], high: number[], low: number[], close: number[],
  cfg: TrendLineConfig,
): TrendLineResult {
  const n = close.length
  const empty: TrendLineResult = {
    state: 'NEUTRAL', hasLine: false, lineValue: NaN, slope: NaN,
    pivot1Idx: -1, pivot2Idx: -1, gapBars: 0, regimeUp: false, atr: NaN, tol: NaN,
    distToLinePct: NaN, penetrated: false, closedBack: false, bullBar: false,
    isRange: false, slDist: cfg.slPip * PIP, tpDist: cfg.tpPip * PIP,
    reason: 'دادهٔ کافی برای ساختِ خطِ روند نیست.',
  }
  if (n < cfg.emaSlow + cfg.k + 5) return empty

  const candles: Candle[] = close.map((cl, i) => ({
    time: i, open: open[i], high: high[i], low: low[i], close: cl, volume: 0,
  }))
  const atrArr = ind.atr(candles, 14)
  const ef = ind.ema(close, cfg.emaFast)
  const es = ind.ema(close, cfg.emaSlow)
  const { sl: slPiv } = swingPivots(high, low, cfg.k)

  // اندیسِ همهٔ swing-lowها + کندلِ تأییدشان (i+k).
  const piv: number[] = []
  for (let i = 0; i < n; i++) if (slPiv[i]) piv.push(i)

  // «آخرین دو pivotِ تأییدشده تا t = n-1»:
  const t = n - 1
  const confirmed = piv.filter(p => p + cfg.k <= t)
  if (confirmed.length < 2) return { ...empty, reason: 'هنوز دو کفِ ساختاریِ تأییدشده برای رسمِ خطِ روند نداریم.' }

  const i1 = confirmed[confirmed.length - 2]
  const i2 = confirmed[confirmed.length - 1]
  const gap = i2 - i1
  const atr = atrArr[t]
  const regimeUp = ef[t] > es[t]

  if (gap <= 0 || gap > cfg.maxGap || !isFinite(atr) || atr <= 0) {
    return {
      ...empty, hasLine: false, gapBars: gap, regimeUp, atr,
      reason: gap > cfg.maxGap
        ? `دو کفِ اخیر خیلی دور از هم‌اند (${gap} کندل > سقفِ ${cfg.maxGap})؛ خطِ روند دیگر «تازه» نیست.`
        : 'شرایطِ ساختِ خطِ روندِ معتبر فراهم نیست.',
    }
  }

  const m = (low[i2] - low[i1]) / (i2 - i1)
  const lineT = low[i2] + m * (t - i2)
  const tol = cfg.pen * atr
  const distPct = ((close[t] - lineT) / lineT) * 100

  // شرطِ خطِ روندِ صعودیِ معتبر: کفِ دوم بالاتر + شیبِ مثبت + رژیمِ صعودی.
  const validUpLine = low[i2] > low[i1] && m > 0 && regimeUp
  const penetrated = low[t] < lineT
  const closedBack = close[t] > (lineT - tol)
  const bullBar = close[t] >= open[t]
  const rng = isRange(high, low, t)

  const base: TrendLineResult = {
    ...empty, hasLine: validUpLine, lineValue: lineT, slope: m,
    pivot1Idx: i1, pivot2Idx: i2, gapBars: gap, regimeUp, atr, tol,
    distToLinePct: distPct, penetrated, closedBack, bullBar, isRange: rng,
  }

  if (!validUpLine) {
    return {
      ...base, state: 'NEUTRAL',
      reason: !regimeUp
        ? 'روندِ کلان صعودی نیست (EMAِ تند زیرِ EMAِ کند)؛ ستاپِ «تستِ خطِ روندِ صعودی» غیرفعال است.'
        : 'دو کفِ اخیر یک خطِ روندِ صعودیِ معتبر (کفِ بالاتر + شیبِ مثبت) نمی‌سازند.',
    }
  }

  // ---- ماشهٔ ENTRY: failed breakout (کمی زیرِ خط رفت، بالای خط بست، کندلِ صعودی) ----
  if (penetrated && closedBack && bullBar && !rng) {
    return {
      ...base, state: 'ENTRY',
      reason: `قیمت در یک sell-offِ تند کمی زیرِ خطِ روندِ صعودی (${lineT.toFixed(2)}$) رفت اما دوباره ` +
        `بالای آن بسته شد (شکستِ ناموفقِ خطِ روند). طبقِ فصلِ ۱۳ کتابِ Al Brooks، این ستاپِ ادامهٔ ` +
        `روندِ صعودی است: تازه‌کارها اینجا می‌فروشند ولی معامله‌گرانِ باتجربه می‌خرند. ورودِ خرید در ` +
        `بازشدنِ کندلِ بعد.`,
    }
  }

  // ---- APPROACHING: قیمت به خط نزدیک است ولی هنوز failed-breakout کامل نشده ----
  // «نزدیک» = فاصلهٔ قیمت تا خط کمتر از ۰.۵×tol باشد (در آستانهٔ تست).
  const near = Math.abs(close[t] - lineT) < 0.5 * tol || (penetrated && !closedBack)
  if (near) {
    let why: string
    if (penetrated && !closedBack) {
      why = `قیمت زیرِ خطِ روندِ صعودی (${lineT.toFixed(2)}$) نفوذ کرده اما هنوز بالای آن نبسته است. ` +
        `اگر کندلِ جاری بالای خط ببندد (شکستِ ناموفق)، سیگنالِ ورودِ خرید صادر می‌شود. منتظرِ بسته‌شدنِ ` +
        `قیمت بالای خط بمانید.`
    } else if (rng) {
      why = `قیمت نزدیکِ خطِ روند است اما سه کندلِ اخیر کاملاً هم‌پوش‌اند (بازارِ رنج). طبقِ Brooks در ` +
        `رنج، شکستِ خط بی‌ثمر است؛ تا خروج از حالتِ رنج وارد نمی‌شویم.`
    } else {
      why = `قیمت به خطِ روندِ صعودی (${lineT.toFixed(2)}$) نزدیک شده است (فاصله ${distPct.toFixed(2)}%). ` +
        `اگر یک sell-offِ تند قیمت را کمی زیرِ خط ببرد و سپس بالای خط ببندد، ستاپِ ورودِ خرید کامل می‌شود.`
    }
    return { ...base, state: 'APPROACHING', reason: why }
  }

  return {
    ...base, state: 'NEUTRAL',
    reason: `خطِ روندِ صعودی فعال است (${lineT.toFixed(2)}$) اما قیمت (${close[t].toFixed(2)}$) فاصلهٔ ` +
      `معناداری با آن دارد (${distPct.toFixed(2)}%). تا نزدیک‌شدنِ قیمت به خط و شکل‌گیریِ «تستِ ناموفق»، ` +
      `سیگنالی نداریم.`,
  }
}

// ===========================================================================
// trendLineDecision — تابعِ سطح‌بالای مشترکِ ماژولار (منبعِ واحد برای همهٔ کارت‌ها).
// ---------------------------------------------------------------------------
// این تابع خروجیِ خامِ computeTrendLine را به یک RouterDecisionِ کاملِ ۴-حالته
// (شاملِ بخشِ مدیریتِ معامله) ترجمه می‌کند. همهٔ کارت‌های طلا (M5/M15/M30/H1/H4)
// دقیقاً همین تابع را با پیکربندیِ اثبات‌شدهٔ خودشان صدا می‌زنند ⇒ صفر تکرارِ کد،
// و افزودن/تغییرِ یک کارت بقیه را دست نمی‌زند (ماژولار).
//
// `fallback`: اگر ماشهٔ trend-line فعال نبود، تصمیمِ «حالتِ پایه»ی همان کارت
//   (مثلاً تحلیلِ رژیمِ HTF) را می‌گیرد و فقط شاخص‌ها/توضیحِ خطِ روند را رویش سوار
//   می‌کند. اگر fallback ندهیم، یک تصمیمِ NEUTRAL/APPROACHINGِ خودبسنده می‌سازد.
// ===========================================================================
import type { RouterDecision, RegimeInfo } from './router'
import { computeLots, assetSpec } from './router'

/** رژیمِ سبکِ مبتنی بر خطِ روند (برای سازگاریِ ساختاری با RouterDecision). */
function trendLineRegime(tl: TrendLineResult): RegimeInfo {
  return {
    regime: tl.regimeUp ? 'trend_up' : 'range',
    efficiencyRatio: 0,
    trendy: tl.regimeUp,
    adx: 0,
    activeStream: tl.regimeUp ? 'bull' : 'none',
    bucket: tl.regimeUp ? 'trend_line' : 'none',
  }
}

export function trendLineDecision(
  cfg: TrendLineConfig, a: { price: number; adx?: number },
  open: number[], high: number[], low: number[], close: number[],
  capital = 10000, riskPct = 1.0,
  fallback?: () => RouterDecision,
): RouterDecision {
  const tl = computeTrendLine(open, high, low, close, cfg)
  const reg = trendLineRegime(tl)
  const spec = assetSpec('XAUUSD')

  // شاخص‌های شفافِ کاربر (طبقِ قانونِ طراحی: فقط مفید، بدونِ آمارِ داخلیِ تحقیق).
  const tlInd: RouterDecision['indicators'] = [
    { name: 'تایم‌فریم', value: cfg.tfFa, status: 'neutral' },
    { name: 'خطِ روندِ صعودی (از دو کفِ اخیر)',
      value: tl.hasLine && isFinite(tl.lineValue) ? tl.lineValue.toFixed(2) + '$' : '—',
      status: tl.hasLine ? 'ok' : 'neutral' },
    { name: 'رابطهٔ قیمت با خطِ روند',
      value: isFinite(tl.distToLinePct) ? (tl.penetrated ? 'کمی زیرِ خط (تست)' : `${tl.distToLinePct.toFixed(2)}% بالای خط`) : '—',
      status: tl.state === 'ENTRY' ? 'ok' : tl.penetrated ? 'warn' : 'neutral' },
    { name: `روندِ کلان (EMA${cfg.emaFast}/${cfg.emaSlow})`,
      value: tl.regimeUp ? 'صعودی ✓' : 'نه‌صعودی', status: tl.regimeUp ? 'ok' : 'neutral' },
    { name: 'شکستِ ناموفقِ خط (بازگشت به بالای خط)',
      value: tl.penetrated ? (tl.closedBack ? 'بله ✓' : 'هنوز نه') : 'خیر',
      status: tl.state === 'ENTRY' ? 'ok' : 'neutral' },
    { name: 'ATR', value: isFinite(tl.atr) ? tl.atr.toFixed(2) + '$' : '—', status: 'neutral' },
    { name: 'قیمتِ فعلی', value: a.price ? a.price.toFixed(2) : '—', status: 'neutral' },
  ]

  // --------- حالتِ ۳: ورود (failed breakout کامل) ---------
  if (tl.state === 'ENTRY') {
    const entry = a.price
    const sl = entry - tl.slDist
    const tp = entry + tl.tpDist
    const { lots, riskDollars, effRiskPct } = computeLots(capital, riskPct, tl.slDist, 1.0, spec)
    const rd = Math.round(riskDollars * 100) / 100
    return {
      state: 'ENTRY', regime: reg,
      headline: `ورود خرید (LONG) — تستِ ناموفقِ خطِ روندِ صعودی (طلا ${cfg.tfFa})`,
      reason: tl.reason,
      sourceLayer: {
        code: 'S215', name: `خطِ روندِ Al Brooks (Trend-Line Failed-Breakout) — ${cfg.tfFa}`, kind: 'price-action',
        filters: [`گیتِ روندِ صعودی EMA${cfg.emaFast}>EMA${cfg.emaSlow}`,
          'شکستِ ناموفقِ خطِ روند (کمی زیرِ خط، بازگشت به بالای خط)', 'قیدِ ضدِ رنج (کندل‌های غیرِ هم‌پوش)'],
        manage: {
          style: 'structural-trail', beTriggerR: 1.0,
          trailDistPrice: tl.slDist, maxHoldBars: cfg.maxHoldBars,
          note: `مدیریتِ ساختاری (خطِ روند): SL اولیه زیرِ کفِ نفوذ (${tl.slDist.toFixed(2)}$). پس از ۱R سود، SL را ` +
            `به بریک‌ایون ببر؛ سپس زیرِ خطِ روندِ صعودی یا کفِ هر پولبکِ جدید بالا بیاور — تا سقفِ ${cfg.maxHoldBars} کندلِ ` +
            `${cfg.tfFa}. اگر قیمت قاطعانه زیرِ خطِ روند بسته شد و بالا نیامد (شکستِ واقعیِ روند)، فوراً خارج شو حتی قبل از TP.`,
        },
      },
      direction: 'LONG', entry, tp, sl,
      rr: `SL ${cfg.slPip}pip (${tl.slDist.toFixed(2)}$) / TP ${cfg.tpPip}pip (${tl.tpDist.toFixed(2)}$) — ` +
        `R:R ≈ ۱:${(cfg.tpPip / cfg.slPip).toFixed(1)} (بگذار بردها بدوند)`,
      probability: Math.round(cfg.indepWr),
      sizing: {
        lotMultiplier: 1.0, label: `خطِ روندِ Al Brooks (${cfg.tfFa})`,
        note: `ورودِ open کندلِ بعد؛ اسپردِ واقعیِ طلا لحاظ می‌شود. این لبه فقط روی طلا کار می‌کند ` +
          `(روی EURUSD بی‌اثر بود) و مستقل از سایرِ لایه‌های سایت است ⇒ سودِ خالصِ کل را بالا می‌برد.`,
        lots: lots ?? undefined, riskDollars: rd, capital, riskPct,
        capitalNote: `با سرمایهٔ ${capital.toLocaleString('en-US')}$ و ریسکِ ${riskPct}% ` +
          `(ریسکِ مؤثر ${effRiskPct.toFixed(2)}%)، حجمِ پیشنهادی ${lots?.toFixed(2) ?? '—'} ${spec.lotUnitFa}. ` +
          `اگر SL (فاصلهٔ ${tl.slDist.toFixed(2)}$) بخورد، حدودِ ${rd.toLocaleString('en-US')}$ ضرر می‌کنید.`,
      },
      tpPlan: { multiplier: cfg.tpPip,
        note: `TP دورِ ${cfg.tpPip}pip. پس از تأییدِ ادامهٔ روند، حرکتِ صعودی معمولاً بزرگ است؛ ` +
          `TP دور اجازه می‌دهد حرکت کامل استخراج شود. تا ${cfg.maxHoldBars} کندلِ ${cfg.tfFa} نگه دارید یا تا برخورد به TP/SL.` },
      slPlan: { multiplier: cfg.slPip,
        note: `SL ${cfg.slPip}pip (${tl.slDist.toFixed(2)}$) زیرِ نقطهٔ نفوذِ خطِ روند. اگر شکستِ خط واقعی بود ` +
          `(نه ناموفق)، این SL ضرر را محدود می‌کند.` },
      indicators: tlInd,
    }
  }

  // --------- حالتِ ۲: نزدیک‌شدن ---------
  if (tl.state === 'APPROACHING') {
    return {
      state: 'APPROACHING', regime: reg,
      headline: `نزدیک‌شدن به سیگنالِ خرید (LONG) — قیمت به خطِ روندِ صعودی نزدیک شد (طلا ${cfg.tfFa})`,
      reason: tl.reason,
      sourceLayer: { code: 'S215', name: `خطِ روندِ Al Brooks (Trend-Line) — ${cfg.tfFa}`, kind: 'price-action' },
      confirmations: [
        { label: 'قیمت در یک sell-offِ تند کمی زیرِ خطِ روندِ صعودی برود', met: tl.penetrated,
          detail: tl.penetrated ? 'رخ داد ✓ (قیمت زیرِ خط نفوذ کرد)' : `اکنون ${tl.distToLinePct.toFixed(2)}% بالای خط است.` },
        { label: 'قیمت دوباره بالای خطِ روند ببندد (شکستِ ناموفق)', met: tl.closedBack && tl.penetrated,
          detail: tl.penetrated && !tl.closedBack ? 'هنوز بالای خط نبسته — منتظرِ بسته‌شدن بمانید.' : (tl.closedBack ? 'برقرار ✓' : 'هنوز نه') },
        { label: 'کندلِ صعودی (close ≥ open)', met: tl.bullBar, detail: tl.bullBar ? 'برقرار ✓' : 'کندلِ فعلی نزولی است.' },
      ],
      indicators: tlInd,
    }
  }

  // --------- ماشه فعال نیست ---------
  if (fallback) {
    const base = fallback()
    base.reason = `این کارت لایهٔ «خطِ روندِ Al Brooks» (S215) را روی افقِ ${cfg.tfFa} پایش می‌کند. ` + tl.reason +
      ` وقتی یک sell-offِ تند قیمت را کمی زیرِ خطِ روندِ صعودی ببرد و قیمت دوباره بالای خط ببندد، سیگنالِ ورودِ خرید صادر می‌شود.`
    base.sourceLayer = { code: 'S215', name: `خطِ روندِ Al Brooks (Trend-Line) — ${cfg.tfFa}`, kind: 'price-action' }
    base.indicators = tlInd
    base.headline = `طلا ${cfg.tfFa} — پایشِ خطِ روند (فعلاً بدونِ سیگنال)`
    return base
  }
  return {
    state: 'NEUTRAL', regime: reg,
    headline: `طلا ${cfg.tfFa} — پایشِ خطِ روند (فعلاً بدونِ سیگنال)`,
    reason: tl.reason + ` وقتی یک sell-offِ تند قیمت را کمی زیرِ خطِ روندِ صعودی ببرد و قیمت دوباره بالای خط ببندد، ` +
      `سیگنالِ ورودِ خرید (LONG) صادر می‌شود. این لایه فقط در روندِ صعودی و فقط روی طلا فعال است.`,
    sourceLayer: { code: 'S215', name: `خطِ روندِ Al Brooks (Trend-Line) — ${cfg.tfFa}`, kind: 'price-action' },
    indicators: tlInd,
  }
}

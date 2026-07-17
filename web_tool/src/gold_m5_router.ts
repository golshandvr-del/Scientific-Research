// ============================================================================
// XAUUSD M5 Scalp Router — بازنگریِ بخشِ اسکالپ (پاسخِ User Note)
// ----------------------------------------------------------------------------
// این ماژول لایهٔ اسکالپِ M5 طلا را طبقِ User Note بازنویسی می‌کند:
//
//   • هیچ TP/SL/حجمی به کاربر نمایش داده نمی‌شود.
//   • در حالتِ ENTRY فقط یک تصمیمِ صریح داده می‌شود: **BUY** (یا در آینده SELL).
//   • کاربر با یک دکمه تأیید می‌کند که معاملهٔ دمو را باز کرده است.
//   • سپس سایت به حالتِ «مدیریت» می‌رود و **فقط لحظه‌ای** یکی از دو پیام را می‌دهد:
//       - «ما سودمونو گرفتیم، سریع معامله رو ببند»       (سود گرفته شد)
//       - «متاسفم تشخیصم اشتباه بود، سریع معامله رو ببند» (اشتباه بود)
//   • یک دکمه که کاربر بزند و بگوید معامله را بست.
//
// منطقِ زیربنایی (اثباتِ سودِ خالص روی ۲۰۰k کندلِ واقعیِ M5):
//   results/Scalp_SignalExit_HiddenTarget_NetProfit_10044.md  →  +۱۰٬۰۴۴$ لایهٔ M5
//   (بهبودِ +۲٬۸۰۷$ نسبت به S79). PF=۱.۳۲، هر دو نیمه مثبت، MaxDD ~۱۳٪.
//
//   ورود:  EMA(20) > EMA(100)  ← روندِ کلانِ صعودیِ M5 (long-bias ساختاریِ طلا؛ L51)
//          AND  RSI(21) < 35    ← پولبک (خریدِ ارزان در روند)
//   «هدفِ پنهان» (به کاربر نمایش داده نمی‌شود — فقط منطقِ داخلیِ خروج):
//          hiddenTpPip = ۱۲۰    ← رسیدنِ سود به این حرکت ⇒ «سودمونو گرفتیم، ببند»
//          hiddenSlPip =  ۸۰    ← رسیدنِ ضرر به این حرکت ⇒ «اشتباه بود، ببند»
//          + شکستِ روند (EMA20<EMA100) در حالِ ضرر ⇒ «اشتباه بود، ببند»
//
// ⚠️ قانونِ شمارهٔ ۱ پروژه: معیارِ همه‌چیز «سودِ خالص» است، نه WR.
//    سودِ خالص = XAUUSD + EURUSD.
// ⚠️ قانونِ طراحیِ سایت: هیچ ارجاعی به شماره‌ی آزمایش‌ها (S79/L41/…) یا آمارِ
//    داخلیِ تحقیق در متنِ نمایشیِ کاربر نمی‌آید.
// ============================================================================

import type { AnalysisResult } from './signal'
import type { RouterDecision, RegimeInfo, Confirmation } from './router'
import * as ind from './indicators'

// پارامترهای ورودِ S79 (وسطِ منطقهٔ پایدار — پرهیز از overfit)
const EMA_FAST = 20
const EMA_SLOW = 100
const RSI_PERIOD = 21
const RSI_ENTRY = 35          // آستانهٔ ورود (pullback)
const RSI_APPROACH = 42       // آستانهٔ «نزدیک‌شدن»

// «هدفِ پنهان» — کشفِ s94/s95 (بهترین سودِ خالص، هر دو نیمه مثبت).
// این اعداد فقط داخلِ منطقِ سایت‌اند و هرگز به کاربر نمایش داده نمی‌شوند.
export const HIDDEN_TP_PIP = 120   // ۱ pip طلا = ۰.۰۱$ ⇒ ۱۲۰ pip = ۱.۲۰$ حرکتِ قیمت
export const HIDDEN_SL_PIP = 80    // ۸۰ pip = ۰.۸۰$ حرکتِ قیمت
const PIP = 0.01                   // ارزشِ یک pip روی XAUUSD (اندازهٔ قیمت)

/** رژیمِ سبک برای این لایه (فقط برای سازگاریِ ساختاری با RouterDecision). */
function m5Regime(emaFast: number, emaSlow: number): RegimeInfo {
  const up = emaFast > emaSlow
  return {
    regime: up ? 'trend_up' : 'range',
    efficiencyRatio: 0,
    trendy: up,
    adx: 0,
    activeStream: up ? 'bull' : 'none',
    bucket: up ? 'm5_trend' : 'none',
  }
}

/**
 * تصمیمِ زندهٔ لایهٔ اسکالپِ M5 طلا (بازنگری‌شده — بدونِ TP/SL/حجمِ نمایشی).
 * خروجی در ENTRY فقط جهت (BUY) + آستانه‌های پنهان (برای موتورِ مدیریت) دارد.
 */
export function decideGoldM5(a: AnalysisResult, close: number[],
                             _capital = 10000, _riskPct = 1.0): RouterDecision {
  const price = a.price

  // شاخص‌های زنده (بدونِ آینده — تا آخرین کندلِ بسته)
  const emaF = ind.ema(close, EMA_FAST)
  const emaS = ind.ema(close, EMA_SLOW)
  const rsiArr = ind.rsi(close, RSI_PERIOD)
  const ef = emaF[emaF.length - 1]
  const es = emaS[emaS.length - 1]
  const rsi = rsiArr[rsiArr.length - 1]
  const reg = m5Regime(ef, es)

  const trendUp = ef > es
  const distPct = ((ef - es) / es) * 100

  // شاخص‌هایی که مستقیماً به تصمیمِ کاربر مربوط‌اند (طبقِ قانونِ طراحی: فقط مفید).
  const indicators: RouterDecision['indicators'] = [
    { name: 'روندِ M5 (EMA20/100)', value: trendUp ? 'صعودی ✔' : 'صعودی نیست ✘',
      status: trendUp ? 'ok' : 'bad' },
    { name: 'RSI(21) — عمقِ پولبک', value: rsi.toFixed(1) + (rsi < RSI_ENTRY ? ` (زیرِ ${RSI_ENTRY} ✔)` : ` (هدف: زیرِ ${RSI_ENTRY})`),
      status: rsi < RSI_ENTRY ? 'ok' : (rsi < RSI_APPROACH ? 'warn' : 'neutral') },
    { name: 'قیمتِ زنده', value: price.toFixed(2) + '$', status: 'neutral' },
  ]

  // --------- حالتِ ۱: روندِ M5 صعودی نیست → خنثی ---------
  // (این لایه فقط BUY است؛ بدونِ روندِ صعودیِ M5 اصلاً وارد نمی‌شود — L51 long-bias طلا.)
  if (!trendUp) {
    return {
      state: 'NEUTRAL', regime: reg,
      headline: 'خنثی — شرایطِ اسکالپِ M5 برقرار نیست',
      reason: `این لایه فقط در روندِ صعودیِ کوتاه‌مدت (EMA20 بالای EMA100 روی M5) و ` +
        `هنگامِ پولبک خرید می‌کند. الان EMA20 هنوز بالای EMA100 نیست، پس معامله‌ای باز نمی‌کنم.`,
      indicators,
    }
  }

  // --------- حالتِ ۳: ورود — روندِ صعودی + پولبک کافی (RSI<35) ---------
  // فقط BUY/SELL — بدونِ TP/SL/حجم. آستانه‌های پنهان در فیلدِ scalp حمل می‌شوند.
  if (rsi < RSI_ENTRY) {
    return {
      state: 'ENTRY', regime: reg,
      headline: 'BUY — همین حالا خرید کن',
      reason: `روندِ کوتاه‌مدتِ طلا صعودی است و قیمت یک پولبک زده. تشخیصِ من: خرید (BUY). ` +
        `معاملهٔ خرید را در حسابِ دمو باز کن و بعد دکمهٔ تأیید را بزن تا مدیریتِ لحظه‌ای شروع شود. ` +
        `نیازی به تعیینِ حد سود/ضرر یا حجم نیست — من لحظه‌به‌لحظه بهت می‌گویم کِی ببندی.`,
      scalp: {
        isScalp: true,
        action: 'BUY',
        hiddenTpPip: HIDDEN_TP_PIP,
        hiddenSlPip: HIDDEN_SL_PIP,
        refPrice: price,
      },
      indicators,
    }
  }

  // --------- حالتِ ۲: نزدیک‌شدن — روند صعودی هست ولی پولبک هنوز کافی نیست ---------
  if (rsi < RSI_APPROACH) {
    const confirmations: Confirmation[] = [
      { label: 'روندِ صعودیِ M5', met: true, detail: `EMA20 بالای EMA100 (فاصله ${distPct.toFixed(2)}%).` },
      { label: `پولبکِ کافی (RSI زیرِ ${RSI_ENTRY})`, met: false,
        detail: `RSI(21) الان ${rsi.toFixed(1)} است؛ منتظرِ افتِ بیشتر تا زیرِ ${RSI_ENTRY} می‌مانیم.` },
    ]
    return {
      state: 'APPROACHING', regime: reg,
      headline: 'نزدیکِ سیگنالِ خرید — منتظرِ پولبکِ عمیق‌تر',
      reason: `روندِ کوتاه‌مدت صعودی است، اما قیمت هنوز به‌اندازهٔ کافی پولبک نزده ` +
        `(RSI(21)=${rsi.toFixed(1)}). اگر RSI به زیرِ ${RSI_ENTRY} برسد، BUY صادر می‌شود. ` +
        `فعلاً منتظر بمان و معامله باز نکن.`,
      confirmations,
      indicators,
    }
  }

  // --------- حالتِ ۱ (شاخهٔ دوم): روند صعودی ولی RSI بالا → خنثی ---------
  return {
    state: 'NEUTRAL', regime: reg,
    headline: 'خنثی — منتظرِ فرصتِ خرید',
    reason: `روندِ کوتاه‌مدت صعودی است اما قیمت گران است (RSI(21)=${rsi.toFixed(1)}، بالای ${RSI_APPROACH}). ` +
      `این لایه فقط هنگامِ پولبک وارد می‌شود؛ الان دنبالِ خرید در این قیمت نمی‌رویم و صبر می‌کنیم.`,
    indicators,
  }
}

// ============================================================================
// موتورِ مدیریتِ لحظه‌ایِ اسکالپ (User Note) — «هدفِ پنهان»
// ----------------------------------------------------------------------------
// پس از اینکه کاربر تأیید کرد معاملهٔ دمو را باز کرده، سایت هر چند ثانیه این تابع
// را صدا می‌زند. خروجی فقط یکی از سه حالت است:
//   'take_profit' → «ما سودمونو گرفتیم، سریع معامله رو ببند»
//   'wrong'       → «متاسفم تشخیصم اشتباه بود، سریع معامله رو ببند»
//   'hold'        → هنوز نگه‌دار (سایت هیچ پیامِ خروجی نمی‌دهد)
// هیچ عدد/TP/SL/حجمی در خروجی نیست — فقط تصمیم و پیام.
// ============================================================================

export type ScalpManageState = 'take_profit' | 'wrong' | 'hold'

export interface ScalpManageInput {
  action: 'BUY' | 'SELL'   // جهتِ معاملهٔ باز
  refPrice: number         // قیمتِ ورودِ کاربر (یا قیمتِ مرجعِ سیگنال)
  livePrice: number        // قیمتِ زندهٔ فعلی
  close: number[]          // سریِ close کندلِ M5 (برای شکستِ روند)
}

export interface ScalpManageResult {
  state: ScalpManageState
  message: string          // پیامِ فارسیِ لحظه‌ای (فقط وقتی take_profit/wrong)
  favorPip: number         // حرکتِ مطلوب به pip (فقط برای دیباگ/داخلی — به کاربر نمایش داده نمی‌شود)
}

export function manageGoldM5Scalp(inp: ScalpManageInput): ScalpManageResult {
  const dir = inp.action === 'BUY' ? 1 : -1
  // حرکتِ «مطلوب» به pip: برای BUY وقتی قیمت بالا رفت مثبت است، برای SELL برعکس.
  const favorPip = (dir * (inp.livePrice - inp.refPrice)) / PIP

  // شکستِ روندِ M5 (EMA20 زیرِ EMA100) در حالِ ضرر → خروجِ «اشتباه بود».
  const emaF = ind.ema(inp.close, EMA_FAST)
  const emaS = ind.ema(inp.close, EMA_SLOW)
  const ef = emaF[emaF.length - 1]
  const es = emaS[emaS.length - 1]
  const trendBroke = inp.action === 'BUY' ? ef < es : ef > es

  if (favorPip >= HIDDEN_TP_PIP) {
    return { state: 'take_profit', message: 'ما سودمونو گرفتیم، سریع معامله رو ببند', favorPip }
  }
  if (favorPip <= -HIDDEN_SL_PIP) {
    return { state: 'wrong', message: 'متاسفم تشخیصم اشتباه بود، سریع معامله رو ببند', favorPip }
  }
  if (trendBroke && favorPip <= 0) {
    return { state: 'wrong', message: 'متاسفم تشخیصم اشتباه بود، سریع معامله رو ببند', favorPip }
  }
  return { state: 'hold', message: '', favorPip }
}

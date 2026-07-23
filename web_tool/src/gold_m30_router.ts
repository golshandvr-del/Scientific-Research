// ============================================================================
// XAUUSD M30 Swing Trend-Pullback Router — ماشینِ حالتِ ۴-وضعیتیِ لایهٔ swingِ M30 طلا
// ----------------------------------------------------------------------------
// این ماژول منطقِ استراتژیِ S81 را زنده اجرا می‌کند (نه منطقِ عمومیِ طلا/S67
// و نه اسکالپِ M5/S79). کاملاً مستقل ⇒ هیچ تداخلی با کارت‌های M5/M15 ندارد.
// منبع: strategies/s81_gold_m30_swing_pullback.py و
//        results/S81_Gold_M30_SwingPullback_NetProfit_14327.md
//
// منطقِ S81 (کاملاً forward-safe، فقط Long):
//   ورود:  EMA(20) > EMA(100)   ← روندِ کلانِ صعودی
//          AND  RSI(14) < 35     ← pullback (نقطهٔ ورودِ ارزان در روند)
//   SL = 120 pip (۱۲$)   ,   TP = 1200 pip (۱۲۰$)   → R:R ≈ ۱:۱۰
//   max_hold = ۱۴۴ کندلِ M30 (۳ روز)
//
// ⚠️ پاسخِ User Note (سرمایهٔ کم ۵۰$): این لایهٔ swing SL بزرگ (۱۲$) دارد؛ روی
//    سرمایهٔ زیرِ ~۱٬۰۰۰$ حتی حداقل‌حجمِ بروکر (۰.۰۱ لات) ریسک را بالای ۱٪ می‌بَرد.
//    اگر سرمایه کم باشد، کارت هشدارِ صریح به کاربر می‌دهد (بندِ پایین).
//
// ⚠️ هزینهٔ واقعیِ حسابِ کاربر: اسپردِ طلا ۰.۴۰$، کمیسیون صفر.
// ⚠️ قانونِ طراحیِ سایت: فقط اطلاعاتِ مفید برای کاربر؛ بدونِ ارجاع به شماره‌ی
//    آزمایش‌ها یا آمارِ داخلیِ تحقیق در متنِ نمایشیِ کاربر.
//
// 🎯 قانونِ شمارهٔ ۱ پروژه: هدف فقط «سودِ خالصِ بیشتر» است، نه Win-Rate.
//    تعریفِ رسمیِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD.
// ============================================================================

import type { AnalysisResult } from './signal'
import type { RouterDecision, RegimeInfo, Confirmation } from './router'
import { computeLots, assetSpec } from './router'
import * as ind from './indicators'

// پارامترهای نهاییِ S81 (وسطِ منطقهٔ پایدار — پرهیز از overfit)
const EMA_FAST = 20
const EMA_SLOW = 100
const RSI_PERIOD = 14
const RSI_ENTRY = 35          // آستانهٔ ورود (pullback)
const RSI_APPROACH = 45       // آستانهٔ «نزدیک‌شدن» (کمی بالاتر از ورود)
const SL_DOLLARS = 12.0       // ۱۲۰ pip × ۰.۱۰$
const TP_DOLLARS = 120.0      // ۱۲۰۰ pip × ۰.۱۰$

// حداقلِ سرمایهٔ امن (تا ریسکِ ۰.۰۱ لات ≤ ۱٪ شود): SL=۱۲$ ⇒ ~۱٬۲۰۰$.
const MIN_SAFE_CAPITAL = 1200

/** رژیمِ سبک برای این لایه (فقط برای سازگاریِ ساختاری با RouterDecision). */
function m30Regime(emaFast: number, emaSlow: number): RegimeInfo {
  const up = emaFast > emaSlow
  return {
    regime: up ? 'trend_up' : 'range',
    efficiencyRatio: 0,
    trendy: up,
    adx: 0,
    activeStream: up ? 'bull' : 'none',
    bucket: up ? 'm30_swing' : 'none',
  }
}

/** هشدارِ سرمایهٔ کم — پاسخِ مستقیم به سوالِ کاربر دربارهٔ ۵۰$. */
function capitalWarning(capital: number): string {
  if (capital >= MIN_SAFE_CAPITAL) return ''
  if (capital < 200) {
    return `⛔ هشدارِ سرمایه: این لایهٔ نوسانی SL بزرگ (~۱۲$ در هر معامله) دارد. ` +
      `با سرمایهٔ ${capital.toLocaleString('en-US')}$ حتی کوچک‌ترین حجمِ مجازِ بروکر (۰.۰۱ لات) ` +
      `یعنی ریسکِ ~۱۲$ = بیش از ۲۰٪ حساب در یک معامله؛ چند ضررِ پیاپی حساب را نابود می‌کند. ` +
      `این لایه برای این حجمِ سرمایه مناسب نیست — حداقلِ امن ≈ ۱٬۲۰۰$. برای سرمایهٔ کم لایهٔ اسکالپِ M5 مناسب‌تر است.`
  }
  return `⚠️ هشدارِ سرمایه: با ${capital.toLocaleString('en-US')}$، حجمِ حداقلیِ بروکر (۰.۰۱ لات) ` +
    `ریسکِ ~۱۲$ = ${(1200 / capital).toFixed(0)}٪ حساب در هر معامله دارد (بالای ۱٪ توصیه‌شده). ` +
    `حداقلِ سرمایهٔ امن برای این لایهٔ نوسانی ≈ ۱٬۲۰۰$ است.`
}

/**
 * تصمیمِ زندهٔ لایهٔ M30 طلا (S81). ورودی: نتیجهٔ analyze + سریِ close (کندلِ M30).
 */
export function decideGoldM30(a: AnalysisResult, close: number[],
                              capital = 10000, riskPct = 1.0): RouterDecision {
  const spec = assetSpec('XAUUSD')
  const price = a.price

  // شاخص‌های زنده (بدونِ آینده — تا آخرین کندلِ بسته)
  const emaF = ind.ema(close, EMA_FAST)
  const emaS = ind.ema(close, EMA_SLOW)
  const rsiArr = ind.rsi(close, RSI_PERIOD)
  const ef = emaF[emaF.length - 1]
  const es = emaS[emaS.length - 1]
  const rsi = rsiArr[rsiArr.length - 1]
  const reg = m30Regime(ef, es)

  const trendUp = ef > es
  const distPct = ((ef - es) / es) * 100
  const capWarn = capitalWarning(capital)

  // شاخص‌هایی که مستقیماً به تصمیمِ کاربر مربوط‌اند (طبقِ قانونِ طراحی: فقط مفید).
  const indicators: RouterDecision['indicators'] = [
    { name: 'روندِ میان‌مدت (EMA20/100 روی M30)', value: trendUp ? 'صعودی ✔' : 'صعودی نیست ✘',
      status: trendUp ? 'ok' : 'bad' },
    { name: 'RSI(14) — عمقِ پولبک', value: rsi.toFixed(1) + (rsi < RSI_ENTRY ? ` (زیرِ ${RSI_ENTRY} ✔)` : ` (هدف: زیرِ ${RSI_ENTRY})`),
      status: rsi < RSI_ENTRY ? 'ok' : (rsi < RSI_APPROACH ? 'warn' : 'neutral') },
    { name: 'قیمتِ زنده', value: price.toFixed(2) + '$', status: 'neutral' },
  ]

  // --------- حالتِ ۱: روندِ M30 صعودی نیست → خنثی ---------
  // (این لایه فقط Long است؛ بدونِ روندِ صعودیِ میان‌مدت اصلاً وارد نمی‌شود.)
  if (!trendUp) {
    return {
      state: 'NEUTRAL', regime: reg,
      headline: 'خنثی — شرایطِ نوسان‌گیریِ M30 برقرار نیست',
      reason: `این لایه فقط در روندِ صعودیِ میان‌مدت (EMA20 بالای EMA100 روی M30) و ` +
        `هنگامِ پولبک خرید می‌کند. الان EMA20 هنوز بالای EMA100 نیست، پس معامله‌ای باز نمی‌کنم.` +
        (capWarn ? `\n${capWarn}` : ''),
      indicators,
    }
  }

  // روند صعودی هست. حالا عمقِ پولبک را می‌سنجیم.
  // --------- حالتِ ۳: ورود — روندِ صعودی + پولبک کافی (RSI<35) ---------
  if (rsi < RSI_ENTRY) {
    const entry = price
    const tp = entry + TP_DOLLARS
    const sl = entry - SL_DOLLARS
    const slDist = SL_DOLLARS
    const { lots, riskDollars, effRiskPct } = computeLots(capital, riskPct, slDist, 1.0, spec)
    const rd = Math.round(riskDollars * 100) / 100
    const lotsTxt = lots != null ? lots.toFixed(2) : '—'
    return {
      state: 'ENTRY', regime: reg,
      headline: 'ورود خرید (LONG) — پولبک در روندِ صعودیِ میان‌مدت (M30)',
      sourceLayer: {
        code: 'M30-Swing', name: 'نوسان‌گیریِ پولبکِ روندِ M30 (EMA20/100 + RSI)', kind: 'ma-confluence',
        filters: [`روندِ صعودی EMA20>EMA100`, `پولبک: RSI(14) < ${RSI_ENTRY}`],
        manage: {
          style: 'let-run-trail', beTriggerR: 1.0, trailDistPrice: SL_DOLLARS, maxHoldBars: 144,
          note: `هدفِ بزرگِ روندی (R:R≈۱:۱۰). پس از ۱R سود (${SL_DOLLARS}$) SL را به بریک‌ایون ببر؛ ` +
            `سپس با فاصلهٔ ${SL_DOLLARS}$ trail کن و تا نگهداریِ ۳ روزه بگذار روندِ صعودی کامل استخراج شود — بگذار برد بدود.`,
        },
      },
      reason: `روندِ میان‌مدتِ طلا صعودی است و قیمت الان یک پولبک زده (RSI(14)=${rsi.toFixed(1)} ` +
        `زیرِ ${RSI_ENTRY}). این «خریدِ ارزان در روندِ صعودی» با هدفِ بزرگ (R:R≈۱:۱۰) است. ` +
        `سفارشِ خرید را باز کنید.` + (capWarn ? `\n${capWarn}` : ''),
      direction: 'LONG', entry, tp, sl,
      rr: `SL ۱۲$ / TP ۱۲۰$ (R:R ≈ ۱:۱۰) — نگهداریِ تا ۳ روز`,
      probability: undefined,
      sizing: {
        lotMultiplier: 1.0,
        label: 'حجمِ پایه (نوسانی)',
        note: `نوسان‌گیریِ M30 با SL بزرگ؛ حجم را کوچک نگه دارید.`,
        lots: lots ?? undefined,
        riskDollars: rd,
        capital,
        riskPct,
        capitalNote: `با سرمایهٔ ${capital.toLocaleString('en-US')}$ و ریسکِ ${riskPct}% ` +
          `(${rd.toLocaleString('en-US')}$)، حجمِ پیشنهادی ${lotsTxt} لات (۱۰۰ اونس) است. ` +
          `اگر SL بخورد حدودِ ${rd.toLocaleString('en-US')}$ ضرر می‌کنید — همان ریسکی که تعیین کردید.`,
      },
      tpPlan: { multiplier: 0, note: `TP ثابتِ ۱۲۰$ بالاتر از ورود (۱۲۰۰ pip). هدفِ بزرگِ روندی.` },
      slPlan: { multiplier: 0, note: `SL ثابتِ ۱۲$ پایین‌تر از ورود (۱۲۰ pip).` },
      indicators,
    }
  }

  // --------- حالتِ ۲: نزدیک‌شدن — روند صعودی هست ولی پولبک هنوز کافی نیست ---------
  if (rsi < RSI_APPROACH) {
    const confirmations: Confirmation[] = [
      { label: 'روندِ صعودیِ میان‌مدت (M30)', met: true, detail: `EMA20 بالای EMA100 (فاصله ${distPct.toFixed(2)}%).` },
      { label: `پولبکِ کافی (RSI زیرِ ${RSI_ENTRY})`, met: false,
        detail: `RSI(14) الان ${rsi.toFixed(1)} است؛ منتظرِ افتِ بیشتر تا زیرِ ${RSI_ENTRY} می‌مانیم.` },
    ]
    return {
      state: 'APPROACHING', regime: reg,
      headline: 'نزدیکِ سیگنالِ خرید — منتظرِ پولبکِ عمیق‌تر (M30)',
      reason: `روندِ میان‌مدت صعودی است، اما قیمت هنوز به‌اندازهٔ کافی پولبک نزده ` +
        `(RSI(14)=${rsi.toFixed(1)}). اگر RSI به زیرِ ${RSI_ENTRY} برسد، سیگنالِ خرید صادر می‌شود. ` +
        `فعلاً منتظر بمانید و معامله باز نکنید.` + (capWarn ? `\n${capWarn}` : ''),
      confirmations,
      indicators,
    }
  }

  // --------- حالتِ ۱ (شاخهٔ دوم): روند صعودی ولی RSI بالا → خنثی ---------
  return {
    state: 'NEUTRAL', regime: reg,
    headline: 'خنثی — منتظرِ فرصتِ خرید (M30)',
    reason: `روندِ میان‌مدت صعودی است اما قیمت گران است (RSI(14)=${rsi.toFixed(1)}، بالای ${RSI_APPROACH}). ` +
      `این لایه فقط هنگامِ پولبک وارد می‌شود؛ الان دنبالِ خرید در این قیمت نمی‌رویم و صبر می‌کنیم.` +
      (capWarn ? `\n${capWarn}` : ''),
    indicators,
  }
}

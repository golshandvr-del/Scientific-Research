// ============================================================================
// XAUUSD M5 Trend-Pullback Router — ماشینِ حالتِ ۴-وضعیتیِ مخصوصِ لایهٔ اسکالپِ M5 طلا
// ----------------------------------------------------------------------------
// این ماژول منطقِ استراتژیِ S79 را زنده اجرا می‌کند (نه منطقِ عمومیِ طلا/S67).
// منبع: strategies/s79_gold_m5_trend_pullback.py و
//        results/S79_Gold_M5_TrendPullback_NetProfit_4256.md
//
// منطقِ S79 (کاملاً forward-safe، فقط Long):
//   ورود:  EMA(20) > EMA(100)   ← روندِ کلانِ صعودی
//          AND  RSI(21) < 35     ← pullback (نقطهٔ ورودِ ارزان در روند)
//   SL = 50 pip (۵$)   ,   TP = 120 pip (۱۲$)   → R:R ≈ ۱:۲.۴
//   max_hold = ۷۲ کندلِ M5 (۶ ساعت)
//
// ⚠️ هزینهٔ واقعیِ حسابِ کاربر (User Note 2): اسپردِ طلا ۰.۴۰$، کمیسیون صفر.
// ⚠️ قانونِ طراحیِ سایت (User Note 2، بند ۳): فقط اطلاعاتی نمایش داده می‌شود که به
//    کاربر در «باز کردن و مدیریتِ معامله» کمک کند. هیچ ارجاعی به شماره‌ی آزمایش‌ها
//    (L41/S67/…) یا آمارِ داخلیِ تحقیق در متنِ کاربر نمی‌آید.
// ============================================================================

import type { AnalysisResult } from './signal'
import type { RouterDecision, RegimeInfo, Confirmation } from './router'
import { computeLots, assetSpec } from './router'
import * as ind from './indicators'

// پارامترهای نهاییِ S79 (وسطِ منطقهٔ پایدار — پرهیز از overfit)
const EMA_FAST = 20
const EMA_SLOW = 100
const RSI_PERIOD = 21
const RSI_ENTRY = 35          // آستانهٔ ورود (pullback)
const RSI_APPROACH = 42       // آستانهٔ «نزدیک‌شدن» (کمی بالاتر از ورود)
const SL_DOLLARS = 5.0        // ۵۰ pip × ۰.۱۰$
const TP_DOLLARS = 12.0       // ۱۲۰ pip × ۰.۱۰$

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
 * تصمیمِ زندهٔ لایهٔ M5 طلا (S79). ورودی: نتیجهٔ analyze + سریِ close (کندلِ M5).
 */
export function decideGoldM5(a: AnalysisResult, close: number[],
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
  // (این لایه فقط Long است؛ بدونِ روندِ صعودیِ M5 اصلاً وارد نمی‌شود.)
  if (!trendUp) {
    return {
      state: 'NEUTRAL', regime: reg,
      headline: 'خنثی — شرایطِ اسکالپِ M5 برقرار نیست',
      reason: `این لایه فقط در روندِ صعودیِ کوتاه‌مدت (EMA20 بالای EMA100 روی M5) و ` +
        `هنگامِ پولبک خرید می‌کند. الان EMA20 هنوز بالای EMA100 نیست، پس معامله‌ای باز نمی‌کنم.`,
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
      headline: 'ورود خرید (LONG) — پولبک در روندِ صعودیِ M5',
      reason: `روندِ کوتاه‌مدتِ طلا صعودی است و قیمت الان یک پولبک زده (RSI(21)=${rsi.toFixed(1)} ` +
        `زیرِ ${RSI_ENTRY}). این «خریدِ ارزان در روندِ صعودی» است. سفارشِ خرید را باز کنید.`,
      direction: 'LONG', entry, tp, sl,
      rr: `SL ۵$ / TP ۱۲$ (R:R ≈ ۱:۲.۴)`,
      probability: undefined,
      sizing: {
        lotMultiplier: 1.0,
        label: 'حجمِ پایه',
        note: `اسکالپِ M5 با حجمِ محافظه‌کارانه.`,
        lots: lots ?? undefined,
        riskDollars: rd,
        capital,
        riskPct,
        capitalNote: `با سرمایهٔ ${capital.toLocaleString('en-US')}$ و ریسکِ ${riskPct}% ` +
          `(${rd.toLocaleString('en-US')}$)، حجمِ پیشنهادی ${lotsTxt} لات (۱۰۰ اونس) است. ` +
          `اگر SL بخورد حدودِ ${rd.toLocaleString('en-US')}$ ضرر می‌کنید — همان ریسکی که تعیین کردید.`,
      },
      tpPlan: { multiplier: 0, note: `TP ثابتِ ۱۲$ بالاتر از ورود (۱۲۰ pip).` },
      slPlan: { multiplier: 0, note: `SL ثابتِ ۵$ پایین‌تر از ورود (۵۰ pip).` },
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
        `(RSI(21)=${rsi.toFixed(1)}). اگر RSI به زیرِ ${RSI_ENTRY} برسد، سیگنالِ خرید صادر می‌شود. ` +
        `فعلاً منتظر بمانید و معامله باز نکنید.`,
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

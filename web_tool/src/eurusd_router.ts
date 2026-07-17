// ============================================================================
// EURUSD Session-Open Drift Router — ماشینِ حالتِ ۴-وضعیتیِ مخصوصِ EURUSD
// ----------------------------------------------------------------------------
// قانونِ شمارهٔ ۱ پروژه: هدف **فقط و فقط «سودِ خالصِ بیشتر»** است — نه Win-Rate.
// تعریفِ فعلیِ «سودِ خالص» = مجموعِ سودِ خالصِ دو ارز: XAUUSD + EURUSD.
//
// این ماژول کاملاً مستقل از منطقِ طلا (router.ts / signal.ts S14) است. منطقِ طلا
// دست‌نخورده می‌ماند (رکوردِ +۳۷٬۱۵۶$). اینجا کشفِ مخصوصِ EURUSD پیاده می‌شود:
//
//   استراتژی S73 — Session-Open Time-of-Day Drift (فایل نتیجه:
//   results/S73_EURUSD_SessionDrift_NetProfit_44458.md)
//
//   کشفِ علمی: EURUSD در M15 عملاً random-walk است (autocorrelation ≈ ۰ ⇒ به همین
//   دلیل mean-reversion/breakout در S71/S72 شکست خوردند). اما یک drift ساختاری و
//   پایدارِ «سشن-محور» دارد: در ساعتِ ۰ UTC (باز شدنِ نقدینگیِ اروپا) یک حرکتِ
//   صعودیِ سیستماتیک رخ می‌دهد (t-stat ≈ +۱۰..+۱۵ در هر ۴ دورهٔ زمانیِ مستقل).
//
//   قواعدِ نهایی (robust، نه overfit — نتیجهٔ grid و آزمونِ استحکام):
//     • فقط Long، در open کندلِ ساعتِ ۰ UTC.
//     • فیلترِ pullback: ۴ کندلِ قبل باید نزولی بوده باشد (buy-the-dip).
//     • SL=۱۲ pip، TP=۱۲ pip (ثابت به pip، نه ATR؛ چون drift کوچک است).
//     • خروجِ زمان‌محور در ۶ کندل (~۱.۵ ساعت).
//     • بک‌تست: net=+۷٬۳۰۲$، WR=۶۷.۵٪، PF=۱.۶۲، MaxDD=−۲.۵٪، هر دو نیمه مثبت.
//
// ماشینِ حالتِ ۴-وضعیتی (منطبق با PARADIGM v2):
//   NEUTRAL     — خارج از پنجرهٔ سشن یا شرطِ pullback برقرار نیست.
//   APPROACHING — نزدیکِ ساعتِ ۰ UTC و بازار در حالِ pullback → منتظرِ کندلِ سشن.
//   ENTRY       — کندلِ ساعتِ ۰ UTC با pullbackِ تأییدشده → Long با TP/SL.
//   (MANAGE در trade_manager پس از ثبتِ کاربر مدیریت می‌شود.)
// ============================================================================
import type { AnalysisResult } from './signal'
import type { RouterDecision, RegimeInfo } from './router'
import { computeLots, assetSpec, DEFAULT_CAPITAL, DEFAULT_RISK_PCT } from './router'

// --- پارامترهای ثابتِ استراتژی S73 (هم‌راستا با strategies/s73_eurusd_session_drift.py) ---
const ENTRY_HOUR_UTC = 0        // ساعتِ باز شدنِ نقدینگیِ اروپا (در فیدِ این پروژه)
const PULLBACK_LOOKBACK = 4     // چند کندلِ قبل باید نزولی باشد
const SL_PIP = 12.0
const TP_PIP = 12.0
const PIP = 0.0001
// «نزدیک‌شدن»: اگر در همان ساعتِ ماقبلِ سشن باشیم و pullback در حالِ شکل‌گیری.
const APPROACH_HOUR_UTC = 23

/** آیا مجموعِ حرکتِ N کندلِ اخیر نزولی است؟ (pullback = buy-the-dip) */
function isPullback(close: number[], lookback = PULLBACK_LOOKBACK): { met: boolean; delta: number } {
  const n = close.length
  if (n < lookback + 1) return { met: false, delta: 0 }
  const delta = close[n - 1] - close[n - 1 - lookback]
  return { met: delta < 0, delta }
}

/**
 * تصمیمِ ۴-حالتیِ EURUSD بر پایهٔ ساعتِ کندلِ جاری (UTC) و شرطِ pullback.
 * @param a       خروجیِ analyze (برای قیمت/ATR/شاخص‌های نمایشی)
 * @param close   سریِ close (برای تشخیصِ pullback)
 * @param nowUtcHour  ساعتِ UTC کندلِ در حالِ شکل‌گیری (۰..۲۳)
 */
export function decideEurusd(
  a: AnalysisResult,
  close: number[],
  nowUtcHour: number,
  capital: number = DEFAULT_CAPITAL,
  riskPct: number = DEFAULT_RISK_PCT,
): RouterDecision {
  const spec = assetSpec('EURUSD')
  const price = a.price
  const pb = isPullback(close)
  const deltaPip = pb.delta / PIP

  // رژیمِ اسمی (فقط برای نمایش؛ استراتژی سشن-محور است نه رژیم-محور)
  const reg: RegimeInfo = {
    regime: 'range', efficiencyRatio: 0, trendy: false, adx: a.adx,
    activeStream: 'none', bucket: 'session',
  }

  const indicators: RouterDecision['indicators'] = [
    { name: 'ساعتِ جاری (UTC)', value: `${nowUtcHour}:00`,
      status: nowUtcHour === ENTRY_HOUR_UTC ? 'ok' : (nowUtcHour === APPROACH_HOUR_UTC ? 'warn' : 'neutral') },
    { name: 'پنجرهٔ سشن (۰ UTC)', value: nowUtcHour === ENTRY_HOUR_UTC ? 'باز (باز شدنِ اروپا)' : 'بسته',
      status: nowUtcHour === ENTRY_HOUR_UTC ? 'ok' : 'neutral' },
    { name: `pullback (${PULLBACK_LOOKBACK} کندل)`, value: `${deltaPip >= 0 ? '+' : ''}${deltaPip.toFixed(1)} pip ${pb.met ? '(نزولی ✓)' : '(صعودی)'}`,
      status: pb.met ? 'ok' : 'warn' },
    { name: 'RSI(14)', value: a.rsi14.toFixed(1), status: 'neutral' },
    { name: 'ATR', value: (a.atr / PIP).toFixed(1) + ' pip', status: 'neutral' },
  ]

  const slDist = SL_PIP * PIP
  const tpDist = TP_PIP * PIP

  // --------- حالتِ ۳: ورود — کندلِ ساعتِ ۰ UTC + pullback تأییدشده ---------
  if (nowUtcHour === ENTRY_HOUR_UTC && pb.met) {
    const entry = price
    const tp = entry + tpDist
    const sl = entry - slDist
    const { lots, riskDollars, effRiskPct } = computeLots(capital, riskPct, slDist, 1.0, spec)
    const rd = Math.round(riskDollars * 100) / 100
    const capitalNote =
      `با سرمایهٔ ${capital.toLocaleString('en-US')}$ و ریسکِ ${riskPct}% (ریسکِ مؤثر ${effRiskPct.toFixed(2)}%)، ` +
      `حجمِ پیشنهادی ${lots != null ? lots.toFixed(2) : '—'} ${spec.lotUnitFa} است. اگر SL (فاصلهٔ ${SL_PIP} pip) بخورد، ` +
      `حدودِ ${rd.toLocaleString('en-US')}$ ضرر می‌کنید — دقیقاً همان ریسکی که تعیین کردید.`
    return {
      state: 'ENTRY', regime: reg,
      headline: 'ورود خرید (LONG) — باز شدنِ سشنِ اروپا با pullback تأیید شد',
      reason:
        `کندلِ ساعتِ ${ENTRY_HOUR_UTC}:00 UTC (باز شدنِ نقدینگیِ اروپا) با شرطِ pullback فعال شد: ` +
        `۴ کندلِ اخیر ${deltaPip.toFixed(1)} pip نزولی بوده‌اند (buy-the-dip). ` +
        `کشفِ S73 (L43): در این پنجره EURUSD یک drift صعودیِ ساختاری و پایدار دارد ` +
        `(t-stat ≈ +۱۰..+۱۵ در هر ۴ دورهٔ زمانیِ مستقل). این «محلِ درستِ استفاده» است.`,
      direction: 'LONG', entry, tp, sl,
      rr: `TP ${TP_PIP} pip / SL ${SL_PIP} pip (≈ 1:${(TP_PIP / SL_PIP).toFixed(2)})`,
      probability: 67.5,   // WR تجربیِ بک‌تست
      sizing: {
        lotMultiplier: 1.0,
        label: 'حجمِ پایه (۱×)',
        note: `استراتژیِ سشن-محور از حجمِ پایه استفاده می‌کند (بدونِ Kelly رژیمی؛ لبه زمانی است نه رژیمی).`,
        lots: lots ?? undefined, riskDollars: rd, capital, riskPct, capitalNote,
      },
      tpPlan: { multiplier: TP_PIP, note: `TP ثابتِ ${TP_PIP} pip — چون drift کوچک است، TPِ بزرگِ ATR-محور نامناسب بود (بک‌تست تأیید کرد).` },
      slPlan: { multiplier: SL_PIP, note: `SL ثابتِ ${SL_PIP} pip — مرکزِ ناحیهٔ پایدار؛ کلِ همسایگیِ ۱۰..۱۴ pip سودده و هر دو نیمه مثبت بود.` },
      indicators,
    }
  }

  // --------- حالتِ ۲: نزدیک‌شدن — ساعتِ ماقبلِ سشن یا سشن بدونِ pullback ---------
  if (nowUtcHour === APPROACH_HOUR_UTC || (nowUtcHour === ENTRY_HOUR_UTC && !pb.met)) {
    const confirmations = [
      { label: `کندلِ ساعتِ ${ENTRY_HOUR_UTC}:00 UTC آغاز شود`, met: nowUtcHour === ENTRY_HOUR_UTC,
        detail: `اکنون ساعتِ ${nowUtcHour}:00 است؛ سیگنال دقیقاً در کندلِ ${ENTRY_HOUR_UTC}:00 UTC فعال می‌شود.` },
      { label: `pullback: ۴ کندلِ اخیر نزولی باشد`, met: pb.met,
        detail: `اکنون ${deltaPip.toFixed(1)} pip است؛ برای ورود باید نزولی (< ۰) باشد (buy-the-dip).` },
    ]
    return {
      state: 'APPROACHING', regime: reg,
      headline: 'نزدیک‌شدن به سیگنالِ خرید — منتظرِ باز شدنِ سشنِ اروپا',
      reason:
        `به پنجرهٔ سیگنالِ ساعتِ ${ENTRY_HOUR_UTC}:00 UTC نزدیک شده‌ایم. ` +
        `${nowUtcHour === ENTRY_HOUR_UTC ? 'کندلِ سشن باز است اما هنوز pullback (نزولی‌بودنِ ۴ کندلِ اخیر) تأیید نشده.' : 'کندلِ سشن هنوز آغاز نشده.'} ` +
        `تا تأییدِ هر دو شرطِ زیر وارد نمی‌شوم.`,
      confirmations,
      indicators,
    }
  }

  // --------- حالتِ ۱: خنثی — خارج از پنجرهٔ سشن ---------
  return {
    state: 'NEUTRAL', regime: reg,
    headline: 'خنثی — خارج از پنجرهٔ سشن',
    reason:
      `ساعتِ جاری ${nowUtcHour}:00 UTC است و در پنجرهٔ سیگنالِ EURUSD (کندلِ ${ENTRY_HOUR_UTC}:00 UTC، ` +
      `باز شدنِ نقدینگیِ اروپا) نیستیم. طبقِ کشفِ S73، EURUSD در M15 بیرون از این پنجره عملاً ` +
      `random-walk است (لبهٔ آماری ندارد) — پس وارد نمی‌شوم. صبر می‌کنم تا پنجرهٔ سشن. ` +
      `(این دقیقاً منطقِ «سود ۰ بهتر از منفی» طبقِ قانونِ #۱ است — همان درسی که S71/S72 داد.)`,
    indicators,
  }
}

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

// --- پارامترهای S164: برگشتِ پیش از London Fix در سومین روزِ کاری مانده به پایان ماه ---
// بک‌تست ۲۰۱۸–۲۰۲۶: net=+$3,473، WR=60.7٪، PF=1.71؛ هر ۴ WF مثبت و WR≥40.
const S164_ENTRY_HOUR_UTC = 13
const S164_APPROACH_HOUR_UTC = 12
const S164_SL_PIP = 15.0
const S164_TP_PIP = 20.0
const S164_MAX_HOLD_BARS = 12

// --- پارامترهای ثابتِ استراتژی S73 (هم‌راستا با strategies/s73_eurusd_session_drift.py) ---
const ENTRY_HOUR_UTC = 0        // ساعتِ باز شدنِ نقدینگیِ اروپا (در فیدِ این پروژه)
const PULLBACK_LOOKBACK = 4     // چند کندلِ قبل باید نزولی باشد
const SL_PIP = 12.0
const TP_PIP = 12.0
const PIP = 0.0001
// «نزدیک‌شدن»: اگر در همان ساعتِ ماقبلِ سشن باشیم و pullback در حالِ شکل‌گیری.
const APPROACH_HOUR_UTC = 23

// ساعتِ UTC → «HH:MM به وقتِ ایران» (ایران آفستِ ثابتِ UTC+3:30، بدونِ DST از ۱۴۰۱).
// همهٔ توصیه‌های زمان-محورِ نمایشیِ EURUSD به وقتِ ایران بیان می‌شوند (پاسخِ User Note).
function toIranHM(utcHour: number): string {
  const total = ((utcHour * 60 + 210) % 1440 + 1440) % 1440
  const hh = Math.floor(total / 60), mm = total % 60
  return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`
}

/** تعداد روزهای کاری از تاریخ جاری تا پایان ماه، با احتساب خود روز. تعطیلات آخرهفته حذف می‌شوند. */
function businessDaysThroughMonthEnd(timestampSec: number): number {
  const now = new Date(timestampSec * 1000)
  const y = now.getUTCFullYear(), m = now.getUTCMonth(), d = now.getUTCDate()
  const last = new Date(Date.UTC(y, m + 1, 0)).getUTCDate()
  let count = 0
  for (let day = d; day <= last; day++) {
    const dow = new Date(Date.UTC(y, m, day)).getUTCDay()
    if (dow !== 0 && dow !== 6) count++
  }
  return count
}

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
  nowUtcTimestamp?: number,
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
    { name: 'ساعتِ جاری (به وقتِ ایران)', value: `${toIranHM(nowUtcHour)}`,
      status: nowUtcHour === ENTRY_HOUR_UTC ? 'ok' : (nowUtcHour === APPROACH_HOUR_UTC ? 'warn' : 'neutral') },
    { name: `پنجرهٔ سشن (${toIranHM(ENTRY_HOUR_UTC)} به وقتِ ایران)`, value: nowUtcHour === ENTRY_HOUR_UTC ? 'باز (باز شدنِ اروپا)' : 'بسته',
      status: nowUtcHour === ENTRY_HOUR_UTC ? 'ok' : 'neutral' },
    { name: `pullback (${PULLBACK_LOOKBACK} کندل)`, value: `${deltaPip >= 0 ? '+' : ''}${deltaPip.toFixed(1)} pip ${pb.met ? '(نزولی ✓)' : '(صعودی)'}`,
      status: pb.met ? 'ok' : 'warn' },
    { name: 'RSI(14)', value: a.rsi14.toFixed(1), status: 'neutral' },
    { name: 'ATR', value: (a.atr / PIP).toFixed(1) + ' pip', status: 'neutral' },
  ]

  const slDist = SL_PIP * PIP
  const tpDist = TP_PIP * PIP

  // ========================================================================
  // S164 — حالت‌های ورود/نزدیک‌شدن: سومین روزِ کاری مانده به پایان ماه، ۱۳ UTC.
  // این لایه Short مستقل است و بر S73 اولویت دارد؛ چون پنجره‌اش بسیار انتخابی است.
  // ========================================================================
  const ts = nowUtcTimestamp ?? Math.floor(Date.now() / 1000)
  const businessDaysLeft = businessDaysThroughMonthEnd(ts)
  const s164Day = businessDaysLeft === 3
  const s164Approaching = s164Day && nowUtcHour === S164_APPROACH_HOUR_UTC
  const s164Indicators: RouterDecision['indicators'] = [
    { name: 'روز کاری تا پایان ماه', value: `${businessDaysLeft} روز (با احتساب امروز)`, status: s164Day ? 'ok' : 'neutral' },
    { name: 'پنجرهٔ S164', value: `${S164_ENTRY_HOUR_UTC}:00 UTC`, status: nowUtcHour === S164_ENTRY_HOUR_UTC ? 'ok' : (s164Approaching ? 'warn' : 'neutral') },
    { name: 'اثر پیش از London Fix', value: s164Day ? 'روز هدف تأیید شد' : 'خارج از روز هدف', status: s164Day ? 'ok' : 'neutral' },
    { name: 'ATR', value: (a.atr / PIP).toFixed(1) + ' pip', status: 'neutral' },
    { name: 'RSI(14)', value: a.rsi14.toFixed(1), status: 'neutral' },
  ]

  if (s164Day && nowUtcHour === S164_ENTRY_HOUR_UTC) {
    const entry = price
    const sl164 = entry + S164_SL_PIP * PIP
    const tp164 = entry - S164_TP_PIP * PIP
    const { lots, riskDollars, effRiskPct } = computeLots(capital, riskPct, S164_SL_PIP * PIP, 1.0, spec)
    const rd = Math.round(riskDollars * 100) / 100
    return {
      state: 'ENTRY', regime: { ...reg, bucket: 'pre-month-end-fix' },
      headline: 'ورود فروش (SHORT) — برگشتِ پیش از London Fix تأیید شد',
      sourceLayer: {
        code: 'S164', name: 'برگشتِ پیش از London Fix (ماه‌پایان)', kind: 'time',
        filters: ['سومین روزِ کاریِ ماندهٔ ماه', `کندلِ ${S164_ENTRY_HOUR_UTC}:00 UTC`],
        manage: {
          style: 'fixed-tp-sl', maxHoldBars: S164_MAX_HOLD_BARS,
          note: `این لایهٔ رویداد-محور TP/SL ثابت دارد (TP ${S164_TP_PIP}pip / SL ${S164_SL_PIP}pip، ناحیهٔ پایدار ۱۸/۱۸). ` +
            `جابه‌جاییِ TP/SL توصیه نمی‌شود؛ فقط اگر تا ${S164_MAX_HOLD_BARS} کندل (۳ ساعت) به هدف نرسید، طبقِ پلن ببند.`,
        },
      },
      reason:
        `امروز سومین روزِ کاری مانده به پایان ماه است و پنجرهٔ ${S164_ENTRY_HOUR_UTC}:00 UTC فعال شد. ` +
        `S164 روی ۲۰۰٬۰۰۰ کندل EURUSD این drift نزولی کوتاه را با سود خالص +$3,473، WR=60.7٪، ` +
        `PF=1.71 و چهار پنجرهٔ walk-forward مثبت تأیید کرد. این لایه با S73/S143 تقریباً همبستگی صفر دارد.`,
      direction: 'SHORT', entry, tp: tp164, sl: sl164,
      rr: `TP ${S164_TP_PIP} pip / SL ${S164_SL_PIP} pip (≈ 1:${(S164_TP_PIP / S164_SL_PIP).toFixed(2)})`,
      probability: 60.7,
      sizing: {
        lotMultiplier: 1.0, label: 'حجم پایهٔ S164 (۱×)',
        note: `ریسک ثابت ۱٪؛ خروج حداکثر پس از ${S164_MAX_HOLD_BARS} کندل M15 (۳ ساعت).`,
        lots: lots ?? undefined, riskDollars: rd, capital, riskPct,
        capitalNote: `سرمایه ${capital.toLocaleString('en-US')}$، ریسک مؤثر ${effRiskPct.toFixed(2)}٪، حجم پیشنهادی ${lots != null ? lots.toFixed(2) : '—'} lot؛ زیان هدف در SL حدود ${rd.toLocaleString('en-US')}$.`,
      },
      tpPlan: { multiplier: S164_TP_PIP, note: `TP ثابت ${S164_TP_PIP} pip؛ نقطهٔ میانی ناحیهٔ پایدار ۱۸/۱۸ ترکیب.` },
      slPlan: { multiplier: S164_SL_PIP, note: `SL ثابت ${S164_SL_PIP} pip؛ بدون جابه‌جایی قبل از تأیید مدیریت معامله.` },
      indicators: s164Indicators,
      timeGate: {
        layerCode: 'S164', label: 'برگشتِ پیش از London Fix (EURUSD ماه‌پایان)',
        entryHoursUtc: [S164_ENTRY_HOUR_UTC],
        dayOfMonthNote: 'فقط در سومین روزِ کاریِ ماندهٔ هر ماه فعال است',
        windowOpen: true,
      },
    }
  }

  if (s164Approaching) {
    return {
      state: 'APPROACHING', regime: { ...reg, bucket: 'pre-month-end-fix' },
      headline: 'نزدیک‌شدن به سیگنال فروشِ ماه‌پایان EURUSD',
      sourceLayer: { code: 'S164', name: 'برگشتِ پیش از London Fix (ماه‌پایان)', kind: 'time' },
      reason: `روز هدف S164 تأیید شده و یک ساعت تا پنجرهٔ ${S164_ENTRY_HOUR_UTC}:00 UTC مانده است. هنوز وارد نمی‌شوم تا زمان دقیق رویداد برسد.`,
      confirmations: [
        { label: `امروز دقیقاً سومین روزِ کاری مانده به پایان ماه باشد`, met: s164Day, detail: `${businessDaysLeft} روز کاری با احتساب امروز باقی مانده است.` },
        { label: `کندلِ ${S164_ENTRY_HOUR_UTC}:00 UTC آغاز شود`, met: false, detail: `اکنون ${nowUtcHour}:00 UTC است؛ ورود زودهنگام مجاز نیست.` },
      ],
      indicators: s164Indicators,
      timeGate: {
        layerCode: 'S164', label: 'برگشتِ پیش از London Fix (EURUSD ماه‌پایان)',
        entryHoursUtc: [S164_ENTRY_HOUR_UTC],
        dayOfMonthNote: 'فقط در سومین روزِ کاریِ ماندهٔ هر ماه فعال است',
        windowOpen: false,
      },
    }
  }

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
      sourceLayer: {
        code: 'S73', name: 'درایوِ باز شدنِ سشنِ اروپا (Session-Open Drift)', kind: 'session',
        filters: [`کندلِ ${ENTRY_HOUR_UTC}:00 UTC`, 'شرطِ pullback (۴ کندلِ اخیر نزولی — buy-the-dip)'],
        manage: {
          style: 'fixed-tp-sl', maxHoldBars: 4,
          note: `لبهٔ زمانیِ کوچک و ساختاری (drift): TP ${TP_PIP}pip / SL ${SL_PIP}pip ثابت. ` +
            `بک‌تست تأیید کرد TPِ بزرگِ ATR-محور و جابه‌جاییِ SL این لبه را خراب می‌کند؛ پس TP/SL را جابه‌جا نکن و به همان پلنِ اولیه پایبند بمان.`,
        },
      },
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
      timeGate: {
        layerCode: 'S73', label: 'درایوِ باز شدنِ سشنِ اروپا (EURUSD Session-Open)',
        entryHoursUtc: [ENTRY_HOUR_UTC], windowOpen: true,
      },
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
      sourceLayer: { code: 'S73', name: 'درایوِ باز شدنِ سشنِ اروپا (Session-Open Drift)', kind: 'session' },
      reason:
        `به پنجرهٔ سیگنالِ ساعتِ ${ENTRY_HOUR_UTC}:00 UTC نزدیک شده‌ایم. ` +
        `${nowUtcHour === ENTRY_HOUR_UTC ? 'کندلِ سشن باز است اما هنوز pullback (نزولی‌بودنِ ۴ کندلِ اخیر) تأیید نشده.' : 'کندلِ سشن هنوز آغاز نشده.'} ` +
        `تا تأییدِ هر دو شرطِ زیر وارد نمی‌شوم.`,
      confirmations,
      indicators,
      timeGate: {
        layerCode: 'S73', label: 'درایوِ باز شدنِ سشنِ اروپا (EURUSD Session-Open)',
        entryHoursUtc: [ENTRY_HOUR_UTC], windowOpen: nowUtcHour === ENTRY_HOUR_UTC,
      },
    }
  }

  // --------- حالتِ ۱: خنثی — خارج از پنجرهٔ سشن ---------
  return {
    state: 'NEUTRAL', regime: reg,
    headline: 'خنثی — خارج از پنجرهٔ سشن',
    reason:
      `ساعتِ جاری ${nowUtcHour}:00 UTC است و نه پنجرهٔ S73 (کندلِ ${ENTRY_HOUR_UTC}:00 UTC) و نه ` +
      `پنجرهٔ S164 (سومین روزِ کاری مانده به پایان ماه، ${S164_ENTRY_HOUR_UTC}:00 UTC) فعال نیست. ` +
      `خارج از این محل‌های آزموده‌شده EURUSD عمدتاً random-walk است؛ پس وارد نمی‌شوم. ` +
      `(این دقیقاً منطقِ «سود ۰ بهتر از منفی» طبقِ قانونِ #۱ است — همان درسی که S71/S72 داد.)`,
    indicators,
    timeGate: {
      layerCode: 'S73', label: 'درایوِ باز شدنِ سشنِ اروپا (EURUSD Session-Open)',
      entryHoursUtc: [ENTRY_HOUR_UTC], windowOpen: false,
    },
  }
}

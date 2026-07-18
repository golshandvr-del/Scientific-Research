// ============================================================================
// short_ma_confluence.ts — لایهٔ سیگنالِ SHORTِ مستقل (کشفِ S97–S102)
// ----------------------------------------------------------------------------
// پاسخِ کاملِ User Note: «چرا سایت سیگنالِ نزولی نمی‌دهد؟»
//
// قانونِ شمارهٔ ۱ پروژه: فقط «سودِ خالصِ بیشتر» مهم است — وین‌ریت مهم نیست.
// تعریفِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD.
//
// ماشهٔ ورود (SHORT): قیمت خطِ میانهٔ سه میانگین [EMA50, EMA100, SMA200] را
//   از بالا رو به پایین قطع کند (کندلِ قبل بالای میانه، کندلِ فعلی زیرِ میانه).
//   این دقیقاً «خطِ چارت خطوطِ MA را از بالا قطع می‌کند» است که تریدرِ کاربر گفت.
//
// خروجِ «بگذار بردها بدوند» (بازطراحیِ s117–s118 — کلیدِ رکوردِ +$95,645):
//   SL=70pip، TP سقفِ ۸۰۰pip، BE=6pip، trailing=6pip، max_hold=48 کندل.
//   کشفِ MFE (s117): خروجِ قدیمی (40/8/8/12) میانگین فقط +4.8pip می‌گرفت درحالی‌که
//   MFE=69.3pip در دسترس بود (۶۴.۶pip روی میز جامانده). ترِیلِ تنگ و max_hold کوتاه
//   حرکتِ نزولیِ بزرگ را زودهنگام قطع می‌کرد. با اجازه‌دادن به بردها که تا ۴۸ کندل
//   بدوند و TP دور، سهمِ SHORT از +$27,852 به +$34,542 رسید (Δ +$6,690).
//
// اعتبار (engine اصلاح‌شده، جهتِ موتور = SHORT، پس از رفعِ باگِ «موتورِ long اشتباه» s117):
//   کلِ ۱۵۰k سهمِ SHORT: +34,542$ | هر دو نیمهٔ داده مثبت (h1 +5,161$، h2 +22,648$)
//   walk-forward هر ۴ پنجره مثبت | همبستگیِ روزانه با long = +0.16 (مکمل/غیرِهم‌بسته).
//   افزایشی به رکورد: +88,955$ → +95,645$.
// جزئیات: results/ShortExitLetWinnersRun_NetProfit_95645.md
// ============================================================================

import { ema, sma } from './indicators'

export interface ShortMAConfig {
  emaFast: number      // 50
  emaMid: number       // 100
  smaSlow: number      // 200
  slPip: number        // 70  (× pipSize واحدِ قیمت)
  bePip: number        // 6
  trailPip: number     // 6
  maxHold: number      // 48
  tpPip: number        // 800 (سقفِ ایمنی؛ خروجِ اصلی با trailing/max_hold)
}

// پارامترِ رکورد s118 «بگذار بردها بدوند» — منبعِ حقیقتِ واحد برای سایت و APK.
export const DEFAULT_SHORT_MA: ShortMAConfig = {
  emaFast: 50, emaMid: 100, smaSlow: 200,
  slPip: 70, bePip: 6, trailPip: 6, maxHold: 48, tpPip: 800,
}

export interface ShortMASignal {
  active: boolean          // آیا ماشهٔ SHORT همین الان شلیک کرد؟
  approaching: boolean     // نزدیک به شلیک (قیمت به میانه نزدیک، بالای آن)
  dnStack: boolean         // چیدمانِ نزولیِ کامل EMA50<EMA100<SMA200 (تأییدِ کیفیت)
  mid: number              // خطِ میانهٔ سه MA
  emaFast: number
  emaMid: number
  smaSlow: number
  distPct: number          // فاصلهٔ قیمت از میانه بر حسبِ درصد (منفی = زیرِ میانه)
  reason: string
}

/**
 * محاسبهٔ سیگنالِ SHORTِ MA-confluence از سریِ close.
 * بدونِ look-ahead: فقط از close[0..i] استفاده می‌شود.
 */
export function computeShortMA(close: number[], cfg: ShortMAConfig = DEFAULT_SHORT_MA): ShortMASignal {
  const n = close.length
  const need = cfg.smaSlow + 2
  if (n < need) {
    return { active: false, approaching: false, dnStack: false,
      mid: NaN, emaFast: NaN, emaMid: NaN, smaSlow: NaN, distPct: 0,
      reason: 'دادهٔ کافی برای میانگین‌ها موجود نیست.' }
  }
  const ef = ema(close, cfg.emaFast)
  const em = ema(close, cfg.emaMid)
  const ss = sma(close, cfg.smaSlow)

  const i = n - 1
  const j = n - 2
  const midNow = (ef[i] + em[i] + ss[i]) / 3
  const midPrev = (ef[j] + em[j] + ss[j]) / 3
  const pNow = close[i]
  const pPrev = close[j]

  // ماشه: قطعِ رو به پایینِ میانه (بالا → پایین)
  const crossedDown = pPrev > midPrev && pNow < midNow
  // چیدمانِ نزولیِ کامل (تأییدِ کیفیت طبقِ S101)
  const dnStack = ef[i] < em[i] && em[i] < ss[i]
  // نزدیک‌شدن: قیمت هنوز بالای میانه ولی فاصله‌اش کم و رو به کاهش است
  const distPct = midNow ? ((pNow - midNow) / midNow) * 100 : 0
  const approaching = !crossedDown && pNow > midNow && distPct < 0.15 && (pNow - midNow) < (pPrev - midPrev)

  let reason: string
  if (crossedDown) {
    reason = `قیمت (${pNow.toFixed(2)}) خطِ میانهٔ سه میانگین EMA${cfg.emaFast}/EMA${cfg.emaMid}/SMA${cfg.smaSlow} ` +
      `(${midNow.toFixed(2)}) را از بالا رو به پایین قطع کرد` +
      (dnStack ? ' و چیدمانِ میانگین‌ها کاملاً نزولی است (EMA50<EMA100<SMA200) — تأییدِ کیفیت.'
               : ' (چیدمانِ میانگین‌ها هنوز کاملاً نزولی نیست؛ سیگنالِ کم‌کیفیت‌تر).')
  } else if (approaching) {
    reason = `قیمت (${pNow.toFixed(2)}) به خطِ میانهٔ میانگین‌ها (${midNow.toFixed(2)}) نزدیک و رو به کاهش است ` +
      `(فاصله ${distPct.toFixed(2)}%). اگر از میانه رو به پایین عبور کند، ماشهٔ SHORT شلیک می‌شود.`
  } else if (pNow < midNow) {
    reason = `قیمت زیرِ خطِ میانهٔ میانگین‌ها است اما همین‌الان قطع نکرد (عبور قبلاً رخ داده). ` +
      `منتظرِ ماشهٔ تازه می‌مانیم تا دیر وارد نشویم.`
  } else {
    reason = `قیمت (${pNow.toFixed(2)}) بالای خطِ میانهٔ میانگین‌ها (${midNow.toFixed(2)}) است؛ شرطِ SHORT برقرار نیست.`
  }

  return {
    active: crossedDown, approaching, dnStack,
    mid: midNow, emaFast: ef[i], emaMid: em[i], smaSlow: ss[i], distPct, reason,
  }
}

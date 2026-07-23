// ============================================================================
// S214 — Al Brooks «Late and Missed Entries» (فصلِ ۱۱) — منطقِ زندهٔ لایهٔ مستقلِ
//        XAUUSD M5 (pre-EOM در ساعاتِ روز + فیلترِ مومنتومِ Late-Entry).
// ----------------------------------------------------------------------------
// این لایه معادلِ دقیقِ منطقِ اثبات‌شده در پایتون است:
//   strategies/s214b_late_entry_as_filter.py  (فیلتر و base)
//   strategies/s214c_final_independent_layer.py (تثبیت + ablation)
//   results/S214_BrooksLateEntry_Xauusd_M5_262519_51.md
//
// تزِ فصلِ ۱۱ (Brooks): وقتی روند «always-in» واقعی است و ورودِ اول را از دست دادی،
// دیر هم که شده at-market وارد شو — چون احتمالِ سود بالاست. ما این تز را به‌صورتِ
// «فیلترِ تأییدِ مومنتوم» روی پنجرهٔ تقویمیِ pre-EOM به کار می‌بریم.
//
// قاعدهٔ ورود (همه causal — تا آخرین کندلِ بسته):
//   ۱) پنجرهٔ تقویمی: روزِ جاری بین ۶ تا ۸ روزِ کاری مانده به پایانِ ماه (from_end∈[-8,-6]).
//   ۲) ساعتِ روز: ساعتِ UTC خارج از {19,20,21,22,23} (پنجرهٔ شبانه سهمِ S144-M15 است).
//   ۳) فیلترِ مومنتوم: EMA20>EMA50 و در ۱۲ کندلِ اخیر یک run کاملِ ≥۴ trend-barِ صعودیِ
//      غیر-climactic (میانگینِ range کندل‌های run ≤ 1.5×ATR14) رخ داده باشد.
//   ⇒ تصمیم: BUY (at-market). SL150/TP300 pip (کالیبرهٔ طلا).
//
// اثباتِ ablation (روی داده واقعی، ۴ سال M5):
//   A) pre-EOM روز بدونِ فیلتر : net −$382  (ضررده — تقویمِ خام بی‌ارزش است)
//   B) pre-EOM روز + فیلتر     : net +$726, WR 50.9%, WF 4/4  ← لبهٔ واقعی
//   C) ردشده‌های فیلتر          : net −$158  (بی‌ارزش)
//   ⇒ منبعِ سود = فیلترِ فصلِ ۱۱، نه تقویم.
//
// ⚠️ قانونِ طراحیِ سایت: هیچ ارجاعی به شماره‌ی آزمایش‌ها/آمارِ داخلی در متنِ کاربر نمی‌آید.
// ============================================================================

import * as ind from './indicators'

// پارامترهای تثبیت‌شدهٔ S214 (مطابقِ FILT در s214c)
const EMA_FAST = 20
const EMA_SLOW = 50
const N_RUN = 4              // حداقلِ طولِ run از trend-barهای صعودیِ متوالی
const BR = 0.5              // آستانهٔ نسبتِ بدنه: |body| ≥ BR×range ⇒ trend bar
const CLX = 1.5             // ضدِ climax: میانگینِ range کندل‌های run ≤ CLX×ATR14
const LOOK = 12             // پنجرهٔ «اخیر» برای رخ‌دادِ run
const ATR_LEN = 14
const NIGHT = new Set([19, 20, 21, 22, 23])   // پنجرهٔ شبانه (سهمِ S144-M15) — کنار گذاشته می‌شود
const PRE_EOM_MIN = -8      // from_end ∈ [-8,-6]
const PRE_EOM_MAX = -6

// مدیریتِ خروجِ پنهان (کالیبرهٔ طلا؛ SL150/TP300 pip، ۱ pip = ۰.۰۱$)
export const S214_HIDDEN_TP_PIP = 300
export const S214_HIDDEN_SL_PIP = 150

/**
 * from_end برای هر کندل: رتبهٔ روزِ کاری از انتهای ماهِ تقویمی.
 *
 * ⚠️ مهم (تفاوت با بک‌تستِ پایتون): در بک‌تست، from_end از «روزهای موجود در داده»
 * ساخته می‌شد چون کلِ ۴ سال داده در دست بود. اما در محیطِ *زنده* سرور فقط چند روزِ
 * آخر کندلِ M5 را می‌گیرد (مثلاً ۵ روز)، پس شمارشِ روزهای موجود کاملاً غلط می‌شود.
 * راهِ درست و مستقل از طولِ داده: from_end را از **تقویمِ واقعی** بازسازی می‌کنیم —
 * تعدادِ روزهای کاری (دوشنبه…جمعه، تقریبِ استانداردِ روزهای معاملاتیِ فارکس/طلا)
 * بین روزِ کندل و آخرین روزِ کاریِ ماهِ تقویمی.
 *   آخرین روزِ کاریِ ماه ⇒ from_end = −1 ؛ ۶ روزِ کاری مانده ⇒ from_end = −6.
 * این معادلِ معناییِ تعریفِ پایتون است (رتبه از انتهای ماه) اما در زمانِ زنده درست کار می‌کند.
 */
function isWeekday(y: number, m0: number, d: number): boolean {
  const wd = new Date(Date.UTC(y, m0, d)).getUTCDay() // 0=یکشنبه … 6=شنبه
  return wd >= 1 && wd <= 5
}

function fromEndForDate(y: number, m0: number, d: number): number {
  // تعدادِ روزهای کاریِ *بعد از* روزِ جاری تا پایانِ ماه (شاملِ نشدنِ خودِ روز).
  const lastDay = new Date(Date.UTC(y, m0 + 1, 0)).getUTCDate() // آخرین روزِ ماه
  let workdaysAfter = 0
  for (let dd = d + 1; dd <= lastDay; dd++) {
    if (isWeekday(y, m0, dd)) workdaysAfter++
  }
  // اگر خودِ روزِ جاری تعطیلِ آخرِهفته باشد، آن را به نزدیک‌ترین روزِ کاریِ بعدی نسبت می‌دهیم
  // (رفتارِ محافظه‌کارانه: from_end بر مبنای روزهای کاری است).
  return -(1 + workdaysAfter)
}

function computeFromEnd(times: number[]): number[] {
  const n = times.length
  const out: number[] = new Array(n)
  const cache = new Map<number, number>()
  for (let i = 0; i < n; i++) {
    const dayKey = Math.floor(times[i] / 86400)
    let fe = cache.get(dayKey)
    if (fe === undefined) {
      const dt = new Date(times[i] * 1000)
      fe = fromEndForDate(dt.getUTCFullYear(), dt.getUTCMonth(), dt.getUTCDate())
      cache.set(dayKey, fe)
    }
    out[i] = fe
  }
  return out
}

/**
 * آیا آخرین کندلِ بسته یک رخ‌دادِ «مومنتومِ late-entry» را در ۱۲ کندلِ اخیر داشته و رژیم صعودی است؟
 * causal: فقط تا آخرین کندلِ بستهٔ index = n-1.
 * خروجی: { active, regimeUp, runCount, hadRecentRun } برای پیام‌سازیِ چهارحالته.
 */
function lateEntryMomentum(open: number[], high: number[], low: number[], close: number[]) {
  const n = close.length
  const emaF = ind.ema(close, EMA_FAST)
  const emaS = ind.ema(close, EMA_SLOW)
  const atr = ind.atr(
    close.map((c, i) => ({ time: 0, open: open[i], high: high[i], low: low[i], close: c, volume: 0 })),
    ATR_LEN,
  )
  const regimeUp = emaF[n - 1] > emaS[n - 1]

  // trend-bar صعودیِ هر کندل
  const trendBar: boolean[] = new Array(n)
  const rng: number[] = new Array(n)
  for (let i = 0; i < n; i++) {
    rng[i] = Math.max(high[i] - low[i], 1e-9)
    const body = close[i] - open[i]
    trendBar[i] = body > 0 && Math.abs(body) >= BR * rng[i]
  }

  // رخ‌دادِ run: کندلی که run دقیقاً به N_RUN می‌رسد و غیر-climactic است
  const runEvt: boolean[] = new Array(n).fill(false)
  let run = 0
  for (let i = 0; i < n; i++) {
    run = trendBar[i] ? run + 1 : 0
    if (run === N_RUN && !isNaN(atr[i]) && atr[i] > 0) {
      let sum = 0
      for (let j = i - N_RUN + 1; j <= i; j++) sum += rng[j]
      const avgRunRng = sum / N_RUN
      if (avgRunRng <= CLX * atr[i]) runEvt[i] = true
    }
  }

  // حالت: آیا در [n-1-LOOK, n-2] رویدادی رخ داده؟ (causal ⇒ تا کندلِ قبلی)
  const i = n - 1
  const lo = Math.max(0, i - LOOK)
  let hadRecentRun = false
  for (let k = lo; k <= i - 1; k++) { if (runEvt[k]) { hadRecentRun = true; break } }

  // شمارشِ run جاری (برای پیامِ «نزدیک‌شدن»)
  let curRun = 0
  for (let k = i; k >= 0; k--) { if (trendBar[k]) curRun++; else break }

  return { active: hadRecentRun && regimeUp, regimeUp, hadRecentRun, curRun }
}

export interface LateEntryState {
  /** آیا شرایطِ ورودِ کاملِ S214 برقرار است؟ (BUY) */
  entry: boolean
  /** آیا در پنجرهٔ تقویمی+ساعتیِ درست هستیم (شرطِ لازم)؟ */
  inWindow: boolean
  /** جزئیاتِ ادراکی برای پیام‌سازی */
  regimeUp: boolean
  hadRecentRun: boolean
  curRun: number
  fromEnd: number
  utcHour: number
  price: number
}

/**
 * ارزیابیِ زندهٔ S214 روی آخرین کندلِ بستهٔ M5 طلا.
 * ورودی: سریِ کاملِ OHLC + زمان (ثانیه) + قیمتِ جاری.
 */
export function evalGoldM5LateEntry(
  open: number[], high: number[], low: number[], close: number[],
  times: number[], price: number,
): LateEntryState {
  const n = close.length
  const fromEndArr = computeFromEnd(times)
  const fromEnd = fromEndArr[n - 1]
  const utcHour = new Date(times[n - 1] * 1000).getUTCHours()

  const inPreEom = fromEnd >= PRE_EOM_MIN && fromEnd <= PRE_EOM_MAX
  const isDay = !NIGHT.has(utcHour)
  const inWindow = inPreEom && isDay

  const mom = lateEntryMomentum(open, high, low, close)
  const entry = inWindow && mom.active

  return {
    entry, inWindow,
    regimeUp: mom.regimeUp, hadRecentRun: mom.hadRecentRun, curRun: mom.curRun,
    fromEnd, utcHour, price,
  }
}

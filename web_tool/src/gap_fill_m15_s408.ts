// ---------------------------------------------------------------------------
// S408 — «گپ‌فیلِ M15 با فیلترِ نوسانِ ثابت» · XAUUSD-M15 · LONG-only
//
// حکمِ نهایی (سند: results/S408_GapFillM15FullData_Xauusd_M15_rqs2_94_ACCEPT.md):
//   ┌──────┬──────────────┬─────┬────────┬─────────┬────────┬─────────────────────┐
//   │  TF  │ حکم / نمره   │  n  │   WR   │  maxDD  │   z    │ هندسه (اندازه‌گیریِ داور) │
//   ├──────┼──────────────┼─────┼────────┼─────────┼────────┼─────────────────────┤
//   │ M15  │ ACCEPT 93.8  │ 496 │ 89.11٪ │  5.19٪  │ 16.38  │ SL=18.2 · TP=9.1pip │
//   └──────┴──────────────┴─────┴────────┴─────────┴────────┴─────────────────────┘
//   هر ۱۱ دروازهٔ RQS2 v2.6 سبز · rank_tier = **A** · n_fail = 0
//   Path C · seed=408 · K=500 · n_trials انباشتهٔ بلوکِ S400 = 286 · z_margin=13.5σ
//   داده: data/mt5_full/XAUUSD_M15.csv (۳۶۳٬۷۷۸ کندل · ۲۰۱۱-۰۱-۰۳ → ۲۰۲۶-۰۸-۰۷)
//   PREREG: results/S408_PREREG_GAP_FILL_M15_FULLDATA.md (کامیت پیش از هر عدد)
//
// ⚠️ **تنها کارتِ مجاز: M15.** برخلافِ S562 (که M15 و H1 هر دو ACCEPT بودند)
//    حکمِ S408 فقط روی **یک** تایم‌فریم صادر شده است. سندِ ACCEPT هیچ کارتِ
//    دیگری را نمی‌پذیرد ⇒ قاعدهٔ MTF پروژه اینجا **هیچ کارتِ اضافه‌ای** تولید
//    نمی‌کند. تعمیم به M30/H1 ممنوع است (والدِ M30 لایهٔ جداگانهٔ S404 است با
//    آستانهٔ خودش، و آن لایه اکنون به سایت وصل نیست).
//
// فیزیکِ لایه — «گپ‌فیل در رژیمِ آرام»:
//   ① بازگشاییِ روز با **گپِ منفیِ** بزرگ‌تر از آستانهٔ علّیِ هم‌نوع ⇒ فروشِ
//      هیجانیِ بازگشایی ⇒ گرایشِ آماری به پُر شدنِ گپ ⇒ LONG.
//   ② هدف **خودِ گپ** است: TP = close روزِ قبل (پُرشدنِ کامل) — نه براکتِ
//      متقارن. لذا rr=0.5 است ولی WR=۸۹٪ ⇒ انتظارِ ریاضی مثبت (5.66pip،
//      و در ۲×هزینه هم مثبت: 2.36 ⇒ دروازهٔ H9 سبز).
//   ③ SL = 2.0×|gap| (k_sl برندهٔ تیون) · بدون BE · بدون time-stop · بدون
//      cooldown · **خروجِ اجباری در آخرین کندلِ همان روز**.
//   ④ دوشنبه حذف (DOW≠0) — یافتهٔ ارثیِ S405/S613: دوشنبه سوخته است.
//   ⑤ فیلترِ V: معامله فقط اگر ATR14ِ **روزِ قبل** ≤ چندکِ ۰.۷۸ از رولینگِ
//      ۲۵۰روزهٔ علّی ⇒ «گپ را فقط در رژیمِ آرام بگیر».
//
// 🔬 کشفِ علمیِ حاکم — **قانونِ DD-انتقال** (این لایه هفتمین نقطهٔ دفتر است):
//      V فعال ⇒ DD منتقل می‌شود: S404 · S405-tune · S407* · **S408** · S562
//      V غایب ⇒ DD منفجر می‌شود: S403 · S406*        (*=داده ناقص، جهت معتبر)
//    اینجا: maxDD نیمهٔ اول ۲.۸۲٪ → کلِ داده ۵.۱۹٪ (۱.۸۴× ≤ ۲× ⇒ P2 سبز).
//
// ⚠️⚠️ **قیدِ پرتفویِ الزامی — انباشته روی این کارت** (سندِ ACCEPT §۴):
//    S408 **ابَرمجموعهٔ S404** است: ۹۹.۴٪ روزهای S404 داخلِ S408 هستند
//    (Jaccard 69.3٪) ⇒ **آلفای مستقل نیست**. قانونِ سند: «**S404 یا S408،
//    نه هر دو**». وضعیتِ فعلیِ سایت: S404 به هیچ کارتی وصل **نیست** ⇒ تعارضی
//    وجود ندارد و اتصالِ S408 مجاز است. اگر روزی S404 وصل شود، یکی از این دو
//    **باید** حذف گردد.
//    در برابرِ هم‌کارتیِ فعلی S562-M15 **مستقل** است (Jaccard ۱۲.۵٪) ⇒ اتصالِ
//    هم‌زمانِ این دو روی کارتِ M15 مجاز است. با این حال چون هر دو «گپِ منفیِ
//    بازگشایی» را می‌خوانند، در روزهایی که هر دو فعال شوند سایزِ مشترک لازم است
//    (۲۰.۹٪ از روزهای S408 در S562 هم هست).
//
// ⚠️ پورتِ **مو-به-موی** strategies/s408_gap_fill_m15_fulldata.py::run_layer +
//    strategies/s400_gap_open.py::{build_days, daily_atr, thresholds_for_day} +
//    strategies/s401_gap_fill_riskguard.py::sim_trade_be +
//    strategies/s404_gap_fill_window.py::vol_flags
//    شش دامِ پورت که آگاهانه دفع شده‌اند:
//
//    ① **BUG-DAYBREAK-TF**: مرزِ روز در پایتونِ S400 با `day_break_sec` =
//       ۲ × میانهٔ فاصلهٔ بارها محاسبه می‌شود. ابزارِ انجماد چاپ کرد که برای
//       M15 این دقیقاً **۱۸۰۰s** است. سایت همان عددِ مشترکِ
//       `dayBreakThreshold(900) = max(1800, 1350) = 1800` را می‌گیرد ⇒ هم‌ارز.
//       (این تک‌منبعِ حقیقت از gap_open_s560 وارد می‌شود، بی‌تکرارِ کد.)
//
//    ② **دو آستانهٔ رولینگ ⇒ در زنده «منجمد» شده‌اند.** کارتِ M15 با
//       range='1mo' فقط ~۲۲ روزِ معاملاتی می‌بیند؛ چندکِ گپ ۵۰۰ روز و چندکِ
//       نوسان ۲۵۰ روز می‌خواهد ⇒ بازتولید در مرورگر ناممکن. هر دو یک‌بار از
//       همان دادهٔ داوری‌شده منجمد شدند:
//         results/_s408_arms/frozen_thresholds_M15.json
//
//       🧾 **اثباتِ صداقتِ انجماد — دو سنجهٔ مستقل، هر دو ثبت‌شده:**
//         (الف) *پریتیِ داور*: شمارشِ سیگنال با آستانهٔ **رولینگ** در ابزارِ
//               انجماد = **۴۹۶**، عیناً برابرِ `_s408_verdict.json::n_trades`
//               = ۴۹۶؛ و هندسهٔ میانه sl=18.2/tp=9.1/rr=0.500 نیز بیت‌به‌بیت
//               برابرِ سند ⇒ پورتِ پایتونیِ مرزِ روز + آستانه + DOW + V +
//               شبیه‌ساز درست است (assert در همان ابزار، وگرنه STOP).
//         (ب) *هم‌ارزیِ پنجرهٔ زنده* (results/_s408_arms/recency_M15.json):
//               در همان ~۲۲ روزی که سایت واقعاً می‌بیند، تصمیمِ آستانهٔ منجمد
//               با رولینگ **۱۰۰٪** یکی است:
//                 ۲۲ روز → گپ ۱۰۰٪ · فیلترِ V ۱۰۰٪ · تصمیمِ نهایی ۱۰۰٪ (۱=۱ سیگنال)
//
//       🔴 **و محدودیتی که پنهان نمی‌شود:** بازپخشِ همین آستانهٔ منجمد روی کلِ
//          ۱۵.۶ سال فقط **۲۱۲** سیگنال می‌دهد نه ۴۹۶. علتش نقصِ پورت نیست —
//          سنجهٔ (الف) بیت‌به‌بیت سبز بود — بلکه **جهشِ رژیمِ قیمتِ طلا**ست:
//          آستانهٔ میان‌هفتهٔ امروزی ۱.۲۹۶$ است (طلا ~۳۵۰۰$)، و همین عدد برای
//          ۲۰۱۱ (طلا ~۱۴۰۰$) درشت است و گپ‌های واقعیِ آن دوره را «کوچک»
//          می‌بیند. افتِ تدریجیِ توافق (۴۵روز ۹۲.۹٪ · ۹۰روز ۹۲.۹٪ · ۱۸۰روز
//          ۹۲.۰٪ · ۲۵۰روز ۸۹.۹٪) دقیقاً امضای همین جهش است. لذا حکمِ صادقانه:
//          **آستانهٔ منجمد فقط برای پنجرهٔ زنده مجاز است، نه بازپخشِ تاریخی.**
//
//    ③ **ATR روزانه زنده می‌مانَد — کمینه‌ترین انجمادِ ممکن.** فقط *آستانهٔ*
//       چندک منجمد است؛ خودِ `ATR14` روزانه در مرورگر **زنده** محاسبه می‌شود
//       (۱۴ روز در پنجرهٔ ۲۲روزهٔ کارت جا می‌شود). این تفکیک عمدی است: هر چه
//       کمتر منجمد شود، لایهٔ زنده به نسخهٔ داوری‌شده نزدیک‌تر می‌مانَد.
//
//    ④ **فرمولِ ATR عیناً پایتون (`daily_atr`)، نه ATR رایجِ وایلدر:**
//       TR[k] = max(H−L, |H−prevClose|, |L−prevClose|) و
//       ATR[k] = **میانگینِ سادهٔ** ۱۴ TR اخیر (نه EMA/RMA). روزِ صفر
//       TR = H−L. و شرطِ فیلتر روی **ATR روزِ قبل** یعنی `atr[k−1]` است —
//       که برای ورودِ روزِ k+1 دو روز عقب‌تر و کاملاً علّی است.
//
//    ⑤ **`>` در گپ ولی `<=` در نوسان — عیناً پایتون.** عبورِ گپ اکیداً
//       بزرگ‌تر (`abs(gap) > th`) و فیلترِ V با کوچک‌تر-مساوی
//       (`a_prev <= q` ⇔ ردِ `flags[k] = a_prev > q`). این عدمِ تقارن سهوی
//       نیست؛ اگر جابه‌جا نوشته شود مرزِ سیگنال‌ها جابه‌جا می‌شود.
//
//    ⑥ **ردِ محافظه‌کارانه در نبودِ تاریخچه.** پایتون اگر ATR موجود نباشد
//       سیگنال را رد می‌کند (نه عبور). پورت هم همین می‌کند: نبودِ ۱۵ روزِ
//       کامل (۱۴ TR + یک روز عقب‌تر) = عدمِ ورود، نه ورودِ بی‌فیلتر.
//
// ⏱️ **صداقتِ پنجرهٔ معامله** (ارثی از S560/S562): خروجِ لایه «آخرین کندلِ
//    همان روزِ معاملاتی» است ⇒ پنجره از open کندلِ اولِ روز تا close روز باز
//    است (~۹۶ کندلِ M15). سایت — درست، برای ضدِ repainting — سیگنال را روی
//    کندلِ **بسته** می‌سنجد، پس ENTRY از لحظه‌ای که کندلِ اولِ روز بسته شود
//    اعلام می‌گردد و تا پایانِ همان روز معتبر می‌مانَد؛ بعد از آن لایه صادقانه
//    به NEUTRAL می‌رود و در متن می‌گوید چند کندل از بازگشایی گذشته است.
//    هیچ سنجشی روی کندلِ در حالِ شکل‌گیری انجام نمی‌شود (look-ahead ممنوع).
//
// ماژولار/ROS2-مانند: این فایل کاملاً مستقل است؛ افزودنش فقط **یک** ورودی در
// CARD_LAYERS (کارتِ M15) می‌خواهد و هیچ لایهٔ دیگری را دست نمی‌زند.
// ---------------------------------------------------------------------------
import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision, RegimeInfo } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'
const GOLD_PIP = 0.1

/** دورهٔ ATR روزانه — `period=14` در strategies/s400_gap_open.py::daily_atr */
const ATR_N = 14

// ---------------------------------------------------------------------------
// 🔴 دامِ پورتِ A — آستانهٔ مرزِ روز **باید** عیناً `s400_gap_open.day_break_sec`
//    باشد، نه `dayBreakThreshold` سایت (که `max(1800, 1.5×tf)` است).
//    پایتون: `2 * int(median(diff(t)))` و مقایسه با **`>=`** (نه `>`).
//    هارنسِ پریتی این را لو داد: `missing_in_ts=1` — یک مرزِ روز که پایتون
//    می‌دید و پورتِ اولیه نمی‌دید. برای M15 هر دو ۱۸۰۰ ثانیه می‌دهند، ولی
//    عملگرِ مقایسه تفاوت می‌سازد: وقفهٔ **دقیقاً** ۱۸۰۰s در پایتون مرز است
//    و با `>` نبود. پس هم فرمول و هم عملگر پورت می‌شوند.
// ---------------------------------------------------------------------------
export function s408DayBreakSec(candles: Candle[]): number {
  const n = candles.length
  if (n < 3) return 1800
  const d: number[] = []
  for (let i = 0; i < n - 1; i++) d.push(candles[i + 1].time - candles[i].time)
  d.sort((a, b) => a - b)
  const m = d.length
  // np.median: میانگینِ دو عضوِ میانی در طولِ زوج
  const med = m % 2 === 1 ? d[(m - 1) / 2] : (d[m / 2 - 1] + d[m / 2]) / 2
  return 2 * Math.trunc(med)          // عیناً `2 * int(np.median(d))`
}

/**
 * 🔴 دامِ پورتِ B — آستانهٔ «آخرهفته» در پایتون **۱۰۰٬۰۰۰ ثانیه** است
 * (`s400_gap_open.build_days`: `t[fb] - t[fb-1] > 100000`)، نه ۸۶٬۴۰۰.
 * تفاوت واقعی است: وقفهٔ ۸۶٬۴۰۰..۱۰۰٬۰۰۰ ثانیه (مثلاً تعطیلیِ میانِ هفته)
 * در پایتون **روزِ عادی** است و آستانهٔ گپِ weekday می‌گیرد، ولی با ۸۶٤۰۰
 * اشتباهاً آستانهٔ weekend (۶.۴۰$ در برابر ۱.۳۰$) می‌گرفت ⇒ سیگنال گم می‌شد.
 * هارنس این را در `k=3933` گرفت.
 */
const WEEKEND_GAP_SEC = 100000

export interface S408Config {
  id: string             // شناسهٔ کارت (XAUUSD-M15)
  tfFa: string           // برچسبِ فارسیِ تایم‌فریم
  tfSec: number          // ثانیهٔ هر کندل (M15 ⇒ 900) — برای مرزِ روز
  thrWeekendUsd: number  // آستانهٔ منجمدِ |گپ| در بازگشاییِ آخرهفته ($/oz)
  thrWeekdayUsd: number  // آستانهٔ منجمدِ |گپ| در بازگشاییِ میان‌هفته ($/oz)
  volThrUsd: number      // آستانهٔ منجمدِ ATR14 روزانه ($) — چندکِ ۰.۷۸ رولینگِ ۲۵۰
  qGap: number           // چندکِ قفل‌شدهٔ گپ (نمایش/مستندسازی)
  qVol: number           // چندکِ قفل‌شدهٔ نوسان (نمایش/مستندسازی)
  kSl: number            // ضریبِ SL روی |گپ| (۲.۰ — برندهٔ تیون)
  approachFrac: number   // «نزدیک‌شدن»: |گپ| ≥ approachFrac×آستانه (فقط UI)
  rqs2: number           // نمرهٔ RQS2 (نمایش)
  nTrades: number        // n داوری‌شده (نمایش)
  wrPct: number          // WR داوری‌شده (نمایش)
  pf: number             // PF داوری‌شده (نمایش)
  maxDdPct: number       // maxDD داوری‌شده (نمایش)
}

// ---------------------------------------------------------------------------
// منبعِ حقیقتِ اعداد — نه دست‌نویس، نه حدس:
//   آستانه‌ها ⟵ results/_s408_arms/frozen_thresholds_M15.json
//               (ساختهٔ tools/s408_freeze_thresholds.py با assertِ پریتیِ داور)
//   متریک‌ها  ⟵ results/_s408_verdict.json  (خروجیِ engine/rqs2.py)
//   قاعده     ⟵ results/S408_GapFillM15FullData_Xauusd_M15_rqs2_94_ACCEPT.md §۱
// ---------------------------------------------------------------------------
export const S408_CFG: Record<string, S408Config> = {
  'XAUUSD-M15': {
    id: 'XAUUSD-M15',
    tfFa: 'M15',
    tfSec: 900,
    thrWeekendUsd: 6.4020,
    thrWeekdayUsd: 1.2960,
    volThrUsd: 132.3252,
    qGap: 60,
    qVol: 0.78,
    kSl: 2.0,
    approachFrac: 0.70,
    rqs2: 93.8,
    nTrades: 496,
    wrPct: 89.11,
    pf: 2.36,
    maxDdPct: 5.19,
  },
}

export interface S408Signal {
  active: boolean
  approaching: boolean
  /** سیگنالِ پایه (گپِ منفیِ عمیق‌تر از آستانه) بی‌توجه به V/DOW */
  baseActive: boolean
  /** فیلترِ V عبور کرد؟ (ATR روزِ قبل ≤ آستانهٔ منجمد) */
  volPass: boolean
  /** دوشنبه نبود؟ (DOW ≠ 0) */
  dowPass: boolean
  /** ATR14ِ روزِ قبل ($) — زنده محاسبه می‌شود */
  atrPrevUsd: number
  volThrUsd: number
  volRatio: number
  /** تعداد روزهای کاملِ در دست (برای تشخیصِ کمبودِ تاریخچه) */
  daysAvail: number
  /** اندیسِ «آخرین کندلِ روزِ قبل» (مرزِ روز)؛ -1 اگر مرزی نبود */
  brkIdx: number
  /** گپ = open(اولین کندلِ روزِ نو) − close(آخرین کندلِ روزِ قبل) — علامت‌دار ($) */
  gapUsd: number
  thrUsd: number
  isWeekend: boolean
  /** روزِ هفتهٔ کندلِ اولِ روزِ نو (۰=دوشنبه … مطابق pandas dayofweek) */
  dow: number
  gapHours: number
  /** چند کندلِ بسته از «اولین کندلِ روزِ نو» گذشته است (۰ = تازه‌ترین) */
  atLatestBar: number
  ratio: number
  /** گاردِ سلامتِ فید (علّی، فقط سمتِ گذشته) */
  dataHealthy: boolean
  /** TP = close روزِ قبل ⇒ فاصلهٔ TP ($) */
  tpDistUsd: number
  /** SL = kSl × |گپ| ⇒ فاصلهٔ SL ($) */
  slDistUsd: number
  /** چند کندلِ M15 تا پایانِ روزِ معاملاتی باقی است (تخمینِ maxHold زنده) */
  barsLeftInDay: number
}

// ---------------------------------------------------------------------------
// dailyBarsAtr — ساختِ روزها و ATR14 روزانه، عیناً build_days + daily_atr
//
// خروجی:
//   ends[k] = اندیسِ آخرین کندلِ روزِ k · atr[k] = ATR14 تا پایانِ روزِ k
// نکته: پایتون روزِ صفر را (بی prev_close) از لیستِ روزهای معاملاتی حذف
// می‌کند، ولی `daily_atr` روی همان لیست کار می‌کند. اینجا هم روزها از همان
// مرزها ساخته می‌شوند و ATR روی همان دنباله محاسبه می‌گردد ⇒ هم‌ارز.
// ---------------------------------------------------------------------------
export function dailyBarsAtr(
  candles: Candle[], _tfSec: number,
): { ends: number[]; starts: number[]; atr: number[] } {
  const n = candles.length
  const brkThr = s408DayBreakSec(candles)          // دامِ A
  const brk: number[] = []
  for (let i = 0; i < n - 1; i++) {
    if (candles[i + 1].time - candles[i].time >= brkThr) brk.push(i)   // دامِ A: `>=`
  }
  const starts = [0, ...brk.map(b => b + 1)]
  const ends = [...brk, n - 1]

  // OHLC روزانه
  const dHigh: number[] = []
  const dLow: number[] = []
  const dClose: number[] = []
  for (let k = 0; k < starts.length; k++) {
    let hi = -Infinity, lo = Infinity
    for (let i = starts[k]; i <= ends[k]; i++) {
      if (candles[i].high > hi) hi = candles[i].high
      if (candles[i].low < lo) lo = candles[i].low
    }
    dHigh.push(hi); dLow.push(lo); dClose.push(candles[ends[k]].close)
  }

  // TR عیناً پایتون (دامِ ④)
  const m = starts.length
  const tr = new Array<number>(m).fill(NaN)
  for (let k = 0; k < m; k++) {
    if (k === 0) { tr[k] = dHigh[k] - dLow[k]; continue }
    const pc = dClose[k - 1]
    tr[k] = Math.max(dHigh[k] - dLow[k],
                     Math.abs(dHigh[k] - pc), Math.abs(dLow[k] - pc))
  }
  // ATR = میانگینِ سادهٔ ۱۴ TR اخیر (نه EMA) — دامِ ④
  const atr = new Array<number>(m).fill(NaN)
  for (let k = ATR_N - 1; k < m; k++) {
    let s = 0
    for (let j = k - ATR_N + 1; j <= k; j++) s += tr[j]
    atr[k] = s / ATR_N
  }
  return { ends, starts, atr }
}

// ---------------------------------------------------------------------------
// computeS408Signal — گپِ منفیِ آستانه‌دار ∧ DOW≠دوشنبه ∧ فیلترِ V ∧ گاردِ فید
// ---------------------------------------------------------------------------
export function computeS408Signal(candles: Candle[], cfg: S408Config): S408Signal {
  const empty: S408Signal = {
    active: false, approaching: false, baseActive: false,
    volPass: false, dowPass: false, atrPrevUsd: NaN, volThrUsd: cfg.volThrUsd,
    volRatio: NaN, daysAvail: 0, brkIdx: -1, gapUsd: NaN, thrUsd: NaN,
    isWeekend: false, dow: -1, gapHours: NaN, atLatestBar: -1, ratio: 0,
    dataHealthy: false, tpDistUsd: NaN, slDistUsd: NaN, barsLeftInDay: 0,
  }
  const n = candles.length
  if (n < 3) return empty

  const brkThr = s408DayBreakSec(candles)          // دامِ A

  // --- آخرین مرزِ روز (i و i+1 هر دو در آرایه) — عیناً منطقِ S560/S562 -------
  let brk = -1
  for (let i = n - 2; i >= 1; i--) {
    if (candles[i + 1].time - candles[i].time >= brkThr) { brk = i; break }   // دامِ A
  }
  if (brk < 0) return empty

  const prev = candles[brk]        // آخرین کندلِ روزِ قبل ⇒ prev_close
  const first = candles[brk + 1]   // اولین کندلِ روزِ نو  ⇒ ورود در open همین

  const dt = first.time - prev.time
  const isWeekend = dt > WEEKEND_GAP_SEC              // دامِ B: عیناً پایتون > 100000s
  const gapUsd = first.open - prev.close              // علامت‌دار
  const thrUsd = isWeekend ? cfg.thrWeekendUsd : cfg.thrWeekdayUsd
  const absGap = Math.abs(gapUsd)
  const ratio = thrUsd > 0 ? absGap / thrUsd : 0

  // --- گاردِ سلامتِ فید (ارثی از S560؛ علّی، فقط سمتِ گذشته) -----------------
  const dataHealthy = (candles[brk].time - candles[brk - 1].time) < brkThr

  // --- DOW: روزِ هفتهٔ کندلِ اولِ روزِ نو · ۰=دوشنبه (pandas dayofweek) -------
  //   JS getUTCDay(): ۰=یک‌شنبه ⇒ تبدیل به مقیاسِ pandas: (d+6)%7
  const jsDow = new Date(first.time * 1000).getUTCDay()
  const dow = (jsDow + 6) % 7
  const dowPass = dow !== 0

  // --- سیگنالِ پایه: گپِ منفیِ اکیداً عمیق‌تر از آستانه (دامِ ⑤: `>`) --------
  const baseActive = gapUsd < 0 && absGap > thrUsd && dataHealthy

  // --- فیلترِ V: ATR14ِ روزِ **قبل** ≤ آستانهٔ منجمد (دامِ ⑤: `<=`) ----------
  //   روزِ مرز = روزی که آخرین کندلش brk است ⇒ k. پایتون شرط را روی
  //   atr[k−1] می‌گذارد (ATR روزِ قبل، علّی برای ورودِ روزِ k+1).
  // 🔴 دامِ پورتِ C — **ایندکسِ روز دو طرف یک معنا ندارد.**
  //   پایتون `build_days` از `range(1, len(starts))` شروع می‌کند («روزِ صفر
  //   prev_close ندارد») ⇒ `days[0]` = **دومین** روزِ تقویمی و در نتیجه
  //   `atr[j]` هم روی همان آرایهٔ جابه‌جا‌شده سوار است. اما `dailyBarsAtr`
  //   از روزِ صفرِ تقویمی می‌شمارد. پس نگاشتِ درست:
  //         days_py[j]  ≡  calDay[j + 1]
  //   و شرطِ پایتون `a_prev = atr_py[k-1]` با `k` \u2261 ایندکسِ روزِ **ورود**
  //   (روزِ نو، یعنی calDay[kDay+1]) برابر است با `atrCal[kDay]` — نه
  //   `atrCal[kDay-1]`. پروبِ عددی همین را نشان داد: پورتِ اولیه یک روز
  //   عقب‌تر بود (ts=79.6464 در برابر py=87.2207 و همان 87.2207 روزِ بعدِ ts).
  //
  //   ⚠️ چرا این خطا بی‌خطر به‌نظر می‌رسید ولی نبود: ATR روزانهٔ طلا هم‌بستهٔ
  //      بالایی دارد، پس یک‌روز-جابه‌جایی اغلب همان سمتِ آستانه می‌افتد و فقط
  //      در روزهای گذر (نزدیکِ ۱۳۲.۳۳$) تصمیم را برمی‌گردانَد — یعنی دقیقاً
  //      روی مرزی‌ترین معاملات. بی‌هارنس هرگز دیده نمی‌شد.
  const { ends, atr } = dailyBarsAtr(candles, cfg.tfSec)
  let kDay = -1
  for (let k = 0; k < ends.length; k++) { if (ends[k] === brk) { kDay = k; break } }

  let atrPrevUsd = NaN
  let daysAvail = 0
  if (kDay >= 0) {
    daysAvail = kDay + 1
    atrPrevUsd = atr[kDay]          // دامِ C: ATR تا پایانِ روزِ قبل = روزِ مرزی
  }
  // دامِ ⑥: نبودِ تاریخچه ⇒ رد (نه عبور)
  const volPass = isFinite(atrPrevUsd) && atrPrevUsd <= cfg.volThrUsd
  const volRatio = isFinite(atrPrevUsd) ? atrPrevUsd / cfg.volThrUsd : NaN

  // --- هندسه: TP = close روزِ قبل · SL = kSl×|گپ| ---------------------------
  const tpDistUsd = prev.close - first.open     // >0 چون گپ منفی است
  const slDistUsd = cfg.kSl * absGap

  const cond = baseActive && dowPass && volPass && tpDistUsd > 0

  // «نزدیک‌شدن» فقط UI: گپِ منفیِ کم‌عمق ولی در روزِ آرام و غیرِ دوشنبه
  const approaching = !cond && volPass && dowPass && gapUsd < 0
    && ratio >= cfg.approachFrac

  // چند کندل تا پایانِ روز باقی است (maxHold زندهٔ تخمینی — فقط نمایش/مدیریت)
  const atLatestBar = (n - 1) - (brk + 1)
  const barsLeftInDay = Math.max(0, Math.round(86400 / cfg.tfSec / 3) - atLatestBar)

  return {
    active: cond, approaching, baseActive,
    volPass, dowPass, atrPrevUsd, volThrUsd: cfg.volThrUsd, volRatio, daysAvail,
    brkIdx: brk, gapUsd, thrUsd, isWeekend, dow,
    gapHours: dt / 3600, atLatestBar, ratio, dataHealthy,
    tpDistUsd, slDistUsd, barsLeftInDay,
  }
}

// ---------------------------------------------------------------------------
// decideS408 — RawSignal → RouterDecision
//
// پنجرهٔ تازگی: لایه تا **پایانِ همان روزِ معاملاتی** پوزیشن نگه می‌دارد، پس
// برخلافِ S560/S562 (maxHold=۱ یا ۲) پنجرهٔ تازگی اینجا طولانی است. با این حال
// برای صداقت، هر چه از بازگشایی گذشته باشد در متن گفته می‌شود و پس از پایانِ
// روز (مرزِ روزِ بعد) لایه به NEUTRAL می‌رود.
// ---------------------------------------------------------------------------
const FRESH_MAX_BARS = 96          // ~یک روزِ کاملِ M15 (۲۴h ÷ ۱۵m = ۹۶)

export function decideS408(
  cfg: S408Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const s = computeS408Signal(candles, cfg)
  const price = a.price

  const fresh = s.atLatestBar >= 0 && s.atLatestBar <= FRESH_MAX_BARS
  const active = s.active && fresh
  const approaching = !active && s.approaching && fresh

  const f2 = (x: number) => (isFinite(x) ? x.toFixed(2) : '—')
  const f1 = (x: number) => (isFinite(x) ? x.toFixed(1) : '—')

  const kindFa = s.isWeekend ? 'بازگشاییِ آخرهفته' : 'بازگشاییِ میان‌هفته'
  const dowFa = ['دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه', 'شنبه', 'یک‌شنبه']
  const dowName = s.dow >= 0 && s.dow < 7 ? dowFa[s.dow] : '—'

  let reason: string
  let approachReason: string | undefined

  if (s.brkIdx < 0) {
    reason = `S408 · هیچ مرزِ روزی در پنجرهٔ ${cfg.tfFa} یافت نشد (داده کوتاه است).`
  } else if (!s.dataHealthy) {
    reason = `S408 · گاردِ سلامتِ فید: کندل‌های پیش از مرزِ روز ناقص‌اند ⇒ `
      + `«بستهٔ روزِ قبل» کهنه است و گپ جعلی می‌شود ⇒ ورود مسدود.`
  } else if (!isFinite(s.atrPrevUsd)) {
    reason = `S408 · تاریخچهٔ کافی برای ATR14 روزانه نیست `
      + `(${s.daysAvail} روزِ کامل در دست؛ ۱۵ روز لازم است) ⇒ ردِ محافظه‌کارانه.`
  } else if (active) {
    reason = `S408 · ${kindFa} با گپِ منفیِ ${f2(s.gapUsd)}$ `
      + `(|گپ| = ${f2(Math.abs(s.gapUsd))}$ > آستانهٔ منجمدِ ${f2(s.thrUsd)}$ · `
      + `نسبت ${f2(s.ratio)}×) · روزِ ${dowName} (≠دوشنبه ✓) · `
      + `رژیمِ آرام: ATR14 روزِ قبل ${f1(s.atrPrevUsd)}$ ≤ ${f1(s.volThrUsd)}$ ✓ `
      + `⇒ خریدِ گپ‌فیل: TP = بستهٔ روزِ قبل (${f2(s.tpDistUsd)}$ بالاتر) · `
      + `SL = ${cfg.kSl}×|گپ| = ${f2(s.slDistUsd)}$ · خروجِ اجباری در پایانِ روز.`
  } else if (approaching) {
    reason = `S408 · گپِ منفیِ ${f2(s.gapUsd)}$ در ${kindFa}، ولی هنوز کم‌عمق‌تر `
      + `از آستانهٔ ${f2(s.thrUsd)}$ (نسبت ${f2(s.ratio)}×). رژیم آرام است ✓.`
    approachReason = `برای فعال‌شدن، |گپ| باید از ${f2(s.thrUsd)}$ عبور کند.`
  } else if (s.gapUsd >= 0) {
    reason = `S408 · گپِ بازگشایی مثبت/صفر است (${f2(s.gapUsd)}$) — این لایه فقط `
      + `گپِ **منفی** را معامله می‌کند (LONG-only).`
  } else if (!s.dowPass) {
    reason = `S408 · گپِ منفیِ ${f2(s.gapUsd)}$ هست ولی روزِ بازگشایی **دوشنبه** `
      + `است ⇒ حذفِ ارثیِ S405/S613 (دوشنبه سوخته) ⇒ ورود ممنوع.`
  } else if (!s.volPass) {
    reason = `S408 · گپِ منفیِ ${f2(s.gapUsd)}$ هست ولی رژیم **پرنوسان** است: `
      + `ATR14 روزِ قبل ${f1(s.atrPrevUsd)}$ > آستانهٔ ${f1(s.volThrUsd)}$ `
      + `(${f2(s.volRatio)}×) ⇒ فیلترِ V می‌بندد (قانونِ DD-انتقال).`
  } else if (!s.baseActive) {
    reason = `S408 · |گپ| = ${f2(Math.abs(s.gapUsd))}$ از آستانهٔ منجمدِ `
      + `${f2(s.thrUsd)}$ عبور نکرد (نسبت ${f2(s.ratio)}×).`
  } else if (!fresh) {
    reason = `S408 · شرایط برقرار بود ولی ${s.atLatestBar} کندل از بازگشاییِ روز `
      + `گذشته است (پنجرهٔ مجاز ${FRESH_MAX_BARS} کندل = یک روز) ⇒ پنجرهٔ معامله بسته.`
  } else {
    reason = `S408 · بی‌سیگنال.`
  }

  const raw: RawSignal = {
    active, approaching,
    direction: 'LONG',
    slDist: isFinite(s.slDistUsd) && s.slDistUsd > 0 ? s.slDistUsd : 18.2 * GOLD_PIP,
    tpDist: isFinite(s.tpDistUsd) && s.tpDistUsd > 0 ? s.tpDistUsd : 9.1 * GOLD_PIP,
    maxHoldBars: Math.max(1, s.barsLeftInDay),
    reason, approachReason,
    indicators: a as any,
  }

  const meta: DecideMeta = {
    code: 'S408',
    name: `گپ‌فیلِ ${cfg.tfFa} با فیلترِ نوسانِ ثابت (RQS2 ${cfg.rqs2} · Tier A)`,
    kind: 'mean-reversion' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote: `TP = بستهٔ روزِ قبل (پُرشدنِ کاملِ گپ) · SL = ${cfg.kSl}×|گپ| · `
      + `بدون BE/time-stop/cooldown · **خروجِ اجباری در آخرین کندلِ همان روز**. `
      + `داوری‌شده: n=${cfg.nTrades} · WR=${cfg.wrPct}٪ · PF=${cfg.pf} · `
      + `maxDD=${cfg.maxDdPct}٪ روی ۱۵.۶ سال. `
      + `⚠️ ابَرمجموعهٔ S404 (۹۹.۴٪) ⇒ هرگز با S404 هم‌زمان معامله نشود؛ `
      + `با S562 مستقل است (Jaccard ۱۲.۵٪) ولی در روزهای هم‌زمان سایزِ مشترک.`,
    filters: [
      `گپِ منفی > آستانهٔ منجمدِ QW q${cfg.qGap} (${kindFa}: ${f2(s.thrUsd)}$)`,
      `DOW ≠ دوشنبه (روزِ فعلی: ${dowName})`,
      `ATR14 روزِ قبل ≤ q${cfg.qVol} منجمد (${f1(s.atrPrevUsd)}$ / ${f1(s.volThrUsd)}$)`,
      `گاردِ سلامتِ فید: ${s.dataHealthy ? 'سالم' : 'ناقص ⇒ مسدود'}`,
      `تازگی: ${s.atLatestBar} کندل از بازگشایی (سقف ${FRESH_MAX_BARS})`,
    ],
  }

  const reg: RegimeInfo = {
    regime: 'range', efficiencyRatio: 0, trendy: false,
    adx: isFinite((a as any).adx) ? (a as any).adx : 0,
    activeStream: 'none', bucket: cfg.tfFa,
  }

  return rawToDecision(raw, meta, cfg.id, price, reg, capital, riskPct)
}

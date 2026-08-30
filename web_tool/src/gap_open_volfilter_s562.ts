// ---------------------------------------------------------------------------
// S562 — «گپِ منفیِ بازگشایی + فیلترِ نوسانِ علّی» · XAUUSD-M15 · XAUUSD-H1 · LONG-only
//
// حکمِ نهایی (سند: results/S562_GapOpenVolFilter_Xauusd_M15H1_rqs2_96_ACCEPT.md):
//   ┌──────┬──────────────┬─────┬────────┬─────────┬────────┬──────────────────────┐
//   │  TF  │ حکم / نمره   │  n  │   WR   │  maxDD  │   z    │ هندسه (منجمدِ S560)  │
//   ├──────┼──────────────┼─────┼────────┼─────────┼────────┼──────────────────────┤
//   │ M15  │ ACCEPT 95.3  │ 438 │ 70.78٪ │  3.71٪  │ 15.28  │ SL=TP=50.9pip mh=1   │
//   │ H1   │ ACCEPT 96.0  │ 254 │ 68.90٪ │  2.07٪  │  7.40  │ SL=TP=101.4pip mh=2  │
//   └──────┴──────────────┴─────┴────────┴─────────┴────────┴──────────────────────┘
//   هر ۱۱ دروازهٔ RQS2 v2.6 سبز در **هر دو** TF · صفر دروازهٔ ناموفق
//   Path C · seed=20260815 · K=500 · n_trials انباشتهٔ خانوادهٔ GapOpen = 421
//   داده: data/mt5_full (۱۵.۶ سال) · PREREG کامیت ec52aa25 (پیش از هر تست)
//
// فیزیکِ لایه — دو جزء، یکی ارثی و یکی نو:
//   ① **سیگنالِ پایه = عیناً S560** (بی‌هیچ تغییر): بازگشاییِ روز با گپِ منفیِ بزرگ
//      ⇒ «فروشِ هیجانیِ بازگشایی» ⇒ گرایشِ آماریِ بازگشت به بالا ⇒ LONG.
//   ② **فیلترِ V (تنها درجهٔ آزادیِ نوِ این لایه):** سیگنال **رد** می‌شود اگر
//      نوسانِ مرجعِ روزِ قبل از چندکِ qv از رولینگِ ۲۵۰روزه بالاتر باشد.
//      یعنی: «گپ را فقط در روزهای آرام معامله کن، در رژیمِ پرنوسان نه.»
//
// 🔬 کشفِ علمیِ حاکم بر این لایه — **قانونِ DD-انتقال** (§۴ سند، سه‌ضلعیِ مستقل):
//      • S561 (هندسه: براکتِ تنگ‌تر)        → DD **بدتر** شد ۱۲.۴٪→۲۷.۳٪ ⇒ REJECT
//      • S404 (انتخابِ معامله: فیلترِ ATR)   → DD ۱۳.۳٪→۲.۶٪  ⇒ ACCEPT 96.8
//      • S562 (انتخابِ معامله: فیلترِ دامنه) → DD ۱۲.۴٪→۳.۷٪ و ۹.۵٪→۲.۱٪ ⇒ دو ACCEPT
//    نتیجه: خوشه‌های باختِ لایه‌های گپ **در رژیمِ پرنوسان زندگی می‌کنند**. دروازهٔ
//    H8 با **حذفِ آن روزها** شکسته می‌شود، نه با دستکاریِ استاپ. و برخلافِ هندسه،
//    اثرِ فیلترِ انتخابی **از نیمهٔ اول به کلِ داده منتقل می‌شود** (۴.۹٪→۳.۷٪).
//
// ⚠️ پورتِ **مو-به-موی** tools/s562_volfilter.py::vol_filter_mask +
//    tools/s560_gapopen_explore.py::day_breaks/causal_neg_gap_quantile.
//    پنج دامِ پورت که آگاهانه دفع شده‌اند:
//
//    ① **BUG-BRKTHRESH** (ارثی از S560): مرزِ روز = گپِ زمانیِ اکیداً بزرگ‌تر از
//       max(1800s, 1.5×TF_SEC). برای M15 ⇒ max(1800, 1350) = **1800s**؛ برای
//       H1 ⇒ max(1800, 5400) = **5400s**. توجه: برای H1 عددِ حاکم **۵۴۰۰** است
//       نه ۱۸۰۰ — نوشتنِ سادهٔ «>۳۰ دقیقه» برای H1 هر کندل را یک «روزِ جعلی»
//       می‌کرد. فرمولِ کلی حفظ شده تا این دام هرگز برنگردد.
//
//    ② **دو آستانهٔ انبساطی ⇒ در زنده باید «منجمد» شوند.** سایت برای M15 فقط
//       ۱ ماه کندل دارد (range=1mo) و برای H1 سه ماه (range=3mo) ⇒ بازتولیدِ
//       چندکِ انبساطیِ ۱۵.۶ساله در مرورگر ممکن نیست. پس **هر دو** آستانه
//       (گپ + نوسان) یک‌بار از کلِ تاریخ محاسبه و منجمد شده‌اند در
//       results/_s562_arms/frozen_thresholds_{M15,H1}.json.
//
//       🧾 **اثباتِ صداقتِ انجماد — دو سنجهٔ مستقل، هر دو ثبت‌شده:**
//         (الف) *parity با داور*: شمارشِ سیگنالِ فیلترِ رولینگ در ابزارِ انجماد
//               = **۴۳۸** برای M15 و **۲۵۵** برای H1، که **عیناً** برابرِ
//               judge_M15.json::n_signals=438 و judge_H1.json::n_signals=255
//               است ⇒ پورتِ پایتونیِ day_breaks+چندکِ گپ+فیلترِ V بیت‌به‌بیت درست است.
//         (ب) *هم‌ارزیِ پنجرهٔ زنده* (results/_s562_arms/recency_{M15,H1}.json):
//               در پنجره‌ای که سایت **واقعاً** می‌بیند، آستانهٔ منجمد همان
//               تصمیمِ چندکِ رولینگ را می‌دهد:
//                 M15 @ ۲۲ روز → گپ ۱۰۰٪ · فیلترِ V ۱۰۰٪ · هم‌آیندی ۱۰۰٪
//                 H1  @ ۶۵ روز → گپ ۱۰۰٪ · فیلترِ V ۱۰۰٪ · هم‌آیندی ۱۰۰٪
//
//       🔴 **و اینجا محدودیتی که پنهان نمی‌شود:** همان فایل‌ها نشان می‌دهند
//          آستانهٔ نوسانِ منجمد اگر روی **کلِ ۱۵.۶ سال** بازپخش شود، فیلترِ
//          رولینگ را بازتولید **نمی‌کند** (M15: ۶۱۳ از ۶۲۲ عبور می‌کند به‌جای
//          ۴۳۸؛ H1: ۳۶۱ از ۳۷۶ به‌جای ۲۵۵). علتش نقصِ پورت نیست — همان پورت
//          در سنجهٔ (الف) بیت‌به‌بیت درست بود — بلکه **جهشِ رژیمِ نوسانِ طلا**ست:
//          نوسانِ ۲۰۲۶ به‌قدری از ۲۰۱۱ بزرگ‌تر است که یک آستانهٔ ثابتِ امروزی،
//          روزهای پرنوسانِ آن سال‌ها را «آرام» می‌بیند. لذا حکمِ صادقانه:
//          **آستانهٔ منجمد فقط برای پنجرهٔ زنده مجاز است، نه برای بازپخشِ تاریخی.**
//          افتِ تدریجی (M15: ۱۲۵روز ۸۹.۳٪ · ۲۵۰روز ۶۸.۱٪ | H1: ۱۲۵روز ۱۰۰٪ ·
//          ۲۵۰روز ۸۰.۰٪) درست همان اثرِ انگشت‌نگاریِ این جهشِ رژیم است.
//
//    ③ **vol_ref خودش زنده می‌مانَد — کمینه‌ترین انجمادِ ممکن.** فقط *آستانهٔ*
//       چندک منجمد است؛ خودِ نوسانِ مرجع (میانگینِ دامنهٔ ۱۴ روزِ اخیر) در
//       مرورگر **زنده** محاسبه می‌شود، چون ۱۴ روز در پنجرهٔ هر دو کارت جا
//       می‌شود. این تفکیک عمدی است: هر چه کمتر منجمد شود، لایهٔ زنده به
//       نسخهٔ داوری‌شده نزدیک‌تر می‌مانَد.
//
//    ④ **علّیتِ سه‌لایه در فیلترِ V** (عیناً پایتون، §۶ بندِ ۱ سند):
//       vol_ref[k] = میانگینِ دامنهٔ روزانهٔ ۱۴ روزِ منتهی به k **شاملِ خودِ k**؛
//       و k = روزی است که سیگنال روی آخرین کندلش می‌نشیند. ورود در open روزِ
//       k+1 است ⇒ هر ۱۴ روز پیش از ورود **کامل شده‌اند** ⇒ صفر look-ahead.
//       شرطِ عبور: `vol_ref[k] <= thr` (کوچک‌تر-مساوی — عیناً پایتون).
//
//    ⑤ **ردِ محافظه‌کارانه در نبودِ تاریخچه.** پایتون اگر vol_ref موجود نباشد
//       (کمتر از ۱۴ روزِ کامل) سیگنال را `continue` می‌کند یعنی **رد**. پورت
//       هم همین می‌کند: نبودِ داده = عدمِ ورود، نه ورودِ بی‌فیلتر. (اگر
//       برعکس عمل می‌کردیم، در ابتدای پنجرهٔ سایت لایه بی‌فیلتر معامله می‌کرد
//       — دقیقاً همان چیزی که دروازهٔ H8 را می‌شکست.)
//
// ماژولار/ROS2-مانند: این فایل کاملاً مستقل است؛ افزودنش فقط دو ورودی در
// CARD_LAYERS (M15 و H1) می‌خواهد و هیچ لایهٔ دیگری را دست نمی‌زند.
// ---------------------------------------------------------------------------
import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision, RegimeInfo } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'
import { dayBreakThreshold } from './gap_open_s560'

const GOLD_PIP = 0.1

/** روزهای میانگینِ دامنه — VOL_N در tools/s562_volfilter.py */
const VOL_N = 14

export interface S562Config {
  id: string            // شناسهٔ کارت (XAUUSD-M15 | XAUUSD-H1)
  tfFa: string          // برچسبِ فارسیِ تایم‌فریم
  tfSec: number         // ثانیهٔ هر کندل (M15⇒900 · H1⇒3600) — برای BUG-BRKTHRESH
  thrWeekendUsd: number // آستانهٔ منجمدِ |گپ| در بازگشاییِ آخرهفته ($/oz)
  thrWeekdayUsd: number // آستانهٔ منجمدِ |گپ| در بازگشاییِ میان‌هفته ($/oz)
  volThrUsd: number     // آستانهٔ منجمدِ نوسانِ مرجع ($) — چندکِ qv از رولینگِ ۲۵۰روزه
  qv: number            // چندکِ قفل‌شدهٔ فیلترِ V (فقط برای نمایش/مستندسازی)
  slPip: number         // براکتِ نادر-فعال (q98 دمِ MFE∪MAE نیمهٔ اول)
  tpPip: number         // متقارن با SL (rr=1.0)
  maxHold: number       // خروجِ زمانیِ خالص (کندل)
  approachFrac: number  // «نزدیک‌شدن»: |گپ| ≥ approachFrac×آستانه (فقط UI)
  rqs2: number          // نمرهٔ RQS2 (نمایش)
  nTrades: number       // n داوری‌شده (نمایش)
  wrPct: number         // WR داوری‌شده (نمایش)
  maxDdPct: number      // maxDD داوری‌شده (نمایش)
}

// ---------------------------------------------------------------------------
// منبعِ حقیقتِ اعداد — نه دست‌نویس، نه حدس:
//   گپ + نوسان + هندسه ⟵ results/_s562_arms/frozen_thresholds_{M15,H1}.json
//   qv + هندسه         ⟵ results/_s562_arms/locked_config.json (BUG-GEOMDRIFT)
//   نمرات               ⟵ §۲ سند / results/_s562_arms/judge_{M15,H1}.json
//
// ⚠️ دامنهٔ مجازِ لایه **فقط** M15 و H1 است (ALLOWED_TFS در ابزارِ پایتون):
//   • M1/M5 → قلمروِ S560 (ACCEPT قطعی) — لمس نشدند.
//   • M30   → قلمروِ لایهٔ ACCEPT دانشمندِ موازی (S404، نمرهٔ 96.8) — عمداً
//             از دامنه حذف شد (قانونِ عدمِ تداخل، §۷ سند).
//   • EURUSD→ به دستورِ کاربر حذف.
//   افزودنِ این لایه به هر کارتِ دیگری = تعمیمِ بی‌شاهد و نقضِ قانونِ Multi-TF.
// ---------------------------------------------------------------------------
export const S562_CFG: Record<string, S562Config> = {
  'XAUUSD-M15': {
    id: 'XAUUSD-M15', tfFa: 'M15',
    tfSec: 900,                    // ⇒ dayBreakThreshold = max(1800, 1350) = 1800s
    thrWeekendUsd: 2.056,
    thrWeekdayUsd: 0.766,
    volThrUsd: 143.3813,
    qv: 85,
    slPip: 50.9, tpPip: 50.9, maxHold: 1,
    approachFrac: 0.75,
    rqs2: 95.3, nTrades: 438, wrPct: 70.78, maxDdPct: 3.71,
  },
  'XAUUSD-H1': {
    id: 'XAUUSD-H1', tfFa: 'H1',
    tfSec: 3600,                   // ⇒ dayBreakThreshold = max(1800, 5400) = 5400s
    thrWeekendUsd: 2.952,
    thrWeekdayUsd: 0.980,
    volThrUsd: 132.0466,
    qv: 78,
    slPip: 101.4, tpPip: 101.4, maxHold: 2,
    approachFrac: 0.75,
    rqs2: 96.0, nTrades: 254, wrPct: 68.90, maxDdPct: 2.07,
  },
}

export interface S562Signal {
  /** سیگنالِ نهایی (پایه ∧ فیلترِ V ∧ گاردِ سلامت) */
  active: boolean
  approaching: boolean
  /** سیگنالِ **پایهٔ** S560 (پیش از فیلترِ V) — برای شفافیتِ UI */
  baseActive: boolean
  /** فیلترِ V عبور داد؟ (روزِ آرام) */
  volPass: boolean
  /** نوسانِ مرجعِ زنده: میانگینِ دامنهٔ روزانهٔ ۱۴ روزِ کامل‌شده ($) */
  volRefUsd: number
  /** آستانهٔ منجمدِ نوسان ($) */
  volThrUsd: number
  /** نسبتِ volRef/volThr — >۱ یعنی رژیمِ پرنوسان ⇒ رد */
  volRatio: number
  /** چند روزِ کاملِ قبل از مرز در دست بود (باید ≥ ۱۴ باشد) */
  volDaysAvail: number
  brkIdx: number
  gapUsd: number
  thrUsd: number
  isWeekend: boolean
  gapHours: number
  atLatestBar: number
  ratio: number
  dataHealthy: boolean
}

// ---------------------------------------------------------------------------
// dailyRanges — تقسیمِ آرایهٔ کندل به «روز»ها و محاسبهٔ دامنهٔ (max high − min low)
// هر روز. پورتِ verbatim بخشِ اولِ vol_filter_mask:
//
//     brk    = day_breaks(t, tf)
//     starts = [0, brk+1...]   ·   ends = [brk..., n-1]
//     rng_day[k] = max(high[starts[k]..ends[k]]) − min(low[starts[k]..ends[k]])
//
// خروجی: آرایهٔ دامنهٔ روزها + آرایهٔ «اندیسِ آخرین کندلِ هر روز» (ends) که برای
// نگاشتِ day_of_end لازم است.
// ---------------------------------------------------------------------------
export function dailyRanges(
  candles: Candle[], tfSec: number,
): { rng: number[]; ends: number[] } {
  const n = candles.length
  const brkThr = dayBreakThreshold(tfSec)
  const brk: number[] = []
  for (let i = 0; i < n - 1; i++) {
    if (candles[i + 1].time - candles[i].time > brkThr) brk.push(i)
  }
  const starts = [0, ...brk.map(b => b + 1)]
  const ends = [...brk, n - 1]
  const rng: number[] = []
  for (let k = 0; k < starts.length; k++) {
    let hi = -Infinity, lo = Infinity
    for (let i = starts[k]; i <= ends[k]; i++) {
      if (candles[i].high > hi) hi = candles[i].high
      if (candles[i].low < lo) lo = candles[i].low
    }
    rng.push(hi - lo)
  }
  return { rng, ends }
}

// ---------------------------------------------------------------------------
// computeS562Signal — سیگنالِ پایهٔ S560 (بازتولیدِ مستقل، بی‌وابستگی به حالتِ S560)
//                     ∧ فیلترِ V ∧ گاردِ سلامتِ فید
//
// چرا سیگنالِ پایه اینجا **دوباره** محاسبه می‌شود و از computeS560Signal فراخوانی
// نمی‌شود: آستانه‌های گپِ S562 برای M15/H1 **متفاوت** از M5 هستند (چندکِ q70/q80
// روی همان TF)، و S560_CFG فقط ورودیِ M5 دارد. فراخوانیِ آن تابع با cfg ناهمسان،
// دامِ خاموشی می‌ساخت. تنها چیزی که از S560 وارد می‌شود `dayBreakThreshold` است
// — همان فرمولِ مشترکِ BUG-BRKTHRESH (تک‌منبعِ حقیقت، بی‌تکرارِ کد).
// ---------------------------------------------------------------------------
export function computeS562Signal(candles: Candle[], cfg: S562Config): S562Signal {
  const empty: S562Signal = {
    active: false, approaching: false, baseActive: false,
    volPass: false, volRefUsd: NaN, volThrUsd: cfg.volThrUsd, volRatio: NaN,
    volDaysAvail: 0, brkIdx: -1, gapUsd: NaN, thrUsd: NaN,
    isWeekend: false, gapHours: NaN, atLatestBar: -1, ratio: 0, dataHealthy: false,
  }
  const n = candles.length
  if (n < 3) return empty

  const brkThr = dayBreakThreshold(cfg.tfSec)

  // --- آخرین مرزِ روز (i و i+1 هر دو در آرایه) — عیناً منطقِ S560 -------------
  let brk = -1
  for (let i = n - 2; i >= 1; i--) {
    if (candles[i + 1].time - candles[i].time > brkThr) { brk = i; break }
  }
  if (brk < 0) return empty

  const prev = candles[brk]          // آخرین کندلِ روزِ قبل (سیگنال اینجا می‌نشیند)
  const first = candles[brk + 1]     // اولین کندلِ روزِ نو   (ورود در open همین)

  const dt = first.time - prev.time
  const isWeekend = dt > 86400                       // عیناً پایتون: > 86400s
  const gapUsd = first.open - prev.close             // علامت‌دار
  const thrUsd = isWeekend ? cfg.thrWeekendUsd : cfg.thrWeekdayUsd
  const absGap = Math.abs(gapUsd)
  const ratio = thrUsd > 0 ? absGap / thrUsd : 0

  // --- گاردِ سلامتِ فید (ارثی از S560، علّی و فقط سمتِ گذشته) ------------------
  const dataHealthy = (candles[brk].time - candles[brk - 1].time) <= brkThr

  // --- سیگنالِ پایه: گپِ منفیِ اکیداً عمیق‌تر از آستانه -----------------------
  const baseActive = gapUsd < 0 && absGap > thrUsd && dataHealthy

  // --- فیلترِ V (دامِ ④): vol_ref = میانگینِ دامنهٔ ۱۴ روزِ منتهی به روزِ مرز ---
  //   روزِ مرز = روزی که آخرین کندلش `brk` است. پس در آرایهٔ ends باید اندیسِ
  //   brk را یافت؛ آن k همان روزِ k پایتون است و ۱۴ روزِ [k-13..k] لازم است.
  const { rng, ends } = dailyRanges(candles, cfg.tfSec)
  let kDay = -1
  for (let k = 0; k < ends.length; k++) { if (ends[k] === brk) { kDay = k; break } }

  let volRefUsd = NaN
  let volDaysAvail = 0
  if (kDay >= 0) {
    volDaysAvail = kDay + 1                         // روزهای کاملِ در دست تا k
    if (kDay >= VOL_N - 1) {
      let s = 0
      for (let j = kDay - (VOL_N - 1); j <= kDay; j++) s += rng[j]
      volRefUsd = s / VOL_N
    }
  }
  // شرطِ عبور عیناً پایتون: vol_ref <= thr  (روزِ آرام).
  // دامِ ⑤: نبودِ تاریخچه ⇒ رد (نه عبور).
  const volPass = isFinite(volRefUsd) && volRefUsd <= cfg.volThrUsd
  const volRatio = isFinite(volRefUsd) ? volRefUsd / cfg.volThrUsd : NaN

  const cond = baseActive && volPass
  // «نزدیک‌شدن» فقط UI است: گپِ منفیِ کم‌عمق **ولی** در روزِ آرام (اگر فیلتر رد
  // کرده باشد، نزدیک‌شدن معنا ندارد چون رژیم غلط است).
  const approaching = !cond && volPass && gapUsd < 0 && ratio >= cfg.approachFrac

  return {
    active: cond, approaching, baseActive,
    volPass, volRefUsd, volThrUsd: cfg.volThrUsd, volRatio, volDaysAvail,
    brkIdx: brk, gapUsd, thrUsd, isWeekend,
    gapHours: dt / 3600,
    atLatestBar: (n - 1) - (brk + 1),   // ۰ ⇒ کندلِ اولِ روزِ نو آخرین کندلِ بسته است
    ratio, dataHealthy,
  }
}

// ---------------------------------------------------------------------------
// decideS562 — RawSignal → RouterDecision
//
// ⚠️ **صداقتِ پنجرهٔ معامله** (ارثی از S560 و اینجا هم رعایت می‌شود):
//   هندسهٔ قفل‌شده maxHold ∈ {۱ کندلِ M15, ۲ کندلِ H1} ⇒ پنجرهٔ کلِ معامله
//   ۱۵ دقیقه (M15) یا ۲ ساعت (H1) است. سایت منطق را — درست، برای ضدِ
//   repainting — روی **کندل‌های بسته** اجرا می‌کند؛ پس وقتی سایت کندلِ اولِ
//   روزِ نو را «بسته» می‌بیند، بخشی از آن پنجره گذشته است.
//
//   این واقعیت پنهان نمی‌شود: با atLatestBar و FRESH_MAX_BARS اعلام می‌گردد.
//     • M15 (maxHold=1) ⇒ فقط atLatestBar=0 تازه است.
//     • H1  (maxHold=2) ⇒ atLatestBar ∈ {0,1} تازه است، چون معامله دو کندل
//       نگه‌داری می‌شود و در کندلِ دومْ هنوز پوزیشن باز است.
//   هیچ تلاشی برای «بازکردنِ مصنوعیِ» پنجره (سنجشِ سیگنال روی کندلِ در حالِ
//   شکل‌گیری) نمی‌شود — آن کار look-ahead می‌ساخت و حکمِ RQS2 را بی‌اعتبار می‌کرد.
// ---------------------------------------------------------------------------
export function decideS562(
  cfg: S562Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const s = computeS562Signal(candles, cfg)
  const price = a.price

  // پنجرهٔ تازگی = maxHold − 1 کندل پس از ورود (H1 دو کندل نگه می‌دارد)
  const freshMaxBars = Math.max(0, cfg.maxHold - 1)
  const fresh = s.atLatestBar >= 0 && s.atLatestBar <= freshMaxBars

  const active = s.active && fresh
  const approaching = (!active && s.approaching && fresh) ? true : false

  const kindFa = s.isWeekend ? 'بازگشاییِ آخرهفته (دوشنبه)' : 'بازگشاییِ روزِ کاری'
  const gapAbs = Math.abs(s.gapUsd)
  const gapPip = isFinite(gapAbs) ? gapAbs / GOLD_PIP : NaN
  const holdFa = cfg.maxHold === 1 ? `۱ کندلِ ${cfg.tfFa}` : `${cfg.maxHold} کندلِ ${cfg.tfFa}`

  let reason: string
  if (active) {
    reason =
      `گپِ منفیِ بازگشایی **و** فیلترِ نوسان، هر دو تأیید شدند: بازار روزِ نو را ` +
      `${gapAbs.toFixed(2)}$ (${gapPip.toFixed(0)} pip) **زیرِ** بستهٔ روزِ قبل باز کرد ` +
      `— بزرگ‌تر از آستانهٔ منجمدِ ${s.thrUsd.toFixed(3)}$ برای ${kindFa} ` +
      `(نسبت ${s.ratio.toFixed(2)}×) — و نوسانِ مرجعِ روزِ قبل ` +
      `${s.volRefUsd.toFixed(1)}$ است که **زیرِ** سقفِ ${s.volThrUsd.toFixed(1)}$ ` +
      `(چندکِ ${cfg.qv}) می‌نشیند ⇒ رژیمِ «روزِ آرام» ⇒ مجازِ ورود. ` +
      `طبقِ سند (RQS2=${cfg.rqs2}، WR ${cfg.wrPct}٪ روی n=${cfg.nTrades}، maxDD ${cfg.maxDdPct}٪) ` +
      `این فروشِ هیجانیِ بازگشایی گرایشِ قویِ آماری به بازگشتِ رو به بالا دارد ⇒ ` +
      `LONG با خروجِ زمانیِ ${holdFa}. ⏱️ پنجره کوتاه است: ورودِ بک‌تستی در open ` +
      `کندلِ اولِ روز بود.`
  } else if (s.baseActive && !s.volPass && isFinite(s.volRefUsd)) {
    // ← مهم‌ترین پیامِ نوِ این لایه نسبت به S560: ردِ رژیمی
    reason =
      `⛔ گپِ منفیِ کافی وجود دارد (${gapAbs.toFixed(2)}$ در ${kindFa}، ` +
      `${s.ratio.toFixed(2)}× آستانه) **ولی فیلترِ نوسان آن را رد کرد**: نوسانِ ` +
      `مرجعِ روزِ قبل ${s.volRefUsd.toFixed(1)}$ است، بالاتر از سقفِ منجمدِ ` +
      `${s.volThrUsd.toFixed(1)}$ (${(s.volRatio * 100).toFixed(0)}٪) ⇒ بازار در ` +
      `**رژیمِ پرنوسان** است. این همان کشفِ مرکزیِ S562 است (قانونِ DD-انتقال، §۴ سند): ` +
      `خوشه‌های باختِ لایه‌های گپ در روزهای پرنوسان زندگی می‌کنند؛ حذفِ همین روزها ` +
      `maxDD را از ۱۲.۴٪ به ۳.۷٪ (M15) و از ۹.۵٪ به ۲.۱٪ (H1) رساند. پس این «ردْ» ` +
      `نقصِ سیگنال نیست — **خودِ مهارتِ لایه** است.`
  } else if (s.baseActive && !isFinite(s.volRefUsd)) {
    reason =
      `گپِ منفیِ کافی وجود دارد ولی **تاریخچهٔ نوسان ناکافی است**: فیلترِ V به ` +
      `میانگینِ دامنهٔ ${VOL_N} روزِ کامل نیاز دارد و فقط ${s.volDaysAvail} روز در ` +
      `پنجرهٔ داده هست. طبقِ منطقِ محافظه‌کارانهٔ ابزارِ داوری (نبودِ تاریخچه = رد، ` +
      `نه عبورِ بی‌فیلتر)، ورود مجاز نیست. اگر برعکس عمل می‌شد، لایه در ابتدای ` +
      `پنجره بی‌فیلتر معامله می‌کرد — همان چیزی که دروازهٔ H8 را می‌شکست.`
  } else if (s.active && !fresh) {
    reason =
      `سیگنالِ کاملِ S562 **امروز رخ داد** (گپ ${gapAbs.toFixed(2)}$ در ${kindFa}، ` +
      `روزِ آرام) ولی پنجرهٔ ${holdFa}ی آن ${s.atLatestBar} کندل پیش بسته شد. ` +
      `هندسهٔ قفل‌شده maxHold=${cfg.maxHold} است ⇒ ورودِ تأخیری هیچ ربطی به حکمِ ` +
      `اندازه‌گیری‌شده ندارد. صادقانه: این فرصت از دست رفته است، نه یک ورودِ معتبر.`
  } else if (s.brkIdx < 0) {
    reason =
      `هیچ مرزِ روزی در پنجرهٔ کندل‌های موجود نیست (این لایه فقط در لحظهٔ ` +
      `بازگشاییِ روز معنا دارد). لایه روزی یک‌بار ارزیابی می‌شود.`
  } else if (!s.dataHealthy) {
    reason =
      `⚠️ **دادهٔ فید در این ناحیه ناپیوسته است** ⇒ لایه عمداً مسدود شد. ` +
      `کندلِ ماقبلِ مرزِ روز با وقفه‌ای بزرگ‌تر از حدِ مجاز آمده، یعنی «بستهٔ ` +
      `روزِ قبل» قیمتی **کهنه** است و گپِ ${gapAbs.toFixed(2)}$ی محاسبه‌شده مصنوعِ ` +
      `شکافِ داده است، نه رفتارِ واقعیِ بازار.`
  } else if (s.gapUsd >= 0) {
    reason =
      `آخرین بازگشایی (${kindFa}) گپِ **مثبت/صفر** داشت (${s.gapUsd.toFixed(2)}$) — ` +
      `این لایه فقط گپِ منفی را معامله می‌کند (فروشِ هیجانی)، پس بی‌سیگنال است.`
  } else {
    const volFa = isFinite(s.volRefUsd)
      ? `نوسانِ مرجع ${s.volRefUsd.toFixed(1)}$ ${s.volPass ? 'زیرِ' : 'بالای'} سقفِ ${s.volThrUsd.toFixed(1)}$`
      : `تاریخچهٔ نوسان ناکافی (${s.volDaysAvail}/${VOL_N} روز)`
    reason =
      `گپِ منفیِ آخرین بازگشایی کم‌عمق بود: ${gapAbs.toFixed(2)}$ یعنی ` +
      `${(s.ratio * 100).toFixed(0)}٪ آستانهٔ ${s.thrUsd.toFixed(3)}$ برای ${kindFa} ` +
      `(${volFa}). لایه کم‌بسامد است (${cfg.nTrades} معامله در ۱۵.۶ سال) و بیشترِ ` +
      `بازگشایی‌ها هیچ‌اند — همین صداقتِ لایه است.`
  }

  const indicators: RouterDecision['indicators'] = [
    {
      name: 'مرزِ روز (بازگشایی)',
      value: s.brkIdx >= 0 ? `${kindFa} · وقفهٔ ${s.gapHours.toFixed(1)}h` : '—',
      status: s.brkIdx >= 0 ? 'ok' : 'neutral',
    },
    {
      name: 'جهتِ گپ (باید منفی باشد)',
      value: isFinite(s.gapUsd)
        ? `${s.gapUsd >= 0 ? '+' : ''}${s.gapUsd.toFixed(2)}$` + (s.gapUsd < 0 ? ' ✔' : ' ✘')
        : '—',
      status: s.gapUsd < 0 ? 'ok' : 'bad',
    },
    {
      name: `عمقِ گپ > آستانهٔ منجمد (${isFinite(s.thrUsd) ? s.thrUsd.toFixed(3) : '—'}$)`,
      value: isFinite(gapAbs)
        ? `${gapAbs.toFixed(2)}$ (${(s.ratio * 100).toFixed(0)}٪)` + (s.baseActive ? ' ✔' : '')
        : '—',
      status: s.baseActive ? 'ok' : (s.ratio >= cfg.approachFrac ? 'warn' : 'bad'),
    },
    {
      // ⭐ دروازهٔ نوِ S562 — همان چیزی که لایه را از S560 جدا می‌کند
      name: `⭐ فیلترِ نوسان: مرجعِ ۱۴روزه ≤ سقفِ q${cfg.qv} (${cfg.volThrUsd.toFixed(1)}$)`,
      value: isFinite(s.volRefUsd)
        ? `${s.volRefUsd.toFixed(1)}$ (${(s.volRatio * 100).toFixed(0)}٪) ` +
          (s.volPass ? '✔ روزِ آرام' : '✘ رژیمِ پرنوسان')
        : `تاریخچه ناکافی (${s.volDaysAvail}/${VOL_N} روز) ✘`,
      status: s.volPass ? 'ok' : 'bad',
    },
    {
      name: `تازگیِ پنجره (maxHold=${cfg.maxHold} کندلِ ${cfg.tfFa})`,
      value: s.brkIdx < 0 ? '—' : (fresh ? 'باز ✔' : `بسته — ${s.atLatestBar} کندل گذشته ✘`),
      status: s.brkIdx < 0 ? 'neutral' : (fresh ? 'ok' : 'bad'),
    },
    {
      name: 'پیوستگیِ فیدِ داده (گاردِ ضدِ گپِ جعلی)',
      value: s.brkIdx < 0 ? '—' : (s.dataHealthy ? 'سالم ✔' : 'ناپیوسته — مسدود ✘'),
      status: s.brkIdx < 0 ? 'neutral' : (s.dataHealthy ? 'ok' : 'bad'),
    },
  ]

  const raw: RawSignal = {
    active, approaching,
    direction: 'LONG',                       // LONG-only (گپِ منفی ⇒ بازگشتِ بالا)
    slDist: cfg.slPip * GOLD_PIP,
    tpDist: cfg.tpPip * GOLD_PIP,
    maxHoldBars: cfg.maxHold,
    reason,
    approachReason: approaching
      ? `منتظرِ عمیق‌شدنِ گپ تا عبور از ${s.thrUsd.toFixed(3)}$ (اکنون ${(s.ratio * 100).toFixed(0)}٪) — رژیمِ نوسان مجاز است`
      : undefined,
    indicators,
  }

  const reg: RegimeInfo = {
    regime: 'range',                         // رویدادِ بازگشتی، نه روندی
    efficiencyRatio: 0, trendy: false,
    adx: 0, activeStream: active ? 'bull' : 'none',
    bucket: `s562_${cfg.tfFa.toLowerCase()}`,
  }

  const meta: DecideMeta = {
    code: 'S562',
    name: `گپِ منفیِ بازگشایی + فیلترِ نوسان (${cfg.tfFa})`,
    kind: 'gap_open' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote:
      `⏱️ **خروجِ زمانی حاکم است، نه استاپِ قیمتی.** هندسهٔ قفل‌شدهٔ بازوِ V-TIME ` +
      `(منجمد از S560، assertِ BUG-GEOMDRIFT): در close کندلِ ${cfg.maxHold}ُمِ ` +
      `${cfg.tfFa} پس از ورود خارج شو. براکتِ SL=TP=${cfg.slPip} pip فقط ` +
      `**محافظِ نادر-فعال** است (چندکِ ۹۸ دمِ MFE∪MAE نیمهٔ اول) و در حالتِ عادی ` +
      `نباید فعال شود — درسِ ۱ خانوادهٔ گپ: بازوِ استاپ-قیمتی (V-BRK) در هر ۵ ` +
      `تایم‌فریم مغلوب شد، و S561 با تنگ‌کردنِ براکت DD را از ۱۲.۴٪ به ۲۷.۳٪ ` +
      `**بدتر** کرد ⇒ استاپ را تنگ نکن. ⚠️ قیدِ تک‌معامله (allow_overlap=false): ` +
      `تا این معامله بسته نشده، بازگشاییِ بعدی نباید معاملهٔ نو باز کند. ` +
      `⚠️ هم‌خانوادگیِ M15↔H1 (jaccard روزانه ۰.۵۶، §۵ سند): این دو کارت غالباً ` +
      `**یک رویداد** را نشان می‌دهند؛ در سایزبندیِ پرتفوی یک خانواده بشمار، نه دو.`,
    filters: [
      `مرزِ روز: وقفهٔ زمانی > ${dayBreakThreshold(cfg.tfSec)}s (قاعدهٔ BUG-BRKTHRESH برای ${cfg.tfFa})`,
      'گپ = open(کندلِ اولِ روز) − close(آخرین کندلِ روزِ قبل) — باید **منفی** باشد',
      `عمقِ گپ اکیداً > آستانهٔ منجمد (آخرهفته ${cfg.thrWeekendUsd}$ / روزِ کاری ${cfg.thrWeekdayUsd}$)`,
      'تفکیکِ آخرهفته/میان‌هفته (گپِ دوشنبه ≈۸× گپِ روزانه)',
      `⭐ فیلترِ نوسانِ علّی: میانگینِ دامنهٔ روزانهٔ ${VOL_N} روزِ کامل‌شده ≤ چندکِ q${cfg.qv} ` +
        `(سقفِ منجمدِ ${cfg.volThrUsd.toFixed(1)}$) — تنها درجهٔ آزادیِ نوِ S562`,
      `خروجِ زمانیِ خالص پس از ${holdFa} · LONG-only · n=${cfg.nTrades} در ۱۵.۶ سال`,
    ],
  }

  return rawToDecision(raw, meta, cfg.id, price, reg, capital, riskPct)
}

// ---------------------------------------------------------------------------
// S560 — «گپِ منفیِ بازگشایی» (GapOpen Negative-Gap) · XAUUSD-M5 · LONG-only
//
// حکمِ نهایی (سند: results/S560_GapOpenNegGap_Xauusd_M1M5M15M30H1_rqs2_96_ACCEPT.md):
//   RQS2 = **96.0** · هر ۱۱ دروازه پاس (H0..H10) · صفر دروازهٔ ناموفق
//   n=407 · WR=71.5٪ (291 برد) · PF=2.514 · expectancy=+8.2128 pip
//   maxDD=2.43٪ · maxConsecLosses=5 (مجاز ۸) · recoveryFactor=20.05
//   lift=+43.98pp روی نالِ 27.51٪ · z=19.87 · z_luck_bound=2.985 ⇒ z_margin=16.885
//   p_perm=0.0 (K=500) · n_trials=400 (Path C، پیش‌ثبتِ کامیت 0f0eab53)
//   بازوِ برنده: **V-TIME** (خروجِ زمانیِ خالص) · seed=20260813 · داده: mt5_full 15.6y
//
// فیزیکِ لایه: وقتی بازارِ طلا روزِ نو را با **گپِ منفیِ بزرگ** باز می‌کند (یعنی
// open روزِ جدید به‌طور معناداری زیرِ close روزِ قبل است)، آن گپ گرایشِ آماریِ
// قوی به **بسته‌شدن رو به بالا** در همان کندلِ نخست دارد. این «فروشِ هیجانیِ
// بازگشایی» است، نه اطلاعاتِ نو ⇒ ورودِ LONG در open و خروجِ زمانی بعدِ ۱ کندل.
//
// دو کشفِ ساختاریِ سند که در همین ماژول قفل شده‌اند:
//   ① **تفکیکِ آخرهفته حیاتی است** (درسِ ۲ سند): گپِ بازگشاییِ دوشنبه ≈۸× گپِ
//      میان‌هفته است. آستانهٔ ادغامی، سیگنال‌های میان‌هفته را خفه می‌کند ⇒ دو
//      آستانهٔ جدا: weekend (گپِ زمانیِ >۲۴h) و weekday.
//   ② **خروجِ زمانی > استاپِ قیمتی در رویدادهای گپ** (درسِ ۱ سند): بازوِ V-BRK
//      در هر ۵ تایم‌فریم مغلوب شد. پس SL=TP=48.1 pip فقط **براکتِ نادر-فعالِ
//      محافظ** است (q98 دمِ MFE∪MAE نیمهٔ اول)، و حاکمِ واقعیِ خروج **زمان** است.
//
// ⚠️ پورتِ **مو-به-موی** tools/s560_adjudicate.py::build + tools/s560_gapopen_explore.py
//    ::day_breaks/causal_neg_gap_quantile — چهار دامِ پورت که آگاهانه دفع شده‌اند:
//
//    ① **BUG-BRKTHRESH** (باگِ کشف‌شدهٔ خودِ سند): مرزِ روز = گپِ زمانیِ اکیداً
//       بزرگ‌تر از max(1800s, 1.5×TF_SEC). برای M5 ⇒ max(1800, 450) = **1800s**.
//       نوشتنِ سادهٔ «>۳۰ دقیقه» برای M5 تصادفاً همان است، ولی فرمولِ کلی حفظ
//       می‌شود تا اگر روزی کارتِ M30 وصل شد، باگ برنگردد.
//
//    ② **آستانهٔ علّیِ انبساطی ⇒ در زنده باید «منجمد» شود.** سایت فقط ۵ روز کندلِ
//       M5 دارد (range=5d) ⇒ بازتولیدِ چندکِ انبساطیِ ۱۵.۶ساله در مرورگر
//       ممکن نیست. راهِ درست: آستانه‌ها **یک‌بار** از کلِ تاریخ محاسبه و در
//       results/_s560_arms/frozen_thresholds_M5.json منجمد شده‌اند و اینجا
//       به‌صورتِ ثابتِ عددی می‌آیند. اثباتِ صداقتِ این کار در همان فایل:
//       شمارشِ سیگنالِ چندکِ انبساطی = **407** که **عیناً** برابرِ judge_M5.json
//       ::n_signals = 407 است (پورتِ پایتون بیت‌به‌بیت درست است)، و نسخهٔ
//       منجمد ۴۱۲ سیگنال می‌دهد (+۱.۲٪ — هم‌ارزیِ عملی، بی‌تورشِ آینده‌نگری
//       چون آستانه از گذشتهٔ کاملِ ثابت آمده، نه از آیندهٔ همین معامله).
//
//    ③ **سیگنال روی «آخرین کندلِ روزِ قبل» می‌نشیند، ورود در open کندلِ اولِ روزِ نو.**
//       عیناً build(): mask[brk] = True و موتور در o[brk+1] وارد می‌شود. پس گپ در
//       لحظهٔ ورود **مشاهده‌پذیر** است (نه آینده‌نگر): معامله‌گر open را می‌بیند،
//       گپ را می‌سنجد، و در همان open وارد می‌شود.
//
//    ④ **کندلِ مصنوعیِ rebaseFuturesToSpot.** اگر کندلِ آخر بسته باشد، سایت یک
//       کندلِ زندهٔ نو با open = last.close می‌سازد. گپِ چنین کندلی **ذاتاً صفر**
//       است (open == close قبلی) ⇒ هرگز سیگنالِ کاذب نمی‌سازد. اما این ماژول
//       فقط روی آرایهٔ closedBars(...) کار می‌کند (ورودیِ ctx.candles) که آن
//       کندلِ زنده را پیشاپیش حذف کرده ⇒ مسئله منتفی است. نکتهٔ آفستِ rebase هم
//       بی‌خطر است: آفستِ **ثابت** از همهٔ کندل‌ها کم می‌شود و گپ یک **تفاضل**
//       است ⇒ تحتِ rebase تغییرناپذیر (offset − offset = 0).
// ---------------------------------------------------------------------------
import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision, RegimeInfo } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'

const GOLD_PIP = 0.1

export interface S560Config {
  id: string            // شناسهٔ کارت (XAUUSD-M5)
  tfFa: string          // برچسبِ فارسیِ تایم‌فریم
  tfSec: number         // ثانیهٔ هر کندل (M5 ⇒ 300) — برای BUG-BRKTHRESH
  thrWeekendUsd: number // آستانهٔ منجمدِ |گپ| در بازگشاییِ آخرهفته ($/oz)
  thrWeekdayUsd: number // آستانهٔ منجمدِ |گپ| در بازگشاییِ میان‌هفته ($/oz)
  slPip: number         // براکتِ نادر-فعال (q98 دم) — 48.1 pip
  tpPip: number         // متقارن با SL (rr=1.0) — 48.1 pip
  maxHold: number       // خروجِ زمانی: ۱ کندلِ M5
  approachFrac: number  // «نزدیک‌شدن»: |گپ| ≥ approachFrac×آستانه (فقط UI)
}

export const S560_CFG: Record<string, S560Config> = {
  // تنها کارتِ ACCEPT که در سایت وجود دارد. M1 هم ACCEPT (95.6) بود ولی کارتِ
  // M1 در سایت ساخته نشده ⇒ طبقِ §۱۰ سند فقط M5 وصل می‌شود.
  // M15/M30/H1 حکمِ **REJECT** داشتند (شکستِ H8 = wall-time/DD) ⇒ تعمیمِ
  // بدونِ شاهد ممنوع؛ قانونِ Multi-TF.
  'XAUUSD-M5': {
    id: 'XAUUSD-M5', tfFa: 'M5',
    tfSec: 300,
    // ↓ منبعِ حقیقت: results/_s560_arms/frozen_thresholds_M5.json (q=80، تفکیکِ آخرهفته)
    thrWeekendUsd: 2.952,
    thrWeekdayUsd: 1.010,
    slPip: 48.1, tpPip: 48.1, maxHold: 1,
    approachFrac: 0.75,
  },
}

// ---------------------------------------------------------------------------
// dayBreakThreshold — پورتِ verbatim قاعدهٔ day_breaks (دامِ ① / BUG-BRKTHRESH):
//   thr = max(1800, 1.5 × TF_SEC)  ⇒ مرزِ روز = اندیسی که diff(time) > thr
// برای M5: max(1800, 450) = 1800s. فرمولِ کلی حفظ شده تا اگر تایم‌فریمِ درشت‌تری
// وصل شد، باگِ «هر کندل یک روزِ جعلی» برنگردد.
// ---------------------------------------------------------------------------
export function dayBreakThreshold(tfSec: number): number {
  return Math.max(1800, 1.5 * tfSec)
}

export interface S560Signal {
  active: boolean
  approaching: boolean
  /** اندیسِ «آخرین کندلِ روزِ قبل» در آرایهٔ ورودی (مرزِ روز)؛ -1 اگر مرزی نبود */
  brkIdx: number
  /** گپ = open(کندلِ اولِ روزِ نو) − close(آخرین کندلِ روزِ قبل) — علامت‌دار ($) */
  gapUsd: number
  /** آستانهٔ فعالِ همین مرز ($) */
  thrUsd: number
  /** بازگشاییِ آخرهفته بود؟ (گپِ زمانیِ > ۲۴h) */
  isWeekend: boolean
  /** فاصلهٔ زمانیِ مرز بر حسبِ ساعت (برای نمایش) */
  gapHours: number
  /** آیا مرزِ روز همان **آخرین** جفتِ کندلِ بسته است؟ (پنجرهٔ معامله تازه است) */
  atLatestBar: number
  /** نسبتِ |گپ| به آستانه */
  ratio: number
}

// ---------------------------------------------------------------------------
// computeS560Signal — پورتِ verbatim tools/s560_adjudicate.py::build
//
//   brk    = اندیس‌هایی که diff(time) > thr        (i = آخرین کندلِ روز)
//   gaps   = o[brk+1] − c[brk]                     (علامت‌دار)
//   weekend= (t[brk+1] − t[brk]) > 86400
//   cond   = (gaps < 0) && |gaps| > thr_causal     (اکیداً بزرگ‌تر — عیناً پایتون)
//
// تفاوتِ تنها با پایتون: `thr_causal` به‌جای چندکِ انبساطیِ درجا، از مقدارِ
// **منجمدِ** cfg خوانده می‌شود (دامِ ② — با اثباتِ parity در هدرِ فایل).
//
// این تابع **آخرین مرزِ روزِ موجود** در آرایه را ارزیابی می‌کند؛ چون هندسهٔ
// لایه فقط ۱ کندل نگه‌داری دارد، تنها مرزِ تازه معنا دارد.
// ---------------------------------------------------------------------------
export function computeS560Signal(candles: Candle[], cfg: S560Config): S560Signal {
  const empty: S560Signal = {
    active: false, approaching: false, brkIdx: -1, gapUsd: NaN,
    thrUsd: NaN, isWeekend: false, gapHours: NaN, atLatestBar: -1, ratio: 0,
  }
  const n = candles.length
  if (n < 3) return empty

  const brkThr = dayBreakThreshold(cfg.tfSec)

  // آخرین مرزِ روز را از انتها پیدا کن (i و i+1 هر دو باید در آرایه باشند)
  let brk = -1
  for (let i = n - 2; i >= 1; i--) {
    if (candles[i + 1].time - candles[i].time > brkThr) { brk = i; break }
  }
  if (brk < 0) return empty

  const prev = candles[brk]          // آخرین کندلِ روزِ قبل  (سیگنال اینجا می‌نشیند)
  const first = candles[brk + 1]     // اولین کندلِ روزِ نو    (ورود در open همین)

  const dt = first.time - prev.time
  const isWeekend = dt > 86400                       // عیناً پایتون: > 86400s
  const gapUsd = first.open - prev.close             // علامت‌دار
  const thrUsd = isWeekend ? cfg.thrWeekendUsd : cfg.thrWeekdayUsd

  const absGap = Math.abs(gapUsd)
  const ratio = thrUsd > 0 ? absGap / thrUsd : 0

  // شرطِ ورود — سه‌گانهٔ verbatim: گپ منفی + اکیداً بزرگ‌تر از آستانه
  const cond = gapUsd < 0 && absGap > thrUsd
  // «نزدیک‌شدن» فقط برای UI است و هیچ نقشی در ورود ندارد (گپ منفی ولی کم‌عمق)
  const approaching = !cond && gapUsd < 0 && ratio >= cfg.approachFrac

  return {
    active: cond,
    approaching,
    brkIdx: brk,
    gapUsd,
    thrUsd,
    isWeekend,
    gapHours: dt / 3600,
    atLatestBar: (n - 1) - (brk + 1),   // ۰ ⇒ کندلِ اولِ روزِ نو آخرین کندلِ بسته است
    ratio,
  }
}

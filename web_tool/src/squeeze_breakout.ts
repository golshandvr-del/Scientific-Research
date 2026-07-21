// ============================================================================
// squeeze_breakout.ts — لایهٔ سیگنالِ LONGِ مستقل (کشفِ S132 — رکوردِ +$121,694)
// ----------------------------------------------------------------------------
// قانونِ شمارهٔ ۱ پروژه: فقط «سودِ خالصِ بیشتر» مهم است — Win-Rate مهم نیست.
// تعریفِ رسمیِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD.
//
// ماشهٔ ورود (LONG) — «انفجارِ نوسان پس از فشردگیِ بولینگر»:
//   ۱) فشردگی: پهنای باندِ بولینگر (BandWidth=(Upper−Lower)/Mid) در کندلِ قبل، در
//      پایین‌ترین `sqzPct` صدکِ `sqzLookback=100` کندلِ اخیر باشد («فنرِ فشرده»).
//   ۲) شکستِ صعودی: close از بالاترین high در `breakoutLookback` کندلِ گذشته عبور کند.
//   ۳) گیتِ روند: EMA50 > EMA200 (فقط انفجارِ هم‌سو با بایاسِ صعودی ⇒ فقط LONG).
//
// مبنای ریاضی: خوشه‌بندیِ نوسان (volatility clustering / اثرِ ARCH) — دوره‌های
//   نوسانِ کم به‌طورِ سیستماتیک به دوره‌های نوسانِ بالا منجر می‌شوند؛ جهتِ انفجار
//   با روندِ کلان قید می‌خورد.
//
// اعتبارِ بک‌تست (engine اصلی، ۱۵۰k کندلِ M15، هزینهٔ واقعی، ریسک ۱٪ + compounding):
//   سودِ مستقلِ لایه = +$20,435 | هر دو نیمهٔ داده مثبت (h1 +$1,930، h2 +$15,276)
//   walk-forward هر ۴ پنجره مثبت | همبستگیِ روزانه با پرتفویِ پایه = +0.28 (ناهمبسته)
//   robust در دو ماشهٔ مستقل (0.25/6 و 0.15/10 هر دو افزایشی).
//   افزایشی به رکورد: +$101,259 → +$121,694 (+۲۰.۲٪).
// جزئیات: results/SqueezeBreakout_NetProfit_121694.md
//
// ----------------------------------------------------------------------------
// ★ فیلترِ «قدرتِ شکست» (S136 — رکوردِ +$126,118) — کاهشِ سیگنالِ غلط
// ----------------------------------------------------------------------------
// همهٔ شکست‌ها یکسان نیستند. شکستِ ضعیف (close فقط کمی بالای priorHigh) اغلب
// «شکستِ کاذب» است ⇒ ضررِ کوچکِ پرتکرار (سیگنالِ غلط). معیارِ کمّیِ کیفیت:
//     brk_strength = (close[i] − priorHigh[i]) / ATR14[i]
// تقسیم بر ATR شکست را مقیاس‌ناپذیر از رژیمِ نوسان می‌کند. فیلتر (گیتِ کیفیت):
//     فقط اگر brk_strength ≥ 0.30 ⇒ ورود.  (در غیرِ این‌صورت سیگنال صادر نمی‌شود)
// اثرِ بک‌تست (موتورِ سرمایهٔ رکورد، ۱۵۰k کندل): لایهٔ Squeeze از +$20,435 به
//   +$24,859 رسید (Δ +$4,424) با حذفِ ۱۲۲۷ سیگنالِ غلط و کاهشِ $1,056 ضرر.
//   گیت‌ها: هر دو نیمهٔ داده مثبت + هر ۴ پنجرهٔ WF مثبت + robust در ۳ آستانه.
//   رکوردِ کل: +$121,694 → +$126,118 (+۳.۶٪).
// این «کاشفِ نو» نیست؛ یک گیتِ کیفیت است ⇒ مطابقِ قانونِ #۱، WR تقریباً ثابت
//   می‌ماند ولی با حذفِ ورودهای بی‌کیفیت، ضرر کم و سودِ خالص زیاد می‌شود.
// جزئیات: results/SqueezeBreakoutFilter_NetProfit_126118.md
// ----------------------------------------------------------------------------
// ★★ فیلترِ دوم «RSI اشباعِ خرید» (S138 — رکوردِ +$128,325) — کاهشِ سیگنالِ غلط
// ----------------------------------------------------------------------------
// حتی پس از گیتِ brk_strength≥0.30، در میانِ ورودهای باقی‌مانده هنوز یک الگوی ضرر
// هست: شکستِ صعودی وقتی RSI14 > 75 (اشباعِ خریدِ شدید) رخ می‌دهد، اغلب «شکستِ خسته/
// پایانِ حرکت» است که سریع برمی‌گردد ⇒ سیگنالِ غلطِ پرتکرار. فیلترِ دوم:
//     فقط اگر RSI14(close) ≤ 75 ⇒ ورود.
// اثرِ بک‌تست (موتورِ سرمایهٔ رکورد، ۱۵۰k کندل): لایهٔ Squeeze از +$24,859 به
//   +$27,066 رسید (Δ +$2,207) با حذفِ سیگنال‌های غلطِ اشباعِ خرید و کاهشِ ضرر.
//   گیت‌ها: هر دو نیمهٔ داده مثبت (h1 +$2,481، h2 +$19,478) + هر ۴ پنجرهٔ WF مثبت
//   [+1,366, +902, +4,723, +10,191] + robust در چند فیلترِ مستقل (RSI≤75, RSI≥50,
//   dist_ema200≤3, atr_pct≤0.4 همه افزایشی).
//   رکوردِ کل: +$126,118 → +$128,325 (+۱.۷٪).
// (یافتهٔ مکمل S137: لایهٔ SHORT هیچ امضای ضررِ قابل‌بهره‌برداری نداشت ⇒ فیلتر روی
//  Squeeze اعمال شد، نه SHORT. جزئیات: results/ShortLossFilter_NoEdge_NetProfit_34959.md)
// جزئیات: results/SqueezeSecondFilter_RSI_NetProfit_128325.md
// ============================================================================

import { ema, bollinger, atr, rsi, type Candle } from './indicators'

// آستانهٔ برندهٔ S136 (robust: هر سه آستانهٔ 0.15/0.20/0.30 مثبت بودند؛ 0.30 بیشترین
// سودِ خالص و بیشترین کاهشِ ضرر را هم‌زمان داد). منبعِ حقیقتِ واحد با بک‌تست.
export const BRK_STRENGTH_MIN = 0.30

// آستانهٔ برندهٔ S138 (فیلترِ دوم): شکست فقط اگر RSI14 ≤ 75 پذیرفته شود (حذفِ شکستِ
// اشباعِ خریدِ شدید که اغلب کاذب است). robust: RSI≤75, RSI≥50, dist_ema200≤3,
// atr_pct≤0.4 همه افزایشی بودند؛ RSI≤75 بیشترین سودِ خالص و کاهشِ ضرر را داد.
export const RSI_OVERBOUGHT_MAX = 75

export interface SqueezeConfig {
  bbPeriod: number         // 20
  bbMult: number           // 2.0
  sqzLookback: number      // 100
  sqzPct: number           // 0.25 (پایین‌ترین ۲۵٪ صدکِ پهنای باند = فشرده)
  breakoutLookback: number // 6
  emaFast: number          // 50
  emaSlow: number          // 200
  tpPip: number            // 300
  slPip: number            // 90
  maxHold: number          // 96 کندلِ M15 = ۲۴ ساعت
}

// پارامترِ برندهٔ s133 — منبعِ حقیقتِ واحد برای سایت و APK.
export const DEFAULT_SQUEEZE: SqueezeConfig = {
  bbPeriod: 20, bbMult: 2.0, sqzLookback: 100, sqzPct: 0.25,
  breakoutLookback: 6, emaFast: 50, emaSlow: 200,
  tpPip: 300, slPip: 90, maxHold: 96,
}

export interface SqueezeSignal {
  active: boolean          // ماشهٔ LONG همین الان شلیک کرد؟
  approaching: boolean     // فشرده هست ولی هنوز شکستِ صعودی رخ نداده
  squeezed: boolean        // آیا بازار فشرده است؟ (پهنای باند در کفِ محلی)
  bandwidth: number        // پهنای باندِ فعلی
  bwPct: number            // صدکِ پهنای باندِ فعلی در پنجرهٔ اخیر (۰..۱)
  priorHigh: number        // سقفِ breakoutLookback کندلِ گذشته
  emaFast: number
  emaSlow: number
  trendUp: boolean         // گیتِ روندِ صعودی EMA50>EMA200
  brkStrength: number      // قدرتِ شکست = (close−priorHigh)/ATR14 (S136)
  strongBreak: boolean     // آیا شکست به‌اندازهٔ کافی قوی است؟ (≥ BRK_STRENGTH_MIN)
  rsi14: number            // RSI14 در کندلِ فعلی (S138)
  notOverbought: boolean   // آیا RSI ≤ 75 است؟ (فیلترِ دومِ S138)
  reason: string
}

/**
 * محاسبهٔ سیگنالِ LONGِ Squeeze→Breakout از سریِ close/high.
 * بدونِ look-ahead: تصمیمِ کندلِ آخر فقط از داده‌های تا همان کندل استفاده می‌کند.
 */
export function computeSqueeze(
  close: number[], high: number[], cfg: SqueezeConfig = DEFAULT_SQUEEZE,
  low?: number[],
): SqueezeSignal {
  const n = close.length
  const need = cfg.bbPeriod + cfg.sqzLookback + 2
  if (n < need) {
    return {
      active: false, approaching: false, squeezed: false,
      bandwidth: NaN, bwPct: 1, priorHigh: NaN,
      emaFast: NaN, emaSlow: NaN, trendUp: false,
      brkStrength: NaN, strongBreak: false,
      rsi14: NaN, notOverbought: true,
      reason: 'دادهٔ کافی برای باندِ بولینگر / پنجرهٔ فشردگی موجود نیست.',
    }
  }

  const bb = bollinger(close, cfg.bbPeriod, cfg.bbMult)  // { upper, mid, lower }
  // پهنای باند در هر کندل
  const bw: number[] = new Array(n).fill(NaN)
  for (let i = 0; i < n; i++) {
    const mid = bb.mid[i]
    if (isFinite(mid) && mid !== 0 && isFinite(bb.upper[i]) && isFinite(bb.lower[i])) {
      bw[i] = (bb.upper[i] - bb.lower[i]) / mid
    }
  }
  const ef = ema(close, cfg.emaFast)
  const es = ema(close, cfg.emaSlow)

  const i = n - 1        // کندلِ فعلی (آخرین کندلِ بسته‌شده)
  const prev = i - 1     // فشردگی «درست پیش از» کندلِ فعلی سنجیده می‌شود

  // صدکِ پهنای باندِ prev در پنجرهٔ sqzLookback (کف = فشرده)
  const lo = Math.max(0, prev - cfg.sqzLookback + 1)
  const window = bw.slice(lo, prev + 1).filter((v) => isFinite(v))
  const bwPrev = bw[prev]
  let bwPct = 1
  if (window.length > 5 && isFinite(bwPrev)) {
    const below = window.filter((v) => v <= bwPrev).length
    bwPct = below / window.length
  }
  const squeezed = isFinite(bwPrev) && bwPct <= cfg.sqzPct

  // سقفِ breakoutLookback کندلِ گذشته (i-brk .. i-1)
  const bLo = Math.max(0, i - cfg.breakoutLookback)
  let priorHigh = -Infinity
  for (let k = bLo; k < i; k++) if (isFinite(high[k])) priorHigh = Math.max(priorHigh, high[k])
  const breakout = isFinite(close[i]) && close[i] > priorHigh

  const trendUp = isFinite(ef[i]) && isFinite(es[i]) && ef[i] > es[i]

  // ── فیلترِ «قدرتِ شکست» (S136) — کاهشِ سیگنالِ غلط ──
  // brk_strength = (close − priorHigh) / ATR14 ؛ فقط شکست‌های قاطع (≥ 0.30) پذیرفته می‌شوند.
  // ATR14 به low نیاز دارد؛ اگر low در دسترس نباشد (سازگاریِ عقب‌رو) فیلتر خنثی می‌ماند.
  let brkStrength = NaN
  if (low && low.length === n && isFinite(priorHigh) && isFinite(close[i])) {
    const candles: Candle[] = new Array(n)
    for (let k = 0; k < n; k++) {
      candles[k] = { time: 0, open: close[k], high: high[k], low: low[k], close: close[k], volume: 0 }
    }
    const atr14 = atr(candles, 14)
    const a = atr14[i]
    if (isFinite(a) && a > 0) brkStrength = (close[i] - priorHigh) / a
  }
  // اگر brk_strength قابل‌محاسبه نبود (low نداریم) ⇒ به‌طورِ محافظه‌کارانه شکست را قوی فرض کن
  // تا رفتارِ عقب‌رو حفظ شود؛ اما وقتی low داریم (حالتِ سایت) فیلتر واقعاً اعمال می‌شود.
  const strongBreak = !isFinite(brkStrength) || brkStrength >= BRK_STRENGTH_MIN

  // ── فیلترِ دوم «RSI اشباعِ خرید» (S138) — کاهشِ سیگنالِ غلط ──
  // شکست وقتی RSI14 > 75 است اغلب «شکستِ خسته» است ⇒ رد می‌شود.
  const rsiArr = rsi(close, 14)
  const rsi14 = rsiArr[i]
  const notOverbought = !isFinite(rsi14) || rsi14 <= RSI_OVERBOUGHT_MAX

  const active = squeezed && breakout && trendUp && strongBreak && notOverbought
  // «نزدیک‌شدن»: فشرده هست و روند صعودی، ولی شکست هنوز رخ نداده (قیمت زیرِ سقف)
  const approaching = squeezed && trendUp && !breakout

  const bsTxt = isFinite(brkStrength) ? brkStrength.toFixed(2) : '—'
  let reason: string
  if (active) {
    reason =
      `فنرِ فشرده رها شد: پهنای باندِ بولینگر در کفِ محلی بود (صدک ${(bwPct * 100).toFixed(0)}٪ ≤ ` +
      `${(cfg.sqzPct * 100).toFixed(0)}٪) و قیمت سقفِ ${cfg.breakoutLookback} کندلِ اخیر (${priorHigh.toFixed(2)}) را ` +
      `با قدرت شکست (قدرتِ شکست=${bsTxt} ≥ ${BRK_STRENGTH_MIN}) — انفجارِ صعودیِ قاطع هم‌سو با روند (EMA50>EMA200).`
  } else if (squeezed && breakout && trendUp && !strongBreak) {
    // شکست رخ داد ولی ضعیف بود ⇒ فیلترِ S136 آن را به‌عنوانِ «سیگنالِ غلطِ محتمل» رد کرد.
    reason =
      `شکستِ صعودی رخ داد اما ضعیف بود (قدرتِ شکست=${bsTxt} < ${BRK_STRENGTH_MIN}؛ close فقط کمی بالای ` +
      `سقفِ ${priorHigh.toFixed(2)}). طبقِ فیلترِ کاهشِ سیگنالِ غلط (S136)، شکست‌های کم‌قدرت اغلب کاذب‌اند و ` +
      `ضررِ کوچکِ پرتکرار می‌سازند ⇒ ورود انجام نمی‌شود (منتظرِ شکستِ قاطع‌تر بمانید).`
  } else if (squeezed && breakout && trendUp && strongBreak && !notOverbought) {
    // شکستِ قوی بود ولی در اشباعِ خریدِ شدید ⇒ فیلترِ دومِ S138 آن را رد کرد.
    reason =
      `شکستِ صعودیِ قوی رخ داد اما در حالتِ اشباعِ خریدِ شدید (RSI14=${isFinite(rsi14) ? rsi14.toFixed(1) : '—'} > ${RSI_OVERBOUGHT_MAX}). ` +
      `طبقِ فیلترِ دومِ کاهشِ سیگنالِ غلط (S138)، شکست در اوجِ اشباع اغلب «شکستِ خسته» است که سریع ` +
      `برمی‌گردد ⇒ ورود انجام نمی‌شود (منتظرِ خنک‌شدنِ RSI یا ستاپِ بعدی بمانید).`
  } else if (approaching) {
    reason =
      `بازار فشرده است (صدکِ پهنای باند ${(bwPct * 100).toFixed(0)}٪) و روند صعودی؛ ` +
      `منتظرِ «تأییدِ شکست»: بسته‌شدنِ قیمت بالای سقفِ ${cfg.breakoutLookback} کندلِ اخیر (${priorHigh.toFixed(2)}$).`
  } else if (!trendUp) {
    reason = `گیتِ روندِ صعودی (EMA50>EMA200) برقرار نیست — ماشهٔ Squeeze فقط در بایاسِ صعودی LONG می‌گیرد.`
  } else {
    reason = `بازار به‌اندازهٔ کافی فشرده نیست (صدکِ پهنای باند ${(bwPct * 100).toFixed(0)}٪ > ${(cfg.sqzPct * 100).toFixed(0)}٪).`
  }

  return {
    active, approaching, squeezed,
    bandwidth: isFinite(bwPrev) ? bwPrev : NaN,
    bwPct, priorHigh: isFinite(priorHigh) ? priorHigh : NaN,
    emaFast: ef[i], emaSlow: es[i], trendUp,
    brkStrength, strongBreak, rsi14, notOverbought, reason,
  }
}

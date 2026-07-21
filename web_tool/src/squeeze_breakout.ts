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
// ============================================================================

import { ema, bollinger } from './indicators'

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
  reason: string
}

/**
 * محاسبهٔ سیگنالِ LONGِ Squeeze→Breakout از سریِ close/high.
 * بدونِ look-ahead: تصمیمِ کندلِ آخر فقط از داده‌های تا همان کندل استفاده می‌کند.
 */
export function computeSqueeze(
  close: number[], high: number[], cfg: SqueezeConfig = DEFAULT_SQUEEZE,
): SqueezeSignal {
  const n = close.length
  const need = cfg.bbPeriod + cfg.sqzLookback + 2
  if (n < need) {
    return {
      active: false, approaching: false, squeezed: false,
      bandwidth: NaN, bwPct: 1, priorHigh: NaN,
      emaFast: NaN, emaSlow: NaN, trendUp: false,
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

  const active = squeezed && breakout && trendUp
  // «نزدیک‌شدن»: فشرده هست و روند صعودی، ولی شکست هنوز رخ نداده (قیمت زیرِ سقف)
  const approaching = squeezed && trendUp && !breakout

  let reason: string
  if (active) {
    reason =
      `فنرِ فشرده رها شد: پهنای باندِ بولینگر در کفِ محلی بود (صدک ${(bwPct * 100).toFixed(0)}٪ ≤ ` +
      `${(cfg.sqzPct * 100).toFixed(0)}٪) و قیمت سقفِ ${cfg.breakoutLookback} کندلِ اخیر (${priorHigh.toFixed(2)}) را ` +
      `رو به بالا شکست — انفجارِ صعودی هم‌سو با روند (EMA50>EMA200).`
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
    emaFast: ef[i], emaSlow: es[i], trendUp, reason,
  }
}

// ============================================================================
// لایهٔ «Al Brooks High-2» روی طلا M15 (S168) — سیگنالِ ساختاریِ price-action
// ----------------------------------------------------------------------------
// منبع: کتابِ «Trading Price Action: TRENDS» اثرِ Al Brooks (منبعِ تلگرام،
//   Telegram-Resource/telegram_source_1/pdfs/1 Trading Price Action - Trends.pdf).
// کشفِ بک‌تست (strategies/s168_brooks_high2_low2.py):
//   در روندِ صعودی (EMA20>EMA50)، اصلاحِ دو-پایه با تشکیلِ «High 2» سیگنالِ ادامهٔ
//   روند می‌دهد. روی XAUUSD long، SL300pt/TP450pt/hold32:
//   net کل +$4,137، WR ۴۸.۸٪، PF ۱.۱۰. walk-forward ۴-پنجره همه مثبت.
//   لبهٔ مستقل تأییدشده: بخشِ خارج از پنجره‌های زمان-محور به‌تنهایی +$1,351
//   (WR ۴۷.۳٪، PF ۱.۰۷) ⇒ لبهٔ ساختاریِ واقعی، نه بازتولیدِ لایه‌های موجود.
//   ⇒ رکوردِ رسمی از +$221,895 به +$223,246 (سهمِ محافظه‌کارانهٔ مستقل).
//
// این لایه فقط برای XAUUSD long فعال است (روی EURUSD در بک‌تست ruin شد).
// معیارِ پروژه: سودِ خالص = XAUUSD + EURUSD (نه Win-Rate)؛ WR فقط کفِ ۴۰٪.
// ============================================================================

// پارامترهای برندهٔ بک‌تست (بر حسبِ point؛ ۱ point طلا = ۰.۰۱$ ⇒ SL300pt=۳.۰۰$).
export const BROOKS_SL_POINT = 300
export const BROOKS_TP_POINT = 450
export const BROOKS_MAX_HOLD = 32
export const BROOKS_EMA_FAST = 20
export const BROOKS_EMA_SLOW = 50
const POINT = 0.01                 // اندازهٔ point طلا بر حسبِ قیمت

export type BrooksState = 'NEUTRAL' | 'APPROACHING' | 'ENTRY'

export interface BrooksSignal {
  state: BrooksState
  slDist: number   // فاصلهٔ SL بر حسبِ قیمت ($)
  tpDist: number   // فاصلهٔ TP بر حسبِ قیمت ($)
  upCount: number  // شمارندهٔ High event در اصلاحِ جاری (۰/۱/۲)
  reason: string
}

// EMA سادهٔ causal روی آرایهٔ close.
function ema(values: number[], period: number): number[] {
  const out = new Array(values.length).fill(NaN)
  const k = 2 / (period + 1)
  let prev = values[0]
  out[0] = prev
  for (let i = 1; i < values.length; i++) {
    prev = values[i] * k + prev * (1 - k)
    out[i] = prev
  }
  return out
}

// ارزیابیِ لایهٔ Brooks High-2 روی کلِ سری (بازمی‌گرداند وضعیتِ آخرین کندلِ بسته).
// منطق دقیقاً همان شمارندهٔ causalِ بک‌تست است (strategies/s168_brooks_high2_low2.py).
export function computeBrooksHigh2(
  high: number[], low: number[], close: number[],
): BrooksSignal {
  const slDist = BROOKS_SL_POINT * POINT
  const tpDist = BROOKS_TP_POINT * POINT
  const n = close.length
  if (n < BROOKS_EMA_SLOW + 5) {
    return { state: 'NEUTRAL', slDist, tpDist, upCount: 0,
      reason: 'دادهٔ کافی برای شمارشِ ساختارِ Brooks موجود نیست.' }
  }

  const ef = ema(close, BROOKS_EMA_FAST)
  const es = ema(close, BROOKS_EMA_SLOW)

  let upCount = 0
  let sawPullback = false
  let signalAtLast = false   // آیا آخرین کندل High-2 (ورود) را تولید کرد؟

  for (let i = 1; i < n; i++) {
    const bull = ef[i] > es[i]
    if (bull) {
      if (high[i] < high[i - 1]) {
        sawPullback = true
      } else if (high[i] > high[i - 1] && sawPullback) {
        upCount += 1
        sawPullback = false
        if (upCount === 2) {
          if (i === n - 1) signalAtLast = true
          upCount = 0
        } else if (upCount >= 4) {
          upCount = 0
        }
      }
    } else {
      upCount = 0
      sawPullback = false
    }
  }

  const bullNow = ef[n - 1] > es[n - 1]

  if (signalAtLast && bullNow) {
    return {
      state: 'ENTRY', slDist, tpDist, upCount: 2,
      reason: `الگوی ساختاریِ «High-2» اثرِ Al Brooks کامل شد: در روندِ صعودی ` +
        `(EMA۲۰>EMA۵۰) دو پایهٔ اصلاح تشکیل و پایهٔ دوم با شکستِ سقفِ کندلِ قبل تأیید شد. ` +
        `طبقِ بک‌تستِ ۱۵۰٬۰۰۰ کندل این لبهٔ ساختاریِ مستقل سودِ خالصِ +$۴٬۱۳۷ ` +
        `(سهمِ مستقلِ +$۱٬۳۵۱، WR ۴۸.۸٪، PF ۱.۱۰) داشت. سیگنالِ خرید (LONG): ` +
        `SL=۳.۰۰$ زیرِ ورود، TP=۴.۵۰$ بالای ورود (R:R=۱.۵). ` +
        `طبقِ قانونِ شمارهٔ ۱ هدف سودِ خالص است نه وین‌ریت.`,
    }
  }

  if (bullNow && (upCount === 1 || sawPullback)) {
    return {
      state: 'APPROACHING', slDist, tpDist, upCount,
      reason: `روند صعودی است (EMA۲۰>EMA۵۰) و پایهٔ اولِ اصلاح (High-1) ` +
        `${upCount === 1 ? 'تشکیل شده' : 'در حالِ تشکیل است'}. اگر پس از یک پایهٔ ` +
        `اصلاحِ دیگر، سقفِ کندلِ قبل دوباره شکسته شود، الگوی «High-2» کامل و سیگنالِ ` +
        `خرید صادر می‌شود. تأییدِ لازم: شکستِ high کندلِ قبلی پس از حداقل یک بارِ pullback.`,
    }
  }

  return {
    state: 'NEUTRAL', slDist, tpDist, upCount,
    reason: bullNow
      ? `روند صعودی است اما هنوز الگوی اصلاحِ دو-پایهٔ Brooks شکل نگرفته ` +
        `(هیچ High-1 فعالی نیست). منتظرِ شروعِ یک اصلاحِ کوتاه در دلِ روند می‌مانیم.`
      : `روند صعودی نیست (EMA۲۰≤EMA۵۰)؛ لایهٔ High-2 فقط در روندِ صعودی ورودِ Long می‌دهد.`,
  }
}

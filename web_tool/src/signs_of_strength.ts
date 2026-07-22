// ============================================================================
// لایهٔ «Al Brooks Signs of Strength» روی طلا M15 (S171) — سنجهٔ عددیِ قدرتِ روند
// ----------------------------------------------------------------------------
// منبع: کتابِ «Trading Price Action: TRENDS» اثرِ Al Brooks، فصلِ ۱۹
//   («Signs of Strength in a Trend»؛ منبعِ تلگرام،
//   Telegram-Resource/telegram_source_1/pdfs/1 Trading Price Action - Trends.pdf).
// کشفِ بک‌تست (strategies/s171_*.py):
//   چهار نشانهٔ عددیِ Brooks برای «روندِ صعودیِ قوی» به یک نمرهٔ ۰..۴ تبدیل شد؛
//   ورود روی «rising-edge» (عبورِ تازهٔ نمره از آستانه). واریانتِ پایدار:
//   w32/thr2/SL300pt/TP450pt/hold96 روی XAUUSD long:
//     کلِ لایه net +$10,251، WR ۵۳.۹٪، PF ۱.۳۶؛ هر ۴ پنجرهٔ walk-forward WR≥۵۰٪.
//   همپوشانی با زمان-محورها ۳۷٪ و با High-2 فقط ۱۱.۵٪ ⇒ سهمِ مستقلِ ناهمبسته:
//     net +$8,130، WR ۵۵.۹٪، PF ۱.۵۳ (هر ۴ پنجره مثبت).
//   ⇒ رکوردِ رسمی از +$225,130 به +$233,260 (سهمِ محافظه‌کارانهٔ مستقل).
//
// این لایه فقط برای XAUUSD long فعال است (روی EURUSD در بک‌تست ruin شد).
// معیارِ پروژه: سودِ خالص = XAUUSD + EURUSD (نه Win-Rate)؛ WR فقط کفِ ۴۰٪.
// ============================================================================

// پارامترهای برندهٔ بک‌تست (point؛ ۱ point طلا = ۰.۰۱$ ⇒ SL300pt=۳.۰۰$).
export const SOS_SL_POINT = 300
export const SOS_TP_POINT = 450
export const SOS_MAX_HOLD = 96
export const SOS_EMA_PERIOD = 20
export const SOS_WINDOW = 32       // پنجرهٔ نگاهِ روند (w32)
export const SOS_THRESHOLD = 2     // آستانهٔ نمره (thr2 از ۴ نشانه)
const POINT = 0.01                 // اندازهٔ point طلا بر حسبِ قیمت

export type SoSState = 'NEUTRAL' | 'APPROACHING' | 'ENTRY'

export interface SoSSignal {
  state: SoSState
  slDist: number    // فاصلهٔ SL بر حسبِ قیمت ($)
  tpDist: number    // فاصلهٔ TP بر حسبِ قیمت ($)
  score: number     // نمرهٔ آخرین کندلِ بسته (۰..۴)
  s1: boolean; s2: boolean; s3: boolean; s4: boolean
  reason: string
}

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

// نمرهٔ Signs-of-Strength برای هر کندل (۰..۴) + تفکیکِ چهار نشانه (causal، shift-safe).
// دقیقاً مطابقِ signs_of_strength_bull در strategies/s171_brooks_signs_of_strength_filter.py.
function computeScores(
  open: number[], high: number[], low: number[], close: number[],
  emaPeriod: number, win: number,
): { score: number[]; s1: boolean[]; s2: boolean[]; s3: boolean[]; s4: boolean[] } {
  const n = close.length
  const emaArr = ema(close, emaPeriod)
  const half = Math.floor(win / 2)

  const s1 = new Array(n).fill(false)
  const s2 = new Array(n).fill(false)
  const s3 = new Array(n).fill(false)
  const s4 = new Array(n).fill(false)
  const score = new Array(n).fill(0)

  for (let i = 0; i < n; i++) {
    if (i < win - 1) continue

    // S1: نسبتِ کندل‌های صعودی (close>open) در win اخیر ≥ ۰.۶۰
    let bullBars = 0
    // S2: میانگینِ |body|/range در win اخیر ≥ ۰.۵۵
    let bodyFracSum = 0
    // S3: هیچ close زیرِ EMA در win اخیر
    let belowCnt = 0
    for (let j = i - win + 1; j <= i; j++) {
      if (close[j] > open[j]) bullBars++
      const rng = Math.max(high[j] - low[j], 1e-12)
      bodyFracSum += Math.abs(close[j] - open[j]) / rng
      if (close[j] < emaArr[j]) belowCnt++
    }
    s1[i] = (bullBars / win) >= 0.60
    s2[i] = (bodyFracSum / win) >= 0.55
    s3[i] = belowCnt <= 0

    // S4: higher-high و higher-low بین نیمهٔ اول و دومِ پنجره
    let hhRecent = -Infinity, hhPrev = -Infinity, llRecent = Infinity, llPrev = Infinity
    for (let j = i - half + 1; j <= i; j++) {           // نیمهٔ اخیر
      if (high[j] > hhRecent) hhRecent = high[j]
      if (low[j] < llRecent) llRecent = low[j]
    }
    for (let j = i - win + 1; j <= i - half; j++) {     // نیمهٔ قبلی
      if (high[j] > hhPrev) hhPrev = high[j]
      if (low[j] < llPrev) llPrev = low[j]
    }
    s4[i] = (hhRecent > hhPrev) && (llRecent > llPrev)

    score[i] = (s1[i] ? 1 : 0) + (s2[i] ? 1 : 0) + (s3[i] ? 1 : 0) + (s4[i] ? 1 : 0)
  }
  return { score, s1, s2, s3, s4 }
}

// ارزیابیِ لایهٔ SoS روی کلِ سری (وضعیتِ آخرین کندلِ بسته).
export function computeSignsOfStrength(
  open: number[], high: number[], low: number[], close: number[],
): SoSSignal {
  const slDist = SOS_SL_POINT * POINT
  const tpDist = SOS_TP_POINT * POINT
  const n = close.length
  if (n < SOS_WINDOW + SOS_EMA_PERIOD + 2) {
    return { state: 'NEUTRAL', slDist, tpDist, score: 0,
      s1: false, s2: false, s3: false, s4: false,
      reason: 'دادهٔ کافی برای سنجهٔ قدرتِ روندِ Brooks موجود نیست.' }
  }

  const { score, s1, s2, s3, s4 } = computeScores(
    open, high, low, close, SOS_EMA_PERIOD, SOS_WINDOW)

  const last = n - 1
  const scLast = score[last]
  const scPrev = score[last - 1]
  const strongNow = scLast >= SOS_THRESHOLD
  const strongPrev = scPrev >= SOS_THRESHOLD
  const risingEdge = strongNow && !strongPrev     // عبورِ تازهٔ نمره از آستانه

  const signList = () => {
    const parts: string[] = []
    if (s1[last]) parts.push('اکثرِ کندل‌ها روندی‌اند')
    if (s2[last]) parts.push('بدنه‌ها بزرگ/سایه‌ها کوتاه (فوریت)')
    if (s3[last]) parts.push('قیمت پیوسته بالای EMA۲۰')
    if (s4[last]) parts.push('سقف‌وکفِ صعودی (swings)')
    return parts.length ? parts.join('، ') : 'هیچ نشانهٔ قوّتی فعال نیست'
  }

  if (risingEdge) {
    return {
      state: 'ENTRY', slDist, tpDist, score: scLast,
      s1: s1[last], s2: s2[last], s3: s3[last], s4: s4[last],
      reason: `الگوی «Signs of Strength» اثرِ Al Brooks (فصلِ ۱۹) تازه فعال شد: نمرهٔ ` +
        `قدرتِ روند از زیرِ آستانه به ${scLast}/۴ رسید (نشانه‌های فعال: ${signList()}). ` +
        `این «rising-edge» نقطهٔ شروعِ فازِ قدرتِ روندِ صعودی است. طبقِ بک‌تستِ ۴ ساله ` +
        `این لبهٔ ساختاریِ مستقل سودِ خالصِ +$۸٬۱۳۰ (WR ۵۵.۹٪، PF ۱.۵۳، هر ۴ پنجرهٔ ` +
        `walk-forward مثبت) داشت. سیگنالِ خرید (LONG): SL=۳.۰۰$ زیرِ ورود، ` +
        `TP=۴.۵۰$ بالای ورود (R:R=۱.۵). طبقِ قانونِ شمارهٔ ۱ هدف سودِ خالص است نه وین‌ریت.`,
    }
  }

  if (strongNow && !risingEdge) {
    return {
      state: 'APPROACHING', slDist, tpDist, score: scLast,
      s1: s1[last], s2: s2[last], s3: s3[last], s4: s4[last],
      reason: `روندِ صعودی همچنان قوی است (نمرهٔ Signs-of-Strength = ${scLast}/۴؛ ` +
        `${signList()}) اما فازِ قدرت پیش‌تر شروع شده و سیگنالِ ورودِ تازه (rising-edge) ` +
        `همین‌الان نیست. لایهٔ S171 فقط در «لحظهٔ تازه شدنِ قدرت» وارد می‌شود تا از ` +
        `ورودِ دیرهنگام پرهیز کند. تأییدِ لازم: افتِ نمره به زیرِ آستانه و سپس عبورِ مجددِ آن.`,
    }
  }

  if (scLast === SOS_THRESHOLD - 1) {
    return {
      state: 'APPROACHING', slDist, tpDist, score: scLast,
      s1: s1[last], s2: s2[last], s3: s3[last], s4: s4[last],
      reason: `نمرهٔ قدرتِ روند ${scLast}/۴ است و تنها یک نشانه تا آستانهٔ ورود ` +
        `(${SOS_THRESHOLD}/۴) فاصله دارد (نشانه‌های فعال: ${signList()}). اگر یک نشانهٔ ` +
        `قوّتِ دیگر (مثلاً بدنه‌های بزرگ‌ترِ روندی یا سقف‌وکفِ صعودی) اضافه شود، الگوی ` +
        `Signs-of-Strength کامل و سیگنالِ خرید صادر می‌شود.`,
    }
  }

  return {
    state: 'NEUTRAL', slDist, tpDist, score: scLast,
    s1: s1[last], s2: s2[last], s3: s3[last], s4: s4[last],
    reason: `نمرهٔ قدرتِ روندِ صعودی پایین است (${scLast}/۴؛ ${signList()}). ` +
      `طبقِ فصلِ ۱۹ کتابِ Brooks، روند هنوز به‌قدرِ کافی «قوی» نیست تا ورودِ ` +
      `روند-دنبال‌کن توجیه شود؛ منتظرِ نشانه‌های بیشترِ قوّت می‌مانیم.`,
  }
}

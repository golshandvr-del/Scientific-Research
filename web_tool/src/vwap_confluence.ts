// ============================================================================
// لایهٔ «Gold Daily-VWAP Confluence Momentum» (S153) — اسکالپِ M5 قیمت-محور
// ----------------------------------------------------------------------------
// کشفِ بک‌تست (strategies/s153_gold_vwap_confluence_momentum.py):
//   محورِ VWAPِ روزانهٔ لنگرشده (daily-anchored) روی طلا M5 اسکن شد. کشف:
//   بازگشت به VWAP (mean-reversion) کار نمی‌کند — طلا روندی است. اما «ادامهٔ
//   حرکت (momentum) بالای VWAP» یک لبهٔ واقعی است: وقتی close بیش از +۱.۵σ بالای
//   VWAPِ روزانه است و هم‌زمان بالای EMA200 (روندِ کلان)، حرکتِ رو‌به‌جلو مثبت است.
//   confluenceِ دوگانه: z>2 ∧ بالای EMA200 ⇒ t=+۱۰.۲۱؛ z>2 ∧ زیرِ EMA200 ⇒ t=−۱.۹۰.
//
//   نتیجهٔ محافظه‌کارانه (risk=0.5%, cd=48): standalone +۱۴٬۱۳۵$، هر ۴ WF مثبت،
//   both-halves مثبت، OOS واقعی مثبت (+۳۵٬۲۹۶$)، corr روزانه با drift طلا = ۰.۳۲۳
//   (<0.35 ⇒ افزایشی). سهمِ افزایشیِ محافظه‌کارانه +۹٬۵۶۹$ ⇒ رکوردِ کل +۲۰۶٬۰۵۰$.
//
// قانونِ شمارهٔ ۱ پروژه: معیارِ همه‌چیز «سودِ خالص» است، نه WR.
//   سودِ خالص = XAUUSD + EURUSD.
// قانونِ طراحیِ سایت: هیچ ارجاعی به شماره‌ی آزمایش‌ها در متنِ نمایشیِ کاربر نمی‌آید.
// ============================================================================

// پارامترهای برندهٔ بک‌تست (بر حسبِ pip؛ ۱pip طلا = ۰.۱۰$ در موتور).
export const VWAP_Z_ENTRY = 1.5        // آستانهٔ ورود (σ بالای VWAP)
export const VWAP_Z_APPROACH = 1.0     // آستانهٔ «نزدیک‌شدن»
export const VWAP_EMA_TREND = 200      // فیلترِ روندِ کلان
export const VWAP_ATR_MULT = 0.5       // حداقلِ رنجِ کندلِ ماشه نسبت به ATR
export const VWAP_SL_PIP = 80          // (موتور pip=0.10 ⇒ ۸۰pip = ۸.۰$)
export const VWAP_TP_PIP = 700         // (۷۰۰pip = ۷۰.۰$ — «بگذار بردها بدوند»)
export const VWAP_MAX_HOLD = 48        // ۴ ساعت روی M5
const PRICE_PIP = 0.10                 // اندازهٔ pip روی قیمتِ طلا ($/oz)

export type VwapState = 'NEUTRAL' | 'APPROACHING' | 'ENTRY'

export interface VwapSignal {
  state: VwapState
  z: number            // z-scoreِ انحرافِ close از VWAPِ روزانه
  vwap: number         // مقدارِ VWAPِ روزانهٔ جاری
  aboveTrend: boolean  // close > EMA200 ؟
  slDist: number       // فاصلهٔ SL بر حسبِ قیمت ($)
  tpDist: number       // فاصلهٔ TP بر حسبِ قیمت ($)
  reason: string
}

/** میانگینِ نمایی (EMA) روی آرایهٔ close. */
function ema(x: number[], span: number): number {
  if (x.length === 0) return NaN
  const k = 2 / (span + 1)
  let e = x[0]
  for (let i = 1; i < x.length; i++) e = x[i] * k + e * (1 - k)
  return e
}

/** ATR سادهٔ N-کندلهٔ اخیر (میانگینِ True Range). */
function atrRecent(high: number[], low: number[], close: number[], period = 14): number {
  const n = close.length
  if (n < 2) return high[n - 1] - low[n - 1]
  let sum = 0, cnt = 0
  for (let i = Math.max(1, n - period); i < n; i++) {
    const tr = Math.max(
      high[i] - low[i],
      Math.abs(high[i] - close[i - 1]),
      Math.abs(low[i] - close[i - 1]),
    )
    sum += tr; cnt++
  }
  return cnt > 0 ? sum / cnt : high[n - 1] - low[n - 1]
}

/**
 * محاسبهٔ VWAPِ روزانهٔ لنگرشده + z-scoreِ انحراف تا کندلِ جاری (forward-safe).
 * از times (ثانیهٔ UTC) برای تشخیصِ مرزِ روزِ معاملاتی استفاده می‌شود؛ اگر volume
 * موجود نبود، وزنِ یکنواخت (typical price سادهٔ بدون‌وزن) به‌کار می‌رود.
 */
export function computeVwap(
  close: number[], high: number[], low: number[],
  times: number[], volume?: number[],
): VwapSignal {
  const n = close.length
  const slDist = VWAP_SL_PIP * PRICE_PIP
  const tpDist = VWAP_TP_PIP * PRICE_PIP
  if (n < 20 || times.length !== n) {
    return {
      state: 'NEUTRAL', z: 0, vwap: close[n - 1] ?? NaN, aboveTrend: false,
      slDist, tpDist,
      reason: 'دادهٔ کافی برای محاسبهٔ VWAPِ روزانه در دست نیست؛ لایه ساکت است.',
    }
  }

  // روزِ تقویمیِ UTC هر کندل (برای reset روزانهٔ VWAP).
  const dayIdx = times.map(t => Math.floor(t / 86400))
  const curDay = dayIdx[n - 1]

  // VWAPِ روزِ جاری: از اولین کندلِ همان روز تا کندلِ جاری.
  let cumPV = 0, cumV = 0
  const devs: number[] = []
  for (let i = 0; i < n; i++) {
    if (dayIdx[i] !== curDay) continue
    const tp = (high[i] + low[i] + close[i]) / 3
    const w = volume && volume[i] > 0 ? volume[i] : 1
    cumPV += tp * w; cumV += w
    const vw = cumV > 0 ? cumPV / cumV : tp
    devs.push(close[i] - vw)
  }
  const vwap = cumV > 0 ? cumPV / cumV : close[n - 1]
  const dev = close[n - 1] - vwap

  // انحرافِ معیارِ ۶۰-کندلهٔ اخیرِ (price − vwap) درونِ روز — مثلِ موتورِ بک‌تست.
  const win = devs.slice(-60)
  const mean = win.reduce((a, b) => a + b, 0) / win.length
  const variance = win.reduce((a, b) => a + (b - mean) * (b - mean), 0) / win.length
  const sd = Math.sqrt(variance)
  const z = sd > 0 ? dev / sd : 0

  const trend = ema(close, VWAP_EMA_TREND)
  const aboveTrend = close[n - 1] > trend

  // فیلترِ ماشه: کندلِ اخیر سبز و رنجش ≥ ضریبی از ATR (حرکتِ واقعی، نه نویز).
  const green = close[n - 1] > (close[n - 2] ?? close[n - 1])
  const atr = atrRecent(high, low, close, 14)
  const rng = high[n - 1] - low[n - 1]
  const strongCandle = green && rng >= VWAP_ATR_MULT * atr

  const base = { z, vwap, aboveTrend, slDist, tpDist }

  // ENTRY: همگراییِ دوگانه (بالای VWAP با قدرت + بالای روندِ کلان) + ماشهٔ حرکت.
  if (z > VWAP_Z_ENTRY && aboveTrend && strongCandle) {
    return {
      ...base, state: 'ENTRY',
      reason: `قیمت اکنون ${z.toFixed(2)}σ بالای «قیمتِ میانگینِ وزنیِ حجمِ امروز» (VWAP=${vwap.toFixed(2)}$) است ` +
        `و هم‌زمان بالای روندِ کلان (EMA200). این «همگراییِ دوگانه» یک لبهٔ ادامهٔ حرکتِ صعودی است — ` +
        `تحلیلِ ۲۰۰٬۰۰۰ کندلِ M5 نشان می‌دهد در چنین لحظاتی طلا میانگین به‌طورِ معنادار بالاتر می‌رود. ` +
        `طبقِ قانونِ شمارهٔ ۱، هدف سودِ خالص است نه وین‌ریت: TP دور نگه داشته می‌شود تا بردها بدوند.`,
    }
  }

  // APPROACHING: قیمت رو به بالای VWAP می‌رود اما هنوز به آستانهٔ قدرت/روند نرسیده.
  if (z > VWAP_Z_APPROACH && (aboveTrend || z > VWAP_Z_ENTRY)) {
    const missing: string[] = []
    if (z <= VWAP_Z_ENTRY) missing.push(`رسیدنِ فاصله از VWAP به ${VWAP_Z_ENTRY}σ (اکنون ${z.toFixed(2)}σ)`)
    if (!aboveTrend) missing.push('عبورِ قیمت به بالای روندِ کلان (EMA200)')
    if (!strongCandle) missing.push('یک کندلِ صعودیِ قوی به‌عنوانِ تأییدِ حرکت')
    return {
      ...base, state: 'APPROACHING',
      reason: `قیمت ${z.toFixed(2)}σ بالای VWAPِ امروز است و در حالِ فاصله‌گرفتن به سمتِ بالا؛ ` +
        `ستاپِ «همگراییِ VWAP» در حالِ شکل‌گیری است. تأییدهای موردِ انتظار: ${missing.join('، ')}.`,
    }
  }

  return {
    ...base, state: 'NEUTRAL',
    reason: `قیمت اکنون ${z.toFixed(2)}σ نسبت به VWAPِ امروز (${vwap.toFixed(2)}$) است` +
      (aboveTrend ? ' و بالای روندِ کلان' : ' و زیرِ روندِ کلان (EMA200)') +
      `. شرطِ همگراییِ دوگانه (فاصلهٔ ≥${VWAP_Z_ENTRY}σ بالای VWAP + بالای EMA200 + کندلِ صعودیِ قوی) ` +
      `هنوز برقرار نیست؛ این لایه فقط در آن لحظاتِ نادر ورود می‌کند.`,
  }
}

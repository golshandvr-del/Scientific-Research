// ============================================================================
// Regime-Router + ماشینِ حالتِ ۴-وضعیتی (پیاده‌سازیِ PARADIGM v2 / User Note 2)
// ----------------------------------------------------------------------------
// این ماژول منطقِ برندهٔ بک‌تست S63 (Rolling Regime-Router) را به یک تصمیمِ
// ۴-حالتی برای سایت تبدیل می‌کند. معیارِ طراحی: «سودِ خالص» — یعنی فقط وقتی
// وارد می‌شویم که رژیم واقعاً محلِ درستِ استفادهٔ یک استراتژی باشد.
//
// چهار حالت (طبقِ درخواستِ کاربر):
//   NEUTRAL    (خنثی)            — دلیلِ عدمِ ورود + مقادیرِ نامشخص.
//   APPROACHING(نزدیک‌شدن)        — ستاپ در حالِ شکل‌گیری + تأییدهایِ موردِ انتظار.
//   ENTRY      (ورود)            — جهت + TP + SL.
//   MANAGE     (مدیریتِ معامله)   — پس از ثبتِ معاملهٔ کاربر (در trade_manager).
// ============================================================================
import type { AnalysisResult } from './signal'

export type RouterState = 'NEUTRAL' | 'APPROACHING' | 'ENTRY'
export type Regime = 'trend_up' | 'trend_down' | 'range'

export interface RegimeInfo {
  regime: Regime
  efficiencyRatio: number       // ER کافمن (روندی‌بودن)
  trendy: boolean               // ER ≥ آستانه
  adx: number
  activeStream: 'bull' | 'bear' | 'none'
  bucket: string                // مثلِ trend_hi (سطلِ رژیمِ S63)
}

export interface Confirmation {
  label: string
  met: boolean
  detail: string
}

export interface RouterDecision {
  state: RouterState
  regime: RegimeInfo
  headline: string              // خطِ اصلیِ تصمیم (فارسی)
  reason: string                // دلیلِ دقیق (چرا این حالت)
  // فقط در ENTRY پر می‌شوند:
  direction?: 'LONG' | 'SHORT'
  entry?: number
  tp?: number
  sl?: number
  rr?: string
  probability?: number
  // فقط در APPROACHING: تأییدهایِ لازم
  confirmations?: Confirmation[]
  // شاخص‌های کلیدی برای شفافیت (همیشه)
  indicators: { name: string; value: string; status: 'ok' | 'warn' | 'bad' | 'neutral' }[]
}

// آستانه‌ها — هم‌راستا با بک‌تست S63
const ER_TREND_THR = 0.30       // ER بالاتر = روندی (سطلِ trend)
const P_HI = 66                 // قدرتِ بالای proba (٪) — سطلِ hi
const P_MIN = 58                // حداقلِ probaِ ورود (٪)
const P_APPROACH = 52           // آستانهٔ «نزدیک‌شدن» (٪)

/**
 * Efficiency-Ratio کافمن روی آرایهٔ close (بدونِ آینده: تا کندلِ قبل).
 */
export function efficiencyRatio(close: number[], win = 32): number {
  const n = close.length
  if (n < win + 2) return 0
  // تا کندلِ i-1 (shift(1)) — پس روی [n-1-win .. n-1]
  const end = n - 1
  const start = end - win
  const net = Math.abs(close[end] - close[start])
  let vol = 0
  for (let i = start + 1; i <= end; i++) vol += Math.abs(close[i] - close[i - 1])
  return vol > 0 ? net / vol : 0
}

/**
 * محاسبهٔ رژیمِ زنده از خروجیِ analyze + سریِ close.
 */
export function computeRegime(a: AnalysisResult, close: number[]): RegimeInfo {
  const er = efficiencyRatio(close, 32)
  const trendy = er >= ER_TREND_THR
  let regime: Regime = 'range'
  let activeStream: 'bull' | 'bear' | 'none' = 'none'
  if (a.regimeOk) { regime = 'trend_up'; activeStream = 'bull' }
  else if (a.trend === 'down' && a.price < a.ema50 && a.ema50 < a.ema200) { regime = 'trend_down'; activeStream = 'bear' }

  const p = a.probability
  const pw = p >= P_HI ? 'hi' : 'lo'
  const ef = trendy ? 'trend' : 'chop'
  const bucket = activeStream === 'none' ? 'none' : `${ef}_${pw}`
  return { regime, efficiencyRatio: er, trendy, adx: a.adx, activeStream, bucket }
}

/**
 * قلبِ Router: از تحلیلِ زنده، تصمیمِ ۴-حالتی می‌سازد.
 *
 * منطقِ برگرفته از L36 (S63):
 *   - Bear-ML در رژیمِ روندیِ نزولی «ستاره» است (اکسپکتنسیِ بالا) → اولویتِ ENTRY.
 *   - Bull-ML کارگرِ باثبات در رژیمِ صعودی.
 *   - رنج/بی‌روند → NEUTRAL (همان رفتاری که در بک‌تست سودِ خالص را نجات داد).
 *   - نزدیکِ آستانه ولی هنوز نه → APPROACHING با ذکرِ تأییدهایِ لازم.
 */
export function decide(a: AnalysisResult, close: number[]): RouterDecision {
  const reg = computeRegime(a, close)
  const p = a.probability
  const atr = a.atr || 1

  // شاخص‌های کلیدی برای شفافیت (همیشه نمایش داده می‌شوند)
  const indicators: RouterDecision['indicators'] = [
    { name: 'روند (EMA50/200)', value: reg.regime === 'trend_up' ? 'صعودی' : reg.regime === 'trend_down' ? 'نزولی' : 'رنج',
      status: reg.regime === 'range' ? 'neutral' : 'ok' },
    { name: 'کاراییِ روند (ER)', value: reg.efficiencyRatio.toFixed(3) + (reg.trendy ? ' (روندی)' : ' (رنج)'),
      status: reg.trendy ? 'ok' : 'warn' },
    { name: 'قدرتِ روند (ADX)', value: a.adx.toFixed(1), status: a.adx >= 20 ? 'ok' : 'warn' },
    { name: 'احتمالِ مدل', value: p.toFixed(1) + '%', status: p >= P_MIN ? 'ok' : (p >= P_APPROACH ? 'warn' : 'bad') },
    { name: 'RSI(14)', value: a.rsi14.toFixed(1), status: 'neutral' },
    { name: 'ATR', value: atr.toFixed(2) + '$', status: 'neutral' },
  ]

  // --------- حالتِ ۱: رنج / بی‌روند → خنثی (کلیدِ سودِ خالص طبقِ L36) ---------
  if (reg.activeStream === 'none' || reg.regime === 'range') {
    return {
      state: 'NEUTRAL', regime: reg,
      headline: 'خنثی — وارد نمی‌شوم',
      reason: `بازار در رژیمِ رنج/بی‌روند است (روند: ${reg.regime === 'range' ? 'نامشخص' : reg.regime}, ` +
        `کاراییِ روند ER=${reg.efficiencyRatio.toFixed(3)} زیرِ آستانهٔ ${ER_TREND_THR}). ` +
        `طبقِ کشفِ L36، فعال‌شدن در چنین رژیمی سودِ خالص را از بین می‌برد؛ پس منتظر شکل‌گیریِ روند می‌مانم.`,
      indicators,
    }
  }

  // رژیمِ روندی داریم؛ آیا نوسان/کارایی کافی است؟
  if (!reg.trendy) {
    // روندِ اسمی هست ولی کارایی پایین → هنوز خنثی، اما نزدیک به رژیمِ مطلوب
    return {
      state: 'NEUTRAL', regime: reg,
      headline: 'خنثی — روند ضعیف است',
      reason: `جهتِ ${reg.regime === 'trend_up' ? 'صعودی' : 'نزولی'} برقرار است اما کاراییِ روند ` +
        `(ER=${reg.efficiencyRatio.toFixed(3)}) هنوز زیرِ آستانهٔ ${ER_TREND_THR} است — یعنی حرکت پرنوسان و ناکاراست. ` +
        `تا تثبیتِ روندِ کارا وارد نمی‌شوم.`,
      indicators,
    }
  }

  const isBull = reg.activeStream === 'bull'
  const dir: 'LONG' | 'SHORT' = isBull ? 'LONG' : 'SHORT'
  // R:R طبقِ همان جریانِ بک‌تست: Bull TP1.0/SL1.5 ، Bear TP1.4/SL1.7
  const tpM = isBull ? 1.0 : 1.4
  const slM = isBull ? 1.5 : 1.7

  // --------- حالتِ ۳: ورود — همهٔ شرایط (رژیمِ روندی + proba کافی) ---------
  if (p >= P_MIN) {
    const entry = a.price
    const tp = isBull ? entry + tpM * atr : entry - tpM * atr
    const sl = isBull ? entry - slM * atr : entry + slM * atr
    return {
      state: 'ENTRY', regime: reg,
      headline: `ورود ${isBull ? 'خرید (LONG)' : 'فروش (SHORT)'} — رژیمِ روندیِ ${isBull ? 'صعودی' : 'نزولی'} تأیید شد`,
      reason: `رژیمِ روندیِ ${isBull ? 'صعودی' : 'نزولی'} کارا (ER=${reg.efficiencyRatio.toFixed(3)}) + ` +
        `احتمالِ مدل ${p.toFixed(1)}% (بالای آستانهٔ ${P_MIN}%). ` +
        `${!isBull ? 'این «محلِ درستِ استفادهٔ» جریانِ Bear است که در بک‌تست بالاترین اکسپکتنسی را داشت (L34).' : 'جریانِ Bull در رژیمِ صعودیِ کارا فعال شد.'}`,
      direction: dir, entry, tp, sl,
      rr: `TP ${tpM}×ATR / SL ${slM}×ATR (≈ 1:${(tpM / slM).toFixed(2)})`,
      probability: p,
      indicators,
    }
  }

  // --------- حالتِ ۲: نزدیک‌شدن به سیگنال ---------
  if (p >= P_APPROACH) {
    const confirmations: Confirmation[] = [
      { label: `احتمالِ مدل ≥ ${P_MIN}%`, met: false,
        detail: `اکنون ${p.toFixed(1)}% است؛ برای ورود باید به ${P_MIN}% برسد (فاصله: ${(P_MIN - p).toFixed(1)}%).` },
      { label: 'قدرتِ روند ADX ≥ ۲۰', met: a.adx >= 20,
        detail: `ADX فعلی ${a.adx.toFixed(1)} است.` },
      { label: 'کاراییِ روند حفظ شود', met: reg.trendy,
        detail: `ER=${reg.efficiencyRatio.toFixed(3)} (باید ≥ ${ER_TREND_THR} بماند).` },
    ]
    return {
      state: 'APPROACHING', regime: reg,
      headline: `نزدیک‌شدن به سیگنالِ ${isBull ? 'خرید' : 'فروش'} — منتظرِ تأیید`,
      reason: `رژیمِ روندیِ ${isBull ? 'صعودی' : 'نزولی'} کارا شکل گرفته و احتمالِ مدل (${p.toFixed(1)}%) ` +
        `به آستانهٔ ورود نزدیک است ولی هنوز به ${P_MIN}% نرسیده. تا تأییدهایِ زیر وارد نمی‌شوم.`,
      confirmations,
      indicators,
    }
  }

  // در رژیمِ روندی ولی probaِ پایین → خنثی با دلیل
  return {
    state: 'NEUTRAL', regime: reg,
    headline: 'خنثی — احتمالِ ورود پایین است',
    reason: `رژیمِ روندیِ ${isBull ? 'صعودی' : 'نزولی'} کارا هست، اما احتمالِ مدل (${p.toFixed(1)}%) ` +
      `زیرِ آستانهٔ نزدیک‌شدن (${P_APPROACH}%) است. سیگنالِ باکیفیت نداریم؛ صبر می‌کنم.`,
    indicators,
  }
}

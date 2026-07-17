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
  // --- اهرم‌های سودِ خالص (S64 + S65) — فقط در ENTRY ---
  sizing?: {                    // S64: حجمِ رژیم-آگاه (Kelly)
    lotMultiplier: number       // ضریبِ حجم نسبت به واحدِ پایه (۱× = پایه)
    label: string               // برچسبِ فارسی (مثلِ «۲ برابرِ پایه»)
    note: string                // دلیلِ حجم (کیفیتِ سطل)
    // --- S67 (L41): حجمِ لاتِ واقعی بر اساسِ سرمایه + ریسکِ درصدی + فاصلهٔ SL ---
    lots?: number               // حجمِ لاتِ استانداردِ پیشنهادی (۱ لات = ۱۰۰ اونس)
    riskDollars?: number        // مبلغِ ریسکِ دلاری (اگر SL بخورد چقدر ضرر)
    capital?: number            // سرمایهٔ کاربر (ورودی)
    riskPct?: number            // درصدِ ریسکِ پایه (ورودی)
    capitalNote?: string        // توضیحِ محاسبهٔ لاتِ سرمایه‌محور
  }
  tpPlan?: {                    // S65: TPِ رژیم-آگاه
    multiplier: number          // ضریبِ TP نهایی (×ATR)
    note: string                // دلیلِ انتخابِ این TP (سطل)
  }
  slPlan?: {                    // S66 (L40): SLِ رژیم-آگاه — اهرمِ چهارمِ سودِ خالص
    multiplier: number          // ضریبِ SL نهایی (×ATR)
    note: string                // دلیلِ انتخابِ این SL (سطل)
  }
  // فقط در APPROACHING: تأییدهایِ لازم
  confirmations?: Confirmation[]
  // شاخص‌های کلیدی برای شفافیت (همیشه)
  indicators: { name: string; value: string; status: 'ok' | 'warn' | 'bad' | 'neutral' }[]
}

// ============================================================================
// نگاشتِ سطلِ رژیم → (وزنِ Kelly، ضریبِ TP) — کشفِ S64/S65 (L38/L39)
// ----------------------------------------------------------------------------
// در بک‌تستِ walk-forward، برای هر سطلِ رژیم یک وزنِ حجم (بر اساسِ اکسپکتنسیِ
// اخیر، کلیپ‌شده در [۰.۵, ۲.۰]) و یک ضریبِ TP (بیشترین سودِ خالص روی پنجرهٔ اخیر)
// یاد گرفته شد. سطلِ روندیِ پرقدرت (trend_hi) بالاترین وزن و دورترین TP را گرفت،
// چون در رژیمِ روندیِ کارآمد حرکت‌ها ادامه‌دارترند (سودِ خالصِ بیشتر با WR کمتر).
// این جدول همان الگویِ پایدارِ کشف‌شده است (۲۰/۲۰ ترکیبِ پارامتر برنده بودند).
// ============================================================================
// S66 (L40): علاوه بر لات و TP، اکنون **SLِ رژیم-آگاه** هم از سطل می‌آید (اهرمِ چهارم).
// ضرایبِ slBull/slBear همان مقادیرِ غالبِ یادگرفته‌شده در گریدِ walk-forward S66 هستند.
interface BucketPlan {
  lot: number
  tpBull: number; tpBear: number
  slBull: number; slBear: number   // S66: SL رژیم-آگاه
  desc: string
}

const BUCKET_PLAN: Record<string, BucketPlan> = {
  // سطلِ قوی: روندِ کارآمد + probaِ بالا → بیشترین حجم و دورترین TP
  trend_hi: { lot: 2.0, tpBull: 2.0, tpBear: 2.6, slBull: 2.0, slBear: 1.7, desc: 'روندِ کارآمد + احتمالِ بالا — قوی‌ترین سطل' },
  // روندِ کارآمد ولی probaِ متوسط → حجمِ متوسط، TP نیمه-دور
  trend_lo: { lot: 1.3, tpBull: 1.3, tpBear: 1.8, slBull: 2.0, slBear: 2.2, desc: 'روندِ کارآمد + احتمالِ متوسط' },
  // probaِ بالا ولی رژیمِ کم‌کارا → حجمِ کمی بالای پایه، TP نزدیک‌تر
  chop_hi:  { lot: 1.2, tpBull: 1.0, tpBear: 1.4, slBull: 2.0, slBear: 1.45, desc: 'احتمالِ بالا ولی روندِ کم‌کارا' },
  // ضعیف‌ترین سطلِ فعال → حجمِ محافظه‌کارانه، TP نزدیک
  chop_lo:  { lot: 0.7, tpBull: 0.8, tpBear: 1.0, slBull: 2.0, slBear: 1.95, desc: 'سطلِ مرزی — حجمِ محافظه‌کارانه' },
}

function bucketPlan(bucket: string): BucketPlan {
  return BUCKET_PLAN[bucket] ?? { lot: 1.0, tpBull: 1.0, tpBear: 1.4, slBull: 1.5, slBear: 1.7, desc: 'پایه' }
}

function lotLabel(m: number): string {
  if (m >= 1.9) return `~۲ برابرِ حجمِ پایه`
  if (m >= 1.25) return `~${m.toFixed(1)} برابرِ حجمِ پایه`
  if (m >= 0.95) return `حجمِ پایه (۱×)`
  return `~${m.toFixed(1)} برابرِ پایه (کاهش‌یافته)`
}

// ============================================================================
// S67 (L41): مدلِ سرمایه — حجمِ لاتِ واقعی بر اساسِ سرمایه + ریسکِ درصدی + SL
// ----------------------------------------------------------------------------
// کشفِ L41: «سودِ خالص» بدونِ مدلِ سرمایه یک عددِ بی‌مقیاس است. اکنون سایت حجمِ
// لاتِ واقعی را طوری پیشنهاد می‌دهد که اگر SL بخورد، دقیقاً `riskPct%` از سرمایهٔ
// کاربر از دست برود. مدلِ لاتِ واقعیِ XAUUSD: ۱ لات = ۱۰۰ اونس ⇒ حرکتِ ۱$ = ۱۰۰$/لات.
// رجوع: results/TPSL_Plan_CapitalEngine_NetProfit_37156.md · engine/capital_engine.py
// ============================================================================
export const CONTRACT_SIZE = 100         // ۱ لات = ۱۰۰ اونس
export const DEFAULT_CAPITAL = 10_000
export const DEFAULT_RISK_PCT = 1.0
const COMMISSION_PER_LOT = 7.0
const MIN_LOT = 0.01
const MAX_LOT = 100.0
const MAX_EFFECTIVE_RISK_PCT = 5.0

/**
 * حجمِ لاتِ واقعی: طوری که اگر SL بخورد، `riskPct% × lotMultiplier` از سرمایه برود.
 * @param capital سرمایهٔ کاربر ($)
 * @param riskPct درصدِ ریسکِ پایه
 * @param slDist  فاصلهٔ SL به دلار (|entry − sl|)
 * @param lotMult ضریبِ Kelly رژیم-آگاه (S64) — به‌عنوانِ ضریبِ مقیاسِ ریسک
 */
export function computeLots(capital: number, riskPct: number, slDist: number, lotMult: number) {
  const effRiskPct = Math.min(riskPct * lotMult, MAX_EFFECTIVE_RISK_PCT)
  const riskDollars = capital * effRiskPct / 100
  let lots = MIN_LOT
  if (slDist > 0) {
    const lossPerLotAtSl = slDist * CONTRACT_SIZE + COMMISSION_PER_LOT
    lots = riskDollars / lossPerLotAtSl
  }
  lots = Math.min(Math.max(Math.round(lots * 100) / 100, MIN_LOT), MAX_LOT)
  return { lots, riskDollars, effRiskPct }
}

// آستانه‌ها — هم‌راستا با بک‌تستِ برندهٔ فعلی S66/L40 (راهکار A از User Note)
// کاهش از ۰.۳۰ به ۰.۱۵ سودِ خالص را +۱۲.۲٪ بالا برد (۶۰۸۲$ → ۶۸۲۳$) و در هر دو
// نیمهٔ walk-forward بهتر بود. رجوع: results/ER_Threshold_Sweep_NetProfit_UserNoteA_L40_50.md
const ER_TREND_THR = 0.15       // ER بالاتر = روندی (سطلِ trend)
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
export function decide(a: AnalysisResult, close: number[],
                       capital: number = DEFAULT_CAPITAL,
                       riskPct: number = DEFAULT_RISK_PCT): RouterDecision {
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
  const plan = bucketPlan(reg.bucket)
  // --- S66 (L40): ضریبِ SL دیگر ثابت نیست؛ از سطلِ رژیم می‌آید (اهرمِ چهارم) ---
  const slM = isBull ? plan.slBull : plan.slBear
  // --- S65: ضریبِ TP رژیم-آگاه (اهرمِ سوم) ---
  const tpM = isBull ? plan.tpBull : plan.tpBear
  // --- S64: ضریبِ حجم (Kelly) از سطلِ رژیم ---
  const lotM = plan.lot

  // --------- حالتِ ۳: ورود — همهٔ شرایط (رژیمِ روندی + proba کافی) ---------
  if (p >= P_MIN) {
    const entry = a.price
    const tp = isBull ? entry + tpM * atr : entry - tpM * atr
    const sl = isBull ? entry - slM * atr : entry + slM * atr
    // --- S67 (L41): حجمِ لاتِ واقعیِ سرمایه‌محور ---
    const slDist = Math.abs(entry - sl)
    const { lots, riskDollars, effRiskPct } = computeLots(capital, riskPct, slDist, lotM)
    return {
      state: 'ENTRY', regime: reg,
      headline: `ورود ${isBull ? 'خرید (LONG)' : 'فروش (SHORT)'} — رژیمِ روندیِ ${isBull ? 'صعودی' : 'نزولی'} تأیید شد`,
      reason: `رژیمِ روندیِ ${isBull ? 'صعودی' : 'نزولی'} کارا (ER=${reg.efficiencyRatio.toFixed(3)}) + ` +
        `احتمالِ مدل ${p.toFixed(1)}% (بالای آستانهٔ ${P_MIN}%). ` +
        `${!isBull ? 'این «محلِ درستِ استفادهٔ» جریانِ Bear است که در بک‌تست بالاترین اکسپکتنسی را داشت (L34).' : 'جریانِ Bull در رژیمِ صعودیِ کارا فعال شد.'}`,
      direction: dir, entry, tp, sl,
      rr: `TP ${tpM}×ATR / SL ${slM}×ATR (≈ 1:${(tpM / slM).toFixed(2)})`,
      probability: p,
      // S64 — حجمِ پیشنهادی (Kelly رژیم-آگاه):
      sizing: {
        lotMultiplier: lotM,
        label: lotLabel(lotM),
        note: `سطلِ رژیم «${reg.bucket}» (${plan.desc}). طبقِ کشفِ L38، حجمِ بیشتر در ` +
          `سطل‌های باکیفیت‌تر سودِ خالص را ~۸۳٪ بالا برد — این «تخصیصِ سرمایه» است نه اهرمِ خام.`,
        // S67 (L41): لاتِ واقعیِ سرمایه‌محور
        lots,
        riskDollars: Math.round(riskDollars * 100) / 100,
        capital,
        riskPct,
        capitalNote: `با سرمایهٔ ${capital.toLocaleString('en-US')}$ و ریسکِ ${riskPct}% ` +
          `(× ضریبِ کیفیتِ سطل ${lotM} ⇒ ریسکِ مؤثر ${effRiskPct.toFixed(2)}%)، حجمِ پیشنهادی ` +
          `${lots.toFixed(2)} لات است. اگر SL (فاصلهٔ ${slDist.toFixed(2)}$) بخورد، حدودِ ` +
          `${(Math.round(riskDollars * 100) / 100).toLocaleString('en-US')}$ ضرر می‌کنید — دقیقاً ` +
          `همان ریسکی که تعیین کردید. (کشفِ L41: سودِ خالص فقط با مدلِ سرمایه معنا دارد.)`,
      },
      // S65 — TPِ رژیم-آگاه:
      tpPlan: {
        multiplier: tpM,
        note: reg.bucket === 'trend_hi'
          ? `روندِ کارآمد اجازهٔ TPِ دورتر (${tpM}×ATR) می‌دهد؛ حرکت‌ها ادامه‌دارترند (L39).`
          : `TP متناسب با کیفیتِ سطل «${reg.bucket}» تنظیم شد (${tpM}×ATR) تا سودِ خالص بیشینه شود (L39).`,
      },
      // S66 (L40) — SLِ رژیم-آگاه (اهرمِ چهارم؛ تنها اهرمی که سود را بالا و ریسک را پایین برد):
      slPlan: {
        multiplier: slM,
        note: `فاصلهٔ استاپ متناسب با رژیمِ سطل «${reg.bucket}» تنظیم شد (${slM}×ATR). ` +
          `طبقِ کشفِ L40، SLِ رژیم-آگاه سودِ خالص را +۲۱٪ بالا برد و هم‌زمان DrawDown را ~۳۵٪ کم کرد ` +
          `(سود/DD تقریباً دو برابر شد) — این «مدیریتِ ریسکِ پویا» است.`,
      },
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

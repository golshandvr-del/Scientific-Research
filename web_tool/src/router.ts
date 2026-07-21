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
import { computeShortMA, DEFAULT_SHORT_MA } from './short_ma_confluence'
import { computeSqueeze, DEFAULT_SQUEEZE } from './squeeze_breakout'

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

  // --- بخشِ اسکالپ (User Note) — بدونِ TP/SL/حجمِ نمایشی ---
  // در لایهٔ اسکالپِ M5 هیچ عددی (TP/SL/lot) به کاربر نمایش داده نمی‌شود.
  // فقط جهت (BUY/SELL) و سپس پیامِ لحظه‌ایِ خروج. آستانه‌های پنهان اینجا حمل می‌شوند
  // تا موتورِ مدیریت (manageGoldM5Scalp) بتواند لحظه‌ای «سود گرفتیم/اشتباه بود» بگوید.
  scalp?: {
    isScalp: true
    action?: 'BUY' | 'SELL'      // فقط در ENTRY — جهتِ پیشنهادی (بدونِ عدد)
    hiddenTpPip: number          // هدفِ سودِ پنهان (px واحدِ pip؛ به کاربر نمایش داده نمی‌شود)
    hiddenSlPip: number          // حدِ ضررِ پنهان (px واحدِ pip؛ به کاربر نمایش داده نمی‌شود)
    refPrice?: number            // قیمتِ مرجعِ سیگنال (برای محاسبهٔ فاصلهٔ pip در مدیریت)
  }
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
// کاربر از دست برود.
//
// ⚠️ رفعِ باگِ User Note (نکتهٔ اول): مدلِ لاتِ قبلی «مخصوصِ XAUUSD» بود
// (CONTRACT_SIZE = ۱۰۰ ثابت) ولی روی همهٔ دارایی‌ها اعمال می‌شد. برای AUDUSD/EURUSD
// که قیمتشان ~۰.۶۵–۱.۱ است و فاصلهٔ SL بسیار کوچک (به «واحدِ قیمت») است، تقسیم بر
// contract-sizeِ طلا (۱۰۰) لاتِ غول‌آسا (مثلِ ۲۸.۳۸) می‌داد. راه‌حل: هر دارایی
// «مشخصاتِ قراردادِ خودش» را دارد (`AssetSpec`)، و «ارزشِ حرکتِ یک واحدِ قیمت به ازای
// هر لات» از همان مشخصات می‌آید — نه از عددِ ثابتِ طلا.
//
//   دارایی   | ۱ لاتِ استاندارد | ارزشِ حرکتِ ۱.۰ واحدِ قیمت / لات
//   ---------|------------------|--------------------------------
//   XAUUSD   | ۱۰۰ اونس         | ۱۰۰$   (حرکتِ ۱$ طلا)
//   EURUSD   | ۱۰۰٬۰۰۰ یورو     | ۱۰۰٬۰۰۰$ (حرکتِ ۱.۰؛ هر پیپ ۰.۰۰۰۱ = ۱۰$)
//   AUDUSD   | ۱۰۰٬۰۰۰ AUD      | ۱۰۰٬۰۰۰$ (همان)
//   DXY      | شاخص (غیرقابلِ‌معاملهٔ مستقیم) → لات پیشنهاد نمی‌شود
//
// رجوع: results/TPSL_Plan_CapitalEngine_NetProfit_37156.md · engine/capital_engine.py
// ============================================================================

/** مشخصاتِ قراردادِ هر دارایی برای محاسبهٔ درستِ حجمِ لات. */
export interface AssetSpec {
  id: string
  /** ارزشِ دلاریِ حرکتِ «۱.۰ واحدِ قیمت» به ازای هر لاتِ استاندارد. */
  valuePerPricePerLot: number
  /** آیا این دارایی اصلاً قابلِ محاسبهٔ لات است؟ (DXY شاخص است → false) */
  tradableLots: boolean
  /** کمیسیونِ رفت‌وبرگشتِ تقریبی به ازای هر لات ($). */
  commissionPerLot: number
  minLot: number
  maxLot: number
  /** واحدِ نمایشِ لات در UI (فارسی) */
  lotUnitFa: string
}

// نگاشتِ مشخصاتِ قراردادِ استاندارد. XAUUSD همان مدلِ برندهٔ S67 است (بدونِ تغییرِ عددی).
export const ASSET_SPECS: Record<string, AssetSpec> = {
  XAUUSD: { id: 'XAUUSD', valuePerPricePerLot: 100,     tradableLots: true,  commissionPerLot: 7.0, minLot: 0.01, maxLot: 100, lotUnitFa: 'لات (۱۰۰ اونس)' },
  EURUSD: { id: 'EURUSD', valuePerPricePerLot: 100_000, tradableLots: true,  commissionPerLot: 7.0, minLot: 0.01, maxLot: 100, lotUnitFa: 'لات (۱۰۰k)' },
  AUDUSD: { id: 'AUDUSD', valuePerPricePerLot: 100_000, tradableLots: true,  commissionPerLot: 7.0, minLot: 0.01, maxLot: 100, lotUnitFa: 'لات (۱۰۰k)' },
  DXY:    { id: 'DXY',    valuePerPricePerLot: 0,       tradableLots: false, commissionPerLot: 0,   minLot: 0.01, maxLot: 100, lotUnitFa: '—' },
}

export function assetSpec(id?: string): AssetSpec {
  return (id && ASSET_SPECS[id]) || ASSET_SPECS.XAUUSD
}

export const DEFAULT_CAPITAL = 10_000
export const DEFAULT_RISK_PCT = 1.0
const MAX_EFFECTIVE_RISK_PCT = 5.0

/**
 * حجمِ لاتِ واقعی: طوری که اگر SL بخورد، `riskPct% × lotMultiplier` از سرمایه برود.
 * اکنون «مشخصاتِ قراردادِ همان دارایی» را می‌گیرد تا لات برای فارکس هم درست باشد.
 * @param capital سرمایهٔ کاربر ($)
 * @param riskPct درصدِ ریسکِ پایه
 * @param slDist  فاصلهٔ SL به «واحدِ قیمتِ همان دارایی» (|entry − sl|)
 * @param lotMult ضریبِ Kelly رژیم-آگاه (S64) — به‌عنوانِ ضریبِ مقیاسِ ریسک
 * @param spec    مشخصاتِ قراردادِ دارایی (ارزشِ حرکت، کمیسیون، min/max)
 */
export function computeLots(capital: number, riskPct: number, slDist: number, lotMult: number, spec: AssetSpec) {
  const effRiskPct = Math.min(riskPct * lotMult, MAX_EFFECTIVE_RISK_PCT)
  const riskDollars = capital * effRiskPct / 100
  // دارایی‌های غیرقابلِ‌معامله (شاخص مثلِ DXY): لات معنا ندارد.
  if (!spec.tradableLots || spec.valuePerPricePerLot <= 0) {
    return { lots: null as number | null, riskDollars, effRiskPct }
  }
  let lots = spec.minLot
  if (slDist > 0) {
    // ضررِ دلاریِ هر لات اگر SL بخورد = فاصلهٔ SL × ارزشِ حرکتِ همان دارایی + کمیسیون
    const lossPerLotAtSl = slDist * spec.valuePerPricePerLot + spec.commissionPerLot
    lots = riskDollars / lossPerLotAtSl
  }
  lots = Math.min(Math.max(Math.round(lots * 100) / 100, spec.minLot), spec.maxLot)
  return { lots: lots as number | null, riskDollars, effRiskPct }
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
                       riskPct: number = DEFAULT_RISK_PCT,
                       spec: AssetSpec = ASSET_SPECS.XAUUSD,
                       high?: number[],
                       low?: number[]): RouterDecision {
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

  // ========================================================================
  // لایهٔ SHORTِ مستقل (S97–S102 / پاسخِ User Note: «چرا سیگنالِ نزولی نمی‌دهی؟»)
  // ------------------------------------------------------------------------
  // قانونِ شمارهٔ ۱: فقط «سودِ خالصِ بیشتر» مهم است — WR مهم نیست.
  // این لایه فقط برای XAUUSD فعال است (کشف روی همان اعتبارسنجی شده) و *مکملِ*
  // منطقِ ML است: وقتی مدلِ صعودی ساکت است ولی قیمت خطِ میانهٔ سه میانگین
  // [EMA50,EMA100,SMA200] را از بالا رو به پایین قطع می‌کند، به‌جای «علاف‌کردنِ»
  // کاربر، یک سیگنالِ SHORT می‌دهد و اجازه می‌دهد بردها بدوند (خروجِ s118).
  // اعتبار: سهمِ SHORT +34,542$، هر دو نیمهٔ داده مثبت، WF هر ۴ پنجره مثبت،
  //   همبستگیِ روزانه با long +0.16 (مکمل). افزایشی: +88,955$ → +95,645$.
  // جزئیات: results/ShortExitLetWinnersRun_NetProfit_95645.md
  // ========================================================================
  if (spec.id === 'XAUUSD' && reg.activeStream !== 'bull') {
    const sm = computeShortMA(close, DEFAULT_SHORT_MA)
    const pip = 0.1                     // طلا: ۱ pip = ۰.۱ واحدِ قیمت
    const slDist = DEFAULT_SHORT_MA.slPip * pip     // ۷۰pip = ۷.۰$
    const trailDist = DEFAULT_SHORT_MA.trailPip * pip
    const beDist = DEFAULT_SHORT_MA.bePip * pip

    const shortInd: RouterDecision['indicators'] = [
      { name: 'خطِ میانهٔ MA (EMA50/EMA100/SMA200)', value: isFinite(sm.mid) ? sm.mid.toFixed(2) + '$' : '—',
        status: sm.active ? 'ok' : (sm.approaching ? 'warn' : 'neutral') },
      { name: 'چیدمانِ نزولیِ MA (EMA50<EMA100<SMA200)', value: sm.dnStack ? 'بله ✓' : 'خیر',
        status: sm.dnStack ? 'ok' : 'neutral' },
      { name: 'فاصلهٔ قیمت از میانه', value: sm.distPct.toFixed(2) + '%',
        status: sm.distPct < 0 ? 'ok' : 'neutral' },
      ...indicators,
    ]

    if (sm.active) {
      // ---- ورودِ SHORT (ماشهٔ MA-confluence شلیک کرد) ----
      const entry = a.price
      const sl = entry + slDist
      // TP اسمیِ دور (۸۰۰pip) فقط به‌عنوانِ «سقفِ» ایمنی؛ خروجِ واقعی با trailing/max_hold است.
      const tpNominal = entry - DEFAULT_SHORT_MA.tpPip * pip
      const { lots, riskDollars, effRiskPct } = computeLots(capital, riskPct, slDist, 1.0, spec)
      const rd = Math.round(riskDollars * 100) / 100
      const qualNote = sm.dnStack
        ? 'چیدمانِ میانگین‌ها کاملاً نزولی است (EMA50<EMA100<SMA200) — سیگنالِ باکیفیت.'
        : 'هشدار: چیدمانِ میانگین‌ها هنوز کاملاً نزولی نیست؛ حجم را محافظه‌کارانه بگیرید.'
      return {
        state: 'ENTRY', regime: reg,
        headline: 'ورود فروش (SHORT) — قیمت خطِ میانهٔ میانگین‌ها را از بالا شکست',
        reason: `${sm.reason} این همان الگویی است که «خطِ چارت، خطوطِ MA را از بالا قطع می‌کند» — ` +
          `شتابِ نزولیِ کوتاه‌مدت. ${qualNote} طبقِ کشفِ MFE (s117)، بردهای بزرگِ نزولی را ` +
          `زودهنگام قطع نمی‌کنیم: پس از ۶ پیپ سود، حد ضرر به سربه‌سر می‌آید و با فاصلهٔ ۶ پیپ ` +
          `سود را دنبال می‌کند، اما اجازه می‌دهیم معامله تا ۴۸ کندل بدود (بگذار بردها بدوند). ` +
          `طبقِ قانونِ شمارهٔ ۱، هدف سودِ خالصِ بیشتر است نه وین‌ریتِ بالا (این استراتژی WR پایین ` +
          `اما سودِ خالصِ بالا دارد — سهمِ +۳۴٬۵۴۲$).`,
        direction: 'SHORT', entry, tp: tpNominal, sl,
        rr: `SL ثابت ۷۰pip (${slDist.toFixed(2)}$) + خروجِ پویا: BE=۶pip، trailing=۶pip، حداکثر ۴۸ کندل (TP سقفِ ۸۰۰pip)`,
        probability: sm.dnStack ? 62 : 55,
        sizing: {
          lotMultiplier: 1.0,
          label: sm.dnStack ? 'کیفیتِ بالا (چیدمانِ نزولیِ کامل)' : 'کیفیتِ متوسط',
          note: `استراتژیِ SHORT-MA-Confluence (خروجِ بازطراحی‌شدهٔ s118). ورودِ open کندلِ بعد، اسپرد ۴pip لحاظ شده. ` +
            `همبستگیِ روزانه با جریانِ long = +0.16 ⇒ این معامله مکملِ سبدِ long است و سودِ خالصِ ` +
            `کل را افزایش می‌دهد (رکورد: +۸۸٬۹۵۵$ → +۹۵٬۶۴۵$).`,
          lots: lots ?? undefined,
          riskDollars: rd,
          capital, riskPct,
          capitalNote: `با سرمایهٔ ${capital.toLocaleString('en-US')}$ و ریسکِ ${riskPct}% ` +
            `(ریسکِ مؤثر ${effRiskPct.toFixed(2)}%)، حجمِ پیشنهادی ${lots?.toFixed(2) ?? '—'} ${spec.lotUnitFa}. ` +
            `اگر SL (فاصلهٔ ${slDist.toFixed(2)}$) بخورد، حدودِ ${rd.toLocaleString('en-US')}$ ضرر می‌کنید.`,
        },
        tpPlan: {
          multiplier: DEFAULT_SHORT_MA.tpPip,
          note: `این استراتژی TPِ ثابت ندارد؛ عددِ ۸۰۰pip فقط «سقفِ ایمنی» است. خروجِ اصلی ` +
            `با trailing و max_hold انجام می‌شود: سود را با فاصلهٔ ۶pip دنبال کنید و اجازه دهید معامله ` +
            `تا ۴۸ کندل بدود. طبقِ کشفِ MFE (s117) «بگذار بردها بدوند» سودِ خالص را بیشینه می‌کند.`,
        },
        slPlan: {
          multiplier: DEFAULT_SHORT_MA.slPip,
          note: `SL ثابت ۷۰pip (${slDist.toFixed(2)}$). پس از رسیدن به ۶pip سود، به سربه‌سر منتقل کنید؛ ` +
            `سپس با trailing ۶pip (${trailDist.toFixed(2)}$) سود را دنبال کنید و بگذارید حرکتِ نزولیِ بزرگ ` +
            `ادامه یابد (تا ۴۸ کندل). این «اجازه‌دادن به بردها» کلیدِ رکوردِ +۹۵٬۶۴۵$ است (s118).`,
        },
        indicators: shortInd,
      }
    }

    if (sm.approaching && reg.activeStream !== 'bear') {
      // ---- نزدیک‌شدن به سیگنالِ SHORT ----
      return {
        state: 'APPROACHING', regime: reg,
        headline: 'نزدیک‌شدن به سیگنالِ فروش (SHORT) — منتظرِ عبور از میانه',
        reason: sm.reason,
        confirmations: [
          { label: 'قیمت از خطِ میانهٔ MA رو به پایین عبور کند', met: false,
            detail: `اکنون ${sm.distPct.toFixed(2)}% بالای میانه است و رو به کاهش.` },
          { label: 'چیدمانِ نزولیِ میانگین‌ها (EMA50<EMA100<SMA200)', met: sm.dnStack,
            detail: sm.dnStack ? 'برقرار است ✓' : 'هنوز کامل نیست — برای کیفیتِ بالاتر منتظر بمانید.' },
        ],
        indicators: shortInd,
      }
    }
  }

  // ========================================================================
  // لایهٔ LONGِ مستقلِ Squeeze→Breakout (کشفِ S132 — رکوردِ +$121,694)
  // ------------------------------------------------------------------------
  // قانونِ شمارهٔ ۱: فقط «سودِ خالصِ بیشتر» مهم است — WR مهم نیست.
  // این لایه فقط برای XAUUSD (M15) و *مکملِ* منطقِ ML است: وقتی مدلِ اصلی
  // هنوز ENTRY نداده اما بازار پس از یک دورهٔ فشردگیِ نوسان (پهنای باندِ بولینگر
  // در کفِ محلی) سقفِ اخیر را رو به بالا می‌شکند و روند صعودی است، یک سیگنالِ
  // LONG می‌دهد و اجازه می‌دهد بردها بدوند (TP دورِ ۳۰۰pip).
  // اعتبار: سودِ مستقل +$20,435، هر دو نیمهٔ داده مثبت، WF هر ۴ پنجره مثبت،
  //   همبستگیِ روزانه با پرتفویِ پایه +0.28 (ناهمبسته). افزایشی: +101,259$ → +121,694$.
  // جزئیات: results/SqueezeBreakout_NetProfit_121694.md
  // ========================================================================
  if (spec.id === 'XAUUSD' && high && high.length === close.length) {
    const sq = computeSqueeze(close, high, DEFAULT_SQUEEZE, low)
    const pip = 0.1                              // طلا: ۱ pip = ۰.۱ واحدِ قیمت
    const slDist = DEFAULT_SQUEEZE.slPip * pip   // ۹۰pip = ۹.۰$
    const tpDist = DEFAULT_SQUEEZE.tpPip * pip   // ۳۰۰pip = ۳۰.۰$

    const sqInd: RouterDecision['indicators'] = [
      { name: 'فشردگیِ بولینگر (صدکِ پهنای باند)', value: isFinite(sq.bwPct) ? (sq.bwPct * 100).toFixed(0) + '%' : '—',
        status: sq.squeezed ? 'ok' : 'neutral' },
      { name: 'سقفِ شکستِ اخیر', value: isFinite(sq.priorHigh) ? sq.priorHigh.toFixed(2) + '$' : '—',
        status: sq.active ? 'ok' : 'neutral' },
      { name: 'گیتِ روندِ صعودی (EMA50>EMA200)', value: sq.trendUp ? 'بله ✓' : 'خیر',
        status: sq.trendUp ? 'ok' : 'neutral' },
      { name: 'قدرتِ شکست (S136، آستانه ≥ ۰.۳۰)',
        value: isFinite(sq.brkStrength) ? sq.brkStrength.toFixed(2) : '—',
        status: sq.active ? 'ok' : (sq.strongBreak ? 'neutral' : 'warn') },
      ...indicators,
    ]

    if (sq.active) {
      // ---- ورودِ LONG (ماشهٔ Squeeze→Breakout شلیک کرد) ----
      const entry = a.price
      const sl = entry - slDist
      const tp = entry + tpDist
      const { lots, riskDollars, effRiskPct } = computeLots(capital, riskPct, slDist, 1.0, spec)
      const rd = Math.round(riskDollars * 100) / 100
      return {
        state: 'ENTRY', regime: reg,
        headline: 'ورود خرید (LONG) — انفجارِ صعودی پس از فشردگیِ نوسان',
        reason: `${sq.reason} این «فنرِ فشرده» است: بازار مدتی کم‌نوسان و متراکم بود و حالا با ` +
          `شکستِ صعودی، انفجارِ نوسان آغاز شده. طبقِ قانونِ شمارهٔ ۱ هدف سودِ خالصِ بیشتر است، نه ` +
          `وین‌ریت: TP دور (۳۰۰pip) نگه داشته می‌شود تا بردها بدوند (WR ~۴۰٪ اما سودِ خالصِ بالا؛ ` +
          `سهمِ مستقل +۲۰٬۴۳۵$، افزایشی به رکورد +۱۲۱٬۶۹۴$).`,
        direction: 'LONG', entry, tp, sl,
        rr: `SL ثابت ۹۰pip (${slDist.toFixed(2)}$) / TP ۳۰۰pip (${tpDist.toFixed(2)}$) — نسبتِ R:R ≈ ۱:۳.۳ (بگذار بردها بدوند)`,
        probability: 58,
        sizing: {
          lotMultiplier: 1.0,
          label: 'Squeeze→Breakout (فشردگی ⇒ انفجارِ صعودی)',
          note: `استراتژیِ S132 (کشفِ نو). ورودِ open کندلِ بعد، اسپرد ۴pip لحاظ شده. ` +
            `همبستگیِ روزانه با پرتفویِ پایه = +0.28 ⇒ جریانِ ناهمبسته که سودِ خالصِ کل را بالا می‌برد.`,
          lots: lots ?? undefined,
          riskDollars: rd,
          capital, riskPct,
          capitalNote: `با سرمایهٔ ${capital.toLocaleString('en-US')}$ و ریسکِ ${riskPct}% ` +
            `(ریسکِ مؤثر ${effRiskPct.toFixed(2)}%)، حجمِ پیشنهادی ${lots?.toFixed(2) ?? '—'} ${spec.lotUnitFa}. ` +
            `اگر SL (فاصلهٔ ${slDist.toFixed(2)}$) بخورد، حدودِ ${rd.toLocaleString('en-US')}$ ضرر می‌کنید.`,
        },
        tpPlan: {
          multiplier: DEFAULT_SQUEEZE.tpPip,
          note: `TP دورِ ۳۰۰pip. انفجارهای پس از فشردگی معمولاً بزرگ‌اند؛ TP دور اجازه می‌دهد ` +
            `حرکتِ صعودی کامل استخراج شود. تا ۹۶ کندل (۲۴ ساعت) نگه دارید یا تا برخورد به TP/SL.`,
        },
        slPlan: {
          multiplier: DEFAULT_SQUEEZE.slPip,
          note: `SL ثابت ۹۰pip (${slDist.toFixed(2)}$) زیرِ نقطهٔ شکست. اگر انفجار کاذب بود (شکستِ ناموفق)، ` +
            `این SL ضررِ کوچک را محدود می‌کند؛ اما بردهای واقعی به‌مراتب بزرگ‌ترند (R:R ۱:۳.۳).`,
        },
        indicators: sqInd,
      }
    }

    if (sq.approaching && reg.activeStream !== 'bull') {
      // ---- نزدیک‌شدن به سیگنالِ LONGِ Squeeze ----
      return {
        state: 'APPROACHING', regime: reg,
        headline: 'نزدیک‌شدن به سیگنالِ خرید (LONG) — فنرِ فشرده، منتظرِ شکست',
        reason: sq.reason,
        confirmations: [
          { label: `قیمت سقفِ ${DEFAULT_SQUEEZE.breakoutLookback} کندلِ اخیر (${isFinite(sq.priorHigh) ? sq.priorHigh.toFixed(2) + '$' : '—'}) را رو به بالا بشکند`,
            met: false, detail: 'شکستِ صعودی هنوز تأیید نشده — منتظرِ بسته‌شدنِ قیمت بالای سقف بمانید.' },
          { label: 'گیتِ روندِ صعودی (EMA50>EMA200)', met: sq.trendUp,
            detail: sq.trendUp ? 'برقرار است ✓' : 'هنوز برقرار نیست.' },
        ],
        indicators: sqInd,
      }
    }
  }

  // --------- حالتِ ۱: رنج / بی‌روند → خنثی (کلیدِ سودِ خالص طبقِ L36) ---------
  // رفعِ باگ (User Note): رژیمِ «رنج» اینجا از سرِ ساختارِ EMA50/200 تعیین می‌شود،
  // نه صرفاً از ER. متنِ قبلی همیشه می‌گفت «ER زیرِ آستانهٔ ۰.۱۵»، حتی وقتی ER بالای
  // آستانه بود (مثلاً ۰.۲۰۴) — یک تناقضِ آشکار با پنلِ شاخص‌ها که همان ER را «(روندی)»
  // نشان می‌داد. اکنون دلیل بر اساسِ علتِ واقعیِ خنثی‌ماندن ساخته می‌شود و متنِ ER فقط
  // وقتی «زیرِ آستانه» گفته می‌شود که واقعاً زیرِ آستانه باشد.
  if (reg.activeStream === 'none' || reg.regime === 'range') {
    // چه‌چیز باعثِ رنج‌بودن شد؟ ساختارِ EMA بی‌روند است (نه صعودی نه نزولیِ منظم).
    const erIsTrendy = reg.efficiencyRatio >= ER_TREND_THR
    const erPhrase = erIsTrendy
      ? `کاراییِ روند ER=${reg.efficiencyRatio.toFixed(3)} هرچند بالای آستانهٔ ${ER_TREND_THR} است، ` +
        `اما ساختارِ میانگین‌ها (EMA50/200) هنوز جهتِ روشنی نمی‌دهد`
      : `کاراییِ روند ER=${reg.efficiencyRatio.toFixed(3)} زیرِ آستانهٔ ${ER_TREND_THR} است و ساختارِ ` +
        `میانگین‌ها (EMA50/200) نیز جهتِ روشنی ندارد`
    return {
      state: 'NEUTRAL', regime: reg,
      headline: 'خنثی — وارد نمی‌شوم',
      reason: `بازار در رژیمِ رنج/بی‌روند است (${erPhrase}). ` +
        `طبقِ کشفِ L36، فعال‌شدن در چنین رژیمی سودِ خالص را از بین می‌برد؛ پس منتظرِ ` +
        `هم‌راستاشدنِ روند (تثبیتِ جهتِ EMA به‌همراهِ کاراییِ کافی) می‌مانم.`,
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
    // --- S67 (L41): حجمِ لاتِ واقعیِ سرمایه‌محور (اکنون per-asset — رفعِ باگِ لات) ---
    const slDist = Math.abs(entry - sl)
    const { lots, riskDollars, effRiskPct } = computeLots(capital, riskPct, slDist, lotM, spec)
    const rd = Math.round(riskDollars * 100) / 100
    // متنِ توضیحِ لات؛ برای دارایی‌های غیرقابلِ‌معامله (DXY) لات نمایش داده نمی‌شود.
    const capitalNote = (lots == null)
      ? `«${spec.id}» یک شاخص است و مستقیماً با لات معامله نمی‌شود؛ پس حجمِ لات ` +
        `پیشنهاد نمی‌دهیم. با سرمایهٔ ${capital.toLocaleString('en-US')}$ و ریسکِ ${riskPct}% ` +
        `(ریسکِ مؤثر ${effRiskPct.toFixed(2)}%)، ریسکِ دلاریِ هدف ${rd.toLocaleString('en-US')}$ است — ` +
        `این دارایی را برای «جهتِ کلانِ دلار» به‌کار ببرید، نه برای اجرای مستقیمِ معامله.`
      : `با سرمایهٔ ${capital.toLocaleString('en-US')}$ و ریسکِ ${riskPct}% ` +
        `(× ضریبِ کیفیتِ سطل ${lotM} ⇒ ریسکِ مؤثر ${effRiskPct.toFixed(2)}%)، حجمِ پیشنهادی ` +
        `${lots.toFixed(2)} ${spec.lotUnitFa} است. اگر SL (فاصلهٔ ${slDist.toFixed(spec.id === 'XAUUSD' ? 2 : 5)} واحدِ قیمت) بخورد، حدودِ ` +
        `${rd.toLocaleString('en-US')}$ ضرر می‌کنید — دقیقاً همان ریسکی که تعیین کردید. ` +
        `(رفعِ باگ: مدلِ لات اکنون مخصوصِ «${spec.id}» است، نه ثابتِ طلا؛ کشفِ L41: سودِ خالص فقط با مدلِ سرمایه معنا دارد.)`
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
        // S67 (L41): لاتِ واقعیِ سرمایه‌محور (per-asset — رفعِ باگِ لات)
        lots: lots ?? undefined,
        riskDollars: rd,
        capital,
        riskPct,
        capitalNote,
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

// ============================================================================
// regime/radar.ts — رادارِ رژیم (تشخیص‌گرِ سایه‌ای)  [webplan P3.5 · ایدهٔ #۴]
// ----------------------------------------------------------------------------
// ورودی: IndicatorSnapshot@v1  ⇒  خروجی: RegimeInfo@v1
//
// روشِ علمیِ خودکالیبره (نه اعدادِ رندِ ساده — اشتباهِ رایجِ #۷؛ نه آستانهٔ یکسان برای
// همهٔ TF — اشتباهِ رایجِ #۶):
//   ● اندازه‌گیریِ تجربی نشان داد ATR% و شیبِ EMA شدیداً TF-محورند (M5 مِدینِ ATR%≈۰.۰۷٪،
//     اما H4≈۰.۵٪ — ۷ برابر). پس آستانهٔ مطلقِ ثابت غلط است. راه‌حل: آستانه را از
//     **صدکِ زندهٔ همان پنجرهٔ کندل** می‌سازیم ⇒ آستانه *شناور* می‌شود (قانونِ «هیچ‌چیز ثابت نیست»).
//   ● ADX ذاتاً نرمال‌شده است (Wilder 1978): مِدینش در همهٔ TFها ~۲۳–۲۵ ماند، پس آستانهٔ
//     مطلقِ آن (۲۲.۵/۱۸.۵، غیر-رند) معتبر و TF-مستقل است.
//
// ⚠️ سایه‌ای: این تابع فقط تشخیص می‌دهد. enabledKinds صرفاً *پیشنهاد* است؛ هیچ لایه‌ای
//    را خاموش نمی‌کند تا وقتی فازِ بعد (Runtime/Council) صراحتاً آن را مصرف کند.
// ============================================================================

import type { Candle } from '../indicators'
import { atr as atrSeries, ema as emaSeries, adx as adxCalc, bollinger } from '../indicators'
import { buildSnapshot } from '../indicators/registry'
import type { IndicatorSnapshot } from '../indicators/contracts'
import {
  REGIME_INFO_VERSION,
  type Regime,
  type LayerKind,
  type RegimeInfo,
} from './contracts'

// --- آستانه‌های مطلقِ TF-مستقل (فقط ADX، چون نرمال‌شده است) ---
const ADX_TREND = 22.5   // بالای این ⇒ روندِ معنادار
const ADX_RANGE = 18.5   // زیرِ این ⇒ بی‌روند/رنج

// --- صدک‌های خودکالیبره (آستانهٔ شناور بر پایهٔ همان پنجره) ---
const ATR_Q_QUIET = 0.35      // ATR% زیرِ صدکِ ۳۵ پنجره ⇒ آرام
const ATR_Q_VOLATILE = 0.85   // ATR% بالای صدکِ ۸۵ پنجره ⇒ نوسانِ بالا
const SLOPE_Q_FLAT = 0.45     // |شیب| زیرِ صدکِ ۴۵ پنجره ⇒ افقی
const BB_Q_SQUEEZE = 0.25     // پهنای بولینگر زیرِ صدکِ ۲۵ ⇒ فشردگی

function percentileRank(sortedAsc: number[], value: number): number {
  // نسبتِ عناصرِ ≤ value (0..1)
  if (sortedAsc.length === 0 || !Number.isFinite(value)) return NaN
  let lo = 0, hi = sortedAsc.length
  while (lo < hi) { const mid = (lo + hi) >> 1; if (sortedAsc[mid] <= value) lo = mid + 1; else hi = mid }
  return lo / sortedAsc.length
}

function sortedFinite(arr: number[]): number[] {
  return arr.filter(Number.isFinite).sort((a, b) => a - b)
}

/**
 * تشخیصِ رژیم از کندل‌ها (نسخهٔ خودکالیبره — به کلِ سری برای صدک‌گیری نیاز دارد).
 * از snapshot برای مقادیرِ آخر استفاده می‌کند اما توزیعِ صدک را از سری‌های خام می‌سازد.
 */
export function classifyRegime(snap: IndicatorSnapshot, candles: Candle[]): RegimeInfo {
  const n = candles.length
  const price = snap.price
  const closes = candles.map(k => k.close)

  // --- سری‌های خام برای صدک‌گیریِ خودکالیبره ---
  const atrArr = atrSeries(candles, 14)
  const atrPctArr = atrArr.map((a, i) => (closes[i] > 0 ? a / closes[i] : NaN))
  const atrPctSorted = sortedFinite(atrPctArr)
  const atrPctNow = atrPctArr[n - 1]
  const atrPctRank = percentileRank(atrPctSorted, atrPctNow)

  const ema50 = emaSeries(closes, 50)
  const LB = 8
  const slopeArr: number[] = new Array(ema50.length).fill(NaN)
  for (let i = LB; i < ema50.length; i++) {
    const a = ema50[i - LB], b = ema50[i]
    if (Number.isFinite(a) && Number.isFinite(b) && a !== 0) slopeArr[i] = (b - a) / a / LB
  }
  const absSlopeSorted = sortedFinite(slopeArr.map(Math.abs))
  const slopeNow = slopeArr[n - 1]
  const slopeRank = percentileRank(absSlopeSorted, Math.abs(slopeNow))

  const bb = bollinger(closes, 20, 2.0)
  const bbWidthArr = bb.upper.map((u, i) => (bb.mid[i] > 0 ? (u - bb.lower[i]) / bb.mid[i] : NaN))
  const bbWidthSorted = sortedFinite(bbWidthArr)
  const bbWidthNow = bbWidthArr[n - 1]
  const bbRank = percentileRank(bbWidthSorted, bbWidthNow)

  const adx = snap.adx
  const ema200 = snap.ema200
  const aboveLong = Number.isFinite(ema200) ? price > ema200 : (Number.isFinite(slopeNow) ? slopeNow > 0 : true)

  // --- شرط‌ها (خودکالیبره) ---
  const trending = Number.isFinite(adx) && adx >= ADX_TREND
  const ranging = Number.isFinite(adx) && adx <= ADX_RANGE
  const veryVolatile = Number.isFinite(atrPctRank) && atrPctRank >= ATR_Q_VOLATILE
  const veryQuiet = Number.isFinite(atrPctRank) && atrPctRank <= ATR_Q_QUIET
  const flat = Number.isFinite(slopeRank) && slopeRank < SLOPE_Q_FLAT
  const squeeze = Number.isFinite(bbRank) && bbRank < BB_Q_SQUEEZE

  let regime: Regime
  let note: string
  let strength: number

  if (trending && !flat) {
    // روندِ معنادار (ADX بالا + شیبِ EMA در نیمهٔ بالای توزیعِ خودش)
    if (aboveLong && slopeNow > 0) {
      regime = 'TREND_UP'
      note = `روندِ صعودی: ADX ${fmt(adx)} ≥ ${ADX_TREND}، شیبِ EMA50 در صدکِ ${(slopeRank * 100).toFixed(0)}، قیمت بالای EMA200.`
    } else if (!aboveLong && slopeNow < 0) {
      regime = 'TREND_DOWN'
      note = `روندِ نزولی: ADX ${fmt(adx)} ≥ ${ADX_TREND}، شیبِ EMA50 در صدکِ ${(slopeRank * 100).toFixed(0)}، قیمت زیرِ EMA200.`
    } else {
      regime = 'VOLATILE'
      note = `ADX قوی (${fmt(adx)}) اما جهتِ شیب و EMA200 ناسازگار؛ روندِ مبهم.`
    }
    strength = (regime === 'VOLATILE')
      ? 0.4
      : clamp01(0.45 + (adx - ADX_TREND) / 40 + (slopeRank - 0.5) * 0.3)
  } else if (veryVolatile) {
    // نوسانِ بالا (ATR% در صدکِ بالای پنجره) بدونِ روندِ پایدار
    regime = 'VOLATILE'
    strength = clamp01(0.4 + (atrPctRank - ATR_Q_VOLATILE) / (1 - ATR_Q_VOLATILE) * 0.5)
    note = `نوسانِ بالا: ATR% در صدکِ ${(atrPctRank * 100).toFixed(0)} پنجره (${fmt2(atrPctNow * 100)}٪ قیمت). بازارِ پرآشوب.`
  } else if (veryQuiet || squeeze) {
    // آرام یا فشرده (کم‌دامنه)
    regime = 'QUIET'
    const q = Number.isFinite(atrPctRank) ? atrPctRank : bbRank
    strength = clamp01(0.5 + (ATR_Q_QUIET - Math.min(q, ATR_Q_QUIET)) / ATR_Q_QUIET * 0.4)
    note = `بازارِ آرام: ATR% صدکِ ${(atrPctRank * 100).toFixed(0)}، پهنای بولینگر صدکِ ${(bbRank * 100).toFixed(0)}. دامنهٔ کم${squeeze ? ' (فشردگی)' : ''}.`
  } else {
    // پیش‌فرض: رنج
    regime = 'RANGE'
    strength = clamp01(0.4 + (ranging ? 0.2 : 0) + (flat ? 0.15 : 0))
    note = `رنج/بی‌روند: ADX ${fmt(adx)}، شیبِ EMA50 ${flat ? 'افقی (زیرِ صدکِ میانه)' : 'ملایم'}. بازگشت‌به‌میانگین محتمل.`
  }

  return {
    v: REGIME_INFO_VERSION,
    regime, strength, note,
    enabledKinds: enabledKindsFor(regime),
    adx: round2(adx),
    atrPct: round4(atrPctNow),
    emaSlopePct: round4(Number.isFinite(slopeNow) ? slopeNow * 100 : NaN),
    bbWidthPct: round4(Number.isFinite(bbWidthNow) ? bbWidthNow * 100 : NaN),
  }
}

/**
 * نگاشتِ رژیم ⇒ انواعِ لایهٔ مجاز (پیاده‌سازیِ «قانونِ شاید هیچ‌چیز ثابت نیست»).
 * neutral همیشه مجاز است (لایه‌های مستقل از رژیم).
 */
export function enabledKindsFor(regime: Regime): LayerKind[] {
  switch (regime) {
    case 'TREND_UP':
    case 'TREND_DOWN':
      return ['trend', 'breakout', 'neutral']
    case 'RANGE':
      return ['fade', 'neutral']
    case 'VOLATILE':
      return ['breakout', 'neutral']
    case 'QUIET':
      return ['fade', 'neutral']
  }
}

/** میان‌بُر: از کندل‌ها مستقیماً رژیم را بده. */
export function detectRegime(asset: string, tf: string, candles: Candle[]): RegimeInfo {
  const snap = buildSnapshot(asset, tf, candles)
  return classifyRegime(snap, candles)
}

// --- کمکی‌ها ---
function clamp01(x: number): number { return Math.max(0, Math.min(1, Number.isFinite(x) ? x : 0)) }
function round2(x: number): number { return Number.isFinite(x) ? Math.round(x * 100) / 100 : NaN }
function round4(x: number): number { return Number.isFinite(x) ? Math.round(x * 10000) / 10000 : NaN }
function fmt(x: number): string { return Number.isFinite(x) ? x.toFixed(1) : '—' }
function fmt2(x: number): string { return Number.isFinite(x) ? x.toFixed(2) : '—' }

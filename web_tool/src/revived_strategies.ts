// ============================================================================
// revived_strategies.ts — لایه‌های احیاشدهٔ RQS+ که ماژولِ مستقلِ اختصاصی نداشتند
// ----------------------------------------------------------------------------
// این فایل ۶ لایهٔ احیاشدهٔ ACCEPTED (RQS+ ≥ 80) را پیاده می‌کند که پیش‌تر فقط در
// اسکریپت‌های پایتونِ /strategies بازتولید شده بودند و ماژولِ TypeScriptِ زندهٔ سایت
// نداشتند:
//
//   S321 — MA-Ribbon (GMMA/Alligator) pullback، دوطرفه           XAUUSD M30      (RQS 88.2)
//   S322 — Ichimoku Kumo breakout-pullback، LONG                  XAUUSD M15      (RQS 86.2)
//   S323 — S/R Pullback + پنجرهٔ طلایی، LONG                       XAUUSD M15/M30/H1 (RQS 88)
//   S324 — Liquidity-Sweep Reversal (fade)                        XAUUSD M15(L)/M30(S) (RQS 93.2)
//   S328 — RSI-21 cross-back Fade، SHORT                          XAUUSD M5/H1    (RQS 94.2/93.9)
//   S330 — Session-ORB Fade (آسیا) + فیلترِ رژیمِ نوسان            XAUUSD M5       (RQS 89.7)
//
// همهٔ پارامترها از فایل‌های نتیجهٔ ACCEPTED گرفته شده‌اند و **غیر-رند/واقعی** هستند
// (اشتباه رایج #۷). هر لایه پارامترهای مخصوصِ TFِ خودش را دارد (اشتباه رایج #۶).
// هیچ look-ahead bias نیست — همهٔ اندیکاتورها فقط از دادهٔ گذشته/جاری می‌خوانند.
//
// خروجیِ استاندارد: تابعِ decide* برای هر لایه یک RouterDecision برمی‌گرداند تا
// strategy_registry.ts آن را به کارتِ مربوطه بدهد (معماریِ ماژولار/توسعه‌پذیر).
// ============================================================================

import { ema, sma, rsi, atr, adx, bollinger, type Candle } from './indicators'
import { assetSpec, computeLots, type RouterDecision, type RegimeInfo, type RouterState } from './router'
import type { AnalysisResult } from './signal'

// ---------------------------------------------------------------------------
// کمکی: ساختِ آرایهٔ Candle از سری‌های OHLC (+زمانِ اختیاری)
// ---------------------------------------------------------------------------
export function toCandles(open: number[], high: number[], low: number[], close: number[], times?: number[]): Candle[] {
  const n = close.length
  const out: Candle[] = new Array(n)
  for (let i = 0; i < n; i++) {
    out[i] = { time: times?.[i] ?? i, open: open[i], high: high[i], low: low[i], close: close[i], volume: 0 }
  }
  return out
}

// pip طلا = ۰.۱$ ⇒ pip قیمت. برای طلا pipSize=0.1 (۱ pip = ۱۰ point). این‌جا فاصلهٔ
// SL/TP بر حسبِ pip را به واحدِ قیمت (دلار) تبدیل می‌کنیم: priceDist = pip × 0.1.
const GOLD_PIP = 0.1

// سیگنالِ خامِ یک لایه پیش از تبدیل به RouterDecision
export interface RawSignal {
  active: boolean               // ماشهٔ ورود همین کندل فعال است؟
  approaching: boolean          // نزدیکِ فعال‌شدن (تأیید لازم دارد)؟
  direction: 'LONG' | 'SHORT'
  slDist: number                // فاصلهٔ SL بر حسبِ واحدِ قیمت (دلار)
  tpDist: number                // فاصلهٔ TP بر حسبِ واحدِ قیمت (دلار)
  maxHoldBars: number
  reason: string                // دلیلِ فارسیِ وضعیت
  approachReason?: string       // اگر approaching: چه تأییدی لازم است
  indicators: RouterDecision['indicators']
}

// ---------------------------------------------------------------------------
// آداپتر مشترک: RawSignal → RouterDecision  (منطقِ ورود/حجم/مدیریت یکسان برای همه)
// ---------------------------------------------------------------------------
export interface DecideMeta {
  code: string                  // S321..
  name: string                  // نامِ فارسی
  kind: RouterDecision['sourceLayer'] extends infer T ? (T extends { kind: infer K } ? K : never) : never
  manageStyle: 'let-run-trail' | 'structural-trail' | 'fixed-tp-sl' | 'regime-atr-trail'
  beTriggerR?: number
  manageNote: string
  filters: string[]
}

export function rawToDecision(
  raw: RawSignal, meta: DecideMeta, assetId: string, price: number,
  reg: RegimeInfo, capital: number, riskPct: number,
): RouterDecision {
  const spec = assetSpec(assetId.startsWith('EUR') ? 'EURUSD' : 'XAUUSD')

  const sourceLayer: RouterDecision['sourceLayer'] = {
    code: meta.code, name: meta.name, kind: meta.kind as any, filters: meta.filters,
    manage: {
      style: meta.manageStyle,
      beTriggerR: meta.beTriggerR,
      maxHoldBars: raw.maxHoldBars,
      note: meta.manageNote,
    },
  }

  if (raw.active) {
    const entry = price
    const sl = raw.direction === 'LONG' ? entry - raw.slDist : entry + raw.slDist
    const tp = raw.direction === 'LONG' ? entry + raw.tpDist : entry - raw.tpDist
    const { lots, riskDollars } = computeLots(capital, riskPct, raw.slDist, 1.0, spec)
    const rd = lots != null ? Math.round(riskDollars * 100) / 100 : undefined
    const rrNum = raw.slDist > 0 ? raw.tpDist / raw.slDist : 0
    return {
      state: 'ENTRY', regime: reg,
      headline: raw.direction === 'LONG'
        ? `ورود به معاملهٔ خرید (LONG) — ${meta.name}`
        : `ورود به معاملهٔ فروش (SHORT) — ${meta.name}`,
      reason: raw.reason,
      sourceLayer,
      direction: raw.direction,
      entry, tp, sl,
      rr: `1:${rrNum.toFixed(2)}`,
      probability: undefined,
      sizing: lots != null ? {
        lotMultiplier: 1.0, label: 'واحدِ پایه',
        note: `حجمِ سرمایه‌محور بر پایهٔ ریسکِ ${riskPct}% و فاصلهٔ SL`,
        lots, riskDollars: rd, capital, riskPct,
        capitalNote: `SL≈${raw.slDist.toFixed(2)}$ ⇒ ریسک ${rd}$`,
      } : undefined,
      indicators: raw.indicators,
    }
  }

  if (raw.approaching) {
    return {
      state: 'APPROACHING', regime: reg,
      headline: `احتمالِ نزدیک‌شدن به سیگنال — ${meta.name}`,
      reason: raw.reason,
      sourceLayer,
      confirmations: raw.approachReason
        ? [{ label: raw.approachReason, met: false, detail: raw.approachReason }]
        : undefined,
      indicators: raw.indicators,
    }
  }

  return {
    state: 'NEUTRAL', regime: reg,
    headline: `خنثی — ${meta.name}`,
    reason: raw.reason,
    indicators: raw.indicators,
  }
}

// یک RegimeInfo سبک از روی سری‌ها (برای لایه‌هایی که رژیمِ اختصاصی ندارند)
function lightRegime(close: number[], adxVal: number, trendy: boolean, bucket: string): RegimeInfo {
  return {
    regime: trendy ? 'trend_up' : 'range',
    efficiencyRatio: 0, trendy,
    adx: isFinite(adxVal) ? adxVal : 0,
    activeStream: trendy ? 'bull' : 'none',
    bucket,
  }
}

const nz = (v: number) => (Number.isFinite(v) ? v : 0)
const last = <T,>(a: T[]) => a[a.length - 1]

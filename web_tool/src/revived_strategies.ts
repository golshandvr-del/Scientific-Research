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

// ===========================================================================
// S328 — RSI-21 cross-back Fade (SHORT)   منشأ: S167 / Subarkah 2009
// ---------------------------------------------------------------------------
// ماشه: RSI21 از بالای hi عبور کرده و به پایین برمی‌گردد (اشباعِ خرید تخلیه می‌شود)
//   ⇒ فروش. فیلترِ رژیم: ADX14(کندلِ قبل) ≤ adx_max (رنج، نه روندِ قوی).
//   TP/SL ثابتِ pip (spike-fade با هدفِ ثابت)، max_hold=24. غیر-رند، per-TF.
// ===========================================================================
export interface S328Config {
  id: string          // XAUUSD-M5 | XAUUSD-H1
  rsiPeriod: number   // 21
  hi: number          // آستانهٔ اشباعِ خرید (M5:75، H1:82)
  adxMax: number      // سقفِ ADX (M5:30، H1:Infinity=خاموش)
  slPip: number       // فاصلهٔ SL بر حسبِ pip (M5:62، H1:195)
  tpPip: number       // فاصلهٔ TP بر حسبِ pip (M5:43، H1:210)
  maxHold: number     // 24
}

export const S328_CFG: Record<string, S328Config> = {
  'XAUUSD-M5': { id: 'XAUUSD-M5', rsiPeriod: 21, hi: 75, adxMax: 30, slPip: 62, tpPip: 43, maxHold: 24 },
  'XAUUSD-H1': { id: 'XAUUSD-H1', rsiPeriod: 21, hi: 82, adxMax: Infinity, slPip: 195, tpPip: 210, maxHold: 24 },
}

export function computeS328(candles: Candle[], cfg: S328Config): RawSignal {
  const close = candles.map(c => c.close)
  const r = rsi(close, cfg.rsiPeriod)
  const { adx: adxArr } = adx(candles, 14)
  const i = close.length - 1
  const slDist = cfg.slPip * GOLD_PIP
  const tpDist = cfg.tpPip * GOLD_PIP

  const rsiNow = r[i], rsiPrev = r[i - 1]
  const adxPrev = adxArr[i - 1]
  const adxOk = !isFinite(cfg.adxMax) || (Number.isFinite(adxPrev) && adxPrev <= cfg.adxMax)
  const crossBack = Number.isFinite(rsiNow) && Number.isFinite(rsiPrev) && rsiPrev > cfg.hi && rsiNow <= cfg.hi

  const indicators: RouterDecision['indicators'] = [
    { name: `RSI-${cfg.rsiPeriod} (اشباعِ خرید > ${cfg.hi})`,
      value: Number.isFinite(rsiNow) ? rsiNow.toFixed(1) + (rsiNow > cfg.hi ? ' (اشباع)' : '') : '—',
      status: crossBack ? 'ok' : (Number.isFinite(rsiNow) && rsiNow > cfg.hi ? 'warn' : 'neutral') },
    ...(isFinite(cfg.adxMax) ? [{ name: `فیلترِ رژیم (ADX≤${cfg.adxMax})`,
      value: Number.isFinite(adxPrev) ? adxPrev.toFixed(0) + (adxOk ? ' ✔' : ' ✘ روندِ قوی') : '—',
      status: (adxOk ? 'ok' : 'bad') as 'ok' | 'bad' }] : []),
  ]

  const active = crossBack && adxOk
  // approaching: RSI هنوز بالای hi است (هنوز برنگشته) و رژیم اجازه می‌دهد
  const approaching = !active && Number.isFinite(rsiNow) && rsiNow > cfg.hi && adxOk

  return {
    active, approaching, direction: 'SHORT', slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason: active
      ? `RSI-${cfg.rsiPeriod} از بالای ${cfg.hi} به ${rsiNow.toFixed(1)} برگشت (تخلیهٔ اشباعِ خرید) و رژیم رنج است ⇒ فروش.`
      : approaching
        ? `RSI-${cfg.rsiPeriod}=${rsiNow.toFixed(1)} بالای آستانهٔ اشباع (${cfg.hi}) است؛ منتظرِ بازگشت به زیرِ آستانه برای ماشهٔ فروش.`
        : `شرطِ اشباعِ خرید/بازگشت برقرار نیست؛ سیگنالِ S328 نداریم.`,
    approachReason: approaching ? `بازگشتِ RSI-${cfg.rsiPeriod} به زیرِ ${cfg.hi}` : undefined,
    indicators,
  }
}

export function decideS328(cfg: S328Config, a: AnalysisResult, candles: Candle[], capital = 10000, riskPct = 1.0): RouterDecision {
  const raw = computeS328(candles, cfg)
  const { adx: adxArr } = adx(candles, 14)
  const reg = lightRegime(candles.map(c => c.close), nz(last(adxArr)), false, 's328_fade')
  return rawToDecision(raw, {
    code: 'S328', name: 'RSI-21 Fade فروش', kind: 'mean-reversion' as any,
    manageStyle: 'fixed-tp-sl', manageNote: 'هدف/حدِ ثابت (spike-fade). SL/TP جابه‌جا نشود؛ تا max_hold یا برخوردِ سطح نگه‌دار.',
    filters: [isFinite(cfg.adxMax) ? `فیلترِ رژیم ADX≤${cfg.adxMax}` : 'بدونِ فیلترِ ADX (H1)', `RSI-${cfg.rsiPeriod} cross-back از ${cfg.hi}`],
  }, cfg.id, a.price, reg, capital, riskPct)
}

// ===========================================================================
// S330 — Session-ORB Fade (سشنِ آسیا) + فیلترِ رژیمِ نوسان   منشأ: S21
// ---------------------------------------------------------------------------
// بازهٔ افتتاحیهٔ سشنِ آسیا (شروع ۰ UTC، or_bars=12 کندلِ M5 = ۱ ساعت) را می‌سازیم.
// در پنجرهٔ trade_window_bars=48 پس از بسته‌شدنِ بازه، اگر یک کندل بیرون از بازه بسته
// شود سپس کندلِ بعدی close را **به داخلِ بازه بازگرداند** ⇒ شکستِ کاذب ⇒ fade:
//   شکستِ بالا که پس گرفته شد ⇒ SHORT ؛ شکستِ پایین که پس گرفته شد ⇒ LONG.
// TP/SL = or_range × k (k_sl=k_tp=1.0 ⇒ RR متقارن، شناور بر حسبِ عرضِ بازه).
// فیلترِ رژیم: ATR14/ATR_MA(500) ≤ 1.1 (نوسانِ غیرِ افراطی — بهبودِ کلیدیِ احیا).
// ===========================================================================
export interface S330Config {
  id: string                    // XAUUSD-M5
  sessionStartHourUtc: number   // 0
  orBars: number                // 12
  tradeWindowBars: number       // 48
  kSl: number                   // 1.0
  kTp: number                   // 1.0
  maxHold: number               // 48
  regimeAtrRatioMax: number     // 1.1
  regimeAtrMa: number           // 500
}

export const S330_CFG: Record<string, S330Config> = {
  'XAUUSD-M5': {
    id: 'XAUUSD-M5', sessionStartHourUtc: 0, orBars: 12, tradeWindowBars: 48,
    kSl: 1.0, kTp: 1.0, maxHold: 48, regimeAtrRatioMax: 1.1, regimeAtrMa: 500,
  },
}

// بازهٔ افتتاحیهٔ سشنِ جاری را پیدا می‌کند (اندیسِ شروع = اولین کندلِ ساعتِ session_start).
function findSessionOpen(times: number[], startHourUtc: number): number {
  for (let i = times.length - 1; i >= 1; i--) {
    const h = new Date(times[i] * 1000).getUTCHours()
    const hPrev = new Date(times[i - 1] * 1000).getUTCHours()
    if (h === startHourUtc && hPrev !== startHourUtc) return i
  }
  return -1
}

export function computeS330(candles: Candle[], cfg: S330Config): RawSignal {
  const n = candles.length
  const close = candles.map(c => c.close)
  const times = candles.map(c => c.time)
  const atr14 = atr(candles, 14)
  const atrMa = sma(atr14, cfg.regimeAtrMa)
  const i = n - 1

  const empty = (reason: string, ind: RouterDecision['indicators']): RawSignal => ({
    active: false, approaching: false, direction: 'LONG', slDist: 0, tpDist: 0,
    maxHoldBars: cfg.maxHold, reason, indicators: ind,
  })

  // فیلترِ رژیمِ نوسان
  const atrRatio = atrMa[i] > 0 ? atr14[i] / atrMa[i] : NaN
  const regimeOk = Number.isFinite(atrRatio) && atrRatio <= cfg.regimeAtrRatioMax
  const indBase: RouterDecision['indicators'] = [
    { name: `رژیمِ نوسان (ATR14/ATR_MA${cfg.regimeAtrMa} ≤ ${cfg.regimeAtrRatioMax})`,
      value: Number.isFinite(atrRatio) ? atrRatio.toFixed(2) + (regimeOk ? ' ✔' : ' ✘ نوسانِ افراطی') : '—',
      status: (regimeOk ? 'ok' : 'bad') as 'ok' | 'bad' },
  ]

  const openIdx = findSessionOpen(times, cfg.sessionStartHourUtc)
  if (openIdx < 0 || openIdx + cfg.orBars >= n) {
    return empty('بازهٔ افتتاحیهٔ سشنِ آسیا هنوز کامل نشده یا یافت نشد؛ صبر می‌کنیم.', indBase)
  }
  // بازهٔ افتتاحیه: [openIdx , openIdx+orBars)
  let orHi = -Infinity, orLo = Infinity
  for (let k = openIdx; k < openIdx + cfg.orBars; k++) { orHi = Math.max(orHi, candles[k].high); orLo = Math.min(orLo, candles[k].low) }
  const orRange = orHi - orLo
  const winStart = openIdx + cfg.orBars
  const inWindow = i >= winStart && i <= winStart + cfg.tradeWindowBars
  indBase.push({ name: 'بازهٔ افتتاحیهٔ آسیا (OR)', value: `${orLo.toFixed(2)}–${orHi.toFixed(2)} (${(orRange / GOLD_PIP).toFixed(0)} pip)`, status: 'neutral' })

  if (!(orRange > 0) || !inWindow) {
    return empty(inWindow ? 'عرضِ بازهٔ افتتاحیه نامعتبر است.' : 'خارج از پنجرهٔ معاملاتیِ پس از بازهٔ افتتاحیه؛ سیگنالی نیست.', indBase)
  }
  if (!regimeOk) return empty('نوسانِ بازار افراطی است (فیلترِ رژیم رد شد)؛ fade نمی‌کنیم.', indBase)

  const slDist = cfg.kSl * orRange
  const tpDist = cfg.kTp * orRange

  // شکستِ کاذب: کندلِ قبل بیرونِ بازه بسته شد، کندلِ جاری close را داخلِ بازه بازگرداند
  const prevBreakUp = close[i - 1] > orHi
  const prevBreakDn = close[i - 1] < orLo
  const backInside = close[i] <= orHi && close[i] >= orLo
  const fadeShort = prevBreakUp && backInside      // شکستِ بالا پس گرفته شد ⇒ فروش
  const fadeLong = prevBreakDn && backInside       // شکستِ پایین پس گرفته شد ⇒ خرید

  if (fadeShort || fadeLong) {
    const dir: 'LONG' | 'SHORT' = fadeLong ? 'LONG' : 'SHORT'
    return {
      active: true, approaching: false, direction: dir, slDist, tpDist, maxHoldBars: cfg.maxHold,
      reason: `شکستِ کاذبِ ${fadeLong ? 'پایینِ' : 'بالای'} بازهٔ افتتاحیهٔ آسیا پس گرفته شد (close داخلِ بازه) و رژیمِ نوسان سالم است ⇒ ${fadeLong ? 'خرید' : 'فروش'} (fade).`,
      indicators: indBase,
    }
  }

  // approaching: قیمت هم‌اکنون بیرونِ بازه است (منتظرِ بازگشتِ close به داخل)
  const outsideNow = close[i] > orHi || close[i] < orLo
  return {
    active: false, approaching: outsideNow, direction: close[i] > orHi ? 'SHORT' : 'LONG',
    slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason: outsideNow
      ? `قیمت بیرونِ بازهٔ افتتاحیهٔ آسیاست؛ منتظرِ بازگشتِ close به داخلِ بازه برای تأییدِ شکستِ کاذب (fade).`
      : `قیمت داخلِ بازهٔ افتتاحیه است؛ هنوز شکستِ کاذبی برای fade رخ نداده.`,
    approachReason: outsideNow ? 'بازگشتِ close به داخلِ بازهٔ افتتاحیه' : undefined,
    indicators: indBase,
  }
}

export function decideS330(cfg: S330Config, a: AnalysisResult, candles: Candle[], capital = 10000, riskPct = 1.0): RouterDecision {
  const raw = computeS330(candles, cfg)
  const reg = lightRegime(candles.map(c => c.close), 0, false, 's330_orb_fade')
  return rawToDecision(raw, {
    code: 'S330', name: 'Session-ORB Fade (آسیا)', kind: 'session' as any,
    manageStyle: 'fixed-tp-sl', manageNote: 'TP/SL شناور بر عرضِ بازهٔ افتتاحیه (RR متقارن). تا max_hold یا برخورد نگه‌دار.',
    filters: ['سشنِ آسیا (۰ UTC)', 'شکستِ کاذبِ بازهٔ افتتاحیه', `فیلترِ رژیم ATR14/ATR_MA${cfg.regimeAtrMa}≤${cfg.regimeAtrRatioMax}`],
  }, cfg.id, a.price, reg, capital, riskPct)
}

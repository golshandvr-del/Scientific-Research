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
  // 🕒 باگِ User Note (نکتهٔ سوم): دروازهٔ زمانی برای شمارشِ معکوسِ ۲۴ساعته زیرِ کارت.
  //   لایه‌های زمان-محور (S310/S312/...) این را پر می‌کنند تا فرانت‌اند نوارِ ریزِ
  //   «عنوانِ لایه · ساعتِ فعال‌سازی به وقتِ ایران · شمارشِ معکوس» را بسازد.
  timeGate?: RouterDecision['timeGate']
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

  // درصدِ اطمینانِ شفاف: نسبتِ شاخص‌های تأییدکننده (ok) به کلِ شاخص‌های تصمیم‌ساز
  //   (neutralها شمرده نمی‌شوند). صرفاً بازتابِ «چند شرط برقرار است»؛ نه احتمالِ آماری.
  const decisive = raw.indicators.filter(i => i.status === 'ok' || i.status === 'warn' || i.status === 'bad')
  const okCount = raw.indicators.filter(i => i.status === 'ok').length
  const confPct = decisive.length > 0 ? Math.round((okCount / decisive.length) * 100) : undefined

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
      probability: confPct,
      sizing: lots != null ? {
        lotMultiplier: 1.0, label: 'واحدِ پایه',
        note: `حجمِ سرمایه‌محور بر پایهٔ ریسکِ ${riskPct}% و فاصلهٔ SL`,
        lots, riskDollars: rd, capital, riskPct,
        // 🔧 باگِ User Note (نکتهٔ دوم): متن باید ضررِ *واقعیِ* دلاری با حجمِ نهایی را بگوید.
        //   فاصلهٔ SL «دلار به ازای هر اونس» است؛ ضررِ کلِ معامله = فاصله × ۱۰۰ × لات.
        capitalNote: `با حجمِ ${lots.toFixed(2)} لات، اگر SL بخورد حدودِ ${rd}$ ضرر می‌کنید ` +
          `(فاصلهٔ SL ≈ ${raw.slDist.toFixed(2)}$ به ازای هر اونس).`,
      } : undefined,
      indicators: raw.indicators,
      timeGate: raw.timeGate,
    }
  }

  if (raw.approaching) {
    return {
      state: 'APPROACHING', regime: reg,
      headline: `احتمالِ نزدیک‌شدن به سیگنال — ${meta.name}`,
      reason: raw.reason,
      sourceLayer,
      direction: raw.direction,
      probability: confPct,
      confirmations: raw.approachReason
        ? [{ label: raw.approachReason, met: false, detail: raw.approachReason }]
        : undefined,
      indicators: raw.indicators,
      timeGate: raw.timeGate,
    }
  }

  // NEUTRAL: طبقِ تعریفِ سایت، ربات باید صریحاً بگوید «به‌دلیلِ کدام لایه/شاخص‌ها»
  //   هنوز واردِ معامله نمی‌شود ⇒ sourceLayer را نگه می‌داریم (کدِ لایهٔ ناظر).
  return {
    state: 'NEUTRAL', regime: reg,
    headline: `خنثی — ${meta.name}`,
    reason: raw.reason,
    sourceLayer,
    indicators: raw.indicators,
    timeGate: raw.timeGate,
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

// ===========================================================================
// S322 — Ichimoku Kumo breakout-pullback (LONG)   XAUUSD M15
// ---------------------------------------------------------------------------
// اجزای Ichimoku (Bill Williams / Goichi Hosoda): Tenkan(9)، Kijun(26)،
//   Senkou-A=(Tenkan+Kijun)/2، Senkou-B=(max52High+min52Low)/2، ابر=Kumo.
// ورود LONG: قیمت بالای Kumo با da_min (جدایی/ATR)، ابرِ ضخیم (thick_min/ATR)،
//   gap کافی (gap_min/ATR بینِ Senkouها)، و pullback به Kijun (فاصله ≤ kijun_atr_max×ATR)،
//   RSI ∈ [rsi_min, rsi_max]. SL=2.5×ATR، TP=3.3×ATR، max_hold=56. غیر-رند.
// ===========================================================================
export interface S322Config {
  id: string
  tenkan: number; kijun: number; senkouB: number
  kijunAtrMax: number; thickMin: number; gapMin: number; daMin: number
  rsiMin: number; rsiMax: number
  slMult: number; tpMult: number; maxHold: number
}

export const S322_CFG: Record<string, S322Config> = {
  'XAUUSD-M15': {
    id: 'XAUUSD-M15', tenkan: 9, kijun: 26, senkouB: 52,
    kijunAtrMax: 0.62, thickMin: 0.32, gapMin: 0.22, daMin: 0.25,
    rsiMin: 45, rsiMax: 90, slMult: 2.5, tpMult: 3.3, maxHold: 56,
  },
}

function donchianMid(high: number[], low: number[], i: number, len: number): number {
  if (i < len - 1) return NaN
  let hi = -Infinity, lo = Infinity
  for (let k = i - len + 1; k <= i; k++) { hi = Math.max(hi, high[k]); lo = Math.min(lo, low[k]) }
  return (hi + lo) / 2
}

export function computeS322(candles: Candle[], cfg: S322Config): RawSignal {
  const high = candles.map(c => c.high), low = candles.map(c => c.low), close = candles.map(c => c.close)
  const atr14 = atr(candles, 14)
  const r = rsi(close, 14)
  const i = close.length - 1
  const atrVal = atr14[i]

  const empty = (reason: string, ind: RouterDecision['indicators']): RawSignal => ({
    active: false, approaching: false, direction: 'LONG', slDist: 0, tpDist: 0,
    maxHoldBars: cfg.maxHold, reason, indicators: ind,
  })

  // Ichimoku جاری (ابر با شیفتِ ۲۶ به جلو ⇒ برای کندلِ جاری از داده‌ی ۲۶ کندلِ قبل)
  const tenkanNow = donchianMid(high, low, i, cfg.tenkan)
  const kijunNow = donchianMid(high, low, i, cfg.kijun)
  const shift = cfg.kijun
  const spanAAt = (j: number) => (donchianMid(high, low, j, cfg.tenkan) + donchianMid(high, low, j, cfg.kijun)) / 2
  const spanBAt = (j: number) => donchianMid(high, low, j, cfg.senkouB)
  const jSrc = i - shift
  const senkouA = jSrc >= 0 ? spanAAt(jSrc) : NaN
  const senkouB = jSrc >= 0 ? spanBAt(jSrc) : NaN

  if ([atrVal, kijunNow, senkouA, senkouB, r[i]].some(v => !Number.isFinite(v)) || !(atrVal > 0)) {
    return empty('دادهٔ کافی برای محاسبهٔ Ichimoku/ATR نیست.', [])
  }

  const cloudTop = Math.max(senkouA, senkouB)
  const cloudBot = Math.min(senkouA, senkouB)
  const thickness = (cloudTop - cloudBot) / atrVal          // ضخامتِ ابر / ATR
  const gap = Math.abs(senkouA - senkouB) / atrVal          // فاصلهٔ SenkouA/B / ATR
  const price = close[i]
  const da = (price - cloudTop) / atrVal                    // جدایی از سقفِ ابر / ATR
  const kijunDist = Math.abs(price - kijunNow) / atrVal     // فاصله تا Kijun (pullback)
  const rsiNow = r[i]

  const aboveCloud = price > cloudTop
  const daOk = da >= cfg.daMin
  const thickOk = thickness >= cfg.thickMin
  const gapOk = gap >= cfg.gapMin
  const pullbackOk = kijunDist <= cfg.kijunAtrMax
  const rsiOk = rsiNow >= cfg.rsiMin && rsiNow <= cfg.rsiMax

  const ind: RouterDecision['indicators'] = [
    { name: 'قیمت نسبت به ابرِ Kumo', value: aboveCloud ? `بالای ابر (جدایی ${da.toFixed(2)}×ATR)` : 'داخل/زیرِ ابر', status: aboveCloud && daOk ? 'ok' : 'warn' },
    { name: `ضخامتِ ابر (≥${cfg.thickMin}×ATR)`, value: thickness.toFixed(2) + (thickOk ? ' ✔' : ' ✘'), status: thickOk ? 'ok' : 'warn' },
    { name: `pullback به Kijun (≤${cfg.kijunAtrMax}×ATR)`, value: kijunDist.toFixed(2) + (pullbackOk ? ' ✔' : ' ✘'), status: pullbackOk ? 'ok' : 'neutral' },
    { name: `RSI-14 ∈ [${cfg.rsiMin},${cfg.rsiMax}]`, value: rsiNow.toFixed(0) + (rsiOk ? ' ✔' : ' ✘'), status: rsiOk ? 'ok' : 'warn' },
  ]

  const slDist = cfg.slMult * atrVal
  const tpDist = cfg.tpMult * atrVal
  const active = aboveCloud && daOk && thickOk && gapOk && pullbackOk && rsiOk
  // approaching: بالای ابرِ سالم اما هنوز pullback به Kijun نرسیده
  const approaching = !active && aboveCloud && daOk && thickOk && gapOk && rsiOk && !pullbackOk

  return {
    active, approaching, direction: 'LONG', slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason: active
      ? `قیمت بالای ابرِ ضخیمِ Kumo (جدایی ${da.toFixed(2)}×ATR) و در pullback به Kijun است، RSI سالم ⇒ خرید.`
      : approaching
        ? `روندِ صعودیِ Ichimoku تأیید است اما قیمت هنوز به Kijun برنگشته؛ منتظرِ pullback برای ورود.`
        : `شرایطِ کاملِ Ichimoku (بالای ابرِ ضخیم + pullback + RSI) برقرار نیست.`,
    approachReason: approaching ? `pullback قیمت به نزدیکیِ Kijun (≤${cfg.kijunAtrMax}×ATR)` : undefined,
    indicators: ind,
  }
}

export function decideS322(cfg: S322Config, a: AnalysisResult, candles: Candle[], capital = 10000, riskPct = 1.0): RouterDecision {
  const raw = computeS322(candles, cfg)
  const { adx: adxArr } = adx(candles, 14)
  const reg = lightRegime(candles.map(c => c.close), nz(last(adxArr)), raw.active || raw.approaching, 's322_ichimoku')
  return rawToDecision(raw, {
    code: 'S322', name: 'Ichimoku Kumo خرید', kind: 'ma-confluence' as any,
    manageStyle: 'structural-trail', beTriggerR: 1.0,
    manageNote: 'پس از ۱R سود، SL را به بریک‌ایون ببر؛ سپس زیرِ Kijun تریل کن. با شکستِ Kijun خارج شو.',
    filters: [`ابرِ Kumo ضخیم (≥${cfg.thickMin}×ATR)`, `pullback به Kijun`, `RSI-14 ∈ [${cfg.rsiMin},${cfg.rsiMax}]`],
  }, cfg.id, a.price, reg, capital, riskPct)
}

// ===========================================================================
// S324 — Liquidity-Sweep Reversal (fade)   XAUUSD M15(LONG) / M30(SHORT)
// ---------------------------------------------------------------------------
// یک swing-pivot (سطحِ نقدینگی) شناسایی می‌شود؛ قیمت آن را «جارو» (sweep) می‌کند
//   (فراتر می‌رود) سپس بلافاصله بازمی‌گردد و سطح را پس می‌گیرد (reclaim) با کندلِ
//   بازگشتیِ قوی (displacement). این یک الگوی fade/mean-reversion است.
//   فیلترها per-TF شناور: swing_len، depth_min (عمقِ جارو/ATR)، disp_min (قدرتِ
//   بازگشت/ATR)، regime (M30: short فقط زیرِ EMA200)، RSI (long≤rsi_lo، short≥rsi_hi).
//   TP<SL کلیدِ عبور از گیتِ WR در fade است (M15: SL2.4/TP0.8، M30: SL3.1/TP1.2 ×ATR).
// ===========================================================================
export interface S324Config {
  id: string
  side: 'LONG' | 'SHORT'
  swingLen: number
  depthMin: number      // عمقِ نفوذ فراتر از pivot / ATR
  dispMin: number       // بدنهٔ کندلِ بازگشت / ATR
  regimeOn: boolean     // فیلترِ EMA200
  rsiOn: boolean
  rsiLo?: number        // برای LONG (RSI ≤ rsiLo)
  rsiHi?: number        // برای SHORT (RSI ≥ rsiHi)
  slMult: number; tpMult: number; maxHold: number
}

export const S324_CFG: Record<string, S324Config> = {
  'XAUUSD-M15': { id: 'XAUUSD-M15', side: 'LONG', swingLen: 16, depthMin: 0.70, dispMin: 0.90, regimeOn: false, rsiOn: true, rsiLo: 40, slMult: 2.4, tpMult: 0.8, maxHold: 48 },
  'XAUUSD-M30': { id: 'XAUUSD-M30', side: 'SHORT', swingLen: 8, depthMin: 0.25, dispMin: 0.50, regimeOn: true, rsiOn: true, rsiHi: 60, slMult: 3.1, tpMult: 1.2, maxHold: 48 },
}

export function computeS324(candles: Candle[], cfg: S324Config): RawSignal {
  const high = candles.map(c => c.high), low = candles.map(c => c.low), close = candles.map(c => c.close), open = candles.map(c => c.open)
  const atr14 = atr(candles, 14)
  const e200 = ema(close, 200)
  const r = rsi(close, 14)
  const i = close.length - 1
  const atrVal = atr14[i]

  const empty = (reason: string): RawSignal => ({
    active: false, approaching: false, direction: cfg.side, slDist: 0, tpDist: 0,
    maxHoldBars: cfg.maxHold, reason, indicators: [],
  })
  if (!(atrVal > 0) || i < cfg.swingLen + 2 || !Number.isFinite(r[i])) return empty('دادهٔ کافی برای S324 نیست.')

  const slDist = cfg.slMult * atrVal
  const tpDist = cfg.tpMult * atrVal

  // pivotِ نقدینگی: بالاترین/پایین‌ترینِ swing_len کندلِ پیش از کندلِ جاری (به‌جز خودِ کندل)
  let priorHi = -Infinity, priorLo = Infinity
  for (let k = i - cfg.swingLen; k < i; k++) { priorHi = Math.max(priorHi, high[k]); priorLo = Math.min(priorLo, low[k]) }

  const body = Math.abs(close[i] - open[i]) / atrVal
  const rsiNow = r[i]

  const ind: RouterDecision['indicators'] = []

  if (cfg.side === 'LONG') {
    // جاروبِ کفِ نقدینگی: low کندلِ جاری زیرِ priorLo رفت (عمق کافی) اما close بالای priorLo پس گرفت
    const sweptDepth = (priorLo - low[i]) / atrVal
    const reclaimed = close[i] > priorLo
    const dispOk = body >= cfg.dispMin
    const depthOk = sweptDepth >= cfg.depthMin
    const rsiOk = !cfg.rsiOn || rsiNow <= (cfg.rsiLo ?? 100)
    const regimeOk = !cfg.regimeOn || close[i] > e200[i]
    ind.push(
      { name: `جاروبِ کفِ نقدینگی (عمق ≥${cfg.depthMin}×ATR)`, value: sweptDepth > 0 ? sweptDepth.toFixed(2) + (depthOk ? ' ✔' : ' ✘') : 'بدونِ جارو', status: depthOk ? 'ok' : 'neutral' },
      { name: `بازگشت/reclaim (بدنه ≥${cfg.dispMin}×ATR)`, value: body.toFixed(2) + (reclaimed && dispOk ? ' ✔' : ' ✘'), status: (reclaimed && dispOk) ? 'ok' : 'warn' },
      { name: `RSI-14 اشباعِ فروش (≤${cfg.rsiLo})`, value: rsiNow.toFixed(0) + (rsiOk ? ' ✔' : ' ✘'), status: rsiOk ? 'ok' : 'warn' },
    )
    const active = depthOk && reclaimed && dispOk && rsiOk && regimeOk
    const approaching = !active && depthOk && !reclaimed
    return {
      active, approaching, direction: 'LONG', slDist, tpDist, maxHoldBars: cfg.maxHold,
      reason: active ? 'کفِ نقدینگی جارو و بلافاصله پس گرفته شد (کندلِ بازگشتِ قوی، RSI اشباعِ فروش) ⇒ خرید (fade).'
        : approaching ? 'کفِ نقدینگی جارو شد اما هنوز reclaim/بازگشت تأیید نشده؛ منتظرِ بستنِ قوی بالای سطح.'
        : 'الگوی جاروب-و-بازگشتِ کف برقرار نیست.',
      approachReason: approaching ? 'بستنِ کندلِ قوی بالای سطحِ جاروشده' : undefined,
      indicators: ind,
    }
  } else {
    // SHORT: جاروبِ سقفِ نقدینگی: high فراتر از priorHi اما close زیرِ priorHi پس گرفت
    const sweptDepth = (high[i] - priorHi) / atrVal
    const reclaimed = close[i] < priorHi
    const dispOk = body >= cfg.dispMin
    const depthOk = sweptDepth >= cfg.depthMin
    const rsiOk = !cfg.rsiOn || rsiNow >= (cfg.rsiHi ?? 0)
    const regimeOk = !cfg.regimeOn || close[i] < e200[i]
    ind.push(
      { name: `جاروبِ سقفِ نقدینگی (عمق ≥${cfg.depthMin}×ATR)`, value: sweptDepth > 0 ? sweptDepth.toFixed(2) + (depthOk ? ' ✔' : ' ✘') : 'بدونِ جارو', status: depthOk ? 'ok' : 'neutral' },
      { name: `بازگشت/reclaim (بدنه ≥${cfg.dispMin}×ATR)`, value: body.toFixed(2) + (reclaimed && dispOk ? ' ✔' : ' ✘'), status: (reclaimed && dispOk) ? 'ok' : 'warn' },
      { name: `RSI-14 اشباعِ خرید (≥${cfg.rsiHi})`, value: rsiNow.toFixed(0) + (rsiOk ? ' ✔' : ' ✘'), status: rsiOk ? 'ok' : 'warn' },
      { name: 'رژیم (close<EMA200)', value: (close[i] < e200[i] ? 'نزولی ✔' : 'صعودی ✘'), status: regimeOk ? 'ok' : 'bad' },
    )
    const active = depthOk && reclaimed && dispOk && rsiOk && regimeOk
    const approaching = !active && depthOk && !reclaimed && regimeOk
    return {
      active, approaching, direction: 'SHORT', slDist, tpDist, maxHoldBars: cfg.maxHold,
      reason: active ? 'سقفِ نقدینگی جارو و بلافاصله پس گرفته شد (کندلِ بازگشتِ قوی زیرِ EMA200، RSI اشباعِ خرید) ⇒ فروش (fade).'
        : approaching ? 'سقفِ نقدینگی جارو شد اما هنوز reclaim تأیید نشده؛ منتظرِ بستنِ قوی زیرِ سطح.'
        : 'الگوی جاروب-و-بازگشتِ سقف (زیرِ EMA200) برقرار نیست.',
      approachReason: approaching ? 'بستنِ کندلِ قوی زیرِ سطحِ جاروشده' : undefined,
      indicators: ind,
    }
  }
}

export function decideS324(cfg: S324Config, a: AnalysisResult, candles: Candle[], capital = 10000, riskPct = 1.0): RouterDecision {
  const raw = computeS324(candles, cfg)
  const reg = lightRegime(candles.map(c => c.close), 0, false, 's324_sweep')
  return rawToDecision(raw, {
    code: 'S324', name: 'Liquidity-Sweep بازگشتی', kind: 'mean-reversion' as any,
    manageStyle: 'fixed-tp-sl', manageNote: 'الگوی fade با TP<SL؛ هدفِ نزدیک را زود بگیر، SL را جابه‌جا نکن. تا max_hold نگه‌دار.',
    filters: [`swing_len=${cfg.swingLen}`, `عمقِ جارو≥${cfg.depthMin}×ATR`, `بازگشت≥${cfg.dispMin}×ATR`, cfg.regimeOn ? 'رژیمِ EMA200' : 'بدونِ فیلترِ رژیم', cfg.side === 'LONG' ? `RSI≤${cfg.rsiLo}` : `RSI≥${cfg.rsiHi}`],
  }, cfg.id, a.price, reg, capital, riskPct)
}

// ===========================================================================
// S321 — MA-Ribbon (GMMA/Alligator) pullback، دوطرفهٔ متقارن   XAUUSD M30
// ---------------------------------------------------------------------------
// ribbonِ فیبوناچیِ ۷-خطی EMA[8,13,21,34,55,89,144] (هم‌خانوادهٔ GMMA/Alligator).
// ورود کلاسیک «buy/sell-the-pullback-to-the-ribbon»:
//   (1) ribbon کاملاً مرتب (order ratio ≥ ord_thr): fan صعودی یا نزولی
//   (2) رژیمِ عرضِ ribbon کافی (width z-score ≥ wz_gate): ribbon منبسط، نه درهم
//   (3) pullback قیمت به بدنهٔ ribbon (عمق ∈ [pull_min, pull_max])
//   (4) شیبِ EMA34 نرمال‌شده با ATR ≥ slope_min
//   (5) RSI ∈ [rsi_min, rsi_max]
//   SL=TP=2.7×ATR (RR متقارن، غیر-رند)، max_hold=36. دوطرفه (LONG/SHORT).
// ===========================================================================
export interface S321Config {
  id: string
  ribbon: number[]      // [8,13,21,34,55,89,144]
  ordThr: number        // 0.40
  wzGate: number        // 0.15
  pullMin: number; pullMax: number   // 0.05 / 0.82
  rsiMin: number; rsiMax: number     // 45 / 85
  slopeMin: number      // 0.055 (شیبِ EMA34/ATR، lookback=5)
  slMult: number; tpMult: number; maxHold: number   // 2.7 / 2.7 / 36
}

export const S321_CFG: Record<string, S321Config> = {
  'XAUUSD-M30': {
    id: 'XAUUSD-M30', ribbon: [8, 13, 21, 34, 55, 89, 144],
    ordThr: 0.40, wzGate: 0.15, pullMin: 0.05, pullMax: 0.82,
    rsiMin: 45, rsiMax: 85, slopeMin: 0.055, slMult: 2.7, tpMult: 2.7, maxHold: 36,
  },
}

export function computeS321(candles: Candle[], cfg: S321Config): RawSignal {
  const close = candles.map(c => c.close)
  const atr14 = atr(candles, 14)
  const r = rsi(close, 14)
  const i = close.length - 1
  const atrVal = atr14[i]

  const empty = (reason: string): RawSignal => ({
    active: false, approaching: false, direction: 'LONG', slDist: 0, tpDist: 0,
    maxHoldBars: cfg.maxHold, reason, indicators: [],
  })
  if (!(atrVal > 0) || i < 150 || !Number.isFinite(r[i])) return empty('دادهٔ کافی برای ribbon نیست.')

  // مقادیرِ EMAهای ribbon در کندلِ جاری
  const emas = cfg.ribbon.map(p => ema(close, p))
  const vals = emas.map(e => e[i])
  if (vals.some(v => !Number.isFinite(v))) return empty('ribbon هنوز محاسبه نشده.')

  // order ratio: نسبتِ جفت‌های مجاورِ مرتب (صعودی: هر EMAِ کوتاه‌تر بالای بلندتر)
  let ascPairs = 0, descPairs = 0
  for (let k = 0; k < vals.length - 1; k++) {
    if (vals[k] > vals[k + 1]) ascPairs++      // کوتاه بالای بلند ⇒ صعودی
    else if (vals[k] < vals[k + 1]) descPairs++
  }
  const nPairs = vals.length - 1
  const ascRatio = ascPairs / nPairs
  const descRatio = descPairs / nPairs

  // عرضِ ribbon = (max-min)/ATR، و z-score آن روی ۱۰۰ کندلِ اخیر
  const widthSeries: number[] = []
  for (let j = Math.max(0, i - 120); j <= i; j++) {
    const vv = emas.map(e => e[j])
    if (vv.some(v => !Number.isFinite(v))) { widthSeries.push(NaN); continue }
    widthSeries.push((Math.max(...vv) - Math.min(...vv)) / (atr14[j] || atrVal))
  }
  const valid = widthSeries.filter(v => Number.isFinite(v))
  const mean = valid.reduce((s, v) => s + v, 0) / (valid.length || 1)
  const sd = Math.sqrt(valid.reduce((s, v) => s + (v - mean) ** 2, 0) / (valid.length || 1)) || 1
  const widthZ = (last(widthSeries) - mean) / sd

  // شیبِ EMA34 نرمال با ATR (lookback=5)
  const e34 = emas[3]  // index 3 = EMA34
  const slope = Number.isFinite(e34[i - 5]) ? (e34[i] - e34[i - 5]) / (5 * atrVal) : NaN

  // pullback: عمقِ نفوذِ قیمت به بدنهٔ ribbon (۰=لبهٔ نزدیک، ۱=لبهٔ دور)
  const rHi = Math.max(...vals), rLo = Math.min(...vals)
  const price = close[i]
  const band = rHi - rLo || atrVal
  const rsiNow = r[i]

  const slDist = cfg.slMult * atrVal
  const tpDist = cfg.tpMult * atrVal
  const wzOk = Number.isFinite(widthZ) && widthZ >= cfg.wzGate
  const slopeMag = Number.isFinite(slope) ? Math.abs(slope) : 0
  const slopeOk = slopeMag >= cfg.slopeMin
  const rsiOk = rsiNow >= cfg.rsiMin && rsiNow <= cfg.rsiMax

  const ind: RouterDecision['indicators'] = [
    { name: `ترتیبِ ribbon (≥${cfg.ordThr})`, value: `صعودی ${ascRatio.toFixed(2)} / نزولی ${descRatio.toFixed(2)}`, status: (ascRatio >= cfg.ordThr || descRatio >= cfg.ordThr) ? 'ok' : 'warn' },
    { name: `عرضِ ribbon (z≥${cfg.wzGate})`, value: (Number.isFinite(widthZ) ? widthZ.toFixed(2) : '—') + (wzOk ? ' ✔' : ' ✘'), status: wzOk ? 'ok' : 'neutral' },
    { name: `شیبِ EMA34 (≥${cfg.slopeMin})`, value: slopeMag.toFixed(3) + (slopeOk ? ' ✔' : ' ✘'), status: slopeOk ? 'ok' : 'warn' },
    { name: `RSI-14 ∈ [${cfg.rsiMin},${cfg.rsiMax}]`, value: rsiNow.toFixed(0) + (rsiOk ? ' ✔' : ' ✘'), status: rsiOk ? 'ok' : 'warn' },
  ]

  // LONG: ribbon صعودیِ مرتب، شیبِ مثبت، pullback قیمت به بدنهٔ ribbon از بالا
  if (ascRatio >= cfg.ordThr && slope > 0 && wzOk && slopeOk && rsiOk) {
    const depth = (rHi - price) / band     // ۰ = روی سقفِ ribbon، ۱ = روی کفِ ribbon
    const pullOk = depth >= cfg.pullMin && depth <= cfg.pullMax
    ind.push({ name: `عمقِ pullback ∈ [${cfg.pullMin},${cfg.pullMax}]`, value: depth.toFixed(2) + (pullOk ? ' ✔' : ''), status: pullOk ? 'ok' : 'neutral' })
    if (pullOk) return { active: true, approaching: false, direction: 'LONG', slDist, tpDist, maxHoldBars: cfg.maxHold, reason: 'ribbonِ GMMA صعودیِ مرتب و منبسط + pullback قیمت به بدنهٔ ribbon + شیب و RSI سالم ⇒ خرید.', indicators: ind }
    return { active: false, approaching: true, direction: 'LONG', slDist, tpDist, maxHoldBars: cfg.maxHold, reason: 'ribbonِ صعودی مرتب است؛ منتظرِ pullback قیمت به بدنهٔ ribbon برای ورودِ خرید.', approachReason: 'pullback قیمت به بدنهٔ ribbon', indicators: ind }
  }
  // SHORT: ribbon نزولیِ مرتب، شیبِ منفی، pullback قیمت به بدنه از پایین
  if (descRatio >= cfg.ordThr && slope < 0 && wzOk && slopeOk && rsiOk) {
    const depth = (price - rLo) / band     // ۰ = روی کفِ ribbon، ۱ = روی سقفِ ribbon
    const pullOk = depth >= cfg.pullMin && depth <= cfg.pullMax
    ind.push({ name: `عمقِ pullback ∈ [${cfg.pullMin},${cfg.pullMax}]`, value: depth.toFixed(2) + (pullOk ? ' ✔' : ''), status: pullOk ? 'ok' : 'neutral' })
    if (pullOk) return { active: true, approaching: false, direction: 'SHORT', slDist, tpDist, maxHoldBars: cfg.maxHold, reason: 'ribbonِ GMMA نزولیِ مرتب و منبسط + pullback قیمت به بدنهٔ ribbon + شیب و RSI سالم ⇒ فروش.', indicators: ind }
    return { active: false, approaching: true, direction: 'SHORT', slDist, tpDist, maxHoldBars: cfg.maxHold, reason: 'ribbonِ نزولی مرتب است؛ منتظرِ pullback قیمت به بدنهٔ ribbon برای ورودِ فروش.', approachReason: 'pullback قیمت به بدنهٔ ribbon', indicators: ind }
  }

  return empty('ribbon مرتب/منبسط با شیب و RSیِ لازم نیست؛ سیگنالِ S321 نداریم.')
}

export function decideS321(cfg: S321Config, a: AnalysisResult, candles: Candle[], capital = 10000, riskPct = 1.0): RouterDecision {
  const raw = computeS321(candles, cfg)
  const reg = lightRegime(candles.map(c => c.close), 0, raw.active || raw.approaching, 's321_ribbon')
  return rawToDecision(raw, {
    code: 'S321', name: 'MA-Ribbon (GMMA) pullback', kind: 'ma-confluence' as any,
    manageStyle: 'structural-trail', beTriggerR: 1.0,
    manageNote: 'پس از ۱R، SL به بریک‌ایون؛ سپس پشتِ EMA34/55ِ ribbon تریل کن. با شکستِ ribbon خارج شو.',
    filters: [`ترتیبِ ribbon≥${cfg.ordThr}`, `عرض z≥${cfg.wzGate}`, `شیب≥${cfg.slopeMin}`, `pullback [${cfg.pullMin},${cfg.pullMax}]`],
  }, cfg.id, a.price, reg, capital, riskPct)
}

// ===========================================================================
// S323 — S/R Pullback + پنجرهٔ طلایی (LONG)   XAUUSD M15/M30/H1
// ---------------------------------------------------------------------------
// در روندِ صعودیِ تأییدشده (close>EMA200 و ADX≥adx_min)، قیمت به یک pivotِ حمایت
//   pullback می‌کند (فاصله تا حمایت ≤ near_max×ATR) با فضای کافی تا مقاومتِ بعدی
//   (room ≥ room_min×ATR)، RSI ≤ rsi_max (نه اشباعِ خرید)، و در پنجرهٔ زمانیِ
//   «طلایی» (ساعتِ h_lo..h_hi به UTC — سشنِ فعالِ نیویورک/لندن). SL/TP per-TF.
// ===========================================================================
export interface S323Config {
  id: string
  nearMax: number; roomMin: number; rsiMax: number
  slopeMin: number; adxMin: number
  golden: boolean; hLo: number; hHi: number
  slMult: number; tpMult: number; maxHold: number
  pivotLen: number
}

export const S323_CFG: Record<string, S323Config> = {
  'XAUUSD-M15': { id: 'XAUUSD-M15', nearMax: 0.85, roomMin: 1.3, rsiMax: 55, slopeMin: 0.0, adxMin: 22, golden: true, hLo: 19, hHi: 23, slMult: 1.8, tpMult: 1.5, maxHold: 96, pivotLen: 20 },
  'XAUUSD-M30': { id: 'XAUUSD-M30', nearMax: 0.85, roomMin: 1.3, rsiMax: 55, slopeMin: 0.0, adxMin: 22, golden: true, hLo: 19, hHi: 23, slMult: 2.1, tpMult: 1.3, maxHold: 48, pivotLen: 20 },
  'XAUUSD-H1':  { id: 'XAUUSD-H1',  nearMax: 0.55, roomMin: 1.3, rsiMax: 55, slopeMin: 0.0, adxMin: 30, golden: true, hLo: 19, hHi: 23, slMult: 1.8, tpMult: 1.7, maxHold: 36, pivotLen: 20 },
}

export function computeS323(candles: Candle[], cfg: S323Config, utcHour: number): RawSignal {
  const high = candles.map(c => c.high), low = candles.map(c => c.low), close = candles.map(c => c.close)
  const atr14 = atr(candles, 14)
  const e200 = ema(close, 200)
  const { adx: adxArr } = adx(candles, 14)
  const r = rsi(close, 14)
  const i = close.length - 1
  const atrVal = atr14[i]

  const empty = (reason: string, ind: RouterDecision['indicators']): RawSignal => ({
    active: false, approaching: false, direction: 'LONG', slDist: 0, tpDist: 0,
    maxHoldBars: cfg.maxHold, reason, indicators: ind,
  })
  if (!(atrVal > 0) || i < 200 || !Number.isFinite(r[i])) return empty('دادهٔ کافی برای S323 نیست.', [])

  const price = close[i]
  const trendUp = price > e200[i]
  const adxVal = adxArr[i]
  const adxOk = Number.isFinite(adxVal) && adxVal >= cfg.adxMin

  // نزدیک‌ترین pivotِ حمایت (پایین‌ترینِ محلی) زیرِ قیمت، و مقاومت (بالاترینِ محلی) بالای قیمت
  let support = -Infinity, resistance = Infinity
  const L = cfg.pivotLen
  for (let k = i - 1; k >= Math.max(0, i - 120); k--) {
    if (k - L < 0 || k + L > i) continue
    const isLow = low.slice(k - L, k + L + 1).every(v => v >= low[k])
    const isHigh = high.slice(k - L, k + L + 1).every(v => v <= high[k])
    if (isLow && low[k] < price && low[k] > support) support = low[k]
    if (isHigh && high[k] > price && high[k] < resistance) resistance = high[k]
  }

  const goldenOk = !cfg.golden || (utcHour >= cfg.hLo && utcHour <= cfg.hHi)
  const rsiNow = r[i]
  const rsiOk = rsiNow <= cfg.rsiMax

  const nearSupport = isFinite(support) ? (price - support) / atrVal : Infinity
  const room = isFinite(resistance) ? (resistance - price) / atrVal : Infinity
  const nearOk = nearSupport <= cfg.nearMax
  const roomOk = room >= cfg.roomMin

  const ind: RouterDecision['indicators'] = [
    { name: `روندِ صعودی (close>EMA200، ADX≥${cfg.adxMin})`, value: (trendUp ? 'صعودی' : 'نزولی') + ` / ADX ${Number.isFinite(adxVal) ? adxVal.toFixed(0) : '—'}`, status: (trendUp && adxOk) ? 'ok' : 'bad' },
    { name: `pullback به حمایت (≤${cfg.nearMax}×ATR)`, value: isFinite(nearSupport) ? nearSupport.toFixed(2) + (nearOk ? ' ✔' : ' ✘') : '—', status: nearOk ? 'ok' : 'neutral' },
    { name: `فضا تا مقاومت (≥${cfg.roomMin}×ATR)`, value: isFinite(room) ? room.toFixed(2) + (roomOk ? ' ✔' : ' ✘') : '—', status: roomOk ? 'ok' : 'warn' },
    { name: `RSI-14 ≤ ${cfg.rsiMax}`, value: rsiNow.toFixed(0) + (rsiOk ? ' ✔' : ' ✘'), status: rsiOk ? 'ok' : 'warn' },
    ...(cfg.golden ? [{ name: `پنجرهٔ طلایی (${cfg.hLo}:00–${cfg.hHi}:00 UTC)`, value: `${utcHour}:00 UTC` + (goldenOk ? ' ✔' : ' ✘ خارج'), status: (goldenOk ? 'ok' : 'neutral') as 'ok' | 'neutral' }] : []),
  ]

  const slDist = cfg.slMult * atrVal
  const tpDist = cfg.tpMult * atrVal
  const trendCtx = trendUp && adxOk
  const active = trendCtx && nearOk && roomOk && rsiOk && goldenOk
  const approaching = !active && trendCtx && roomOk && rsiOk && (goldenOk || nearOk)

  return {
    active, approaching, direction: 'LONG', slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason: active
      ? 'روندِ صعودیِ تأییدشده + pullback به حمایت با فضای کافی تا مقاومت + RSI غیرِ اشباع در پنجرهٔ طلایی ⇒ خرید.'
      : approaching
        ? 'روندِ صعودی برقرار است؛ منتظرِ pullback کاملِ قیمت به حمایت (یا ورود به پنجرهٔ طلایی) برای ماشهٔ خرید.'
        : (trendCtx ? 'روند صعودی است اما ستاپِ pullback/طلایی کامل نیست.' : 'روندِ صعودیِ لازم (EMA200/ADX) برقرار نیست؛ سیگنالِ S323 نداریم.'),
    approachReason: approaching ? 'کامل‌شدنِ pullback به حمایت در پنجرهٔ طلایی' : undefined,
    indicators: ind,
  }
}

export function decideS323(cfg: S323Config, a: AnalysisResult, candles: Candle[], utcHour: number, capital = 10000, riskPct = 1.0): RouterDecision {
  const raw = computeS323(candles, cfg, utcHour)
  const { adx: adxArr } = adx(candles, 14)
  const reg = lightRegime(candles.map(c => c.close), nz(last(adxArr)), raw.active || raw.approaching, 's323_sr_pullback')
  return rawToDecision(raw, {
    code: 'S323', name: 'S/R Pullback طلایی', kind: 'price-action' as any,
    manageStyle: 'structural-trail', beTriggerR: 1.0,
    manageNote: 'پس از ۱R، SL به بریک‌ایون؛ سپس زیرِ آخرین swing-low تریل کن. با نزدیک‌شدن به مقاومت، TP را پیش‌دستانه بگیر.',
    filters: [`روند EMA200 + ADX≥${cfg.adxMin}`, `pullback حمایت ≤${cfg.nearMax}×ATR`, `فضا ≥${cfg.roomMin}×ATR`, `RSI≤${cfg.rsiMax}`, cfg.golden ? `پنجرهٔ طلایی ${cfg.hLo}-${cfg.hHi} UTC` : 'بدونِ فیلترِ زمان'],
  }, cfg.id, a.price, reg, capital, riskPct)
}

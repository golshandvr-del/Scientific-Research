// ============================================================================
// s335_reflex_cycle.ts — لایهٔ جدید S335 (Reflex-TrendFlex Cycle-Turn)
// ----------------------------------------------------------------------------
// استراتژیِ *جدید* (User Note این نشست: «خودت با ترکیبِ اندیکاتورها یک استراتژیِ
// جدید بساز»). تنها لایه‌ای که هستهٔ سیگنالش از دستهٔ cycle/DSP اِهلرز می‌آید.
//
// منبعِ نظری: John F. Ehlers — "Reflex and TrendFlex Indicators" (S&C, Feb 2020)
//   • TrendFlex = جهت/قدرتِ روندِ کم‌تأخیر (صفرمحور) → «چه جهت».
//   • Reflex    = چرخهٔ کم‌تأخیر (صفرمحور)            → «چه زمان».
//
// منطقِ LONG (خریدِ کفِ چرخه درونِ روندِ صعودی):
//   گیت:    trendflex > tfMin  &  hurst > huMin  &  (r2 > r2Min)?  &  (chop < chopMax)?
//   تریگر:  zero_up  → reflex از زیرِ صفر به بالای صفر عبور کرد
//           dip_turn → reflex از کف (≤ -rfDip) رو به بالا برگشت
//   جهتِ سیگنال روی آخرین کندلِ بسته‌شده (i = n-1) ارزیابی می‌شود؛ بدون look-ahead.
//
// نتایجِ RQS+ (منبعِ حقیقتِ Python: strategies/s335_*.py — strategies/s335_results.txt):
//   XAUUSD M5  = ACCEPT RQS+ 91.2 (zero_up ; WR 64.9% · PF 2.62 · n 74)
//   XAUUSD M15 = ACCEPT RQS+ 89.7 (dip_turn; WR 60.0% · PF 2.08 · n 195)
//   XAUUSD H1  = ACCEPT RQS+ 93.1 (dip_turn; WR 61.9% · PF 1.97 · n 42)
//   (M30/H4 و EURUSDِ همهٔ TF = REJECT — زیستگاهِ لایه فقط روندِ طلاست.)
//   همپوشانیِ رویداد-محور با نزدیک‌ترین رقیبِ LONG (S333) = 0.0% → لایهٔ مستقل.
//
// همهٔ توابعِ اندیکاتور بیت‌به‌بیت از engine/indicator_bank.py پورت شده‌اند
// (الگوی مرجع: squeeze_s332.ts). برابریِ عددی با هارنسِ Python تأیید شده است.
// ============================================================================
import type { Candle } from './indicators'
import type { RouterDecision } from './router'
import type { RegimeInfo } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'

// ---------------------------------------------------------------------------
// اندیکاتورها — پورتِ verbatim از indicator_bank.py
// ---------------------------------------------------------------------------

/** Super Smoother (اِهلرز) — پورتِ _ssf_arr(xv, period). دقت: آرگومان همان مقداری است
 *  که در فرمولِ a می‌آید (در reflex/trendflex مقدارِ period/2 پاس می‌شود). */
export function ssfArr(x: number[], period: number): number[] {
  const n = x.length
  const out = new Array<number>(n).fill(0)
  const a = Math.exp(-1.414 * Math.PI / period)
  const b = 2 * a * Math.cos(1.414 * Math.PI / period)
  const c2 = b, c3 = -a * a, c1 = 1 - c2 - c3
  for (let i = 0; i < n; i++) {
    if (i < 2) out[i] = x[i]
    else out[i] = c1 * (x[i] + x[i - 1]) / 2 + c2 * out[i - 1] + c3 * out[i - 2]
  }
  return out
}

/** _flex(df, period, trend) — پایهٔ مشترکِ reflex/trendflex. ssf با period/2. */
function flexSeries(close: number[], period: number, trend: boolean): number[] {
  const n = close.length
  const ssf = ssfArr(close, period / 2)
  const out = new Array<number>(n).fill(0)
  let ms = 0
  for (let i = period; i < n; i++) {
    let s: number
    if (trend) {
      let sum = 0
      for (let k = 1; k <= period; k++) sum += ssf[i] - ssf[i - k]
      s = sum / period
    } else {
      const slope = (ssf[i - period] - ssf[i]) / period
      let sum = 0
      for (let k = 1; k <= period; k++) sum += ssf[i] + k * slope - ssf[i - k]
      s = sum / period
    }
    ms = 0.04 * s * s + 0.96 * ms
    out[i] = ms ? s / Math.sqrt(ms) : 0
  }
  return out
}

export function reflexSeries(close: number[], period = 20): number[] {
  return flexSeries(close, period, false)
}
export function trendflexSeries(close: number[], period = 20): number[] {
  return flexSeries(close, period, true)
}

/** R² رگرسیونِ خطی — پورتِ r2(df, p). پنجرهٔ x=0..p-1 (قدیم→جدید). */
export function r2Series(close: number[], period = 20): number[] {
  const n = close.length
  const out = new Array<number>(n).fill(NaN)
  let st = 0, stt = 0
  for (let t = 0; t < period; t++) { st += t; stt += t * t }
  for (let i = period - 1; i < n; i++) {
    let sy = 0, sxy = 0, syy = 0
    for (let t = 0; t < period; t++) {
      const y = close[i - (period - 1) + t]
      sy += y; sxy += t * y; syy += y * y
    }
    const num = period * sxy - st * sy
    const den = (period * stt - st * st) * (period * syy - sy * sy)
    const r = den > 0 ? num / Math.sqrt(den) : 0
    out[i] = r * r
  }
  return out
}

/** نمای هرست (R/S روی log-returns) — پورتِ hurst(df, p). پنجرهٔ مستقیم (قدیم→جدید). */
export function hurstSeries(close: number[], period = 64): number[] {
  const n = close.length
  const out = new Array<number>(n).fill(NaN)
  const ret = new Array<number>(n).fill(0)
  for (let i = 1; i < n; i++) ret[i] = close[i - 1] !== 0 ? Math.log(close[i] / close[i - 1]) : 0
  const logP = Math.log(period)
  for (let i = period; i < n; i++) {
    // w = ret[i-p+1 .. i]  (مستقیم، منطبق با numpy slice)
    let m = 0
    for (let k = 0; k < period; k++) m += ret[i - period + 1 + k]
    m /= period
    let cum = 0, mn = Infinity, mx = -Infinity, s2 = 0
    for (let k = 0; k < period; k++) {
      const dev = ret[i - period + 1 + k] - m
      cum += dev
      if (cum < mn) mn = cum
      if (cum > mx) mx = cum
      s2 += dev * dev
    }
    const sd = Math.sqrt(s2 / period), R = mx - mn
    out[i] = (sd && R > 0) ? Math.log(R / sd) / logP : 0.5
  }
  return out
}

/** Choppiness Index — پورتِ chop(df, p) با True Range. */
export function chopSeries(c: Candle[], period = 14): number[] {
  const n = c.length
  const out = new Array<number>(n).fill(NaN)
  const tr = new Array<number>(n).fill(NaN)
  for (let i = 0; i < n; i++) {
    const hl = c[i].high - c[i].low
    if (i === 0) { tr[i] = hl; continue }
    const pc = c[i - 1].close
    tr[i] = Math.max(hl, Math.abs(c[i].high - pc), Math.abs(c[i].low - pc))
  }
  const logP = Math.log10(period)
  for (let i = period - 1; i < n; i++) {
    let sumTr = 0
    let hh = -Infinity, ll = Infinity
    for (let k = 0; k < period; k++) {
      sumTr += tr[i - k]
      if (c[i - k].high > hh) hh = c[i - k].high
      if (c[i - k].low < ll) ll = c[i - k].low
    }
    const rng = hh - ll
    out[i] = rng > 0 ? 100 * Math.log10(sumTr / rng) / logP : NaN
  }
  return out
}

// ---------------------------------------------------------------------------
// پیکربندیِ هر کارت (per-TF، مقادیرِ غیررند از دلِ اسکنِ RQS+ — اشتباهِ #۶/#۷)
// ---------------------------------------------------------------------------
export type S335Trigger = 'zero_up' | 'dip_turn'

export interface S335Config {
  id: string
  tfFa: string
  trigger: S335Trigger
  pRf: number          // دورهٔ reflex
  pTf: number          // دورهٔ trendflex
  pHu: number          // دورهٔ hurst
  pR2: number          // دورهٔ r2
  pChop: number        // دورهٔ chop
  rfDip: number        // آستانهٔ کفِ reflex (فقط dip_turn)
  tfMin: number        // کفِ trendflex
  huMin: number        // کفِ hurst
  r2Min: number | null // کفِ r2 (اگر فعال)
  chopMax: number | null // سقفِ chop (اگر فعال)
  slPip: number        // فاصلهٔ SL بر حسبِ point (طلا: ×0.1 = دلار)
  tpPip: number
  maxHoldBars: number
}

// مقادیر دقیقاً منطبق با S335_FINAL در strategies/s335_overlap_audit.py و اسکنِ MTF
export const S335_CFG: Record<string, S335Config> = {
  'XAUUSD-M5': {
    id: 'XAUUSD-M5', tfFa: 'M5', trigger: 'zero_up',
    pRf: 21, pTf: 34, pHu: 55, pR2: 21, pChop: 21,
    rfDip: 1.0, tfMin: 0.2, huMin: 0.53, r2Min: null, chopMax: 38.2,
    slPip: 170, tpPip: 255, maxHoldBars: 60,
  },
  'XAUUSD-M15': {
    id: 'XAUUSD-M15', tfFa: 'M15', trigger: 'dip_turn',
    pRf: 21, pTf: 34, pHu: 55, pR2: 21, pChop: 21,
    rfDip: 1.0, tfMin: 0.5, huMin: 0.50, r2Min: 0.55, chopMax: null,
    slPip: 200, tpPip: 340, maxHoldBars: 64,
  },
  'XAUUSD-H1': {
    id: 'XAUUSD-H1', tfFa: 'H1', trigger: 'dip_turn',
    pRf: 21, pTf: 34, pHu: 55, pR2: 21, pChop: 21,
    rfDip: 1.0, tfMin: 0.5, huMin: 0.50, r2Min: null, chopMax: 38.2,
    slPip: 480, tpPip: 720, maxHoldBars: 40,
  },
}

// ---------------------------------------------------------------------------
// computeS335 — تصمیمِ خام روی آخرین کندلِ بسته‌شده
// ---------------------------------------------------------------------------
export function computeS335(candles: Candle[], cfg: S335Config): RawSignal {
  const need = Math.max(cfg.pHu, cfg.pTf, cfg.pR2, cfg.pChop) + 5
  const idle = (reason: string): RawSignal => ({
    active: false, approaching: false, direction: 'LONG',
    slDist: 0, tpDist: 0, maxHoldBars: cfg.maxHoldBars, reason,
    indicators: [],
  })
  if (candles.length < need) return idle('دادهٔ کافی برای محاسبهٔ اندیکاتورهای چرخه هنوز فراهم نیست.')

  const close = candles.map(c => c.close)
  const reflex = reflexSeries(close, cfg.pRf)
  const tflex = trendflexSeries(close, cfg.pTf)
  const hurst = hurstSeries(close, cfg.pHu)
  const r2 = cfg.r2Min != null ? r2Series(close, cfg.pR2) : null
  const chop = cfg.chopMax != null ? chopSeries(candles, cfg.pChop) : null

  const i = candles.length - 1
  const rNow = reflex[i], rPrev = reflex[i - 1]
  const tfNow = tflex[i], huNow = hurst[i]
  const r2Now = r2 ? r2[i] : NaN
  const chopNow = chop ? chop[i] : NaN

  // پیمایش/دلیلِ هر گیت برای نمایشِ چهار-حالته
  const tfOk = Number.isFinite(tfNow) && tfNow > cfg.tfMin
  const huOk = Number.isFinite(huNow) && huNow > cfg.huMin
  const r2Ok = cfg.r2Min == null ? true : (Number.isFinite(r2Now) && r2Now > cfg.r2Min)
  const chopOk = cfg.chopMax == null ? true : (Number.isFinite(chopNow) && chopNow < cfg.chopMax)
  const regimeOk = tfOk && huOk && r2Ok && chopOk

  let trigOk = false
  if (Number.isFinite(rNow) && Number.isFinite(rPrev)) {
    if (cfg.trigger === 'zero_up') trigOk = rPrev <= 0 && rNow > 0
    else trigOk = rPrev <= -cfg.rfDip && rNow > rPrev
  }

  const indicators: RouterDecision['indicators'] = [
    { name: 'TrendFlex (روند)', value: Number.isFinite(tfNow) ? tfNow.toFixed(2) : '—',
      status: tfOk ? 'ok' : 'bad' },
    { name: 'Hurst (حافظهٔ روند)', value: Number.isFinite(huNow) ? huNow.toFixed(2) : '—',
      status: huOk ? 'ok' : 'bad' },
    { name: 'Reflex (چرخه)', value: Number.isFinite(rNow) ? rNow.toFixed(2) : '—',
      status: trigOk ? 'ok' : 'neutral' },
  ]
  if (cfg.r2Min != null) indicators.push(
    { name: 'R² (خطی‌بودنِ روند)', value: Number.isFinite(r2Now) ? r2Now.toFixed(2) : '—',
      status: r2Ok ? 'ok' : 'bad' })
  if (cfg.chopMax != null) indicators.push(
    { name: 'Choppiness', value: Number.isFinite(chopNow) ? chopNow.toFixed(1) : '—',
      status: chopOk ? 'ok' : 'bad' })

  const slDist = cfg.slPip * 0.1
  const tpDist = cfg.tpPip * 0.1

  if (regimeOk && trigOk) {
    const trigTxt = cfg.trigger === 'zero_up'
      ? 'reflex از زیرِ صفر به بالای صفر عبور کرد (شروعِ فازِ صعودیِ چرخه)'
      : `reflex از کفِ چرخه (زیرِ ${(-cfg.rfDip).toFixed(1)}) رو به بالا برگشت`
    return {
      active: true, approaching: false, direction: 'LONG',
      slDist, tpDist, maxHoldBars: cfg.maxHoldBars,
      reason: `روندِ صعودیِ کم‌تأخیر برقرار است (TrendFlex=${tfNow.toFixed(2)}>0، ` +
        `Hurst=${huNow.toFixed(2)}) و ${trigTxt} ⇒ خریدِ کفِ چرخه.`,
      indicators,
    }
  }

  // APPROACHING: رژیم برقرار است اما هنوز تریگرِ چرخه نیامده
  if (regimeOk && !trigOk) {
    const wait = cfg.trigger === 'zero_up'
      ? 'منتظرِ عبورِ reflex از صفر به بالا (پایانِ فازِ نزولیِ چرخه) باشید.'
      : `منتظرِ برگشتِ reflex از کف (زیرِ ${(-cfg.rfDip).toFixed(1)}) رو به بالا باشید.`
    return {
      active: false, approaching: true, direction: 'LONG',
      slDist, tpDist, maxHoldBars: cfg.maxHoldBars,
      reason: `روندِ صعودیِ کم‌تأخیر برقرار است اما چرخهٔ کوتاه‌مدت هنوز کف نزده. ` +
        `Reflex فعلی=${Number.isFinite(rNow) ? rNow.toFixed(2) : '—'}.`,
      approachReason: wait,
      indicators,
    }
  }

  // NEUTRAL: رژیمِ روند برقرار نیست
  const bad: string[] = []
  if (!tfOk) bad.push('TrendFlex هنوز روندِ صعودی را تأیید نکرده')
  if (!huOk) bad.push('Hurst پایین است (بازارِ بازگشتی/نویزی)')
  if (!r2Ok) bad.push('R² پایین است (روندِ غیرخطی)')
  if (!chopOk) bad.push('Choppiness بالاست (بازارِ رنج)')
  return {
    active: false, approaching: false, direction: 'LONG',
    slDist, tpDist, maxHoldBars: cfg.maxHoldBars,
    reason: `ورود نمی‌گیرم چون: ${bad.join(' · ')}.`,
    indicators,
  }
}

// ---------------------------------------------------------------------------
// decideS335 — آداپترِ RouterDecision
// ---------------------------------------------------------------------------
export function decideS335(
  cfg: S335Config, a: { close: number } | any, candles: Candle[],
  capital: number, riskPct: number,
): RouterDecision {
  const raw = computeS335(candles, cfg)
  const price = candles.length ? candles[candles.length - 1].close : 0
  const reg: RegimeInfo = (a && a.regime) ? a.regime : { label: 'روندی', kind: 'trend' } as any
  const filters = [
    `TrendFlex>${cfg.tfMin}`, `Hurst>${cfg.huMin}`,
    ...(cfg.r2Min != null ? [`R²>${cfg.r2Min}`] : []),
    ...(cfg.chopMax != null ? [`Chop<${cfg.chopMax}`] : []),
    cfg.trigger === 'zero_up' ? 'Reflex zero-up' : `Reflex dip-turn(${cfg.rfDip})`,
  ]
  const meta: DecideMeta = {
    code: 'S335', name: 'چرخشِ چرخهٔ اِهلرز (Reflex-TrendFlex)', kind: 'trend' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote: 'TP/SL ثابتِ per-TF (غیررند). خروج با TP/TP یا سقفِ نگه‌داری.',
    filters,
  }
  return rawToDecision(raw, meta, cfg.id, price, reg, capital, riskPct)
}

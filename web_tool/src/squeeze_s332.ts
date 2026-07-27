// ============================================================================
// squeeze_s332.ts — لایهٔ احیاشدهٔ S332 (Bollinger Squeeze → Breakout)
// ----------------------------------------------------------------------------
// احیای لایهٔ سوختهٔ S132 روی XAUUSD در دو تایم‌فریم، با دو «فیلترِ رژیمِ» متفاوت:
//
//   • XAUUSD-H4  →  فیلترِ رژیمِ مومنتوم:  ADX(14) > 22  &  +DI > −DI
//                   TP=500 / SL=350 pip، maxHold=24 → RQS+ = 92.1  (WR 65.7٪، PF 1.99)
//
//   • XAUUSD-M15 →  فیلترِ آماری/فراکتالیِ بانک:  r2(20) > 0.58  &  hurst(64) > 0.55
//                   TP=285 / SL=190 pip، maxHold=64 → RQS+ = 91.2  (WR 60.4٪، PF 2.24)
//
// منبعِ کامل: results/S332_SqueezeBankFilters_Xauusd_H4M15_91.md
// کدِ منبعِ حقیقتِ Python: strategies/s332_squeeze_rqs_revival.py + bank_filters.py
//
// ماژولار/توسعه‌پذیر: این فایل کاملاً مستقل است؛ افزودنش به سایت فقط یک ورودی در
//   CARD_LAYERS (H4 و M15) می‌خواهد و هیچ لایهٔ دیگری را دست نمی‌زند.
//
// همپوشانی (ثبت‌شده): H4 با S313-H1 = ۳۴٪ هم‌روز (مکمل)؛ M15 با S225-M15 = ۹.۴٪ هم‌بار
//   (مکمل — هندسهٔ TP/SL معکوس). هیچ لایهٔ فعالِ دیگری این دو ترکیب را پوشش نمی‌دهد.
// ============================================================================

import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision } from './router'
import { bollinger, ema, adx } from './indicators'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'
import type { RegimeInfo } from './router'

const GOLD_PIP = 0.1

// ---------------------------------------------------------------------------
// فیلترهای آماری — پورتِ بیت‌به‌بیت از web_tool/src/indicators/bank/statistical.ts
//   (همان کدی که در strategies/bank_filters.py احیای M15 با آن یافت شد)
// ---------------------------------------------------------------------------

/** R² رگرسیونِ خطیِ قیمت روی زمان در پنجرهٔ `period` — «چقدر روند تمیز/خطی است». */
export function r2Series(close: number[], period = 20): number[] {
  const n = close.length
  const out = new Array(n).fill(NaN)
  for (let i = period - 1; i < n; i++) {
    let sx = 0, sy = 0, sxy = 0, sxx = 0, syy = 0
    for (let k = 0; k < period; k++) {
      const t = k, y = close[i - (period - 1 - k)]
      sx += t; sy += y; sxy += t * y; sxx += t * t; syy += y * y
    }
    const num = period * sxy - sx * sy
    const den = (period * sxx - sx * sx) * (period * syy - sy * sy)
    const r = den ? num / Math.sqrt(den) : 0
    out[i] = r * r
  }
  return out
}

/** نمای هرست (R/S) در پنجرهٔ `period` — >0.5 روندی/persistent، <0.5 بازگشتی. */
export function hurstSeries(close: number[], period = 64): number[] {
  const n = close.length
  const out = new Array(n).fill(0.5)
  const ret = new Array(n).fill(NaN)
  for (let i = 1; i < n; i++) ret[i] = close[i - 1] ? Math.log(close[i] / close[i - 1]) : 0
  const logP = Math.log(period)
  for (let i = period; i < n; i++) {
    const w: number[] = []
    for (let k = 0; k < period; k++) w.push(ret[i - k] || 0)
    const m = w.reduce((a, b) => a + b, 0) / period
    let cum = 0, mn = Infinity, mx = -Infinity, s2 = 0
    for (let k = 0; k < period; k++) { cum += w[k] - m; if (cum < mn) mn = cum; if (cum > mx) mx = cum; s2 += (w[k] - m) * (w[k] - m) }
    const sd = Math.sqrt(s2 / period), R = mx - mn
    out[i] = (sd && R > 0) ? Math.log(R / sd) / logP : 0.5
  }
  return out
}

// ---------------------------------------------------------------------------
// پیکربندیِ هر کارت (per-TF، مقادیرِ غیررند از دلِ اسکن — اشتباهِ رایج #۶/#۷)
// ---------------------------------------------------------------------------
export type S332FilterKind = 'adx_di' | 'r2_hurst'

export interface S332Config {
  id: string              // XAUUSD-H4 | XAUUSD-M15
  tfFa: string            // نامِ فارسیِ TF
  // پارامترهای squeeze
  bbPeriod: number        // 20
  bbMult: number          // 2.0
  sqzLookback: number     // 100
  sqzPct: number          // کفِ صدکِ فشردگی (0.25)
  breakoutLookback: number
  emaFast: number         // 50
  emaSlow: number         // 200
  // فیلترِ رژیم
  filterKind: S332FilterKind
  adxMin?: number         // برای adx_di
  r2Min?: number          // برای r2_hurst
  r2Period?: number
  hurstMin?: number
  hurstPeriod?: number
  // TP/SL/hold
  slPip: number
  tpPip: number
  maxHold: number
  rqs: number             // RQS+ ثبت‌شده (برای نمایش)
}

export const S332_CFG: Record<string, S332Config> = {
  // H4 — فیلترِ رژیمِ مومنتوم (ADX/DI)
  'XAUUSD-H4': {
    id: 'XAUUSD-H4', tfFa: 'H4',
    bbPeriod: 20, bbMult: 2.0, sqzLookback: 100, sqzPct: 0.25, breakoutLookback: 6,
    emaFast: 50, emaSlow: 200,
    filterKind: 'adx_di', adxMin: 22,
    slPip: 350, tpPip: 500, maxHold: 24, rqs: 92.1,
  },
  // M15 — فیلترِ آماری/فراکتالیِ بانک (r2 + hurst)
  'XAUUSD-M15': {
    id: 'XAUUSD-M15', tfFa: 'M15',
    bbPeriod: 20, bbMult: 2.0, sqzLookback: 100, sqzPct: 0.25, breakoutLookback: 6,
    emaFast: 50, emaSlow: 200,
    filterKind: 'r2_hurst', r2Min: 0.58, r2Period: 20, hurstMin: 0.55, hurstPeriod: 64,
    slPip: 190, tpPip: 285, maxHold: 64, rqs: 91.2,
  },
}

// ---------------------------------------------------------------------------
// ساختِ RawSignal روی آخرین کندلِ بسته‌شده — منطقِ verbatim از build_squeeze_signal
// ---------------------------------------------------------------------------
export function computeS332(candles: Candle[], cfg: S332Config): RawSignal {
  const n = candles.length
  const close = candles.map(c => c.close)
  const high = candles.map(c => c.high)

  const slDist = cfg.slPip * GOLD_PIP
  const tpDist = cfg.tpPip * GOLD_PIP

  const emptyInd: RouterDecision['indicators'] = [
    { name: 'داده', value: 'ناکافی', status: 'neutral' },
  ]
  const need = Math.max(cfg.bbPeriod + cfg.sqzLookback, cfg.emaSlow, cfg.breakoutLookback) + 2
  if (n < need) {
    return {
      active: false, approaching: false, direction: 'LONG',
      slDist, tpDist, maxHoldBars: cfg.maxHold,
      reason: 'دادهٔ کافی برای باندِ بولینگر / پنجرهٔ فشردگی موجود نیست.',
      indicators: emptyInd,
    }
  }

  // BandWidth بولینگر
  const bb = bollinger(close, cfg.bbPeriod, cfg.bbMult)
  const bw = new Array(n).fill(NaN)
  for (let i = 0; i < n; i++) {
    const mid = bb.mid[i]
    if (isFinite(mid) && mid !== 0 && isFinite(bb.upper[i]) && isFinite(bb.lower[i])) {
      bw[i] = (bb.upper[i] - bb.lower[i]) / mid
    }
  }
  const ef = ema(close, cfg.emaFast)
  const es = ema(close, cfg.emaSlow)

  const i = n - 1        // آخرین کندلِ بسته‌شده
  const prev = i - 1     // فشردگی «درست پیش از» کندلِ فعلی

  // صدکِ پهنای باندِ prev در پنجرهٔ sqzLookback (کف = فشرده)
  const lo = Math.max(0, prev - cfg.sqzLookback + 1)
  const window = bw.slice(lo, prev + 1).filter(v => isFinite(v))
  const bwPrev = bw[prev]
  let bwPct = 1
  if (window.length > 5 && isFinite(bwPrev)) {
    bwPct = window.filter(v => v <= bwPrev).length / window.length
  }
  const squeezed = isFinite(bwPrev) && bwPct <= cfg.sqzPct

  // سقفِ breakoutLookback کندلِ گذشته
  const bLo = Math.max(0, i - cfg.breakoutLookback)
  let priorHigh = -Infinity
  for (let k = bLo; k < i; k++) if (isFinite(high[k])) priorHigh = Math.max(priorHigh, high[k])
  const breakout = isFinite(close[i]) && close[i] > priorHigh

  const trendUp = isFinite(ef[i]) && isFinite(es[i]) && ef[i] > es[i]

  // --- فیلترِ رژیم (per-TF) ---
  let filterOk = false
  const regimeInd: RouterDecision['indicators'] = []
  let adxVal = NaN

  if (cfg.filterKind === 'adx_di') {
    const res = adx(candles, 14)
    adxVal = res.adx[i]
    const pdi = res.pdi[i], mdi = res.mdi[i]
    const adxOk = isFinite(adxVal) && adxVal > (cfg.adxMin ?? 22)
    const diOk = isFinite(pdi) && isFinite(mdi) && pdi > mdi
    filterOk = adxOk && diOk
    regimeInd.push(
      { name: `فیلترِ رژیم: ADX(14) > ${cfg.adxMin}`,
        value: isFinite(adxVal) ? adxVal.toFixed(1) + (adxOk ? ' ✔' : ' ✘') : '—',
        status: adxOk ? 'ok' : 'bad' },
      { name: '+DI > −DI (جهتِ صعودی)',
        value: (isFinite(pdi) && isFinite(mdi)) ? `${pdi.toFixed(0)} / ${mdi.toFixed(0)}` + (diOk ? ' ✔' : ' ✘') : '—',
        status: diOk ? 'ok' : 'bad' },
    )
  } else {
    // r2_hurst
    const r2 = r2Series(close, cfg.r2Period ?? 20)
    const hu = hurstSeries(close, cfg.hurstPeriod ?? 64)
    const r2v = r2[i], huv = hu[i]
    const r2Ok = isFinite(r2v) && r2v > (cfg.r2Min ?? 0.58)
    const huOk = isFinite(huv) && huv > (cfg.hurstMin ?? 0.55)
    filterOk = r2Ok && huOk
    regimeInd.push(
      { name: `فیلترِ آماری: R²(${cfg.r2Period}) > ${cfg.r2Min} (روندِ تمیز)`,
        value: isFinite(r2v) ? r2v.toFixed(2) + (r2Ok ? ' ✔' : ' ✘') : '—',
        status: r2Ok ? 'ok' : 'bad' },
      { name: `نمای هرست(${cfg.hurstPeriod}) > ${cfg.hurstMin} (حافظهٔ روندی)`,
        value: isFinite(huv) ? huv.toFixed(2) + (huOk ? ' ✔' : ' ✘') : '—',
        status: huOk ? 'ok' : 'bad' },
    )
  }

  const indicators: RouterDecision['indicators'] = [
    { name: `فنرِ فشرده (BandWidth در کفِ ${Math.round(cfg.sqzPct * 100)}٪)`,
      value: isFinite(bwPrev) ? `صدک ${Math.round(bwPct * 100)}` + (squeezed ? ' ✔' : ' ✘') : '—',
      status: squeezed ? 'ok' : 'neutral' },
    { name: `شکستِ صعودی (close > سقفِ ${cfg.breakoutLookback} کندل)`,
      value: breakout ? 'بله ✔' : 'خیر', status: breakout ? 'ok' : 'neutral' },
    { name: 'گیتِ روند (EMA50 > EMA200)',
      value: trendUp ? 'صعودی ✔' : 'غیرصعودی ✘', status: trendUp ? 'ok' : 'bad' },
    ...regimeInd,
  ]

  // ماشهٔ ورود: فشردگی + شکست + روند + فیلترِ رژیم
  const active = squeezed && breakout && trendUp && filterOk
  // approaching: فنر فشرده و روند صعودی و فیلترِ رژیم برقرار، ولی هنوز شکست کامل نشده
  const approaching = !active && squeezed && trendUp && filterOk && !breakout

  const filterFa = cfg.filterKind === 'adx_di'
    ? `ADX>${cfg.adxMin} و +DI>−DI`
    : `R²>${cfg.r2Min} و هرست>${cfg.hurstMin}`

  let reason: string
  if (active) {
    reason = `فنرِ فشردهٔ بولینگر با شکستِ صعودی رها شد و فیلترِ رژیم (${filterFa}) تأیید کرد ⇒ ورودِ خرید.`
  } else if (approaching) {
    reason = `فنر فشرده و رژیم مساعد است (${filterFa})، اما هنوز کندلِ شکست بالای سقفِ ${cfg.breakoutLookback}‌کندلی بسته نشده.`
  } else if (!squeezed) {
    reason = 'باندِ بولینگر هنوز به‌قدرِ کافی فشرده نیست (فنر آمادهٔ انفجار نیست).'
  } else if (!trendUp) {
    reason = 'گیتِ روند برقرار نیست (EMA50 ≤ EMA200) — انفجار هم‌سو با روندِ صعودی نیست.'
  } else if (!filterOk) {
    reason = `فیلترِ رژیم (${filterFa}) هنوز تأیید نمی‌کند — کیفیتِ روند کافی نیست.`
  } else {
    reason = 'شرایطِ ورود کامل نیست.'
  }

  return {
    active, approaching, direction: 'LONG',
    slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason,
    approachReason: approaching
      ? `منتظرِ بسته‌شدنِ کندلِ شکست بالای سقفِ ${cfg.breakoutLookback}‌کندلی` : undefined,
    indicators,
  }
}

// ---------------------------------------------------------------------------
// decideS332 — RawSignal → RouterDecision (منطقِ ورود/حجم/مدیریتِ مشترک)
// ---------------------------------------------------------------------------
export function decideS332(
  cfg: S332Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS332(candles, cfg)
  const price = a.price

  const filterFa = cfg.filterKind === 'adx_di'
    ? 'فیلترِ رژیمِ روند (ADX/DI)'
    : 'فیلترِ آماری/فراکتالی (R² + هرست)'

  const reg: RegimeInfo = {
    regime: 'trend_up', efficiencyRatio: 0, trendy: true,
    adx: 0, activeStream: 'bull', bucket: `s332_${cfg.tfFa.toLowerCase()}`,
  }

  const meta: DecideMeta = {
    code: 'S332',
    name: `انفجارِ فشردگیِ بولینگر (${cfg.tfFa})`,
    kind: 'squeeze' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote: `هدف/حدِ ثابتِ مخصوصِ ${cfg.tfFa} (${cfg.tpPip}/${cfg.slPip} pip). ` +
      `تا برخورد به TP/SL یا پایانِ ${cfg.maxHold} کندل نگه‌دار؛ اگر ${filterFa} معکوس شد، خروجِ زودهنگام را بسنج.`,
    filters: [
      'فنرِ فشرده (BandWidth کف صدک ۲۵٪)',
      `شکستِ صعودی (سقفِ ${cfg.breakoutLookback} کندل)`,
      'گیتِ روند EMA50>EMA200',
      filterFa,
    ],
  }

  return rawToDecision(raw, meta, cfg.id, price, reg, capital, riskPct)
}

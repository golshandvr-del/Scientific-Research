// ============================================================================
// swing_fade_s341.ts — لایهٔ نوِ/احیاشدهٔ S341 (Al Brooks «Horizontal Lines:
//   Swing Points» — فصلِ ۱۷) روی XAUUSD-H1 (LONG).
// ----------------------------------------------------------------------------
// داستان: نسخهٔ خامِ swing-fade روی H1 «سوخته» بود (RQS+=۳۳، WR=۵۶٪ ⇒ رد روی کفِ WR<۶۰٪).
// طبق «قانونِ جعبه‌ابزار»، Brooks در همین فصل می‌گوید «the middle acts like a magnet»:
// fade فقط وقتی می‌ارزد که قیمت از میانگین «کشیده» شده باشد. نگاشتِ مکانیکی = ema_dist_atr.
// افزودنِ تنها یک فیلترِ کشش (ema_dist_atr ≤ −0.7) + خستگی (ifish_rsi ≤ −0.25):
//   RQS+ = 33 → 94.5 · WR 56٪ → 66.7٪ · PF 2.01 · DD 1.5٪ · MCL 2 · net +$387 · n=42
//
// منطق (verbatim از strategies/s341_swing_fade_h1_revived.py؛ سیگنال روی i=n-1، ورود در i+1):
//   رژیمِ رنج (اجباری): chop(14) ≥ 61.8 · r2(20) ≤ 0.22 · |Kaufman-ER(11)| ≤ 0.16
//   failed breakout زیرِ swing low(w=4): low[i] < swingLow − 0.05·ATR  و  close[i] > swingLow
//   فیلترِ کششِ مغناطیسی: ema_dist_atr(ema50,atr14)[i] ≤ −0.7
//   فیلترِ خستگی:        ifish_rsi(14)[i] ≤ −0.25
//
// همپوشانی (ثبت‌شده، ممیزیِ اجباری): با S333 = ۰٪ و با S335 = ۰٪ — چون S341 فقط در رژیمِ
//   رنج (chop≥61.8) شلیک می‌کند و همهٔ لایه‌های LONGِ H1 در رژیمِ روند (chop<38.2) ⇒ لبهٔ
//   کاملاً متعامد که شکافِ «روزهای رنج» را پُر می‌کند (نه فیلتر، بلکه edgeِ مستقل).
// منبعِ کامل: results/S341_SwingFadeMagnet_Xauusd_H1_rqs94.md
// ماژولار: فایلِ مستقل؛ افزودنش فقط یک ورودی در CARD_LAYERS['XAUUSD-H1'] می‌خواهد.
// ============================================================================

import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision } from './router'
import { ema, atr } from './indicators'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'
import type { RegimeInfo } from './router'

const GOLD_PIP = 0.1

// ---------------------------------------------------------------------------
export interface S341Config {
  id: string            // XAUUSD-H1
  tfFa: string
  w: number             // 4 — نیم‌پنجرهٔ فراکتال
  bufFrac: number       // 0.05 — بافرِ ATR برای «واقعا زیرِ سطح رفته»
  stretch: number       // 0.7 — |ema_dist_atr| حداقل (کششِ مغناطیسی)
  exh: number           // 0.25 — |ifish_rsi| حداقل (خستگی)
  chopMin: number       // 61.8
  r2Max: number         // 0.22
  erMax: number         // 0.16
  erP: number           // 11 (Kaufman ER lucas)
  slPip: number         // 520
  tpPip: number         // 1550
  maxHold: number       // 16
  rqs: number
}

export const S341_CFG: Record<string, S341Config> = {
  'XAUUSD-H1': {
    id: 'XAUUSD-H1', tfFa: 'H1',
    w: 4, bufFrac: 0.05, stretch: 0.7, exh: 0.25,
    chopMin: 61.8, r2Max: 0.22, erMax: 0.16, erP: 11,
    slPip: 520, tpPip: 1550, maxHold: 16, rqs: 94.5,
  },
}

// ---------------------------------------------------------------------------
// پورتِ verbatim اندیکاتورهای engine/indicator_bank.py
// ---------------------------------------------------------------------------
function trueRange(h: number[], l: number[], c: number[]): number[] {
  const n = h.length
  const tr = new Array(n).fill(NaN)
  for (let i = 0; i < n; i++) {
    if (i === 0) { tr[i] = h[i] - l[i]; continue }
    const a = h[i] - l[i]
    const b = Math.abs(h[i] - c[i - 1])
    const d = Math.abs(l[i] - c[i - 1])
    tr[i] = Math.max(a, b, d)
  }
  return tr
}

// chop(p): 100*log10(sum_p TR / (maxHigh_p − minLow_p)) / log10(p)
function chopArr(h: number[], l: number[], c: number[], p: number): number[] {
  const n = h.length
  const tr = trueRange(h, l, c)
  const out = new Array(n).fill(NaN)
  for (let i = p - 1; i < n; i++) {
    let sumTr = 0
    let hh = -Infinity, ll = Infinity
    for (let k = i - p + 1; k <= i; k++) {
      sumTr += tr[k]
      if (h[k] > hh) hh = h[k]
      if (l[k] < ll) ll = l[k]
    }
    const rng = hh - ll
    if (rng > 0 && sumTr > 0) out[i] = 100 * Math.log10(sumTr / rng) / Math.log10(p)
  }
  return out
}

// r2(p): R² رگرسیونِ خطیِ close روی زمان در پنجرهٔ p (raw، مطابقِ engine)
function r2Arr(c: number[], p: number): number[] {
  const n = c.length
  const out = new Array(n).fill(NaN)
  const t: number[] = []
  for (let k = 0; k < p; k++) t.push(k)
  const st = t.reduce((a, b) => a + b, 0)
  const stt = t.reduce((a, b) => a + b * b, 0)
  for (let i = p - 1; i < n; i++) {
    let sy = 0, sxy = 0, syy = 0
    for (let k = 0; k < p; k++) {
      const w = c[i - p + 1 + k]
      sy += w; sxy += t[k] * w; syy += w * w
    }
    const num = p * sxy - st * sy
    const den = (p * stt - st * st) * (p * syy - sy * sy)
    const r = den > 0 ? num / Math.sqrt(den) : 0
    out[i] = r * r
  }
  return out
}

// Kaufman Efficiency Ratio(p): |x[i]-x[i-p]| / sum(|x[k]-x[k-1]|)
function erArr(c: number[], p: number): number[] {
  const n = c.length
  const out = new Array(n).fill(NaN)
  for (let i = p; i < n; i++) {
    const ch = Math.abs(c[i] - c[i - p])
    let v = 0
    for (let k = 0; k < p; k++) v += Math.abs(c[i - k] - c[i - k - 1])
    out[i] = v ? ch / v : 0
  }
  return out
}

// Wilder RMA == ewm(alpha=1/p)  (برای ATR مطابقِ engine.rma_s)
function rma(x: number[], p: number): number[] {
  const n = x.length
  const out = new Array(n).fill(NaN)
  const a = 1 / p
  let prev = NaN
  for (let i = 0; i < n; i++) {
    if (!isFinite(x[i])) { out[i] = prev; continue }
    prev = isFinite(prev) ? prev + a * (x[i] - prev) : x[i]
    out[i] = prev
  }
  return out
}

// ema_dist_atr(ema50, atr14): (close − EMA50) / RMA(TR,14)
function emaDistAtr(h: number[], l: number[], c: number[], emaP: number, atrP: number): number[] {
  const n = c.length
  const e = ema(c, emaP)
  const a = rma(trueRange(h, l, c), atrP)
  const out = new Array(n).fill(NaN)
  for (let i = 0; i < n; i++) {
    if (isFinite(e[i]) && isFinite(a[i]) && a[i] !== 0) out[i] = (c[i] - e[i]) / a[i]
  }
  return out
}

// RSI مطابقِ engine.rsi_s (Wilder ewm alpha=1/p) — چون ifish روی همین بنا شده
function rsiWilder(c: number[], p: number): number[] {
  const n = c.length
  const out = new Array(n).fill(NaN)
  const a = 1 / p
  let ag = NaN, al = NaN
  for (let i = 1; i < n; i++) {
    const d = c[i] - c[i - 1]
    const g = d > 0 ? d : 0
    const ls = d < 0 ? -d : 0
    ag = isFinite(ag) ? ag + a * (g - ag) : g
    al = isFinite(al) ? al + a * (ls - al) : ls
    const rs = al !== 0 ? ag / al : NaN
    out[i] = isFinite(rs) ? 100 - 100 / (1 + rs) : (al === 0 ? 100 : NaN)
  }
  return out
}

// ifish_rsi(14): InverseFisher(0.1*(RSI-50))
function ifishRsi(c: number[], p: number): number[] {
  const r = rsiWilder(c, p)
  const n = c.length
  const out = new Array(n).fill(NaN)
  for (let i = 0; i < n; i++) {
    if (!isFinite(r[i])) continue
    const v = 0.1 * (r[i] - 50)
    const e2 = Math.exp(2 * v)
    out[i] = (e2 - 1) / (e2 + 1)
  }
  return out
}

// آخرین swing-low که کاملاً در گذشته تأیید شده (بدونِ look-ahead)، مطابقِ _fractal_levels
function lastSwingLow(h: number[], l: number[], w: number): number[] {
  const n = l.length
  const out = new Array(n).fill(NaN)
  let curSl = NaN
  for (let i = 0; i < n; i++) {
    const pp = i - w
    if (pp - w >= 0) {
      const lp = l[pp]
      let leftMin = Infinity, rightMin = Infinity
      for (let k = pp - w; k < pp; k++) if (l[k] < leftMin) leftMin = l[k]
      for (let k = pp + 1; k <= pp + w; k++) if (l[k] < rightMin) rightMin = l[k]
      if (lp < leftMin && lp < rightMin) curSl = lp
    }
    out[i] = curSl
  }
  return out
}

// ---------------------------------------------------------------------------
// computeS341 — منطقِ verbatim روی آخرین کندلِ بستهٔ i=n-1
// ---------------------------------------------------------------------------
export function computeS341(candles: Candle[], cfg: S341Config): RawSignal {
  const n = candles.length
  const h = candles.map(c => c.high)
  const l = candles.map(c => c.low)
  const c = candles.map(x => x.close)

  const slDist = cfg.slPip * GOLD_PIP
  const tpDist = cfg.tpPip * GOLD_PIP
  const emptyInd: RouterDecision['indicators'] = [
    { name: 'داده', value: 'ناکافی', status: 'neutral' },
  ]
  const need = Math.max(60, cfg.w * 2 + 3, cfg.erP + 2)
  if (n < need) {
    return {
      active: false, approaching: false, direction: 'LONG',
      slDist, tpDist, maxHoldBars: cfg.maxHold,
      reason: 'دادهٔ کافی برای تشخیصِ سطحِ سوئینگ/رژیم موجود نیست.',
      indicators: emptyInd,
    }
  }

  const ch = chopArr(h, l, c, 14)
  const r2 = r2Arr(c, 20)
  const er = erArr(c, cfg.erP)
  const atrArr = atr(candles, 14)
  const edist = emaDistAtr(h, l, c, 50, 14)
  const ifr = ifishRsi(c, 14)
  const slArr = lastSwingLow(h, l, cfg.w)

  const i = n - 1

  const chOk = isFinite(ch[i]) && ch[i] >= cfg.chopMin
  const r2Ok = isFinite(r2[i]) && r2[i] <= cfg.r2Max
  const erOk = isFinite(er[i]) && Math.abs(er[i]) <= cfg.erMax
  const rangeOk = chOk && r2Ok && erOk

  const a = atrArr[i]
  const lvl = slArr[i]
  const buf = (isFinite(a) ? a : 0) * cfg.bufFrac
  const brokeBelow = isFinite(lvl) && (l[i] < lvl - buf)
  const closedBack = isFinite(lvl) && (c[i] > lvl)
  const failedBreak = brokeBelow && closedBack

  const stretchOk = isFinite(edist[i]) && edist[i] <= -cfg.stretch
  const exhOk = isFinite(ifr[i]) && ifr[i] <= -cfg.exh

  const active = rangeOk && failedBreak && stretchOk && exhOk
  // approaching: رژیمِ رنج برقرار و قیمت کشیده/خسته هست، اما failed-breakout هنوز رخ نداده
  const approaching = !active && rangeOk && stretchOk && !failedBreak && isFinite(lvl)

  const fmt = (x: number) => (isFinite(x) ? x.toFixed(2) : '—')
  const indicators: RouterDecision['indicators'] = [
    { name: `رژیمِ رنج (Chop14 ≥ ${cfg.chopMin})`,
      value: `${fmt(ch[i])}` + (chOk ? ' ✔' : ' ✘'), status: chOk ? 'ok' : 'bad' },
    { name: `بی‌روندی (R²20 ≤ ${cfg.r2Max})`,
      value: `${fmt(r2[i])}` + (r2Ok ? ' ✔' : ' ✘'), status: r2Ok ? 'ok' : 'bad' },
    { name: `کاراییِ پایین (|ER${cfg.erP}| ≤ ${cfg.erMax})`,
      value: `${fmt(Math.abs(er[i]))}` + (erOk ? ' ✔' : ' ✘'), status: erOk ? 'ok' : 'bad' },
    { name: `کششِ مغناطیسی (ema_dist_atr ≤ −${cfg.stretch})`,
      value: `${fmt(edist[i])}` + (stretchOk ? ' ✔' : ' ✘'), status: stretchOk ? 'ok' : 'neutral' },
    { name: `خستگیِ فروش (ifish_rsi ≤ −${cfg.exh})`,
      value: `${fmt(ifr[i])}` + (exhOk ? ' ✔' : ' ✘'), status: exhOk ? 'ok' : 'neutral' },
    { name: 'شکستِ ناموفقِ زیرِ کفِ سوئینگ',
      value: isFinite(lvl) ? (failedBreak ? 'رخ داد ✔' : 'نه') : 'کفِ سوئینگ نامشخص',
      status: failedBreak ? 'ok' : 'neutral' },
  ]

  let reason: string
  if (active) {
    reason = `روزِ رنج (Chop=${fmt(ch[i])})؛ قیمت زیرِ کفِ سوئینگ شکست اما ناموفق ماند و به بالای سطح برگشت، ` +
      `درحالی‌که از میانگین کشیده (${fmt(edist[i])} ATR) و فروش خسته است ⇒ ورودِ fadeِ خرید به سمتِ میانه (مغناطیس).`
  } else if (approaching) {
    reason = `رژیمِ رنج و کششِ پایین از میانگین برقرار است؛ منتظرِ یک «شکستِ ناموفق» زیرِ کفِ سوئینگ ` +
      `(بسته‌شدنِ دوباره بالای سطح) برای ورودِ fade.`
  } else if (!rangeOk) {
    reason = `رژیمِ رنجِ لازم برقرار نیست (Chop=${fmt(ch[i])}، R²=${fmt(r2[i])}، |ER|=${fmt(Math.abs(er[i]))}) — ` +
      `این لایه فقط در روزهای رنج fade می‌کند، در روند خیر.`
  } else if (!stretchOk) {
    reason = `قیمت هنوز به‌قدرِ کافی از میانگین دور نشده (${fmt(edist[i])})؛ «مغناطیسِ میانه» ضعیف است.`
  } else {
    reason = 'شرایطِ رنج/کشش هست اما شکستِ ناموفقِ معتبری زیرِ کفِ سوئینگ ثبت نشده است.'
  }

  return {
    active, approaching, direction: 'LONG',
    slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason,
    approachReason: approaching
      ? 'منتظرِ شکستِ ناموفق زیرِ کفِ سوئینگ (بازگشتِ close بالای سطح)' : undefined,
    indicators,
  }
}

// ---------------------------------------------------------------------------
export function decideS341(
  cfg: S341Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS341(candles, cfg)
  const price = a.price

  const reg: RegimeInfo = {
    regime: 'range', efficiencyRatio: 0, trendy: false,
    adx: 0, activeStream: 'range', bucket: `s341_${cfg.tfFa.toLowerCase()}`,
  }

  const meta: DecideMeta = {
    code: 'S341',
    name: `fadeِ سطحِ سوئینگ در رنج (Brooks Swing-Points · ${cfg.tfFa})`,
    kind: 'swing_fade' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote: `هدف/حدِ ثابتِ مخصوصِ ${cfg.tfFa} (${cfg.tpPip}/${cfg.slPip} pip، TP به سمتِ میانهٔ رنج). ` +
      `تا برخورد به TP/SL یا پایانِ ${cfg.maxHold} کندل نگه‌دار؛ اگر رژیم از رنج به روندِ نزولیِ قوی ` +
      `تغییر کرد (Chop افت کرد / کندلِ نزولیِ قوی زیرِ کفِ شکست بست)، خروجِ زودهنگام را بسنج.`,
    filters: [
      `رژیمِ رنج (Chop14≥${cfg.chopMin} · R²20≤${cfg.r2Max} · |ER${cfg.erP}|≤${cfg.erMax})`,
      'شکستِ ناموفقِ زیرِ کفِ سوئینگ (failed breakout)',
      `کششِ مغناطیسی ema_dist_atr ≤ −${cfg.stretch}`,
      `خستگیِ فروش ifish_rsi ≤ −${cfg.exh}`,
    ],
  }

  return rawToDecision(raw, meta, cfg.id, price, reg, capital, riskPct)
}

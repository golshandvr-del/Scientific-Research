// ============================================================================
// indicators/bank/structure.ts — دستهٔ روند-دنبال‌کن/ساختاری (Trend-following / Structure)
// ----------------------------------------------------------------------------
// منابع: EN/RU/deep-web. اندیکاتورهای ساختاریِ پرکاربرد (Supertrend/PSAR/Aroon/
// Vortex/Donchian/QQE/STC/ConnorsRSI/Waddah/ElderImpulse/Chandelier/GannHiLo/TDI).
// منطق کاملاً verbatim از bank.ts؛ بدونِ look-ahead و active:false.
// ============================================================================

import * as I from '../../indicators'
import { makeKit, closes, highs, lows, emaArr, smaArr, rmaArr, stdArr, trArr, NaNArr, asSeries, highest, lowest } from './kit'

const K = makeKit()
const { def } = K

// Supertrend (ATR-based) — خطِ روند؛ خروجی = مقدارِ خطِ سوپرترند (الگوریتمِ استاندارد)
def('supertrend', 'trend', 'deep-web', { period: 10, mult: 3 }, ['period', 'mult'], 'سوپرترند (ATR-محور)', (c, p) => {
  const n = c.length, atr = rmaArr(trArr(c), p.period), out = NaNArr(n)
  let finalUp = NaN, finalDn = NaN, dir = 1, started = false
  for (let i = 0; i < n; i++) {
    if (!Number.isFinite(atr[i])) continue
    const mid = (c[i].high + c[i].low) / 2
    const basicUp = mid - p.mult * atr[i]   // باندِ پایین (خطِ حمایتِ روندِ صعودی)
    const basicDn = mid + p.mult * atr[i]   // باندِ بالا (خطِ مقاومتِ روندِ نزولی)
    if (!started) { finalUp = basicUp; finalDn = basicDn; dir = 1; out[i] = finalUp; started = true; continue }
    // بازآراییِ باندهای نهایی (فرمولِ کلاسیکِ سوپرترند)
    finalUp = (basicUp > finalUp || c[i - 1].close < finalUp) ? basicUp : finalUp
    finalDn = (basicDn < finalDn || c[i - 1].close > finalDn) ? basicDn : finalDn
    // تعیینِ جهت بر اساسِ شکستِ خطِ فعلی
    if (dir === 1 && c[i].close < finalUp) dir = -1
    else if (dir === -1 && c[i].close > finalDn) dir = 1
    out[i] = dir === 1 ? finalUp : finalDn
  }
  return asSeries(out)
})

// Parabolic SAR
def('psar', 'trend', 'EN', { step: 0.02, max: 0.2 }, ['step', 'max'], 'سارِ سهموی', (c, p) => {
  const n = c.length, out = NaNArr(n)
  if (n < 2) return asSeries(out)
  let bull = c[1].close >= c[0].close
  let af = p.step, ep = bull ? c[0].high : c[0].low, sar = bull ? c[0].low : c[0].high
  for (let i = 1; i < n; i++) {
    sar = sar + af * (ep - sar)
    if (bull) {
      if (c[i].low < sar) { bull = false; sar = ep; ep = c[i].low; af = p.step }
      else { if (c[i].high > ep) { ep = c[i].high; af = Math.min(p.max, af + p.step) } }
    } else {
      if (c[i].high > sar) { bull = true; sar = ep; ep = c[i].high; af = p.step }
      else { if (c[i].low < ep) { ep = c[i].low; af = Math.min(p.max, af + p.step) } }
    }
    out[i] = sar
  }
  return asSeries(out)
})

// Aroon Oscillator = AroonUp − AroonDown
def('aroon', 'trend', 'EN', { period: 25 }, ['period'], 'اسیلاتورِ آرون', (c, p) => {
  const h = highs(c), l = lows(c), n = c.length, out = NaNArr(n)
  for (let i = p.period; i < n; i++) {
    let hi = 0, li = 0, hv = -Infinity, lv = Infinity
    for (let k = 0; k <= p.period; k++) { if (h[i - k] > hv) { hv = h[i - k]; hi = k } if (l[i - k] < lv) { lv = l[i - k]; li = k } }
    const up = (100 * (p.period - hi)) / p.period, dn = (100 * (p.period - li)) / p.period
    out[i] = up - dn
  }
  return asSeries(out)
})

// Vortex Indicator (VI+ − VI−)
def('vortex', 'trend', 'EN', { period: 14 }, ['period'], 'اندیکاتورِ گردابی (ورتکس)', (c, p) => {
  const n = c.length, vmP = NaNArr(n), vmN = NaNArr(n), tr = trArr(c)
  for (let i = 1; i < n; i++) { vmP[i] = Math.abs(c[i].high - c[i - 1].low); vmN[i] = Math.abs(c[i].low - c[i - 1].high) }
  const out = NaNArr(n)
  for (let i = p.period; i < n; i++) {
    let sp = 0, sn = 0, st = 0
    for (let k = 0; k < p.period; k++) { sp += vmP[i - k] || 0; sn += vmN[i - k] || 0; st += tr[i - k] || 0 }
    out[i] = st ? (sp - sn) / st : 0
  }
  return asSeries(out)
})

// Donchian channel midline
def('donchian_mid', 'trend', 'EN', { period: 20 }, ['period'], 'خطِ میانیِ کانالِ دونچیان', (c, p) => {
  const h = highs(c), l = lows(c), n = c.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) out[i] = (highest(h, i, p.period) + lowest(l, i, p.period)) / 2
  return asSeries(out)
})

// QQE — Quantitative Qualitative Estimation (RSI هموار + باندِ ATR-RSI)
def('qqe', 'momentum', 'RU', { rsiP: 14, sf: 5 }, ['rsiP', 'sf'], 'برآوردِ کمی-کیفی (QQE)', (c, p) => {
  const rsi = I.rsi(closes(c), p.rsiP) as unknown as number[]
  return asSeries(emaArr(rsi, p.sf))
})

// Schaff Trend Cycle (STC)
def('stc', 'momentum', 'EN', { fast: 23, slow: 50, cycle: 10 }, ['fast', 'slow', 'cycle'], 'چرخهٔ روندِ شاف (STC)', (c, p) => {
  const x = closes(c), n = x.length
  const macd = emaArr(x, p.fast).map((v, i) => v - emaArr(x, p.slow)[i])
  const stoch1 = NaNArr(n)
  for (let i = p.cycle - 1; i < n; i++) { const hh = highest(macd, i, p.cycle), ll = lowest(macd, i, p.cycle); stoch1[i] = (hh - ll) ? (100 * (macd[i] - ll)) / (hh - ll) : 50 }
  const d1 = emaArr(stoch1, Math.max(2, Math.floor(p.cycle / 2)))
  const stoch2 = NaNArr(n)
  for (let i = p.cycle - 1; i < n; i++) { const hh = highest(d1, i, p.cycle), ll = lowest(d1, i, p.cycle); stoch2[i] = (hh - ll) ? (100 * (d1[i] - ll)) / (hh - ll) : 50 }
  return asSeries(emaArr(stoch2, Math.max(2, Math.floor(p.cycle / 2))))
})

// Connors RSI = (RSI3 + streakRSI + PctRank)/3
def('crsi', 'momentum', 'deep-web', { rsiP: 3, streakP: 2, rankP: 100 }, ['rsiP', 'streakP', 'rankP'], 'کانرزِ RSI', (c, p) => {
  const x = closes(c), n = x.length
  const rsi = I.rsi(x, p.rsiP) as unknown as number[]
  const streak = NaNArr(n); let s = 0
  for (let i = 1; i < n; i++) { if (x[i] > x[i - 1]) s = s >= 0 ? s + 1 : 1; else if (x[i] < x[i - 1]) s = s <= 0 ? s - 1 : -1; else s = 0; streak[i] = s }
  const streakRsi = I.rsi(streak.map(v => (Number.isFinite(v) ? v : 0)), p.streakP) as unknown as number[]
  const ret = NaNArr(n); for (let i = 1; i < n; i++) ret[i] = x[i - 1] ? (x[i] - x[i - 1]) / x[i - 1] : 0
  const rank = NaNArr(n)
  for (let i = p.rankP; i < n; i++) { let below = 0; for (let k = 1; k <= p.rankP; k++) if (ret[i - k] < ret[i]) below++; rank[i] = (100 * below) / p.rankP }
  const out = NaNArr(n)
  for (let i = 0; i < n; i++) if (Number.isFinite(rsi[i]) && Number.isFinite(streakRsi[i]) && Number.isFinite(rank[i])) out[i] = (rsi[i] + streakRsi[i] + rank[i]) / 3
  return asSeries(out)
})

// Waddah Attar Explosion (MACD-diff × BB-width)
def('waddah', 'momentum', 'RU', { fast: 20, slow: 40, bbP: 20, bbM: 2 }, ['fast', 'slow', 'bbP', 'bbM'], 'انفجارِ وداح‌عطار', (c, p) => {
  const x = closes(c), n = x.length
  const macd = emaArr(x, p.fast).map((v, i) => v - emaArr(x, p.slow)[i])
  const sd = stdArr(x, p.bbP), sma = smaArr(x, p.bbP)
  const out = NaNArr(n)
  for (let i = 1; i < n; i++) {
    const t = (macd[i] - macd[i - 1]) * 150
    const bbw = 2 * p.bbM * sd[i]
    out[i] = Number.isFinite(t) && Number.isFinite(bbw) ? t : NaN
    void sma
  }
  return asSeries(out)
})

// Elder Impulse (EMA-slope sign × MACD-hist sign) → {−1,0,+1}
def('elder_impulse', 'composite', 'EN', { emaP: 13, macdF: 12, macdS: 26, macdSig: 9 }, ['emaP', 'macdF', 'macdS', 'macdSig'], 'سیستمِ ضربهٔ الدر', (c, p) => {
  const x = closes(c), n = x.length
  const e = emaArr(x, p.emaP)
  const macd = emaArr(x, p.macdF).map((v, i) => v - emaArr(x, p.macdS)[i])
  const sig = emaArr(macd, p.macdSig)
  const hist = macd.map((v, i) => v - sig[i])
  const out = NaNArr(n)
  for (let i = 1; i < n; i++) {
    const es = Math.sign(e[i] - e[i - 1]), hs = Math.sign(hist[i] - hist[i - 1])
    out[i] = (es > 0 && hs > 0) ? 1 : (es < 0 && hs < 0) ? -1 : 0
  }
  return asSeries(out)
})

// Chandelier Exit (long) — ATR trailing از بالاترین سقف
def('chandelier', 'trend', 'EN', { period: 22, mult: 3 }, ['period', 'mult'], 'خروجِ شمعدانی (ترِیلینگ)', (c, p) => {
  const h = highs(c), atr = rmaArr(trArr(c), p.period), n = c.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) out[i] = highest(h, i, p.period) - p.mult * atr[i]
  return asSeries(out)
})

// Gann HiLo Activator
def('gann_hilo', 'trend', 'RU', { period: 10 }, ['period'], 'فعال‌سازِ گانِ های‌لو', (c, p) => {
  const h = highs(c), l = lows(c), n = c.length, out = NaNArr(n)
  const sh = smaArr(h, p.period), sl = smaArr(l, p.period)
  let dir = 1
  for (let i = p.period; i < n; i++) {
    if (c[i].close > sh[i - 1]) dir = 1; else if (c[i].close < sl[i - 1]) dir = -1
    out[i] = dir === 1 ? sl[i] : sh[i]
  }
  return asSeries(out)
})

// TDI — Traders Dynamic Index (RSI هموارشده؛ خطِ سیگنال)
def('tdi', 'momentum', 'RU', { rsiP: 13, sig: 7 }, ['rsiP', 'sig'], 'شاخصِ پویای معامله‌گران', (c, p) => {
  const rsi = I.rsi(closes(c), p.rsiP) as unknown as number[]
  return asSeries(smaArr(rsi, p.sig))
})

export const STRUCTURE_ITEMS = K.items

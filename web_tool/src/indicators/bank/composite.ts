// ============================================================================
// indicators/bank/composite.ts — دستهٔ تبدیل‌های قیمت + ترکیبی (Price transforms / Composite)
// ----------------------------------------------------------------------------
// منابع: EN/composite. تبدیل‌های قیمتیِ پایه (HL2/HLC3/OHLC4/WCP/midpoint) و چند
// اندیکاتورِ ترکیبیِ رژیم‌محور (فاصلهٔ ATR-نرمال، RSI روی ER کافمن، دروازهٔ چاپینس).
// منطق کاملاً verbatim از bank.ts؛ بدونِ look-ahead و active:false.
// ============================================================================

import * as I from '../../indicators'
import { makeKit, closes, highs, lows, emaArr, rmaArr, trArr, NaNArr, asSeries, highest, lowest } from './kit'

const K = makeKit()
const { def } = K

def('hl2', 'overlap', 'EN', {}, [], 'میانگینِ سقف-کف', (c) => asSeries(c.map(k => (k.high + k.low) / 2)))
def('hlc3', 'overlap', 'EN', {}, [], 'قیمتِ نوعی (typical)', (c) => asSeries(c.map(k => (k.high + k.low + k.close) / 3)))
def('ohlc4', 'overlap', 'EN', {}, [], 'میانگینِ چهارقیمتی', (c) => asSeries(c.map(k => (k.open + k.high + k.low + k.close) / 4)))
def('wcp', 'overlap', 'EN', {}, [], 'قیمتِ بستهٔ وزنی', (c) => asSeries(c.map(k => (k.high + k.low + 2 * k.close) / 4)))
def('midpoint', 'overlap', 'EN', { period: 14 }, ['period'], 'نقطهٔ میانیِ کلوز', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) out[i] = (highest(x, i, p.period) + lowest(x, i, p.period)) / 2
  return asSeries(out)
})

// ATR-normalized distance from EMA (رژیمِ کشش)
def('ema_dist_atr', 'composite', 'composite', { emaP: 50, atrP: 14 }, ['emaP', 'atrP'], 'فاصلهٔ نرمال‌شدهٔ قیمت از EMA (بر حسبِ ATR)', (c, p) => {
  const x = closes(c), e = emaArr(x, p.emaP), a = rmaArr(trArr(c), p.atrP), n = x.length, out = NaNArr(n)
  for (let i = 0; i < n; i++) out[i] = a[i] ? (x[i] - e[i]) / a[i] : NaN
  return asSeries(out)
})

// RSI of Kaufman ER (کارایی-محور)
def('rsi_of_er', 'composite', 'composite', { erP: 10, rsiP: 14 }, ['erP', 'rsiP'], 'RSI روی نسبتِ کاراییِ کافمن', (c, p) => {
  const x = closes(c), n = x.length, er = NaNArr(n)
  for (let i = p.erP; i < n; i++) {
    const change = Math.abs(x[i] - x[i - p.erP])
    let vol = 0; for (let k = 0; k < p.erP; k++) vol += Math.abs(x[i - k] - x[i - k - 1])
    er[i] = vol ? change / vol : 0
  }
  return asSeries(I.rsi(er.map(v => (Number.isFinite(v) ? v * 100 : 0)), p.rsiP) as unknown as number[])
})

// Choppiness-gated trend flag (chop<38.2 و شیبِ EMA) → {−1,0,+1}
def('trend_gate', 'composite', 'composite', { chopP: 14, emaP: 50, thr: 38.2 }, ['chopP', 'emaP', 'thr'], 'دروازهٔ روند با فیلترِ چاپینس', (c, p) => {
  const x = closes(c), n = x.length, tr = trArr(c), h = highs(c), l = lows(c), e = emaArr(x, p.emaP)
  const out = NaNArr(n)
  for (let i = p.chopP; i < n; i++) {
    let sumTr = 0; for (let k = 0; k < p.chopP; k++) sumTr += tr[i - k] || 0
    const rng = highest(h, i, p.chopP) - lowest(l, i, p.chopP)
    const chop = rng > 0 ? (100 * Math.log10(sumTr / rng)) / Math.log10(p.chopP) : 100
    if (chop < p.thr) out[i] = Math.sign(e[i] - e[i - 1]); else out[i] = 0
  }
  return asSeries(out)
})

export const COMPOSITE_ITEMS = K.items

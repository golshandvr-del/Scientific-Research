// ============================================================================
// indicators/bank/momentum.ts — دستهٔ مومنتوم/اسیلاتورها (شامل بومیِ چینی)
// ----------------------------------------------------------------------------
// منابع: EN/deep-web/pandas-ta + CN (通达信: KDJ/BIAS/WR/PSY/BRAR/CR/TRIX/DPO/…).
// همه بدونِ look-ahead و active:false.
// ============================================================================

import * as I from '../../indicators'
import { makeKit, closes, highs, lows, emaArr, smaArr, NaNArr, asSeries, highest, lowest } from './kit'

const K = makeKit()
const { def } = K

// ---- batch 2: Momentum عمومی (EN/deep-web) -------------------------------
// AO — Awesome Oscillator = SMA5(median) − SMA34(median)
def('ao', 'momentum', 'EN', { fast: 5, slow: 34 }, ['fast', 'slow'], 'اسیلاتورِ عالی (بیل ویلیامز)', (c, p) => {
  const med = c.map(k => (k.high + k.low) / 2)
  const f = smaArr(med, p.fast), s = smaArr(med, p.slow)
  return asSeries(f.map((v, i) => v - s[i]))
})

// AC — Accelerator Oscillator = AO − SMA5(AO)
def('ac', 'momentum', 'EN', { fast: 5, slow: 34, smooth: 5 }, ['fast', 'slow', 'smooth'], 'اسیلاتورِ شتاب‌دهنده', (c, p) => {
  const med = c.map(k => (k.high + k.low) / 2)
  const ao = smaArr(med, p.fast).map((v, i) => v - smaArr(med, p.slow)[i])
  const sm = smaArr(ao, p.smooth)
  return asSeries(ao.map((v, i) => v - sm[i]))
})

// APO — Absolute Price Oscillator = EMA(fast) − EMA(slow)
def('apo', 'momentum', 'EN', { fast: 12, slow: 26 }, ['fast', 'slow'], 'اسیلاتورِ مطلقِ قیمت', (c, p) => {
  const x = closes(c), f = emaArr(x, p.fast), s = emaArr(x, p.slow)
  return asSeries(f.map((v, i) => v - s[i]))
})

// PPO — Percentage Price Oscillator = 100·(EMAf − EMAs)/EMAs
def('ppo', 'momentum', 'EN', { fast: 12, slow: 26 }, ['fast', 'slow'], 'اسیلاتورِ درصدیِ قیمت', (c, p) => {
  const x = closes(c), f = emaArr(x, p.fast), s = emaArr(x, p.slow)
  return asSeries(f.map((v, i) => (s[i] ? (100 * (v - s[i])) / s[i] : NaN)))
})

// CMO — Chande Momentum Oscillator
def('cmo', 'momentum', 'EN', { period: 14 }, ['period'], 'اسیلاتورِ مومنتومِ چاند', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period; i < n; i++) {
    let up = 0, dn = 0
    for (let k = 0; k < p.period; k++) { const d = x[i - k] - x[i - k - 1]; if (d > 0) up += d; else dn -= d }
    out[i] = (up + dn) === 0 ? 0 : (100 * (up - dn)) / (up + dn)
  }
  return asSeries(out)
})

// TSI — True Strength Index
def('tsi', 'momentum', 'EN', { long: 25, short: 13 }, ['long', 'short'], 'شاخصِ قدرتِ حقیقی', (c, p) => {
  const x = closes(c), n = x.length
  const mom = NaNArr(n); for (let i = 1; i < n; i++) mom[i] = x[i] - x[i - 1]
  const abs = mom.map(v => Math.abs(v))
  const d1 = emaArr(mom, p.long), d2 = emaArr(d1, p.short)
  const a1 = emaArr(abs, p.long), a2 = emaArr(a1, p.short)
  return asSeries(d2.map((v, i) => (a2[i] ? (100 * v) / a2[i] : NaN)))
})

// ROC — Rate of Change (%)
def('roc', 'momentum', 'EN', { period: 10 }, ['period'], 'نرخِ تغییر (درصد)', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period; i < n; i++) out[i] = x[i - p.period] ? (100 * (x[i] - x[i - p.period])) / x[i - p.period] : NaN
  return asSeries(out)
})

// MOM — Momentum (خام)
def('mom', 'momentum', 'EN', { period: 10 }, ['period'], 'مومنتومِ خام', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period; i < n; i++) out[i] = x[i] - x[i - p.period]
  return asSeries(out)
})

// BOP — Balance of Power = (close−open)/(high−low)
def('bop', 'momentum', 'EN', { smooth: 14 }, ['smooth'], 'توازنِ قدرت', (c, p) => {
  const raw = c.map(k => (k.high - k.low) ? (k.close - k.open) / (k.high - k.low) : 0)
  return asSeries(smaArr(raw, p.smooth))
})

// CFO — Chande Forecast Oscillator (انحراف از رگرسیونِ خطی، درصد)
def('cfo', 'momentum', 'EN', { period: 14 }, ['period'], 'اسیلاتورِ پیش‌بینیِ چاند', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) {
    let sx = 0, sy = 0, sxy = 0, sxx = 0
    for (let k = 0; k < p.period; k++) { const xi = k, yi = x[i - (p.period - 1 - k)]; sx += xi; sy += yi; sxy += xi * yi; sxx += xi * xi }
    const m = (p.period * sxy - sx * sy) / (p.period * sxx - sx * sx)
    const b = (sy - m * sx) / p.period
    const fc = m * (p.period - 1) + b
    out[i] = x[i] ? (100 * (x[i] - fc)) / x[i] : NaN
  }
  return asSeries(out)
})

// PGO — Pretty Good Oscillator = (close − SMA)/EMA(ATR)
def('pgo', 'momentum', 'deep-web', { period: 14 }, ['period'], 'اسیلاتورِ نسبتاً خوب', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  const sma = smaArr(x, p.period)
  const tr = NaNArr(n)
  for (let i = 1; i < n; i++) tr[i] = Math.max(c[i].high - c[i].low, Math.abs(c[i].high - c[i - 1].close), Math.abs(c[i].low - c[i - 1].close))
  const eatr = emaArr(tr, p.period)
  for (let i = 0; i < n; i++) out[i] = eatr[i] ? (x[i] - sma[i]) / eatr[i] : NaN
  return asSeries(out)
})

// Fisher Transform (روی نرمال‌شدهٔ median در کانالِ period)
def('fisher', 'momentum', 'EN', { period: 9 }, ['period'], 'تبدیلِ فیشرِ اِهلرز', (c, p) => {
  const med = c.map(k => (k.high + k.low) / 2), n = med.length, out = NaNArr(n)
  let v = 0, prevF = 0
  for (let i = p.period - 1; i < n; i++) {
    const hh = highest(med, i, p.period), ll = lowest(med, i, p.period)
    const rng = hh - ll || 1e-10
    v = 0.66 * ((2 * (med[i] - ll) / rng) - 1) + 0.67 * v
    const vv = Math.max(-0.999, Math.min(0.999, v))
    const f = 0.5 * Math.log((1 + vv) / (1 - vv)) + 0.5 * prevF
    out[i] = f; prevF = f
  }
  return asSeries(out)
})

// Inverse Fisher of RSI
def('ifish_rsi', 'momentum', 'EN', { period: 14 }, ['period'], 'فیشرِ معکوسِ RSI', (c, p) => {
  const rsi = I.rsi(closes(c), p.period) as unknown as number[]
  return asSeries(rsi.map(r => {
    if (!Number.isFinite(r)) return NaN
    const v = 0.1 * (r - 50)
    return (Math.exp(2 * v) - 1) / (Math.exp(2 * v) + 1)
  }))
})

// RVGI — Relative Vigor Index
def('rvgi', 'momentum', 'EN', { period: 10 }, ['period'], 'شاخصِ سرزندگیِ نسبی', (c, p) => {
  const n = c.length, num = NaNArr(n), den = NaNArr(n)
  const co = c.map(k => k.close - k.open), hl = c.map(k => k.high - k.low)
  for (let i = 3; i < n; i++) {
    num[i] = (co[i] + 2 * co[i - 1] + 2 * co[i - 2] + co[i - 3]) / 6
    den[i] = (hl[i] + 2 * hl[i - 1] + 2 * hl[i - 2] + hl[i - 3]) / 6
  }
  const sn = smaArr(num, p.period), sd = smaArr(den, p.period)
  return asSeries(sn.map((v, i) => (sd[i] ? v / sd[i] : NaN)))
})

// ---- batch 3: بومیِ چینی (通达信/同花顺) — momentum-محورها ----------------
// KDJ — خطِ J = 3K − 2D
def('kdj_j', 'momentum', 'CN', { period: 9, k: 3, d: 3 }, ['period', 'k', 'd'], 'خطِ J از KDJ چینی (3K−2D)', (c, p) => {
  const h = highs(c), l = lows(c), x = closes(c), n = x.length
  const rsv = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) {
    const hh = highest(h, i, p.period), ll = lowest(l, i, p.period)
    rsv[i] = (hh - ll) ? (100 * (x[i] - ll)) / (hh - ll) : 50
  }
  const kSer = NaNArr(n); let kPrev = 50
  for (let i = 0; i < n; i++) { if (!Number.isFinite(rsv[i])) continue; kPrev = (rsv[i] + (p.k - 1) * kPrev) / p.k; kSer[i] = kPrev }
  const dSer = NaNArr(n); let dPrev = 50
  for (let i = 0; i < n; i++) { if (!Number.isFinite(kSer[i])) continue; dPrev = (kSer[i] + (p.d - 1) * dPrev) / p.d; dSer[i] = dPrev }
  return asSeries(kSer.map((k, i) => (Number.isFinite(dSer[i]) ? 3 * k - 2 * dSer[i] : NaN)))
})

// BIAS — 乖离率 = 100·(close − SMA)/SMA
def('bias', 'momentum', 'CN', { period: 6 }, ['period'], 'نرخِ انحراف (乖离率)', (c, p) => {
  const x = closes(c), s = smaArr(x, p.period)
  return asSeries(x.map((v, i) => (s[i] ? (100 * (v - s[i])) / s[i] : NaN)))
})

// WR — Williams %R چینی (0..100 معکوس)
def('wr_cn', 'momentum', 'CN', { period: 14 }, ['period'], 'ویلیامز %R چینی (威廉)', (c, p) => {
  const h = highs(c), l = lows(c), x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) {
    const hh = highest(h, i, p.period), ll = lowest(l, i, p.period)
    out[i] = (hh - ll) ? (100 * (hh - x[i])) / (hh - ll) : 50
  }
  return asSeries(out)
})

// PSY — 心理线 = 100·(روزهای صعودی)/N
def('psy', 'momentum', 'CN', { period: 12 }, ['period'], 'خطِ روانی (心理线)', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period; i < n; i++) {
    let up = 0
    for (let k = 0; k < p.period; k++) if (x[i - k] > x[i - k - 1]) up++
    out[i] = (100 * up) / p.period
  }
  return asSeries(out)
})

// BR — 意愿指标
def('br', 'momentum', 'CN', { period: 26 }, ['period'], 'شاخصِ اراده BR (情绪)', (c, p) => {
  const n = c.length, out = NaNArr(n)
  for (let i = p.period; i < n; i++) {
    let num = 0, den = 0
    for (let k = 0; k < p.period; k++) {
      const pc = c[i - k - 1].close
      num += Math.max(0, c[i - k].high - pc); den += Math.max(0, pc - c[i - k].low)
    }
    out[i] = den ? (100 * num) / den : 100
  }
  return asSeries(out)
})

// AR — 人气指标
def('ar', 'momentum', 'CN', { period: 26 }, ['period'], 'شاخصِ محبوبیت AR (人气)', (c, p) => {
  const n = c.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) {
    let num = 0, den = 0
    for (let k = 0; k < p.period; k++) { num += c[i - k].high - c[i - k].open; den += c[i - k].open - c[i - k].low }
    out[i] = den ? (100 * num) / den : 100
  }
  return asSeries(out)
})

// CR — 带状能量线
def('cr', 'momentum', 'CN', { period: 26 }, ['period'], 'خطِ انرژیِ نواری CR (带状能量)', (c, p) => {
  const n = c.length, out = NaNArr(n)
  for (let i = p.period; i < n; i++) {
    let num = 0, den = 0
    for (let k = 0; k < p.period; k++) {
      const m = (c[i - k - 1].high + c[i - k - 1].low + c[i - k - 1].close) / 3
      num += Math.max(0, c[i - k].high - m); den += Math.max(0, m - c[i - k].low)
    }
    out[i] = den ? (100 * num) / den : 100
  }
  return asSeries(out)
})

// TRIX — 三重指数平滑 (درصد)
def('trix', 'momentum', 'CN', { period: 12 }, ['period'], 'تریکس (三重指数平滑)', (c, p) => {
  const e1 = emaArr(closes(c), p.period), e2 = emaArr(e1, p.period), e3 = emaArr(e2, p.period), n = e3.length
  const out = NaNArr(n)
  for (let i = 1; i < n; i++) out[i] = e3[i - 1] ? (100 * (e3[i] - e3[i - 1])) / e3[i - 1] : NaN
  return asSeries(out)
})

// DPO — 区间震荡线 Detrended Price Oscillator
def('dpo', 'momentum', 'CN', { period: 20 }, ['period'], 'اسیلاتورِ بدونِ‌روند (区间震荡)', (c, p) => {
  const x = closes(c), s = smaArr(x, p.period), n = x.length, out = NaNArr(n)
  const shift = Math.floor(p.period / 2) + 1
  for (let i = 0; i < n; i++) if (i - shift >= 0 && Number.isFinite(s[i - shift])) out[i] = x[i] - s[i - shift]
  return asSeries(out)
})

// MTM — 动量线
def('mtm', 'momentum', 'CN', { period: 12, smooth: 6 }, ['period', 'smooth'], 'خطِ مومنتومِ چینی (动量)', (c, p) => {
  const x = closes(c), n = x.length, raw = NaNArr(n)
  for (let i = p.period; i < n; i++) raw[i] = x[i] - x[i - p.period]
  return asSeries(smaArr(raw, p.smooth))
})

// ADTM — 动态买卖气 (بازهٔ −1..+1)
def('adtm', 'momentum', 'CN', { period: 23, smooth: 8 }, ['period', 'smooth'], 'انرژیِ پویای خرید/فروش (动态买卖气)', (c, p) => {
  const n = c.length, dtm = NaNArr(n), dbm = NaNArr(n)
  for (let i = 1; i < n; i++) {
    if (c[i].open <= c[i - 1].open) dtm[i] = 0
    else dtm[i] = Math.max(c[i].high - c[i].open, c[i].open - c[i - 1].open)
    if (c[i].open >= c[i - 1].open) dbm[i] = 0
    else dbm[i] = Math.max(c[i].open - c[i].low, c[i].open - c[i - 1].open)
  }
  const out = NaNArr(n)
  for (let i = p.period; i < n; i++) {
    let sd = 0, sb = 0
    for (let k = 0; k < p.period; k++) { sd += dtm[i - k] || 0; sb += dbm[i - k] || 0 }
    const stm = Math.max(sd, sb)
    out[i] = stm ? (sd - sb) / stm : 0
  }
  return asSeries(smaArr(out, p.smooth))
})

export const MOMENTUM_ITEMS = K.items

// ============================================================================
// indicators/bank/cycle.ts — دستهٔ چرخه/DSP/اِهلرز (Cycle / Ehlers / DSP)
// ----------------------------------------------------------------------------
// منابع: deep-web (John Ehlers — mesasoftware, Cycle Analytics). پیشرفته‌ترین دسته،
// هدفِ رفعِ اشتباهِ رایج #۲ (اجتناب از پیچیدگی). همه بدونِ look-ahead و active:false.
// ============================================================================

import { makeKit, closes, NaNArr, asSeries } from './kit'

const K = makeKit()
const { def } = K

// Super Smoother Filter (Ehlers 2-pole Butterworth)
def('ssf', 'cycle', 'deep-web', { period: 10 }, ['period'], 'فیلترِ سوپر-اسموترِ اِهلرز', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  const a = Math.exp(-1.414 * Math.PI / p.period)
  const b = 2 * a * Math.cos(1.414 * Math.PI / p.period)
  const c2 = b, c3 = -a * a, c1 = 1 - c2 - c3
  for (let i = 0; i < n; i++) {
    if (i < 2) { out[i] = x[i]; continue }
    out[i] = c1 * (x[i] + x[i - 1]) / 2 + c2 * out[i - 1] + c3 * out[i - 2]
  }
  return asSeries(out)
})

// High-Pass Filter (Ehlers 1-pole)
def('ehp', 'cycle', 'deep-web', { period: 48 }, ['period'], 'فیلترِ بالاگذرِ اِهلرز', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  const a = (Math.cos(2 * Math.PI / p.period) + Math.sin(2 * Math.PI / p.period) - 1) / Math.cos(2 * Math.PI / p.period)
  for (let i = 0; i < n; i++) {
    if (i < 1) { out[i] = 0; continue }
    out[i] = (1 - a / 2) * (x[i] - x[i - 1]) + (1 - a) * out[i - 1]
  }
  return asSeries(out)
})

// Roofing Filter (High-Pass → Super Smoother)
def('roof', 'cycle', 'deep-web', { hp: 48, ss: 10 }, ['hp', 'ss'], 'فیلترِ سقفیِ اِهلرز', (c, p) => {
  const x = closes(c), n = x.length, hp = NaNArr(n)
  const a = (Math.cos(2 * Math.PI / p.hp) + Math.sin(2 * Math.PI / p.hp) - 1) / Math.cos(2 * Math.PI / p.hp)
  for (let i = 0; i < n; i++) { if (i < 2) { hp[i] = 0; continue } hp[i] = (1 - a / 2) * (1 - a / 2) * (x[i] - 2 * x[i - 1] + x[i - 2]) + 2 * (1 - a) * hp[i - 1] - (1 - a) * (1 - a) * hp[i - 2] }
  const out = NaNArr(n)
  const aa = Math.exp(-1.414 * Math.PI / p.ss), bb = 2 * aa * Math.cos(1.414 * Math.PI / p.ss)
  const c2 = bb, c3 = -aa * aa, c1 = 1 - c2 - c3
  for (let i = 0; i < n; i++) { if (i < 2) { out[i] = hp[i]; continue } out[i] = c1 * (hp[i] + hp[i - 1]) / 2 + c2 * out[i - 1] + c3 * out[i - 2] }
  return asSeries(out)
})

// Laguerre Filter (Ehlers) — MA کم‌تأخیر
def('laguerre', 'cycle', 'deep-web', { gamma: 0.8 }, ['gamma'], 'فیلترِ لاگرِ اِهلرز', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  let L0 = 0, L1 = 0, L2 = 0, L3 = 0
  const g = p.gamma
  for (let i = 0; i < n; i++) {
    const pL0 = L0, pL1 = L1, pL2 = L2
    L0 = (1 - g) * x[i] + g * L0
    L1 = -g * L0 + pL0 + g * L1
    L2 = -g * L1 + pL1 + g * L2
    L3 = -g * L2 + pL2 + g * L3
    out[i] = (L0 + 2 * L1 + 2 * L2 + L3) / 6
  }
  return asSeries(out)
})

// Laguerre RSI (Ehlers)
def('laguerre_rsi', 'cycle', 'deep-web', { gamma: 0.5 }, ['gamma'], 'RSI لاگرِ اِهلرز', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  let L0 = 0, L1 = 0, L2 = 0, L3 = 0
  const g = p.gamma
  for (let i = 0; i < n; i++) {
    const pL0 = L0, pL1 = L1, pL2 = L2
    L0 = (1 - g) * x[i] + g * L0
    L1 = -g * L0 + pL0 + g * L1
    L2 = -g * L1 + pL1 + g * L2
    L3 = -g * L2 + pL2 + g * L3
    let cu = 0, cd = 0
    if (L0 >= L1) cu += L0 - L1; else cd += L1 - L0
    if (L1 >= L2) cu += L1 - L2; else cd += L2 - L1
    if (L2 >= L3) cu += L2 - L3; else cd += L3 - L2
    out[i] = (cu + cd) ? (100 * cu) / (cu + cd) : 50
  }
  return asSeries(out)
})

// Ehlers Reflex (2020)
def('reflex', 'cycle', 'deep-web', { period: 20 }, ['period'], 'ریفلکسِ اِهلرز (۲۰۲۰)', (c, p) => {
  const x = closes(c), n = x.length, ssf = NaNArr(n)
  const a = Math.exp(-1.414 * Math.PI / (p.period / 2)), b = 2 * a * Math.cos(1.414 * Math.PI / (p.period / 2))
  const c2 = b, c3 = -a * a, c1 = 1 - c2 - c3
  for (let i = 0; i < n; i++) { if (i < 2) { ssf[i] = x[i]; continue } ssf[i] = c1 * (x[i] + x[i - 1]) / 2 + c2 * ssf[i - 1] + c3 * ssf[i - 2] }
  const out = NaNArr(n); let ms = 0
  for (let i = p.period; i < n; i++) {
    const slope = (ssf[i - p.period] - ssf[i]) / p.period
    let sum = 0; for (let k = 1; k <= p.period; k++) sum += ssf[i] + k * slope - ssf[i - k]
    sum /= p.period
    ms = 0.04 * sum * sum + 0.96 * ms
    out[i] = ms ? sum / Math.sqrt(ms) : 0
  }
  return asSeries(out)
})

// Ehlers TrendFlex (2020)
def('trendflex', 'cycle', 'deep-web', { period: 20 }, ['period'], 'ترندفلکسِ اِهلرز (۲۰۲۰)', (c, p) => {
  const x = closes(c), n = x.length, ssf = NaNArr(n)
  const a = Math.exp(-1.414 * Math.PI / (p.period / 2)), b = 2 * a * Math.cos(1.414 * Math.PI / (p.period / 2))
  const c2 = b, c3 = -a * a, c1 = 1 - c2 - c3
  for (let i = 0; i < n; i++) { if (i < 2) { ssf[i] = x[i]; continue } ssf[i] = c1 * (x[i] + x[i - 1]) / 2 + c2 * ssf[i - 1] + c3 * ssf[i - 2] }
  const out = NaNArr(n); let ms = 0
  for (let i = p.period; i < n; i++) {
    let sum = 0; for (let k = 1; k <= p.period; k++) sum += ssf[i] - ssf[i - k]
    sum /= p.period
    ms = 0.04 * sum * sum + 0.96 * ms
    out[i] = ms ? sum / Math.sqrt(ms) : 0
  }
  return asSeries(out)
})

// Ehlers Center of Gravity
def('cg', 'cycle', 'deep-web', { period: 10 }, ['period'], 'مرکزِ ثقلِ اِهلرز (CG)', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n)
  for (let i = p.period - 1; i < n; i++) {
    let num = 0, den = 0
    for (let k = 0; k < p.period; k++) { num += (1 + k) * x[i - k]; den += x[i - k] }
    out[i] = den ? -num / den + (p.period + 1) / 2 : 0
  }
  return asSeries(out)
})

// DSMA — Deviation-Scaled MA (Ehlers)
def('dsma', 'cycle', 'deep-web', { period: 20 }, ['period'], 'میانگینِ مقیاسِ‌انحرافِ اِهلرز', (c, p) => {
  const x = closes(c), n = x.length, out = NaNArr(n), zeros = NaNArr(n), filt = NaNArr(n)
  const a = Math.exp(-1.414 * Math.PI / (p.period / 2)), b = 2 * a * Math.cos(1.414 * Math.PI / (p.period / 2))
  const c2 = b, c3 = -a * a, c1 = 1 - c2 - c3
  let prev = NaN
  for (let i = 0; i < n; i++) {
    zeros[i] = i >= 2 ? x[i] - x[i - 2] : 0
    if (i < 2) { filt[i] = 0; out[i] = x[i]; prev = x[i]; continue }
    filt[i] = c1 * (zeros[i] + zeros[i - 1]) / 2 + c2 * filt[i - 1] + c3 * filt[i - 2]
    let rms = 0; const w = Math.min(p.period, i + 1)
    for (let k = 0; k < w; k++) rms += filt[i - k] * filt[i - k]
    rms = Math.sqrt(rms / w)
    const sc = rms ? Math.abs(filt[i] / rms) : 0
    const alpha = Math.max(0.01, Math.min(1, (5 * sc) / p.period))
    prev = alpha * x[i] + (1 - alpha) * prev
    out[i] = prev
  }
  return asSeries(out)
})

export const CYCLE_ITEMS = K.items

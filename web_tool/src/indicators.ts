// ============================================================================
// بازتولید کتابخانه اندیکاتورهای پروژه (engine/indicators.py) در TypeScript
// همه توابع بدون look-ahead bias — فقط از داده گذشته/جاری استفاده می‌کنند.
// ورودی‌ها آرایه‌های عددی هم‌طول هستند؛ خروجی هم‌طول با NaN در ابتدای سری.
// ============================================================================

export interface Candle {
  time: number   // unix seconds
  open: number
  high: number
  low: number
  close: number
  volume: number
}

const NaNArr = (n: number) => new Array<number>(n).fill(NaN)

// میانگین متحرک ساده
export function sma(x: number[], period: number): number[] {
  const out = NaNArr(x.length)
  let sum = 0
  for (let i = 0; i < x.length; i++) {
    sum += x[i]
    if (i >= period) sum -= x[i - period]
    if (i >= period - 1) out[i] = sum / period
  }
  return out
}

// میانگین متحرک نمایی (span-based، معادل pandas ewm(span=period, adjust=False))
export function ema(x: number[], period: number): number[] {
  const out = NaNArr(x.length)
  const alpha = 2 / (period + 1)
  let prev = NaN
  for (let i = 0; i < x.length; i++) {
    const v = x[i]
    if (isNaN(v)) { out[i] = prev; continue }
    if (isNaN(prev)) prev = v
    else prev = alpha * v + (1 - alpha) * prev
    out[i] = prev
  }
  return out
}

// EWM با آلفای مستقیم (معادل ewm(alpha=1/period, adjust=False))
function ewmAlpha(x: number[], alpha: number): number[] {
  const out = NaNArr(x.length)
  let prev = NaN
  for (let i = 0; i < x.length; i++) {
    const v = x[i]
    if (isNaN(v)) { out[i] = prev; continue }
    if (isNaN(prev)) prev = v
    else prev = alpha * v + (1 - alpha) * prev
    out[i] = prev
  }
  return out
}

export function diff(x: number[]): number[] {
  const out = NaNArr(x.length)
  for (let i = 1; i < x.length; i++) out[i] = x[i] - x[i - 1]
  return out
}

export function pctChange(x: number[], p: number): number[] {
  const out = NaNArr(x.length)
  for (let i = p; i < x.length; i++) {
    const base = x[i - p]
    out[i] = base !== 0 ? (x[i] - base) / base : NaN
  }
  return out
}

export function rsi(close: number[], period = 14): number[] {
  const d = diff(close)
  const gain = d.map(v => (isNaN(v) ? NaN : Math.max(v, 0)))
  const loss = d.map(v => (isNaN(v) ? NaN : Math.max(-v, 0)))
  const ag = ewmAlpha(gain, 1 / period)
  const al = ewmAlpha(loss, 1 / period)
  const out = NaNArr(close.length)
  for (let i = 0; i < close.length; i++) {
    if (isNaN(ag[i]) || isNaN(al[i])) continue
    const rs = al[i] === 0 ? NaN : ag[i] / al[i]
    out[i] = isNaN(rs) ? 100 : 100 - 100 / (1 + rs)
  }
  return out
}

export function trueRange(c: Candle[]): number[] {
  const out = NaNArr(c.length)
  for (let i = 0; i < c.length; i++) {
    const hl = c[i].high - c[i].low
    if (i === 0) { out[i] = hl; continue }
    const pc = c[i - 1].close
    out[i] = Math.max(hl, Math.abs(c[i].high - pc), Math.abs(c[i].low - pc))
  }
  return out
}

export function atr(c: Candle[], period = 14): number[] {
  return ewmAlpha(trueRange(c), 1 / period)
}

export function rollingStd(x: number[], period: number): number[] {
  // انحراف معیار نمونه‌ای (ddof=1) مانند pandas.rolling(...).std()
  const out = NaNArr(x.length)
  for (let i = period - 1; i < x.length; i++) {
    let mean = 0
    for (let k = i - period + 1; k <= i; k++) mean += x[k]
    mean /= period
    let s = 0
    for (let k = i - period + 1; k <= i; k++) s += (x[k] - mean) ** 2
    out[i] = Math.sqrt(s / (period - 1))
  }
  return out
}

export function bollinger(close: number[], period = 20, mult = 2.0) {
  const mid = sma(close, period)
  const std = rollingStd(close, period)
  const upper = close.map((_, i) => mid[i] + mult * std[i])
  const lower = close.map((_, i) => mid[i] - mult * std[i])
  return { lower, mid, upper }
}

export function macd(close: number[], fast = 12, slow = 26, signal = 9) {
  const ef = ema(close, fast)
  const es = ema(close, slow)
  const line = close.map((_, i) => ef[i] - es[i])
  const sig = ema(line, signal)
  const hist = line.map((_, i) => line[i] - sig[i])
  return { line, sig, hist }
}

export function stoch(c: Candle[], kPeriod = 14, dPeriod = 3) {
  const out = NaNArr(c.length)
  for (let i = kPeriod - 1; i < c.length; i++) {
    let lo = Infinity, hi = -Infinity
    for (let k = i - kPeriod + 1; k <= i; k++) {
      if (c[k].low < lo) lo = c[k].low
      if (c[k].high > hi) hi = c[k].high
    }
    const denom = hi - lo
    out[i] = denom !== 0 ? (100 * (c[i].close - lo)) / denom : NaN
  }
  const d = sma(out, dPeriod)
  return { k: out, d }
}

export function adx(c: Candle[], period = 14) {
  const n = c.length
  const plusDM = NaNArr(n), minusDM = NaNArr(n)
  for (let i = 1; i < n; i++) {
    const up = c[i].high - c[i - 1].high
    const dn = c[i - 1].low - c[i].low
    let p = up > 0 ? up : 0
    let m = dn > 0 ? dn : 0
    if (p - m < 0) p = 0
    if (m - p < 0) m = 0
    plusDM[i] = p; minusDM[i] = m
  }
  const tr = trueRange(c)
  const atr_ = ewmAlpha(tr, 1 / period)
  const pdmE = ewmAlpha(plusDM, 1 / period)
  const mdmE = ewmAlpha(minusDM, 1 / period)
  const pdi = NaNArr(n), mdi = NaNArr(n), dx = NaNArr(n)
  for (let i = 0; i < n; i++) {
    if (isNaN(atr_[i]) || atr_[i] === 0) continue
    pdi[i] = (100 * pdmE[i]) / atr_[i]
    mdi[i] = (100 * mdmE[i]) / atr_[i]
    const s = pdi[i] + mdi[i]
    dx[i] = s !== 0 ? (100 * Math.abs(pdi[i] - mdi[i])) / s : NaN
  }
  const adx_ = ewmAlpha(dx, 1 / period)
  return { adx: adx_, pdi, mdi }
}

export function zscore(x: number[], period: number): number[] {
  const mean = sma(x, period)
  const std = rollingStd(x, period)
  return x.map((_, i) => (std[i] ? (x[i] - mean[i]) / std[i] : NaN))
}

// شیب رگرسیون خطی روی پنجره متحرک (معادل rolling_slope)
export function rollingSlope(x: number[], period: number): number[] {
  const out = NaNArr(x.length)
  const xs: number[] = []
  for (let k = 0; k < period; k++) xs.push(k)
  const xMean = (period - 1) / 2
  let denom = 0
  for (let k = 0; k < period; k++) denom += (xs[k] - xMean) ** 2
  for (let i = period - 1; i < x.length; i++) {
    let yMean = 0
    for (let k = 0; k < period; k++) yMean += x[i - period + 1 + k]
    yMean /= period
    let num = 0
    for (let k = 0; k < period; k++) num += (xs[k] - xMean) * (x[i - period + 1 + k] - yMean)
    out[i] = num / denom
  }
  return out
}

// ============================================================================
// Vortex Indicator (VI+ , VI-) — لایهٔ S211. تشخیصِ جهتِ روند.
//   VMP = |high - low[t-1]|,  VMM = |low - high[t-1]|
//   TR  = max(h-l, |h-c[t-1]|, |l-c[t-1]|)
//   VI+ = sum(VMP,p)/sum(TR,p) ,  VI- = sum(VMM,p)/sum(TR,p)
// بدونِ look-ahead — فقط از داده تا اندیسِ i استفاده می‌شود.
// ============================================================================
export function vortex(c: Candle[], period = 14): { viPlus: number[]; viMinus: number[] } {
  const n = c.length
  const viPlus = NaNArr(n)
  const viMinus = NaNArr(n)
  if (n < period + 1) return { viPlus, viMinus }
  const vmp = NaNArr(n)
  const vmm = NaNArr(n)
  const tr = NaNArr(n)
  for (let i = 1; i < n; i++) {
    vmp[i] = Math.abs(c[i].high - c[i - 1].low)
    vmm[i] = Math.abs(c[i].low - c[i - 1].high)
    tr[i] = Math.max(
      c[i].high - c[i].low,
      Math.abs(c[i].high - c[i - 1].close),
      Math.abs(c[i].low - c[i - 1].close),
    )
  }
  for (let i = period; i < n; i++) {
    let sP = 0, sM = 0, sT = 0
    for (let k = i - period + 1; k <= i; k++) { sP += vmp[k]; sM += vmm[k]; sT += tr[k] }
    if (sT > 0) { viPlus[i] = sP / sT; viMinus[i] = sM / sT }
  }
  return { viPlus, viMinus }
}

// ============================================================================
// Kaufman Efficiency Ratio — لایهٔ S211. کیفیت/کاراییِ روند در بازهٔ period.
//   ER = |close[t]-close[t-p]| / sum(|close diff|, p)   (۰..۱ ؛ ۱=روندِ خالص)
// ============================================================================
export function kaufmanER(close: number[], period = 10): number[] {
  const n = close.length
  const out = NaNArr(n)
  if (n < period + 1) return out
  const absd = NaNArr(n)
  for (let i = 1; i < n; i++) absd[i] = Math.abs(close[i] - close[i - 1])
  for (let i = period; i < n; i++) {
    const change = Math.abs(close[i] - close[i - period])
    let vol = 0
    for (let k = i - period + 1; k <= i; k++) vol += absd[k]
    out[i] = vol > 0 ? change / vol : NaN
  }
  return out
}

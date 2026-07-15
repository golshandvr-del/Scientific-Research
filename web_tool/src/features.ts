// ============================================================================
// بازتولید دقیق engine/features.py در TypeScript — ۵۷ feature به ترتیب
// feature_order.txt. این خروجی مستقیماً به مدل ONNX (onnxruntime-web) داده می‌شود
// تا سیگنال «دقیقاً معادل ربات» در مرورگر تولید شود (نه تقریب).
//
// نکات هم‌ارزی حیاتی با پایتون:
//   - hour/dow از زمان UTC گرفته می‌شوند (features.py با pd.to_datetime(unit='s')
//     که UTC است کار می‌کند). پس getUTCHours/getUTCDay استفاده می‌شود.
//   - daily_open و VWAP لنگرشده بر اساس «تاریخ UTC» گروه‌بندی می‌شوند.
//   - streak: طول دنباله‌ی هم‌علامت diff، علامت‌دار (مثل groupby cumcount پایتون).
//   - همه‌ی اندیکاتورها از indicators.ts که هم‌ارز indicators.py است می‌آیند.
// ============================================================================
import type { Candle } from './indicators'
import * as ind from './indicators'

// ترتیب دقیق ۵۷ feature (مطابق mt5_robot/feature_order.txt)
export const FEATURE_ORDER: string[] = [
  'ret_1', 'ret_2', 'ret_3', 'ret_5', 'ret_8', 'ret_13', 'ret_21',
  'rsi_7', 'rsi_14', 'rsi_21',
  'macd', 'macd_sig', 'macd_hist',
  'atr', 'atr_pct', 'atr_ratio', 'range_pct', 'body_pct',
  'adx', 'di_diff',
  'bb_pos', 'bb_width',
  'stoch_k', 'stoch_d',
  'dist_ema20', 'dist_ema50', 'dist_ema100',
  'slope_20', 'slope_50',
  'zscore_20', 'zscore_50',
  'vol_ratio',
  'upper_wick', 'lower_wick', 'streak',
  'hour_sin', 'hour_cos', 'dow', 'hour',
  'dist_daily_open',
  'trend_h1', 'slope_h1', 'ret_h1',
  'trend_h4', 'slope_h4', 'ret_h4',
  'trend_d1', 'slope_d1', 'ret_d1',
  'above_ema200', 'dist_ema200',
  'vwap_dist', 'vwap_dist_atr', 'above_vwap',
  'ema50_dist_atr', 'vol_z20', 'close_pos_in_range',
]

const NaNArr = (n: number) => new Array<number>(n).fill(NaN)

// rolling mean که NaN را نادیده می‌گیرد نیست؛ اینجا مثل pandas.rolling(period).mean()
function rollingMean(x: number[], period: number): number[] {
  const out = NaNArr(x.length)
  for (let i = period - 1; i < x.length; i++) {
    let s = 0, ok = true
    for (let k = i - period + 1; k <= i; k++) {
      if (isNaN(x[k])) { ok = false; break }
      s += x[k]
    }
    if (ok) out[i] = s / period
  }
  return out
}

export interface FeatureMatrix {
  names: string[]
  // برای هر کندل، بردار ۵۷تایی؛ ردیف‌هایی که هنوز NaN دارند نامعتبرند
  rows: Float32Array[]
  // فیلد کمکی برای رژیم پایه S14
  ema50: number[]
  ema200: number[]
  vwap: number[]
  atr: number[]
  rsi14: number[]
  adx: number[]
  macdHist: number[]
  valid: boolean[]  // آیا ردیف i هیچ NaN ندارد
}

// VWAP روزانه لنگرشده — گروه‌بندی بر اساس تاریخ UTC (روز تقویمی)
function anchoredVWAP(c: Candle[]): number[] {
  const out = NaNArr(c.length)
  let cumPV = 0, cumV = 0, curDay = -1
  for (let i = 0; i < c.length; i++) {
    const day = Math.floor(c[i].time / 86400) // روز UTC
    if (day !== curDay) { cumPV = 0; cumV = 0; curDay = day }
    const tp = (c[i].high + c[i].low + c[i].close) / 3
    cumPV += tp * c[i].volume
    cumV += c[i].volume
    out[i] = cumV > 0 ? cumPV / cumV : NaN
  }
  return out
}

// open روز جاری (اولین open هر روز UTC) — معادل groupby(date)['open'].transform('first')
function dailyOpen(c: Candle[]): number[] {
  const out = new Array<number>(c.length)
  let curDay = -1, firstOpen = NaN
  for (let i = 0; i < c.length; i++) {
    const day = Math.floor(c[i].time / 86400)
    if (day !== curDay) { curDay = day; firstOpen = c[i].open }
    out[i] = firstOpen
  }
  return out
}

// streak علامت‌دار: طول دنباله‌ی هم‌علامتِ diff(close)، ضرب در علامت.
// معادل: sign = sign(close.diff()); groupby(run).cumcount()+1 ; *sign
function signedStreak(close: number[]): number[] {
  const out = NaNArr(close.length)
  let run = 0
  let prevSign = NaN
  for (let i = 0; i < close.length; i++) {
    if (i === 0) { out[i] = NaN; continue } // diff نامعین
    const d = close[i] - close[i - 1]
    const s = d > 0 ? 1 : (d < 0 ? -1 : 0)
    if (i === 1 || s !== prevSign) run = 1
    else run = run + 1
    prevSign = s
    out[i] = run * s
  }
  return out
}

export function buildFeatures(c: Candle[]): FeatureMatrix {
  const n = c.length
  const close = c.map(x => x.close)
  const high = c.map(x => x.high)
  const low = c.map(x => x.low)
  const open = c.map(x => x.open)
  const vol = c.map(x => x.volume)

  // بازده‌ها
  const ret: Record<number, number[]> = {}
  for (const p of [1, 2, 3, 5, 8, 13, 21]) ret[p] = ind.pctChange(close, p)

  // RSI
  const rsi7 = ind.rsi(close, 7), rsi14 = ind.rsi(close, 14), rsi21 = ind.rsi(close, 21)

  // MACD
  const { line: macdLine, sig: macdSig, hist: macdHist } = ind.macd(close)

  // ATR و نوسان
  const atr = ind.atr(c, 14)
  const atrPct = atr.map((v, i) => v / close[i])
  const atrMA = rollingMean(atr, 50)
  const atrRatio = atr.map((v, i) => v / atrMA[i])
  const rangePct = c.map((k, i) => (high[i] - low[i]) / close[i])
  const bodyPct = c.map((k, i) => Math.abs(close[i] - open[i]) / close[i])

  // ADX / DI
  const { adx, pdi, mdi } = ind.adx(c, 14)
  const diDiff = pdi.map((v, i) => v - mdi[i])

  // Bollinger
  const { lower: bbLo, upper: bbUp } = ind.bollinger(close, 20, 2.0)
  const bbPos = close.map((_, i) => {
    const w = bbUp[i] - bbLo[i]
    return w === 0 ? NaN : (close[i] - bbLo[i]) / w
  })
  const bbWidth = close.map((_, i) => (bbUp[i] - bbLo[i]) / close[i])

  // Stochastic
  const { k: stochK, d: stochD } = ind.stoch(c, 14, 3)

  // فاصله از EMAها
  const ema20 = ind.ema(close, 20)
  const ema50 = ind.ema(close, 50)
  const ema100 = ind.ema(close, 100)
  const ema200 = ind.ema(close, 200)
  const distEma20 = close.map((_, i) => (close[i] - ema20[i]) / ema20[i])
  const distEma50 = close.map((_, i) => (close[i] - ema50[i]) / ema50[i])
  const distEma100 = close.map((_, i) => (close[i] - ema100[i]) / ema100[i])

  // شیب
  const slope20raw = ind.rollingSlope(close, 20)
  const slope50raw = ind.rollingSlope(close, 50)
  const slope20 = slope20raw.map((v, i) => v / close[i])
  const slope50 = slope50raw.map((v, i) => v / close[i])

  // z-score
  const z20 = ind.zscore(close, 20)
  const z50 = ind.zscore(close, 50)

  // حجم
  const volMA20 = rollingMean(vol, 20)
  const volRatio = vol.map((v, i) => v / volMA20[i])

  // ساختار کندل
  const upperWick = c.map((_, i) => {
    const rng = high[i] - low[i]
    return rng === 0 ? NaN : (high[i] - Math.max(open[i], close[i])) / rng
  })
  const lowerWick = c.map((_, i) => {
    const rng = high[i] - low[i]
    return rng === 0 ? NaN : (Math.min(open[i], close[i]) - low[i]) / rng
  })
  const streak = signedStreak(close)

  // ویژگی‌های زمانی (UTC)
  const hourArr = c.map(k => new Date(k.time * 1000).getUTCHours())
  // pandas dayofweek: دوشنبه=0 ... یکشنبه=6 ؛ JS getUTCDay: یکشنبه=0..شنبه=6
  const dowArr = c.map(k => {
    const jsDow = new Date(k.time * 1000).getUTCDay() // 0=Sun..6=Sat
    return (jsDow + 6) % 7 // تبدیل به Mon=0..Sun=6
  })
  const hourSin = hourArr.map(h => Math.sin((2 * Math.PI * h) / 24))
  const hourCos = hourArr.map(h => Math.cos((2 * Math.PI * h) / 24))

  // فاصله از open روزانه
  const dOpen = dailyOpen(c)
  const distDailyOpen = close.map((_, i) => (close[i] - dOpen[i]) / dOpen[i])

  // ویژگی‌های چند-تایم‌فریمی (M15→H1=4, H4=16, D1=96)
  const mtf: Record<string, { trend: number[]; slope: number[]; ret: number[] }> = {}
  for (const [htf, name] of [[4, 'h1'], [16, 'h4'], [96, 'd1']] as [number, string][]) {
    const emaHtf = ind.ema(close, htf * 3)
    const trend = close.map((_, i) => (close[i] - emaHtf[i]) / emaHtf[i])
    const slopeRaw = ind.rollingSlope(close, htf)
    const slope = slopeRaw.map((v, i) => v / close[i])
    const retN = ind.pctChange(close, htf)
    mtf[name] = { trend, slope, ret: retN }
  }

  // EMA200 رژیم
  const aboveEma200 = close.map((_, i) => (close[i] > ema200[i] ? 1 : 0))
  const distEma200 = close.map((_, i) => (close[i] - ema200[i]) / ema200[i])

  // VWAP لنگرشده و مشتقات
  const vwap = anchoredVWAP(c)
  const vwapDist = close.map((_, i) => (close[i] - vwap[i]) / close[i])
  const vwapDistAtr = close.map((_, i) => (close[i] - vwap[i]) / atr[i])
  const aboveVwap = close.map((_, i) => (close[i] > vwap[i] ? 1 : 0))
  const ema50DistAtr = close.map((_, i) => (close[i] - ema50[i]) / atr[i])
  const volZ20 = ind.zscore(vol, 20)
  const closePos = c.map((_, i) => {
    const rng = high[i] - low[i]
    return rng === 0 ? NaN : (close[i] - low[i]) / rng
  })

  // نگاشت نام → آرایه، سپس ساخت ماتریس به ترتیب FEATURE_ORDER
  const map: Record<string, number[]> = {
    ret_1: ret[1], ret_2: ret[2], ret_3: ret[3], ret_5: ret[5],
    ret_8: ret[8], ret_13: ret[13], ret_21: ret[21],
    rsi_7: rsi7, rsi_14: rsi14, rsi_21: rsi21,
    macd: macdLine, macd_sig: macdSig, macd_hist: macdHist,
    atr, atr_pct: atrPct, atr_ratio: atrRatio, range_pct: rangePct, body_pct: bodyPct,
    adx, di_diff: diDiff,
    bb_pos: bbPos, bb_width: bbWidth,
    stoch_k: stochK, stoch_d: stochD,
    dist_ema20: distEma20, dist_ema50: distEma50, dist_ema100: distEma100,
    slope_20: slope20, slope_50: slope50,
    zscore_20: z20, zscore_50: z50,
    vol_ratio: volRatio,
    upper_wick: upperWick, lower_wick: lowerWick, streak,
    hour_sin: hourSin, hour_cos: hourCos, dow: dowArr, hour: hourArr,
    dist_daily_open: distDailyOpen,
    trend_h1: mtf.h1.trend, slope_h1: mtf.h1.slope, ret_h1: mtf.h1.ret,
    trend_h4: mtf.h4.trend, slope_h4: mtf.h4.slope, ret_h4: mtf.h4.ret,
    trend_d1: mtf.d1.trend, slope_d1: mtf.d1.slope, ret_d1: mtf.d1.ret,
    above_ema200: aboveEma200, dist_ema200: distEma200,
    vwap_dist: vwapDist, vwap_dist_atr: vwapDistAtr, above_vwap: aboveVwap,
    ema50_dist_atr: ema50DistAtr, vol_z20: volZ20, close_pos_in_range: closePos,
  }

  const rows: Float32Array[] = []
  const valid: boolean[] = []
  for (let i = 0; i < n; i++) {
    const arr = new Float32Array(FEATURE_ORDER.length)
    let ok = true
    for (let j = 0; j < FEATURE_ORDER.length; j++) {
      const v = map[FEATURE_ORDER[j]][i]
      arr[j] = v
      if (!Number.isFinite(v)) ok = false
    }
    rows.push(arr)
    valid.push(ok)
  }

  return {
    names: FEATURE_ORDER,
    rows,
    ema50, ema200, vwap, atr, rsi14, adx, macdHist,
    valid,
  }
}

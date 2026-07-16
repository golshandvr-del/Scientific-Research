// ============================================================================
// موتور سیگنال زنده — بازتولید منطق استراتژی برنده پروژه:
//   «استراتژی ۱۴: VWAP-Regime Selective ML (Long-only, BE=60٪)»  WR=61.6٪
//
// نکته علمی مهم و صادقانه:
//   مدل نهایی پروژه یک LightGBM ensemble (ONNX) است که در محیط MT5 اجرا می‌شود.
//   اجرای مدل ML در Cloudflare Workers ممکن نیست، لذا این ابزار آنلاین یک
//   «موتور امتیازدهی احتمالی شفاف» است که بر همان feature‌ها و همان قواعد رژیمِ
//   S14 بنا شده. این یک تقریب قابل‌توضیح از سیگنال است، نه خودِ مدل ONNX.
//   خروجی احتمال، به بازه‌ی تجربی WR پروژه (~۵۸–۶۶٪) کالیبره شده است.
// ============================================================================
import type { Candle } from './indicators'
import * as ind from './indicators'
import { findPivots, activeLevels, nearestSR, type SRLevel } from './structure'

// پارامترهای نهایی استراتژی برنده (از mt5_robot/model_meta.txt)
export const S14 = {
  HZ: 48,        // افق ۴۸ کندل = ۱۲ ساعت
  TP_M: 1.0,     // TP = 1.0 × ATR
  SL_M: 1.5,     // SL = 1.5 × ATR
  BE: 60.0,      // نقطه سربه‌سر (%)
  THR: 0.68,     // آستانه اطمینان مدل اصلی
}

export interface AnalysisResult {
  price: number
  atr: number
  ema50: number
  ema200: number
  vwap: number
  rsi14: number
  adx: number
  macdHist: number
  trend: 'up' | 'down' | 'range'
  regimeOk: boolean          // آیا context پایه (close>EMA50>EMA200) برقرار است؟
  activeBrain: 'bull' | 'bear' | 'none'  // مغز فعال طبق روتر سه‌مغزی
  // سیگنال
  direction: 'LONG' | 'SHORT' | 'NONE'
  probability: number        // احتمال برخورد TP قبل از SL (%)
  entryThreshold: number     // آستانهٔ ورود (٪) — برای نمایش هماهنگ در UI
  noEntryReason: string      // دلیل دقیق عدم ورود (خالی اگر سیگنال فعال باشد)
  confidence: 'high' | 'medium' | 'low'
  scoreBreakdown: { name: string; value: number; contrib: number; note: string }[]
  entry: number | null
  tp: number | null
  sl: number | null
  rr: string
  // سطوح
  levels: SRLevel[]
  resistance: SRLevel | null
  support: SRLevel | null
  // سناریوهای شکست
  breakoutScenarios: BreakoutScenario[]
}

export interface BreakoutScenario {
  level: number
  kind: 'res' | 'sup'
  label: string
  ifBreak: string           // اگر شکست، روند احتمالی
  probability: number       // درصد احتمال ادامه‌ی حرکت پس از شکست
  distancePct: number       // فاصله فعلی تا سطح (%)
}

// سیگموئید برای کالیبراسیون امتیاز به احتمال
function sigmoid(x: number) { return 1 / (1 + Math.exp(-x)) }

function last<T>(a: T[]): T { return a[a.length - 1] }

// محاسبه VWAP روزانه لنگرشده (session-anchored) — مثل features.py
function anchoredVWAP(c: Candle[]): number[] {
  const out = new Array<number>(c.length).fill(NaN)
  let cumPV = 0, cumV = 0, curDay = -1
  for (let i = 0; i < c.length; i++) {
    const day = Math.floor(c[i].time / 86400)
    if (day !== curDay) { cumPV = 0; cumV = 0; curDay = day }
    const tp = (c[i].high + c[i].low + c[i].close) / 3
    cumPV += tp * c[i].volume
    cumV += c[i].volume
    out[i] = cumV > 0 ? cumPV / cumV : c[i].close
  }
  return out
}

export function analyze(c: Candle[]): AnalysisResult {
  const n = c.length
  const close = c.map(x => x.close)
  const high = c.map(x => x.high)
  const low = c.map(x => x.low)
  const vol = c.map(x => x.volume)

  const ema20 = ind.ema(close, 20)
  const ema50 = ind.ema(close, 50)
  const ema100 = ind.ema(close, 100)
  const ema200 = ind.ema(close, 200)
  const atrArr = ind.atr(c, 14)
  const rsi14 = ind.rsi(close, 14)
  const { adx: adxArr, pdi, mdi } = ind.adx(c, 14)
  const { hist: macdHist } = ind.macd(close)
  const bb = ind.bollinger(close, 20, 2.0)
  const vwapArr = anchoredVWAP(c)
  const volMean20 = ind.sma(vol, 20)
  const volZ = ind.zscore(vol, 20)

  const i = n - 1
  const price = close[i]
  const atr = atrArr[i]
  const e50 = ema50[i], e200 = ema200[i], e100 = ema100[i], e20 = ema20[i]
  const vwap = vwapArr[i]

  // ---- تشخیص روند ----
  let trend: 'up' | 'down' | 'range' = 'range'
  if (price > e50 && e50 > e200) trend = 'up'
  else if (price < e50 && e50 < e200) trend = 'down'

  // context پایه استراتژی S14: فقط روند صعودی (long-only)
  const regimeOk = price > e50 && e50 > e200

  // ---- امتیازدهی احتمالی شفاف (بر پایه feature‌های S14) ----
  // هر عامل یک وزن دارد؛ مجموع وزن‌دار وارد سیگموئید کالیبره می‌شود.
  const breakdown: { name: string; value: number; contrib: number; note: string }[] = []
  let score = 0

  const add = (name: string, value: number, contrib: number, note: string) => {
    score += contrib
    breakdown.push({ name, value: Number(value.toFixed(4)), contrib: Number(contrib.toFixed(3)), note })
  }

  // پایه (bias صعودی ساختاری طلا که پروژه کشف کرد)
  add('bias_base', 1, 0.12, 'بایاس صعودی بلندمدت طلا (کشف پروژه)')

  // 1) رژیم روند (مهم‌ترین فیلتر S14)
  add('regime', regimeOk ? 1 : 0, regimeOk ? 0.55 : -1.2,
    regimeOk ? 'روند صعودی تأیید شد (close>EMA50>EMA200)' : 'خارج از رژیم صعودی — سیگنال long نامعتبر')

  // 2) فاصله از VWAP نرمال‌شده با ATR (snapback) — نزدیک/کمی زیر VWAP بهتر است
  const vwapDistAtr = atr ? (price - vwap) / atr : 0
  // بهترین ناحیه: بین -0.5 و +1.0 ATR از VWAP (پول‌بک سالم در روند صعودی)
  let vwapContrib = 0
  if (vwapDistAtr >= -0.5 && vwapDistAtr <= 1.0) vwapContrib = 0.35
  else if (vwapDistAtr > 1.0 && vwapDistAtr <= 2.0) vwapContrib = 0.05
  else if (vwapDistAtr > 2.0) vwapContrib = -0.30  // کشش بیش‌ازحد بالای VWAP → ریسک برگشت
  else vwapContrib = -0.15                          // خیلی زیر VWAP در روند صعودی
  add('vwap_dist_atr', vwapDistAtr, vwapContrib, 'موقعیت نسبت به VWAP روزانه')

  // 3) کشش از EMA50 (snapback) — دور نشدن بیش‌ازحد
  const ema50DistAtr = atr ? (price - e50) / atr : 0
  let emaContrib = 0
  if (ema50DistAtr >= 0 && ema50DistAtr <= 2.0) emaContrib = 0.22
  else if (ema50DistAtr > 3.5) emaContrib = -0.25
  add('ema50_dist_atr', ema50DistAtr, emaContrib, 'کشش قیمت از EMA50')

  // 4) RSI — ناحیه سالم روند صعودی (نه اشباع خرید شدید)
  const r = rsi14[i]
  let rsiContrib = 0
  if (r >= 45 && r <= 65) rsiContrib = 0.25
  else if (r > 75) rsiContrib = -0.30
  else if (r < 35) rsiContrib = -0.10
  add('rsi_14', r, rsiContrib, 'مومنتوم RSI')

  // 5) ADX — قدرت روند
  const a = adxArr[i]
  let adxContrib = 0
  if (a >= 20 && a <= 45) adxContrib = 0.20
  else if (a < 15) adxContrib = -0.12   // بازار بدون روند
  add('adx', a, adxContrib, 'قدرت روند (ADX)')

  // 6) MACD histogram مثبت — تأیید مومنتوم
  const mh = macdHist[i]
  add('macd_hist', mh, mh > 0 ? 0.15 : -0.10, mh > 0 ? 'مومنتوم مثبت' : 'مومنتوم منفی')

  // 7) قدرت حجم نسبی
  const vz = volZ[i]
  add('vol_z20', vz, vz > 0.3 ? 0.12 : (vz < -0.5 ? -0.08 : 0), 'حجم نسبی')

  // 8) موقعیت close در رنج کندل آخر (بستن قوی)
  const rng = high[i] - low[i]
  const closePos = rng > 0 ? (price - low[i]) / rng : 0.5
  add('close_pos', closePos, closePos > 0.6 ? 0.10 : (closePos < 0.3 ? -0.08 : 0), 'قدرت بسته‌شدن کندل')

  // 9) DI diff (جهت روند)
  const diDiff = pdi[i] - mdi[i]
  add('di_diff', diDiff, diDiff > 0 ? 0.10 : -0.10, 'جهت DI+/DI-')

  // ---- کالیبراسیون به احتمال ----
  // سیگموئید با شیب متعادل؛ سپس به بازه‌ی تجربی پروژه (~۴۵–۷۰٪) نگاشت می‌شود.
  const rawP = sigmoid(score * 1.15)
  // نگاشت خطی به بازه واقع‌گرایانه‌ی WR پروژه: مرکز حدود ۶۰٪
  const probability = Math.max(30, Math.min(78, 42 + rawP * 34))

  // ---- تصمیم سیگنال ----
  // اصلاح باگ ناهماهنگی: تصمیم دقیقاً بر پایهٔ همان probability نمایش‌داده‌شده است.
  //   شرط ورود = رژیم صعودی OK  و  probability ≥ آستانهٔ ۶۰٪.
  //   (اثر فاصلهٔ VWAP قبلاً درون خود score/probability لحاظ شده است، پس شرط
  //    جداگانهٔ vwapContrib حذف شد تا «درصد» و «سیگنال» هرگز متناقض نباشند.)
  const ENTRY_THRESHOLD = 60
  let direction: 'LONG' | 'SHORT' | 'NONE' = 'NONE'
  let activeBrain: 'bull' | 'bear' | 'none' = 'none'
  let entry: number | null = null, tp: number | null = null, sl: number | null = null
  // دلیل دقیق و صادقانهٔ عدم ورود (برای نمایش هماهنگ در UI)
  let noEntryReason = ''

  // آیا رژیم نزولی برقرار است؟ (آینهٔ رژیم صعودی — مغز نزولی S31)
  const bearRegimeOk = price < e50 && e50 < e200

  // ---- امتیاز نزولی متقارن (فقط برای مغز نزولی) ----
  // آینهٔ امتیاز صعودی: عوامل با علامت معکوس برای سیگنال SHORT.
  let bearScore = 0.12  // بایاس پایه در روند نزولی تأییدشده
  bearScore += bearRegimeOk ? 0.55 : -1.2
  // فاصله از VWAP (در روند نزولی: کمی بالای VWAP = پول‌بک فروش سالم)
  if (vwapDistAtr <= 0.5 && vwapDistAtr >= -1.0) bearScore += 0.35
  else if (vwapDistAtr < -2.0) bearScore -= 0.30
  // کشش از EMA50 به سمت پایین
  if (ema50DistAtr <= 0 && ema50DistAtr >= -2.0) bearScore += 0.22
  else if (ema50DistAtr < -3.5) bearScore -= 0.25
  // RSI معکوس (ناحیه سالم روند نزولی)
  if (r >= 35 && r <= 55) bearScore += 0.25
  else if (r < 25) bearScore -= 0.30
  else if (r > 65) bearScore -= 0.10
  // ADX همان
  if (a >= 20 && a <= 45) bearScore += 0.20
  else if (a < 15) bearScore -= 0.12
  // MACD منفی تأیید نزولی
  bearScore += mh < 0 ? 0.15 : -0.10
  // DI diff منفی
  bearScore += diDiff < 0 ? 0.10 : -0.10
  const bearRawP = sigmoid(bearScore * 1.15)
  const bearProbability = Math.max(30, Math.min(78, 42 + bearRawP * 34))

  if (regimeOk) {
    // مغز صعودی فعال
    activeBrain = 'bull'
    if (probability >= ENTRY_THRESHOLD) {
      direction = 'LONG'
      entry = price
      tp = price + S14.TP_M * atr
      sl = price - S14.SL_M * atr
    } else {
      noEntryReason = `مغز صعودی فعال است اما احتمال (${probability.toFixed(1)}%) زیر آستانهٔ ۶۰٪ است.`
    }
  } else if (bearRegimeOk) {
    // مغز نزولی فعال (S31) — پاسخ به User Note
    activeBrain = 'bear'
    if (bearProbability >= ENTRY_THRESHOLD) {
      direction = 'SHORT'
      entry = price
      tp = price - 1.4 * atr   // مغز نزولی: TP1.4/SL1.7
      sl = price + 1.7 * atr
    } else {
      noEntryReason = `مغز نزولی فعال است اما احتمال (${bearProbability.toFixed(1)}%) زیر آستانهٔ ۶۰٪ است.`
    }
  } else {
    // رنج — همهٔ مغزها غیرفعال
    activeBrain = 'none'
    noEntryReason = 'بازار در حالت رنج/بدون‌روند است — طبق تحقیق (S32) هیچ مغزی edge پایدار ندارد؛ عدم معامله.'
  }

  // احتمال نمایشی نهایی = احتمال مغزِ فعال
  const shownProbability = activeBrain === 'bear' ? bearProbability : probability

  let confidence: 'high' | 'medium' | 'low' = 'low'
  if (shownProbability >= 66) confidence = 'high'
  else if (shownProbability >= 60) confidence = 'medium'

  // ---- سطوح حمایت/مقاومت ----
  const pivots = findPivots(c, 5, 5)
  const levels = activeLevels(c, pivots, 0.0012, 60, 1500)
  const { resistance, support } = nearestSR(levels, price)

  // ---- سناریوهای شکست ----
  const scenarios: BreakoutScenario[] = []
  const mkScenario = (lvl: SRLevel): BreakoutScenario => {
    const distancePct = ((lvl.price - price) / price) * 100
    // احتمال ادامه پس از شکست بر اساس: قدرت سطح (touches)، هم‌راستایی با روند، ADX
    let p = 50
    if (lvl.kind === 'res') {
      // شکست مقاومت رو به بالا: در روند صعودی محتمل‌تر
      p = 48
      if (trend === 'up') p += 12
      if (a >= 20) p += 6
      if (mh > 0) p += 4
      p -= Math.min(lvl.touches * 2, 10)  // سطح قوی‌تر → مقاومت بیشتر برای شکست
      return {
        level: lvl.price, kind: 'res', distancePct,
        label: `مقاومت ${lvl.price.toFixed(2)} (${lvl.touches} برخورد)`,
        ifBreak: `شکست رو به بالا → ادامه روند صعودی به سمت هدف بعدی`,
        probability: Math.max(35, Math.min(80, p)),
      }
    } else {
      // شکست حمایت رو به پایین: در روند نزولی محتمل‌تر
      p = 48
      if (trend === 'down') p += 12
      if (a >= 20) p += 6
      if (mh < 0) p += 4
      p -= Math.min(lvl.touches * 2, 10)
      return {
        level: lvl.price, kind: 'sup', distancePct,
        label: `حمایت ${lvl.price.toFixed(2)} (${lvl.touches} برخورد)`,
        ifBreak: `شکست رو به پایین → آغاز/ادامه حرکت نزولی به حمایت بعدی`,
        probability: Math.max(35, Math.min(80, p)),
      }
    }
  }
  if (resistance) scenarios.push(mkScenario(resistance))
  if (support) scenarios.push(mkScenario(support))

  return {
    price, atr, ema50: e50, ema200: e200, vwap,
    rsi14: r, adx: a, macdHist: mh,
    trend, regimeOk, activeBrain,
    direction, probability: Number(shownProbability.toFixed(1)),
    entryThreshold: ENTRY_THRESHOLD, noEntryReason,
    confidence,
    scoreBreakdown: breakdown,
    entry, tp, sl,
    rr: activeBrain === 'bear'
      ? `TP 1.4×ATR / SL 1.7×ATR (مغز نزولی S31)`
      : `TP ${S14.TP_M}×ATR / SL ${S14.SL_M}×ATR (BE=${S14.BE}%)`,
    levels, resistance, support,
    breakoutScenarios: scenarios,
  }
}

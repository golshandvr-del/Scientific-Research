// ============================================================================
// sell_climax_s327.ts — لایهٔ S327 (احیای S174: Al Brooks Sell-Climax Exhaustion
//                        Reversal → LONG) با پارادایمِ RQS+
// ----------------------------------------------------------------------------
// خاستگاه: S174 (results/S174_BrooksSellClimaxReversal_NetProfit_237181_REJECTED.md)
//   ایدهٔ Brooks (Trading Price Action: TRENDS، فصلِ ۲): وقتی یک روندِ نزولیِ کشیده
//   به یک «بدنهٔ نزولیِ استثنایی-بزرگ» (sell-climax) می‌رسد ⇒ خالی‌شدنِ فروش
//   (sell vacuum) و خستگیِ فروشندگان ⇒ بازگشتِ سریعِ صعودی ⇒ ورودِ LONG.
//
//   در «عصرِ سودِ خالص» با TP>SL آزموده و رد شد (WR ۴۶.۹٪). تشخیصِ نو: ساختارِ
//   TP/SL معکوسِ ماهیتِ لایه بود؛ بازگشتِ پس از climax حرکتی *سریع و کوتاه* است ⇒
//   با TP<SL (fade) WR بالا می‌رود.
//
// احیا با RQS+ (سند: results/S327_SellClimaxReversal_XauEur_M5M15M30H1H4_98.md):
//   XAUUSD M5  — RQS+ 97.6 (WR 88.6٪، PF 2.78)
//   XAUUSD M15 — RQS+ 87.8 (WR 81.6٪، PF 1.54)
//   XAUUSD M30 — RQS+ 83.5 (WR 77.1٪، PF 1.37)
//   XAUUSD H1  — RQS+ 83.8 (WR 81.1٪، PF 1.39)
//   XAUUSD H4  — RQS+ 90.9 (WR 79.5٪، PF 1.56)
//   EURUSD M30 — RQS+ 86.9 (WR 84.2٪، PF 1.44)
//   (EURUSD M5 مرده؛ EURUSD M15 عمدتاً هم‌سیگنالِ S326 ⇒ به‌صورتِ مستقل وصل نمی‌شود.)
//
// استقلال از S326 (results/_s327_independence_test.json): روی نقاطِ *منحصربه‌فرد*
//   (غیرهمپوشان با S326) کیفیتِ S327 بالاتر یا برابرِ کل است (XAU M5: unique RQS 97.5،
//   PF 4.36؛ M30: unique RQS 89.5). ⇒ لایهٔ مستقل. برای پرهیز از شمارشِ دوباره،
//   در روتر پس از S326 صدا زده می‌شود (اگر S326 ENTRY داد، router زودتر return می‌کند).
//
// ماشهٔ ورود (LONG فقط):
//   (۱) کلایمکس:       کندلِ نزولی و |body| ≥ kBody × میانگینِ ۲۰-کندلیِ |body| (shift-safe)
//   (۲) قدرتِ بدنه:    body/range ≥ brMin (کندلِ پرقدرت، نه دوجی)  [اگر brMin>0]
//   (۳) عمقِ رگه:      streak(close<open) ≥ streakN                 [اگر streakN>0]
//   (۴) اشباعِ فروش:   RSI14 ≤ rsiLo
//   (۵) رژیمِ صعودیِ کلان: close > EMA200 (bounce، نه چاقوی در حالِ سقوط)
//   SL/TP شناورِ ATR-محور (TP<SL، غیر-رند): SL = slMult×ATR ، TP = tpMult×ATR
//
// بدونِ look-ahead: کلایمکس/رگه از کندل‌های بسته‌شده؛ سیگنال روی کندلِ جاری.
// ============================================================================

import { Candle, rsi, ema, atr } from './indicators'

export interface SellClimaxConfig {
  kBody: number        // آستانهٔ قدرتِ کلایمکس (× میانگینِ ۲۰-کندلیِ |body|)
  brMin: number        // آستانهٔ body/range (0 = خاموش)
  streakN: number      // حداقلِ رگهٔ نزولیِ منتهی (0 = خاموش)
  rsiMax: number       // آستانهٔ اشباعِ فروش (RSI14)
  emaTrend: number     // 200 — رژیمِ صعودیِ کلان
  atrP: number         // 14
  bodyMaLen: number    // 20 — پنجرهٔ میانگینِ بدنه
  slMult: number       // ضریبِ SL بر ATR (غیر-رند)
  tpMult: number       // ضریبِ TP بر ATR (غیر-رند، < slMult)
  maxHold: number      // سقفِ نگه‌داری (کندل)
}

// پارامترهای قفل‌شدهٔ برندهٔ RQS+ — منبعِ حقیقتِ واحد (per جفت‌ارز-تایم‌فریم).
// قانونِ «TP/SL مختصِ هر TF» + «اعدادِ غیر-رند» رعایت شده.
// منبع: results/_s327_sell_climax_*.json + گزارشِ S327.
export const SELL_CLIMAX_CFG: Record<string, SellClimaxConfig> = {
  'XAUUSD-M5':  { kBody: 1.6, brMin: 0.60, streakN: 2, rsiMax: 30, emaTrend: 200, atrP: 14, bodyMaLen: 20, slMult: 3.5, tpMult: 1.30, maxHold: 24 },
  'XAUUSD-M15': { kBody: 2.5, brMin: 0.45, streakN: 3, rsiMax: 35, emaTrend: 200, atrP: 14, bodyMaLen: 20, slMult: 2.8, tpMult: 1.00, maxHold: 16 },
  'XAUUSD-M30': { kBody: 2.5, brMin: 0.45, streakN: 2, rsiMax: 35, emaTrend: 200, atrP: 14, bodyMaLen: 20, slMult: 2.4, tpMult: 1.00, maxHold: 16 },
  'XAUUSD-H1':  { kBody: 1.6, brMin: 0.60, streakN: 3, rsiMax: 42, emaTrend: 200, atrP: 14, bodyMaLen: 20, slMult: 2.8, tpMult: 1.00, maxHold: 48 },
  'XAUUSD-H4':  { kBody: 2.5, brMin: 0.60, streakN: 0, rsiMax: 35, emaTrend: 200, atrP: 14, bodyMaLen: 20, slMult: 3.5, tpMult: 1.30, maxHold: 24 },
  'EURUSD-M30': { kBody: 1.6, brMin: 0.60, streakN: 2, rsiMax: 30, emaTrend: 200, atrP: 14, bodyMaLen: 20, slMult: 2.0, tpMult: 0.70, maxHold: 16 },
}

export interface SellClimaxSignal {
  active: boolean          // ماشهٔ LONG همین‌الان شلیک کرد؟
  approaching: boolean     // نزدیک: کلایمکس + رژیم صعودی برقرار، RSI هنوز کمی بالای آستانه
  streak: number           // طولِ رگهٔ نزولیِ فعلی
  rsiVal: number
  atrVal: number
  aboveTrend: boolean
  bodyVal: number          // |body| کندلِ جاری
  bodyMa: number           // میانگینِ ۲۰-کندلیِ |body| (shift-safe)
  bodyRatio: number        // body/range کندلِ جاری
  isClimax: boolean        // کندلِ کلایمکس (نزولیِ استثنایی-بزرگ)؟
  reason: string
  entry?: number
  sl?: number
  tp?: number
}

/** طولِ رگهٔ نزولیِ متوالی (close<open) تا اندیسِ جاری. */
function downStreak(open: number[], close: number[]): number {
  let run = 0
  for (let i = 0; i < close.length; i++) {
    if (close[i] < open[i]) run++
    else run = 0
  }
  return run
}

/**
 * محاسبهٔ سیگنالِ LONGِ S327 (Sell-Climax Reversal) از کندل‌ها.
 * cfg را از SELL_CLIMAX_CFG[`${pair}-${tf}`] بده.
 */
export function computeSellClimax(candles: Candle[], cfg: SellClimaxConfig): SellClimaxSignal {
  const n = candles.length
  const need = Math.max(cfg.emaTrend, cfg.atrP, cfg.bodyMaLen) + cfg.streakN + 2
  const empty: SellClimaxSignal = {
    active: false, approaching: false, streak: 0,
    rsiVal: NaN, atrVal: NaN, aboveTrend: false,
    bodyVal: NaN, bodyMa: NaN, bodyRatio: NaN, isClimax: false,
    reason: 'دادهٔ کافی برای RSI/EMA200/ATR/میانگینِ بدنه موجود نیست.',
  }
  if (n < need) return empty

  const open = candles.map(c => c.open)
  const close = candles.map(c => c.close)
  const high = candles.map(c => c.high)
  const low = candles.map(c => c.low)
  const rsiArr = rsi(close, 14)
  const emaArr = ema(close, cfg.emaTrend)
  const atrArr = atr(candles, cfg.atrP)

  const i = n - 1
  if ([rsiArr[i], emaArr[i], atrArr[i]].some(v => Number.isNaN(v)) || !(atrArr[i] > 0)) return empty

  const pNow = close[i]
  const bodyVal = Math.abs(close[i] - open[i])
  const rng = Math.max(high[i] - low[i], 1e-12)
  const bodyRatio = bodyVal / rng
  const isBear = close[i] < open[i]

  // میانگینِ ۲۰-کندلیِ |body| با shift(1): از کندلِ i-1 به عقب، بدونِ خودِ کندلِ جاری.
  let bodyMa = NaN
  if (i - 1 >= cfg.bodyMaLen) {
    let s = 0
    for (let k = i - cfg.bodyMaLen; k <= i - 1; k++) s += Math.abs(close[k] - open[k])
    bodyMa = s / cfg.bodyMaLen
  }

  const streak = downStreak(open, close)
  const aboveTrend = pNow > emaArr[i]
  const rsiVal = rsiArr[i]
  const atrVal = atrArr[i]

  // هستهٔ کلایمکس: کندلِ نزولی + بدنهٔ استثنایی-بزرگ (+ قدرتِ بدنه + عمقِ رگه)
  const bodyOk = Number.isFinite(bodyMa) && bodyMa > 0 && bodyVal >= cfg.kBody * bodyMa
  const brOk = cfg.brMin <= 0 || bodyRatio >= cfg.brMin
  const streakOk = cfg.streakN <= 0 || streak >= cfg.streakN
  const isClimax = isBear && bodyOk && brOk && streakOk

  const oversold = rsiVal <= cfg.rsiMax
  const active = isClimax && oversold && aboveTrend

  // نزدیک‌شدن: کلایمکس + رژیمِ صعودی برقرار، ولی RSI هنوز کمی بالای آستانه (≤ +8)
  const approaching = !active && isClimax && aboveTrend &&
    (rsiVal > cfg.rsiMax && rsiVal <= cfg.rsiMax + 8)

  let entry: number | undefined, sl: number | undefined, tp: number | undefined
  let reason: string
  const trendTxt = aboveTrend ? `قیمت بالای EMA${cfg.emaTrend} (روندِ کلان صعودی)` : `قیمت زیرِ EMA${cfg.emaTrend}`
  const bodyTimes = Number.isFinite(bodyMa) && bodyMa > 0 ? (bodyVal / bodyMa).toFixed(1) : '—'

  if (active) {
    entry = pNow
    sl = pNow - cfg.slMult * atrVal
    tp = pNow + cfg.tpMult * atrVal
    reason = `کلایمکسِ فروش (خستگیِ روندِ نزولی): کندلِ نزولیِ استثنایی-بزرگ با بدنهٔ ` +
      `${bodyTimes}× میانگینِ اخیر (فروشِ هیجانی/خالی‌شدنِ فروش)، RSI14 ${rsiVal.toFixed(1)} ≤ ${cfg.rsiMax} ` +
      `(اشباعِ فروش)، و ${trendTxt}. طبقِ Al Brooks این «sell vacuum» است: فروشندگان خسته شده‌اند و ` +
      `کوچک‌ترین خریدِ قوی، قیمت را سریع به میانگین برمی‌گرداند. ورود LONG با هدفِ کوچکِ سریع ` +
      `(TP=${cfg.tpMult}×ATR) و حدِ ضررِ بازترِ ${cfg.slMult}×ATR ⇒ WR بالا. ` +
      `SL=${sl.toFixed(2)} ، TP=${tp.toFixed(2)}. برگرفته از لایهٔ Sell-Climax Reversal (S327، احیای S174).`
  } else if (approaching) {
    reason = `کندلِ کلایمکسِ نزولی (بدنهٔ ${bodyTimes}× میانگین) شکل گرفت و ${trendTxt}؛ اما RSI14 هنوز ` +
      `${rsiVal.toFixed(1)} است (هدف: ≤ ${cfg.rsiMax}). اگر فروش کمی ادامه یابد و RSI به اشباعِ فروش برسد، ` +
      `سیگنالِ بازگشتیِ LONG صادر می‌شود. منتظرِ تأیید بمان. برگرفته از لایهٔ Sell-Climax Reversal (S327).`
  } else if (!aboveTrend) {
    reason = `${trendTxt} ⇒ در روندِ نزولیِ کلان «چاقوی در حالِ سقوط» نمی‌گیریم؛ این لایه فقط بازگشتِ ` +
      `کوتاه‌مدت پس از کلایمکس را در روندِ صعودیِ کلان شکار می‌کند. ورود نمی‌کنیم.`
  } else if (!isClimax) {
    if (!isBear) {
      reason = `کندلِ جاری صعودی است؛ کلایمکسِ فروش نیاز به یک کندلِ نزولیِ استثنایی-بزرگ دارد. منتظرِ فروشِ هیجانی می‌مانیم.`
    } else if (!bodyOk) {
      reason = `کندلِ نزولی هست اما بدنه‌اش به‌اندازهٔ کافی بزرگ نیست (${bodyTimes}× از ${cfg.kBody}× لازم). ` +
        `کلایمکس نیاز به فروشِ هیجانیِ استثنایی دارد؛ منتظرِ کندلِ نزولیِ بزرگ‌تر می‌مانیم.`
    } else if (!streakOk) {
      reason = `کلایمکس شکل گرفت اما رگهٔ نزولیِ منتهی کافی نیست (${streak} از ${cfg.streakN} کندلِ لازم). منتظرِ روندِ نزولیِ کشیده‌ترِ کوتاه‌مدت می‌مانیم.`
    } else {
      reason = `کندلِ کلایمکس هنوز به‌اندازهٔ کافی «پرقدرت» نیست (body/range=${bodyRatio.toFixed(2)} از ${cfg.brMin} لازم). منتظرِ کندلِ نزولیِ توپُرتر می‌مانیم.`
    }
  } else {
    reason = `کلایمکس و رژیم برقرارند اما RSI14=${rsiVal.toFixed(1)} هنوز اشباعِ فروش نیست ` +
      `(هدف ≤ ${cfg.rsiMax}). منتظرِ سیگنالِ تازه می‌مانیم.`
  }

  return {
    active, approaching, streak,
    rsiVal, atrVal, aboveTrend,
    bodyVal, bodyMa, bodyRatio, isClimax,
    reason, entry, sl, tp,
  }
}

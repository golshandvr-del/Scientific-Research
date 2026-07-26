// ============================================================================
// streak_reversal_s326.ts — لایهٔ S326 (احیای S22: Streak-Reversal / Mean-Reversion)
// ----------------------------------------------------------------------------
// خاستگاه: S22 (results/Streak_Reversal_MeanRev_58.md) — سوگیریِ serial-dependence:
//   پس از N کندلِ نزولیِ متوالی، احتمالِ برگشتِ صعودیِ کندلِ بعد ≈ ۵۳–۵۴٪ (edge خام).
//   در «عصرِ WR» به‌خاطرِ قیدِ خودسرانهٔ «≥۳ معامله/روز» رد شد.
//
// احیا با RQS+ (سند: results/S326_StreakReversal_XauEur_XauM5M30_EurM15_92_ACCEPTED.md):
//   XAUUSD M5  — RQS+ 92.0 (WR 84.4٪، PF 1.66، WF-4/4 مثبت)
//   XAUUSD M30 — RQS+ 87.4 (WR 79.6٪، PF 1.42، WF-4/4 مثبت)
//   EURUSD M15 — RQS+ 84.1 (WR 81.6٪، PF 1.32، WF-4/4 مثبت)
//   (H1/H4/EUR-M30 رد شدند: G4 Walk-Forward — یک fold منفی؛ به سایت وصل نمی‌شوند.)
//
// همپوشانی با لایه‌های فعال (results/_s326_overlap_audit.json): ≤۲.۵٪ ⇒ لایهٔ مستقل.
//   دلیل: لایه‌های فعال continuation با TP>SL‌اند؛ S326 یک contrarian reversion با
//   TP<SL در RSI اشباعِ فروش است ⇒ جایی که آن‌ها LONG نمی‌دهند.
//
// ماشهٔ ورود (LONG فقط — long-bias طلا/EUR در این کانفیگ‌ها):
//   (۱) رگهٔ نزولی:      streak(close<open) ≥ streakN
//   (۲) اشباعِ فروش:     RSI14 ≤ 30
//   (۳) رژیمِ صعودیِ کلان: close > EMA200
//   (۴) [M30] شتابِ رگه: |close[t-streak] − close[t]| ≥ runMin × ATR14
//   SL/TP شناورِ ATR-محور (TP<SL، غیر-رند): SL = slMult×ATR ، TP = tpMult×ATR
//
// بدونِ look-ahead: رگه از کندل‌های بسته‌شده شمرده می‌شود؛ سیگنال روی کندلِ جاری.
// ============================================================================

import { Candle, rsi, ema, atr } from './indicators'

export interface StreakRevConfig {
  streakN: number      // طولِ رگهٔ نزولیِ متوالی
  rsiMax: number       // 30 — آستانهٔ اشباعِ فروش
  emaTrend: number     // 200 — رژیمِ صعودیِ کلان
  runMinAtr: number    // شتابِ رگه بر ATR (0 = خاموش)
  atrP: number         // 14
  slMult: number       // ضریبِ SL بر ATR (غیر-رند)
  tpMult: number       // ضریبِ TP بر ATR (غیر-رند، < slMult)
  maxHold: number      // سقفِ نگه‌داری (کندل)
}

// پارامترهای قفل‌شدهٔ برندهٔ RQS+ — منبعِ حقیقتِ واحد (per جفت‌ارز-تایم‌فریم).
// قانونِ «TP/SL مختص هر TF» + «اعدادِ غیر-رند» رعایت شده.
export const STREAK_REV_CFG: Record<string, StreakRevConfig> = {
  'XAUUSD-M5':  { streakN: 5, rsiMax: 30, emaTrend: 200, runMinAtr: 0.0, atrP: 14, slMult: 3.1, tpMult: 1.15, maxHold: 24 },
  'XAUUSD-M30': { streakN: 5, rsiMax: 30, emaTrend: 200, runMinAtr: 2.5, atrP: 14, slMult: 3.5, tpMult: 1.30, maxHold: 48 },
  'EURUSD-M15': { streakN: 4, rsiMax: 30, emaTrend: 200, runMinAtr: 0.0, atrP: 14, slMult: 3.5, tpMult: 1.30, maxHold: 48 },
}

export interface StreakRevSignal {
  active: boolean          // ماشهٔ LONG همین‌الان شلیک کرد؟
  approaching: boolean     // نزدیک: رگه + رژیم صعودی برقرار ولی RSI هنوز بالای آستانه
  streak: number           // طولِ رگهٔ نزولیِ فعلی
  rsiVal: number
  emaVal: number
  atrVal: number
  aboveTrend: boolean
  runAmpAtr: number        // شتابِ رگه بر ATR
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
 * محاسبهٔ سیگنالِ LONGِ S326 از کندل‌ها.
 * cfg را از STREAK_REV_CFG[`${pair}-${tf}`] بده.
 */
export function computeStreakReversal(candles: Candle[], cfg: StreakRevConfig): StreakRevSignal {
  const n = candles.length
  const need = Math.max(cfg.emaTrend, cfg.atrP) + cfg.streakN + 2
  const empty: StreakRevSignal = {
    active: false, approaching: false, streak: 0,
    rsiVal: NaN, emaVal: NaN, atrVal: NaN, aboveTrend: false, runAmpAtr: 0,
    reason: 'دادهٔ کافی برای RSI/EMA200/ATR موجود نیست.',
  }
  if (n < need) return empty

  const open = candles.map(c => c.open)
  const close = candles.map(c => c.close)
  const rsiArr = rsi(close, 14)
  const emaArr = ema(close, cfg.emaTrend)
  const atrArr = atr(candles, cfg.atrP)

  const i = n - 1
  if ([rsiArr[i], emaArr[i], atrArr[i]].some(v => Number.isNaN(v)) || !(atrArr[i] > 0)) return empty

  const pNow = close[i]
  const streak = downStreak(open, close)
  const aboveTrend = pNow > emaArr[i]
  const rsiVal = rsiArr[i]
  const atrVal = atrArr[i]

  // (۴) شتابِ رگه بر ATR: |close[t-streak] − close[t]| / ATR
  let runAmpAtr = 0
  if (streak >= 1 && i - streak >= 0) {
    runAmpAtr = (close[i - streak] - pNow) / atrVal   // نزولی ⇒ مثبت
  }

  const streakOk = streak >= cfg.streakN
  const oversold = rsiVal <= cfg.rsiMax
  const runOk = cfg.runMinAtr <= 0 || runAmpAtr >= cfg.runMinAtr
  const active = streakOk && oversold && aboveTrend && runOk

  // نزدیک‌شدن: رگه + رژیمِ صعودی برقرار، شتاب کافی، ولی RSI هنوز کمی بالای آستانه (≤ +8)
  const approaching = !active && streakOk && aboveTrend && runOk &&
    (rsiVal > cfg.rsiMax && rsiVal <= cfg.rsiMax + 8)

  let entry: number | undefined, sl: number | undefined, tp: number | undefined
  let reason: string
  const trendTxt = aboveTrend ? `قیمت بالای EMA${cfg.emaTrend} (روندِ کلان صعودی)` : `قیمت زیرِ EMA${cfg.emaTrend}`

  if (active) {
    entry = pNow
    sl = pNow - cfg.slMult * atrVal
    tp = pNow + cfg.tpMult * atrVal
    reason = `بازگشتِ میانگین (mean-reversion): ${streak} کندلِ نزولیِ متوالی + RSI14 ` +
      `${rsiVal.toFixed(1)} ≤ ${cfg.rsiMax} (فروشِ هیجانی/اشباعِ فروش)، و ${trendTxt}. ` +
      `این «فنرِ فشرده به سمتِ پایین» است که معمولاً به‌سرعت برمی‌گردد. ورود LONG با هدفِ ` +
      `کوچکِ سریع (TP=${cfg.tpMult}×ATR) و حدِ ضررِ بازترِ ${cfg.slMult}×ATR ⇒ WR بالا. ` +
      `SL=${sl.toFixed(2)} ، TP=${tp.toFixed(2)}. برگرفته از لایهٔ Streak-Reversal (S326، احیای S22).`
  } else if (approaching) {
    reason = `${streak} کندلِ نزولیِ متوالی و ${trendTxt}؛ اما RSI14 هنوز ${rsiVal.toFixed(1)} است ` +
      `(هدف: ≤ ${cfg.rsiMax}). اگر فروش کمی ادامه یابد و RSI به اشباعِ فروش برسد، سیگنالِ ` +
      `بازگشتیِ LONG صادر می‌شود. منتظرِ تأیید بمان. برگرفته از لایهٔ Streak-Reversal (S326).`
  } else if (!aboveTrend) {
    reason = `${trendTxt} ⇒ در روندِ نزولیِ کلان «چاقوی در حالِ سقوط» نمی‌گیریم؛ این لایه فقط ` +
      `بازگشتِ کوتاه‌مدت را در روندِ صعودیِ کلان شکار می‌کند. ورود نمی‌کنیم.`
  } else if (!streakOk) {
    reason = `رگهٔ نزولیِ کافی نداریم (${streak} از ${cfg.streakN} کندلِ لازم). منتظرِ فروشِ ` +
      `متوالیِ عمیق‌ترِ کوتاه‌مدت می‌مانیم.`
  } else {
    reason = `رگه و رژیم برقرارند اما RSI14=${rsiVal.toFixed(1)} هنوز اشباعِ فروش نیست ` +
      `(هدف ≤ ${cfg.rsiMax})${cfg.runMinAtr > 0 ? ` یا شتابِ رگه کافی نیست (${runAmpAtr.toFixed(2)}×ATR از ${cfg.runMinAtr})` : ''}. ` +
      `منتظرِ سیگنالِ تازه می‌مانیم.`
  }

  return {
    active, approaching, streak,
    rsiVal, emaVal: emaArr[i], atrVal, aboveTrend, runAmpAtr,
    reason, entry, sl, tp,
  }
}

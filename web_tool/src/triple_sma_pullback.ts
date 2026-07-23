// ============================================================================
// triple_sma_pullback.ts — لایهٔ S211 (XAUUSD M15 LONG)
// ----------------------------------------------------------------------------
// Triple-SMA(13/100/200) stack-pullback + Vortex + Kaufman-ER
//
// خاستگاه: User Note (ادعای تریدر دربارهٔ سه SMA ۸/۷۰/۲۴۰). آزمونِ علمی نشان داد:
//   • «bounce» خام توهمِ سوگیریِ بصری بود (edge≈۰).
//   • اما ساختارِ چیدمان(stack)+pullback لبه دارد؛ مقادیرِ برنده ۱۳/۱۰۰/۲۰۰ (نه ۸/۷۰/۲۴۰).
//   • فیلترِ کمیابِ Vortex(VI+>VI−)+Kaufman-ER>0.20 هم سود و هم پایداری را افزود.
//
// نتیجهٔ بک‌تست (سهمِ مستقلِ ناهمپوشان، پذیرفته‌شده در رکورد):
//   XAUUSD M15 LONG — net +$6,338 ، WR 51.7٪ ، WF [924,268,1403,2636] ✅
//   رکورد +$252,471 → +$258,809. سند: results/S211_TripleSMA_Vortex_ER_Xauusd_M15_258809_52.md
//
// ماشهٔ ورود (LONG فقط — طلا بایاسِ صعودی دارد، L53):
//   (۱) چیدمانِ صعودی:   SMA13 > SMA100 > SMA200
//   (۲) pullback:        low[t-1] ≤ SMA13[t-1]   (لمسِ سایه از پایین)
//   (۳) بستنِ بازگشتی:   close[t] > SMA13[t]
//   (۴) تأییدِ روند:     VI+ > VI-  AND  Kaufman-ER(10) > 0.20
//   SL=150 point (1.50$) ، TP=300 point (3.00$)  [R:R = 1:2] ، max_hold=32 کندلِ M15
//
// بدونِ look-ahead: فقط از close/high/low تا اندیسِ جاری استفاده می‌شود.
// ============================================================================

import { Candle, sma, vortex, kaufmanER } from './indicators'

export interface TripleSMAConfig {
  fast: number       // 13
  mid: number        // 100
  slow: number       // 200
  vortexP: number    // 14
  erP: number        // 10
  erMin: number      // 0.20
  slPip: number      // 150 point (واحدِ point طلا = 0.01$)
  tpPip: number      // 300 point
  maxHold: number    // 32
}

// پارامترِ رکوردِ S211 — منبعِ حقیقتِ واحد برای سایت و local-mobile.
export const DEFAULT_TRIPLE_SMA: TripleSMAConfig = {
  fast: 13, mid: 100, slow: 200,
  vortexP: 14, erP: 10, erMin: 0.20,
  slPip: 150, tpPip: 300, maxHold: 32,
}

export interface TripleSMASignal {
  active: boolean          // آیا ماشهٔ LONG همین الان شلیک کرد؟
  approaching: boolean     // نزدیک به شلیک (چیدمان صعودی + قیمت روی pullback ولی تأیید ناقص)
  upStack: boolean         // چیدمانِ صعودیِ کامل SMA13>SMA100>SMA200
  fast: number
  mid: number
  slow: number
  viPlus: number
  viMinus: number
  er: number
  distFastPct: number      // فاصلهٔ قیمت از SMA13 بر حسب درصد
  reason: string
  // مقادیرِ پیشنهادیِ TP/SL (به واحدِ قیمت) وقتی active است
  entry?: number
  sl?: number
  tp?: number
}

/**
 * محاسبهٔ سیگنالِ LONGِ Triple-SMA از کندل‌های M15.
 * نیازمندِ حداقل slow+vortexP+2 کندل.
 */
export function computeTripleSMA(candles: Candle[], cfg: TripleSMAConfig = DEFAULT_TRIPLE_SMA): TripleSMASignal {
  const n = candles.length
  const need = cfg.slow + cfg.vortexP + 2
  const empty: TripleSMASignal = {
    active: false, approaching: false, upStack: false,
    fast: NaN, mid: NaN, slow: NaN, viPlus: NaN, viMinus: NaN, er: NaN, distFastPct: 0,
    reason: 'دادهٔ کافی برای میانگین‌ها/اندیکاتورها موجود نیست.',
  }
  if (n < need) return empty

  const close = candles.map(c => c.close)
  const low = candles.map(c => c.low)
  const sf = sma(close, cfg.fast)
  const sm = sma(close, cfg.mid)
  const ss = sma(close, cfg.slow)
  const { viPlus, viMinus } = vortex(candles, cfg.vortexP)
  const er = kaufmanER(close, cfg.erP)

  const i = n - 1
  const j = n - 2
  if ([sf[i], sm[i], ss[i], sf[j], viPlus[i], viMinus[i], er[i]].some(v => Number.isNaN(v))) return empty

  const pNow = close[i]

  // (۱) چیدمانِ صعودیِ کامل
  const upStack = sf[i] > sm[i] && sm[i] > ss[i]
  // (۲) pullback: سایهٔ کندلِ قبل به/زیرِ SMA13 رسیده
  const pulledBack = low[j] <= sf[j]
  // (۳) بستنِ بازگشتی بالای SMA13
  const closedBack = pNow > sf[i]
  // (۴) تأییدِ روند
  const trendOk = viPlus[i] > viMinus[i] && er[i] > cfg.erMin

  const active = upStack && pulledBack && closedBack && trendOk
  const distFastPct = sf[i] ? ((pNow - sf[i]) / sf[i]) * 100 : 0

  // نزدیک‌شدن: چیدمان صعودی برقرار و قیمت نزدیکِ SMA13 (در حالِ pullback) ولی تأیید ناقص
  const nearFast = Math.abs(distFastPct) < 0.12
  const approaching = !active && upStack && nearFast &&
    (!trendOk || !closedBack || !pulledBack)

  let reason: string
  const trendTxt = `VI+ ${viPlus[i].toFixed(2)} ${viPlus[i] > viMinus[i] ? '>' : '≤'} VI- ${viMinus[i].toFixed(2)}` +
    ` ، ER ${er[i].toFixed(2)} ${er[i] > cfg.erMin ? '>' : '≤'} ${cfg.erMin}`

  let entry: number | undefined, sl: number | undefined, tp: number | undefined
  if (active) {
    // point طلا = 0.01$ ⇒ pip موتور = 0.10$؛ اینجا slPip/tpPip بر حسبِ point است.
    // در فایلِ بک‌تست SL=150 point = 1.50$، TP=300 point = 3.00$.
    entry = pNow
    sl = pNow - cfg.slPip * 0.01
    tp = pNow + cfg.tpPip * 0.01
    reason = `ماشهٔ LONG شلیک شد: چیدمانِ صعودی SMA13(${sf[i].toFixed(2)})>SMA100(${sm[i].toFixed(2)})>` +
      `SMA200(${ss[i].toFixed(2)})، قیمت پس از pullback به SMA13 دوباره بالای آن بست (${pNow.toFixed(2)})، ` +
      `و تأییدِ روند برقرار است (${trendTxt}). ورود LONG. SL=${sl.toFixed(2)} ، TP=${tp.toFixed(2)} (R:R=1:2).`
  } else if (approaching) {
    const miss: string[] = []
    if (!pulledBack) miss.push('هنوز pullback به SMA13 کامل نشده')
    if (!closedBack) miss.push('قیمت هنوز بالای SMA13 نبسته')
    if (!trendOk) miss.push(`تأییدِ روند ناقص (${trendTxt})`)
    reason = `چیدمانِ صعودیِ سه SMA برقرار است و قیمت نزدیکِ SMA13 (فاصله ${distFastPct.toFixed(2)}%). ` +
      `منتظرِ تأییدها می‌مانیم: ${miss.join(' ؛ ')}. برگرفته از لایهٔ Triple-SMA (S211).`
  } else if (!upStack) {
    reason = `چیدمانِ سه SMA هنوز کاملاً صعودی نیست (SMA13 ${sf[i].toFixed(2)} / SMA100 ${sm[i].toFixed(2)} / ` +
      `SMA200 ${ss[i].toFixed(2)}). شرطِ رژیمِ روندِ صعودی برقرار نیست ⇒ ورود نمی‌کنیم.`
  } else {
    reason = `چیدمان صعودی است اما ماشهٔ تازه نداریم (pullback/بستنِ بازگشتی/تأییدِ روند هم‌زمان برقرار نشد؛ ` +
      `${trendTxt}). منتظرِ سیگنالِ تازه می‌مانیم.`
  }

  return {
    active, approaching, upStack,
    fast: sf[i], mid: sm[i], slow: ss[i],
    viPlus: viPlus[i], viMinus: viMinus[i], er: er[i], distFastPct,
    reason, entry, sl, tp,
  }
}

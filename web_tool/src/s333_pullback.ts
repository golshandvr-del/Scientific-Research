// ============================================================================
// s333_pullback.ts — لایهٔ احیاشدهٔ S333 (احیای S79 Trend-Pullback با RQS+)
// ----------------------------------------------------------------------------
// منشأ: S79 (Gold M5 Trend-Pullback) که در عصرِ «سودِ خالص» با R:R نامتقارن ساخته
//   شده بود (WR 39٪، RQS+ 24 — مردود). S333 آن را با روشِ علمیِ اصیل احیا می‌کند:
//
//   *** اصلِ روش‌شناختی (تصحیحِ کاربر) ***
//   افزایشِ WR فقط از «دقتِ محلِ ورود + فیلترِ رژیم» می‌آید، نه از هندسهٔ TP<SL.
//   همهٔ کانفیگ‌ها هندسهٔ منصفانه دارند: TP ≥ SL ⇒ breakeven ≤ 50٪ ⇒ WR واقعی است.
//
//   هسته:   روندِ صعودیِ کلان (EMA20>EMA100) + pullbackِ RSI21 + «تأییدِ بازگشت».
//   فیلتر:  رژیمِ persistence — Hurst (R/S) و در بعضی TF نسبتِ کارآییِ Kaufman (ER-Lucas29).
//   تأیید:  rsi_turn (RSI از کفِ خود برمی‌گردد) یا price_turn (close از high قبلی رد شد).
//
//   نتایجِ RQS+ (بک‌تستِ رویداد-محور، هزینهٔ واقعیِ حساب: spread=3.3pip, comm=0):
//     XAUUSD-M5   rsi_turn hu>0.57 ER>0.25  SL120/TP120  RQS 91.3  WR65.6٪ PF2.85 n64
//     XAUUSD-M15  none     hu>0.57           SL200/TP240  RQS 91.7  WR62.8٪ PF2.30 n51
//     XAUUSD-M30  price_turn hu>0.53         SL380/TP420  RQS 91.1  WR66.7٪ PF2.48 n42
//     XAUUSD-H1   none     hu>0.50 ER>0.25   SL450/TP520  RQS 89.8  WR62.2٪ PF1.85 n74
//   (H4 و EURUSD رد شدند — EUR: لبه‌ای نیست، WR≈50٪ PF≈1.0؛ کنترلِ long-biasِ طلا.)
//
//   همهٔ پارامترها غیر-رند/واقعی (اشتباه #۷)، per-TF جدا (اشتباه #۶).
//   verbatim از strategies/s333_s79_pullback_revival.py پورت شده.
// ============================================================================

import { ema, rsi, adx, type Candle } from './indicators'
import { hurstSeries } from './squeeze_s332'
import { type RouterDecision, type RegimeInfo } from './router'
import type { AnalysisResult } from './signal'
import { rawToDecision, type RawSignal, type DecideMeta } from './revived_strategies'

const GOLD_PIP = 0.1
const nz = (v: number) => (Number.isFinite(v) ? v : 0)
const last = <T,>(a: T[]) => a[a.length - 1]

// ---------------------------------------------------------------------------
// نسبتِ کارآییِ Kaufman روی پنجرهٔ Lucas — verbatim از _er_v پایتون (بانکِ اندیکاتور).
//   ER[i] = |close[i]-close[i-p]| / Σ_{k=0..p-1} |close[i-k]-close[i-k-1]|
// ---------------------------------------------------------------------------
export function erLucasSeries(close: number[], p = 29): number[] {
  const n = close.length
  const out = new Array(n).fill(NaN)
  for (let i = p; i < n; i++) {
    const ch = Math.abs(close[i] - close[i - p])
    let v = 0
    for (let k = 0; k < p; k++) v += Math.abs(close[i - k] - close[i - k - 1])
    out[i] = v ? ch / v : 0
  }
  return out
}

export type ConfirmKind = 'none' | 'rsi_turn' | 'price_turn'

export interface S333Config {
  id: string            // 'XAUUSD-M5' ..
  emaFast: number       // 20
  emaSlow: number       // 100
  rsiP: number          // 21
  rsiTh: number         // 32/35
  confirm: ConfirmKind
  hurstTh: number       // 0.50..0.57
  erTh?: number         // 0.25 (فقط M5/H1)
  slPip: number         // غیر-رند
  tpPip: number         // TP >= SL همیشه
  maxHoldBars: number
}

// پیکربندیِ برندهٔ هر TF (از BEST_CFG پایتون — RQS+ ≥ 89).
export const S333_CFG: Record<string, S333Config> = {
  'XAUUSD-M5':  { id: 'XAUUSD-M5',  emaFast: 20, emaSlow: 100, rsiP: 21, rsiTh: 35, confirm: 'rsi_turn',
                  hurstTh: 0.57, erTh: 0.25, slPip: 120, tpPip: 120, maxHoldBars: 96 },
  'XAUUSD-M15': { id: 'XAUUSD-M15', emaFast: 20, emaSlow: 100, rsiP: 21, rsiTh: 32, confirm: 'none',
                  hurstTh: 0.57,             slPip: 200, tpPip: 240, maxHoldBars: 96 },
  'XAUUSD-M30': { id: 'XAUUSD-M30', emaFast: 20, emaSlow: 100, rsiP: 21, rsiTh: 35, confirm: 'price_turn',
                  hurstTh: 0.53,             slPip: 380, tpPip: 420, maxHoldBars: 80 },
  'XAUUSD-H1':  { id: 'XAUUSD-H1',  emaFast: 20, emaSlow: 100, rsiP: 21, rsiTh: 32, confirm: 'none',
                  hurstTh: 0.50, erTh: 0.25, slPip: 450, tpPip: 520, maxHoldBars: 64 },
}

// ---------------------------------------------------------------------------
// computeS333 — سیگنالِ خامِ لایه برای «کندلِ جاری» (causal، بدونِ look-ahead).
//   وضعیت‌ها: active (ماشهٔ ورود) / approaching (pullback در جریان، منتظرِ تأیید) / خنثی.
// ---------------------------------------------------------------------------
export function computeS333(candles: Candle[], cfg: S333Config): RawSignal {
  const n = candles.length
  const slDist = cfg.slPip * GOLD_PIP
  const tpDist = cfg.tpPip * GOLD_PIP
  const need = Math.max(cfg.emaSlow, 64) + 5   // 64 = پنجرهٔ Hurst
  if (n < need) {
    return { active: false, approaching: false, direction: 'LONG', slDist, tpDist,
      maxHoldBars: cfg.maxHoldBars, reason: 'دادهٔ کافی برای محاسبهٔ روند/رژیم موجود نیست.',
      indicators: [] }
  }

  const close = candles.map(c => c.close)
  const high = candles.map(c => c.high)
  const ef = ema(close, cfg.emaFast)
  const es = ema(close, cfg.emaSlow)
  const r = rsi(close, cfg.rsiP)
  const hu = hurstSeries(close, 64)
  const er = cfg.erTh != null ? erLucasSeries(close, 29) : null

  const i = n - 1
  const upTrend = ef[i] > es[i]
  const huOk = nz(hu[i]) > cfg.hurstTh
  const erOk = er == null ? true : nz(er[i]) > (cfg.erTh as number)

  // ---- تأییدِ بازگشت (دقتِ ورود) ----
  let coreActive = false
  let dipInProgress = false
  if (cfg.confirm === 'none') {
    coreActive = upTrend && r[i] < cfg.rsiTh
    dipInProgress = upTrend && r[i] < cfg.rsiTh + 5 && r[i] >= cfg.rsiTh
  } else if (cfg.confirm === 'rsi_turn') {
    // کندلِ قبل در ناحیهٔ اشباع بود، حالا RSI از کفِ خود برمی‌گردد و هنوز < th+10
    coreActive = upTrend && r[i - 1] < cfg.rsiTh && r[i] > r[i - 1] && r[i] < cfg.rsiTh + 10
    dipInProgress = upTrend && r[i] < cfg.rsiTh   // هنوز در کف، منتظرِ چرخش
  } else { // price_turn
    const dipped = r[i] < cfg.rsiTh || r[i - 1] < cfg.rsiTh
    coreActive = upTrend && dipped && close[i] > high[i - 1]
    dipInProgress = upTrend && dipped && close[i] <= high[i - 1]
  }

  const active = coreActive && huOk && erOk
  const approaching = !active && dipInProgress && huOk

  const indicators: RouterDecision['indicators'] = [
    { name: `روندِ کلان EMA${cfg.emaFast}>EMA${cfg.emaSlow}`,
      value: upTrend ? 'صعودی ✓' : 'صعودی نیست', status: upTrend ? 'ok' : 'bad' },
    { name: `RSI${cfg.rsiP} (pullback < ${cfg.rsiTh})`,
      value: r[i].toFixed(1), status: r[i] < cfg.rsiTh ? 'ok' : (r[i] < cfg.rsiTh + 10 ? 'warn' : 'neutral') },
    { name: 'رژیمِ Hurst (پایداریِ روند)',
      value: `${nz(hu[i]).toFixed(2)} (> ${cfg.hurstTh})`, status: huOk ? 'ok' : 'bad' },
  ]
  if (er != null) {
    indicators.push({ name: 'نسبتِ کارآیی ER-Lucas29',
      value: `${nz(er[i]).toFixed(2)} (> ${cfg.erTh})`, status: erOk ? 'ok' : 'bad' })
  }
  indicators.push({ name: 'تأییدِ بازگشت',
    value: cfg.confirm === 'none' ? 'ورودِ مستقیمِ pullback'
      : (cfg.confirm === 'rsi_turn' ? 'چرخشِ RSI از کف' : 'شکستِ high کندلِ قبل'),
    status: coreActive ? 'ok' : (dipInProgress ? 'warn' : 'neutral') })

  const reason = active
    ? `روندِ صعودیِ کلان (EMA${cfg.emaFast}>EMA${cfg.emaSlow}) پابرجاست و در رژیمِ پایدار ` +
      `(Hurst=${nz(hu[i]).toFixed(2)}${er != null ? `، ER=${nz(er[i]).toFixed(2)}` : ''}) یک ` +
      `اصلاحِ RSI${cfg.rsiP} تأیید‌شده رخ داد ⇒ خرید در پولبک. TP=${cfg.tpPip}pip، SL=${cfg.slPip}pip ` +
      `(هندسهٔ منصفانه، R:R≥1). WR واقعیِ بک‌تست ≈ ۶۳–۶۷٪.`
    : approaching
      ? `روند صعودی و یک اصلاحِ RSI در جریان است؛ رژیم پایدار است اما هنوز «تأییدِ بازگشت» ` +
        `کامل نشده.`
      : upTrend
        ? `روند صعودی است اما یا اصلاحی در جریان نیست یا رژیم پایدار نیست (Hurst=${nz(hu[i]).toFixed(2)}).`
        : `روندِ کلان صعودی نیست؛ این لایه فقط در روندِ صعودی خرید می‌دهد.`

  return {
    active, approaching, direction: 'LONG', slDist, tpDist, maxHoldBars: cfg.maxHoldBars,
    reason,
    approachReason: approaching ? 'منتظرِ «تأییدِ بازگشتِ» pullback (چرخشِ RSI یا شکستِ high کندلِ قبل).' : undefined,
    indicators,
  }
}

// ---------------------------------------------------------------------------
// decideS333 — آداپترِ RouterDecision (هم‌تراز با سایرِ لایه‌های احیاشده).
// ---------------------------------------------------------------------------
export function decideS333(cfg: S333Config, a: AnalysisResult, candles: Candle[],
                           capital = 10000, riskPct = 1.0): RouterDecision {
  const raw = computeS333(candles, cfg)
  const { adx: adxArr } = adx(candles, 14)
  const reg: RegimeInfo = {
    regime: raw.active || raw.approaching ? 'trend_up' : 'range',
    efficiencyRatio: 0, trendy: raw.active || raw.approaching,
    adx: nz(last(adxArr)), activeStream: 'bull', bucket: 's333_pullback',
  }
  const meta: DecideMeta = {
    code: 'S333', name: 'خرید در پولبکِ روند (Trend-Pullback)', kind: 'ma-confluence' as any,
    manageStyle: 'structural-trail', beTriggerR: 1.0,
    manageNote: 'پس از ۱R سود، SL را به بریک‌ایون ببر؛ سپس زیرِ EMA20 تریل کن. ' +
      'اگر روند شکست (close < EMA100) یا Hurst به زیرِ آستانه افتاد، زودتر خارج شو.',
    filters: [`روندِ EMA${cfg.emaFast}>EMA${cfg.emaSlow}`, `pullbackِ RSI${cfg.rsiP}<${cfg.rsiTh}`,
      `رژیمِ Hurst>${cfg.hurstTh}`,
      ...(cfg.erTh != null ? [`ER-Lucas29>${cfg.erTh}`] : []),
      cfg.confirm === 'none' ? 'ورودِ مستقیم' : (cfg.confirm === 'rsi_turn' ? 'تأییدِ چرخشِ RSI' : 'تأییدِ شکستِ high')],
  }
  return rawToDecision(raw, meta, cfg.id, a.price, reg, capital, riskPct)
}

// آداپترِ رجیستری: کارخانهٔ لایه (هم‌تراز با s327Layer/s330Layer).
export function s333Layer(cfg: S333Config) {
  return (a: AnalysisResult, candles: Candle[], capital = 10000, riskPct = 1.0) =>
    decideS333(cfg, a, candles, capital, riskPct)
}

// ============================================================================
// micro_channel_s340.ts — لایهٔ نوِ S340 (Al Brooks «Micro Channels» — فصلِ ۱۶)
// ----------------------------------------------------------------------------
// لبهٔ اصیلِ ادامهٔ روند/مومنتوم روی XAUUSD-H4 (LONG):
//   micro channel = رشتهٔ ۳–۷ کندلِ فوق‌فشردهٔ صعودی (higher-high & higher-low،
//   overlap کم، بدنه‌های صعودیِ غالب). «most breakouts fail» ⇒ اولین شکستِ نزولیِ
//   micro channel (failed pullback) به‌شدت خریده می‌شود ⇒ ورودِ with-trend.
//
//   XAUUSD-H4 → ema8>ema21 (رژیم) · k∈[3,7] · body≥0.40 · closePos≥0.45 · overlap≤0.70
//               SL=520 / TP=780 pip، maxHold=20 → RQS+ = 92.6 (WR 65.6٪، PF 2.13، +$1,080)
//
// منبعِ کامل: results/S340_BrooksMicroChannel_Xauusd_H4_rqs93.md
// کدِ منبعِ حقیقتِ Python: strategies/s340_brooks_micro_channel.py (پورتِ verbatim)
//
// همپوشانی (ثبت‌شده): با S327 = ۰٪، با S332 = ۸.۲٪ ⇒ لبهٔ مستقل (نه فیلتر).
// ماژولار/توسعه‌پذیر: فایلِ کاملاً مستقل؛ افزودنش فقط یک ورودی در CARD_LAYERS['XAUUSD-H4']
//   می‌خواهد و هیچ لایهٔ دیگری را دست نمی‌زند.
// ============================================================================

import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision } from './router'
import { ema } from './indicators'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'
import type { RegimeInfo } from './router'

const GOLD_PIP = 0.1

// ---------------------------------------------------------------------------
export interface S340Config {
  id: string            // XAUUSD-H4
  tfFa: string
  kMin: number          // 3
  kMax: number          // 7
  emaFast: number       // 8
  emaSlow: number       // 21
  bodyMin: number       // 0.40 — کف نسبتِ بدنه‌های صعودیِ قویِ درونِ micro channel
  closePosMin: number   // 0.45 — قدرتِ failed-breakout ((c-l)/rng)
  overlapMax: number    // 0.70 — سقفِ همپوشانیِ کندل‌ها (فشردگی)
  slPip: number
  tpPip: number
  maxHold: number
  rqs: number
}

export const S340_CFG: Record<string, S340Config> = {
  'XAUUSD-H4': {
    id: 'XAUUSD-H4', tfFa: 'H4',
    kMin: 3, kMax: 7, emaFast: 8, emaSlow: 21,
    bodyMin: 0.40, closePosMin: 0.45, overlapMax: 0.70,
    slPip: 520, tpPip: 780, maxHold: 20, rqs: 92.6,
  },
}

// ---------------------------------------------------------------------------
// computeS340 — منطقِ verbatim از micro_channel_signals روی آخرین کندلِ بستهٔ i=n-1
// ---------------------------------------------------------------------------
export function computeS340(candles: Candle[], cfg: S340Config): RawSignal {
  const n = candles.length
  const o = candles.map(c => c.open)
  const h = candles.map(c => c.high)
  const l = candles.map(c => c.low)
  const c = candles.map(x => x.close)

  const slDist = cfg.slPip * GOLD_PIP
  const tpDist = cfg.tpPip * GOLD_PIP

  const emptyInd: RouterDecision['indicators'] = [
    { name: 'داده', value: 'ناکافی', status: 'neutral' },
  ]
  const need = cfg.kMax + 3
  if (n < need + cfg.emaSlow) {
    return {
      active: false, approaching: false, direction: 'LONG',
      slDist, tpDist, maxHoldBars: cfg.maxHold,
      reason: 'دادهٔ کافی برای تشخیصِ micro channel موجود نیست.',
      indicators: emptyInd,
    }
  }

  const ef = ema(c, cfg.emaFast)
  const es = ema(c, cfg.emaSlow)
  const rng = (idx: number) => Math.max(h[idx] - l[idx], 1e-9)
  const body = (idx: number) => c[idx] - o[idx]
  const bodyFrac = (idx: number) => Math.abs(body(idx)) / rng(idx)

  const i = n - 1        // آخرین کندلِ بسته‌شده (سیگنال روی i، ورود در کندلِ بعد)

  // --- رژیمِ صعودی ---
  const trendUp = isFinite(ef[i]) && isFinite(es[i]) && ef[i] > es[i]

  // --- ماشهٔ failed downside breakout روی کندلِ i ---
  const isPullback = l[i] < l[i - 1]
  const closePos = (c[i] - l[i]) / rng(i)
  const failed = isPullback && closePos >= cfg.closePosMin

  // --- شمارشِ طولِ micro channel پیش از pullback (کندل‌های i-1, i-2, ...) ---
  let mcLen = 0
  let strongBody = 0
  let j = i - 1
  while (j >= 1) {
    const asc = (h[j] > h[j - 1]) && (l[j] >= l[j - 1])
    if (!asc) break
    const ovLo = Math.max(l[j], l[j - 1])
    const ovHi = Math.min(h[j], h[j - 1])
    const overlap = Math.max(0, ovHi - ovLo) / rng(j)
    if (overlap > cfg.overlapMax) break
    mcLen += 1
    if (body(j) > 0 && bodyFrac(j) >= 0.35) strongBody += 1
    j -= 1
  }
  const lenOk = mcLen >= cfg.kMin && mcLen <= cfg.kMax
  const bodyOk = mcLen > 0 && (strongBody / mcLen) >= cfg.bodyMin

  const active = trendUp && failed && lenOk && bodyOk
  // approaching: micro channelِ معتبر و رژیمِ صعودی هست، اما هنوز failed-pullback رخ نداده
  const approaching = !active && trendUp && lenOk && bodyOk && !failed

  const indicators: RouterDecision['indicators'] = [
    { name: 'رژیمِ صعودی (EMA8 > EMA21)',
      value: trendUp ? 'صعودی ✔' : 'غیرصعودی ✘', status: trendUp ? 'ok' : 'bad' },
    { name: `طولِ micro channel در بازهٔ [${cfg.kMin},${cfg.kMax}]`,
      value: `${mcLen} کندل` + (lenOk ? ' ✔' : ' ✘'), status: lenOk ? 'ok' : 'neutral' },
    { name: `بدنه‌های صعودیِ قوی ≥ ${Math.round(cfg.bodyMin * 100)}٪`,
      value: mcLen > 0 ? `${Math.round(100 * strongBody / mcLen)}٪` + (bodyOk ? ' ✔' : ' ✘') : '—',
      status: bodyOk ? 'ok' : 'neutral' },
    { name: `failed pullback (بازگشتِ close، (c-l)/rng ≥ ${cfg.closePosMin})`,
      value: isPullback ? (closePos.toFixed(2) + (failed ? ' ✔' : ' ✘')) : 'بدونِ pullback',
      status: failed ? 'ok' : 'neutral' },
  ]

  let reason: string
  if (active) {
    reason = `micro channelِ صعودیِ ${mcLen}‌کندلی + شکستِ نزولیِ اول که fail شد (close برگشت بالا) ⇒ ورودِ خریدِ ادامهٔ روند.`
  } else if (approaching) {
    reason = `micro channelِ صعودیِ ${mcLen}‌کندلی معتبر است؛ منتظرِ یک pullbackِ کوچک که fail شود (close نزدیکِ بالا ببندد) برای ورود.`
  } else if (!trendUp) {
    reason = 'رژیمِ صعودی برقرار نیست (EMA8 ≤ EMA21) — micro channelِ صعودی معنا ندارد.'
  } else if (!lenOk) {
    reason = mcLen > cfg.kMax
      ? `رشتهٔ صعودی ${mcLen} کندل است (بیش از ${cfg.kMax}) — احتمالِ climax/برگشت؛ ورود نمی‌کنیم.`
      : `micro channelِ فشرده‌ای (حداقل ${cfg.kMin} کندل) هنوز شکل نگرفته است.`
  } else {
    reason = 'بدنه‌های micro channel هنوز به‌قدرِ کافی قوی/صعودی نیستند.'
  }

  return {
    active, approaching, direction: 'LONG',
    slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason,
    approachReason: approaching
      ? 'منتظرِ اولین pullbackِ کوچک که fail شود (بازگشتِ close نزدیکِ بالا)' : undefined,
    indicators,
  }
}

// ---------------------------------------------------------------------------
export function decideS340(
  cfg: S340Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS340(candles, cfg)
  const price = a.price

  const reg: RegimeInfo = {
    regime: 'trend_up', efficiencyRatio: 0, trendy: true,
    adx: 0, activeStream: 'bull', bucket: `s340_${cfg.tfFa.toLowerCase()}`,
  }

  const meta: DecideMeta = {
    code: 'S340',
    name: `کانالِ ریزِ ادامهٔ روند (Brooks Micro-Channel · ${cfg.tfFa})`,
    kind: 'micro_channel' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote: `هدف/حدِ ثابتِ مخصوصِ ${cfg.tfFa} (${cfg.tpPip}/${cfg.slPip} pip). ` +
      `تا برخورد به TP/SL یا پایانِ ${cfg.maxHold} کندل نگه‌دار؛ اگر رژیمِ صعودی (EMA8>EMA21) معکوس شد یا ` +
      `کندلِ برگشتیِ قوی زیرِ کفِ pullback بسته شد، خروجِ زودهنگام را بسنج.`,
    filters: [
      'رژیمِ صعودی EMA8>EMA21',
      `طولِ micro channel ∈ [${cfg.kMin},${cfg.kMax}] (نه climax)`,
      `بدنه‌های صعودیِ قوی ≥ ${Math.round(cfg.bodyMin * 100)}٪`,
      'failed downside breakout (بازگشتِ close)',
    ],
  }

  return rawToDecision(raw, meta, cfg.id, price, reg, capital, riskPct)
}

// ============================================================================
// trend_from_open_s344.ts — لایهٔ نوِ S344 (Al Brooks «Trend from the Open &
//   Small Pullback Trends» — فصلِ ۲۳ کتابِ Trading Price Action: TRENDS)
// ----------------------------------------------------------------------------
// لبهٔ اصیلِ «open-extreme first-pullback continuation» روی XAUUSD-M15 (SHORT):
//   روزی که در چند کندلِ نخست یک اکسترمم می‌سازد (opening-range کوچک نسبت به ADR)
//   و بعد با-روند ادامه می‌دهد؛ در اولین pullbackِ کوچک با جهتِ اسپایکِ اولیه وارد می‌شویم.
//
//   XAUUSD-M15 SHORT → n_open=4 · f_range=0.20 · pull_max=0.62 · min_spike=0.20
//     فیلترِ رژیمِ بانک r2h: r2(34) ≥ 0.30  &  hurst(55) ≥ 0.52
//     SL=220 / TP=340 pip، maxHold=32 → RQS+ = 91.4 (WR 64.1٪، PF 2.08، +$1,571)
//     لبهٔ مستقل (خارج از پنجره‌های زمان-محورِ S139..S144): RQS+ = 92.9 (n=57)
//
// منبعِ کامل: results/S344_BrooksTrendFromOpen_Xauusd_M15_rqs91.md
// کدِ منبعِ حقیقتِ Python: strategies/s344_brooks_trend_from_open.py (پورتِ verbatim)
//
// همپوشانی (ثبت‌شده): با زمان-محورِ S139..S144 = ۳۸٪ ⇒ لبهٔ مستقل (نه فیلتر).
//   نخستین لبهٔ SHORT روی کارتِ XAUUSD-M15 (بقیهٔ لایه‌های این کارت LONG بودند).
// ماژولار/توسعه‌پذیر: فایلِ کاملاً مستقل؛ افزودنش فقط یک ورودی در CARD_LAYERS['XAUUSD-M15'].
// ============================================================================

import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'
import type { RegimeInfo } from './router'
import { r2Series, hurstSeries } from './squeeze_s332'

const GOLD_PIP = 0.1

// ---------------------------------------------------------------------------
export interface S344Config {
  id: string            // XAUUSD-M15
  tfFa: string
  side: 'LONG' | 'SHORT'
  nOpen: number         // 4 — تعدادِ کندلِ opening-range
  fRange: number        // 0.20 — سقفِ نسبتِ opening-range به ADR
  pullMax: number       // 0.62 — سقفِ نسبتِ pullback به leg
  minSpike: number      // 0.20 — حداقل نسبتِ leg به ADR
  adrLookbackDays: number   // 14
  r2Period: number      // 34
  r2Min: number         // 0.30
  hurstPeriod: number   // 55
  hurstMin: number      // 0.52
  slPip: number
  tpPip: number
  maxHold: number
  rqs: number
}

export const S344_CFG: Record<string, S344Config> = {
  'XAUUSD-M15': {
    id: 'XAUUSD-M15', tfFa: 'M15', side: 'SHORT',
    nOpen: 4, fRange: 0.20, pullMax: 0.62, minSpike: 0.20,
    adrLookbackDays: 14, r2Period: 34, r2Min: 0.30, hurstPeriod: 55, hurstMin: 0.52,
    slPip: 220, tpPip: 340, maxHold: 32, rqs: 91.4,
  },
}

// ---------------------------------------------------------------------------
// کمکی: شناسهٔ روزِ UTC (floor به روز) از timestampِ ثانیه‌ای
// ---------------------------------------------------------------------------
function dayId(tsSec: number): number {
  return Math.floor(tsSec / 86400)
}

// ADR (میانگینِ دامنهٔ lookback روزِ قبل) در روزِ کندلِ i — کاملاً causal، منطبق با پایتون.
function adrForDay(
  h: number[], l: number[], days: number[], lookback: number,
): Map<number, number> {
  const n = h.length
  const uniq: number[] = []
  const dayHi = new Map<number, number>()
  const dayLo = new Map<number, number>()
  for (let i = 0; i < n; i++) {
    const d = days[i]
    if (!dayHi.has(d)) { dayHi.set(d, h[i]); dayLo.set(d, l[i]); uniq.push(d) }
    else {
      if (h[i] > (dayHi.get(d) as number)) dayHi.set(d, h[i])
      if (l[i] < (dayLo.get(d) as number)) dayLo.set(d, l[i])
    }
  }
  const dayRange = new Map<number, number>()
  for (const d of uniq) dayRange.set(d, (dayHi.get(d) as number) - (dayLo.get(d) as number))
  const adrOfDay = new Map<number, number>()
  for (let idx = 0; idx < uniq.length; idx++) {
    const start = Math.max(0, idx - lookback)
    const prev = uniq.slice(start, idx)
    if (prev.length) {
      let s = 0
      for (const p of prev) s += dayRange.get(p) as number
      adrOfDay.set(uniq[idx], s / prev.length)
    } else {
      adrOfDay.set(uniq[idx], NaN)
    }
  }
  return adrOfDay
}

// ---------------------------------------------------------------------------
// computeS344 — منطقِ verbatim از trend_from_open_signals، ارزیابی روی «امروزِ جاری»
//   (روزِ کندلِ آخر i=n-1). سیگنال وقتی فعال است که کندلِ آخر همان اولین pullbackِ
//   کوچکِ روز در جهتِ side باشد.
// ---------------------------------------------------------------------------
export function computeS344(candles: Candle[], cfg: S344Config): RawSignal {
  const n = candles.length
  const o = candles.map(c => c.open)
  const h = candles.map(c => c.high)
  const l = candles.map(c => c.low)
  const c = candles.map(x => x.close)
  const t = candles.map(x => x.time)

  const side = cfg.side === 'LONG' ? 'long' : 'short'
  const slDist = cfg.slPip * GOLD_PIP
  const tpDist = cfg.tpPip * GOLD_PIP

  const emptyInd: RouterDecision['indicators'] = [
    { name: 'داده', value: 'ناکافی', status: 'neutral' },
  ]
  const need = cfg.hurstPeriod + cfg.nOpen + 10
  if (n < need) {
    return {
      active: false, approaching: false, direction: cfg.side,
      slDist, tpDist, maxHoldBars: cfg.maxHold,
      reason: 'دادهٔ کافی برای تشخیصِ trend-from-open موجود نیست.',
      indicators: emptyInd,
    }
  }

  const days = t.map(dayId)
  const adrMap = adrForDay(h, l, days, cfg.adrLookbackDays)

  // فیلترِ رژیمِ بانک r2h (روی close) — همان توابعِ squeeze_s332 (منطبق با ib.r2/ib.hurst)
  const r2 = r2Series(c, cfg.r2Period)
  const hu = hurstSeries(c, cfg.hurstPeriod)

  const i = n - 1                 // آخرین کندلِ بسته‌شده (سیگنال روی i، ورود در کندلِ بعد)
  const d = days[i]

  // مرزِ روزِ جاری: نخستین اندیسِ کندلِ امروز
  let j0 = i
  while (j0 > 0 && days[j0 - 1] === d) j0 -= 1
  const idr = i - j0              // اندیسِ درون‌روزیِ کندلِ آخر (۰-based)
  const bpd = { M5: 288, M15: 96, M30: 48, H1: 24 }[cfg.tfFa] ?? 96
  const entryFromBar = cfg.nOpen
  const entryToBar = Math.floor(0.85 * bpd)

  const adr = adrMap.get(d) as number
  const oi0 = j0
  const oi1 = j0 + cfg.nOpen

  // فیلترِ رژیم روی کندلِ i
  const r2v = r2[i], huv = hu[i]
  const r2Ok = isFinite(r2v) && r2v >= cfg.r2Min
  const huOk = isFinite(huv) && huv >= cfg.hurstMin
  const regimeOk = r2Ok && huOk

  let active = false
  let broke = false
  let legVal = 0
  let pullVal = NaN
  let initR = NaN
  let spikeDirOk = false
  let smallRange = false

  // فقط اگر روزِ جاری به‌قدرِ کافی کندل دارد و opening-range کامل شده و ADR معتبر است
  if (idr >= cfg.nOpen && oi1 <= n && isFinite(adr) && adr > 0) {
    let initHi = -Infinity, initLo = Infinity
    for (let k = oi0; k < oi1; k++) { if (h[k] > initHi) initHi = h[k]; if (l[k] < initLo) initLo = l[k] }
    initR = initHi - initLo
    const openPx = o[j0]
    smallRange = initR < cfg.fRange * adr

    if (smallRange) {
      const spikeDir = c[oi1 - 1] >= openPx ? 'long' : 'short'
      spikeDirOk = spikeDir === side
      if (spikeDirOk) {
        // بازپخشِ روز از oi1 تا i برای یافتنِ «اولین pullback»؛ سیگنال فقط اگر i همان کندل باشد.
        let legHi = initHi, legLo = initLo
        let firstPullBar = -1
        for (let k = oi1; k <= i; k++) {
          const kIdr = k - j0
          if (side === 'long') {
            if (h[k] > legHi) legHi = h[k]
            if (!broke && h[k] > initHi) broke = true
            if (broke) {
              const leg = legHi - initLo
              if (leg >= cfg.minSpike * adr && leg > 0) {
                const pull = (legHi - l[k]) / leg
                if (pull > 0 && pull <= cfg.pullMax && kIdr >= entryFromBar && kIdr <= entryToBar) {
                  if (k >= 1 && l[k] < l[k - 1] && c[k] < legHi) { firstPullBar = k; legVal = leg; pullVal = pull; break }
                }
              }
            }
          } else {
            if (l[k] < legLo) legLo = l[k]
            if (!broke && l[k] < initLo) broke = true
            if (broke) {
              const leg = initHi - legLo
              if (leg >= cfg.minSpike * adr && leg > 0) {
                const pull = (h[k] - legLo) / leg
                if (pull > 0 && pull <= cfg.pullMax && kIdr >= entryFromBar && kIdr <= entryToBar) {
                  if (k >= 1 && h[k] > h[k - 1] && c[k] > legLo) { firstPullBar = k; legVal = leg; pullVal = pull; break }
                }
              }
            }
          }
        }
        active = firstPullBar === i && regimeOk
      }
    }
  }

  // approaching: اسپایکِ هم‌جهت و رنجِ کوچک و رژیم برقرار است، اما هنوز اولین pullback نشکسته.
  const approaching = !active && smallRange && spikeDirOk && broke && regimeOk

  const dirFa = side === 'short' ? 'نزولی' : 'صعودی'
  const indicators: RouterDecision['indicators'] = [
    { name: `رنجِ اولیهٔ کوچک (opening-range < ${cfg.fRange}×ADR)`,
      value: isFinite(initR) && isFinite(adr) && adr > 0
        ? (initR / adr).toFixed(2) + '×ADR' + (smallRange ? ' ✔' : ' ✘') : '—',
      status: smallRange ? 'ok' : 'neutral' },
    { name: `اسپایکِ اولیهٔ هم‌جهت (${dirFa})`,
      value: spikeDirOk ? 'هم‌جهت ✔' : 'ناهم‌جهت/نامشخص ✘', status: spikeDirOk ? 'ok' : 'neutral' },
    { name: `رژیمِ روندِ قوی (R²(${cfg.r2Period})≥${cfg.r2Min} و Hurst(${cfg.hurstPeriod})≥${cfg.hurstMin})`,
      value: (isFinite(r2v) ? r2v.toFixed(2) : '—') + '/' + (isFinite(huv) ? huv.toFixed(2) : '—')
        + (regimeOk ? ' ✔' : ' ✘'), status: regimeOk ? 'ok' : 'bad' },
    { name: `اولین pullbackِ کوچک (pull ≤ ${cfg.pullMax}×leg)`,
      value: isFinite(pullVal) ? pullVal.toFixed(2) + (active ? ' ✔' : '') : (broke ? 'در انتظار' : '—'),
      status: active ? 'ok' : 'neutral' },
  ]

  let reason: string
  if (active) {
    reason = `روزِ trend-from-open ${dirFa}: رنجِ اولیهٔ کوچک + اسپایکِ ${dirFa} + اولین pullbackِ کوچک ` +
      `(${(pullVal).toFixed(2)}×leg) در رژیمِ روندِ قوی ⇒ ورودِ ${side === 'short' ? 'فروشِ' : 'خریدِ'} ادامهٔ روند.`
  } else if (approaching) {
    reason = `روزِ trend-from-open ${dirFa} در حالِ شکل‌گیری (رنجِ اولیهٔ کوچک + اسپایکِ ${dirFa})؛ ` +
      `منتظرِ اولین pullbackِ کوچکِ ${cfg.pullMax}×leg برای ورود.`
  } else if (!smallRange) {
    reason = 'رنجِ اولیهٔ روز کوچک نیست (opening-range بزرگ) — الگوی trend-from-open برقرار نیست.'
  } else if (!spikeDirOk) {
    reason = `اسپایکِ اولیهٔ روز هم‌جهتِ ${dirFa} نیست — ورود نمی‌کنیم.`
  } else if (!regimeOk) {
    reason = 'رژیمِ روندِ قوی (R²/Hurst) هنوز تأیید نشده — از ورود پرهیز می‌کنیم.'
  } else {
    reason = 'هنوز اولین pullbackِ کوچکِ روز شکل نگرفته یا خارج از پنجرهٔ زمانیِ ورود است.'
  }

  return {
    active, approaching, direction: cfg.side,
    slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason,
    approachReason: approaching
      ? `منتظرِ اولین pullbackِ کوچکِ روز (≤ ${cfg.pullMax}×leg) در جهتِ ${dirFa}` : undefined,
    indicators,
  }
}

// ---------------------------------------------------------------------------
export function decideS344(
  cfg: S344Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS344(candles, cfg)

  const reg: RegimeInfo = {
    regime: cfg.side === 'SHORT' ? 'trend_down' : 'trend_up', efficiencyRatio: 0,
    trendy: true, adx: 0, activeStream: cfg.side === 'SHORT' ? 'bear' : 'bull',
    bucket: `s344_${cfg.tfFa.toLowerCase()}`,
  }

  const meta: DecideMeta = {
    code: 'S344',
    name: `روند از بازِ روز (Brooks Trend-from-Open · ${cfg.tfFa})`,
    kind: 'trend_from_open' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote: `هدف/حدِ ثابتِ مخصوصِ ${cfg.tfFa} (${cfg.tpPip}/${cfg.slPip} pip). ` +
      `تا برخورد به TP/SL یا پایانِ ${cfg.maxHold} کندل نگه‌دار؛ اگر اکسترممِ روز شکست یا ` +
      `کندلِ برگشتیِ قویِ ضدِ روند بسته شد (احتمالِ climax پس از ~۲/۳ روز)، خروجِ زودهنگام را بسنج.`,
    filters: [
      `رنجِ اولیهٔ کوچک < ${cfg.fRange}×ADR`,
      `اسپایکِ اولیه ≥ ${cfg.minSpike}×ADR هم‌جهت`,
      `رژیمِ روندِ قوی R²(${cfg.r2Period})≥${cfg.r2Min} · Hurst(${cfg.hurstPeriod})≥${cfg.hurstMin}`,
      `اولین pullbackِ کوچک ≤ ${cfg.pullMax}×leg`,
    ],
  }

  return rawToDecision(raw, meta, cfg.id, a.price, reg, capital, riskPct)
}

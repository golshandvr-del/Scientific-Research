// ============================================================================
// trend_resumption_s354.ts — لایهٔ نوِ S354 (Al Brooks «Trend Resumption Day» —
//   فصلِ ۲۵ کتابِ Trading Price Action: TRENDS)
//
//   مفهوم (فصلِ ۲۵):
//     ۱) روندِ قویِ صبحگاهی (اسپایک در «ساعتِ اول») در جهتِ init_dir.
//     ۲) سپس یک trading-range فشرده که ساعت‌ها طول می‌کشد.
//     ۳) در «ساعتِ پایانیِ روز» روندِ اولیه از سر گرفته می‌شود (resumption)؛
//        leg دوم اغلب هم‌اندازهٔ leg اول (⇒ TP = measured-move، RR شناور=۲).
//
//   کارتِ پذیرفته‌شده (RQS2=80.8 · ACCEPT · همه‌ی ۱۱ دروازه):
//     XAUUSD-H1 · LONG only · SL=1.3×ATR · TP=2.0×SL · maxHold=20
//     گیت: r2_fib_55 ≥ 0.394314 (آستانهٔ سراسریِ q45، ثابتِ از‌پیش‌محاسبه‌شده)
//     پارامترها: nOpen=3 · lateFrom=0.68 · spikeK=0.8 · tightATR=12.0 · atrP=21
//
//   سند: results/S354_BrooksTrendResumption_Xauusd_H1_rqs2-80.md
//   پورتِ verbatim از strategies/s354_brooks_trend_resumption.py::build_signals
//   (فقط شاخهٔ LONG؛ ATR = atrSeriesS354 با parity ثابت‌شده تا 1.7e-6 با atr_fib_21).
// ============================================================================
import type { Candle } from './indicators'
import type { RouterDecision, RegimeInfo } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'
import type { AnalysisResult } from './signal'
import { r2Series } from './squeeze_s332'

export interface S354Config {
  id: string              // XAUUSD-H1
  tfFa: string            // نامِ فارسیِ TF
  pip: number             // اندازهٔ pip (۰.۱ برای طلا)
  barsPerDay: number      // 24 برای H1
  nOpen: number           // 3 — طولِ «ساعتِ اول» (کندل)
  lateFrom: number        // 0.68 — کسرِ روز که پنجرهٔ پایانی از آن آغاز می‌شود
  spikeK: number          // 0.8 — leg1 ≥ spikeK×ATR
  tightATR: number        // 12.0 — mid_range ≤ tightATR×ATR
  atrPeriod: number       // 21
  r2Period: number        // 55
  r2Min: number           // 0.394314 — آستانهٔ رژیمِ روند (q45 سراسری)
  slK: number             // 1.3 — SL = slK×ATR (بر حسبِ pip)
  rr: number              // 2.0 — TP = rr×SL
  maxHold: number         // 20
}

export const S354_CFG: Record<string, S354Config> = {
  'XAUUSD-H1': {
    id: 'XAUUSD-H1', tfFa: 'H1', pip: 0.1, barsPerDay: 24,
    nOpen: 3, lateFrom: 0.68, spikeK: 0.8, tightATR: 12.0,
    atrPeriod: 21, r2Period: 55, r2Min: 0.394314,
    slK: 1.3, rr: 2.0, maxHold: 20,
  },
}

// شناسهٔ روزِ UTC (منطبق با `dt.dt.floor('D')` پایتون)
function dayIdOf(tsSec: number): number {
  return Math.floor(tsSec / 86400)
}

// ATR (Wilder RMA، causal) — parity با atr_fib_21 پایتون تا 1.7e-6 پس از warmup.
//   seed = میانگینِ سادهٔ p کندلِ اولِ TR، سپس recursionِ Wilder.
export function atrSeriesS354(
  high: number[], low: number[], close: number[], p: number,
): number[] {
  const n = high.length
  const tr = new Array<number>(n).fill(0)
  if (n === 0) return tr
  tr[0] = high[0] - low[0]
  for (let i = 1; i < n; i++) {
    tr[i] = Math.max(
      high[i] - low[i],
      Math.abs(high[i] - close[i - 1]),
      Math.abs(low[i] - close[i - 1]),
    )
  }
  const atr = new Array<number>(n).fill(NaN)
  if (n >= p) {
    let s = 0
    for (let k = 0; k < p; k++) s += tr[k]
    atr[p - 1] = s / p
    for (let i = p; i < n; i++) atr[i] = (atr[i - 1] * (p - 1) + tr[i]) / p
  }
  return atr
}

// ---------------------------------------------------------------------------
// computeS354 — ارزیابیِ ماشهٔ resumption روی «کندلِ آخرِ بسته‌شده» (i = n-1).
//   پورتِ verbatim از build_signals (شاخهٔ LONG): همان مرزِ روزِ UTC، همان اسپایکِ
//   صبح، همان رنجِ midday تا t-1، همان قیدِ tightness نسبت به ATR، همان breakoutِ
//   c[t] > mseg_hi و همان «فقط اولین resumptionِ روز».
// ---------------------------------------------------------------------------
export function computeS354(candles: Candle[], cfg: S354Config): RawSignal {
  const n = candles.length
  const o = candles.map(c => c.open)
  const h = candles.map(c => c.high)
  const l = candles.map(c => c.low)
  const c = candles.map(x => x.close)
  const t = candles.map(x => x.time)

  const slDist = cfg.slK          // موقت؛ پس از دانستنِ ATR به pip→price تبدیل می‌شود
  const need = cfg.r2Period + cfg.atrPeriod + cfg.barsPerDay + 10

  const fail = (reason: string): RawSignal => ({
    active: false, approaching: false, direction: 'LONG',
    slDist: 0, tpDist: 0, maxHoldBars: cfg.maxHold, reason,
    indicators: [{ name: 'داده', value: 'ناکافی', status: 'neutral' }],
  })

  if (n < need) return fail('دادهٔ کافی برای تشخیصِ روزِ ازسرگیریِ روند (trend resumption) موجود نیست.')

  const atr = atrSeriesS354(h, l, c, cfg.atrPeriod)
  const r2 = r2Series(c, cfg.r2Period)

  const i = n - 1
  const dToday = dayIdOf(t[i])

  // مرزِ روزِ جاری: [ds, i]
  let ds = i
  while (ds > 0 && dayIdOf(t[ds - 1]) === dToday) ds -= 1
  const pos = i - ds                       // اندیسِ درون‌روزیِ کندلِ آخر
  const ndlen = pos + 1                     // طولِ روزِ جاری تا کنون (کندل)

  const openEnd = ds + cfg.nOpen            // پایانِ ساعتِ اول (exclusive)
  const lateStart = ds + Math.round(cfg.lateFrom * ndlen)

  // --- اسپایکِ صبح (init_dir باید صعودی باشد ⇒ فقط LONG) ---
  const atrRef = openEnd - 1 < n ? atr[openEnd - 1] : NaN
  const atrRefOk = isFinite(atrRef) && atrRef > 0
  const initRet = openEnd - 1 >= 0 ? c[openEnd - 1] - o[ds] : NaN
  const initDir = Math.sign(initRet)
  const leg1 = Math.abs(initRet)
  const spikeOk = atrRefOk && initDir > 0 && leg1 >= cfg.spikeK * atrRef

  // --- گاردِ روز و پنجرهٔ midday (منطبق با پایتون) ---
  const midLoIdx = openEnd
  const midHiIdx = Math.max(openEnd + 1, lateStart)
  const dayLongEnough = ndlen >= cfg.nOpen + 4
  const rangeReady = midHiIdx - midLoIdx >= 2 && midHiIdx <= i
  const inLateWindow = i >= Math.max(midHiIdx, lateStart)

  // ATR و r2 روی کندلِ جاری
  const atrNow = isFinite(atr[i - 1]) ? atr[i - 1] : atrRef
  const r2Now = r2[i]
  const regimeOk = isFinite(r2Now) && r2Now >= cfg.r2Min

  const slPip = atrRefOk ? cfg.slK * (atrRef / cfg.pip) : 0
  const tpPip = slPip * cfg.rr
  const slPrice = slPip * cfg.pip
  const tpPrice = tpPip * cfg.pip

  // رنجِ midday تا کندلِ i-1 (causal، منطبق با h[mid_lo:t] پایتون که t=i)
  let msegHi = -Infinity, msegLo = Infinity
  for (let k = midLoIdx; k < i; k++) {
    if (h[k] > msegHi) msegHi = h[k]
    if (l[k] < msegLo) msegLo = l[k]
  }
  const midRange = msegHi - msegLo
  const tightOk = isFinite(atrNow) && atrNow > 0 && midRange > 0 && midRange <= cfg.tightATR * atrNow

  const fmt = (x: number) => (isFinite(x) ? x.toFixed(2) : '—')
  const ind: RawSignal['indicators'] = [
    { name: 'اسپایکِ صبح (leg1/ATR)', value: atrRefOk ? (leg1 / atrRef).toFixed(2) : '—',
      status: spikeOk ? 'bullish' : 'neutral' },
    { name: 'فشردگیِ رنجِ میانی (range/ATR)', value: (isFinite(atrNow) && atrNow > 0) ? (midRange / atrNow).toFixed(2) : '—',
      status: tightOk ? 'bullish' : 'neutral' },
    { name: `رژیمِ روند R²(${cfg.r2Period})`, value: fmt(r2Now),
      status: regimeOk ? 'bullish' : 'bearish' },
    { name: 'سقفِ رنجِ میانی', value: isFinite(msegHi) ? msegHi.toFixed(2) : '—', status: 'neutral' },
  ]

  // شرطِ کلیِ ساختارِ روز (پیش‌نیازِ ماشه)
  const structureOk = spikeOk && dayLongEnough && rangeReady && tightOk && regimeOk && slPip > 0

  // --- ماشهٔ resumption: breakoutِ صعودی از سقفِ رنجِ میانی ---
  if (structureOk && inLateWindow && c[i] > msegHi) {
    return {
      active: true, approaching: false, direction: 'LONG',
      slDist: slPrice, tpDist: tpPrice, maxHoldBars: cfg.maxHold,
      reason: `روزِ ازسرگیریِ روند: اسپایکِ صعودیِ صبح (leg1=${(leg1 / atrRef).toFixed(1)}×ATR) → ` +
        `رنجِ میانیِ فشرده (${(midRange / atrNow).toFixed(1)}×ATR) → شکستِ صعودی در ساعتِ پایانیِ روز ` +
        `بالای سقفِ رنج ${msegHi.toFixed(2)}. leg دوم measured-move (TP=۲×SL).`,
      indicators: ind,
    }
  }

  // --- حالتِ approaching: ساختار آماده است ولی هنوز breakout رخ نداده ---
  if (structureOk && inLateWindow && c[i] <= msegHi) {
    return {
      active: false, approaching: true, direction: 'LONG',
      slDist: slPrice, tpDist: tpPrice, maxHoldBars: cfg.maxHold,
      reason: `ساختارِ روزِ ازسرگیریِ روند کامل است (اسپایکِ صعودیِ صبح + رنجِ میانیِ فشرده` +
        ` + رژیمِ روند)، اما قیمت هنوز سقفِ رنج (${msegHi.toFixed(2)}) را نشکسته.`,
      approachReason: `منتظرِ بستنِ یک کندلِ H1 بالای ${msegHi.toFixed(2)} در ساعتِ پایانیِ روز ` +
        `باش؛ آنگاه سیگنالِ LONG با TP=۲×SL فعال می‌شود.`,
      indicators: ind,
    }
  }

  // --- خنثی: توضیحِ صریحِ اینکه کدام پیش‌شرط برقرار نیست ---
  let why = 'شرایطِ روزِ ازسرگیریِ روند فراهم نیست: '
  if (!spikeOk) why += `اسپایکِ صعودیِ قویِ صبح تشکیل نشده (leg1/ATR=${atrRefOk ? (leg1 / atrRef).toFixed(2) : '—'} < ${cfg.spikeK}). `
  else if (!dayLongEnough) why += 'روز هنوز به‌قدرِ کافی پیش نرفته. '
  else if (!tightOk) why += `رنجِ میانی به‌قدرِ کافی فشرده نیست (range/ATR=${(isFinite(atrNow) && atrNow > 0) ? (midRange / atrNow).toFixed(1) : '—'} > ${cfg.tightATR}). `
  else if (!regimeOk) why += `رژیمِ روند ضعیف است (R²=${fmt(r2Now)} < ${cfg.r2Min}). `
  else if (!inLateWindow) why += 'هنوز به پنجرهٔ ساعتِ پایانیِ روز نرسیده‌ایم. '
  else why += 'شکستِ صعودی از سقفِ رنج هنوز رخ نداده. '

  return {
    active: false, approaching: false, direction: 'LONG',
    slDist: slPrice, tpDist: tpPrice, maxHoldBars: cfg.maxHold,
    reason: why, indicators: ind,
  }
}

// ---------------------------------------------------------------------------
// decideS354 — آداپترِ لایه برای رجیستری.
// ---------------------------------------------------------------------------
export function decideS354(
  cfg: S354Config, a: AnalysisInput, candles: Candle[],
  capital: number, riskPct: number,
): RouterDecision {
  const raw = computeS354(candles, cfg)

  const reg: RegimeInfo = {
    regime: 'trend_up', efficiencyRatio: 0, trendy: true, adx: 0,
    activeStream: 'bull', bucket: `s354_${cfg.tfFa.toLowerCase()}`,
  }

  const meta: DecideMeta = {
    code: 'S354',
    name: `روزِ ازسرگیریِ روند (Brooks Trend Resumption · ${cfg.tfFa})`,
    kind: 'trend_resumption' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote: `هدف/حدِ متناسب با نوسان: SL=${cfg.slK}×ATR ، TP=${cfg.rr}×SL (measured-move ` +
      `برای leg دومِ روز). معامله را تا TP/SL یا پایانِ ${cfg.maxHold} کندل نگه‌دار. ` +
      `⚠️ اگر قیمت به داخلِ رنجِ میانی برگشت و زیرِ نقطهٔ شکست بسته شد، شکست ناموفق است ` +
      `⇒ می‌توانی زودتر خارج شوی؛ اما حدِ ضرر را دورتر نبر.`,
    filters: [
      `اسپایکِ صعودیِ صبح (${cfg.nOpen} کندلِ اول) با leg1 ≥ ${cfg.spikeK}×ATR`,
      `رنجِ میانیِ فشرده ≤ ${cfg.tightATR}×ATR`,
      'شکستِ صعودی از سقفِ رنجِ میانی در ساعتِ پایانیِ روز',
      `رژیمِ روند R²(${cfg.r2Period}) ≥ ${cfg.r2Min}`,
      'فقط اولین ازسرگیریِ هر روز',
    ],
  }

  return rawToDecision(raw, meta, cfg.id, a.price, reg, capital, riskPct)
}

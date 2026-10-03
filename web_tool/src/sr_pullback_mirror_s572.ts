// ---------------------------------------------------------------------------
// S572 — «پولبکِ S/R طلایی، هندسهٔ آینه‌ای (TP≥SL)» · XAUUSD-**M30** + **H1**
//
// حکمِ نهایی (سند: results/S572_SRPullbackGoldenMirrorPool_Xauusd_M30H1_rqs2_79_ACCEPT.md):
//   استخرِ تقویمیِ {M30, H1} با هندسهٔ آینه‌ای ⇒ RQS2 = **78.7** (تنش 78.4 — پایدار)
//   n=181 (پس از FIFO) · WR=53.59٪ · PF=1.398 · lift=+14.22pp · z=3.92 · RR=1.45
//   هر ۱۱ دروازهٔ H0..H10 سبز · سه بذر (23/101/777) حکمِ یکسان.
//   اعضا (میراثِ سیگنالِ منجمدِ S323، فقط هندسه آینه شد):
//     · XAUUSD-M30: n=156 · WR 49.36٪ · lift +12.68pp · SL=34.7 / TP=56.0 pip (RR 1.61)
//     · XAUUSD-H1 : n=37  · WR 70.27٪ · lift +24.61pp · SL=66.0 / TP=69.8 pip (RR 1.06)
//
// چرا این لایه (مسیرِ انتخابِ کاربر: از کمترین شمارهٔ S400+ که عامدانه وصل نشده):
//   S404/S407 (XOR با S408 · اِراتا) · S526/S569/S1521/S1560/S1621/S1913/S802
//   (زیرمجموعهٔ ساکنانِ زنده) همه در مستندات عامدانه رد شده‌اند. S572 اولین
//   ACCEPTِ مستقلِ وصل‌نشده است و **خودِ سندش** صریحاً نامزدِ استقرارش دانسته:
//   «توصیهٔ پوانکاره: S572 نامزد استقرار است». روی هر دو کارتِ ACCEPT وصل می‌شود
//   (قانونِ MTF: روی همهٔ تایم‌فریم‌های پذیرفته‌شده).
//
// 🔴 دامِ پورت — با مرجعِ عددی بسته شد (نه با چشم):
//   مرجع: results/_s572_parity/XAUUSD_{M30,H1}.json (ساختهٔ tools/export_s572_parity.py
//   که ماشینِ منجمدِ S323 را عیناً اجرا می‌کند؛ گاردِ سلامت: ۱۵۶ و ۳۷ معاملهٔ
//   پس از FIFO بازتولید شد). ابزار: tools/_parity_s572.mts.
//   ① **پیوت‌ها left=6/right=6** (نه ۵، نه pivotLen=20 که در signals_backtested
//      بی‌استفاده است) و **سطوح با max_levels=40 و tol=0.0015** — نه ۶۰/۰.۰۰۱۲
//      که ماژولِ structure.ts دارد. یک پورتِ «تقریباً» اینجا رویدادِ دیگری می‌سازد.
//   ② **ادغامِ سطح، جایگزینیِ قیمت است نه میانگین** (تفاوتِ Python و structure.ts).
//   ③ **سطوح در کندلِ تأیید (p+right) ثبت می‌شوند**، نه کندلِ خودِ پیوت — anti-lookahead.
//   ④ **گیتِ شیبِ EMA50:** `(ema50[i] − ema50[i−10])/ATR > 0` (nan→0) — نه شیبِ EMA200.
//   ⑤ **گیتِ پنجرهٔ طلایی** ساعتِ **UTCِ خودِ کندل** است (hLo=19..hHi=23).
//   ⑥ **ورود روی open کندلِ بعد** (simulate_trades) و **allow_overlap=false** ⇒
//      FIFO؛ nِ منتشرشده (۱۵۶/۳۷) پس از FIFO است، نه شمارِ سیگنالِ خام.
//   ⑦ **گرم‌شدن:** بک‌تست `sig[:300]=False` می‌گذارد ⇒ زیرِ ۳۰۰ کندل سیگنال نداریم.
//      سایت پنجرهٔ کوتاه می‌دهد؛ اگر کمتر باشد صادقانه «دادهٔ ناکافی» می‌دهیم.
//   ⑧ ⚠️ **وابستگیِ برشیِ SR:** سطوحِ فعال تا ۱۵۰۰ کندل عمر دارند؛ پنجرهٔ کوتاهِ
//      سایت ممکن است سطحی که در بک‌تست فعال بود را نبیند ⇒ این لایه ذاتاً کمی
//      به طولِ پنجره حساس است (مثلِ هر لایهٔ ساختار-محور روی کارت‌های کوتاه‌پنجره).
//
// منابع: S323 (قانونِ منجمدِ پولبکِ S/R) · S571/S570 (بازآزمونِ کاملِ داده) ·
//        S572 (تبدیلِ آینه‌ای، صفر پارامترِ آزاد) · S431/S432 (دستورکارِ استخر).
// ---------------------------------------------------------------------------

import type { Candle } from './indicators'
import { ema, atr, rsi, adx } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision, RegimeInfo } from './router'
import { type RawSignal, type DecideMeta, rawToDecision, GOLD_PIP } from './revived_strategies'

export interface S572Config {
  id: string
  tfFa: string
  // سیگنال (منجمد از DEPLOYED_CFG کارتِ مربوطه در s357_s323_v24_rejudge)
  nearMax: number
  roomMin: number
  rsiMax: number
  slopeMin: number
  adxMin: number
  golden: boolean
  hLo: number
  hHi: number
  // هندسهٔ **آینه‌ای** (SL=tpMult قدیم × ATR، TP=slMult قدیم × ATR) — pip منجمد
  slPip: number
  tpPip: number
  maxHold: number
  // پارامترهای ثابتِ ساختار (signals_backtested)
  pivotLeft: number
  pivotRight: number
  srTol: number
  srMaxLevels: number
  srExpiry: number
  warmup: number
  rqs2: number
  nTrades: number
  wr: number
  lift: number
  z: number
}

export const S572_CFG: Record<string, S572Config> = {
  'XAUUSD-M30': {
    id: 'XAUUSD-M30', tfFa: 'M30',
    nearMax: 0.85, roomMin: 1.3, rsiMax: 55, slopeMin: 0.0, adxMin: 22,
    golden: true, hLo: 19, hHi: 23,
    // عددِ منجمد از results/_s572_mirror/members.json (SL=tpMult قدیم=1.3×ATR، TP=slMult قدیم=2.1×ATR)
    slPip: 34.7, tpPip: 56.0, maxHold: 48,
    pivotLeft: 6, pivotRight: 6, srTol: 0.0015, srMaxLevels: 40, srExpiry: 1500, warmup: 300,
    rqs2: 78.7, nTrades: 156, wr: 49.36, lift: 12.68, z: 3.92,
  },
  'XAUUSD-H1': {
    id: 'XAUUSD-H1', tfFa: 'H1',
    nearMax: 0.55, roomMin: 1.3, rsiMax: 55, slopeMin: 0.0, adxMin: 30,
    golden: true, hLo: 19, hHi: 23,
    slPip: 66.0, tpPip: 69.8, maxHold: 36,
    pivotLeft: 6, pivotRight: 6, srTol: 0.0015, srMaxLevels: 40, srExpiry: 1500, warmup: 300,
    rqs2: 78.7, nTrades: 37, wr: 70.27, lift: 24.61, z: 3.92,
  },
}

// ── پیوت‌های تأییدشده (پورتِ عینِ engine/structure.py::_pivots با left=6/right=6) ──
//    phPrice[conf] = قیمتِ پیوتِ سقف که در کندلِ conf=p+right تأیید شد (NaN اگر نباشد).
interface Pivots { phPrice: number[]; plPrice: number[] }

function computePivots(c: Candle[], left: number, right: number): Pivots {
  const n = c.length
  const phPrice = new Array<number>(n).fill(NaN)
  const plPrice = new Array<number>(n).fill(NaN)
  for (let p = left; p < n - right; p++) {
    const hv = c[p].high
    let isPh = true
    for (let k = p - left; k <= p + right; k++) {
      if (k === p) continue
      if (c[k].high > hv) { isPh = false; break }
    }
    if (isPh) phPrice[p + right] = hv
    const lv = c[p].low
    let isPl = true
    for (let k = p - left; k <= p + right; k++) {
      if (k === p) continue
      if (c[k].low < lv) { isPl = false; break }
    }
    if (isPl) plPrice[p + right] = lv
  }
  return { phPrice, plPrice }
}

// ── سطوحِ فعالِ حمایت/مقاومت (پورتِ عینِ _active_levels: max_levels=40, expiry=1500) ──
//    ⚠️ ادغام = جایگزینیِ قیمت (نه میانگین)؛ انقضا بر اساسِ آخرین لمس.
interface SR { support: number[]; resistance: number[] }

function computeSR(c: Candle[], piv: Pivots, tol: number, maxLevels: number, expiry: number): SR {
  const n = c.length
  const close = c.map(k => k.close)
  const support = new Array<number>(n).fill(NaN)
  const resistance = new Array<number>(n).fill(NaN)

  const lvPrice = new Array<number>(maxLevels).fill(0)
  const lvLast = new Array<number>(maxLevels).fill(0)
  const lvActive = new Array<number>(maxLevels).fill(0)   // 1=مقاومت، −1=حمایت، 0=خالی

  for (let i = 0; i < n; i++) {
    const rp = piv.phPrice[i]
    if (!Number.isNaN(rp)) {
      let merged = false
      for (let s = 0; s < maxLevels; s++) {
        if (lvActive[s] !== 0 && Math.abs(lvPrice[s] - rp) / rp < tol) {
          lvPrice[s] = rp; lvLast[s] = i; lvActive[s] = 1; merged = true; break
        }
      }
      if (!merged) {
        let slot = -1
        for (let s = 0; s < maxLevels; s++) if (lvActive[s] === 0) { slot = s; break }
        if (slot === -1) {
          let oldest = 0
          for (let s = 1; s < maxLevels; s++) if (lvLast[s] < lvLast[oldest]) oldest = s
          slot = oldest
        }
        lvPrice[slot] = rp; lvLast[slot] = i; lvActive[slot] = 1
      }
    }
    const lp = piv.plPrice[i]
    if (!Number.isNaN(lp)) {
      let merged = false
      for (let s = 0; s < maxLevels; s++) {
        if (lvActive[s] !== 0 && Math.abs(lvPrice[s] - lp) / lp < tol) {
          lvPrice[s] = lp; lvLast[s] = i; lvActive[s] = -1; merged = true; break
        }
      }
      if (!merged) {
        let slot = -1
        for (let s = 0; s < maxLevels; s++) if (lvActive[s] === 0) { slot = s; break }
        if (slot === -1) {
          let oldest = 0
          for (let s = 1; s < maxLevels; s++) if (lvLast[s] < lvLast[oldest]) oldest = s
          slot = oldest
        }
        lvPrice[slot] = lp; lvLast[slot] = i; lvActive[slot] = -1
      }
    }
    for (let s = 0; s < maxLevels; s++) {
      if (lvActive[s] !== 0 && i - lvLast[s] > expiry) lvActive[s] = 0
    }
    const cpx = close[i]
    let bestRes = NaN, bestSup = NaN
    for (let s = 0; s < maxLevels; s++) {
      if (lvActive[s] === 0) continue
      const pxs = lvPrice[s]
      if (pxs >= cpx) { if (Number.isNaN(bestRes) || pxs < bestRes) bestRes = pxs }
      else { if (Number.isNaN(bestSup) || pxs > bestSup) bestSup = pxs }
    }
    resistance[i] = bestRes
    support[i] = bestSup
  }
  return { support, resistance }
}

export interface S572Features {
  support: number[]
  resistance: number[]
  atr14: number[]
  ema50: number[]
  ema200: number[]
  rsi14: number[]
  adx14: number[]
  slope: number[]
  nearSupport: number[]
  room: number[]
  sig: boolean[]
}

const nanTo = (v: number, fill: number) => (Number.isFinite(v) ? v : fill)

/**
 * پورتِ عینِ `strategies/s357_s323_v24_rejudge.py::signals_backtested` — همه علّی.
 * روی **کلِ** آرایه محاسبه می‌شود (سطوحِ SR عمرِ ۱۵۰۰ کندلی دارند ⇒ بریدنِ داده
 * از ابتدا سری‌ها را عوض می‌کند).
 */
export function s572Features(candles: Candle[], cfg: S572Config): S572Features {
  const n = candles.length
  const high = candles.map(c => c.high)
  const low = candles.map(c => c.low)
  const close = candles.map(c => c.close)

  const piv = computePivots(candles, cfg.pivotLeft, cfg.pivotRight)
  const sr = computeSR(candles, piv, cfg.srTol, cfg.srMaxLevels, cfg.srExpiry)
  const atr14 = atr(candles, 14)
  const e50 = ema(close, 50)
  const e200 = ema(close, 200)
  const r14 = rsi(close, 14)
  const { adx: adxArr } = adx(candles, 14)

  const nearSupport = new Array<number>(n).fill(Infinity)
  const room = new Array<number>(n).fill(-Infinity)
  const slope = new Array<number>(n).fill(0)
  const sig = new Array<boolean>(n).fill(false)

  for (let i = 0; i < n; i++) {
    const a = atr14[i] > 0 ? atr14[i] : NaN
    nearSupport[i] = nanTo((close[i] - sr.support[i]) / a, 99)
    room[i] = nanTo((sr.resistance[i] - close[i]) / a, -99)
    if (i >= 10 && Number.isFinite(a) && Number.isFinite(e50[i]) && Number.isFinite(e50[i - 10])) {
      slope[i] = nanTo((e50[i] - e50[i - 10]) / a, 0)
    } else {
      slope[i] = 0
    }
  }

  for (let i = 0; i < n; i++) {
    const hour = new Date(candles[i].time * 1000).getUTCHours()
    const adxV = Number.isFinite(adxArr[i]) ? adxArr[i] : 0
    const up = close[i] > e50[i] && e50[i] > e200[i]
    const near = nearSupport[i] > 0 && nearSupport[i] < cfg.nearMax
    const roomOk = room[i] > cfg.roomMin
    const rsiOk = Number.isFinite(r14[i]) && r14[i] < cfg.rsiMax
    const slopeOk = slope[i] >= cfg.slopeMin
    const adxOk = adxV >= cfg.adxMin
    const gold = !cfg.golden || (hour >= cfg.hLo && hour <= cfg.hHi)
    sig[i] = up && near && roomOk && rsiOk && slopeOk && adxOk && gold
  }
  // بک‌تست: sig[:300]=False (گرم‌شدنِ شاخص‌ها/سطوح)
  for (let i = 0; i < Math.min(cfg.warmup, n); i++) sig[i] = false

  return {
    support: sr.support, resistance: sr.resistance, atr14, ema50: e50, ema200: e200,
    rsi14: r14, adx14: adxArr, slope, nearSupport, room, sig,
  }
}

export function computeS572(candles: Candle[], cfg: S572Config): RawSignal {
  const n = candles.length
  const slDist = cfg.slPip * GOLD_PIP
  const tpDist = cfg.tpPip * GOLD_PIP
  const minBars = cfg.warmup + 20   // ۳۰۰ گرم‌شدن + حاشیهٔ سطوح/شاخص

  const base = (reason: string, ind: RouterDecision['indicators']): RawSignal => ({
    active: false, approaching: false, direction: 'LONG', slDist, tpDist,
    maxHoldBars: cfg.maxHold, reason, indicators: ind,
  })

  if (n < minBars) {
    return base(
      `دادهٔ ناکافی: این لایه دستِ‌کم ${minBars} کندلِ ${cfg.tfFa} می‌خواهد ` +
      `(گرم‌شدنِ EMA200/ADX/RSI + سطوحِ S/R با عمرِ ${cfg.srExpiry} کندل)، ` +
      `ولی فیدِ فعلی ${n} کندل دارد ⇒ هیچ حکمی صادر نمی‌شود.`, [])
  }

  const f = s572Features(candles, cfg)
  const i = n - 1
  const last = candles[i]
  const a = f.atr14[i]
  const sup = f.support[i]
  const res = f.resistance[i]
  const hour = new Date(last.time * 1000).getUTCHours()

  const up = last.close > f.ema50[i] && f.ema50[i] > f.ema200[i]
  const adxV = Number.isFinite(f.adx14[i]) ? f.adx14[i] : 0
  const adxOk = adxV >= cfg.adxMin
  const near = f.nearSupport[i] > 0 && f.nearSupport[i] < cfg.nearMax
  const roomOk = f.room[i] > cfg.roomMin
  const rsiOk = Number.isFinite(f.rsi14[i]) && f.rsi14[i] < cfg.rsiMax
  const slopeOk = f.slope[i] >= cfg.slopeMin
  const goldenOk = !cfg.golden || (hour >= cfg.hLo && hour <= cfg.hHi)
  const active = f.sig[i]
  const trendCtx = up && adxOk

  const ind: RouterDecision['indicators'] = [
    { name: `روندِ صعودی (close>EMA50>EMA200، ADX≥${cfg.adxMin})`,
      value: `${up ? 'صعودی' : 'نزولی'} / ADX ${Number.isFinite(f.adx14[i]) ? f.adx14[i].toFixed(0) : '—'}`,
      status: trendCtx ? 'ok' : 'bad' },
    { name: `پولبک به حمایتِ S/R (فاصله ≤ ${cfg.nearMax}×ATR14)`,
      value: Number.isFinite(sup) ? `${last.close.toFixed(2)} − ${sup.toFixed(2)} = ${f.nearSupport[i].toFixed(2)}×ATR` : 'حمایتِ فعالی نیست',
      status: near ? 'ok' : 'neutral' },
    { name: `فضا تا مقاومتِ بعدی (≥ ${cfg.roomMin}×ATR14)`,
      value: Number.isFinite(res) ? `${(res - last.close).toFixed(2)} (${f.room[i].toFixed(2)}×ATR)` : '—',
      status: roomOk ? 'ok' : 'warn' },
    { name: `RSI-14 < ${cfg.rsiMax} (غیرِ اشباعِ خرید)`,
      value: Number.isFinite(f.rsi14[i]) ? f.rsi14[i].toFixed(0) : '—',
      status: rsiOk ? 'ok' : 'warn' },
    { name: `شیبِ EMA50 (۱۰ کندل) ≥ ${cfg.slopeMin}×ATR`,
      value: f.slope[i].toFixed(3),
      status: slopeOk ? 'ok' : 'bad' },
    { name: `پنجرهٔ طلایی (${cfg.hLo}:00–${cfg.hHi}:00 UTC)`,
      value: `${hour}:00 UTC${goldenOk ? '' : ' — خارج'}`,
      status: goldenOk ? 'ok' : 'neutral' },
    { name: 'حد ضرر / هدف (هندسهٔ آینه‌ای منجمد — مخصوصِ همین تایم‌فریم)',
      value: `${cfg.slPip} / ${cfg.tpPip} pip (نسبت ${(cfg.tpPip / cfg.slPip).toFixed(2)} ⇒ TP≥SL)`,
      status: 'ok' },
  ]

  if (active) {
    return {
      active: true, approaching: false, direction: 'LONG', slDist, tpDist, maxHoldBars: cfg.maxHold,
      reason:
        `پولبکِ طلاییِ S/R روی ${cfg.tfFa}: روندِ صعودیِ تأییدشده (close>EMA50>EMA200 و ` +
        `ADX ${adxV.toFixed(0)}≥${cfg.adxMin})، قیمت به حمایتِ خوشه‌ای پولبک کرده ` +
        `(${f.nearSupport[i].toFixed(2)}×ATR)، فضای کافی تا مقاومت (${f.room[i].toFixed(2)}×ATR)، ` +
        `RSI ${f.rsi14[i].toFixed(0)}<${cfg.rsiMax}، شیبِ مثبت، و در پنجرهٔ طلایی ${cfg.hLo}–${cfg.hHi} UTC ⇒ خرید.`,
      indicators: ind,
    }
  }

  const approaching = trendCtx && roomOk && rsiOk && slopeOk && (goldenOk || near)
  if (approaching) {
    return {
      active: false, approaching: true, direction: 'LONG', slDist, tpDist, maxHoldBars: cfg.maxHold,
      reason: `روندِ صعودی برقرار است روی ${cfg.tfFa}؛ منتظرِ کامل‌شدنِ پولبک به حمایت ` +
        `(یا ورود به پنجرهٔ طلایی) برای ماشهٔ خرید.`,
      approachReason: `تأییدِ لازم: فاصله تا حمایتِ S/R باید ≤ ${cfg.nearMax}×ATR شود ` +
        `و ساعتِ UTC در ${cfg.hLo}–${cfg.hHi} باشد.`,
      indicators: ind,
    }
  }

  let why: string
  if (!trendCtx) why = 'روندِ صعودیِ لازم (EMA50/EMA200/ADX) برقرار نیست.'
  else if (!near) why = Number.isFinite(sup)
    ? `قیمت به حمایتِ S/R نزدیک نیست (فاصله ${f.nearSupport[i].toFixed(2)}×ATR > ${cfg.nearMax}).`
    : 'حمایتِ فعالی بالای کفِ قیمت ثبت نشده است.'
  else if (!roomOk) why = `فضا تا مقاومتِ بعدی کافی نیست (${f.room[i].toFixed(2)}×ATR ≤ ${cfg.roomMin}).`
  else if (!rsiOk) why = `RSI-14 اشباعِ خرید است (${Number.isFinite(f.rsi14[i]) ? f.rsi14[i].toFixed(0) : '—'} ≥ ${cfg.rsiMax}).`
  else if (!goldenOk) why = `خارج از پنجرهٔ طلایی (${cfg.hLo}–${cfg.hHi} UTC).`
  else why = 'ستاپِ پولبکِ طلایی کامل نیست.'

  return {
    active: false, approaching: false, direction: 'LONG', slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason: `بدونِ سیگنال روی ${cfg.tfFa}. ${why}`, indicators: ind,
  }
}

export function decideS572(
  cfg: S572Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS572(candles, cfg)
  const price = a.price
  const reg: RegimeInfo = {
    regime: 'trend_up', efficiencyRatio: 0, trendy: true,
    adx: 0, activeStream: 'bull', bucket: `s572_${cfg.tfFa.toLowerCase()}`,
  }
  const meta: DecideMeta = {
    code: 'S572',
    name: `پولبکِ طلاییِ S/R — هندسهٔ آینه‌ای (${cfg.tfFa})`,
    kind: 'sr_pullback_mirror' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote:
      `هندسهٔ **منجمدِ آینه‌ای** (نه شناور): SL=${cfg.slPip} / TP=${cfg.tpPip} pip — ` +
      `تبدیلِ آینه‌ایِ slMult↔tpMult روی پیکربندیِ منجمدِ S323 (صفر پارامترِ آزاد)، ` +
      `از artifactِ حکم (results/_s572_mirror) ⇒ در سایت بازتولید نمی‌شود. ` +
      `تا برخورد به TP یا SL نگه‌دار. ` +
      `⚠️ قیدِ تک‌معامله (allow_overlap=false): حکمِ RQS2 روی صفِ FIFO صادر شد ⇒ ` +
      `تا این معامله بسته نشده، سیگنالِ بعدی نباید معاملهٔ جدید باز کند. ` +
      `⚠️ **ورود روی open کندلِ بعد** است (simulate_trades)، نه close کندلِ سیگنال. ` +
      `⚠️ **استخرِ دو-کارتی:** حکمِ S572 روی جمعیتِ تجمیعیِ {M30, H1} است (FIFO تقویمی). ` +
      `اگر هر دو کارت هم‌زمان روشن شوند، **یک** پوزیشن گرفته شود (همان رویدادِ پولبک، ` +
      `نه دو شاهد). مکانیزمِ «شاهدِ کاذبِ بین‌کارتی» سایت همین را اعمال می‌کند. ` +
      `⚠️ در برابرِ ساکنانِ زندهٔ M30/H1 (S547/S312/S431 · S562/S356/S431/S312) ` +
      `مکانیزمِ متفاوتی است (پولبکِ ساختاری در برابرِ تقویم/گپ/شکست) ⇒ ارزشِ مستقل دارد.`,
    filters: [
      `روندِ صعودی: close>EMA50 و EMA50>EMA200 و شیبِ ۱۰-کندلیِ EMA50 ≥ 0 (نسبت به ATR)`,
      `پولبک به حمایتِ خوشه‌ایِ S/R (پیوتِ ۶/۶، ادغام tol=${cfg.srTol}، عمرِ ${cfg.srExpiry}) با فاصله < ${cfg.nearMax}×ATR14`,
      `فضای کافی تا مقاومتِ بعدی: room > ${cfg.roomMin}×ATR14`,
      `RSI-14 < ${cfg.rsiMax} · ADX-14 ≥ ${cfg.adxMin} · پنجرهٔ طلایی ${cfg.hLo}–${cfg.hHi} UTC`,
      `جهت = LONG-only (قانونِ S323) · هندسهٔ آینه‌ایِ TP≥SL ⇒ صفر تورشِ WR-سازی`,
      `صفر پارامترِ آزاد: قانونِ سیگنال از S323 منجمد، تنها تصمیمِ S572 تبدیلِ آینه‌ای بود`,
    ],
  }
  return rawToDecision(raw, meta, cfg.id, price, reg, capital, riskPct)
}

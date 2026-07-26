// ============================================================================
// squeeze_revival_s313.ts — لایهٔ احیاشدهٔ S313 (Bollinger-Squeeze → Breakout)
// ----------------------------------------------------------------------------
// این ماژول لایهٔ سوختهٔ S132/S136/S138 را با معیارِ رسمیِ RQS+ زنده می‌کند.
// نتیجهٔ رسمیِ شبیه‌سازِ رویداد-محور (results/S313_SqueezeBreakout_Xauusd_H1M30_92.md):
//   • XAUUSD H1  → RQS+ = 89.8  (n=807, WR=67.8%, PF=3.27, DD=5.9%, MCL=5)  ✅ ACCEPT
//   • XAUUSD M30 → RQS+ = 92.5  (n=275, WR=67.6%, PF=3.34, DD=2.1%, MCL=4)  ✅ ACCEPT  (نیازمندِ فیلترِ ADX≥30)
//   • M15/M5 و کلِ EURUSD → DEAD (لبه کوچک‌تر از هزینهٔ اسپرد / بی‌لبه).
//
// تفاوتِ بنیادی با لایهٔ سوختهٔ قدیم (squeeze_breakout.ts):
//   لایهٔ قدیم squeeze را «اسکالپِ سریع» مدل می‌کرد (maxHold=96، TP/SL ثابتِ رند).
//   کشفِ probe (results): لبهٔ squeeze روی طلا یک «drift کندِ افق‌بلند (۲۴–۴۸ کندل)»
//   است، نه انفجارِ فوری. پس بهبودهای احیا:
//     ۱) TP/SL بر حسبِ ATRِ لحظهٔ سیگنال (نه عددِ رند)  — تطبیق با رژیمِ نوسان.
//     ۲) maxHold بلند (۴۸ کندل)                          — گرفتنِ drift کند.
//     ۳) SL=3.2·ATR > TP=2.15·ATR (RR به‌نفعِ WR)         — عبور از گیتِ WR≥60.
//     ۴) فیلترِ close-pos ≥ 0.55 (کیفیتِ کندلِ شکست)      — حذفِ fakeout.
//     ۵) Breakeven-Trailing (trigger=1.1·ATR, offset=0.4·ATR) — باختِ بزرگ→سربه‌سر.
//     ۶) فیلترِ ADX≥30 فقط در M30                          — تقویتِ لبه تا عبور از G5.
//
// همپوشانی (results/S313f): با لایه‌های زمان‌محورِ طلا فقط ۲۹.۸–۳۸.۵٪ هم‌زمانی دارد
//   (کمتر از پایهٔ تصادفیِ ۴۳.۳٪) ⇒ لایهٔ کاملاً مستقل/ارتوگونال.
//
// ⚠️ ماژولار و توسعه‌پذیر: این فایل مستقل است و لایه‌های دیگر را دست نمی‌زند؛ فقط
//    از طریقِ روترهای H1/M30 به‌عنوانِ یک لایهٔ کاندیدا فراخوانی می‌شود.
// ============================================================================

import type { AnalysisResult } from './signal'
import type { RouterDecision, RegimeInfo } from './router'
import { computeLots, assetSpec } from './router'
import { ema, bollinger, atr, adx, type Candle } from './indicators'

// پارامترهای برندهٔ احیا (منبعِ حقیقتِ واحد — از results/_s313_FINAL.json).
export interface S313Config {
  id: string               // 'XAUUSD-H1' یا 'XAUUSD-M30'
  tfFa: string             // نامِ فارسیِ تایم‌فریم
  bbPeriod: number         // 20
  bbMult: number           // 2.0
  sqzLookback: number      // 100
  sqzPct: number           // 0.25  (پایین‌ترین ۲۵٪ صدکِ پهنای باند = فشرده)
  breakoutLookback: number // 10
  emaFast: number          // 50
  emaSlow: number          // 200
  atrPeriod: number        // 14
  slAtr: number            // 3.2
  tpAtr: number            // 2.15
  maxHold: number          // 48
  closePosMin: number      // 0.55
  adxMin: number           // H1=0 (غیرفعال)، M30=30
  beTriggerAtr: number     // 1.1
  beOffsetAtr: number      // 0.4
}

// H1: بدونِ فیلترِ ADX (لبه به‌قدرِ کافی قوی است).
export const S313_H1: S313Config = {
  id: 'XAUUSD-H1', tfFa: 'H1 (یک‌ساعته)',
  bbPeriod: 20, bbMult: 2.0, sqzLookback: 100, sqzPct: 0.25,
  breakoutLookback: 10, emaFast: 50, emaSlow: 200, atrPeriod: 14,
  slAtr: 3.2, tpAtr: 2.15, maxHold: 48, closePosMin: 0.55,
  adxMin: 0, beTriggerAtr: 1.1, beOffsetAtr: 0.4,
}

// M30: همان + فیلترِ ADX≥30 (تقویتِ لبه تا عبور از سدِ هزینهٔ اسپردِ طلا).
export const S313_M30: S313Config = {
  ...S313_H1,
  id: 'XAUUSD-M30', tfFa: 'M30 (نیم‌ساعته)', adxMin: 30,
}

export interface S313Signal {
  active: boolean          // ماشهٔ LONG همین الان شلیک کرد؟
  approaching: boolean     // فشرده + روند صعودی، ولی شکست هنوز رخ نداده
  squeezed: boolean        // بازار فشرده است؟
  bwPct: number            // صدکِ پهنای باند (۰..۱)
  priorHigh: number
  trendUp: boolean         // EMA50 > EMA200
  closePos: number         // موقعیتِ close در دامنهٔ کندلِ فعلی (۰..۱)
  strongClose: boolean     // close-pos ≥ closePosMin
  adxVal: number           // ADX فعلی
  adxOk: boolean           // ADX ≥ adxMin (در H1 همیشه true)
  atrVal: number           // ATR در لحظهٔ سیگنال (برای TP/SL)
  reason: string
}

/**
 * محاسبهٔ سیگنالِ زندهٔ S313 از سریِ OHLC (کندلِ H1 یا M30). بدونِ look-ahead:
 * فقط از داده‌های تا آخرین کندلِ بسته‌شده استفاده می‌شود.
 */
export function computeS313(
  open: number[], high: number[], low: number[], close: number[],
  cfg: S313Config,
): S313Signal {
  const n = close.length
  const need = cfg.bbPeriod + cfg.sqzLookback + 2
  const empty = (reason: string): S313Signal => ({
    active: false, approaching: false, squeezed: false, bwPct: 1,
    priorHigh: NaN, trendUp: false, closePos: NaN, strongClose: false,
    adxVal: NaN, adxOk: false, atrVal: NaN, reason,
  })
  if (n < need) return empty('دادهٔ کافی برای باندِ بولینگر / پنجرهٔ فشردگی موجود نیست.')

  const bb = bollinger(close, cfg.bbPeriod, cfg.bbMult)
  const bw: number[] = new Array(n).fill(NaN)
  for (let i = 0; i < n; i++) {
    const mid = bb.mid[i]
    if (isFinite(mid) && mid !== 0 && isFinite(bb.upper[i]) && isFinite(bb.lower[i])) {
      bw[i] = (bb.upper[i] - bb.lower[i]) / mid
    }
  }
  const ef = ema(close, cfg.emaFast)
  const es = ema(close, cfg.emaSlow)

  // کندل‌ها برای ATR/ADX
  const candles: Candle[] = new Array(n)
  for (let k = 0; k < n; k++) {
    candles[k] = { time: 0, open: open[k], high: high[k], low: low[k], close: close[k], volume: 0 }
  }
  const atrArr = atr(candles, cfg.atrPeriod)
  const adxRes = adx(candles, 14)

  const i = n - 1        // کندلِ فعلی (آخرین بسته‌شده)
  const prev = i - 1     // فشردگی «درست پیش از» کندلِ فعلی سنجیده می‌شود

  // صدکِ پهنای باندِ prev در پنجرهٔ sqzLookback (کف = فشرده)
  const lo = Math.max(0, prev - cfg.sqzLookback + 1)
  const window = bw.slice(lo, prev + 1).filter((v) => isFinite(v))
  const bwPrev = bw[prev]
  let bwPct = 1
  if (window.length > 5 && isFinite(bwPrev)) {
    bwPct = window.filter((v) => v <= bwPrev).length / window.length
  }
  const squeezed = isFinite(bwPrev) && bwPct <= cfg.sqzPct

  // سقفِ breakoutLookback کندلِ گذشته (i-brk .. i-1)
  const bLo = Math.max(0, i - cfg.breakoutLookback)
  let priorHigh = -Infinity
  for (let k = bLo; k < i; k++) if (isFinite(high[k])) priorHigh = Math.max(priorHigh, high[k])
  const breakout = isFinite(close[i]) && close[i] > priorHigh

  const trendUp = isFinite(ef[i]) && isFinite(es[i]) && ef[i] > es[i]

  // کیفیتِ کندلِ شکست: موقعیتِ close در دامنهٔ کندل (۱=سقف). فقط شکستِ قاطع.
  const rng = Math.max(high[i] - low[i], 1e-9)
  const closePos = (close[i] - low[i]) / rng
  const strongClose = closePos >= cfg.closePosMin

  // فیلترِ ADX (فقط M30). در H1 که adxMin=0 است همیشه برقرار.
  const adxVal = adxRes.adx[i]
  const adxOk = cfg.adxMin <= 0 || (isFinite(adxVal) && adxVal >= cfg.adxMin)

  const atrVal = atrArr[i]

  const active = squeezed && breakout && trendUp && strongClose && adxOk && isFinite(atrVal) && atrVal > 0
  const approaching = squeezed && trendUp && !breakout && adxOk

  let reason: string
  if (active) {
    reason =
      `فنرِ فشرده رها شد: پهنای باندِ بولینگر در کفِ محلی بود (صدک ${(bwPct * 100).toFixed(0)}٪ ≤ ` +
      `${(cfg.sqzPct * 100).toFixed(0)}٪) و قیمت سقفِ ${cfg.breakoutLookback} کندلِ اخیر ` +
      `(${priorHigh.toFixed(2)}$) را با کندلِ قاطع (بسته‌شدن در ${(closePos * 100).toFixed(0)}٪ بالای دامنه) ` +
      `شکست — هم‌سو با روندِ صعودی (EMA50>EMA200)` +
      (cfg.adxMin > 0 ? ` و قدرتِ روند کافی (ADX=${adxVal.toFixed(0)}≥${cfg.adxMin})` : '') + '.'
  } else if (squeezed && breakout && trendUp && !strongClose) {
    reason =
      `شکستِ صعودی رخ داد اما کندل قاطع نبود (بسته‌شدن فقط در ${(closePos * 100).toFixed(0)}٪ دامنه، ` +
      `کمتر از ${(cfg.closePosMin * 100).toFixed(0)}٪). شکست‌های کم‌کیفیت اغلب کاذب‌اند ⇒ منتظرِ شکستِ قاطع‌تر بمانید.`
  } else if (squeezed && breakout && trendUp && strongClose && !adxOk) {
    reason =
      `شکستِ قاطع رخ داد اما قدرتِ روند کافی نیست (ADX=${isFinite(adxVal) ? adxVal.toFixed(0) : '—'} < ${cfg.adxMin}). ` +
      `در این تایم‌فریم فقط انفجارهایی که در روندِ قوی رخ دهند لبهٔ کافی برای پوششِ هزینه دارند ⇒ ورود انجام نمی‌شود.`
  } else if (approaching) {
    reason =
      `بازار فشرده است (صدکِ پهنای باند ${(bwPct * 100).toFixed(0)}٪) و روند صعودی؛ ` +
      `منتظرِ «تأییدِ شکست»: بسته‌شدنِ قاطعِ قیمت بالای سقفِ ${cfg.breakoutLookback} کندلِ اخیر (${priorHigh.toFixed(2)}$).`
  } else if (!trendUp) {
    reason = `گیتِ روندِ صعودی (EMA50>EMA200) برقرار نیست — این لایه فقط در بایاسِ صعودی LONG می‌گیرد.`
  } else {
    reason = `بازار به‌اندازهٔ کافی فشرده نیست (صدکِ پهنای باند ${(bwPct * 100).toFixed(0)}٪ > ${(cfg.sqzPct * 100).toFixed(0)}٪).`
  }

  return {
    active, approaching, squeezed, bwPct,
    priorHigh: isFinite(priorHigh) ? priorHigh : NaN,
    trendUp, closePos, strongClose, adxVal, adxOk, atrVal, reason,
  }
}

/**
 * تصمیمِ زندهٔ لایهٔ S313 (H1 یا M30). فقط وقتی سیگنالِ فعال/نزدیک هست حالتِ
 * ENTRY/APPROACHING برمی‌گرداند؛ در غیرِ این‌صورت NEUTRAL (تا روتر به fallback برود).
 */
export function decideS313(
  cfg: S313Config, a: AnalysisResult,
  open: number[], high: number[], low: number[], close: number[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const spec = assetSpec('XAUUSD')
  const price = a.price
  const sig = computeS313(open, high, low, close, cfg)

  const reg: RegimeInfo = {
    regime: sig.trendUp ? 'trend_up' : 'range',
    efficiencyRatio: 0, trendy: sig.trendUp, adx: isFinite(sig.adxVal) ? sig.adxVal : 0,
    activeStream: sig.trendUp ? 'bull' : 'none',
    bucket: cfg.id === 'XAUUSD-M30' ? 's313_m30' : 's313_h1',
  }

  const indicators: RouterDecision['indicators'] = [
    { name: 'فشردگیِ بولینگر (صدکِ پهنای باند)',
      value: `${(sig.bwPct * 100).toFixed(0)}٪` + (sig.squeezed ? ` (فشرده ✔)` : ` (هدف: ≤${(cfg.sqzPct * 100).toFixed(0)}٪)`),
      status: sig.squeezed ? 'ok' : 'neutral' },
    { name: 'روندِ کلان (EMA50/200)', value: sig.trendUp ? 'صعودی ✔' : 'صعودی نیست ✘',
      status: sig.trendUp ? 'ok' : 'bad' },
    ...(cfg.adxMin > 0 ? [{ name: `قدرتِ روند (ADX≥${cfg.adxMin})`,
      value: (isFinite(sig.adxVal) ? sig.adxVal.toFixed(0) : '—') + (sig.adxOk ? ' ✔' : ' ✘'),
      status: (sig.adxOk ? 'ok' : 'warn') as 'ok' | 'warn' }] : []),
    { name: 'قیمتِ زنده', value: price.toFixed(2) + '$', status: 'neutral' as const },
  ]

  // ---------- حالتِ ENTRY: ماشهٔ فعال ----------
  if (sig.active) {
    const slDist = cfg.slAtr * sig.atrVal
    const tpDist = cfg.tpAtr * sig.atrVal
    const entry = price
    const sl = entry - slDist
    const tp = entry + tpDist
    const { lots, riskDollars } = computeLots(capital, riskPct, slDist, 1.0, spec)
    const rd = Math.round(riskDollars * 100) / 100
    const lotsTxt = lots != null ? lots.toFixed(2) : '—'
    const beTriggerPrice = cfg.beTriggerAtr * sig.atrVal      // سود لازم برای BE (واحدِ قیمت)
    const beOffsetPrice = cfg.beOffsetAtr * sig.atrVal
    return {
      state: 'ENTRY', regime: reg,
      headline: `ورود خرید (LONG) — انفجارِ پس از فشردگی (${cfg.tfFa})`,
      sourceLayer: {
        code: 'S313', name: `انفجارِ فشردگیِ بولینگر (Squeeze→Breakout، ${cfg.tfFa})`, kind: 'squeeze',
        filters: [
          `فشردگی: صدکِ پهنای باند ≤ ${(cfg.sqzPct * 100).toFixed(0)}٪`,
          `شکستِ سقفِ ${cfg.breakoutLookback} کندل`,
          `روندِ صعودی EMA50>EMA200`,
          `کیفیتِ کندل: close-pos ≥ ${(cfg.closePosMin * 100).toFixed(0)}٪`,
          ...(cfg.adxMin > 0 ? [`قدرتِ روند: ADX ≥ ${cfg.adxMin}`] : []),
        ],
        manage: {
          style: 'let-run-trail', beTriggerR: cfg.beTriggerAtr / cfg.slAtr,
          trailDistPrice: beOffsetPrice, maxHoldBars: cfg.maxHold,
          note: `این یک «drift کندِ امتدادی» است، نه اسکالپِ سریع. وقتی سود به ~${beTriggerPrice.toFixed(2)}$ ` +
            `رسید (۱.۱×ATR)، SL را به کمی بالای نقطهٔ ورود (بریک‌ایون + ${beOffsetPrice.toFixed(2)}$) ببر تا ` +
            `اگر حرکت برگشت، معامله به‌جای ضررِ بزرگ سربه‌سر بسته شود. تا نگهداریِ ${cfg.maxHold} کندل بگذار ` +
            `روندِ صعودی کامل استخراج شود.`,
        },
      },
      reason: `${sig.reason} این ستاپ روی ${cfg.tfFa} با معیارِ مقاومِ RQS+ اثبات شده ` +
        `(WR ~۶۸٪). سفارشِ خرید را باز کنید و طبقِ پلنِ مدیریت، پس از سودِ اولیه SL را به بریک‌ایون ببرید.`,
      direction: 'LONG', entry, tp, sl,
      rr: `SL ${slDist.toFixed(2)}$ (${cfg.slAtr}×ATR) / TP ${tpDist.toFixed(2)}$ (${cfg.tpAtr}×ATR) — نگهداریِ تا ${cfg.maxHold} کندل`,
      sizing: {
        lotMultiplier: 1.0, label: 'حجمِ پایه',
        note: `SL بر حسبِ نوسانِ لحظه‌ای (ATR) تنظیم شده؛ حجم را متناسب با ریسکِ ${riskPct}% نگه دارید.`,
        lots: lots ?? undefined, riskDollars: rd, capital, riskPct,
        capitalNote: `با سرمایهٔ ${capital.toLocaleString('en-US')}$ و ریسکِ ${riskPct}% (${rd.toLocaleString('en-US')}$)، ` +
          `حجمِ پیشنهادی ${lotsTxt} لات (۱۰۰ اونس). اگر SL بخورد ~${rd.toLocaleString('en-US')}$ ضرر می‌کنید.`,
      },
      tpPlan: { multiplier: cfg.tpAtr, note: `TP = ${cfg.tpAtr}×ATR بالاتر از ورود (متغیر با نوسانِ لحظه‌ای — نه عددِ ثابت).` },
      slPlan: { multiplier: cfg.slAtr, note: `SL = ${cfg.slAtr}×ATR پایین‌تر از ورود (متغیر با نوسانِ لحظه‌ای).` },
      indicators,
    }
  }

  // ---------- حالتِ APPROACHING: فشرده + روند صعودی، منتظرِ شکست ----------
  if (sig.approaching) {
    return {
      state: 'APPROACHING', regime: reg,
      headline: `نزدیکِ سیگنالِ خرید — فنرِ فشرده، منتظرِ شکست (${cfg.tfFa})`,
      sourceLayer: { code: 'S313', name: `انفجارِ فشردگیِ بولینگر (${cfg.tfFa})`, kind: 'squeeze' },
      reason: sig.reason,
      confirmations: [
        { label: 'فشردگیِ بولینگر (پهنای باند در کف)', met: true,
          detail: `صدکِ پهنای باند ${(sig.bwPct * 100).toFixed(0)}٪ ≤ ${(cfg.sqzPct * 100).toFixed(0)}٪.` },
        { label: 'روندِ صعودی EMA50>EMA200', met: true, detail: 'بایاسِ کلان صعودی است.' },
        { label: `شکستِ قاطعِ سقفِ ${cfg.breakoutLookback} کندل`, met: false,
          detail: `منتظرِ بسته‌شدنِ قیمت بالای ${isFinite(sig.priorHigh) ? sig.priorHigh.toFixed(2) : '—'}$ با کندلِ قوی.` },
      ],
      indicators,
    }
  }

  // ---------- حالتِ NEUTRAL: شرایط برقرار نیست (روتر به fallback می‌رود) ----------
  // طبقِ تعریفِ سایت: در خنثی هم باید صریحاً بگوید کدام لایه ناظرِ این کارت است.
  return {
    state: 'NEUTRAL', regime: reg,
    headline: `خنثی — شرایطِ انفجارِ فشردگی برقرار نیست (${cfg.tfFa})`,
    reason: sig.reason,
    sourceLayer: { code: 'S313', name: `انفجارِ فشردگیِ بولینگر (${cfg.tfFa})`, kind: 'squeeze' },
    indicators,
  }
}

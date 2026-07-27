// ============================================================================
// strategy_registry.ts — رجیستریِ ماژولارِ لایه‌های احیاشده (RQS+ ≥ 80)
// ----------------------------------------------------------------------------
// این فایل «مغزِ مسیریابیِ» سایتِ بازطراحی‌شده است: پس از حذفِ کاملِ استراتژی‌های
// قدیمی (طبق User Note)، تنها ۱۱ لایهٔ احیاشدهٔ ACCEPTED در سایت باقی می‌مانند و
// این رجیستری آن‌ها را به کارت‌های (جفت‌ارز × تایم‌فریم) نگاشت می‌کند.
//
// معماری (ماژولار/توسعه‌پذیر — نباید در هیچ به‌روزرسانی از بین برود):
//   • هر لایه یک تابعِ decide* مستقل دارد که RouterDecision برمی‌گرداند.
//   • CARD_LAYERS: نگاشتِ «کارت → فهرستِ لایه‌های فعال (به‌ترتیبِ اولویت)».
//   • runCard(): لایه‌های کارت را اجرا می‌کند و طبقِ اولویتِ حالت (ENTRY > APPROACHING
//     > NEUTRAL) یک تصمیمِ اصلی برمی‌گرداند؛ بقیهٔ لایه‌های فعال در otherLayers می‌آیند.
//   • افزودنِ لایهٔ جدید = فقط یک ورودی در REGISTRY + CARD_LAYERS (بدونِ دستکاریِ کارت‌ها).
//
// ۱۱ لایهٔ احیاشده:
//   زمان-محور:   S310 (EOM drift)، S312 (mid-month drift)
//   ماژولِ آماده: S313 (squeeze)، S326 (streak-rev)، S327 (sell-climax)
//   ماژولِ نو:    S321 (ribbon)، S322 (ichimoku)، S323 (S/R pullback)،
//                 S324 (liquidity-sweep)، S328 (RSI21 fade)، S330 (ORB fade)
// ============================================================================

import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision } from './router'

// --- ماژول‌های آمادهٔ قبلی ---
import { decideS313, S313_M30, S313_H1 } from './squeeze_revival_s313'
import { computeStreakReversal, STREAK_REV_CFG, type StreakRevConfig } from './streak_reversal_s326'
import { computeSellClimax, SELL_CLIMAX_CFG, type SellClimaxConfig } from './sell_climax_s327'
import {
  computeEndOfMonth, EOM_ENTRY_HOURS, EOM_APPROACH_HOUR, EOM_SL_PIP, EOM_TP_PIP, EOM_MAX_HOLD,
} from './end_of_month_drift'
import {
  computeMidMonth, MID_ENTRY_HOURS, MID_APPROACH_HOUR, MID_SL_PIP, MID_TP_PIP, MID_MAX_HOLD,
} from './mid_month_drift'

// --- ماژولِ لایه‌های نو ---
import {
  decideS321, S321_CFG, decideS322, S322_CFG, decideS323, S323_CFG,
  decideS324, S324_CFG, decideS328, S328_CFG, decideS330, S330_CFG,
  rawToDecision, type RawSignal, type DecideMeta,
} from './revived_strategies'
import { assetSpec, computeLots, type RegimeInfo } from './router'
// --- ماژولِ نوِ این نشست: احیای squeeze روی H4 (ADX/DI) و M15 (r2+hurst) ---
import { decideS332, S332_CFG } from './squeeze_s332'

const GOLD_PIP = 0.1

// ---------------------------------------------------------------------------
// آداپترِ لایه: امضای یکنواخت برای همهٔ لایه‌ها
//   ورودی: کارت (asset-tf)، AnalysisResult، کندل‌ها، ساعت/زمانِ UTC، سرمایه/ریسک
//   خروجی: RouterDecision (یا null اگر لایه روی این کارت فعال نیست)
// ---------------------------------------------------------------------------
export interface LayerContext {
  cardId: string
  a: AnalysisResult
  candles: Candle[]
  utcHour: number
  times: number[]
  capital: number
  riskPct: number
}
export type LayerFn = (ctx: LayerContext) => RouterDecision | null

function lightRegime(adxVal: number, trendy: boolean, bucket: string): RegimeInfo {
  return { regime: trendy ? 'trend_up' : 'range', efficiencyRatio: 0, trendy, adx: isFinite(adxVal) ? adxVal : 0, activeStream: trendy ? 'bull' : 'none', bucket }
}

// ---- آداپترِ S326 (Streak-Reversal) ----
function s326Layer(cfg: StreakRevConfig): LayerFn {
  return (ctx) => {
    const sig = computeStreakReversal(ctx.candles, cfg)
    const price = ctx.a.price
    const raw: RawSignal = {
      active: sig.active, approaching: sig.approaching, direction: 'LONG',
      slDist: cfg.slMult * sig.atrVal, tpDist: cfg.tpMult * sig.atrVal, maxHoldBars: cfg.maxHold,
      reason: sig.reason,
      approachReason: sig.approaching ? `بازگشتِ RSI به زیرِ ${cfg.rsiMax}` : undefined,
      indicators: [
        { name: `رگهٔ نزولی (≥${cfg.streakN} کندل)`, value: `${sig.streak}` + (sig.streak >= cfg.streakN ? ' ✔' : ''), status: sig.streak >= cfg.streakN ? 'ok' : 'neutral' },
        { name: `RSI-14 اشباعِ فروش (≤${cfg.rsiMax})`, value: isFinite(sig.rsiVal) ? sig.rsiVal.toFixed(0) : '—', status: sig.rsiVal <= cfg.rsiMax ? 'ok' : 'warn' },
        { name: `روندِ کلان (EMA${cfg.emaTrend})`, value: sig.aboveTrend ? 'صعودی ✔' : 'نزولی ✘', status: sig.aboveTrend ? 'ok' : 'bad' },
      ],
    }
    const reg = lightRegime(0, sig.aboveTrend, 's326_streak')
    return rawToDecision(raw, {
      code: 'S326', name: 'Streak-Reversal بازگشتی', kind: 'mean-reversion' as any,
      manageStyle: 'fixed-tp-sl', manageNote: 'بازگشت به میانگین با TP<SL؛ هدفِ نزدیک را زود بگیر، SL جابه‌جا نشود.',
      filters: [`رگهٔ ≥${cfg.streakN}`, `RSI≤${cfg.rsiMax}`, `EMA${cfg.emaTrend} صعودی`, cfg.runMinAtr > 0 ? `شتابِ رگه≥${cfg.runMinAtr}×ATR` : 'بدونِ قیدِ شتاب'],
    }, ctx.cardId, price, reg, ctx.capital, ctx.riskPct)
  }
}

// ---- آداپترِ S327 (Sell-Climax Reversal) ----
function s327Layer(cfg: SellClimaxConfig): LayerFn {
  return (ctx) => {
    const sig = computeSellClimax(ctx.candles, cfg)
    const price = ctx.a.price
    const raw: RawSignal = {
      active: sig.active, approaching: sig.approaching, direction: 'LONG',
      slDist: cfg.slMult * sig.atrVal, tpDist: cfg.tpMult * sig.atrVal, maxHoldBars: cfg.maxHold,
      reason: sig.reason,
      approachReason: sig.approaching ? `تأییدِ بازگشت (RSI≤${cfg.rsiMax} + کندلِ صعودی)` : undefined,
      indicators: [
        { name: `کندلِ کلایمکس (بدنه≥${cfg.kBody}×MA)`, value: sig.isClimax ? 'بله ✔' : 'خیر', status: sig.isClimax ? 'ok' : 'neutral' },
        { name: `RSI-14 اشباعِ فروش (≤${cfg.rsiMax})`, value: isFinite(sig.rsiVal) ? sig.rsiVal.toFixed(0) : '—', status: sig.rsiVal <= cfg.rsiMax ? 'ok' : 'warn' },
        { name: `روندِ کلان (EMA${cfg.emaTrend})`, value: sig.aboveTrend ? 'صعودی ✔' : 'نزولی ✘', status: sig.aboveTrend ? 'ok' : 'bad' },
      ],
    }
    const reg = lightRegime(0, sig.aboveTrend, 's327_climax')
    return rawToDecision(raw, {
      code: 'S327', name: 'Sell-Climax بازگشتی (Brooks)', kind: 'price-action' as any,
      manageStyle: 'fixed-tp-sl', manageNote: 'تخلیهٔ فروش (Brooks exhaustion) با TP<SL؛ هدفِ نزدیک را بگیر، SL جابه‌جا نشود.',
      filters: [`کلایمکس kBody=${cfg.kBody}`, `body/range≥${cfg.brMin}`, `RSI≤${cfg.rsiMax}`, `EMA${cfg.emaTrend} صعودی`],
    }, ctx.cardId, price, reg, ctx.capital, ctx.riskPct)
  }
}

// ---- آداپترِ S310 (End-of-Month Drift) ----
const s310Layer: LayerFn = (ctx) => {
  const sig = computeEndOfMonth(ctx.times, ctx.utcHour)
  const price = ctx.a.price
  const active = sig.state === 'ENTRY'
  const approaching = sig.state === 'APPROACHING'
  const raw: RawSignal = {
    active, approaching, direction: 'LONG',
    slDist: EOM_SL_PIP * GOLD_PIP, tpDist: EOM_TP_PIP * GOLD_PIP, maxHoldBars: EOM_MAX_HOLD,
    reason: sig.reason,
    approachReason: approaching ? `ورود به ساعاتِ ${EOM_ENTRY_HOURS.join('/')} UTC در پنجرهٔ پایانِ ماه` : undefined,
    indicators: [
      { name: 'پنجرهٔ پایانِ ماه (۷ روزِ مانده)', value: sig.isEomWindow ? 'باز ✔' : 'بسته', status: sig.isEomWindow ? 'ok' : 'neutral' },
      { name: 'ساعتِ UTC', value: `${sig.utcHour}:00` + (EOM_ENTRY_HOURS.includes(sig.utcHour) ? ' (ورود)' : ''), status: EOM_ENTRY_HOURS.includes(sig.utcHour) ? 'ok' : 'neutral' },
    ],
    // 🕒 باگِ User Note #۳: دروازهٔ زمانی برای نوارِ شمارشِ معکوس زیرِ کارت.
    timeGate: {
      layerCode: 'S310', label: 'درایوِ پایانِ ماه',
      entryHoursUtc: EOM_ENTRY_HOURS,
      dayOfMonthNote: '۷ روزِ پایانیِ هر ماه',
      windowOpen: sig.isEomWindow && EOM_ENTRY_HOURS.includes(sig.utcHour),
      endHourUtc: Math.max(...EOM_ENTRY_HOURS) + 1,
    },
  }
  const reg = lightRegime(0, true, 's310_eom')
  return rawToDecision(raw, {
    code: 'S310', name: 'End-of-Month Drift', kind: 'time' as any,
    manageStyle: 'fixed-tp-sl', manageNote: `هدف/حدِ ثابت (${EOM_TP_PIP}/${EOM_SL_PIP} pip)؛ تا پایانِ پنجره یا برخورد نگه‌دار.`,
    filters: ['۷ روزِ پایانِ ماه', `ساعاتِ ${EOM_ENTRY_HOURS.join('/')} UTC`, 'فیلترِ کیفیت (ATR/close-pos/EMA200)'],
  }, ctx.cardId, price, reg, ctx.capital, ctx.riskPct)
}

// ---- آداپترِ S312 (Mid-Month Drift) — SL/TP per-TF ----
function s312Layer(slPip: number, tpPip: number, maxHold: number): LayerFn {
  return (ctx) => {
    const sig = computeMidMonth(ctx.times, ctx.utcHour)
    const price = ctx.a.price
    const active = sig.state === 'ENTRY'
    const approaching = sig.state === 'APPROACHING'
    const raw: RawSignal = {
      active, approaching, direction: 'LONG',
      slDist: slPip * GOLD_PIP, tpDist: tpPip * GOLD_PIP, maxHoldBars: maxHold,
      reason: sig.reason,
      approachReason: approaching ? 'ورود به ساعاتِ معاملاتیِ روزِ میانِ‌ماه' : undefined,
      indicators: [
        { name: 'روزِ میانِ‌ماه (dom ∈ {۱۰,۱۳,۲۰})', value: sig.isMidWindow ? 'بله ✔' : 'خیر', status: sig.isMidWindow ? 'ok' : 'neutral' },
        { name: 'ساعتِ UTC', value: `${sig.utcHour}:00`, status: MID_ENTRY_HOURS.includes(sig.utcHour) ? 'ok' : 'neutral' },
      ],
      // 🕒 باگِ User Note #۳: دروازهٔ زمانی برای نوارِ شمارشِ معکوس زیرِ کارت.
      timeGate: {
        layerCode: 'S312', label: 'درایوِ میانهٔ ماه',
        entryHoursUtc: MID_ENTRY_HOURS,
        dayOfMonthNote: 'روزهای ۱۰، ۱۳ و ۲۰ هر ماه',
        activeDaysOfMonth: [10, 13, 20],
        windowOpen: sig.isMidWindow && MID_ENTRY_HOURS.includes(sig.utcHour),
        endHourUtc: Math.max(...MID_ENTRY_HOURS) + 1,
      },
    }
    const reg = lightRegime(0, true, 's312_mid')
    return rawToDecision(raw, {
      code: 'S312', name: 'Mid-Month Drift', kind: 'time' as any,
      manageStyle: 'fixed-tp-sl', manageNote: `هدف/حدِ متقارنِ ثابت (${tpPip}/${slPip} pip)؛ تا پایانِ پنجره یا برخورد نگه‌دار.`,
      filters: ['روزهای ۱۰/۱۳/۲۰ ماه', 'ساعاتِ معاملاتی', 'فیلترِ کیفیت (روندِ کلان)'],
    }, ctx.cardId, price, reg, ctx.capital, ctx.riskPct)
  }
}

// ---------------------------------------------------------------------------
// آداپترهای نازک برای ماژول‌های دارای decide* (فقط cfg را می‌بندند)
// ---------------------------------------------------------------------------
const s313Layer = (cfg: typeof S313_M30): LayerFn => (ctx) => {
  const o = ctx.candles.map(c => c.open), h = ctx.candles.map(c => c.high)
  const l = ctx.candles.map(c => c.low), c2 = ctx.candles.map(c => c.close)
  return decideS313(cfg, ctx.a, o, h, l, c2, ctx.capital, ctx.riskPct)
}
const s321Layer = (cfg: typeof S321_CFG[string]): LayerFn => (ctx) => decideS321(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
const s322Layer = (cfg: typeof S322_CFG[string]): LayerFn => (ctx) => decideS322(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
const s323Layer = (cfg: typeof S323_CFG[string]): LayerFn => (ctx) => decideS323(cfg, ctx.a, ctx.candles, ctx.utcHour, ctx.capital, ctx.riskPct)
const s324Layer = (cfg: typeof S324_CFG[string]): LayerFn => (ctx) => decideS324(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
const s328Layer = (cfg: typeof S328_CFG[string]): LayerFn => (ctx) => decideS328(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
const s330Layer = (cfg: typeof S330_CFG[string]): LayerFn => (ctx) => decideS330(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)
// لایهٔ نوِ این نشست: squeeze احیاشده (H4=ADX/DI · M15=r2+hurst)
const s332Layer = (cfg: typeof S332_CFG[string]): LayerFn => (ctx) => decideS332(cfg, ctx.a, ctx.candles, ctx.capital, ctx.riskPct)

// ---------------------------------------------------------------------------
// نگاشتِ کارت → لایه‌های فعال (به‌ترتیبِ اولویت). فقط لایه‌هایی که روی همان
// (جفت‌ارز × TF) با RQS+ ≥ 80 ACCEPTED شده‌اند. منبع: نامِ فایل‌های results/.
// افزودنِ کارت/لایهٔ جدید فقط این جدول را تغییر می‌دهد (ماژولار/توسعه‌پذیر).
//
//   کارت         لایه‌های ACCEPTED (منبعِ نامِ فایل results/)
//   XAUUSD-M5    S330(FADE) · S328(SHORT) · S327(LONG) · S326(LONG)
//   XAUUSD-M15   S324(LONG) · S322(LONG) · S323(LONG) · S310(LONG) · S312(LONG)
//   XAUUSD-M30   S313(LONG) · S324(SHORT) · S321(L+S) · S327(LONG) · S326(LONG) · S323(LONG) · S312(LONG)
//   XAUUSD-H1    S313(LONG) · S328(SHORT) · S327(LONG) · S323(LONG) · S312(LONG)
//   XAUUSD-H4    S327(LONG)
//   EURUSD-M15   S326(LONG)
//   EURUSD-M30   S327(LONG)
// ---------------------------------------------------------------------------
export const CARD_LAYERS: Record<string, LayerFn[]> = {
  'XAUUSD-M5': [
    s330Layer(S330_CFG['XAUUSD-M5']),
    s328Layer(S328_CFG['XAUUSD-M5']),
    s327Layer(SELL_CLIMAX_CFG['XAUUSD-M5']),
    s326Layer(STREAK_REV_CFG['XAUUSD-M5']),
  ],
  'XAUUSD-M15': [
    s324Layer(S324_CFG['XAUUSD-M15']),
    s322Layer(S322_CFG['XAUUSD-M15']),
    s323Layer(S323_CFG['XAUUSD-M15']),
    s310Layer,
    s312Layer(295, 295, 48),
  ],
  'XAUUSD-M30': [
    s313Layer(S313_M30),
    s324Layer(S324_CFG['XAUUSD-M30']),
    s321Layer(S321_CFG['XAUUSD-M30']),
    s327Layer(SELL_CLIMAX_CFG['XAUUSD-M30']),
    s326Layer(STREAK_REV_CFG['XAUUSD-M30']),
    s323Layer(S323_CFG['XAUUSD-M30']),
    s312Layer(295, 295, 36),
  ],
  'XAUUSD-H1': [
    s313Layer(S313_H1),
    s328Layer(S328_CFG['XAUUSD-H1']),
    s327Layer(SELL_CLIMAX_CFG['XAUUSD-H1']),
    s323Layer(S323_CFG['XAUUSD-H1']),
    s312Layer(395, 395, 24),
  ],
  'XAUUSD-H4': [
    s332Layer(S332_CFG['XAUUSD-H4']),   // احیای squeeze با فیلترِ ADX/DI — RQS+=92.1
    s327Layer(SELL_CLIMAX_CFG['XAUUSD-H4']),
  ],
  'EURUSD-M15': [
    s326Layer(STREAK_REV_CFG['EURUSD-M15']),
  ],
  'EURUSD-M30': [
    s327Layer(SELL_CLIMAX_CFG['EURUSD-M30']),
  ],
}

export const REGISTERED_CARDS = Object.keys(CARD_LAYERS)

// ---------------------------------------------------------------------------
// اجرای یک کارت: همهٔ لایه‌های فعالِ آن را صدا می‌زند و طبقِ اولویتِ حالت
// (ENTRY > APPROACHING > NEUTRAL) تصمیمِ اصلی را انتخاب می‌کند. سایرِ لایه‌های
// فعال در otherLayers جمع می‌شوند (نمایشِ collapsed زیرِ سیگنالِ اصلی).
// ---------------------------------------------------------------------------
const STATE_RANK: Record<string, number> = { ENTRY: 3, APPROACHING: 2, NEUTRAL: 1 }

export function runCard(ctx: LayerContext): RouterDecision {
  const layers = CARD_LAYERS[ctx.cardId] || []
  const decisions: RouterDecision[] = []
  for (const fn of layers) {
    try {
      const d = fn(ctx)
      if (d) decisions.push(d)
    } catch (e) {
      // لایهٔ مشکل‌دار نباید کلِ کارت را بشکند (پایداری)
      console.error(`[registry] layer error on ${ctx.cardId}:`, (e as Error)?.message)
    }
  }
  if (decisions.length === 0) {
    return {
      state: 'NEUTRAL',
      regime: lightRegime(0, false, 'no_layer'),
      headline: 'خنثی — لایهٔ فعالی برای این کارت نیست',
      reason: 'برای این ترکیبِ جفت‌ارز/تایم‌فریم لایهٔ احیاشده‌ای ثبت نشده است.',
      indicators: [],
    }
  }
  // مرتب‌سازی: بالاترین رتبهٔ حالت، سپس بالاترین probability (اگر بود)
  decisions.sort((x, y) => {
    const r = (STATE_RANK[y.state] || 0) - (STATE_RANK[x.state] || 0)
    if (r !== 0) return r
    return (y.probability || 0) - (x.probability || 0)
  })
  const primary = decisions[0]
  const others = decisions.slice(1).filter(d => d.state === 'ENTRY' || d.state === 'APPROACHING')
  if (others.length > 0) {
    // 🔧 باگِ User Note #۴: هر لایهٔ همزمانِ فعال، اعدادِ کاملِ معاملهٔ خودش را حمل می‌کند
    //   تا کاربر بتواند *همزمان چند لایه* را مستقل معامله کند (نه فقط لایهٔ اصلی را).
    primary.otherLayers = others.map(d => ({
      code: d.sourceLayer?.code || '—',
      name: d.sourceLayer?.name || d.headline,
      kind: (d.sourceLayer?.kind as string) || 'unknown',
      state: d.state as 'ENTRY' | 'APPROACHING',
      direction: d.direction,
      reason: d.reason,
      confirmations: d.confirmations,
      // اعدادِ معامله فقط وقتی state=ENTRY است معنا دارند:
      entry: d.state === 'ENTRY' ? d.entry : undefined,
      tp: d.state === 'ENTRY' ? d.tp : undefined,
      sl: d.state === 'ENTRY' ? d.sl : undefined,
      rr: d.state === 'ENTRY' ? d.rr : undefined,
      probability: d.probability,
      sizing: d.state === 'ENTRY' ? d.sizing : undefined,
      tpPlan: d.state === 'ENTRY' ? d.tpPlan : undefined,
    }))
  }
  // 🕒 باگِ User Note #۳: جمع‌آوریِ دروازه‌های زمانیِ *همهٔ* لایه‌های این کارت (نه فقط
  //   primary) برای نوارِ شمارشِ معکوسِ مستقلِ ۲۴ساعته. حذفِ تکراری بر پایهٔ layerCode.
  const gates = decisions
    .map(d => d.timeGate)
    .filter((g): g is NonNullable<RouterDecision['timeGate']> => !!g)
  if (gates.length > 0) {
    const seen = new Set<string>()
    primary.cardTimeGates = gates.filter(g => {
      if (seen.has(g.layerCode)) return false
      seen.add(g.layerCode)
      return true
    })
  }
  return primary
}

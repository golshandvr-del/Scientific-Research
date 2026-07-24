// ============================================================================
// XAUUSD Higher-Timeframe Routers (H1 / H4 / D1) — ماژولِ ماژولارِ تایم‌فریم‌های بالا
// ----------------------------------------------------------------------------
// پاسخ به User Note (این نشست فقط دیباگ/بهبودِ سایت + ماژولار کردنِ آن):
//   «کارت‌های یک‌ساعت، چهارساعت و یک‌روز برای طلا باید اضافه شود.»
//   «طراحیِ سایت ماژولار شود — برای هر کارت منطقِ تصمیم‌گیریِ ۴-حالتهٔ مستقل.»
//
// هر تایم‌فریم تابعِ decide مخصوصِ خودش را دارد (decideGoldH1 / decideGoldH4 /
// decideGoldD1) تا هر کارت ظرفیتِ استفاده از استراتژیِ اختصاصیِ خودش را داشته باشد.
// این ماژول کاملاً مستقل است ⇒ افزودن/تغییرِ منطقِ یک تایم‌فریم بقیه را دست نمی‌زند.
//
// ⚠️ وضعیتِ فعلیِ تحقیق: روی H1/H4/D1 طلا هنوز هیچ لایهٔ اثبات‌شده‌ای (WR≥۴۰٪ + گیتِ
//    سختِ ضدِ overfit) کشف نشده است. طبقِ قانونِ اصلیِ پروژه (فقط سودِ خالصِ اثبات‌شده)
//    این کارت‌ها فعلاً سیگنالِ ورودِ خام نمی‌دهند؛ بلکه در «حالتِ تحقیقِ فعال» کار می‌کنند:
//    وضعیتِ روند/رژیمِ همان تایم‌فریم را با شاخص‌های مخصوصِ خودش شفاف نشان می‌دهند و
//    آماده‌اند تا در تحقیقِ آینده منطقِ ورود/خروجِ اثبات‌شده به آن‌ها اضافه شود.
//    (این دقیقاً همان ساختارِ «قالبِ خامِ آمادهٔ گسترش» است، اما هر تایم‌فریم منطقِ
//     تحلیلیِ مستقلِ خودش را دارد — نه یک placeholder یکسان برای همه.)
//
// 🎯 قانونِ شمارهٔ ۱ پروژه: هدف فقط «سودِ خالصِ بیشتر» است، نه Win-Rate.
//    تعریفِ رسمیِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD.
// ============================================================================

import type { AnalysisResult } from './signal'
import type { RouterDecision, RegimeInfo } from './router'
import { computeLots, assetSpec } from './router'
import * as ind from './indicators'
import { computeTrendLine, TREND_LINE_CFG, type TrendLineConfig } from './gold_trend_line'
import { channelDecision, CHANNEL_CFG } from './gold_channel'

// ---------------------------------------------------------------------------
// پیکربندیِ اختصاصیِ هر تایم‌فریم (هر کارت پارامترهای مستقلِ خودش را دارد).
// این جدول باعث می‌شود منطقِ مشترکِ تحلیل، خروجیِ متناسب با تایم‌فریم بدهد و در عینِ
// حال هر تابعِ decide مستقل بماند (ماژولار). دوره‌های EMA/RSI بر پایهٔ رفتارِ متعارفِ
// هر افق انتخاب شده‌اند (H1 سریع‌تر، D1 کندتر) و آماده‌ی تنظیمِ دقیق در تحقیقِ آینده.
// ---------------------------------------------------------------------------
interface HtfConfig {
  id: string
  tfFa: string                 // نامِ فارسیِ تایم‌فریم برای نمایش
  emaFast: number
  emaSlow: number
  rsiPeriod: number
  adxTrendMin: number          // آستانهٔ ADX برای «روندی‌بودن» در این افق
  bucket: string               // نامِ سطلِ رژیم (شناسه‌ی داخلی)
}

const H1_CFG: HtfConfig = { id: 'XAUUSD-H1', tfFa: 'H1 (یک‌ساعته)',   emaFast: 20, emaSlow: 50,  rsiPeriod: 14, adxTrendMin: 22, bucket: 'h1_research' }
const H4_CFG: HtfConfig = { id: 'XAUUSD-H4', tfFa: 'H4 (چهارساعته)', emaFast: 20, emaSlow: 50,  rsiPeriod: 14, adxTrendMin: 20, bucket: 'h4_research' }
const D1_CFG: HtfConfig = { id: 'XAUUSD-D1', tfFa: 'D1 (روزانه)',    emaFast: 20, emaSlow: 50,  rsiPeriod: 14, adxTrendMin: 18, bucket: 'd1_research' }

/** رژیمِ سبکِ همین تایم‌فریم (بر پایهٔ رابطهٔ EMAها + ADX). */
function htfRegime(cfg: HtfConfig, emaFast: number, emaSlow: number, adx: number): RegimeInfo {
  const up = emaFast > emaSlow
  const trendy = adx >= cfg.adxTrendMin
  return {
    regime: trendy ? (up ? 'trend_up' : 'trend_down') : 'range',
    efficiencyRatio: 0,
    trendy,
    adx,
    activeStream: trendy ? (up ? 'bull' : 'bear') : 'none',
    bucket: cfg.bucket,
  }
}

// ---------------------------------------------------------------------------
// موتورِ تحلیلِ مشترکِ تایم‌فریم‌های بالا (هستهٔ ریاضی) — هر تابعِ decide آن را با
// پیکربندیِ مخصوصِ خودش صدا می‌زند. خروجی همیشه NEUTRAL (حالتِ تحقیقِ فعال) است چون
// هنوز لایهٔ اثبات‌شده‌ای روی این افق نداریم؛ اما تحلیلِ روند/رژیم واقعی و مخصوصِ همان
// تایم‌فریم است تا کاربر تصویرِ شفافی از افقِ بالادستی داشته باشد.
// ---------------------------------------------------------------------------
function analyzeHtf(cfg: HtfConfig, a: AnalysisResult, close: number[]): RouterDecision {
  const n = close.length
  const emaFast = ind.ema(close, cfg.emaFast)[n - 1]
  const emaSlow = ind.ema(close, cfg.emaSlow)[n - 1]
  const rsi = a.rsi14 ?? 50
  const adx = a.adx ?? 0
  const price = a.price
  const regime = htfRegime(cfg, emaFast, emaSlow, adx)

  const up = emaFast > emaSlow
  const trendFa = regime.trendy
    ? (up ? 'روندِ صعودی' : 'روندِ نزولی')
    : 'رنج/بی‌روند'
  const trendColor: 'ok' | 'warn' | 'bad' | 'neutral' =
    regime.trendy ? (up ? 'ok' : 'bad') : 'neutral'

  return {
    state: 'NEUTRAL',
    regime,
    headline: `طلا ${cfg.tfFa} — حالتِ تحقیقِ فعال (${trendFa})`,
    reason:
      `این کارت افقِ ${cfg.tfFa} را با منطقِ تحلیلیِ مستقلِ خودش پایش می‌کند. ` +
      `هم‌اکنون رابطهٔ EMA(${cfg.emaFast})/EMA(${cfg.emaSlow}) وضعیتِ «${trendFa}» را نشان می‌دهد ` +
      `و ADX روی ${adx.toFixed(1)} است. طبقِ قانونِ اصلیِ پروژه، تا وقتی لایه‌ای با ` +
      `WR≥۴۰٪ و سودِ خالصِ مثبت که گیتِ سختِ ضدِ overfit را روی همین تایم‌فریم پاس کند ` +
      `کشف نشود، این کارت سیگنالِ ورودِ خام نمی‌دهد. این افق برای «هم‌راستاییِ روندِ ` +
      `بالادستی» و به‌عنوان بسترِ افزودنِ استراتژیِ اختصاصیِ آینده آماده است.`,
    sourceLayer: {
      code: '—',
      name: `طلا ${cfg.tfFa} — بدونِ لایهٔ فعال (در دستِ تحقیق)`,
      kind: 'regime-ml',
    },
    indicators: [
      { name: 'تایم‌فریم', value: cfg.tfFa, status: 'neutral' },
      { name: 'وضعیتِ روند', value: trendFa, status: trendColor },
      { name: `EMA(${cfg.emaFast})`, value: emaFast ? emaFast.toFixed(2) : '—', status: 'neutral' },
      { name: `EMA(${cfg.emaSlow})`, value: emaSlow ? emaSlow.toFixed(2) : '—', status: 'neutral' },
      { name: 'RSI(14)', value: rsi.toFixed(1), status: rsi >= 70 ? 'warn' : rsi <= 30 ? 'warn' : 'neutral' },
      { name: 'ADX', value: adx.toFixed(1), status: regime.trendy ? 'ok' : 'neutral' },
      { name: 'قیمتِ فعلی', value: price ? price.toFixed(2) : '—', status: 'neutral' },
      { name: 'وضعیتِ تحقیق', value: 'حالتِ تحقیقِ فعال (بدونِ سیگنالِ خام)', status: 'neutral' },
    ],
  }
}

// ---------------------------------------------------------------------------
// لایهٔ اثبات‌شدهٔ S215 (Al Brooks «Trend Lines»، فصلِ ۱۳) — Failed-Breakout LONG.
// این تابعِ مشترک، موتورِ ماژولارِ gold_trend_line را با پیکربندیِ اختصاصیِ همان
// تایم‌فریم اجرا و به یک تصمیمِ ۴-حالتی (با بخشِ مدیریتِ معامله) تبدیل می‌کند.
// روی H1/H4 طلا سهمِ مستقلِ اثبات‌شده دارد (بک‌تستِ S215b؛ WF-4/4). اگر ماشه فعال
// نباشد، به تحلیلِ «حالتِ تحقیقِ فعالِ» همان تایم‌فریم برمی‌گردیم (analyzeHtf).
// ---------------------------------------------------------------------------
const PIP = 0.1                          // طلا: ۱ pip = ۰.۱ واحدِ قیمت

function trendLineEntry(
  cfg: TrendLineConfig, htfCfg: HtfConfig, a: AnalysisResult,
  open: number[], high: number[], low: number[], close: number[],
  capital: number, riskPct: number,
): RouterDecision {
  const tl = computeTrendLine(open, high, low, close, cfg)
  const n = close.length
  const emaFast = ind.ema(close, htfCfg.emaFast)[n - 1]
  const emaSlow = ind.ema(close, htfCfg.emaSlow)[n - 1]
  const adx = a.adx ?? 0
  const regime = htfRegime(htfCfg, emaFast, emaSlow, adx)
  const spec = assetSpec('XAUUSD')

  // شاخص‌های مخصوصِ لایهٔ trend-line (شفافیت برای کاربر — بدونِ آمارِ داخلیِ تحقیق).
  const tlInd: RouterDecision['indicators'] = [
    { name: 'تایم‌فریم', value: htfCfg.tfFa, status: 'neutral' },
    { name: 'خطِ روندِ صعودی (از دو کفِ اخیر)',
      value: tl.hasLine && isFinite(tl.lineValue) ? tl.lineValue.toFixed(2) + '$' : '—',
      status: tl.hasLine ? 'ok' : 'neutral' },
    { name: 'رابطهٔ قیمت با خطِ روند',
      value: isFinite(tl.distToLinePct) ? (tl.penetrated ? 'کمی زیرِ خط (تست)' : `${tl.distToLinePct.toFixed(2)}% بالای خط`) : '—',
      status: tl.state === 'ENTRY' ? 'ok' : tl.penetrated ? 'warn' : 'neutral' },
    { name: 'روندِ کلان (EMA' + htfCfg.emaFast + '/' + htfCfg.emaSlow + ')',
      value: tl.regimeUp ? 'صعودی ✓' : 'نه‌صعودی', status: tl.regimeUp ? 'ok' : 'neutral' },
    { name: 'شکستِ ناموفقِ خط (بازگشت به بالای خط)',
      value: tl.penetrated ? (tl.closedBack ? 'بله ✓' : 'هنوز نه') : 'خیر',
      status: tl.state === 'ENTRY' ? 'ok' : 'neutral' },
    { name: 'ATR', value: isFinite(tl.atr) ? tl.atr.toFixed(2) + '$' : '—', status: 'neutral' },
    { name: 'قیمتِ فعلی', value: a.price ? a.price.toFixed(2) : '—', status: 'neutral' },
  ]

  if (tl.state === 'ENTRY') {
    const entry = a.price
    const sl = entry - tl.slDist
    const tp = entry + tl.tpDist
    const { lots, riskDollars, effRiskPct } = computeLots(capital, riskPct, tl.slDist, 1.0, spec)
    const rd = Math.round(riskDollars * 100) / 100
    return {
      state: 'ENTRY', regime,
      headline: `ورود خرید (LONG) — تستِ ناموفقِ خطِ روندِ صعودی (طلا ${htfCfg.tfFa})`,
      reason: tl.reason,
      sourceLayer: {
        code: 'S215', name: `خطِ روندِ Al Brooks (Trend-Line Failed-Breakout) — ${htfCfg.tfFa}`, kind: 'price-action',
        filters: ['گیتِ روندِ صعودی EMA' + htfCfg.emaFast + '>EMA' + htfCfg.emaSlow,
          'شکستِ ناموفقِ خطِ روند (کمی زیرِ خط، بازگشت به بالای خط)', 'قیدِ ضدِ رنج (کندل‌های غیرِ هم‌پوش)'],
        manage: {
          style: 'structural-trail', beTriggerR: 1.0,
          trailDistPrice: tl.slDist, maxHoldBars: cfg.maxHoldBars,
          note: `مدیریتِ ساختاری (خطِ روند): SL اولیه زیرِ کفِ نفوذ (${tl.slDist.toFixed(2)}$). پس از ۱R سود، SL را ` +
            `به بریک‌ایون ببر؛ سپس زیرِ خطِ روندِ صعودی یا کفِ هر پولبکِ جدید بالا بیاور — تا سقفِ ${cfg.maxHoldBars} کندلِ ` +
            `${htfCfg.tfFa}. اگر قیمت قاطعانه زیرِ خطِ روند بسته شد و بالا نیامد (شکستِ واقعیِ روند)، فوراً خارج شو حتی قبل از TP.`,
        },
      },
      direction: 'LONG', entry, tp, sl,
      rr: `SL ${cfg.slPip}pip (${tl.slDist.toFixed(2)}$) / TP ${cfg.tpPip}pip (${tl.tpDist.toFixed(2)}$) — ` +
        `R:R ≈ ۱:${(cfg.tpPip / cfg.slPip).toFixed(1)} (بگذار بردها بدوند)`,
      probability: Math.round(cfg.indepWr),
      sizing: {
        lotMultiplier: 1.0, label: `خطِ روندِ Al Brooks (${htfCfg.tfFa})`,
        note: `ورودِ open کندلِ بعد؛ اسپردِ واقعیِ طلا لحاظ می‌شود. این لبه فقط روی طلا کار می‌کند ` +
          `(روی EURUSD بی‌اثر بود) و مستقل از سایرِ لایه‌های سایت است ⇒ سودِ خالصِ کل را بالا می‌برد.`,
        lots: lots ?? undefined, riskDollars: rd, capital, riskPct,
        capitalNote: `با سرمایهٔ ${capital.toLocaleString('en-US')}$ و ریسکِ ${riskPct}% ` +
          `(ریسکِ مؤثر ${effRiskPct.toFixed(2)}%)، حجمِ پیشنهادی ${lots?.toFixed(2) ?? '—'} ${spec.lotUnitFa}. ` +
          `اگر SL (فاصلهٔ ${tl.slDist.toFixed(2)}$) بخورد، حدودِ ${rd.toLocaleString('en-US')}$ ضرر می‌کنید.`,
      },
      tpPlan: { multiplier: cfg.tpPip,
        note: `TP دورِ ${cfg.tpPip}pip. پس از تأییدِ ادامهٔ روند، حرکتِ صعودی معمولاً بزرگ است؛ ` +
          `TP دور اجازه می‌دهد حرکت کامل استخراج شود. تا ${cfg.maxHoldBars} کندلِ ${htfCfg.tfFa} نگه دارید یا تا برخورد به TP/SL.` },
      slPlan: { multiplier: cfg.slPip,
        note: `SL ${cfg.slPip}pip (${tl.slDist.toFixed(2)}$) زیرِ نقطهٔ نفوذِ خطِ روند. اگر شکستِ خط واقعی بود ` +
          `(نه ناموفق)، این SL ضرر را محدود می‌کند.` },
      indicators: tlInd,
    }
  }

  if (tl.state === 'APPROACHING') {
    return {
      state: 'APPROACHING', regime,
      headline: `نزدیک‌شدن به سیگنالِ خرید (LONG) — قیمت به خطِ روندِ صعودی نزدیک شد (طلا ${htfCfg.tfFa})`,
      reason: tl.reason,
      sourceLayer: {
        code: 'S215', name: `خطِ روندِ Al Brooks (Trend-Line) — ${htfCfg.tfFa}`, kind: 'price-action',
      },
      confirmations: [
        { label: 'قیمت در یک sell-offِ تند کمی زیرِ خطِ روندِ صعودی برود', met: tl.penetrated,
          detail: tl.penetrated ? 'رخ داد ✓ (قیمت زیرِ خط نفوذ کرد)' : `اکنون ${tl.distToLinePct.toFixed(2)}% بالای خط است.` },
        { label: 'قیمت دوباره بالای خطِ روند ببندد (شکستِ ناموفق)', met: tl.closedBack && tl.penetrated,
          detail: tl.penetrated && !tl.closedBack ? 'هنوز بالای خط نبسته — منتظرِ بسته‌شدن بمانید.' : (tl.closedBack ? 'برقرار ✓' : 'هنوز نه') },
        { label: 'کندلِ صعودی (close ≥ open)', met: tl.bullBar, detail: tl.bullBar ? 'برقرار ✓' : 'کندلِ فعلی نزولی است.' },
      ],
      indicators: tlInd,
    }
  }

  // ماشه فعال نیست ⇒ تحلیلِ «حالتِ تحقیقِ فعالِ» همان تایم‌فریم، اما با نمایشِ وضعیتِ خطِ روند.
  const base = analyzeHtf(htfCfg, a, close)
  // خطِ روند را به ابتدای شاخص‌ها اضافه می‌کنیم تا کاربر بداند لایهٔ Trend-Line فعال و در حالِ پایش است.
  base.reason = `این کارت لایهٔ «خطِ روندِ Al Brooks» (S215) را روی افقِ ${htfCfg.tfFa} پایش می‌کند. ` + tl.reason +
    ` وقتی یک sell-offِ تند قیمت را کمی زیرِ خطِ روندِ صعودی ببرد و قیمت دوباره بالای خط ببندد، سیگنالِ ورودِ خرید صادر می‌شود.`
  base.sourceLayer = { code: 'S215', name: `خطِ روندِ Al Brooks (Trend-Line) — ${htfCfg.tfFa}`, kind: 'price-action' }
  base.indicators = tlInd
  base.headline = `طلا ${htfCfg.tfFa} — پایشِ خطِ روند (فعلاً بدونِ سیگنال)`
  return base
}

// ---------------------------------------------------------------------------
// توابعِ decide مستقلِ هر تایم‌فریم — هر کدام منطق/پیکربندیِ خودش را دارد (ماژولار).
// امضاء گسترش یافت تا OHLC را بگیرد (لایهٔ trend-line به high/low/open نیاز دارد).
//   • H1/H4 → لایهٔ اثبات‌شدهٔ S215 (Trend-Line Failed-Breakout LONG).
//   • D1   → هنوز لایهٔ اثبات‌شده ندارد (بک‌تست: n<۳۰ پس از کسرِ همپوشانی) ⇒ حالتِ تحقیق.
// ---------------------------------------------------------------------------
export function decideGoldH1(
  a: AnalysisResult, close: number[], capital = 10000, riskPct = 1.0,
  open?: number[], high?: number[], low?: number[],
): RouterDecision {
  if (open && high && low && high.length === close.length && low.length === close.length) {
    return trendLineEntry(TREND_LINE_CFG['XAUUSD-H1'], H1_CFG, a, open, high, low, close, capital, riskPct)
  }
  return analyzeHtf(H1_CFG, a, close)
}

export function decideGoldH4(
  a: AnalysisResult, close: number[], capital = 10000, riskPct = 1.0,
  open?: number[], high?: number[], low?: number[],
): RouterDecision {
  if (open && high && low && high.length === close.length && low.length === close.length) {
    // لایهٔ اصلی: خطِ روندِ Al Brooks (S215). اگر سیگنالِ فعال داد، همان را نشان بده.
    const tl = trendLineEntry(TREND_LINE_CFG['XAUUSD-H4'], H4_CFG, a, open, high, low, close, capital, riskPct)
    if (tl.state === 'ENTRY' || tl.state === 'APPROACHING') return tl
    // لایهٔ مکملِ مستقلِ S219 (کانال، position-in-channel): سهمِ مستقلِ +$2,911 روی H4
    // (WR ۵۸.۳٪، WF-4/4). فقط وقتی S215 غیرفعال است ⇒ بدونِ تداخل. fallback = تصمیمِ خطِ روند.
    // (H1 عمداً کانال ندارد: پنجرهٔ walk-forwardِ سهمِ مستقلش منفی شد ⇒ رد.)
    return channelDecision(CHANNEL_CFG['XAUUSD-H4'], a, open, high, low, close, capital, riskPct, () => tl)
  }
  return analyzeHtf(H4_CFG, a, close)
}

export function decideGoldD1(a: AnalysisResult, close: number[], _capital = 10000, _riskPct = 1.0): RouterDecision {
  return analyzeHtf(D1_CFG, a, close)
}

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
import * as ind from './indicators'

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
// توابعِ decide مستقلِ هر تایم‌فریم — هر کدام منطق/پیکربندیِ خودش را دارد (ماژولار).
// امضاء هم‌راستا با سایرِ روترهای طلا: (analysis, close, capital, riskPct).
// capital/riskPct فعلاً استفاده نمی‌شوند (حالتِ تحقیق، بدونِ حجم) اما برای هم‌سانیِ
// امضاء نگه داشته شده‌اند تا افزودنِ منطقِ ورود در آینده امضاء را نشکند.
// ---------------------------------------------------------------------------
export function decideGoldH1(a: AnalysisResult, close: number[], _capital = 10000, _riskPct = 1.0): RouterDecision {
  return analyzeHtf(H1_CFG, a, close)
}

export function decideGoldH4(a: AnalysisResult, close: number[], _capital = 10000, _riskPct = 1.0): RouterDecision {
  return analyzeHtf(H4_CFG, a, close)
}

export function decideGoldD1(a: AnalysisResult, close: number[], _capital = 10000, _riskPct = 1.0): RouterDecision {
  return analyzeHtf(D1_CFG, a, close)
}

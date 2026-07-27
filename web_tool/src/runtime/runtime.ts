// ============================================================================
// runtime/runtime.ts — گرهِ Runtime (بسترِ اجرای لایه‌ها)  [webplan P4 · گره ۳]
// ----------------------------------------------------------------------------
// این گره «مرزِ رسمیِ» اجرای لایه‌هاست. در P4 صرفاً runCard موجود را با تایپِ رسمیِ
// CardDecision@v1 می‌پیچد تا:
//   • مرزِ معماری مستند و نسخه‌دار شود (LayerSignal[] → CardDecision)،
//   • فازِ بعد (P4.5 Council) بتواند «سایه‌ای» بینِ اجرا و تصمیم بنشیند،
// بدونِ آنکه یک بایت از خروجیِ تصمیم تغییر کند (برابریِ بیت‌به‌بیت با snapshot طلایی).
//
// ⚠️ Strangler Fig: runCardTyped فقط یک پوششِ نازک است. منطقِ انتخابِ اولویتِ حالت
//    و ساختِ otherLayers هنوز داخلِ strategy_registry.runCard است و دست‌نخورده می‌ماند.
//    (کشیدنِ آن منطق به این گره در P5 انجام می‌شود، همچنان با تضمینِ parity.)
// ============================================================================

import { runCard, type LayerContext } from '../strategy_registry'
import type { CardDecision, RuntimeMeta } from './contracts'
import { RUNTIME_CONTRACT_VERSION } from './contracts'
import { CARD_LAYERS } from '../strategy_registry'

/**
 * اجرای یک کارت با تایپِ رسمیِ CardDecision@v1.
 * خروجی *دقیقاً* همان چیزی است که runCard می‌دهد (هیچ تبدیل/فیلترِ اضافه‌ای نیست).
 */
export function runCardTyped(ctx: LayerContext): CardDecision {
  return runCard(ctx) as CardDecision
}

/**
 * فرادادهٔ اجرای کارت (سایه‌ای/اختیاری) — برای گزارش و مستندات، نه تغییرِ تصمیم.
 * تعدادِ لایه‌های ثبت‌شدهٔ کارت را از رجیستری می‌خواند.
 */
export function runtimeMetaFor(cardId: string): RuntimeMeta {
  const layers = CARD_LAYERS[cardId] || []
  return {
    contractVersion: RUNTIME_CONTRACT_VERSION,
    cardId,
    layerCount: layers.length,
  }
}

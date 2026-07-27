// ============================================================================
// runtime/contracts.ts — قراردادهای نسخه‌دارِ گرهِ Runtime  [webplan P4 · گره ۳]
// ----------------------------------------------------------------------------
// گره ۳ (بسترِ اجرا) در webplan §۳. این گره لایه‌ها را اجرا می‌کند و خروجیِ هر لایه
// یک LayerSignal است؛ جمعِ آن‌ها برای یک کارت یک CardDecision می‌شود.
//
// درسِ ROS2 (ایدهٔ #۸): مرزِ این گره باید یک نوعِ نسخه‌دار باشد. اما P4 «Strangler Fig»
// است و باید خروجیِ *بیت‌به‌بیت یکسان* بدهد. پس به‌جای تعریفِ شکلِ جدید (که رفتار را
// می‌شکند)، قرارداد را به‌صورتِ **نام‌گذاریِ رسمیِ نسخه‌دار روی همان ساختارِ موجود**
// (RouterDecision) تعریف می‌کنیم:
//   • LayerSignal@v1  ≡  RouterDecision (خروجیِ یک لایه)
//   • CardDecision@v1 ≡  RouterDecision (تصمیمِ اصلیِ کارت، با otherLayers/…)
// این کار مرزِ معماری را رسمی و مستند می‌کند بی‌آنکه یک بایت از خروجی تغییر کند.
// نسخهٔ v2 (اگر روزی لازم شد) باید adapter داشته باشد، نه ویرایشِ درجای v1.
// ============================================================================

import type { RouterDecision } from '../router'

/** نسخهٔ قراردادِ Runtime — تغییرِ ناسازگار ⇒ v2 + adapter. */
export const RUNTIME_CONTRACT_VERSION = 1 as const

/**
 * LayerSignal@v1 — خروجیِ استانداردِ *یک لایه* برای یک کارت.
 * از نظرِ ساختاری همان RouterDecision است (تثبیتِ نام، نه تغییرِ شکل).
 */
export type LayerSignal = RouterDecision

/**
 * CardDecision@v1 — تصمیمِ اصلیِ *یک کارت* (پس از رأی/اولویتِ حالت).
 * همان RouterDecision با میدان‌های تجمیعی (otherLayers/cardTimeGates).
 */
export type CardDecision = RouterDecision

/**
 * برچسبِ حالتِ کارت — چهار-حالتِ رسمیِ سایت.
 * (MANAGING حالتِ ظاهریِ فرانت‌اند است پس از ثبتِ معامله؛ در بستر تولید نمی‌شود.)
 */
export type CardState = 'NEUTRAL' | 'APPROACHING' | 'ENTRY'

/** فراداده‌ای که هر تصمیم می‌تواند نسخهٔ قرارداد خود را اعلام کند (اختیاری، سایه‌ای). */
export interface RuntimeMeta {
  readonly contractVersion: typeof RUNTIME_CONTRACT_VERSION
  readonly cardId: string
  readonly layerCount: number
}

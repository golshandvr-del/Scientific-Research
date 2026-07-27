// ============================================================================
// price/heartbeat.ts — Heartbeat / سلامتِ گرهِ قیمت  [webplan P2 · ایدهٔ #۷]
// ----------------------------------------------------------------------------
// طبقِ webplan (گرهِ UI · ایدهٔ #۷): «اگر قیمتِ زنده > ۹۰ ثانیه کهنه شد، نوارِ قرمز
// "دادهٔ زنده قطع — سیگنال منجمد"». این فایل منطقِ *محاسبهٔ* آن وضعیت را می‌دهد
// (خالص، محیط‌آگنوستیک). نمایشِ نوار در فرانت‌اند در فازِ P5 وصل می‌شود.
//
// ⚠️ افزودنی: هیچ تصمیمی را تغییر نمی‌دهد؛ فقط یک گزارشِ سلامت تولید می‌کند.
// ============================================================================

import { STALE_THRESHOLD_SEC, type PriceHealth } from './contracts'

/**
 * محاسبهٔ وضعیتِ سلامتِ قیمت از سنِ قیمتِ زنده.
 * @param liveAgeSec سنِ قیمتِ زنده بر حسبِ ثانیه.
 * @param source منبعی که واقعاً استفاده شد.
 * @param thresholdSec آستانهٔ کهنگی (پیش‌فرض STALE_THRESHOLD_SEC = ۹۰).
 */
export function computeHealth(
  liveAgeSec: number,
  source: string,
  thresholdSec: number = STALE_THRESHOLD_SEC,
): PriceHealth {
  const age = isFinite(liveAgeSec) ? Math.max(0, Math.round(liveAgeSec)) : Infinity
  const stale = age > thresholdSec
  return {
    ok: !stale && isFinite(age),
    liveAgeSec: isFinite(age) ? age : -1,
    stale,
    source: source || 'unknown',
    note: !isFinite(age)
      ? 'سنِ قیمت نامعلوم است'
      : stale
        ? `دادهٔ زنده کهنه است (${age}s > ${thresholdSec}s) — سیگنال منجمد`
        : 'دادهٔ زنده تازه است',
  }
}

export { STALE_THRESHOLD_SEC } from './contracts'
export type { PriceHealth } from './contracts'

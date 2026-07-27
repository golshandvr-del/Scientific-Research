// ============================================================================
// indicators/contracts.ts — قراردادِ پیامِ نسخه‌دارِ گرهِ اندیکاتور  [webplan P3 · ایدهٔ #۸]
// ----------------------------------------------------------------------------
// این فایل «مرزِ ثابتِ» گرهِ اندیکاتور است (گره ۲ در webplan §۳). طبقِ درسِ ROS2،
// خروجیِ گرهِ اندیکاتور یک نوعِ دادهٔ امضاشده و نسخه‌دار (IndicatorSnapshot@v1) است
// تا هیچ گره/نشستِ بعدی نتواند شکلِ داده را بی‌سر و صدا عوض کند. تغییرِ شکل ⇒
// ساختِ نسخهٔ v2 + adapter، نه ویرایشِ درجای v1.
//
// ⚠️ P3 «Strangler Fig» است: این قرارداد فعلاً *افزودنی* است و رفتارِ موجود را
//    تغییر نمی‌دهد. لایه‌ها هنوز اندیکاتورهایشان را مستقیم صدا می‌زنند؛ این گره
//    زیرساختِ کشِ تنبلِ مشترک است که در فازهای بعد مصرف‌کننده پیدا می‌کند.
// ============================================================================

import type { Candle } from '../indicators'

/** نسخهٔ قرارداد — هر تغییرِ ناسازگار باید این را بالا ببرد و adapter بنویسد. */
export const INDICATOR_SNAPSHOT_VERSION = 1 as const

/** خروجیِ یک اندیکاتور: یک سری (number[]) یا مقدارِ اسکالر یا ساختارِ چند-سری. */
export type IndicatorValue = number | number[] | Record<string, number[]> | Record<string, number>

/**
 * تعریفِ یک اندیکاتور در رجیستری. مشابهِ رجیستریِ استراتژی:
 *   نام + پارامترهای پیش‌فرض + تابعِ compute (بدونِ look-ahead).
 * تابعِ compute کلِ سری را برمی‌گرداند تا کش بتواند «آخرین مقدار» و «سریِ کامل»
 * را هر دو سرو کند. کلیدِ پارامتر برای کش از paramKeys ساخته می‌شود (ترتیبِ ثابت).
 */
export interface IndicatorDef<P extends Record<string, number> = Record<string, number>> {
  /** نامِ یکتا (مثل 'ema', 'rsi', 'adx', 'alligator'). */
  name: string
  /** پارامترهای پیش‌فرض (اگر لایه پارامتر نداد). */
  defaults: P
  /** ترتیبِ ثابتِ کلیدهای پارامتر — برای ساختِ کلیدِ کشِ قطعی. */
  paramKeys: (keyof P)[]
  /** توضیحِ کوتاهِ فارسی (برای کاوشگرِ اندیکاتور P8 و مستندات). */
  desc?: string
  /** محاسبهٔ اندیکاتور روی کندل‌ها. باید بدونِ look-ahead باشد. */
  compute: (candles: Candle[], params: P) => IndicatorValue
}

/**
 * IndicatorSnapshot@v1 — خروجیِ استانداردِ گرهِ اندیکاتور برای یک (asset, tf, lastBarTime).
 *
 * دو راهِ دسترسی:
 *   1. get(name, params?) — دسترسیِ عمومی به هر اندیکاتورِ رجیستری‌شده (کش‌شده).
 *   2. میدان‌های آمادهٔ پرکاربرد (price/atr/ema50/…) — دسترسیِ سریع برای کدِ داغ.
 *
 * قانونِ کش (webplan §۳): کلیدِ کش = name + پارامترها + آخرین‌زمانِ کندل. اگر دو
 * لایه EMA200 بخواهند، یک‌بار حساب می‌شود.
 */
export interface IndicatorSnapshot {
  /** نسخهٔ قرارداد (همیشه === INDICATOR_SNAPSHOT_VERSION در v1). */
  readonly v: typeof INDICATOR_SNAPSHOT_VERSION
  readonly asset: string
  readonly tf: string
  /** زمانِ آخرین کندلِ ورودی (کلیدِ اصلیِ کش). */
  readonly lastBarTime: number
  /** تعدادِ کندل‌های ورودی. */
  readonly barCount: number

  /**
   * دسترسیِ عمومی به هر اندیکاتورِ رجیستری‌شده — سریِ کامل (number[]) یا ساختار.
   * نتیجه memoize می‌شود (کلید = name+params+lastBarTime).
   */
  series(name: string, params?: Record<string, number>): IndicatorValue | null

  /** آخرین مقدارِ یک اندیکاتورِ تک-سری (میان‌بُر رایج). */
  last(name: string, params?: Record<string, number>): number | null

  // --- میدان‌های آمادهٔ پرکاربرد (آخرین مقدار) برای دسترسیِ سریع ---
  readonly price: number
  readonly atr: number
  readonly ema20: number
  readonly ema50: number
  readonly ema100: number
  readonly ema200: number
  readonly rsi14: number
  readonly adx: number
  readonly macdHist: number
}

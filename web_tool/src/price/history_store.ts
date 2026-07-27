// ============================================================================
// price/history_store.ts — قراردادِ ذخیره‌سازیِ تاریخچهٔ کندل  [webplan P2 · گرهِ قیمت]
// ----------------------------------------------------------------------------
// این فایل «مرزِ ثابتِ» زیرسیستمِ ذخیره‌سازیِ تاریخچه است (رابطِ HistoryStore).
// طبقِ webplan §۳ (گرهِ قیمت) و §۵ (سازگاریِ دوگانه)، گرهِ قیمت باید تاریخچهٔ
// کندل را ذخیره کند تا:
//   ۱) روی گوشیِ Termux تاریخچهٔ چند-روزه فراتر از سقفِ کوتاهِ Yahoo داشته باشیم.
//   ۲) پلِ «شبیه‌ساز↔سایت» (ماشینِ زمان P6، کاوشگر P8) داده بخواند.
//
// چرا «رابط + دو پیاده‌سازی»؟ (webplan §۵)
//   - فایل‌سیستم فقط روی Termux/Node هست؛ Cloudflare ندارد.
//   - پس منطق پشتِ یک رابطِ واحد پنهان می‌شود:
//       · DiskHistoryStore   → Termux/Node (فایل‌سیستم واقعی)
//       · MemoryHistoryStore → Cloudflare/تست (بدونِ فایل‌سیستم)
//   کدِ بالادست (گرهِ قیمت) فقط رابط را می‌بیند و محیط‌آگنوستیک می‌ماند.
//
// ⚠️ P2 «Strangler Fig / افزودنی» است: این ماژول به‌تنهایی هیچ رفتارِ endpointِ
//    فعلی را تغییر نمی‌دهد. ابتدا فقط زیرساخت + تستِ واحد اضافه می‌شود؛ اتصال به
//    مسیرِ دادهٔ زنده در گامِ بعدیِ همین فاز (با حفظِ برابری) انجام می‌گیرد.
// ============================================================================

import type { Candle } from '../indicators'

/** نسخهٔ قراردادِ ذخیره‌سازی — هر تغییرِ ناسازگارِ فرمت باید این را بالا ببرد. */
export const HISTORY_STORE_VERSION = 1 as const

/**
 * کلیدِ افرازِ (partition) ذخیره‌سازی: هر (asset, tf) یک بافرِ مستقل.
 * قرارداد نام: `${asset}-${tf}` با حروفِ بزرگ‌شده، مثلِ "XAUUSD-M5".
 */
export function partitionKey(asset: string, tf: string): string {
  return `${asset.toUpperCase()}-${tf.toUpperCase()}`
}

/** پیکربندیِ سقفِ حجم/تعدادِ کندلِ هر افراز. */
export interface HistoryLimits {
  /**
   * سقفِ تعدادِ کندلِ نگهداری‌شده در هر افراز (ring-buffer).
   * وقتی از این عبور کند ⇒ حذفِ قدیمی‌ترین‌ها (FIFO).
   */
  maxBars: number
  /**
   * کفِ حداقلِ تعدادِ کندل که هرگز پایین‌تر از آن پاک نمی‌شود
   * (webplan: «سقفِ حجم … با کفِ حداقل»). محافظ در برابرِ تنظیمِ خیلی کوچک.
   */
  minBars: number
}

/** پیش‌فرضِ سقف/کف — معادلِ تقریبیِ «۲۰۰MB پیش‌فرض، کفِ ۲۰MB» webplan روی مقیاسِ کندل. */
export const DEFAULT_LIMITS: HistoryLimits = {
  // ~۵۰k کندلِ M5 ≈ چند ماه تاریخچه؛ در فرمتِ فشرده حجمِ کمی می‌گیرد.
  maxBars: 50_000,
  minBars: 500,
}

/** نتیجهٔ یک عملِ ادغام (upsert) در بافر. */
export interface AppendResult {
  /** تعدادِ کندلِ نهاییِ بافر پس از ادغام و برشِ سقف. */
  total: number
  /** چند کندلِ واقعاً *جدید* افزوده شد (زمان‌های تازه). */
  added: number
  /** چند کندلِ موجود *به‌روزرسانی* شد (همان زمان، مقدارِ تغییر یافته). */
  updated: number
  /** چند کندلِ قدیمی به‌خاطرِ سقف حذف شد (FIFO). */
  evicted: number
}

/** یک حفرهٔ زمانیِ کشف‌شده در تاریخچه (برای gap-fill). */
export interface Gap {
  /** زمانِ کندلِ بسته‌شدهٔ پیش از حفره. */
  fromTime: number
  /** زمانِ کندلِ بعد از حفره. */
  toTime: number
  /** تعدادِ کندلِ گم‌شده در این حفره (بر اساسِ tfSec). */
  missingBars: number
}

/**
 * رابطِ HistoryStore — مرزِ ثابتِ ذخیره‌سازی (webplan §۳/§۵).
 * پیاده‌سازی‌ها: DiskHistoryStore (Termux) و MemoryHistoryStore (Cloudflare/تست).
 *
 * قراردادهای رفتاری (که هر دو پیاده‌سازی باید رعایت کنند):
 *   - append: ادغامِ upsert بر اساسِ `time` (کلیدِ یکتا)، مرتب‌سازیِ صعودی،
 *     سپس برشِ FIFO تا maxBars (با احترام به minBars).
 *   - load: کندل‌ها را «به ترتیبِ زمانیِ صعودی» برمی‌گرداند (کهنه→تازه).
 *   - همهٔ متدها async هستند تا با backendِ دیسکی/شبکه‌ای سازگار بمانند.
 */
export interface HistoryStore {
  /** نسخهٔ قرارداد. */
  readonly version: typeof HISTORY_STORE_VERSION

  /**
   * ادغامِ مجموعه‌ای کندلِ تازه در افرازِ (asset,tf).
   * upsert بر اساسِ time؛ سپس برشِ سقف. خروجی: آمارِ عملیات.
   */
  append(asset: string, tf: string, candles: Candle[], limits?: HistoryLimits): Promise<AppendResult>

  /**
   * بازیابیِ تاریخچهٔ یک افراز (صعودی). اگر limit داده شود، فقط `limit`
   * کندلِ *آخر* (تازه‌ترین‌ها) برگردانده می‌شود.
   */
  load(asset: string, tf: string, limit?: number): Promise<Candle[]>

  /** تعدادِ کندلِ ذخیره‌شدهٔ یک افراز (بدونِ بارگذاریِ کامل، اگر ممکن). */
  count(asset: string, tf: string): Promise<number>

  /** زمانِ تازه‌ترین کندلِ ذخیره‌شده (یا null اگر خالی). */
  lastTime(asset: string, tf: string): Promise<number | null>

  /** پاک‌کردنِ کاملِ یک افراز (برای تست/ری‌ست). */
  clear(asset: string, tf: string): Promise<void>
}

// ---------------------------------------------------------------------------
// توابعِ کمکیِ خالص (Pure) — منطقِ مشترکِ هر دو پیاده‌سازی. جدا نگه داشته شده
// تا یک‌بار نوشته و در Disk و Memory و تست یکسان استفاده شوند (Isomorphic).
// ---------------------------------------------------------------------------

/**
 * ادغامِ upsert دو سریِ کندل بر اساسِ `time`.
 * - کندلِ تازه با زمانِ جدید ⇒ افزوده می‌شود.
 * - کندلِ تازه با زمانِ موجود ⇒ کندلِ قدیمی را جایگزین می‌کند (آخرین حقیقت).
 * خروجی: سریِ مرتبِ صعودی + آمار.
 */
export function mergeCandles(existing: Candle[], incoming: Candle[]): {
  merged: Candle[]; added: number; updated: number
} {
  const map = new Map<number, Candle>()
  for (const k of existing) map.set(k.time, k)
  let added = 0, updated = 0
  for (const k of incoming) {
    if (!isFinite(k.time)) continue
    if (map.has(k.time)) {
      const prev = map.get(k.time)!
      // فقط اگر واقعاً تغییری هست، به‌روزرسانی شمرده می‌شود.
      if (prev.open !== k.open || prev.high !== k.high || prev.low !== k.low ||
          prev.close !== k.close || (prev.volume || 0) !== (k.volume || 0)) {
        updated++
      }
      map.set(k.time, k)
    } else {
      map.set(k.time, k)
      added++
    }
  }
  const merged = Array.from(map.values()).sort((a, b) => a.time - b.time)
  return { merged, added, updated }
}

/**
 * برشِ FIFO تا سقفِ maxBars با احترام به کفِ minBars.
 * قدیمی‌ترین کندل‌ها (ابتدای آرایهٔ صعودی) حذف می‌شوند.
 * خروجی: سریِ برش‌خورده + تعدادِ حذف‌شده.
 */
export function enforceLimit(candles: Candle[], limits: HistoryLimits): {
  trimmed: Candle[]; evicted: number
} {
  const cap = Math.max(limits.minBars, limits.maxBars)
  if (candles.length <= cap) return { trimmed: candles, evicted: 0 }
  const evicted = candles.length - cap
  return { trimmed: candles.slice(evicted), evicted }
}

/**
 * کشفِ حفره‌های زمانی در یک سریِ صعودی (برای gap-fill هنگامِ روشن‌شدنِ سرور).
 * @param tfSec طولِ کندل بر حسبِ ثانیه (مثلاً M5=300).
 * @param toleranceBars چند کندلِ فاصله «طبیعی» است (تعطیلیِ آخرِ هفتهٔ بازار و…)
 *        پیش‌فرض ۱: هر فاصلهٔ بیش از ۱ کندل، حفره حساب می‌شود.
 */
export function detectGaps(candles: Candle[], tfSec: number, toleranceBars = 1): Gap[] {
  const gaps: Gap[] = []
  if (candles.length < 2 || tfSec <= 0) return gaps
  for (let i = 1; i < candles.length; i++) {
    const dt = candles[i].time - candles[i - 1].time
    const bars = Math.round(dt / tfSec)
    if (bars > toleranceBars) {
      gaps.push({
        fromTime: candles[i - 1].time,
        toTime: candles[i].time,
        missingBars: bars - 1,
      })
    }
  }
  return gaps
}

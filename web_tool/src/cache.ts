// ============================================================================
// cache.ts — کشِ حافظه‌ایِ مستقل از محیط (Node/Termux + Cloudflare Workers)
// ----------------------------------------------------------------------------
// چرا این فایل ساخته شد (پاسخ به هدفِ «سرعتِ گوشی»):
//   کدِ داده‌گیری از `cf: { cacheTtl }` استفاده می‌کرد که یک قابلیتِ انحصاریِ
//   Cloudflare است و روی Node/Termux (گوشی) *کاملاً بی‌اثر* است. نتیجه: روی گوشی
//   هر رفرش ⇒ ۱۲ دارایی × چند درخواستِ مستقیم به Yahoo ⇒ rate-limit/کندی ⇒ صفحهٔ
//   خالی تا ۲ دقیقه. این ماژول یک کشِ حافظه‌ایِ ساده اما «باهوش» می‌سازد که در هر
//   دو محیط کار می‌کند و بارِ منابعِ بیرونی را ۹۰٪+ کم می‌کند.
//
// سه قابلیتِ کلیدی:
//   1) TTL — هر ورودی تا `freshMs` «تازه» است و بدونِ fetch برگردانده می‌شود.
//   2) SWR (stale-while-revalidate) — پس از انقضایِ تازگی، مقدارِ «کهنه» فوراً
//      برگردانده می‌شود و در *پس‌زمینه* تازه‌سازی می‌شود ⇒ کاربر هیچ‌وقت منتظر نمی‌ماند.
//   3) De-dup (single-flight) — اگر چند دارایی هم‌زمان یک کلید (مثلاً کندلِ H1 طلا)
//      را بخواهند، فقط *یک* fetchِ واقعی انجام می‌شود و بقیه به همان Promise می‌چسبند.
//
// ⚠️ این ماژول هیچ ربطی به منطقِ تصمیم‌گیری/استراتژی ندارد؛ فقط یک لایهٔ داده است.
// ============================================================================

interface CacheEntry<T> {
  value: T
  storedAt: number      // زمانِ ذخیره (ms)
  freshMs: number       // تا این مدت «تازه» است
  staleMs: number       // تا این مدت (پس از تازگی) «کهنهٔ قابلِ استفاده» است
}

// کشِ سراسری (در طولِ عمرِ پراسس). روی Node پایدار می‌ماند؛ روی CF هر ایزوله جدا.
const _store = new Map<string, CacheEntry<any>>()

// درخواست‌های در حالِ پرواز (برای de-dup) — کلید ⇒ Promise.
const _inflight = new Map<string, Promise<any>>()

// آمار ساده برای دیباگ/رصد (اختیاری).
export const cacheStats = { hits: 0, misses: 0, stale: 0, dedup: 0, revalidations: 0 }

export interface CacheOpts {
  freshMs?: number      // پیش‌فرض ۳۰ ثانیه
  staleMs?: number      // پیش‌فرض ۵ دقیقه (سِرو کهنه در صورتِ خطای منبع)
}

// ----------------------------------------------------------------------------
// cachedFetch — هستهٔ ماژول.
//   key      : کلیدِ یکتا (معمولاً URL یا symbol:interval:range)
//   producer : تابعی که مقدارِ تازه را می‌سازد (fetchِ واقعی)
//   opts     : TTLها
// رفتار:
//   • تازه؟           ⇒ فوراً برگردان (hit).
//   • کهنه ولی معتبر؟  ⇒ فوراً کهنه را برگردان + تازه‌سازیِ پس‌زمینه (SWR).
//   • نبود/منقضی؟      ⇒ منتظرِ producer بمان (با de-dup).
//   • producer خطا داد و کهنه داریم؟ ⇒ کهنه را برگردان (تابِ خطا).
// ----------------------------------------------------------------------------
export async function cachedFetch<T>(key: string, producer: () => Promise<T>, opts: CacheOpts = {}): Promise<T> {
  const freshMs = opts.freshMs ?? 30_000
  const staleMs = opts.staleMs ?? 300_000
  const now = Date.now()
  const hit = _store.get(key)

  if (hit) {
    const age = now - hit.storedAt
    if (age < hit.freshMs) {
      cacheStats.hits++
      return hit.value as T                 // تازه ⇒ فوری
    }
    if (age < hit.freshMs + hit.staleMs) {
      cacheStats.stale++
      // کهنهٔ معتبر ⇒ فوراً برگردان و در پس‌زمینه تازه کن (بدونِ منتظر ماندنِ کاربر).
      void _revalidate(key, producer, freshMs, staleMs)
      return hit.value as T
    }
    // خیلی کهنه ⇒ مثلِ miss رفتار کن (پایین).
  }

  cacheStats.misses++
  return _load(key, producer, freshMs, staleMs)
}

// بارگذاریِ همزمان با de-dup (single-flight).
function _load<T>(key: string, producer: () => Promise<T>, freshMs: number, staleMs: number): Promise<T> {
  const existing = _inflight.get(key)
  if (existing) { cacheStats.dedup++; return existing as Promise<T> }

  const p = (async () => {
    try {
      const value = await producer()
      _store.set(key, { value, storedAt: Date.now(), freshMs, staleMs })
      return value
    } catch (err) {
      // اگر مقدارِ کهنه (هرچند خیلی کهنه) داریم، به‌جای خطا آن را برگردان.
      const stale = _store.get(key)
      if (stale) return stale.value as T
      throw err
    } finally {
      _inflight.delete(key)
    }
  })()

  _inflight.set(key, p)
  return p
}

// تازه‌سازیِ پس‌زمینه برای SWR — خطا را می‌بلعد (کاربر مقدارِ کهنه را قبلاً گرفته).
async function _revalidate<T>(key: string, producer: () => Promise<T>, freshMs: number, staleMs: number): Promise<void> {
  if (_inflight.has(key)) return   // یک تازه‌سازی در جریان است.
  cacheStats.revalidations++
  try { await _load(key, producer, freshMs, staleMs) } catch { /* بی‌صدا */ }
}

// پیش‌گرم‌سازی: مقدار را وارد کش کن (بدونِ اینکه کاربری منتظر بماند).
export async function warm<T>(key: string, producer: () => Promise<T>, opts: CacheOpts = {}): Promise<void> {
  try { await cachedFetch(key, producer, opts) } catch { /* بی‌صدا */ }
}

// پاک‌سازیِ دستی (برای تست).
export function cacheClear(): void { _store.clear(); _inflight.clear() }

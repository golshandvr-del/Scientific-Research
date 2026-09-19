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

// ----------------------------------------------------------------------------
// 🩹 رفعِ نشتیِ حافظه (باگِ «سایت بعد از مدتی بالا نمی‌آید»)
// ----------------------------------------------------------------------------
// تشخیص: این Map هیچ سقفی نداشت و هیچ ورودیِ منقضی‌ای از آن حذف نمی‌شد. هر کلید
// (`symbol:interval:range`) یک آرایهٔ کندل (صدها تا هزاران شیء) نگه می‌داشت. با
// چرخشِ کارت‌ها/تایم‌فریم‌ها کلیدهای تازه مدام اضافه می‌شدند و **هرگز** چیزی آزاد
// نمی‌شد ⇒ RSSِ workerd تا ۵۸۹MB بالا رفت و پراسس عملاً فریز شد. این دقیقاً همان
// «اول سریع، بعد کند، بعد اصلاً بالا نمی‌آید» است: تا وقتی حافظه جا دارد سریع است.
//
// چرا LRU و نه فقط TTL: در حالتِ خطای منبع، این ماژول عمداً مقدارِ «خیلی کهنه» را
// هم نگه می‌دارد (تابِ خطا — خطِ `catch` در `_load`). پس نمی‌توان صرفاً بر اساسِ
// انقضا حذف کرد، وگرنه همان تابِ خطا از بین می‌رود. راهِ درست: سقفِ تعدادِ ورودی
// + بیرون‌انداختنِ «کم‌استفاده‌ترین» (LRU). ظرفیت با سخاوت انتخاب شده تا تمامِ
// کلیدهای واقعیِ سایت (۹ کارت × چند تایم‌فریم × چند منبع) جا شوند و LRU فقط
// کلیدهای مرده/یتیم را بیرون بیندازد.
const MAX_ENTRIES = 300

// سقفِ درخواست‌های هم‌زمانِ در حالِ پرواز. اگر منبعِ بیرونی هنگ کند، `_inflight`
// هم می‌توانست بی‌مرز رشد کند (هر Promiseِ معلق = حافظه + یک اتصال).
const MAX_INFLIGHT = 64

// کشِ سراسری (در طولِ عمرِ پراسس). روی Node پایدار می‌ماند؛ روی CF هر ایزوله جدا.
// نکته: `Map` در JS ترتیبِ درج را حفظ می‌کند ⇒ با `delete`+`set` روی هر دسترسی،
// همان Map خودش یک صفِ LRU می‌شود بدونِ هیچ ساختارِ دادهٔ اضافه.
const _store = new Map<string, CacheEntry<any>>()

// درخواست‌های در حالِ پرواز (برای de-dup) — کلید ⇒ Promise.
const _inflight = new Map<string, Promise<any>>()

// آمار ساده برای دیباگ/رصد (اختیاری).
export const cacheStats = { hits: 0, misses: 0, stale: 0, dedup: 0, revalidations: 0, evictions: 0 }

// «تازه‌ترین استفاده» را علامت می‌زند: حذف و درجِ دوباره ⇒ می‌رود آخرِ صف.
function _touch(key: string, entry: CacheEntry<any>): void {
  _store.delete(key)
  _store.set(key, entry)
}

// سقف را اعمال می‌کند: از ابتدای صف (قدیمی‌ترین دسترسی) حذف می‌کند تا جا باز شود.
function _evictIfNeeded(): void {
  while (_store.size > MAX_ENTRIES) {
    const oldest = _store.keys().next()
    if (oldest.done) break
    _store.delete(oldest.value)
    cacheStats.evictions++
  }
}

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
      _touch(key, hit)                      // LRU: این کلید تازه استفاده شد
      return hit.value as T                 // تازه ⇒ فوری
    }
    if (age < hit.freshMs + hit.staleMs) {
      cacheStats.stale++
      _touch(key, hit)                      // LRU: کهنه‌ولی‌زنده هم «استفاده» است
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

  // 🩹 سدِ ازدحام: اگر بیش از حد درخواستِ معلق داریم، منبعِ بیرونی هنگ کرده است.
  // در آن حالت به‌جای افزودنِ درخواستِ تازه (که فقط نشتی را بدتر می‌کند)، اگر
  // مقدارِ کهنه‌ای داریم همان را بده. این «مارپیچِ مرگ» را می‌شکند: سایت با دادهٔ
  // کهنه بالا می‌آید به‌جای اینکه اصلاً بالا نیاید.
  if (_inflight.size >= MAX_INFLIGHT) {
    const stale = _store.get(key)
    if (stale) return Promise.resolve(stale.value as T)
  }

  const p = (async () => {
    try {
      const value = await producer()
      _store.set(key, { value, storedAt: Date.now(), freshMs, staleMs })
      _evictIfNeeded()
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

// ----------------------------------------------------------------------------
// 🔭 رصدِ سلامتِ کش — برای تشخیصِ زودهنگامِ نشتی در آینده.
// چرا لازم است: باگِ نشتی ماه‌ها **بی‌صدا** بود؛ تنها نشانه‌اش «سایت کند شده» بود
// که هزار علتِ ممکن دارد. با این عدد‌ها، دفعهٔ بعد در چند ثانیه معلوم می‌شود که
// مشکل از کش است یا نه: اگر `entries` به سقف چسبیده و `evictions` مدام بالا
// می‌رود، یعنی الگوی کلیدها پراکنده شده و باید بررسی شود.
// ----------------------------------------------------------------------------
export function cacheHealth() {
  return {
    entries: _store.size,
    maxEntries: MAX_ENTRIES,
    inflight: _inflight.size,
    maxInflight: MAX_INFLIGHT,
    saturated: _store.size >= MAX_ENTRIES,
    congested: _inflight.size >= MAX_INFLIGHT,
    stats: { ...cacheStats },
  }
}

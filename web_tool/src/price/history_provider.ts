// ============================================================================
// price/history_provider.ts — انتخابِ خودکارِ backendِ HistoryStore  [webplan P2/§۵]
// ----------------------------------------------------------------------------
// «سازگاریِ دوگانه» (webplan §۵): فایل‌سیستم فقط روی Termux/Node هست.
//   - روی Node/Termux  ⇒ DiskHistoryStore (تاریخچهٔ دائم روی گوشی).
//   - روی Cloudflare/مرورگر ⇒ MemoryHistoryStore (بدونِ fs).
//
// تشخیصِ محیط «امن» است: فقط به وجودِ process.versions.node نگاه می‌کنیم و
// DiskHistoryStore را *پویا* import می‌کنیم تا باندلِ Cloudflare هرگز node:fs را
// نبیند. اگر بارگذاریِ دیسک به هر دلیل شکست خورد، امن به Memory برمی‌گردیم
// (fail-safe) — ذخیره‌سازی نباید هرگز مسیرِ اصلیِ قیمت را بشکند.
//
// singletonِ فرآیند: یک store مشترک برای همهٔ کارت‌ها (افراز per asset-TF داخلِ store).
// ============================================================================

import type { HistoryStore } from './history_store'
import { MemoryHistoryStore } from './memory_history_store'

let _store: HistoryStore | null = null
let _initPromise: Promise<HistoryStore> | null = null

/** آیا روی Node/Termux هستیم (فایل‌سیستم در دسترس)؟ */
function isNodeEnv(): boolean {
  return typeof process !== 'undefined'
    && !!(process as any).versions
    && !!(process as any).versions.node
}

/**
 * baseDir ذخیره‌سازیِ دیسک. قابلِ تنظیم با env (HISTORY_DIR) تا کاربر روی گوشی
 * محلِ ذخیره (و در نتیجه سقفِ عملیِ حجم) را کنترل کند. پیش‌فرض: ./data/history
 * نسبت به cwdِ سرور.
 */
function diskBaseDir(): string {
  const env = (typeof process !== 'undefined' && (process as any).env) || {}
  return env.HISTORY_DIR || './data/history'
}

/**
 * دریافتِ singletonِ HistoryStore مناسبِ محیط.
 * روی Node تلاش می‌کند Disk بسازد؛ در صورتِ خطا به Memory برمی‌گردد.
 */
export async function getHistoryStore(): Promise<HistoryStore> {
  if (_store) return _store
  if (_initPromise) return _initPromise
  _initPromise = (async () => {
    if (isNodeEnv()) {
      try {
        const mod = await import('./disk_history_store')
        _store = new mod.DiskHistoryStore(diskBaseDir())
        return _store
      } catch {
        // fail-safe: اگر Disk در دسترس نبود، Memory.
      }
    }
    _store = new MemoryHistoryStore()
    return _store
  })()
  return _initPromise
}

/** برای تست: تزریقِ یک store دلخواه و ری‌ستِ singleton. */
export function _setHistoryStoreForTest(s: HistoryStore | null): void {
  _store = s
  _initPromise = null
}

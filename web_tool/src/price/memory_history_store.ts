// ============================================================================
// price/memory_history_store.ts — پیاده‌سازیِ حافظه‌ایِ HistoryStore  [webplan P2]
// ----------------------------------------------------------------------------
// backendِ «بدونِ فایل‌سیستم» (webplan §۵). روی Cloudflare Workers (که fs ندارد)
// و در تست‌ها استفاده می‌شود. داده در یک Map زندهٔ همان فرآیند نگه‌داری می‌شود؛
// با ری‌استارتِ Worker پاک می‌شود (ذاتِ محیطِ بی‌حالتِ لبه) — این پذیرفته است،
// چون تاریخچهٔ دائم روی Termux/DiskHistoryStore ذخیره می‌شود.
//
// منطقِ ادغام/برش/حفره «خالص» است و از history_store.ts می‌آید ⇒ رفتارِ Disk و
// Memory بیت‌به‌بیت یکسان می‌ماند (اصلِ Isomorphic — ایدهٔ #۹ webplan).
// ============================================================================

import type { Candle } from '../indicators'
import {
  HISTORY_STORE_VERSION, DEFAULT_LIMITS, partitionKey,
  mergeCandles, enforceLimit,
  type HistoryStore, type HistoryLimits, type AppendResult,
} from './history_store'

export class MemoryHistoryStore implements HistoryStore {
  readonly version = HISTORY_STORE_VERSION
  private parts = new Map<string, Candle[]>()

  async append(asset: string, tf: string, candles: Candle[], limits: HistoryLimits = DEFAULT_LIMITS): Promise<AppendResult> {
    const key = partitionKey(asset, tf)
    const existing = this.parts.get(key) || []
    const { merged, added, updated } = mergeCandles(existing, candles)
    const { trimmed, evicted } = enforceLimit(merged, limits)
    this.parts.set(key, trimmed)
    return { total: trimmed.length, added, updated, evicted }
  }

  async load(asset: string, tf: string, limit?: number): Promise<Candle[]> {
    const key = partitionKey(asset, tf)
    const arr = this.parts.get(key) || []
    if (limit != null && limit > 0 && arr.length > limit) return arr.slice(arr.length - limit)
    // کپیِ سطحی برمی‌گردانیم تا فراخوان نتواند بافرِ داخلی را دستکاری کند.
    return arr.slice()
  }

  async count(asset: string, tf: string): Promise<number> {
    return (this.parts.get(partitionKey(asset, tf)) || []).length
  }

  async lastTime(asset: string, tf: string): Promise<number | null> {
    const arr = this.parts.get(partitionKey(asset, tf))
    return arr && arr.length ? arr[arr.length - 1].time : null
  }

  async clear(asset: string, tf: string): Promise<void> {
    this.parts.delete(partitionKey(asset, tf))
  }
}

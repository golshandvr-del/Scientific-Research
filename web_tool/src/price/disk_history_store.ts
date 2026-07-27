// ============================================================================
// price/disk_history_store.ts — پیاده‌سازیِ دیسکیِ HistoryStore  [webplan P2]
// ----------------------------------------------------------------------------
// backendِ «فایل‌سیستمِ واقعی» برای Termux/Node (webplan §۳/§۵). تاریخچهٔ دائمِ
// کندل روی دیسکِ گوشی ذخیره می‌شود تا فراتر از سقفِ کوتاهِ Yahoo (چند روز) برویم.
//
// طراحیِ کلیدی برای سازگاریِ دوگانه (مهم!):
//   - این فایل «هرگز» در سطحِ بالا به node:fs اشاره نمی‌کند. importِ fs *پویا*
//     (dynamic) و فقط داخلِ متدها انجام می‌شود. نتیجه: باندلِ Cloudflare می‌تواند
//     این ماژول را import کند بدونِ کرش؛ فقط اگر واقعاً روی Node ازش استفاده شود،
//     fs بارگذاری می‌گردد. (روی Cloudflare اصلاً از MemoryHistoryStore استفاده می‌کنیم.)
//
// فرمتِ ذخیره‌سازی: JSONL (هر خط یک کندلِ فشردهٔ [t,o,h,l,c,v]). ساده، پایدار،
//   append-friendly و بدونِ نیاز به کتابخانهٔ باینری. هر افراز یک فایل:
//     <baseDir>/<ASSET>-<TF>.jsonl   مثلِ  history/XAUUSD-M5.jsonl
//
// ring-buffer: پس از هر append، اگر از سقف گذشت، فایل با کندل‌های برش‌خورده
//   (FIFO) بازنویسی می‌شود ⇒ حجم روی گوشی کنترل‌شده می‌ماند.
//
// منطقِ ادغام/برش/حفره «خالص» از history_store.ts می‌آید ⇒ رفتارِ Disk و Memory
// بیت‌به‌بیت یکسان (اصلِ Isomorphic — ایدهٔ #۹).
// ============================================================================

import type { Candle } from '../indicators'
import {
  HISTORY_STORE_VERSION, DEFAULT_LIMITS, partitionKey,
  mergeCandles, enforceLimit,
  type HistoryStore, type HistoryLimits, type AppendResult,
} from './history_store'

// نوعِ حداقلیِ ماژولِ fs که لازم داریم (بدونِ import ساختاری در سطحِ بالا).
type FsPromises = {
  mkdir(path: string, opts?: any): Promise<any>
  readFile(path: string, enc: any): Promise<string>
  writeFile(path: string, data: string, enc?: any): Promise<void>
  appendFile(path: string, data: string, enc?: any): Promise<void>
  rm(path: string, opts?: any): Promise<void>
  stat(path: string): Promise<any>
}

export class DiskHistoryStore implements HistoryStore {
  readonly version = HISTORY_STORE_VERSION
  private baseDir: string
  private fsp: FsPromises | null = null
  private pathJoin: ((...p: string[]) => string) | null = null
  // کشِ حافظه‌ایِ هر افراز تا load/count سریع باشد و بازنویسیِ ring-buffer آسان.
  private cache = new Map<string, Candle[]>()
  private ready = new Map<string, Promise<void>>()

  constructor(baseDir: string) {
    this.baseDir = baseDir
  }

  // بارگذاریِ تنبلِ ماژول‌های Node — فقط اولین‌بار که واقعاً روی Node استفاده شود.
  private async ensureFs(): Promise<{ fsp: FsPromises; join: (...p: string[]) => string }> {
    if (!this.fsp || !this.pathJoin) {
      const fsMod: any = await import('node:fs/promises')
      const pathMod: any = await import('node:path')
      this.fsp = fsMod as FsPromises
      this.pathJoin = pathMod.join
      await this.fsp.mkdir(this.baseDir, { recursive: true })
    }
    return { fsp: this.fsp, join: this.pathJoin! }
  }

  private fileFor(join: (...p: string[]) => string, asset: string, tf: string): string {
    return join(this.baseDir, `${partitionKey(asset, tf)}.jsonl`)
  }

  // بارگذاریِ افراز از دیسک به کش (یک‌بار). خطای «فایل نیست» = افرازِ خالی.
  private async loadPartition(asset: string, tf: string): Promise<Candle[]> {
    const key = partitionKey(asset, tf)
    if (this.cache.has(key)) return this.cache.get(key)!
    if (!this.ready.has(key)) {
      this.ready.set(key, (async () => {
        const { fsp, join } = await this.ensureFs()
        const file = this.fileFor(join, asset, tf)
        let arr: Candle[] = []
        try {
          const text = await fsp.readFile(file, 'utf8')
          arr = parseJsonl(text)
        } catch { /* فایل هنوز نیست ⇒ خالی */ }
        this.cache.set(key, arr)
      })())
    }
    await this.ready.get(key)!
    return this.cache.get(key) || []
  }

  async append(asset: string, tf: string, candles: Candle[], limits: HistoryLimits = DEFAULT_LIMITS): Promise<AppendResult> {
    const key = partitionKey(asset, tf)
    const existing = await this.loadPartition(asset, tf)
    const { merged, added, updated } = mergeCandles(existing, candles)
    const { trimmed, evicted } = enforceLimit(merged, limits)
    this.cache.set(key, trimmed)

    const { fsp, join } = await this.ensureFs()
    const file = this.fileFor(join, asset, tf)
    if (evicted > 0 || updated > 0 || existing.length === 0) {
      // بازنویسیِ کاملِ فایل (لازم است چون FIFO/به‌روزرسانی درجای خط ممکن نیست).
      await fsp.writeFile(file, serializeJsonl(trimmed), 'utf8')
    } else if (added > 0) {
      // مسیرِ سریعِ افزودنِ محض: فقط کندل‌های تازه را append کن (بدونِ بازنویسی).
      const onlyNew = candles
        .filter(k => isFinite(k.time) && k.time > (existing.length ? existing[existing.length - 1].time : -Infinity))
        .sort((a, b) => a.time - b.time)
      if (onlyNew.length) await fsp.appendFile(file, serializeJsonl(onlyNew), 'utf8')
      else await fsp.writeFile(file, serializeJsonl(trimmed), 'utf8')
    }
    return { total: trimmed.length, added, updated, evicted }
  }

  async load(asset: string, tf: string, limit?: number): Promise<Candle[]> {
    const arr = await this.loadPartition(asset, tf)
    if (limit != null && limit > 0 && arr.length > limit) return arr.slice(arr.length - limit)
    return arr.slice()
  }

  async count(asset: string, tf: string): Promise<number> {
    return (await this.loadPartition(asset, tf)).length
  }

  async lastTime(asset: string, tf: string): Promise<number | null> {
    const arr = await this.loadPartition(asset, tf)
    return arr.length ? arr[arr.length - 1].time : null
  }

  async clear(asset: string, tf: string): Promise<void> {
    const key = partitionKey(asset, tf)
    this.cache.delete(key)
    this.ready.delete(key)
    const { fsp, join } = await this.ensureFs()
    try { await fsp.rm(this.fileFor(join, asset, tf), { force: true }) } catch { /* ignore */ }
  }
}

// ---------------------------------------------------------------------------
// سریال‌سازیِ JSONL — هر خط یک آرایهٔ فشردهٔ [t,o,h,l,c,v].
// (فشرده‌تر از آبجکتِ کامل؛ خواندن/نوشتنِ سریع و مقاوم به خرابیِ جزئی.)
// ---------------------------------------------------------------------------
export function serializeJsonl(candles: Candle[]): string {
  let out = ''
  for (const k of candles) {
    out += JSON.stringify([k.time, k.open, k.high, k.low, k.close, k.volume || 0]) + '\n'
  }
  return out
}

export function parseJsonl(text: string): Candle[] {
  const out: Candle[] = []
  const lines = text.split('\n')
  for (const line of lines) {
    const s = line.trim()
    if (!s) continue
    try {
      const a = JSON.parse(s)
      if (Array.isArray(a) && a.length >= 5) {
        out.push({ time: a[0], open: a[1], high: a[2], low: a[3], close: a[4], volume: a[5] ?? 0 })
      }
    } catch { /* خطِ خراب را رد کن (مقاومت به خرابیِ جزئی) */ }
  }
  // اطمینان از ترتیبِ صعودی (در صورتِ append نامرتب).
  out.sort((a, b) => a.time - b.time)
  return out
}

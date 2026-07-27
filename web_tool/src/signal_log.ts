// ============================================================================
// signal_log.ts — لاگِ حافظه‌ایِ سیگنال‌ها (رینگ‌بافر) برای کشفِ سیگنال‌های متناقض
// ----------------------------------------------------------------------------
// انگیزه (User Note):
//   کاربر گزارش داد که کارتِ M15 «در چند ثانیه سیگنالِ خرید داد و پس از رفرش
//   سیگنالِ فروش» — یک سیگنالِ متناقضِ گمراه‌کننده. برای *دیدنِ* این باگ در حینِ
//   کار، هر تصمیمِ ENTRY (خرید/فروش) که سرور تولید می‌کند این‌جا با «زمانِ دقیق +
//   کارت + جهت + کدِ لایه» ثبت می‌شود. سپس با /api/signal-log می‌توان لاگ را دید و
//   با /api/signal-log/conflicts سیگنال‌های متناقضِ همان کارت در بازهٔ کوتاه را کشف کرد.
//
// چرا حافظه‌ای (رینگ‌بافر)؟ چون محیطِ اجرا Cloudflare Workers/Pages است و
// فایل‌سیستمِ runtime ندارد. رینگ‌بافرِ ماژول‌سطح تا وقتی instance زنده است باقی
// می‌ماند — برای دیباگِ زنده کافی است (و در local-mobile که یک process است، پایدارتر).
// ============================================================================

export interface SignalLogEntry {
  ts: number            // Date.now() میلی‌ثانیه — زمانِ دقیقِ ثبت
  iso: string           // زمانِ خوانا (ISO)
  card: string          // شناسهٔ کارت (مثلِ XAUUSD-M15)
  state: string         // ENTRY / APPROACHING / NEUTRAL
  direction: string     // LONG / SHORT / —
  layerCode: string     // کدِ لایهٔ منبع (S322 و …) یا '—'
  layerName: string     // نامِ خوانای لایه
  price: number         // قیمتِ لحظه‌ای
  entry?: number
  tp?: number
  sl?: number
  candleTime?: number   // زمانِ آخرین کندلِ بسته‌شده (برای تشخیصِ repaint در برابر تغییرِ واقعی)
}

const MAX_ENTRIES = 800
const buf: SignalLogEntry[] = []

/** ثبتِ یک رویدادِ تصمیم (فقط ENTRY/APPROACHING ثبت می‌شود؛ NEUTRAL نویز است). */
export function logSignal(card: string, dec: any, price: number, candleTime?: number): void {
  try {
    const state = dec?.state || 'NEUTRAL'
    if (state !== 'ENTRY' && state !== 'APPROACHING') return
    const now = Date.now()
    const e: SignalLogEntry = {
      ts: now,
      iso: new Date(now).toISOString(),
      card,
      state,
      direction: dec?.direction || '—',
      layerCode: dec?.sourceLayer?.code || '—',
      layerName: dec?.sourceLayer?.name || dec?.headline || '—',
      price: Number(price) || 0,
      entry: dec?.entry,
      tp: dec?.tp,
      sl: dec?.sl,
      candleTime,
    }
    buf.push(e)
    if (buf.length > MAX_ENTRIES) buf.splice(0, buf.length - MAX_ENTRIES)
  } catch { /* لاگ نباید هرگز مسیرِ اصلی را بشکند */ }
}

/** آخرین n رویداد (پیش‌فرض همه). */
export function getLog(limit = MAX_ENTRIES): SignalLogEntry[] {
  return buf.slice(-limit)
}

/**
 * کشفِ سیگنال‌های متناقض: برای هر کارت، دو رویدادِ ENTRY با جهتِ مخالف که فاصلهٔ
 * زمانی‌شان کمتر از windowSec ثانیه است. این دقیقاً همان «خرید بعد فروش در چند
 * ثانیه» است که کاربر گزارش داد.
 */
export function findConflicts(windowSec = 120): Array<{
  card: string; gapSec: number
  a: SignalLogEntry; b: SignalLogEntry
}> {
  const entries = buf.filter(e => e.state === 'ENTRY')
  const byCard: Record<string, SignalLogEntry[]> = {}
  for (const e of entries) (byCard[e.card] ||= []).push(e)
  const out: Array<{ card: string; gapSec: number; a: SignalLogEntry; b: SignalLogEntry }> = []
  for (const card of Object.keys(byCard)) {
    const list = byCard[card].sort((x, y) => x.ts - y.ts)
    for (let i = 1; i < list.length; i++) {
      const a = list[i - 1], b = list[i]
      if (a.direction !== b.direction && a.direction !== '—' && b.direction !== '—') {
        const gapSec = (b.ts - a.ts) / 1000
        if (gapSec <= windowSec) out.push({ card, gapSec: Math.round(gapSec), a, b })
      }
    }
  }
  return out.sort((p, q) => q.a.ts - p.a.ts)
}

export function clearLog(): void { buf.length = 0 }

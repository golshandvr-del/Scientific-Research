// ============================================================================
// بازتولید ماژول ساختار قیمت (engine/structure.py) در TypeScript
// Pivot High/Low و سطوح حمایت/مقاومت فعال — بدون look-ahead bias.
// ============================================================================
import type { Candle } from './indicators'

export interface Pivot {
  price: number
  bar: number        // اندیس کندلِ خودِ pivot
  confBar: number    // اندیس کندلی که pivot در آن تأیید شد
  kind: 'res' | 'sup'
}

// یافتن pivotها. یک pivot-high در کندل p یعنی high[p] بزرگ‌ترین در [p-left, p+right].
// تأیید در کندل p+right رخ می‌دهد.
export function findPivots(c: Candle[], left = 5, right = 5): Pivot[] {
  const n = c.length
  const pivots: Pivot[] = []
  for (let p = left; p < n - right; p++) {
    const hv = c[p].high
    let isPh = true
    for (let k = p - left; k <= p + right; k++) {
      if (k === p) continue
      if (c[k].high > hv) { isPh = false; break }
    }
    if (isPh) pivots.push({ price: hv, bar: p, confBar: p + right, kind: 'res' })

    const lv = c[p].low
    let isPl = true
    for (let k = p - left; k <= p + right; k++) {
      if (k === p) continue
      if (c[k].low < lv) { isPl = false; break }
    }
    if (isPl) pivots.push({ price: lv, bar: p, confBar: p + right, kind: 'sup' })
  }
  return pivots
}

export interface SRLevel {
  price: number
  kind: 'res' | 'sup'
  touches: number    // تعداد برخورد/ادغام (قدرت سطح)
  bornBar: number
  lastBar: number
}

// سطوح فعال حمایت/مقاومت با ادغام سطوح نزدیک و انقضا.
// خروجی: لیست سطوح فعال در «انتهای داده» (وضعیت جاری بازار).
export function activeLevels(
  c: Candle[],
  pivots: Pivot[],
  tol = 0.0012,
  maxLevels = 60,
  expiry = 1500
): SRLevel[] {
  interface Slot { price: number; last: number; born: number; kind: 'res' | 'sup'; touches: number; active: boolean }
  const slots: Slot[] = []
  const n = c.length

  // pivotها را بر اساس کندلِ تأیید مرتب می‌کنیم تا به‌ترتیب زمانی اعمال شوند
  const byConf = [...pivots].sort((a, b) => a.confBar - b.confBar)
  let pi = 0

  for (let i = 0; i < n; i++) {
    // اعمال pivotهایی که در این کندل تأیید شده‌اند
    while (pi < byConf.length && byConf[pi].confBar === i) {
      const pv = byConf[pi]; pi++
      // ادغام با سطح فعال نزدیک
      let merged = false
      for (const s of slots) {
        if (s.active && Math.abs(s.price - pv.price) / pv.price < tol) {
          s.price = (s.price * s.touches + pv.price) / (s.touches + 1)
          s.last = i
          s.kind = pv.kind
          s.touches += 1
          merged = true
          break
        }
      }
      if (!merged) {
        // یافتن جای خالی یا قدیمی‌ترین
        let free = slots.find(s => !s.active)
        if (!free && slots.length < maxLevels) {
          free = { price: 0, last: 0, born: 0, kind: 'res', touches: 0, active: false }
          slots.push(free)
        }
        if (!free) {
          // جایگزینی قدیمی‌ترین
          free = slots.reduce((a, b) => (a.last <= b.last ? a : b))
        }
        free.price = pv.price
        free.last = i
        free.born = i
        free.kind = pv.kind
        free.touches = 1
        free.active = true
      }
    }
    // انقضا
    for (const s of slots) {
      if (s.active && i - s.last > expiry) s.active = false
    }
  }

  return slots
    .filter(s => s.active)
    .map(s => ({ price: s.price, kind: s.kind, touches: s.touches, bornBar: s.born, lastBar: s.last }))
    .sort((a, b) => a.price - b.price)
}

// نزدیک‌ترین مقاومت بالای قیمت و نزدیک‌ترین حمایت زیر قیمت
export function nearestSR(levels: SRLevel[], price: number) {
  let res: SRLevel | null = null
  let sup: SRLevel | null = null
  for (const l of levels) {
    if (l.price >= price) {
      if (!res || l.price < res.price) res = l
    } else {
      if (!sup || l.price > sup.price) sup = l
    }
  }
  return { resistance: res, support: sup }
}

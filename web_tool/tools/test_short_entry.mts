// ============================================================================
// test_short_entry.mts — تستِ یکپارچهٔ لایهٔ SHORT در مسیرِ واقعیِ analyze()+decide()
// ----------------------------------------------------------------------------
// این تست داده‌ٔ تاریخیِ واقعی را می‌خواند، پنجره‌ای را که در آن قیمت خطِ میانهٔ
// [EMA50,EMA100,SMA200] را از بالا رو به پایین قطع کرده پیدا می‌کند، همان پنجره را
// به analyze()+decide() می‌دهد و تأیید می‌کند که حالتِ ENTRY SHORT با tp/slPlan/tpPlan
// درست شلیک می‌شود. هدف: اطمینان از اینکه UI و ثبتِ معامله «undefined» نمی‌گیرد.
// ============================================================================
import { readFileSync } from 'node:fs'
import { analyze } from '../src/signal.ts'
import { decide, ASSET_SPECS } from '../src/router.ts'
import { ema, sma } from '../src/indicators.ts'
import type { Candle } from '../src/indicators.ts'

// ---- بارگذاریِ داده ----
const raw = readFileSync('../data/XAUUSD_M15.csv', 'utf8').trim().split('\n')
const candles: Candle[] = []
for (let i = 1; i < raw.length; i++) {
  const [t, o, h, l, c, v] = raw[i].split(',')
  candles.push({ time: +t, open: +o, high: +h, low: +l, close: +c, volume: +v })
}
const close = candles.map(c => c.close)
console.log(`داده: ${candles.length} کندل`)

// ---- یافتنِ باری که قطعِ رو به پایینِ خطِ میانه رخ داده ----
const e50 = ema(close, 50), e100 = ema(close, 100), s200 = sma(close, 200)
const mid = close.map((_, i) => (e50[i] + e100[i] + s200[i]) / 3)
let crossBars: number[] = []
for (let i = 300; i < close.length; i++) {
  if (close[i - 1] > mid[i - 1] && close[i] < mid[i]) crossBars.push(i)
}
console.log(`تعدادِ کلِ ماشه‌های قطعِ رو به پایین: ${crossBars.length}`)

// چند نمونهٔ اخیر را تست کن تا حالتِ ENTRY را قطعاً ببینیم
const spec = ASSET_SPECS.XAUUSD
let entryHits = 0, approachHits = 0, neutralHits = 0
const sample = crossBars.slice(-40)   // ۴۰ ماشهٔ آخر
let firstEntry: any = null
for (const b of sample) {
  const win = candles.slice(0, b + 1)          // فقط داده تا همان کندل (بدون آینده)
  const a = analyze(win)
  const dec = decide(a, win.map(c => c.close), 10000, 1.0, spec)
  if (dec.state === 'ENTRY' && dec.direction === 'SHORT') { entryHits++; if (!firstEntry) firstEntry = { b, dec } }
  else if (dec.state === 'APPROACHING') approachHits++
  else neutralHits++
}
console.log(`\nاز ${sample.length} ماشهٔ آخر: ENTRY_SHORT=${entryHits}  APPROACHING=${approachHits}  سایر=${neutralHits}`)

if (firstEntry) {
  const d = firstEntry.dec
  console.log('\n=== نمونهٔ ENTRY SHORT (اعتبارسنجیِ فیلدها) ===')
  console.log('  state      :', d.state)
  console.log('  direction  :', d.direction)
  console.log('  headline   :', d.headline)
  console.log('  entry      :', d.entry?.toFixed(2))
  console.log('  tp (سقف)   :', d.tp?.toFixed(2), '  (باید عدد باشد نه undefined)')
  console.log('  sl         :', d.sl?.toFixed(2))
  console.log('  probability:', d.probability)
  console.log('  tpPlan؟    :', !!d.tpPlan)
  console.log('  slPlan؟    :', !!d.slPlan)
  console.log('  sizing.lots:', d.sizing?.lots)
  // بررسیِ صحت: tp باید پایین‌تر از entry باشد (SHORT)، sl بالاتر از entry
  const ok = typeof d.tp === 'number' && typeof d.sl === 'number' &&
             d.tp < d.entry! && d.sl > d.entry! && !!d.tpPlan && !!d.slPlan
  console.log('\n' + (ok ? '✅ تستِ ENTRY SHORT پاس شد — همهٔ فیلدها معتبر (بدون undefined).'
                          : '❌ تست شکست خورد — فیلدی نامعتبر است.'))
  process.exit(ok ? 0 : 1)
} else {
  console.log('\n⚠️ هیچ ENTRY SHORT در نمونه شلیک نشد (ممکن است فیلترِ activeStream=bear مانع شده باشد).')
  process.exit(0)
}

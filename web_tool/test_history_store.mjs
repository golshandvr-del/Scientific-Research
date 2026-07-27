// =============================================================================
//  test_history_store.mjs — آزمونِ زیرسیستمِ ذخیره‌سازیِ تاریخچه  [webplan P2]
// -----------------------------------------------------------------------------
//  چه چیزی را اثبات می‌کند؟
//   ۱) توابعِ خالص: mergeCandles (upsert)، enforceLimit (FIFO cap)، detectGaps.
//   ۲) MemoryHistoryStore و DiskHistoryStore «رفتارِ یکسان» دارند (Isomorphic).
//   ۳) ring-buffer روی دیسک: سقفِ حجم رعایت و قدیمی‌ترین‌ها FIFO حذف می‌شوند.
//   ۴) پایداریِ دیسک: پس از بستن و بازخوانی، همان داده برمی‌گردد (gap-fill-ready).
//
//  اجرا:  cd web_tool && node test_history_store.mjs
// =============================================================================
import { build } from 'esbuild'
import { pathToFileURL } from 'node:url'
import { writeFileSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

async function load(entry) {
  const res = await build({ entryPoints: [entry], bundle: true, format: 'esm', write: false, platform: 'node' })
  const tmp = mkdtempSync(join(tmpdir(), 'hist-'))
  const modPath = join(tmp, 'm.mjs')
  writeFileSync(modPath, res.outputFiles[0].text)
  return import(pathToFileURL(modPath).href)
}

const H = await load('src/price/history_store.ts')
const M = await load('src/price/memory_history_store.ts')
const D = await load('src/price/disk_history_store.ts')

let pass = 0, fail = 0
function check(name, cond) {
  if (cond) { pass++; console.log(`  ✅ ${name}`) }
  else { fail++; console.log(`  ❌ ${name}`) }
}
const k = (t, c) => ({ time: t, open: c, high: c + 1, low: c - 1, close: c, volume: 10 })

// --- ۱) mergeCandles: upsert بر اساسِ زمان ---
console.log('\n[۱] mergeCandles (upsert)')
{
  const a = [k(100, 1), k(200, 2), k(300, 3)]
  const b = [k(300, 99), k(400, 4)]   // 300 به‌روزرسانی، 400 جدید
  const { merged, added, updated } = H.mergeCandles(a, b)
  check('طول نهایی = 4', merged.length === 4)
  check('added = 1 (زمانِ 400)', added === 1)
  check('updated = 1 (زمانِ 300)', updated === 1)
  check('زمانِ 300 مقدارِ تازه (close=99) گرفت', merged.find(x => x.time === 300).close === 99)
  check('ترتیب صعودی', merged.every((x, i) => i === 0 || x.time > merged[i - 1].time))
}

// --- ۲) enforceLimit: برشِ FIFO ---
console.log('\n[۲] enforceLimit (FIFO cap)')
{
  const arr = Array.from({ length: 10 }, (_, i) => k(i * 100, i))
  const { trimmed, evicted } = H.enforceLimit(arr, { maxBars: 4, minBars: 2 })
  check('طول = 4', trimmed.length === 4)
  check('evicted = 6', evicted === 6)
  check('قدیمی‌ها حذف شدند (اولین زمان = 600)', trimmed[0].time === 600)
  check('تازه‌ترین حفظ شد (آخر = 900)', trimmed[trimmed.length - 1].time === 900)
}

// --- ۳) detectGaps ---
console.log('\n[۳] detectGaps')
{
  const tf = 300
  // فاصلهٔ عادی 300؛ یک پرش از 900→2100 (۳ کندلِ گم‌شده) ایجاد می‌کنیم
  const arr = [k(0, 1), k(300, 2), k(600, 3), k(900, 4), k(2100, 5), k(2400, 6)]
  const gaps = H.detectGaps(arr, tf)
  check('یک حفره پیدا شد', gaps.length === 1)
  check('حفره از 900 تا 2100', gaps[0].fromTime === 900 && gaps[0].toTime === 2100)
  check('missingBars = 3', gaps[0].missingBars === 3)
}

// --- ۴) parity: Memory vs Disk رفتارِ یکسان ---
console.log('\n[۴] parity: Memory vs Disk')
{
  const dir = mkdtempSync(join(tmpdir(), 'disk-'))
  const mem = new M.MemoryHistoryStore()
  const disk = new D.DiskHistoryStore(dir)
  const limits = { maxBars: 5, minBars: 2 }

  const batch1 = Array.from({ length: 4 }, (_, i) => k(i * 300, i))       // 0..900
  const batch2 = [k(900, 999), k(1200, 4), k(1500, 5), k(1800, 6)]        // upsert 900 + 3 جدید ⇒ کل 7 → cap 5

  const rM1 = await mem.append('XAUUSD', 'M5', batch1, limits)
  const rD1 = await disk.append('XAUUSD', 'M5', batch1, limits)
  check('append#1 total یکسان', rM1.total === rD1.total)
  check('append#1 added یکسان', rM1.added === rD1.added)

  const rM2 = await mem.append('XAUUSD', 'M5', batch2, limits)
  const rD2 = await disk.append('XAUUSD', 'M5', batch2, limits)
  check('append#2 total یکسان', rM2.total === rD2.total && rM2.total === 5)
  check('append#2 updated یکسان', rM2.updated === rD2.updated && rM2.updated === 1)
  check('append#2 evicted یکسان', rM2.evicted === rD2.evicted)

  const loadM = await mem.load('XAUUSD', 'M5')
  const loadD = await disk.load('XAUUSD', 'M5')
  check('load: طول یکسان', loadM.length === loadD.length)
  check('load: محتوا بیت‌به‌بیت یکسان', JSON.stringify(loadM) === JSON.stringify(loadD))
  check('load: upsert اعمال شد (900.close=999)', loadD.find(x => x.time === 900)?.close === 999)
  check('lastTime یکسان', (await mem.lastTime('XAUUSD','M5')) === (await disk.lastTime('XAUUSD','M5')))

  // --- ۵) پایداریِ دیسک: نمونهٔ تازه از همان پوشه همان داده را می‌خواند ---
  console.log('\n[۵] پایداریِ دیسک (بازخوانی از فایل)')
  const disk2 = new D.DiskHistoryStore(dir)
  const reload = await disk2.load('XAUUSD', 'M5')
  check('بازخوانی: طول یکسان', reload.length === loadD.length)
  check('بازخوانی: محتوا یکسان', JSON.stringify(reload) === JSON.stringify(loadD))

  // load با limit
  const last2 = await disk2.load('XAUUSD', 'M5', 2)
  check('load(limit=2): دو کندلِ آخر', last2.length === 2 && last2[1].time === 1800)

  rmSync(dir, { recursive: true, force: true })
}

console.log(`\n=== نتیجه: ${pass} پاس / ${fail} فیل ===`)
process.exit(fail ? 1 : 0)

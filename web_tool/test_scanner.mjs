// =============================================================================
//  test_scanner.mjs — تستِ موتورِ کاوشگرِ اندیکاتور P8 روی دادهٔ واقعیِ CSV
// -----------------------------------------------------------------------------
//  موتور را از راهِ esbuild بارگذاری می‌کند (بدونِ build کامل)، روی برشی از
//  XAUUSD_M5.csv اجرا می‌کند و اثبات می‌کند:
//    ۱) گزارش ساختارِ ScanReport@v1 دارد،
//    ۲) اندیکاتورهای پیچیده (alligator/ichimoku) هم کاوش می‌شوند (علیهِ اشتباهِ #۳)،
//    ۳) خروجی قطعی و منطقی است (spread، p-value، کاندیدها).
// =============================================================================
import { build } from 'esbuild'
import { pathToFileURL } from 'node:url'
import { writeFileSync, readFileSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, '..')

async function loadTs(entry) {
  const res = await build({ entryPoints: [entry], bundle: true, format: 'esm', write: false, platform: 'node' })
  const tmp = mkdtempSync(join(tmpdir(), 'scan-'))
  const modPath = join(tmp, 'mod.mjs')
  writeFileSync(modPath, res.outputFiles[0].text)
  return import(pathToFileURL(modPath).href)
}

function readCsv(path, maxRows) {
  const lines = readFileSync(path, 'utf8').trim().split('\n')
  const out = []
  const start = Math.max(1, lines.length - maxRows)
  for (let i = start; i < lines.length; i++) {
    const [t, o, h, l, c, v] = lines[i].trim().split(',').map(Number)
    if ([t, o, h, l, c].every(Number.isFinite)) out.push({ time: t, open: o, high: h, low: l, close: c, volume: v || 0 })
  }
  return out
}

const { scanIndicators } = await loadTs(join(__dirname, 'src', 'scanner', 'scanner.ts'))

let failures = 0
function check(cond, msg) { if (!cond) { console.log('❌ ' + msg); failures++ } else console.log('✅ ' + msg) }

const candles = readCsv(join(ROOT, 'data', 'XAUUSD_M5.csv'), 3000)
console.log(`کندل‌های خوانده‌شده (XAUUSD M5): ${candles.length}\n`)

const report = scanIndicators('XAUUSD', 'M5', candles, 5)

check(report.v === 1, 'گزارش نسخهٔ ScanReport@v1 دارد')
check(report.asset === 'XAUUSD' && report.tf === 'M5', 'asset/tf درست ثبت شد')
check(report.horizon === 5, 'horizon=5 اعمال شد')
check(Array.isArray(report.edges) && report.edges.length > 0, `edges غیرتهی (${report.edges.length} لبه)`)

// اثباتِ کاوشِ اندیکاتورهای پیچیده (علیهِ اشتباهِ رایجِ #۳):
const complexNames = new Set(report.edges.map(e => e.indicator))
check(complexNames.has('alligator'), 'الیگیتور کاوش شد (اندیکاتورِ پیچیده)')
check(complexNames.has('ichimoku'), 'ایچیموکو کاوش شد (اندیکاتورِ پیچیده)')
check(complexNames.has('vortex'), 'ورتکس کاوش شد')
check(complexNames.has('adx'), 'ADX کاوش شد')

// اعتبارِ آماری: p-value در [0,1]، spearman در [-1,1].
const allValid = report.edges.every(e =>
  e.pValue >= 0 && e.pValue <= 1 && e.spearman >= -1 && e.spearman <= 1 && e.n >= 200)
check(allValid, 'همهٔ لبه‌ها آماری معتبرند (p∈[0,1], ρ∈[-1,1], n≥200)')

// کاندیداها زیرمجموعهٔ edges با isCandidate=true.
check(report.candidates.every(e => e.isCandidate), 'همهٔ candidates پرچمِ isCandidate دارند')

console.log(`\n📊 خلاصه: ${report.note}`)
console.log(`\nقوی‌ترین ۸ لبه (بر اساسِ |spread|×معناداری):`)
for (const e of report.edges.slice(0, 8)) {
  const tag = e.isCandidate ? `⭐${e.direction}` : '  '
  console.log(`  ${tag}  ${e.indicator}${e.sub ? '.' + e.sub : ''}  spread=${e.spread}٪  ρ=${e.spearman}  p=${e.pValue}  n=${e.n}`)
}

console.log(failures === 0 ? '\n🎉 همهٔ تست‌ها پاس شدند.' : `\n💥 ${failures} تست شکست خورد.`)
process.exit(failures === 0 ? 0 : 1)

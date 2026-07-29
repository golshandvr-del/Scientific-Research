// parity_s344_signal.mjs — برابریِ سیگنالِ نهاییِ TS↔Python برای S344 (XAUUSD-M15 SHORT).
// برای هر کندلِ i، یک «پنجرهٔ دنباله‌دارِ» ثابت (WIN کندلِ آخر تا i) به computeS344 داده می‌شود.
// چون منطق:
//   • ADR = میانگینِ دامنهٔ ۱۴ روزِ قبل (۱۴×۹۶=۱۳۴۴ کندلِ M15)،
//   • رژیم = r2(34) & hurst(55) (همگراییِ سریع)،
//   • مرزِ روز و opening-range فقط به «روزِ جاریِ کندلِ i» وابسته‌اند،
// پس WIN=3000 هر سه را کاملاً و causal پوشش می‌دهد و ارزیابی O(WIN) می‌ماند.
// اجرا: cd web_tool && node parity_s344_signal.mjs
import fs from 'fs'
import { computeS344, S344_CFG } from './dist_parity/trend_from_open_s344.js'

const WIN = 3000      // >> 1344 (ADR) و >> 55 (hurst)
const WARMUP = 3000   // فقط کندل‌هایی با idx≥WARMUP تست می‌شوند (پنجرهٔ کامل)
const CARD = 'XAUUSD-M15'

function main() {
  const ref = JSON.parse(fs.readFileSync('../strategies/s344_parity_ref.json', 'utf8'))
  const cfg = S344_CFG[CARD]
  const candles = ref.candles.map(c => ({
    time: c.time, open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume || 0,
  }))
  const N = candles.length
  const pySet = new Set(ref.signal_idx)

  // اندیس‌های تست: همهٔ entryهای پایتون (idx≥WARMUP) + نمونهٔ ثابت از non-entryها
  const entryIdx = [...ref.signal_idx].filter(i => i >= WARMUP).sort((a, b) => a - b)
  const belowWarmup = [...ref.signal_idx].filter(i => i < WARMUP)
  const nonEntry = []
  const step = Math.max(1, Math.floor((N - WARMUP) / 2000))
  for (let i = WARMUP; i < N; i += step) if (!pySet.has(i)) nonEntry.push(i)
  const testIdx = [...new Set([...entryIdx, ...nonEntry])].sort((a, b) => a - b)

  let mism = 0, falsePos = 0, falseNeg = 0, checked = 0
  const mismEx = []
  for (const i of testIdx) {
    const lo = Math.max(0, i - WIN + 1)
    const win = candles.slice(lo, i + 1)          // پنجرهٔ دنباله‌دار؛ کندلِ آخر = i
    const raw = computeS344(win, cfg)
    const tsActive = !!raw.active
    const py = pySet.has(i)
    checked++
    if (tsActive !== py) {
      mism++
      if (tsActive && !py) falsePos++
      if (!tsActive && py) falseNeg++
      if (mismEx.length < 15) mismEx.push({ i, py, ts: tsActive })
    }
  }

  const ok = mism === 0
  console.log(`\n=== ${CARD} (S344 SHORT) ===`)
  console.log(`  python signals total = ${ref.signal_idx.length}  (below WARMUP=${belowWarmup.length}, testable=${entryIdx.length})`)
  console.log(`  tested   = ${checked}  (${entryIdx.length} entries + ${nonEntry.length} non-entry samples)`)
  console.log(`  mismatch = ${mism}  (falsePos=${falsePos}, falseNeg=${falseNeg})  ${ok ? '✅ PASS' : '❌ FAIL'}`)
  if (!ok) console.log('  ❌ examples:', JSON.stringify(mismEx))
  process.exit(ok ? 0 : 1)
}

main()

// parity_s341_signal.mjs — برابریِ سیگنالِ ورودِ TS↔Python برای S341 (هر ۴ تایم‌فریم).
// برای هر کندلِ i، یک «پنجرهٔ دنباله‌دارِ» ثابت (WIN کندلِ آخر تا i) به computeS341
// داده می‌شود؛ چون:
//   • اندیکاتورهای EWM/RMA/chop با ~۳۰۰ کندل همگرا می‌شوند،
//   • منطقِ سیگنالِ دوم فقط ۴۰ کندلِ اخیر را می‌شمارد،
// پس WIN=800 هر دو را کاملاً پوشش می‌دهد و ارزیابی O(WIN) (کارآمد) می‌ماند.
// اجرا: cd web_tool && node parity_s341_signal.mjs [CARD ...]
import fs from 'fs'
import { computeS341, S341_CFG } from './dist_parity/swing_fade_s341.js'

const WIN = 800     // طولِ پنجرهٔ دنباله‌دار (>> 300 همگراییِ اندیکاتور و 40 پنجرهٔ سیگنالِ دوم)
const WARMUP = 1500 // فقط کندل‌هایی با idx≥WARMUP تست می‌شوند (همهٔ سیگنال‌های پایتون idx≥2044)

function refPath(card) {
  return card === 'XAUUSD-H1'
    ? '../strategies/s341_parity_ref.json'
    : `../strategies/s341_parity_ref_${card}.json`
}

function testCard(card) {
  const ref = JSON.parse(fs.readFileSync(refPath(card), 'utf8'))
  const cfg = S341_CFG[card]
  const candles = ref.candles.map(c => ({
    time: c.time, open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume || 0,
  }))
  const N = candles.length
  const pySet = new Set(ref.signal_idx)

  // اندیس‌های تست: همهٔ entryهای پایتون + نمونهٔ ثابت از non-entryها
  const entryIdx = [...ref.signal_idx].filter(i => i >= WARMUP).sort((a, b) => a - b)
  const nonEntry = []
  const step = Math.max(1, Math.floor((N - WARMUP) / 500))
  for (let i = WARMUP; i < N; i += step) if (!pySet.has(i)) nonEntry.push(i)
  const testIdx = [...new Set([...entryIdx, ...nonEntry])].sort((a, b) => a - b)

  let mism = 0, falsePos = 0, falseNeg = 0, checked = 0
  const mismEx = []
  for (const i of testIdx) {
    const lo = Math.max(0, i - WIN + 1)
    const win = candles.slice(lo, i + 1)          // پنجرهٔ دنباله‌دار؛ کندلِ آخر = i
    const raw = computeS341(win, cfg)
    const tsActive = !!raw.active
    const py = pySet.has(i)
    checked++
    if (tsActive !== py) {
      mism++
      if (tsActive && !py) falsePos++
      if (!tsActive && py) falseNeg++
      if (mismEx.length < 12) mismEx.push({ i, py, ts: tsActive })
    }
  }

  const ok = mism === 0
  console.log(`\n=== ${card} ===  entries(py,idx≥${WARMUP})=${entryIdx.length}`)
  console.log(`  tested   = ${checked}  (${entryIdx.length} entries + ${nonEntry.length} non-entry)`)
  console.log(`  mismatch = ${mism}  (falsePos=${falsePos}, falseNeg=${falseNeg})  ${ok ? '✅ PASS' : '❌'}`)
  if (!ok) console.log('  ❌ examples:', JSON.stringify(mismEx))
  return ok
}

const cards = process.argv.slice(2)
  .length ? process.argv.slice(2)
  : ['XAUUSD-M5', 'XAUUSD-M15', 'XAUUSD-M30', 'XAUUSD-H1']

let all = true
for (const card of cards) all = testCard(card) && all
console.log(`\nOVERALL: ${all ? 'ALL PASS ✓' : 'SEE ABOVE'}`)
process.exit(all ? 0 : 1)

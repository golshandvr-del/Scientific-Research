// parity_s341_signal.mjs — برابریِ سیگنالِ ورودِ TS↔Python برای S341-H1.
// همهٔ کندل‌هایی که پایتون active زده + نمونهٔ ثابت از non-entry را با
// computeS341(candles[0..i]) در TS بازتولید و مقایسه می‌کند.
// اجرا: cd web_tool && node parity_s341_signal.mjs
import fs from 'fs'
import { computeS341, S341_CFG } from './dist_parity/swing_fade_s341.js'

const ref = JSON.parse(fs.readFileSync('../strategies/s341_parity_ref.json', 'utf8'))
const cfg = S341_CFG['XAUUSD-H1']
const candles = ref.candles.map(c => ({
  time: c.time, open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume || 0,
}))
const N = candles.length

// مجموعهٔ سیگنالِ پایتون به‌صورتِ Set برای جست‌وجوی O(1)
const pySet = new Set(ref.signal_idx)

// اندیس‌های تست: همهٔ entryهای پایتون + نمونهٔ شبه‌تصادفیِ ثابت از non-entryها
const entryIdx = [...ref.signal_idx].sort((a, b) => a - b)
const warmup = 250  // تا اندیکاتورهای EWM/RMA همگرا شوند (همهٔ سیگنال‌ها idx≥2044)
const nonEntry = []
const step = Math.max(1, Math.floor((N - warmup) / 600))
for (let i = warmup; i < N; i += step) if (!pySet.has(i)) nonEntry.push(i)

const testIdx = [...new Set([...entryIdx, ...nonEntry])].sort((a, b) => a - b)

let mism = 0, falsePos = 0, falseNeg = 0, checked = 0
const mismEx = []
for (const i of testIdx) {
  const raw = computeS341(candles.slice(0, i + 1), cfg)
  const tsActive = !!raw.active
  const py = pySet.has(i)
  checked++
  if (tsActive !== py) {
    mism++
    if (tsActive && !py) falsePos++
    if (!tsActive && py) falseNeg++
    if (mismEx.length < 10) mismEx.push({ i, py, ts: tsActive })
  }
}

console.log('S341-H1 signal-level parity (TS computeS341 vs Python build_signal)\n')
console.log(`  entries(py) = ${entryIdx.length}`)
console.log(`  tested      = ${checked}  (all ${entryIdx.length} entries + ${nonEntry.length} non-entry samples)`)
console.log(`  mismatch    = ${mism}  (falsePos=${falsePos}, falseNeg=${falseNeg})`)
if (mism === 0) {
  console.log('\n  ✅ PARITY PASS — TS منطبق بر Python روی همهٔ کندل‌های آزموده‌شده')
  process.exitCode = 0
} else {
  console.log('\n  ❌ mismatch examples:', JSON.stringify(mismEx))
  process.exitCode = 1
}

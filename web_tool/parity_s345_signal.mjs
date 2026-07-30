// parity_s345_signal.mjs — برابریِ سیگنالِ نهاییِ TS↔Python برای S345 (هر دو کارت).
// برای هر کندلِ i، یک «پنجرهٔ دنباله‌دارِ» ثابت (WIN کندلِ آخر تا i) به computeS345 داده
// می‌شود. منطقِ لایه فقط به این‌ها وابسته است:
//   • ATR(14) و r2(34)  ⇒ همگراییِ سریع،
//   • مرزِ روزِ جاری + رگرسیونِ تجمعیِ همان روز (حداکثر یک روز کندل)،
//   • روزِ ماهِ کندلِ i (فیلترِ Turn-of-Month).
// پس WIN=1500 (>> یک روزِ M15 = ۹۶ و >> ۳۴/۱۴) هر سه را کاملاً و causal پوشش می‌دهد.
// اجرا: cd web_tool && node parity_s345_signal.mjs
import fs from 'fs'
import { computeS345, S345_CFG } from './dist_parity/reversal_day_s345.js'

const WIN = 1500
const WARMUP = 1500
const CARDS = ['XAUUSD-M15', 'EURUSD-M30']

function runCardParity(card) {
  const fn = `../strategies/s345_parity_ref_${card.replace('-', '_')}.json`
  const ref = JSON.parse(fs.readFileSync(fn, 'utf8'))
  const cfg = S345_CFG[card]
  const candles = ref.candles.map(c => ({
    time: c.time, open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume || 0,
  }))
  const N = candles.length
  const pySet = new Set(ref.signal_idx)

  // اندیس‌های تست: همهٔ سیگنال‌های پایتون (idx≥WARMUP) + نمونهٔ منظم از non-signalها
  const entryIdx = [...ref.signal_idx].filter(i => i >= WARMUP).sort((a, b) => a - b)
  const belowWarmup = [...ref.signal_idx].filter(i => i < WARMUP)
  const nonEntry = []
  const step = Math.max(1, Math.floor((N - WARMUP) / 2500))
  for (let i = WARMUP; i < N; i += step) if (!pySet.has(i)) nonEntry.push(i)
  const testIdx = [...new Set([...entryIdx, ...nonEntry])].sort((a, b) => a - b)

  let mism = 0, falsePos = 0, falseNeg = 0, checked = 0
  const mismEx = []
  for (const i of testIdx) {
    const lo = Math.max(0, i - WIN + 1)
    const win = candles.slice(lo, i + 1)          // پنجرهٔ دنباله‌دار؛ کندلِ آخر = i
    const raw = computeS345(win, cfg)
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
  console.log(`\n=== ${card} (S345 ${cfg.side}) ===`)
  console.log(`  python signals total = ${ref.signal_idx.length}  (below WARMUP=${belowWarmup.length}, testable=${entryIdx.length})`)
  console.log(`  tested   = ${checked}  (${entryIdx.length} signals + ${nonEntry.length} non-signal samples)`)
  console.log(`  mismatch = ${mism}  (falsePos=${falsePos}, falseNeg=${falseNeg})  ${ok ? '✅ PASS' : '❌ FAIL'}`)
  if (!ok) console.log('  ❌ examples:', JSON.stringify(mismEx))
  return ok
}

function main() {
  let allOk = true
  for (const card of CARDS) allOk = runCardParity(card) && allOk
  console.log(`\n${allOk ? '✅ ALL CARDS PARITY PASS' : '❌ PARITY FAILED'}`)
  process.exit(allOk ? 0 : 1)
}

main()

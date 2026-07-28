// parity_s335_signal.mjs — برابریِ سیگنالِ ورودِ TS↔Python.
// برای هر TF: تمام کندل‌هایی که پایتون entry زده + نمونهٔ تصادفیِ non-entry را
// با computeS335(candles[0..i]) در TS بازتولید و مقایسه می‌کند.
// اجرا (پس از bundle): node parity_s335_signal.mjs
import fs from 'fs'
import { computeS335, S335_CFG } from './dist_parity/s335_reflex_cycle.js'

const TF_KEY = { M5: 'XAUUSD-M5', M15: 'XAUUSD-M15', H1: 'XAUUSD-H1' }

function testTF(tf) {
  const ref = JSON.parse(fs.readFileSync(`../strategies/s335_signal_${tf}.json`, 'utf8'))
  const cfg = S335_CFG[TF_KEY[tf]]
  const candles = ref.candles.map(c => ({ ...c, volume: 0 }))
  const pySig = ref.signal
  const N = candles.length

  // مجموعهٔ اندیس‌های تست: همهٔ entryهای پایتون + نمونهٔ non-entry
  const entryIdx = []
  for (let i = 0; i < N; i++) if (pySig[i]) entryIdx.push(i)
  const nonEntry = []
  const need = Math.max(cfg.pHu, cfg.pTf, cfg.pR2, cfg.pChop) + 5
  // نمونهٔ شبه‌تصادفیِ ثابت از non-entryها (هر ~step امین)
  const step = Math.max(1, Math.floor((N - need) / 400))
  for (let i = need; i < N; i += step) if (!pySig[i]) nonEntry.push(i)

  const testIdx = [...entryIdx, ...nonEntry].sort((a, b) => a - b)
  let mism = 0, falsePos = 0, falseNeg = 0, checked = 0
  for (const i of testIdx) {
    const raw = computeS335(candles.slice(0, i + 1), cfg)
    const tsActive = !!raw.active
    const py = !!pySig[i]
    checked++
    if (tsActive !== py) {
      mism++
      if (tsActive && !py) falsePos++
      if (!tsActive && py) falseNeg++
      if (mism <= 8) console.log(`  MISMATCH @${i}: py=${py} ts=${tsActive}`)
    }
  }
  const status = mism === 0 ? 'PASS' : 'FAIL'
  console.log(`${tf.padEnd(4)} entries(py)=${entryIdx.length} tested=${checked} mismatch=${mism} (FP=${falsePos} FN=${falseNeg})  [${status}]`)
  return mism === 0
}

console.log('S335 signal-level parity (TS computeS335 vs Python build_signal)\n')
let ok = true
for (const tf of ['M5', 'M15', 'H1']) ok = testTF(tf) && ok
console.log(`\nOVERALL: ${ok ? 'ALL PASS ✓' : 'SEE ABOVE'}`)
process.exit(ok ? 0 : 1)

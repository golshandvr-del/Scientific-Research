// parity_s335.mjs — تستِ برابریِ عددیِ TS↔Python برای اندیکاتورهای S335.
// JSONِ مرجعِ پایتون را می‌خواند، همان اندیکاتورها را با توابعِ TS محاسبه و
// حداکثرِ اختلاف را گزارش می‌کند. اجرا: node parity_s335.mjs (پس از build:parity)
import fs from 'fs'
import {
  reflexSeries, trendflexSeries, hurstSeries, r2Series, chopSeries,
} from './dist_parity/s335_reflex_cycle.js'

const ref = JSON.parse(fs.readFileSync('../strategies/s335_parity_ref.json', 'utf8'))
const P = ref.params
const close = ref.candles.map(c => c.close)
const candles = ref.candles.map(c => ({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close, volume: 0 }))

const tsReflex = reflexSeries(close, P.p_rf)
const tsTflex  = trendflexSeries(close, P.p_tf)
const tsHurst  = hurstSeries(close, P.p_hu)
const tsR2     = r2Series(close, P.p_r2)
const tsChop   = chopSeries(candles, P.p_ch)

function compare(name, py, ts) {
  let maxAbs = 0, maxRel = 0, nCompared = 0, nMismatchNaN = 0
  let worstIdx = -1
  for (let i = 0; i < py.length; i++) {
    const a = py[i]            // null یا number
    const b = ts[i]            // number یا NaN
    const aNaN = (a === null || a === undefined)
    const bNaN = (b === null || b === undefined || !Number.isFinite(b))
    if (aNaN || bNaN) {
      if (aNaN !== bNaN) nMismatchNaN++       // یکی NaN، دیگری معتبر (مرزی)
      continue
    }
    nCompared++
    const d = Math.abs(a - b)
    if (d > maxAbs) { maxAbs = d; worstIdx = i }
    const rel = Math.abs(a) > 1e-9 ? d / Math.abs(a) : d
    if (rel > maxRel) maxRel = rel
  }
  const status = maxAbs < 1e-4 ? 'PASS' : (maxAbs < 1e-2 ? 'WARN' : 'FAIL')
  console.log(`${name.padEnd(11)} n=${nCompared} maxAbs=${maxAbs.toExponential(3)} maxRel=${maxRel.toExponential(3)} nan-edge=${nMismatchNaN} worstIdx=${worstIdx}  [${status}]`)
  if (worstIdx >= 0 && maxAbs >= 1e-4) {
    console.log(`    @${worstIdx}: py=${py[worstIdx]} ts=${ts[worstIdx]}`)
  }
  return status
}

console.log(`parity check on ${close.length} bars (params ${JSON.stringify(P)})\n`)
const results = [
  compare('reflex', ref.reflex, tsReflex),
  compare('trendflex', ref.trendflex, tsTflex),
  compare('hurst', ref.hurst, tsHurst),
  compare('r2', ref.r2, tsR2),
  compare('chop', ref.chop, tsChop),
]
const allPass = results.every(r => r === 'PASS')
console.log(`\nOVERALL: ${allPass ? 'ALL PASS ✓' : 'SEE ABOVE'}`)
process.exit(allPass ? 0 : 1)

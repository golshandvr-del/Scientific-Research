// ============================================================================
// parity_s355_state.mjs — اثباتِ برابریِ پورت (TS ⟷ Python) برای دروازهٔ S355
// ----------------------------------------------------------------------------
// هدف: ثابت کردنِ اینکه `lpsbStateSeries` در TypeScript **عیناً** همان چیزی را
// تولید می‌کند که `strategies/s351_lpsb.lpsb_signals(...)[2]` در پایتون تولید
// می‌کند — چون حکمِ RQS2=83.9 روی نسخهٔ پایتون صادر شده و اگر پورت یک کندل هم
// جابه‌جا باشد، سایت چیزی را نشان می‌دهد که هرگز آزموده نشده است.
//
// مرجعِ پایتون با این دستور ساخته می‌شود (خروجی به /tmp، در مخزن ذخیره نمی‌شود
// چون ۲۰۰٬۰۰۰ عدد است):
//
//   PYTHONPATH=. python3 -c "
//   import json, numpy as np
//   from engine import scalp_engine as se
//   from strategies.s351_lpsb import lpsb_signals
//   from strategies.s351_verdict import CENTRAL
//   df = se.load_data(se.ASSETS['XAUUSD_M5']['file'])
//   _, _, st = lpsb_signals(df, CENTRAL['L'], CENTRAL['f'], warmup=300)
//   json.dump([int(x) for x in st], open('/tmp/_s355_state_py.json','w'))"
//
// اجرا:  node web_tool/parity_s355_state.mjs
// معیارِ قبولی: mismatch = 0 روی **هر** کندل (نه نمونه‌برداری).
// ============================================================================
import { readFileSync } from 'node:fs'
import { build } from 'esbuild'
import { pathToFileURL } from 'node:url'

const ROOT = '/home/user/webapp'

// ۱) کامپایلِ ماژولِ S355 به یک باندلِ موقتِ ESM
const outfile = '/tmp/_s355_layer.mjs'
await build({
  entryPoints: [`${ROOT}/web_tool/src/lpsb_state_s355.ts`],
  bundle: true, format: 'esm', platform: 'node', outfile, logLevel: 'error',
})
const { lpsbStateSeries, LPSB_CENTRAL } = await import(pathToFileURL(outfile).href)

// ۲) بارگذاریِ همان CSVِ پایتون
const csv = readFileSync(`${ROOT}/data/XAUUSD_M5.csv`, 'utf8').trim().split('\n')
const header = csv[0].split(',')
const iT = header.indexOf('time'), iO = header.indexOf('open'), iH = header.indexOf('high'),
      iL = header.indexOf('low'), iC = header.indexOf('close')
const candles = csv.slice(1).map(line => {
  const p = line.split(',')
  const ts = p[iT]
  const tsec = /^\d+$/.test(ts) ? parseInt(ts, 10)
                                : Math.floor(new Date(ts.replace(' ', 'T') + 'Z').getTime() / 1000)
  return { time: tsec, open: +p[iO], high: +p[iH], low: +p[iL], close: +p[iC], volume: 0 }
})
console.log('candles:', candles.length)

// ۳) حالتِ ساختار در TypeScript
const ts = lpsbStateSeries(candles, LPSB_CENTRAL.L, LPSB_CENTRAL.f)

// ۴) مرجعِ پایتون
const py = JSON.parse(readFileSync('/tmp/_s355_state_py.json', 'utf8'))
if (py.length !== ts.length) {
  console.log(`LENGTH MISMATCH: py=${py.length} ts=${ts.length}`)
  process.exit(1)
}

// ۵) مقایسهٔ کندل‌به‌کندل
let mismatch = 0
const firstBad = []
for (let i = 0; i < py.length; i++) {
  if (py[i] !== ts[i]) {
    mismatch++
    if (firstBad.length < 12) firstBad.push({ i, py: py[i], ts: ts[i] })
  }
}

const cnt = a => { const c = { '-1': 0, '0': 0, '1': 0 }; for (const v of a) c[String(v)]++; return c }
console.log('py state counts:', cnt(py))
console.log('ts state counts:', cnt(Array.from(ts)))
console.log(`mismatch: ${mismatch} / ${py.length}`)
if (mismatch) {
  console.log('first mismatches:', JSON.stringify(firstBad))
  console.log('PARITY: FAIL ❌')
  process.exit(1)
}
console.log('PARITY: OK ✅  (verbatim — every single bar identical)')

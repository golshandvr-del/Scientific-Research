// parity S354: computeS354 (TS/esbuild) vs Python build_signals long entry-bars.
// شبیه‌سازیِ زنده: در هر کندلِ i، فقط candles[0..i] داده می‌شود و active بررسی می‌شود.
import { readFileSync } from 'node:fs'
import { build } from 'esbuild'
import { pathToFileURL } from 'node:url'
import { writeFileSync } from 'node:fs'

// ۱) کامپایلِ ماژولِ S354 به یک باندلِ موقتِ ESM
const outfile = '/tmp/_s354_layer.mjs'
await build({
  entryPoints: ['/home/user/webapp/web_tool/src/trend_resumption_s354.ts'],
  bundle: true, format: 'esm', platform: 'node', outfile,
  logLevel: 'error',
})
const { computeS354, S354_CFG } = await import(pathToFileURL(outfile).href)

// ۲) بارگذاریِ کندل‌های XAU-H1 از CSV (همان دادهٔ پایتون)
const csv = readFileSync('/home/user/webapp/data/XAUUSD_H1.csv', 'utf8').trim().split('\n')
const header = csv[0].split(',')
const iTime = header.indexOf('time'), iO = header.indexOf('open'), iH = header.indexOf('high'),
      iL = header.indexOf('low'), iC = header.indexOf('close')
const candles = csv.slice(1).map(line => {
  const p = line.split(',')
  // time may be ISO or epoch; normalize to epoch seconds
  let ts = p[iTime]
  let tsec
  if (/^\d+$/.test(ts)) tsec = parseInt(ts, 10)
  else tsec = Math.floor(new Date(ts.replace(' ', 'T') + 'Z').getTime() / 1000)
  return { time: tsec, open: +p[iO], high: +p[iH], low: +p[iL], close: +p[iC] }
})
const n = candles.length
console.log('candles:', n, '| first time:', candles[0].time, '| last:', candles[n - 1].time)

// ۳) شبیه‌سازیِ زنده: entry-bar های TS
const cfg = S354_CFG['XAUUSD-H1']
const tsEntries = []
// برای سرعت: فقط از warmup به بعد (need). اما برای دقتِ کامل از 0.
const need = cfg.r2Period + cfg.atrPeriod + cfg.barsPerDay + 10
for (let i = need; i < n; i++) {
  const sub = candles.slice(0, i + 1)   // کندل‌های بسته تا i
  const raw = computeS354(sub, cfg)
  if (raw.active) tsEntries.push(i)
}
console.log('TS active entry-bars:', tsEntries.length)

// ۴) مقایسه با پایتون
const py = JSON.parse(readFileSync('/home/user/webapp/results/_scan_S354/_py_entrybars_H1.json', 'utf8'))
const pySet = new Set(py.entry_bars)
const tsSet = new Set(tsEntries)
const onlyPy = py.entry_bars.filter(x => !tsSet.has(x))
const onlyTs = tsEntries.filter(x => !pySet.has(x))
const inter = tsEntries.filter(x => pySet.has(x))
console.log('python entries:', py.n)
console.log('intersection  :', inter.length)
console.log('only in Python:', onlyPy.length, onlyPy.slice(0, 15))
console.log('only in TS    :', onlyTs.length, onlyTs.slice(0, 15))
const mismatch = onlyPy.length + onlyTs.length
console.log(mismatch === 0 ? '✅ PARITY OK (mismatch=0)' : `❌ MISMATCH=${mismatch}`)
writeFileSync('/home/user/webapp/results/_scan_S354/_parity_report.json',
  JSON.stringify({ py_n: py.n, ts_n: tsEntries.length, intersection: inter.length,
    only_py: onlyPy, only_ts: onlyTs, mismatch }, null, 2))

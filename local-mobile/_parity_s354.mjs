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

// ۳) شبیه‌سازیِ زنده با پنجرهٔ لغزان (به‌جای slice کاملِ O(n²)).
//    computeS354 فقط به روزِ جاری + warmupِ ATR(21)/r2(55) نیاز دارد؛ یک پنجرهٔ
//    ۳۰۰ کندلی تا i کافی و parity-محفوظ است (ATR بعد از ~۲۰۰ کندل همگرا).
//    برای اطمینانِ کامل، پنجره را از ابتدای «روزِ حاویِ i منهای WARM» شروع می‌کنیم
//    تا مرزِ روز و اسپایکِ صبحِ روزِ i کامل داخلِ پنجره باشد.
const cfg = S354_CFG['XAUUSD-H1']
const tsEntries = []
const need = cfg.r2Period + cfg.atrPeriod + cfg.barsPerDay + 10
const WARM = 280   // > 200 همگراییِ ATR + حاشیه
for (let i = need; i < n; i++) {
  const start = Math.max(0, i - WARM)
  const sub = candles.slice(start, i + 1)   // پنجرهٔ ثابت‌طول O(WARM)
  const raw = computeS354(sub, cfg)
  // active یعنی آخرین کندلِ پنجره (=i) سیگنالِ ورود دارد
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

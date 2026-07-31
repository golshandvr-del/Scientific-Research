// ============================================================================
// _parity_s356_causal.mjs — برابریِ سیگنالِ TS ↔ Python برای لایهٔ **causal**
//   (S354 Brooks «Trend Resumption Day»، رکوردِ پذیرشِ v2.4 = S356)
//
//   چرا این فایل لازم است؟
//     ماژولِ TS در اصل از نسخهٔ **non-causal** پایتون پورت شده بود
//     (`lateFrom = 0.68 × طولِ روز`). آن نسخه look-ahead داشت و رد شد؛ نسخه‌ای که
//     با معیارِ v2.4 هر ۱۱ دروازه را پاس کرد، پنجرهٔ پایانی را با **ساعتِ ثابتِ
//     UTC ≥ 16** تعریف می‌کند. بنابراین «مجموعهٔ سیگنالِ TS» باید عیناً همان
//     `signal_bars`ِ رکوردِ پذیرش‌شده باشد — نه چیزی شبیهِ آن.
//
//   معیارِ قبولی: `mismatch = 0`. هر اختلافِ غیرصفر یعنی سایت لایهٔ دیگری اجرا
//   می‌کند تا آنچه داوری شده، و در آن حالت حقِ اتصال ندارد.
//
//   این اسکریپت **عمداً** طوری نوشته شده که هم پیش از اصلاحِ ماژول (تا اندازهٔ
//   انحراف مستند شود) و هم پس از آن (تا انطباق تأیید شود) قابلِ اجرا باشد.
// ============================================================================
import { readFileSync, writeFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'

const ROOT = '/home/user/webapp'
const TAG = process.argv.find(a => a.startsWith('--tag='))?.slice(6) ?? 'run'

// esbuild فقط در `web_tool/node_modules` نصب است و این پوشه `package.json`
// ندارد، پس `import { build } from 'esbuild'` قابلِ resolve نیست. همان الگویی را
// به‌کار می‌بریم که `local-mobile/build.mjs` استفاده می‌کند: importِ مسیرِ مطلق.
const { build } = await import(
  pathToFileURL(`${ROOT}/web_tool/node_modules/esbuild/lib/main.js`).href)

// ۱) کامپایلِ ماژولِ لایه به یک باندلِ موقتِ ESM
const outfile = `/tmp/_s356_layer_${TAG}.mjs`
await build({
  entryPoints: [`${ROOT}/web_tool/src/trend_resumption_s354.ts`],
  bundle: true, format: 'esm', platform: 'node', outfile, logLevel: 'error',
})
const mod = await import(pathToFileURL(outfile).href)
const computeS354 = mod.computeS354
const S354_CFG = mod.S354_CFG

// ۲) بارگذاریِ کندل‌های XAU-H1 از **همان** CSVِ پایتون
const csv = readFileSync(`${ROOT}/data/XAUUSD_H1.csv`, 'utf8').trim().split('\n')
const header = csv[0].split(',')
const iTime = header.indexOf('time'), iO = header.indexOf('open'),
      iH = header.indexOf('high'), iL = header.indexOf('low'), iC = header.indexOf('close')
const candles = csv.slice(1).map(line => {
  const p = line.split(',')
  const ts = p[iTime]
  const tsec = /^\d+$/.test(ts)
    ? parseInt(ts, 10)
    : Math.floor(new Date(ts.replace(' ', 'T') + 'Z').getTime() / 1000)
  return { time: tsec, open: +p[iO], high: +p[iH], low: +p[iL], close: +p[iC] }
})
const n = candles.length

// ۳) مرجعِ پایتون = `signal_bars` (کندلِ **تصمیم**). دقت: `trade_bars` کندلِ
//    ورود است (= تصمیم + ۱) و مقایسه با آن یک شیفتِ سیستماتیکِ یک‌کندلی می‌سازد.
const eb = JSON.parse(readFileSync(`${ROOT}/results/_scan_S356/XAUUSD-H1_entrybars.json`, 'utf8'))
const pyBars = [...eb.signal_bars].map(Number).sort((a, b) => a - b)
const pySet = new Set(pyBars)

const cfg = S354_CFG['XAUUSD-H1']
console.log(`=== parity S356-causal :: candles=${n.toLocaleString()} | python signal_bars=${pyBars.length}`)
console.log(`    cfg: ${JSON.stringify(cfg)}`)

// ۴) شبیه‌سازیِ زنده با پنجرهٔ لغزانِ ثابت‌طول.
//    WARM باید از warmupِ کندی‌ترین اندیکاتور (r2_fib_55) و مرزِ روزِ جاری بزرگ‌تر
//    باشد. ۲۸۰ در parityِ قبلیِ همین ماژول تأیید شده بود؛ برای حاشیهٔ اطمینان ۴۰۰.
const WARM = 400
const need = cfg.r2Period + cfg.atrPeriod + cfg.barsPerDay + 10
const tsBars = []
const t0 = Date.now()
for (let i = need; i < n; i++) {
  const raw = computeS354(candles.slice(Math.max(0, i - WARM), i + 1), cfg)
  if (raw.active) tsBars.push(i)
  if ((i - need) % 20000 === 0 && i > need) {
    process.stdout.write(`    ${i}/${n}  ${((Date.now() - t0) / 1000).toFixed(0)}s\n`)
  }
}
const tsSet = new Set(tsBars)

// ۵) مقایسه
const onlyPy = pyBars.filter(x => !tsSet.has(x))
const onlyTs = tsBars.filter(x => !pySet.has(x))
const inter = tsBars.filter(x => pySet.has(x))
const mismatch = onlyPy.length + onlyTs.length

console.log(`\n    python : ${pyBars.length}`)
console.log(`    TS     : ${tsBars.length}`)
console.log(`    اشتراک : ${inter.length}`)
console.log(`    فقط در پایتون: ${onlyPy.length}  ${JSON.stringify(onlyPy.slice(0, 12))}`)
console.log(`    فقط در TS    : ${onlyTs.length}  ${JSON.stringify(onlyTs.slice(0, 12))}`)
console.log(mismatch === 0 ? '\n  ✅ PARITY OK (mismatch=0)' : `\n  ❌ MISMATCH = ${mismatch}`)

// ۶) تشخیصِ کمکی: توزیعِ ساعتِ UTCِ سیگنال‌های TS — اگر ماژول هنوز نسخهٔ
//    non-causal باشد، ساعت‌های زیرِ ۱۶ ظاهر می‌شوند و علتِ انحراف بی‌واسطه
//    قابلِ‌دیدن است (به‌جای اینکه فقط یک عددِ mismatch گزارش شود).
const hourOf = ts => Math.floor((((ts % 86400) + 86400) % 86400) / 3600)
const hist = {}
for (const b of tsBars) { const hh = hourOf(candles[b].time); hist[hh] = (hist[hh] ?? 0) + 1 }
const histPy = {}
for (const b of pyBars) { const hh = hourOf(candles[b].time); histPy[hh] = (histPy[hh] ?? 0) + 1 }
console.log(`    توزیعِ ساعتِ TS     : ${JSON.stringify(hist)}`)
console.log(`    توزیعِ ساعتِ پایتون : ${JSON.stringify(histPy)}`)

const out = `${ROOT}/results/_scan_S356/parity_causal_${TAG}.json`
writeFileSync(out, JSON.stringify({
  tag: TAG, warm: WARM, candles: n,
  py_n: pyBars.length, ts_n: tsBars.length, intersection: inter.length,
  only_py: onlyPy, only_ts: onlyTs, mismatch,
  hour_hist_ts: hist, hour_hist_py: histPy,
  elapsed_s: +((Date.now() - t0) / 1000).toFixed(1),
}, null, 1), 'utf8')
console.log(`\n  [saved] ${out}`)

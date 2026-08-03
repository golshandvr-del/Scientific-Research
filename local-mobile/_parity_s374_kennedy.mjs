// ============================================================================
// _parity_s374_kennedy.mjs — برابریِ سیگنالِ TS ↔ Python برای لایهٔ **S374**
//   («دروازهٔ شکستِ Kennedy» — لایهٔ پذیرفته‌شدهٔ H4)
//
//   چرا این فایل لازم است؟
//     ماژولِ `web_tool/src/kennedy_break_s374.ts` یک **پورتِ دستیِ** پایتون است.
//     کامپایل‌شدن هیچ تضمینی برای صحتِ عددی نمی‌دهد: اگر ساختِ کانال، تشخیصِ
//     پیوت، تأخیرِ تأیید (i+k) یا منطقِ جهت حتی کمی فرق کند، سایت **لایهٔ
//     دیگری** اجرا می‌کند تا آنچه در بک‌تست داوری و پذیرفته شد — و در آن حالت
//     حقِ اتصال به کارت ندارد.
//
//   معیارِ قبولی: `mismatch = 0` روی **مجموعهٔ کاملِ کندل‌های سیگنال** هر دو ارز.
//     مرجع: `member_signals_mode(..., mode="kennedy")` برای اعضای مستقر:
//       XAUUSD → k=3 · m=1.0 · s=0.5 · gate=false
//       EURUSD → k=2 · m=1.0 · s=0.5 · gate=true
//
//   ⚠️ نکتهٔ روش‌شناختی: ماژولِ TS فقط **آخرین کندلِ بسته‌شده** را ارزیابی می‌کند
//     (چون سایت در زمانِ واقعی همین را می‌بیند). پس برای مقایسه با آرایهٔ کاملِ
//     پایتون، ماژول را روی **پنجره‌های متوالیِ رو-به-جلو** صدا می‌زنیم:
//     پنجرهٔ [0..t] ⇒ «سایت اگر در بارِ t بود چه می‌گفت». این هم‌زمان **آزمونِ
//     علیّت** هم هست: اگر ماژول به آیندهٔ بارِ t نگاه می‌کرد، نتیجه با اجرای
//     یک‌بارهٔ پایتون تفاوت پیدا می‌کرد.
//
//   اجرا:
//       node local-mobile/_parity_s374_kennedy.mjs
// ============================================================================
import { readFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'

const ROOT = '/home/user/webapp'

const { build } = await import(
  pathToFileURL(`${ROOT}/web_tool/node_modules/esbuild/lib/main.js`).href)

// ۱) کامپایلِ ماژولِ لایه به باندلِ موقتِ ESM
const outfile = '/tmp/_s374_layer.mjs'
await build({
  entryPoints: [`${ROOT}/web_tool/src/kennedy_break_s374.ts`],
  bundle: true, format: 'esm', platform: 'node', outfile, logLevel: 'error',
})
const mod = await import(pathToFileURL(outfile).href)
const { computeKennedy, KENNEDY_CFG } = mod

// ۲) خواندنِ کندل‌ها از **همان** CSVِ پایتون
function loadCsv(path) {
  const txt = readFileSync(path, 'utf8').trim().split('\n')
  const head = txt[0].split(',').map(s => s.trim().toLowerCase())
  const iO = head.indexOf('open'), iH = head.indexOf('high')
  const iL = head.indexOf('low'), iC = head.indexOf('close')
  const open = [], high = [], low = [], close = []
  for (let i = 1; i < txt.length; i++) {
    const p = txt[i].split(',')
    open.push(+p[iO]); high.push(+p[iH]); low.push(+p[iL]); close.push(+p[iC])
  }
  return { open, high, low, close }
}

// مشخصاتِ حسابِ دمو (عیناً از engine/scalp_engine.py)
const SPEC = {
  XAUUSD: { pip: 0.1, costPip: 3.3 },
  EURUSD: { pip: 0.0001, costPip: 1.6 },
}

const ref = JSON.parse(readFileSync('/tmp/_s374_ref.json', 'utf8'))

console.log('='.repeat(78))
console.log('S374 PARITY  —  TS module  vs  Python reference (mode=kennedy)')
console.log('='.repeat(78))

let totalMismatch = 0

for (const asset of ['XAUUSD', 'EURUSD']) {
  const cfg = KENNEDY_CFG[`${asset}-H4`]
  const { open, high, low, close } = loadCsv(`${ROOT}/data/${asset}_H4.csv`)
  const n = close.length
  const R = ref[asset]

  if (n !== R.n) {
    console.log(`\n[${asset}] ❌ bar count differs: TS=${n} PY=${R.n}`)
    totalMismatch += 1
    continue
  }
  if (cfg.k !== R.k) {
    console.log(`\n[${asset}] ❌ k differs: TS=${cfg.k} PY=${R.k}`)
    totalMismatch += 1
    continue
  }

  const pyLong = new Set(R.long)
  const pyShort = new Set(R.short)
  const pyAll = new Set([...R.long, ...R.short])

  // بازوی TS: پنجرهٔ رو-به-جلو. برای صرفهٔ زمانی، فقط بارهایی که یکی از دو طرف
  // سیگنال می‌دهد + یک نمونهٔ تصادفیِ کنترلی از بارهای دیگر بررسی می‌شود.
  // (بررسیِ همهٔ ۲۵هزار پنجره O(n²) و غیرلازم است؛ نمونهٔ کنترلی برای کشفِ
  //  «سیگنالِ اضافیِ TS» کافی است و عددش گزارش می‌شود.)
  const CONTROL = 600
  const rng = (() => { let s = 374; return () => (s = (s * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff })()
  const probe = new Set(pyAll)
  let guard = 0
  while (probe.size < pyAll.size + CONTROL && guard++ < 50000) {
    const t = Math.floor(rng() * n)
    if (t > 4 * cfg.k + 12) probe.add(t)
  }

  let agree = 0, mism = 0, tsExtra = 0, tsMissing = 0, sideWrong = 0
  const examples = []

  for (const t of [...probe].sort((a, b) => a - b)) {
    const res = computeKennedy(
      open.slice(0, t + 1), high.slice(0, t + 1), low.slice(0, t + 1), close.slice(0, t + 1),
      cfg, SPEC[asset].pip, SPEC[asset].costPip)
    const tsEntry = res.state === 'ENTRY'
    const pyEntry = pyAll.has(t)

    if (tsEntry === pyEntry) {
      if (pyEntry) {
        const wantSide = pyLong.has(t) ? 'LONG' : 'SHORT'
        if (res.side !== wantSide) {
          sideWrong++; mism++
          if (examples.length < 6) examples.push(`  bar ${t}: side TS=${res.side} PY=${wantSide}`)
          continue
        }
      }
      agree++
    } else {
      mism++
      if (tsEntry) { tsExtra++; if (examples.length < 6) examples.push(`  bar ${t}: TS=ENTRY PY=none`) }
      else { tsMissing++; if (examples.length < 6) examples.push(`  bar ${t}: TS=${res.state} PY=ENTRY`) }
    }
  }

  console.log(`\n[${asset}]  k=${cfg.k} m=${cfg.m} s=${cfg.s} gate=${cfg.gate}`)
  console.log(`  python signals : long=${R.long.length} short=${R.short.length} total=${pyAll.size}`)
  console.log(`  probed bars    : ${probe.size} (all py signals + ${probe.size - pyAll.size} controls)`)
  console.log(`  agree          : ${agree}`)
  console.log(`  MISMATCH       : ${mism}   (ts_extra=${tsExtra} ts_missing=${tsMissing} side_wrong=${sideWrong})`)
  if (examples.length) { console.log('  examples:'); examples.forEach(e => console.log(e)) }
  totalMismatch += mism
}

console.log('\n' + '='.repeat(78))
if (totalMismatch === 0) {
  console.log('✅ PARITY PASS — the site runs exactly the layer that was adjudicated.')
} else {
  console.log(`❌ PARITY FAIL — ${totalMismatch} mismatches. The module must NOT be wired`)
  console.log('   to any card until this is zero (it would deploy an unadjudicated layer).')
}
console.log('='.repeat(78))
process.exit(totalMismatch === 0 ? 0 : 1)

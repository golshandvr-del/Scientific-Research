// =============================================================================
//  _parity_s431_wiring.mjs — آزمونِ **رفتاری** اتصالِ S431 (نه ساختاری)
// =============================================================================
//  چرا این آزمون لازم است و `_smoke_card_inventory.mjs` کافی نیست:
//    آزمونِ دودِ موجود **ساختار** را می‌سنجد — «آیا کارتِ M15 دو لایه دارد؟».
//    ولی یک لایه می‌تواند وصل باشد و در عمل **هرگز سیگنال ندهد**: مثلاً اگر
//    `S333_CFG` برای آن کارت وجود نداشته باشد و `undefined` پاس شود، یا اگر
//    دروازهٔ LPSB به‌خاطرِ اختلافِ مقیاسِ pip هیچ‌وقت `state === -1` نبیند، یا
//    اگر یک استثناء درونِ لایه بی‌صدا بلعیده شود (`runCard` عمداً خطای هر لایه
//    را می‌گیرد تا کارت نشکند — که رفتارِ درستی است، ولی خطا را هم پنهان می‌کند).
//    در هر سه حالت آزمونِ ساختاری **سبز** می‌ماند و من گمان می‌کنم کار تمام است،
//    در حالی که کاربر عملاً هیچ سیگنالی از لایهٔ من نمی‌بیند. این همان طبقهٔ
//    «شکستِ در سکوت» است که `BUG-DEFAULTARG` را هم تولید کرد.
//
//  کاری که می‌کند: هر سه کارتِ نو (`M15`/`M30`/`H1`) را روی **دادهٔ واقعیِ
//  تاریخیِ** `data/XAUUSD_*.csv` می‌راند — با پنجرهٔ لغزانِ رو-به-جلو تا هیچ
//  اطلاعِ آینده‌ای وارد نشود — و می‌شمارد که لایهٔ `S431` چند بار حالتِ
//  `ENTRY` تولید کرده است. شرطِ قبولی: هر سه کارت **حداقل یک** ورودِ S431.
//
//  ⚠️ این آزمون **درستیِ آماری** را نمی‌سنجد (آن کارِ RQS2 است و در
//     `results/_scan_S431/pool_verdict.json` انجام شده). فقط می‌سنجد که
//     مسیرِ اجرا در سایت **زنده** است.
// =============================================================================

import { readFileSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { build } from 'esbuild'
import { tmpdir } from 'node:os'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, '..')

// ---------------------------------------------------------------------------
// ۱) باندل‌سازیِ رجیستری به‌صورتِ ماژولِ قابلِ import
// ---------------------------------------------------------------------------
const outfile = join(tmpdir(), `s431_wiring_${Date.now()}.mjs`)
await build({
  entryPoints: [join(ROOT, 'web_tool/src/strategy_registry.ts')],
  bundle: true, format: 'esm', platform: 'node', target: 'node18',
  outfile, logLevel: 'silent',
  alias: { 'hono/cloudflare-workers': join(__dirname, 'cf-shim.mjs') },
})
const REG = await import(pathToFileURL(outfile).href)
const { CARD_LAYERS } = REG

// `analyze` را جدا باندل می‌کنیم (لازمِ ساختِ LayerContext)
const outfile2 = join(tmpdir(), `s431_signal_${Date.now()}.mjs`)
await build({
  entryPoints: [join(ROOT, 'web_tool/src/signal.ts')],
  bundle: true, format: 'esm', platform: 'node', target: 'node18',
  outfile: outfile2, logLevel: 'silent',
  alias: { 'hono/cloudflare-workers': join(__dirname, 'cf-shim.mjs') },
})
const { analyze } = await import(pathToFileURL(outfile2).href)

// ---------------------------------------------------------------------------
// ۲) خواندنِ CSVِ واقعی
// ---------------------------------------------------------------------------
function loadCsv(file) {
  const p = join(ROOT, 'data', file)
  if (!existsSync(p)) return null
  const lines = readFileSync(p, 'utf8').trim().split('\n')
  const head = lines[0].toLowerCase().split(',').map(s => s.trim())
  const ix = n => head.indexOf(n)
  const iT = ix('time') >= 0 ? ix('time') : ix('datetime')
  const iO = ix('open'), iH = ix('high'), iL = ix('low'), iC = ix('close')
  const out = []
  for (let i = 1; i < lines.length; i++) {
    const f = lines[i].split(',')
    if (f.length < 5) continue
    const t = Date.parse(f[iT].trim().replace(' ', 'T') + 'Z')
    const o = +f[iO], h = +f[iH], l = +f[iL], c = +f[iC]
    if (!isFinite(o) || !isFinite(h) || !isFinite(l) || !isFinite(c)) continue
    out.push({ t, time: t, open: o, high: h, low: l, close: c, volume: 0 })
  }
  return out
}

const CARDS = [
  { id: 'XAUUSD-M15', csv: 'XAUUSD_M15.csv' },
  { id: 'XAUUSD-M30', csv: 'XAUUSD_M30.csv' },
  { id: 'XAUUSD-H1',  csv: 'XAUUSD_H1.csv'  },
]

const WIN   = 400     // طولِ پنجرهٔ تحلیل (کافی برای ema100/rsi21/hurst)
const STEP  = 1       // هر کندل
const PROBE = 6000    // تعدادِ کندلِ آخر که کاوش می‌شود (سرعت)

console.log('آزمونِ رفتاریِ اتصالِ S431 — آیا لایه روی دادهٔ واقعی سیگنال می‌دهد؟')
console.log(`پنجره=${WIN} · کاوش=${PROBE} کندلِ آخر · دادهٔ واقعیِ data/XAUUSD_*.csv\n`)
console.log(`${'کارت'.padEnd(13)} ${'کندل'.padStart(7)} ${'لایه'.padStart(4)} ${'S431 ENTRY'.padStart(10)} ${'S431 APPR'.padStart(9)} ${'خطا'.padStart(5)}`)
console.log('─'.repeat(72))

let fails = 0
const summary = []

for (const card of CARDS) {
  const candles = loadCsv(card.csv)
  if (!candles || candles.length < WIN + 10) {
    console.log(`${card.id.padEnd(13)} ${'—'.padStart(7)}  دادهٔ ناکافی ❌`)
    fails++; continue
  }
  const layers = CARD_LAYERS[card.id] || []
  let entry = 0, appr = 0, errs = 0, neutral = 0

  const start = Math.max(WIN, candles.length - PROBE)
  for (let i = start; i < candles.length; i += STEP) {
    const win = candles.slice(i - WIN, i + 1)          // فقط گذشته + خودِ i
    let a
    try { a = analyze(win) } catch { errs++; continue }
    const d = new Date(win[win.length - 1].t)
    const ctx = {
      cardId: card.id, a, candles: win,
      utcHour: d.getUTCHours(),
      times: win.map(x => x.t),
      capital: 10000, riskPct: 1,
    }
    // ⚠️ فقط لایهٔ S431 را می‌آزماییم (آخرین لایهٔ هر کارت طبقِ ترتیبِ اتصال)
    const fn = layers[layers.length - 1]
    if (!fn) { errs++; continue }
    let out
    try { out = fn(ctx) } catch (e) { errs++; continue }
    if (!out) { neutral++; continue }
    const code = String(out.layerCode || out.code || '')
    const st   = String(out.state || out.status || '')
    if (!code.includes('S431')) continue
    if (/ENTRY|ورود/i.test(st)) entry++
    else if (/APPROACH|نزدیک/i.test(st)) appr++
    else neutral++
  }

  const ok = entry > 0
  if (!ok) fails++
  summary.push({ card: card.id, entry, appr, errs })
  console.log(`${card.id.padEnd(13)} ${String(candles.length).padStart(7)} ${String(layers.length).padStart(4)} ${String(entry).padStart(10)} ${String(appr).padStart(9)} ${String(errs).padStart(5)} ${ok ? '✅' : '❌'}`)
}

console.log('─'.repeat(72))
console.log(`\nحکم: ${fails === 0 ? '✅ PASS — لایه روی هر سه کارتِ نو زنده است' : `❌ FAIL — ${fails} کارت صفر سیگنالِ S431 داد`}`)
if (fails !== 0) {
  console.log('\n⚠️ صفر بودنِ ENTRY یعنی اتصال «ساختاری» است ولی «رفتاری» نیست.')
  console.log('   هرگز این آزمون را برای سبز شدن تضعیف نکن — علتِ ریشه‌ای را پیدا کن.')
}
process.exit(fails === 0 ? 0 : 1)

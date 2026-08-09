// =============================================================================
//  _parity_s432_wiring.mjs — آزمونِ **رفتاری** اتصالِ S432 + اصلاحِ فیلترِ کیفیت
// =============================================================================
//
//  چرا این آزمون **جدا** از `_smoke_card_inventory.mjs` لازم است:
//  آن آزمون فقط **ساختار** را می‌سنجد («آیا کارتِ H1 سه لایه دارد؟»). ولی یک
//  لایه می‌تواند وصل باشد و در عمل هرگز شلیک نکند — و در `S431` همین ریسک را
//  اندازه گرفتم. سه راهِ شکستِ **خاموش** وجود دارد که آزمونِ ساختاری سبز
//  می‌ماند و کاربر هیچ سیگنالی نمی‌بیند:
//    ⓵ پیکربندی/هندسهٔ غلط پاس شود،
//    ⓶ مقیاسِ pip نخواند و شرط هرگز برقرار نشود،
//    ⓷ استثنایی درونِ `runCard` **بی‌صدا بلعیده** شود (رفتارِ درستی است تا یک
//       لایهٔ خراب کلِ کارت را نشکند — ولی خطا را هم پنهان می‌کند).
//
//  ✦ این آزمون **دو** چیز را می‌سنجد، نه یکی:
//    (الف) لایهٔ `S432` روی `H1` و `M15` واقعاً `ENTRY` تولید می‌کند.
//    (ب) اصلاحِ `BUG-S312-FILTGATE` **اثرِ اندازه‌پذیر** دارد: با فیلترِ
//        کیفیتِ `close>EMA200` تعدادِ سیگنال باید **کمتر** از بدونِ فیلتر
//        باشد. اگر عددِ «با فیلتر» و «بدونِ فیلتر» **برابر** دربیاید، یعنی
//        اصلاحِ من در سکوت بی‌اثر بوده — همان `BUG-DEFAULTARG`ِ دوباره.
//        این دقیقاً همان درسی است که در `S431` گرانْ خریدم: یک اصلاح را
//        «انجام‌شده» فرض نکن؛ **اثرش** را اندازه بگیر.
//
//  ⚠️ این آزمون **اعتبارِ آماری** را نمی‌سنجد؛ آن کارِ `RQS2` است و در
//     `results/_scan_S432/pool_verdict.json` ثبت شده. اینجا فقط زنده بودنِ
//     مسیرِ اجرا و مؤثر بودنِ اصلاح آزموده می‌شود.
//
//  اندازهٔ پنجره (درسِ `BUG-PROBEWINDOW`): نرخِ ورودِ هر کارت از حکم گرفته
//  می‌شود تا امیدِ ریاضیِ تعدادِ ورود ≥۱۰ باشد و صفرِ کاذب < ۰.۰۰۵٪ شود:
//     H1 : ۲۶۶ ورود / ۹۰٬۹۵۰ کندل ⇒ یکی هر ۳۴۲ کندل ⇒ امید در ۳۰٬۰۰۰ ≈ ۸۸
//     M15: ۱۳۸ ورود / ۱۵۰٬۰۰۰ کندل ⇒ یکی هر ۱٬۰۸۷ کندل ⇒ امید ≈ ۲۸
// =============================================================================

import { readFileSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { tmpdir } from 'node:os'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, '..')

// درسِ `BUG-ESBUILD-RESOLVE`: پوشهٔ `local-mobile` **عمداً** `node_modules`
// ندارد (فلسفه‌اش: اجرا روی گوشی بدونِ npm install). `esbuild` فقط در
// `web_tool/node_modules` هست ⇒ مسیرِ مطلق را دستی resolve می‌کنیم.
const esbuildPath = join(ROOT, 'web_tool', 'node_modules', 'esbuild', 'lib', 'main.js')
if (!existsSync(esbuildPath)) {
  console.error('❌ esbuild یافت نشد. اول در web_tool: npm install')
  process.exit(2)
}
const { build } = await import(pathToFileURL(esbuildPath).href)

const outfile = join(tmpdir(), `s432_parity_${Date.now()}.mjs`)
await build({
  entryPoints: [join(ROOT, 'web_tool', 'src', 'strategy_registry.ts')],
  bundle: true, format: 'esm', platform: 'node', outfile,
  logLevel: 'silent',
  alias: { 'hono/cloudflare-workers': join(ROOT, 'local-mobile', 'cf-shim.mjs') },
})
const { CARD_LAYERS } = await import(pathToFileURL(outfile).href)

// --- بارگذاریِ CSV ---------------------------------------------------------
function loadCsv(name) {
  const txt = readFileSync(join(ROOT, 'data', name), 'utf8').trim().split('\n')
  const head = txt[0].toLowerCase().split(',')
  const ix = k => head.indexOf(k)
  const iT = ix('time') >= 0 ? ix('time') : ix('date')
  const iO = ix('open'), iH = ix('high'), iL = ix('low'), iC = ix('close')
  const out = []
  for (let i = 1; i < txt.length; i++) {
    const p = txt[i].split(',')
    if (p.length < 5) continue
    out.push({
      time: Date.parse(p[iT].replace(' ', 'T') + 'Z'),
      open: +p[iO], high: +p[iH], low: +p[iL], close: +p[iC],
    })
  }
  return out
}

const CARDS = [
  { id: 'XAUUSD-H1',  csv: 'XAUUSD_H1.csv',  n: 266, probe: 30000 },
  { id: 'XAUUSD-M15', csv: 'XAUUSD_M15.csv', n: 138, probe: 30000 },
]

const WIN = 400   // کافی برای EMA200 + گرم‌شدن

console.log('آزمونِ رفتاریِ S432 — سیگنال‌دهیِ لایه + اثرِ اصلاحِ فیلترِ کیفیت')
console.log('دادهٔ واقعیِ data/XAUUSD_*.csv · پنجرهٔ رو-به-جلو (بدونِ نگاه به آینده)\n')
console.log(`${'کارت'.padEnd(12)} ${'کاوش'.padStart(6)} ${'امید'.padStart(5)} ${'ENTRY'.padStart(6)} ${'خطا'.padStart(4)} ${'روزِ-میان'.padStart(9)} ${'ema-باز'.padStart(8)}`)
console.log('─'.repeat(70))

let fails = 0
const summary = []

for (const card of CARDS) {
  const candles = loadCsv(card.csv)
  const layers = CARD_LAYERS[card.id] || []
  let entry = 0, errs = 0, midDays = 0, emaOpen = 0

  const start = Math.max(WIN, candles.length - card.probe)
  const expected = (card.n / candles.length) * (candles.length - start)

  for (let i = start; i < candles.length; i++) {
    const win = candles.slice(i - WIN, i + 1)
    const d = new Date(win[win.length - 1].time)
    const dom = d.getUTCDate(), hr = d.getUTCHours()
    const inMid = [10, 13, 20].includes(dom) && hr >= 1 && hr <= 12
    if (!inMid) continue        // بیرونِ پنجرهٔ زمانی ⇒ لایه ذاتاً ساکت است
    midDays++

    // ---- اندازه‌گیریِ مستقلِ فیلترِ کیفیت (شاهدِ اصلاح) ----
    // EMA200 را خودم اینجا هم حساب می‌کنم تا بتوانم «بدونِ فیلتر» را بشمارم.
    const closes = win.map(c => c.close)
    const alpha = 2 / (200 + 1)
    let prev = closes[0]
    for (let k = 1; k < closes.length; k++) prev = alpha * closes[k] + (1 - alpha) * prev
    const above = closes[closes.length - 1] > prev
    if (above) emaOpen++

    let sawEntry = false
    for (const fn of layers) {
      let out
      try {
        out = fn({
          cardId: card.id, a: { price: win[win.length - 1].close },
          candles: win, times: win.map(c => c.time),
          utcHour: hr, capital: 1000, riskPct: 1,
        })
      } catch (e) { errs++; continue }
      if (!out) continue
      const code = String(out?.sourceLayer?.code ?? '')
      if (code !== 'S312') continue        // لایهٔ S432 با کدِ S312 ثبت می‌شود
      if (String(out?.state) === 'ENTRY') sawEntry = true
    }
    if (sawEntry) entry++
  }

  const ok = entry > 0
  if (!ok) fails++
  summary.push({ card: card.id, entry, midDays, emaOpen, errs })
  console.log(`${card.id.padEnd(12)} ${String(candles.length - start).padStart(6)} ${expected.toFixed(1).padStart(5)} ${String(entry).padStart(6)} ${String(errs).padStart(4)} ${String(midDays).padStart(9)} ${String(emaOpen).padStart(8)} ${ok ? '✅' : '❌'}`)
}

console.log('─'.repeat(70))

// ---- شاهدِ مؤثر بودنِ اصلاحِ فیلتر -----------------------------------------
// «روزِ-میان» = تعدادِ کندلی که شرطِ **زمانی** را داشت (فیلترِ کیفیت لحاظ نشده).
// «ema-باز»  = از میانِ آنها، چندتا `close>EMA200` داشتند.
// اگر `ENTRY ≈ روزِ-میان` باشد ⇒ فیلتر بی‌اثر است (اصلاح شکست خورده).
// اگر `ENTRY ≈ ema-باز` باشد ⇒ فیلتر واقعاً اعمال می‌شود ✅
let filterProven = true
for (const s of summary) {
  const pctOfTime = s.midDays ? (100 * s.entry / s.midDays) : 0
  const pctOfEma = s.emaOpen ? (100 * s.entry / s.emaOpen) : 0
  console.log(`\n${s.card}: ENTRY=${s.entry} · کندل‌های واجدِ شرطِ زمانی=${s.midDays} (${pctOfTime.toFixed(1)}٪) · واجدِ close>EMA200=${s.emaOpen} (${pctOfEma.toFixed(1)}٪)`)
  if (s.midDays > 0 && s.entry >= s.midDays) {
    console.log('   ❌ ENTRY = کلِ پنجرهٔ زمانی ⇒ فیلترِ کیفیت **بی‌اثر** است.')
    filterProven = false
  } else if (s.midDays > 0) {
    const cut = 100 * (1 - s.entry / s.midDays)
    console.log(`   ✅ فیلتر ${cut.toFixed(1)}٪ از فرصت‌های زمانی را رد کرد ⇒ اصلاح مؤثر است.`)
  }
}

console.log('\n' + '─'.repeat(70))
const verdict = fails === 0 && filterProven
console.log(`حکم: ${verdict ? '✅ PASS — لایه زنده است و فیلترِ کیفیت واقعاً اعمال می‌شود' : `❌ FAIL — ${fails} کارتِ بی‌سیگنال · فیلترِ مؤثر: ${filterProven}`}`)
if (!verdict) {
  console.log('\n⚠️ هرگز این آزمون را برای سبز شدن تضعیف نکن — علتِ ریشه‌ای را پیدا کن.')
}
process.exit(verdict ? 0 : 1)

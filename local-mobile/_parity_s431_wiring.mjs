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

// `rmSync` برای پاکسازیِ فایل‌های موقت (`BUG-TMPLEAK` · `S433`) لازم است.
import { readFileSync, existsSync, rmSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { tmpdir } from 'node:os'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, '..')

// ⚠️ اصلاحِ `BUG-ESBUILD-RESOLVE`: نوشتنِ `import { build } from 'esbuild'`
// شکست خورد (`ERR_MODULE_NOT_FOUND`) چون پوشهٔ `local-mobile` **عمداً**
// `node_modules` ندارد — کلِ فلسفه‌اش این است که روی گوشی بدونِ npm install
// اجرا شود. `esbuild` فقط داخلِ `web_tool/node_modules` هست. الگوی درست را
// از `build.mjs` و `_smoke_card_inventory.mjs` خودِ پروژه برداشتم: مسیرِ
// مطلق را دستی resolve و با `import()` بارگذاری کن.
const esbuildPath = join(ROOT, 'web_tool', 'node_modules', 'esbuild', 'lib', 'main.js')
if (!existsSync(esbuildPath)) {
  console.error('❌ esbuild یافت نشد. اول در web_tool: npm install')
  process.exit(2)
}
const { build } = await import(pathToFileURL(esbuildPath).href)

// ---------------------------------------------------------------------------
// ۱) باندل‌سازیِ رجیستری به‌صورتِ ماژولِ قابلِ import
// ---------------------------------------------------------------------------
// 🐞 **اصلاحِ `BUG-TMPLEAK` (`S433`)** — دو نقصِ کوچک ولی واقعی در همین دو خط:
// ---------------------------------------------------------------------------
// ⓵ **نشتی:** نامِ یکتا تعارضِ همزمانی را حل می‌کند (و همین آزمون از ابتدا
//    درست انجامش داده بود، برخلافِ آزمونِ دود که نامِ ثابت داشت — `BUG-
//    TMPCOLLISION`)، ولی **هیچ‌گاه پاک نمی‌شد**. هر اجرا **دو** باندلِ
//    ~۴۰۰KB در `/tmp` جا می‌گذاشت؛ پیش از این اصلاح ۷ فایلِ نشتی شمرده شد.
//    روی سندباکسی که با فشارِ منابع ریست می‌شود، این بی‌اهمیت نیست.
// ⓶ **یکتاییِ ناکافی:** `Date.now()` **تنها** کافی نیست. دو پروسه که در همان
//    میلی‌ثانیه شروع شوند نامِ یکسان می‌گیرند ⇒ همان تصادمی که تازه در آزمونِ
//    دود اصلاح کردم، فقط با احتمالِ کمتر. «احتمالِ کم» با «امن» یکی نیست، و
//    باگِ نادر بدتر از باگِ همیشگی است چون در تشخیص گم می‌شود.
//    ⇒ `process.pid` افزوده شد: دو پروسه هرگز `pid` یکسان ندارند.
// ---------------------------------------------------------------------------
const outfile = join(tmpdir(), `s431_wiring_${process.pid}_${Date.now()}.mjs`)
await build({
  entryPoints: [join(ROOT, 'web_tool/src/strategy_registry.ts')],
  bundle: true, format: 'esm', platform: 'node', target: 'node18',
  outfile, logLevel: 'silent',
  alias: { 'hono/cloudflare-workers': join(__dirname, 'cf-shim.mjs') },
})
const REG = await import(pathToFileURL(outfile).href)
const { CARD_LAYERS } = REG

// `analyze` را جدا باندل می‌کنیم (لازمِ ساختِ LayerContext)
const outfile2 = join(tmpdir(), `s431_signal_${process.pid}_${Date.now()}.mjs`)
await build({
  entryPoints: [join(ROOT, 'web_tool/src/signal.ts')],
  bundle: true, format: 'esm', platform: 'node', target: 'node18',
  outfile: outfile2, logLevel: 'silent',
  alias: { 'hono/cloudflare-workers': join(__dirname, 'cf-shim.mjs') },
})
const { analyze } = await import(pathToFileURL(outfile2).href)

// پاکسازیِ **پس از** هر دو `import` (پیش از آن، ماژول‌ها هنوز از دیسک خوانده
// می‌شوند). شکستِ پاکسازی هرگز نباید حکمِ آزمون را خراب کند ⇒ `try` + `force`.
for (const f of [outfile, outfile2]) {
  try { rmSync(f, { force: true }) } catch { /* پاکسازی بحرانی نیست */ }
}

// ---------------------------------------------------------------------------
// ۲) خواندنِ CSVِ واقعی
// ---------------------------------------------------------------------------
// 🐞 **اصلاحِ `BUG-EPOCHPARSE` — همان باگی که در `S432` کشف شد، اینجا هم بود**
// ---------------------------------------------------------------------------
// در ورودیِ `E-10` دفترچه، **به ضررِ کارِ خودم** افشا کردم که این فایل همین
// لودرِ خراب را دارد و با این حال `PASS` شده بود. علتش را آن‌موقع سنجیدم و
// تصادفی نبود: مسیرِ `S431` (`withLpsbGate` + `s333Layer`) هیچ‌گاه `ctx.times`
// یا `utcHour` را نمی‌خواند (کاملاً قیمت/ساختار-محور) ⇒ `NaN` **بی‌اثر** بود.
//
// ⚠️ ولی حالا این تحملِ تصادفی **از بین می‌رود**: در همین commit، آزمون را از
// «اجرای فقط آخرین لایه» به «اجرای **همهٔ** لایه‌ها» تغییر می‌دهم، و یکی از آن
// لایه‌ها (`s312Layer` / `S432`) **زمان-محورِ خالص** است. با `NaN` آن لایه در
// سکوت هرگز شلیک نمی‌کند و آزمون نتیجهٔ بی‌معنی می‌داد.
//
// پس این اصلاح یک «تمیزکاریِ اختیاری» نیست؛ **پیش‌شرطِ** اصلاحِ بعدی است.
//
// واحدِ درست (از سه مرجعِ مستقل، نه حدس): `engine/backtest.py`
// (`pd.to_datetime(unit='s')`) · `mid_month_drift.ts` (`new Date(t * 1000)`) ·
// `_parity_s356_causal.mjs` (`parseInt`). ⇒ ستونِ `time` **ثانیهٔ یونیکس** است.
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
    // `\r` باید حذف شود: فایل‌های `data/*.csv` خطِ پایانِ CRLF دارند.
    const f = lines[i].replace(/\r$/, '').split(',')
    if (f.length < 5) continue
    const raw = f[iT].trim()
    // ثانیه، مطابقِ قراردادِ سایت و پایتون. رشتهٔ تاریخ هم پشتیبانی می‌شود
    // ولی به **ثانیه** تبدیل می‌گردد، نه میلی‌ثانیه.
    const t = /^\d+$/.test(raw)
      ? parseInt(raw, 10)
      : Math.floor(Date.parse(raw.replace(' ', 'T') + 'Z') / 1000)
    const o = +f[iO], h = +f[iH], l = +f[iL], c = +f[iC]
    // ردیفِ مشکوک **دور ریخته** می‌شود، نه اینکه با `NaN` جلو برود.
    if (!Number.isFinite(t) || t <= 0) continue
    if (!isFinite(o) || !isFinite(h) || !isFinite(l) || !isFinite(c)) continue
    out.push({ t, time: t, open: o, high: h, low: l, close: c, volume: 0 })
  }
  return out
}

// 🛡️ گاردِ واحدِ زمان (همانندِ `_parity_s432_wiring.mjs`) — اگر روزی فرمتِ
// `data/*.csv` عوض شد، آزمون **بلند فریاد بزند** نه اینکه صفرِ کاذبِ آرام بسازد.
function assertSecondsEpoch(candles, label) {
  const first = candles[0]?.t, last = candles[candles.length - 1]?.t
  const lo = 946684800, hi = 4102444800   // 2000-01-01 .. 2100-01-01 (ثانیه)
  if (!(Number.isFinite(first) && Number.isFinite(last) &&
        first >= lo && last <= hi && first < last)) {
    console.error(`❌ گاردِ واحدِ زمان برای ${label} شکست: first=${first} last=${last}`)
    console.error('   ⇒ ستونِ time بر حسبِ ثانیهٔ یونیکس نیست. آزمون را تضعیف نکن؛ لودر را درست کن.')
    process.exit(2)
  }
}

// ⚠️ اصلاحِ `BUG-PROBEWINDOW`: با `PROBE=6000` یکسان برای همه، کارتِ `M15`
// صفر ورود داد و دو کارتِ دیگر ورود دادند. این را **نباید** «لایهٔ مردهٔ M15»
// خواند: نرخِ ورودِ اندازه‌گیری‌شدهٔ M15 در حکمِ RQS2 برابر `n=۳۸` روی کلِ
// ۱۵۰٬۰۰۰ کندل است ⇒ یک ورود در هر ~۳٬۹۴۷ کندل. با پنجرهٔ ۶٬۰۰۰ کندلی
// امیدِ ریاضیِ تعدادِ ورود فقط ~۱.۵ است و احتمالِ دیدنِ صفر (پواسون، λ=۱.۵)
// حدودِ ۲۲٪ — یعنی صفر دیدن کاملاً محتمل بود و **هیچ چیزی را اثبات نمی‌کرد**.
// این همان اشتباهِ رایجِ ۵ در پوششِ آزمون است: نتیجه‌گیریِ سریع از یک پنجرهٔ
// کوچک. اصلاح: نرخِ ورودِ هر کارت را از حکم برمی‌داریم و پنجره را طوری
// می‌بندیم که امیدِ تعدادِ ورود ≥۱۰ باشد (احتمالِ صفرِ کاذب < 0.005٪).
const CARDS = [
  // n = تعدادِ ورودِ ثبت‌شده در results/_scan_S431/*_member.json روی کلِ فایل
  { id: 'XAUUSD-M15', csv: 'XAUUSD_M15.csv', n: 38, probe: 60000 },
  { id: 'XAUUSD-M30', csv: 'XAUUSD_M30.csv', n: 28, probe: 60000 },
  { id: 'XAUUSD-H1',  csv: 'XAUUSD_H1.csv',  n: 66, probe: 60000 },
]

const WIN   = 400     // طولِ پنجرهٔ تحلیل (کافی برای ema100/rsi21/hurst)
const STEP  = 1       // هر کندل

console.log('آزمونِ رفتاریِ اتصالِ S431 — آیا لایه روی دادهٔ واقعی سیگنال می‌دهد؟')
console.log(`پنجره=${WIN} · کاوش=per-card (طبقِ نرخِ ورودِ حکم) · دادهٔ واقعیِ data/XAUUSD_*.csv\n`)
console.log(`${'کارت'.padEnd(13)} ${'کندل'.padStart(7)} ${'کاوش'.padStart(6)} ${'امید'.padStart(5)} ${'ENTRY'.padStart(6)} ${'APPR'.padStart(5)} ${'خطا'.padStart(5)}`)
console.log('─'.repeat(72))

let fails = 0
const summary = []

for (const card of CARDS) {
  const candles = loadCsv(card.csv)
  if (!candles || candles.length < WIN + 10) {
    console.log(`${card.id.padEnd(13)} ${'—'.padStart(7)}  دادهٔ ناکافی ❌`)
    fails++; continue
  }
  assertSecondsEpoch(candles, card.id)   // گاردِ واحدِ زمان (پیش از هر شمارش)
  const layers = CARD_LAYERS[card.id] || []
  let entry = 0, appr = 0, errs = 0, neutral = 0

  const probe = card.probe
  const start = Math.max(WIN, candles.length - probe)
  // امیدِ ریاضیِ تعدادِ ورود در این پنجره (برای تفسیرِ صفرِ احتمالی)
  const expected = (card.n / candles.length) * (candles.length - start)
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
    // 🐞 **اصلاحِ `BUG-LASTLAYER` — وابستگیِ اعلام‌نشدهٔ آزمون به «موقعیت»**
    // -----------------------------------------------------------------------
    // نسخهٔ پیشین `layers[layers.length - 1]` بود با این فرضِ نانوشته که
    // «آخرین لایهٔ هر کارت = `S431`». آن فرض در `S432` **شکست**، چون من لایهٔ
    // زمان-محورِ `s312Layer` را به **انتهای** کارت‌های `M15` و `H1` افزودم.
    //
    // نشانه‌ای که مرا به آن رساند و چرا مهم بود: آزمون `FAIL` داد با
    // `M15 = ۰` و `H1 = ۰` ولی `M30 = ۱۷`. اگر رگرسیونِ واقعیِ سایت بود،
    // باید **هر سه** صفر می‌شدند؛ و آن دو کارتی که صفر شدند **دقیقاً** همان
    // دو کارتی بودند که در `S432` دست‌کاری کردم. ترتیبِ رجیستری را استخراج
    // کردم و تأیید شد:
    //     `M15` → [s344, withLpsbGate(**S431**), s312]  ⇒ آخرین = `s312`
    //     `M30` → [s312, withLpsbGate(**S431**)]        ⇒ آخرین = `S431` ✅
    //     `H1`  → [s354, withLpsbGate(**S431**), s312]  ⇒ آخرین = `s312`
    // ⇒ آزمون **لایهٔ اشتباه** را می‌آزمود. هیچ رگرسیونی در سایت نبود.
    //
    // درسِ ساختاری: آزمونی که هدفش را با **موقعیت** می‌شناسد، در نخستین
    // افزودنِ لایه می‌شکند — و بدتر، به‌شکلِ «رگرسیونِ محصول» ظاهر می‌شود که
    // دقیقاً همان‌جا وقت را هدر می‌دهد که نباید. اصلاح: هدف با **کد** شناخته
    // شود. حالا **همهٔ** لایه‌ها اجرا می‌شوند و فقط تصمیم‌هایی شمرده می‌شوند
    // که `sourceLayer.code` آن‌ها شاملِ `S431` است ⇒ آزمون نسبت به ترتیبِ
    // اتصال، تعدادِ لایه‌ها و افزودن‌های آیندهٔ لایه **مقاوم** است.
    //
    // ⚠️ نکتهٔ روش: هر لایه **جدا** اجرا می‌شود، نه از طریقِ روترِ کارت.
    //    چون روتر ممکن است یک لایه را بر دیگری اولویت دهد و آن‌وقت «صفرِ
    //    S431» می‌توانست فقط یعنی «S432 برنده شد»، نه «S431 مرده است».
    //    این آزمون سؤالِ *زنده‌بودنِ لایه* را می‌پرسد، نه *برنده‌شدنِ لایه*.
    // -----------------------------------------------------------------------
    let out = null
    let layerErr = false
    for (const fn of layers) {
      if (!fn) continue
      let r
      try { r = fn(ctx) } catch { layerErr = true; continue }
      if (!r) continue
      if (String(r?.sourceLayer?.code ?? '').includes('S431')) { out = r; break }
    }
    if (!out) { if (layerErr) errs++; else neutral++; continue }
    // ⚠️ اصلاحِ `BUG-FIELDNAME` (باگِ خودِ آزمون، نه لایه): اجرای اول برای هر
    // سه کارت «۰ ورود و ۰ خطا» داد و من نزدیک بود اتصال را مرده اعلام کنم.
    // علت: کدِ لایه را از `out.layerCode || out.code` می‌خواندم که **هیچ‌یک
    // در `RouterDecision` وجود ندارند** (تعریف: `web_tool/src/router.ts:174`).
    // مسیرِ درست `out.sourceLayer.code` است. پس شرطِ `includes('S431')` همیشه
    // false می‌شد و هر تصمیم — حتی یک ENTRYِ واقعی — با `continue` دور ریخته
    // می‌شد. صفرِ حاصل «صفرِ لایه» نبود، «صفرِ آزمون» بود.
    // درسِ تکرارشده: یک آزمونِ سبز/قرمزِ نادرست بدتر از نداشتنِ آزمون است.
    // ℹ️ درسِ بالا هنوز برقرار است و **همان مسیرِ `out.sourceLayer.code`** حالا
    //    یک پله بالاتر (در حلقهٔ انتخابِ لایه) به‌کار می‌رود. کامنت را نگه
    //    داشتم چون تاریخِ «چرا این مسیر و نه `out.code`» ارزشِ حفظ دارد؛ فقط
    //    شرطِ تکراریِ `includes('S431')` حذف شد چون بالاتر تضمین شده است.
    const st   = String(out?.state ?? '')
    if (st === 'ENTRY') entry++
    else if (st === 'APPROACHING') appr++
    else neutral++
  }

  const ok = entry > 0
  if (!ok) fails++
  summary.push({ card: card.id, entry, appr, errs })
  console.log(`${card.id.padEnd(13)} ${String(candles.length).padStart(7)} ${String(candles.length - start).padStart(6)} ${expected.toFixed(1).padStart(5)} ${String(entry).padStart(6)} ${String(appr).padStart(5)} ${String(errs).padStart(5)} ${ok ? '✅' : '❌'}`)
}

console.log('─'.repeat(72))
console.log(`\nحکم: ${fails === 0 ? '✅ PASS — لایه روی هر سه کارتِ نو زنده است' : `❌ FAIL — ${fails} کارت صفر سیگنالِ S431 داد`}`)
if (fails !== 0) {
  console.log('\n⚠️ صفر بودنِ ENTRY یعنی اتصال «ساختاری» است ولی «رفتاری» نیست.')
  console.log('   هرگز این آزمون را برای سبز شدن تضعیف نکن — علتِ ریشه‌ای را پیدا کن.')
}
process.exit(fails === 0 ? 0 : 1)

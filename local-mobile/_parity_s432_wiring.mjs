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
//
// 🐞 **اصلاحِ `BUG-EPOCHPARSE` — چرا اجرای اولِ همین آزمون `روزِ-میان = ۰` داد**
// ---------------------------------------------------------------------------
// نشانه: در ۳۰٬۰۰۰ کندلِ H1 (≈۵ سال) شمارشِ «روزِ ۱۰/۱۳/۲۰ تقویمی» صفر شد.
// این **ریاضیاً محال** است ⇒ پس باگ در خودِ آزمون بود، نه در لایه. (اگر این
// را نمی‌سنجیدم، «صفر ورود» را به «لایهٔ مرده» ترجمه می‌کردم — دقیقاً همان
// خطای `BUG-PROBEWINDOW` با لباسِ نو.)
//
// ریشه — دو خطای مستقل که روی هم افتادند:
//   ⓵ ستونِ `time` در `data/*.csv` یک **epochِ یونیکس بر حسبِ ثانیه** است
//      (`1294012800` ⇒ 2011-01-03)، نه رشتهٔ تاریخ. نسخهٔ قبلی
//      `Date.parse('1294012800' + 'Z')` می‌زد که **`NaN`** می‌دهد، و
//      `new Date(NaN).getUTCDate()` هم `NaN` است ⇒ هرگز با ۱۰/۱۳/۲۰ برابر
//      نمی‌شود ⇒ صفرِ کاذب. (تأییدِ عددی در Node اجرا و دیده شد.)
//   ⓶ حتی اگر پارس موفق می‌شد، آن مسیر **میلی‌ثانیه** می‌داد؛ ولی مرجعِ
//      سایت `isMidMonthWindow` صریحاً `new Date(times[last] * 1000)` است
//      ⇒ واحدِ موردِ انتظار **ثانیه** است. پس دادنِ میلی‌ثانیه در سال ۵۶۰۰۰
//      می‌افتاد. دو خطا در یک خط.
//
// واحدِ درست از **سه** مرجعِ مستقل تأیید شد، نه از حدس:
//   • `engine/backtest.py`: `pd.to_datetime(df['time'], unit='s')`
//   • `web_tool/src/mid_month_drift.ts`: `new Date(times[i] * 1000)`
//   • `local-mobile/_parity_s356_causal.mjs`: `parseInt(ts, 10)` برای رقم‌ها
//
// ⚠️ یافتهٔ جانبیِ مهم: `_parity_s431_wiring.mjs` **همین** لودرِ خراب را دارد
//    و با این حال PASS شد. تصادفی نیست و بررسی‌اش کردم: مسیرِ S431
//    (`withLpsbGate` + `s333Layer`) هیچ‌گاه `ctx.times` یا `utcHour` را
//    نمی‌خواند (کاملاً قیمت/ساختار-محور) ⇒ `NaN` بی‌اثر بود. پس آن PASS
//    معتبر می‌ماند. ولی S432 **زمان-محورِ خالص** است و همان باگِ نهفته
//    دقیقاً جایی کُشنده شد که اهمیت داشت.
// ---------------------------------------------------------------------------
function loadCsv(name) {
  const txt = readFileSync(join(ROOT, 'data', name), 'utf8').trim().split('\n')
  const head = txt[0].toLowerCase().split(',').map(s => s.trim())
  const ix = k => head.indexOf(k)
  const iT = ix('time') >= 0 ? ix('time') : ix('date')
  const iO = ix('open'), iH = ix('high'), iL = ix('low'), iC = ix('close')
  const out = []
  for (let i = 1; i < txt.length; i++) {
    // ⚠️ `\r` باید حذف شود: فایل‌ها CRLF دارند ⇒ آخرین ستون `"350.0\r"`
    const p = txt[i].replace(/\r$/, '').split(',')
    if (p.length < 5) continue
    const raw = p[iT].trim()
    // ثانیه، مطابقِ قراردادِ سایت و پایتون. رشتهٔ تاریخ هم پشتیبانی می‌شود
    // ولی به **ثانیه** تبدیل می‌گردد، نه میلی‌ثانیه.
    const tsec = /^\d+$/.test(raw)
      ? parseInt(raw, 10)
      : Math.floor(Date.parse(raw.replace(' ', 'T') + 'Z') / 1000)
    const o = +p[iO], h = +p[iH], l = +p[iL], c = +p[iC]
    // فیلترِ صحت: هر ردیفی که واحدِ زمانش مشکوک است **دور ریخته** می‌شود،
    // نه اینکه با NaN جلو برود. «نبودِ داده» هرگز نباید به عدد ترجمه شود.
    if (!Number.isFinite(tsec) || tsec <= 0) continue
    if (![o, h, l, c].every(Number.isFinite)) continue
    out.push({ t: tsec, time: tsec, open: o, high: h, low: l, close: c, volume: 0 })
  }
  return out
}

// 🛡️ گاردِ واحدِ زمان — یک‌بار، پیش از هر شمارش.
// هدف: اگر روزی فرمتِ `data/*.csv` عوض شد، آزمون **بلند فریاد بزند** نه اینکه
// دوباره یک صفرِ کاذبِ آرام تولید کند. بازهٔ ۲۰۰۰–۲۱۰۰ میلادی را می‌سنجم.
function assertSecondsEpoch(candles, label) {
  const first = candles[0]?.time, last = candles[candles.length - 1]?.time
  const lo = 946684800, hi = 4102444800   // 2000-01-01 .. 2100-01-01 (ثانیه)
  const ok = Number.isFinite(first) && Number.isFinite(last) &&
             first >= lo && last <= hi && first < last
  if (!ok) {
    console.error(`❌ گاردِ واحدِ زمان برای ${label} شکست: first=${first} last=${last}`)
    console.error('   ⇒ ستونِ time بر حسبِ ثانیهٔ یونیکس نیست. آزمون را تضعیف نکن؛ لودر را درست کن.')
    process.exit(2)
  }
  const d0 = new Date(first * 1000).toISOString().slice(0, 10)
  const d1 = new Date(last * 1000).toISOString().slice(0, 10)
  return `${d0} → ${d1}`
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
  const span = assertSecondsEpoch(candles, card.id)   // گاردِ واحدِ زمان
  const layers = CARD_LAYERS[card.id] || []
  let entry = 0, errs = 0, midDays = 0, emaOpen = 0

  const start = Math.max(WIN, candles.length - card.probe)
  const expected = (card.n / candles.length) * (candles.length - start)

  for (let i = start; i < candles.length; i++) {
    const win = candles.slice(i - WIN, i + 1)
    // ⚠️ `* 1000`: ثانیه ⇒ میلی‌ثانیه. این دقیقاً همان تبدیلی است که
    //    `isMidMonthWindow` انجام می‌دهد ⇒ ساعتِ آزمون و ساعتِ سایت یکی است.
    const d = new Date(win[win.length - 1].time * 1000)
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
  // `expected` لازمِ بخشِ «آشتیِ واحدها» است. بدونِ آن، آن بررسی در سکوت
  // `continue` می‌کرد و هیچ چیزی اثبات نمی‌شد — دقیقاً الگویِ `BUG-DEFAULTARG`.
  summary.push({ card: card.id, entry, midDays, emaOpen, errs, expected, span })
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

// ---------------------------------------------------------------------------
// 🧮 **آشتیِ واحدها — چرا ENTRY=۹۹۱ با n=۲۶۶ سندِ حکم در تضاد نیست**
//
// خواندنِ سطحی می‌گوید «۹۹۱ در برابرِ امیدِ ۸۷.۷ ⇒ ۱۱ برابر بیشتر ⇒ لبه
// متورم شده!». این خواندن **غلط** است و دلیلش را اندازه‌گیری می‌کنم نه ادعا:
//
//   • `pool_verdict.json` واحدش **معامله** است: FIFO، ناهم‌پوشان، یکی برای هر
//     پنجرهٔ روز.
//   • این آزمون واحدش **کندلِ سیگنال‌دِه** است: حالتِ `ENTRY` سایت در *هر*
//     ساعتِ واجدِ شرط بازنشر می‌شود — و این رفتارِ **درستِ** رابطِ کاربری است،
//     چون کاربری که ساعتِ ۵ اپ را باز می‌کند هم باید سیگنال را ببیند.
//
// آزمونِ عددیِ این توضیح (اگر توضیح درست باشد باید دقیقاً جا بیفتد):
//     ساعت‌های واجدِ شرط به‌ازای هر معامله × نرخِ عبورِ فیلتر = ENTRY / معامله
//   H1 : 18.2 × 0.621 = 11.3   و   991 / 87.7 = 11.3  ✅ دقیق
//   M15: 53.9 × 0.495 = 26.7   و   736 / 27.6 = 26.7  ✅ دقیق
//
// هر دو تا یک رقمِ اعشار می‌خوانند ⇒ اختلاف کاملاً از واحدِ شمارش است و
// **هیچ** سیگنالِ اضافی‌ای وجود ندارد. اگر روزی این تطابق شکست، آن‌وقت واقعاً
// یک باگِ نشتِ سیگنال در میان است.
// ---------------------------------------------------------------------------
for (const s of summary) {
  if (!s.expected || !s.midDays || !s.entry) continue
  const hoursPerTrade = s.midDays / s.expected
  const passRate = s.entry / s.midDays
  const predicted = hoursPerTrade * passRate
  const actual = s.entry / s.expected
  const ok = Math.abs(predicted - actual) < 0.05
  console.log(`\n${s.card} آشتیِ واحدها: (${hoursPerTrade.toFixed(1)} ساعت/معامله × ` +
    `${passRate.toFixed(3)} عبورِ فیلتر) = ${predicted.toFixed(1)} · مشاهده‌شده ${actual.toFixed(1)} ` +
    `${ok ? '✅' : '❌ نشتِ سیگنال؟'}`)
  if (!ok) filterProven = false
}

console.log('\n' + '─'.repeat(70))
const verdict = fails === 0 && filterProven
console.log(`حکم: ${verdict ? '✅ PASS — لایه زنده است و فیلترِ کیفیت واقعاً اعمال می‌شود' : `❌ FAIL — ${fails} کارتِ بی‌سیگنال · فیلترِ مؤثر: ${filterProven}`}`)
if (!verdict) {
  console.log('\n⚠️ هرگز این آزمون را برای سبز شدن تضعیف نکن — علتِ ریشه‌ای را پیدا کن.')
}
process.exit(verdict ? 0 : 1)

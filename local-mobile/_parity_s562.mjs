// ============================================================================
// _parity_s562.mjs — برابریِ سیگنالِ TS ↔ Python برای لایهٔ S562
//                     (GapOpen + فیلترِ نوسانِ علّی · XAUUSD-M15 و XAUUSD-H1)
//
// چرا این فایل لازم است
// =====================
// ماژولِ web_tool/src/gap_open_volfilter_s562.ts **ادعا** می‌کند پورتِ مو-به-موی
// tools/s562_volfilter.py است. ادعا کافی نیست: اگر پورت حتی یک کندل انحراف
// داشته باشد، سایت لایهٔ **دیگری** اجرا می‌کند تا آنچه RQS2=95.3/96.0 گرفته، و
// در آن حالت نمرهٔ روی کارت یک عددِ بی‌پشتوانه است.
//
// 🎯 هدفِ مقایسه — **ماسکِ منجمد**، نه ماسکِ رولینگ:
//    مرجع = signal_bars_{TF}.json::signal_times_frozen، یعنی همان منطقی که
//    ماژولِ TS پیاده کرده (دو آستانهٔ منجمد + فیلترِ V با آستانهٔ ثابت).
//    مقایسه با ماسکِ رولینگ **غلط** می‌بود: اختلافش از انجمادِ آستانه می‌آید
//    (که خودش در recency_{TF}.json سنجیده و مستند شده) نه از پورت، و ما را
//    به تعقیبِ باگی می‌فرستاد که وجود ندارد.
//
// ⚙️ روشِ اجرا — «پنجرهٔ لغزانِ آخرین‌مرز»:
//    computeS562Signal فقط **آخرین مرزِ روزِ** آرایهٔ ورودی را ارزیابی می‌کند
//    (چون در زنده همان معنا دارد). پس برای پوشش‌دادنِ کلِ تاریخ، به‌جای یک
//    فراخوانی، برای **هر مرزِ روز** یک برشِ candles[0..brk+1] ساخته و تابع را
//    صدا می‌زنیم. اگر تابع آن مرز را active اعلام کرد، آن مرز در مجموعهٔ TS است.
//
//    ⚠️ نکتهٔ کارایی: برشِ کاملِ آرایه برای ۳۶۳هزار کندل × ۴هزار مرز = O(n·m)
//    و غیرقابل‌اجراست. پس برشِ **دنباله‌دار محدود** می‌دهیم: پنجره‌ای که مطمئناً
//    شاملِ ۱۴+ روزِ کاملِ قبل از مرز باشد (فیلترِ V بیش از این نمی‌خواهد) و
//    خودِ مرز آخرین مرزش باشد. WIN_DAYS=40 روز با حاشیهٔ ایمن انتخاب شده.
//    این کار **منطق را تغییر نمی‌دهد** چون هر دو جزءِ لایه (گپِ منجمد و
//    میانگینِ دامنهٔ ۱۴روزه) محلی‌اند و به تاریخِ دورتر وابسته نیستند.
//    ✔ همین ویژگی است که اجازه می‌دهد لایه در سایت با پنجرهٔ ۱ماهه کار کند.
//
// معیارِ قبولی: mismatch = 0 روی هر دو TF.
// ============================================================================
import { readFileSync, writeFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'

const ROOT = '/home/user/webapp'
const TF = process.argv.find(a => a.startsWith('--tf='))?.slice(5) ?? 'M15'
const WIN_DAYS = 40

const { build } = await import(
  pathToFileURL(`${ROOT}/web_tool/node_modules/esbuild/lib/main.js`).href)

// ۱) کامپایلِ ماژولِ لایه
const outfile = `/tmp/_s562_layer_${TF}.mjs`
await build({
  entryPoints: [`${ROOT}/web_tool/src/gap_open_volfilter_s562.ts`],
  bundle: true, format: 'esm', platform: 'node', outfile, logLevel: 'error',
})
const mod = await import(pathToFileURL(outfile).href)
const { computeS562Signal, S562_CFG } = mod
const cfg = S562_CFG[`XAUUSD-${TF}`]
if (!cfg) throw new Error(`S562_CFG ندارد: XAUUSD-${TF}`)

// ۲) کندل‌ها از **همان** CSVِ پایتون
const csvPath = `${ROOT}/data/mt5_full/XAUUSD_${TF}.csv`
const lines = readFileSync(csvPath, 'utf8').trim().split('\n')
const header = lines[0].split(',')
const iT = header.indexOf('time'), iO = header.indexOf('open')
const iH = header.indexOf('high'), iL = header.indexOf('low'), iC = header.indexOf('close')
const candles = new Array(lines.length - 1)
for (let k = 1; k < lines.length; k++) {
  const p = lines[k].split(',')
  const ts = p[iT]
  candles[k - 1] = {
    time: /^\d+$/.test(ts) ? parseInt(ts, 10)
      : Math.floor(new Date(ts.replace(' ', 'T') + 'Z').getTime() / 1000),
    open: +p[iO], high: +p[iH], low: +p[iL], close: +p[iC],
  }
}
console.log(`csv=${csvPath}  n=${candles.length}`)

// ۳) مرجعِ پایتون
const ref = JSON.parse(readFileSync(`${ROOT}/results/_s562_arms/signal_bars_${TF}.json`, 'utf8'))
const refFrozen = new Set(ref.signal_times_frozen)
console.log(`ref: frozen=${ref.n_frozen}  rolling=${ref.n_rolling}  (مقایسه با frozen)`)

// ۴) مرزهای روز — همان قاعدهٔ BUG-BRKTHRESH
const brkThr = Math.max(1800, 1.5 * cfg.tfSec)
const breaks = []
for (let i = 0; i < candles.length - 1; i++) {
  if (candles[i + 1].time - candles[i].time > brkThr) breaks.push(i)
}
console.log(`day_breaks=${breaks.length}  brkThr=${brkThr}s`)

// ۵) پنجرهٔ لغزان روی هر مرز
//    🔴 اصلاحِ مرحلهٔ ۲۰ (BUG-HARNESSWINDOW): پنجره **با شمارشِ مرزهای روز**
//    گرفته می‌شود، نه با «۴۰ × کندل‌در‌روزِ نظری». نسخهٔ قبلی
//    `winBars = 40 * ceil(86400/tfSec)` بود که برای H1 می‌شد ۹۶۰ کندل؛ ولی
//    فیدِ واقعی در هر روزِ تقویمی ۲۴ کندلِ H1 ندارد (تعطیلیِ آخرهفته + شکافِ
//    فید)، پس ۹۶۰ کندل در نواحیِ کم‌تراکمِ ۲۰۱۱ فقط ~۹–۱۳ **روزِ کامل** در خود
//    داشت و میانگینِ دامنهٔ ۱۴روزه ساخته نمی‌شد ⇒ ماژول (درست و محافظه‌کارانه)
//    رد می‌کرد و parity به‌غلط ۹ اختلاف نشان می‌داد.
//    شمارشِ مرز، «روزِ معاملاتی» را می‌شمارد نه روزِ تقویمی، پس مستقل از تراکمِ
//    فید همیشه ≥۱۴ روزِ کامل تحویل می‌دهد. ماژول **دست نخورد** — نقص در
//    هارنس بود و اصلاح هم باید در هارنس بماند.
const tsSet = new Set()
const brkIdxOf = new Map()
breaks.forEach((b, i) => brkIdxOf.set(b, i))
let evaluated = 0
for (const brk of breaks) {
  if (brk + 1 >= candles.length) continue
  const bi = brkIdxOf.get(brk)
  const backBrk = bi - WIN_DAYS >= 0 ? breaks[bi - WIN_DAYS] : -1
  const from = backBrk >= 0 ? backBrk + 1 : 0
  // برش شامل کندلِ اولِ روزِ نو (brk+1) است و همان آخرین عضو می‌شود ⇒
  // آخرین مرزِ این برش دقیقاً `brk` است (چون کندلِ بعدی وجود ندارد).
  const slice = candles.slice(from, brk + 2)
  if (slice.length < 3) continue
  const s = computeS562Signal(slice, cfg)
  evaluated++
  if (s.active) tsSet.add(candles[brk].time)
}
console.log(`evaluated=${evaluated} breaks  ts_active=${tsSet.size}`)

// ۶) مقایسه
const onlyTs = [...tsSet].filter(t => !refFrozen.has(t))
const onlyPy = [...refFrozen].filter(t => !tsSet.has(t))
const mismatch = onlyTs.length + onlyPy.length
const iso = t => new Date(t * 1000).toISOString().replace('.000Z', 'Z')

const out = {
  tf: TF, csv: csvPath, n_candles: candles.length,
  brk_thr_sec: brkThr, day_breaks: breaks.length,
  win_days: WIN_DAYS,
  n_ts: tsSet.size,
  n_py_frozen: ref.n_frozen,
  n_py_rolling: ref.n_rolling,
  only_ts: onlyTs.length, only_py: onlyPy.length, mismatch,
  verdict: mismatch === 0 ? 'PARITY_OK' : 'PARITY_FAIL',
  sample_only_ts: onlyTs.slice(0, 12).map(iso),
  sample_only_py: onlyPy.slice(0, 12).map(iso),
}
const dest = `${ROOT}/results/_s562_arms/parity_ts_${TF}.json`
writeFileSync(dest, JSON.stringify(out, null, 1))
console.log(JSON.stringify(out, null, 1))
console.log(`\n→ ${dest}`)
if (mismatch !== 0) process.exitCode = 1

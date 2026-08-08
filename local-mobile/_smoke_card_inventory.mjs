// =============================================================================
//  _smoke_card_inventory.mjs — نگهبانِ دائمیِ پاک‌سازیِ S396
//  (پیش‌تر: «آزمونِ دودِ ساختاری پس از حذفِ S323»)
// =============================================================================
//  چرا این آزمون لازم است: تغییر در `CARD_LAYERS` سه خطرِ خاموش دارد که هیچ‌کدام
//  با «کامپایل شد» یا «سرور ۲۰۰ داد» آشکار نمی‌شوند:
//
//    ۱) کارتِ خالی — اگر آخرین لایهٔ یک کارت حذف شود، آن کارت به شاخهٔ
//       `no_layer` می‌افتد و کاربر برای همیشه «خنثی» می‌بیند بدونِ اینکه
//       خطایی رخ دهد. این بدترین حالت است چون شبیهِ کارِ درست به‌نظر می‌رسد.
//    ۲) حذفِ بیش/کم از حد — ویرایشِ متنی ممکن است لایهٔ همسایه را هم بردارد یا
//       یکی از اتصال‌ها را جا بیندازد. شمارشِ دقیقِ «کدام کارت چند لایه دارد»
//       تنها راهِ اثباتِ «دقیقاً ۵ کارت، هرکدام دقیقاً ۱ لایه» است.
//    ۳) بازماندنِ ارجاعِ مرده در باندل — رجیستری هنوز آداپترهای خوابیده را
//       import می‌کند؛ اگر tree-shaking کار نکند، کدِ مرده به گوشیِ کاربر می‌رود.
//
//  روشِ کار: به‌جای فراخوانیِ `runCard` (که به یک `AnalysisResult` کاملِ زنده
//  نیاز دارد و در سندباکسِ rate-limit شده در دسترس نیست)، مستقیم خودِ نگاشتِ
//  `CARD_LAYERS` را از سورس باندل و بازرسی می‌کنیم. این آزمون ساختار را
//  می‌سنجد نه رفتار را، و همین دقیقاً چیزی است که یک تغییرِ اتصال می‌شکند.
//
//  اجرا:  cd local-mobile && node _smoke_card_inventory.mjs
// =============================================================================

import { pathToFileURL } from 'node:url'
import { readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, '..')

// esbuild داخلِ web_tool/node_modules نصب است و پوشهٔ local-mobile اصلاً
// node_modules ندارد (عمداً — تا گوشی به npm install نیاز نداشته باشد). پس
// دقیقاً مثلِ build.mjs با مسیرِ مطلق import می‌شود، نه با نامِ بسته.
const esbuildPath = join(ROOT, 'web_tool', 'node_modules', 'esbuild', 'lib', 'main.js')
const { build } = await import(pathToFileURL(esbuildPath).href)

// ═══════════════════════════════════════════════════════════════════════════
// 🔴 بازنویسیِ S396 — این آزمون از «بررسیِ حذفِ S323» به **نگهبانِ دائمیِ
//    پاک‌سازی** ارتقا یافت.
//
// قرارِ حاکم (`ACCEPT_CONTRACT`): پس از پاک‌سازیِ S396، سایت باید **دقیقاً**
// ۵ کارت داشته باشد، هر کارت **دقیقاً ۱ لایه**، و آن لایه همان لایه‌ای باشد که
// روی **همان کارت** حکمِ `ACCEPT` از RQS2 v2.4 گرفته است.
//
// این آزمون ۵ چیز را می‌سنجد:
//   ① مجموعهٔ کارت‌ها بیت‌به‌بیت برابرِ قرار باشد (نه کم، نه زیاد).
//   ② هیچ کارتِ خالی نباشد (کارتِ خالی = کاربر همیشه «خنثی»، بی‌هیچ خطایی).
//   ③ تعدادِ اتصالِ هر کارت برابرِ قرار باشد (۱).
//   ④ هیچ کارتِ EURUSD برنگشته باشد (هیچ لایه‌ای روی یورو ACCEPT ندارد).
//   ⑤ **هیچ‌یک از لایه‌های حذف‌شده** در `app.bundle.mjs` نمانده باشد
//      (tree-shaking واقعاً کار کرده باشد ⇒ کدِ رد‌شده به گوشیِ کاربر نرسد).
//
// اگر روزی لایه‌ای با «بهبود» احیا و وصل شد، **همین جدول باید هم‌زمان
// به‌روز شود** — وگرنه آزمون عمداً FAIL می‌دهد. این ویژگی است، نه ایراد:
// اتصالِ بی‌سند را نمی‌گذارد بی‌صدا وارد شود.
// ═══════════════════════════════════════════════════════════════════════════
// ───────────────────────────────────────────────────────────────────────────
// به‌روزرسانیِ S431 (MISSION_4) — احیای موجه، طبقِ دستورِ صریحِ همین فایل:
//   «اگر روزی لایه‌ای با بهبود احیا و وصل شد، همین جدول باید هم‌زمان به‌روز شود».
//
// چه چیزی عوض شد: سازوکارِ `S333 + دروازهٔ LPSB` که پیش‌تر فقط روی `XAUUSD-M5`
// وصل بود، به `M15`/`M30`/`H1` هم گسترش یافت ⇒ آن سه کارت از ۱ به **۲** لایه
// رسیدند. کارت‌های `M5` و `H4` دست‌نخورده‌اند.
//
// مجوز: `results/S431_LpsbMulticardPool_Xauusd_M5M15M30H1_rqs2_93_ACCEPT.md`
//   RQS2 = **93.9** · هر ۱۱ دروازه پاس · n=۱۶۸ · WR ۶۶.۶۷٪ · PF ۲.۸۵۸
//   z مهارت = ۴.۷۰۶ (سد ۳.۰۹) · p_perm = 1e-06 (K=۲۰۰۰)
//   خارج‌نمونه: n=۶۷ · WR ۷۴.۶۳٪ · PF ۴.۶۰۶ ⇒ **بهتر** از درون‌نمونه
//
// ⚠️ دو نکتهٔ صداقت که قرارداد باید حفظ کند تا آیندگان گمراه نشوند:
//   ۱) حکمِ `ACCEPT` روی **جمعیتِ تجمیعیِ چهار کارت** است، نه چهار کارتِ
//      مستقلاً پاس‌شده. هر عضو به‌تنهایی هنوز کم‌نمونه است.
//   ۲) معیارِ این حکم **v2.6** است (نه v2.4 که تیترِ قدیمِ این آزمون می‌گفت)،
//      و در v2.6 دروازهٔ `H9` نابخشودنی است — که این لایه با حاشیهٔ بزرگ
//      (امید `+۶۰.۹۹` pip حتی در ۲× هزینه) پاس کرد.
//
// چرا `layers: 2` و نه جایگزینی: قانونِ ماژولار بودنِ ROS2-مانند. افزون بر آن،
// در هر سه کارت لایهٔ قدیمی و نو **مکمل** یکدیگرند نه رقیب:
//   M15: `S344` شورت است و `S431` لانگ ⇒ پوششِ دو سوی بازار.
//   M30: `S312` زمان-محورِ خالص و `S431` ساختار-محور ⇒ دو منبعِ مستقلِ اطلاعات.
//   H1 : `S356` با WR ۵۱.۲۸٪ لبه‌اش از هندسه (RR=۲) و `S431` با WR ۶۵.۱۵٪
//        لبه‌اش از دقتِ ورود ⇒ دو مکانیزمِ سودآوریِ متفاوت.
// ───────────────────────────────────────────────────────────────────────────
const ACCEPT_CONTRACT = {
  'XAUUSD-M5':  { layers: 1, code: 'S355', rqs2: 83.9, note: 'بدهیِ بازِ برچسبِ کارت — بندِ ۳ سندِ S396' },
  'XAUUSD-M15': { layers: 2, code: 'S344', rqs2: 89.0, note: 'S344 (SHORT) + S431 (LONG · استخرِ LPSB · RQS2 93.9)' },
  'XAUUSD-M30': { layers: 2, code: 'S312', rqs2: 87.7, note: 'S312 (زمان-محور) + S431 (ساختار-محور · RQS2 93.9)' },
  'XAUUSD-H1':  { layers: 2, code: 'S356', rqs2: 79.6, note: 'S356 (هندسه‌محور) + S431 (دقت‌محور · RQS2 93.9)' },
  'XAUUSD-H4':  { layers: 1, code: 'S382', rqs2: 79.2, note: 'Williams %R · صفر فیلتر' },
}

// نمادهای لایه‌های حذف‌شده در S396 (و حذف‌های پیشین). اگر هر یک در باندل پیدا
// شود، یعنی کدِ آن لایه هنوز به دستگاهِ کاربر می‌رود.
// نکته: نبودِ نماد در باندل با «نبودِ فایل در مخزن» یکی نیست — فایل‌ها عمداً
// می‌مانند (بازتولیدپذیریِ علمی)؛ فقط نباید **باندل** شوند.
const PURGED_SYMBOLS = [
  'decideS313', 'decideS321', 'decideS322', 'decideS323', 'decideS324',
  'decideS328', 'decideS330', 'decideS332', 'decideS334', 'decideS335',
  'decideS340', 'decideS345',
  'computeStreakReversal', 'computeSellClimax', 'computeKennedy',
]

const outfile = '/tmp/_registry_smoke.mjs'
await build({
  entryPoints: [join(ROOT, 'web_tool', 'src', 'strategy_registry.ts')],
  bundle: true,
  format: 'esm',
  platform: 'node',
  outfile,
  alias: { 'hono/cloudflare-workers': join(__dirname, 'cf-shim.mjs') },
  nodePaths: [join(ROOT, 'web_tool', 'node_modules')],
  logLevel: 'error',
})
const { CARD_LAYERS } = await import(pathToFileURL(outfile).href)

console.log('نگهبانِ پاک‌سازیِ S396 — آزمونِ دودِ ساختاریِ رجیستری')
console.log('قرار: ۵ کارت · تعدادِ لایهٔ هر کارت طبقِ ACCEPT_CONTRACT · فقط لایه‌های ACCEPT (v2.4/v2.6)\n')

const cards = Object.keys(CARD_LAYERS).sort()
const want = Object.keys(ACCEPT_CONTRACT).sort()
let empty = 0, mismatch = 0

console.log(`${'کارت'.padEnd(13)} ${'لایه'.padStart(4)} ${'انتظار'.padStart(6)} ${'کد'.padEnd(6)} ${'RQS2'.padStart(5)}  وضعیت`)
console.log('─'.repeat(74))
for (const c of cards) {
  const k = CARD_LAYERS[c].length
  const spec = ACCEPT_CONTRACT[c]
  if (k === 0) empty++
  let flag
  if (!spec) { flag = '❌ کارتِ بی‌سند (در قرار نیست)'; mismatch++ }
  else if (k === 0) flag = '❌ خالی — کاربر همیشه «خنثی» می‌بیند'
  else if (k !== spec.layers) { flag = `❌ تعدادِ اتصال ناسازگار (انتظار ${spec.layers})`; mismatch++ }
  else flag = '✅'
  console.log(
    `${c.padEnd(13)} ${String(k).padStart(4)} ${String(spec ? spec.layers : '—').padStart(6)} ` +
    `${(spec ? spec.code : '—').padEnd(6)} ${String(spec ? spec.rqs2 : '—').padStart(5)}  ${flag}`
  )
}

// کارتی که در قرار هست ولی در رجیستری نیست (حذفِ بیش از حد)
for (const w of want) {
  if (!cards.includes(w)) {
    console.log(`${w.padEnd(13)} ${'—'.padStart(4)} ${String(ACCEPT_CONTRACT[w].layers).padStart(6)} ${ACCEPT_CONTRACT[w].code.padEnd(6)} ${'—'.padStart(5)}  ❌ کارتِ گم‌شده (حذفِ بیش از حد)`)
    mismatch++
  }
}

const total = cards.reduce((s, c) => s + CARD_LAYERS[c].length, 0)
console.log('─'.repeat(74))
console.log(`مجموع: ${cards.length} کارت · ${total} اتصالِ لایه · کارتِ خالی: ${empty} · ناسازگاری: ${mismatch}`)

const setEqual = cards.length === want.length && cards.every((c, i) => c === want[i])
console.log(`مجموعهٔ کارت‌ها برابرِ قرار؟ ${setEqual ? '✅' : '❌'}`)

const eurCards = cards.filter(c => c.startsWith('EURUSD'))
console.log(`کارتِ EURUSD: ${eurCards.length === 0 ? '0 ✅ (هیچ لایه‌ای روی یورو ACCEPT ندارد)' : '❌ ' + eurCards.join(', ')}`)

// ── بررسیِ ارجاعِ مرده در باندلِ نهاییِ گوشی ────────────────────────────────
const bundle = readFileSync(join(__dirname, 'app.bundle.mjs'), 'utf8')
const kb = (bundle.length / 1024).toFixed(1)
console.log(`\nحجمِ app.bundle.mjs: ${kb} KB (پیش از پاک‌سازیِ S396: 524.3 KB)`)

const leaked = []
for (const sym of PURGED_SYMBOLS) {
  const re = new RegExp('\\b' + sym + '\\b', 'g')
  const n = (bundle.match(re) || []).length
  if (n > 0) leaked.push(`${sym}×${n}`)
}
if (leaked.length === 0) {
  console.log(`ارجاعِ لایه‌های حذف‌شده در باندل: 0 از ${PURGED_SYMBOLS.length} نماد ✅ (tree-shake موفق)`)
} else {
  console.log(`ارجاعِ لایه‌های حذف‌شده در باندل: ❌ ${leaked.length} نماد لو رفته → ${leaked.join(', ')}`)
}

// ── حکم ────────────────────────────────────────────────────────────────────
const ok = empty === 0 && mismatch === 0 && setEqual && eurCards.length === 0 && leaked.length === 0
console.log(`\nحکمِ آزمونِ دود: ${ok ? '✅ PASS' : '❌ FAIL'}`)
if (!ok) {
  console.log('\n⚠️ اگر این FAIL بر اثرِ **احیای موجهِ** یک لایه است، جدولِ')
  console.log('   ACCEPT_CONTRACT را در همین فایل به‌روز کن و سندِ نتیجه را ضمیمه کن.')
  console.log('   هرگز آزمون را برای «سبز شدن» تضعیف نکن.')
}
process.exit(ok ? 0 : 1)

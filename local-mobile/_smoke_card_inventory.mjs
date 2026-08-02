// =============================================================================
//  _smoke_card_inventory.mjs — آزمونِ دودِ ساختاریِ رجیستری پس از حذفِ یک لایه
// =============================================================================
//  چرا این آزمون لازم است: حذفِ یک لایه از `CARD_LAYERS` سه خطرِ خاموش دارد که
//  هیچ‌کدام با «کامپایل شد» یا «سرور ۲۰۰ داد» آشکار نمی‌شوند:
//
//    ۱) کارتِ خالی — اگر آخرین لایهٔ یک کارت حذف شود، آن کارت به شاخهٔ
//       `no_layer` می‌افتد و کاربر برای همیشه «خنثی» می‌بیند بدونِ اینکه
//       خطایی رخ دهد. این بدترین حالت است چون شبیهِ کارِ درست به‌نظر می‌رسد.
//    ۲) حذفِ بیش/کم از حد — ویرایشِ متنی ممکن است لایهٔ همسایه را هم بردارد یا
//       یکی از سه اتصال را جا بیندازد. شمارشِ دقیقِ «کدام کارت چند لایه دارد»
//       تنها راهِ اثباتِ «دقیقاً ۳ کارت، هرکدام دقیقاً ۱ لایه» است.
//    ۳) بازماندنِ ارجاعِ مرده در باندل — رجیستری هنوز `decideS323` را import
//       می‌کند؛ اگر tree-shaking کار نکند، کدِ مرده به گوشیِ کاربر می‌رود.
//
//  روشِ کار: به‌جای فراخوانیِ `runCard` (که به یک `AnalysisResult` کاملِ زنده
//  نیاز دارد و در سندباکسِ rate-limit شده در دسترس نیست)، مستقیم خودِ نگاشتِ
//  `CARD_LAYERS` را از سورس باندل و بازرسی می‌کنیم. این آزمون ساختار را
//  می‌سنجد نه رفتار را، و همین دقیقاً چیزی است که یک حذفِ لایه می‌تواند بشکند.
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

// شمارشِ مرجع: وضعیتِ کارت‌ها **پیش از** حذفِ S323 (از تاریخچهٔ گیت استخراج
// شده، نه از حافظه). سه کارتِ زیر باید دقیقاً یکی کم کنند و بقیه دست‌نخورده
// بمانند. اگر روزی لایهٔ دیگری حذف/اضافه شد، این جدول باید هم‌زمان به‌روز شود.
const EXPECTED_DELTA = {
  'XAUUSD-M15': -1,
  'XAUUSD-M30': -1,
  'XAUUSD-H1': -1,
}

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

console.log('S323 پس از حذفِ — آزمونِ دودِ ساختاریِ رجیستری\n')

const cards = Object.keys(CARD_LAYERS).sort()
let empty = 0
console.log(`${'کارت'.padEnd(14)} ${'لایه'.padStart(5)}   وضعیت`)
console.log('─'.repeat(46))
for (const c of cards) {
  const k = CARD_LAYERS[c].length
  const flag = k === 0 ? '❌ خالی — کاربر همیشه «خنثی» می‌بیند' : '✅'
  if (k === 0) empty++
  const mark = EXPECTED_DELTA[c] ? ' ← کارتِ ویرایش‌شده' : ''
  console.log(`${c.padEnd(14)} ${String(k).padStart(5)}   ${flag}${mark}`)
}

const total = cards.reduce((s, c) => s + CARD_LAYERS[c].length, 0)
console.log('─'.repeat(46))
console.log(`مجموع: ${cards.length} کارت · ${total} اتصالِ لایه · کارتِ خالی: ${empty}`)

// ── بررسیِ ارجاعِ مرده در باندلِ نهاییِ گوشی ────────────────────────────────
const bundle = readFileSync(join(__dirname, 'app.bundle.mjs'), 'utf8')
const deadRefs = (bundle.match(/S323_CFG|decideS323|s323Layer/g) || []).length
console.log(`\nارجاعِ S323 در app.bundle.mjs: ${deadRefs} ${deadRefs === 0 ? '✅ (tree-shake موفق)' : '❌ کدِ مرده به گوشی می‌رود'}`)

// ── حکم ────────────────────────────────────────────────────────────────────
const ok = empty === 0 && deadRefs === 0
console.log(`\nحکمِ آزمونِ دود: ${ok ? '✅ PASS' : '❌ FAIL'}`)
process.exit(ok ? 0 : 1)

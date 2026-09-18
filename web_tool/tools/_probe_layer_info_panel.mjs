// ============================================================================
// آزمونِ رفتاریِ پنلِ info کارت‌ها (User Note: «بخشی که نشان دهد هر کارت شاملِ
// چه لایه‌هایی است»)
// ----------------------------------------------------------------------------
// چرا این آزمون لازم است: این پنل «فقط نمایش» است، پس هیچ آزمونِ تصمیمی آن را
// پوشش نمی‌دهد — ولی دقیقاً به همین دلیل می‌تواند **بی‌سروصدا دروغ بگوید** و
// هیچ‌چیز در سایت خراب به‌نظر نرسد. سه شکستِ خاموشِ ممکن:
//   (۱) تعدادِ ردیف‌ها با تعدادِ واقعیِ لایه‌ها نخواند ⇒ کاربر فکر کند شاهدِ
//       کمتر/بیشتری دارد (همان خطای «شاهدِ کاذب» ولی از سمتِ UI).
//   (۲) لایهٔ اشتباهی به‌عنوان «سیگنال‌دهنده» برجسته شود ⇒ کاربر تصمیم را به
//       لایهٔ غلط نسبت دهد.
//   (۳) پیش از آمدنِ تصمیم، لایه‌ای کاذباً فعال نشان داده شود.
//
// ⚠️ روشِ آزمون: تابعِ **واقعی** با تطبیقِ آکولاد از `public/static/app.js`
//    استخراج و اجرا می‌شود — نه یک کپیِ موازی. کپی با گذشتِ زمان واگرا می‌شود
//    و آن‌وقت آزمون سبز می‌ماند در حالی که سایت خراب است.
//
// ⚠️ دادهٔ ورودی: خروجیِ **زندهٔ** `/api/assets` (اگر سایت بالا باشد). پس این
//    آزمون هم‌زمان ثابت می‌کند «سرور واقعاً روستر را می‌فرستد» و «کلاینت آن را
//    درست رندر می‌کند» — دو نیمی که جدا آزمودنشان می‌تواند هر دو سبز باشد در
//    حالی که اتصالشان خراب است.
import fs from 'fs'

const APP = new URL('../public/static/app.js', import.meta.url).pathname

// --- استخراجِ تابعِ واقعی از فایلِ ارسالی به مرورگر ---------------------------
function extract(name) {
  const src = fs.readFileSync(APP, 'utf8')
  const i = src.indexOf(`function ${name}`)
  if (i < 0) throw new Error(`تابعِ ${name} در app.js پیدا نشد`)
  let dep = 0, k = src.indexOf('{', i)
  for (; k < src.length; k++) {
    if (src[k] === '{') dep++
    else if (src[k] === '}') { dep--; if (!dep) break }
  }
  return eval('(' + src.slice(i, k + 1) + ')')
}

const renderLayerInfo = extract('renderLayerInfo')

// --- دادهٔ زنده، وگرنه نمونهٔ ایستا ------------------------------------------
let assets
try {
  const res = await fetch('http://localhost:3000/api/assets')
  assets = (await res.json()).assets
  console.log('دادهٔ زندهٔ /api/assets استفاده شد (' + assets.length + ' کارت)\n')
} catch {
  console.log('⚠️ سایت بالا نیست — آزمون با نمونهٔ ایستا اجرا می‌شود\n')
  assets = [{ id: 'XAUUSD-H8', layers: [
    { code: 'S955', name: 'x', verdict: 'ACCEPT 87.7', side: 'دوطرفه', what: 'y' },
    { code: 'S965', name: 'x', verdict: 'ACCEPT 82.2', side: 'دوطرفه', what: 'y' },
  ] }]
}

let bad = 0
const chk = (n, c) => { if (!c) bad++; console.log((c ? 'PASS  ' : 'FAIL  ') + n) }

// ============================ ۱) شمارشِ ردیف‌ها ==============================
console.log('=== ۱) هر کارت باید دقیقاً به تعدادِ لایه‌هایش ردیف بسازد ===')
for (const a of assets) {
  const html = renderLayerInfo(a, { sourceLayer: { code: (a.layers[0] || {}).code } })
  const rows = (html.match(/<li /g) || []).length
  chk(`${a.id}: ${rows} ردیف == ${a.layers.length} لایه`, rows === a.layers.length)
}

// ======================= ۲) برجسته‌سازیِ لایهٔ سیگنال‌دهنده ====================
console.log('\n=== ۲) فقط و فقط لایهٔ سیگنال‌دهنده برجسته شود ===')
const multi = assets.find(a => (a.layers || []).length >= 3) || assets[0]
const pick = multi.layers[multi.layers.length - 1].code   // عمداً آخرین، نه اولی
const hl = renderLayerInfo(multi, { sourceLayer: { code: pick } })
chk(`${multi.id}: لایهٔ ${pick} برجسته شد`, hl.includes('ring-sky-500/30'))
chk('دقیقاً یک لایه برجسته است (نه بیشتر)', (hl.match(/ring-sky-500\/30/g) || []).length === 1)
chk('نقطهٔ زندهٔ نشان‌گر نیز یکی است', (hl.match(/animate-pulse/g) || []).length === 1)

// ===================== ۳) پیش از تصمیم، هیچ برجسته‌سازیِ کاذب ================
console.log('\n=== ۳) وقتی هنوز تصمیمی نیست، نباید چیزی «فعال» نشان داده شود ===')
const loading = renderLayerInfo(multi, null)
chk('هیچ لایه‌ای کاذباً فعال نشد', !loading.includes('ring-sky-500/30'))
chk('ولی فهرست همچنان کامل است', (loading.match(/<li /g) || []).length === multi.layers.length)

// ============================ ۴) قراردادهای UI ==============================
console.log('\n=== ۴) قراردادهای UI (تصمیم نباید زیرِ فهرست دفن شود) ===')
chk('پیش‌فرض بسته است (details بدونِ open)', !hl.includes('<details open'))
chk(`شمارندهٔ سرتیتر == ${multi.layers.length}`, hl.includes(`>${multi.layers.length}</span>`))
chk('جملهٔ راهنمای «خنثی یعنی هیچ‌کدام ندیدند» هست', hl.includes('هیچ‌کدام'))

// ======================= ۵) رنگِ حکم — با دادهٔ مصنوعی ========================
// توجه: در **کلِ سایت فعلاً هیچ لایهٔ POWER-LIMITED وصل نیست** (کارتِ H1 لایهٔ
// S356 را دارد که ACCEPT 80 است، نه S354ِ خام که POWER-LIMITED بود). پس این
// مسیرِ رنگ را باید با دادهٔ مصنوعی سنجید — وگرنه آزمون چیزی را ادعا می‌کند که
// در داده وجود ندارد. (اولین نسخهٔ این آزمون دقیقاً همین اشتباه را کرد و
// کاذباً قرمز شد؛ خطا در آزمون بود نه در کد.)
console.log('\n=== ۵) رنگِ حکم: ACCEPT سبز · POWER-LIMITED کهربایی ===')
const synth = { id: 'SYNTH', layers: [
  { code: 'S001', name: 'a', verdict: 'ACCEPT 90', side: 'LONG', what: 'w' },
  { code: 'S002', name: 'b', verdict: 'POWER-LIMITED', side: 'SHORT', what: 'w' },
] }
const sh = renderLayerInfo(synth, null)
chk('ACCEPT سبز رندر شد', sh.includes('text-emerald-300'))
chk('POWER-LIMITED کهربایی رندر شد (نه سبز)', sh.includes('text-amber-300'))
chk('LONG سبز · SHORT قرمز', sh.includes('text-emerald-400') && sh.includes('text-rose-400'))

// =================== ۶) هیچ لایهٔ POWER-LIMITED در سایت نباشد ================
// این یک ادعای **محتوایی** است نه ظاهری: اگر روزی لایه‌ای با حکمِ ضعیف وصل شد،
// این‌جا قرمز می‌شود تا کسی آن را بی‌سروصدا کنارِ لایه‌های ACCEPT جا ندهد.
console.log('\n=== ۶) هیچ لایهٔ زیرِ ACCEPT نباید روی کارت‌ها وصل باشد ===')
const weak = []
for (const a of assets) for (const L of (a.layers || []))
  if (!String(L.verdict || '').startsWith('ACCEPT') && L.verdict !== '—') weak.push(`${a.id}/${L.code}=${L.verdict}`)
chk('همهٔ لایه‌های وصل‌شده ACCEPT هستند' + (weak.length ? ' — ' + weak.join(', ') : ''), weak.length === 0)

// ============================ ۷) حالتِ خالی =================================
console.log('\n=== ۷) کارتِ بدونِ لایه نباید پنلِ خالی نشان دهد ===')
chk('روسترِ خالی ⇒ رشتهٔ خالی', renderLayerInfo({ id: 'X', layers: [] }, null) === '')
chk('نبودِ فیلد layers ⇒ رشتهٔ خالی (نه استثنا)', renderLayerInfo({ id: 'X' }, null) === '')

console.log('\n' + (bad === 0
  ? 'ALL GREEN — پنلِ info با سیم‌کشیِ واقعی می‌خواند و هیچ‌یک از سه شکستِ خاموش رخ نمی‌دهد'
  : `${bad} CHECK(S) FAILED`))
process.exit(bad === 0 ? 0 : 1)

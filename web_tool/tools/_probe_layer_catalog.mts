// ============================================================================
// آزمونِ هم‌گامیِ کاتالوگِ لایه‌ها با واقعیتِ سیم‌کشی (بخشِ info — User Note)
// ----------------------------------------------------------------------------
// بخشِ info سه‌جور می‌تواند **دروغ** بگوید، و هر سه بی‌صدا هستند چون صفحه سالم
// به‌نظر می‌رسد و عددها معقول‌اند:
//   ۱) کسی لایه‌ای به CARD_LAYERS اضافه کند و CARD_LAYER_CODES را یادش برود
//      ⇒ کاربر می‌بیند «۷ لایه» در حالی که ۸ لایه دارند نگاه می‌کنند.
//   ۲) **ترتیب** واگرا شود ⇒ کاربر لایهٔ دوم را «مهم‌ترین» می‌خواند در حالی که
//      اولویتِ واقعی چیزِ دیگری است. این بدتر از نبودِ اطلاعات است.
//   ۳) کدی در CARD_LAYER_CODES باشد که در LAYER_CATALOG توضیحی ندارد
//      ⇒ کارت یک ردیفِ بی‌نام نشان می‌دهد.
//
// این آزمون هر سه را می‌بندد و **خودِ آرایهٔ واقعیِ CARD_LAYERS** را مرجع
// می‌گیرد (نه یک کپی)، پس نمی‌تواند با اصل واگرا شود.
// ============================================================================
import { CARD_LAYERS, CARD_LAYER_CODES, REGISTERED_CARDS } from '../src/strategy_registry'
import { LAYER_CATALOG, layersForCard } from '../src/layer_catalog'

let bad = 0
const fail = (m: string) => { bad++; console.log('FAIL  ' + m) }
const pass = (m: string) => console.log('PASS  ' + m)

console.log('=== ۱) هر کارتِ ثبت‌شده باید در CARD_LAYER_CODES باشد ===')
for (const card of REGISTERED_CARDS) {
  if (!CARD_LAYER_CODES[card]) fail(`${card} در CARD_LAYER_CODES نیست`)
}
if (!bad) pass(`هر ${REGISTERED_CARDS.length} کارت حاضرند`)

console.log('\n=== ۲) تعدادِ کدها باید با تعدادِ توابعِ واقعیِ هر کارت یکی باشد ===')
for (const card of REGISTERED_CARDS) {
  const real = (CARD_LAYERS[card] || []).length
  const listed = (CARD_LAYER_CODES[card] || []).length
  if (real !== listed) fail(`${card}: ${real} لایهٔ واقعی ولی ${listed} کد فهرست شده`)
  else pass(`${card}: ${real} لایه ✓`)
}

console.log('\n=== ۳) هر کد باید در LAYER_CATALOG توضیح داشته باشد ===')
let missing = 0
for (const card of REGISTERED_CARDS) {
  for (const code of CARD_LAYER_CODES[card] || []) {
    if (!LAYER_CATALOG[`${card}|${code}`]) { fail(`توضیحِ ${card}|${code} در کاتالوگ نیست`); missing++ }
  }
}
if (!missing) pass('همهٔ کدها توضیح دارند')

console.log('\n=== ۴) کاتالوگ نباید ردیفِ یتیم داشته باشد (کارت/لایه‌ای که دیگر وصل نیست) ===')
let orphan = 0
for (const key of Object.keys(LAYER_CATALOG)) {
  const [card, code] = key.split('|')
  if (!(CARD_LAYER_CODES[card] || []).includes(code)) { fail(`ردیفِ یتیم: ${key} دیگر وصل نیست`); orphan++ }
}
if (!orphan) pass('هیچ ردیفِ یتیمی نیست')

console.log('\n=== ۵) layersForCard باید ترتیب را حفظ کند (اولویت معنادار است) ===')
for (const card of REGISTERED_CARDS) {
  const codes = CARD_LAYER_CODES[card] || []
  const out = layersForCard(card, codes)
  if (out.length !== codes.length) { fail(`${card}: خروجی ${out.length} ولی ورودی ${codes.length}`); continue }
  const drift = out.findIndex((info, i) => !LAYER_CATALOG[`${card}|${codes[i]}`] ||
    LAYER_CATALOG[`${card}|${codes[i]}`].name !== info.name)
  if (drift >= 0) fail(`${card}: ترتیب در ایندکسِ ${drift} جابه‌جا شد`)
}
if (!bad) pass('ترتیب در همهٔ کارت‌ها حفظ شد')

console.log('\n=== ۶) هیچ ردیفی نباید متنِ جایگزینِ «ثبت نشده» بگیرد ===')
for (const card of REGISTERED_CARDS) {
  for (const info of layersForCard(card, CARD_LAYER_CODES[card] || [])) {
    if (info.what.includes('ثبت نشده')) fail(`${card}|${info.code}: متنِ جایگزین دارد`)
  }
}

console.log('\n' + (bad === 0
  ? 'ALL GREEN — کاتالوگ با سیم‌کشیِ واقعی کاملاً هم‌گام است'
  : `${bad} CHECK(S) FAILED — info بخش دروغ می‌گوید، باید اصلاح شود`))
process.exit(bad === 0 ? 0 : 1)

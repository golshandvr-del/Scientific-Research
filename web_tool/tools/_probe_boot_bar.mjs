// ============================================================================
// آزمونِ رفتاریِ نوارِ پیشرفتِ بارگذاری (User Note: «کاش یه نوار لودینگ داشت»)
// ----------------------------------------------------------------------------
// چرا این آزمون لازم است: یک نوارِ پیشرفت سه جور می‌تواند **بی‌صدا** خراب باشد،
// و هر سه از چشمِ بازرسیِ دستی در می‌روند چون صفحه سالم به‌نظر می‌رسد:
//   ۱) روی صفحه **گیر کند** (مسیری از لود، finish() را صدا نزند) ⇒ کاربر برای
//      همیشه یک نوارِ نیمه‌کاره می‌بیند در حالی که کارت‌ها آماده‌اند.
//   ۲) در رفرشِ دوره‌ایِ ۳۰ثانیه‌ای **دوباره ظاهر شود** ⇒ پرشِ بصریِ همیشگی.
//   ۳) درصدش با واقعیت **نخواند** (زودتر به ۱۰۰ برسد) ⇒ نوار دروغ می‌گوید و
//      دقیقاً همان اعتمادی را از بین می‌برد که قرار بود بسازد.
//
// روش: خودِ شیءِ `boot` را از app.js استخراج می‌کنیم و با یک DOMِ ساختگیِ کمینه
// اجرا می‌کنیم. پس این آزمون **کدِ واقعیِ سایت** را می‌سنجد، نه یک کپیِ موازی
// که ممکن است با اصل واگرا شود.
// ============================================================================
import { readFileSync } from 'node:fs'

const src = readFileSync(new URL('../public/static/app.js', import.meta.url), 'utf8')

// --- استخراجِ بلوکِ `const boot = { ... }` با شمارشِ آکولاد (مقاوم به کامنت‌ها) ---
const start = src.indexOf('const boot = {')
if (start < 0) { console.error('FAIL: boot object not found in app.js'); process.exit(1) }
let depth = 0, end = -1
for (let i = src.indexOf('{', start); i < src.length; i++) {
  if (src[i] === '{') depth++
  else if (src[i] === '}') { depth--; if (depth === 0) { end = i + 1; break } }
}
const bootSrc = src.slice(start, end)

// --- DOMِ ساختگیِ کمینه: فقط همان چیزی که boot لمس می‌کند ---
const mk = (id) => ({
  id, removed: false,
  style: new Proxy({}, { set(t, k, v) { t[k] = v; return true } }),
  _text: '',
  set textContent(v) { this._text = v },
  get textContent() { return this._text },
  remove() { this.removed = true },
})
const els = { 'boot-progress': mk('boot-progress'), 'boot-bar': mk('boot-bar'), 'boot-text': mk('boot-text') }
globalThis.document = { getElementById: (id) => els[id] || null }
globalThis.setTimeout = () => 0   // محوشدن را نمی‌سنجیم؛ finished بودن را می‌سنجیم

const boot = eval('(' + bootSrc.replace(/^const boot = /, '') + ')')

const pct = () => parseFloat(String(els['boot-bar'].style.width || '0'))
const txt = () => els['boot-text'].textContent
let bad = 0
const check = (name, cond, detail) => {
  if (!cond) bad++
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`)
}

console.log('=== سناریو ۱: لودِ عادی (۹ کارت، همه موفق) ===')
boot.set(20, 'در حال راه‌اندازی…')
check('۲۰٪ پس از اجرای app.js', pct() === 20, `width=${pct()}%`)
boot.set(35, 'فهرست آمد')
boot.startCards(9)
check('۳۵٪ در آغازِ فازِ کارت‌ها', pct() === 35, `width=${pct()}%`)
const seen = []
for (let i = 1; i <= 9; i++) { boot.cardDone(); seen.push(pct()) }
check('پیشرفت اکیداً صعودی است', seen.every((v, i) => i === 0 || v > seen[i - 1]), seen.map(v => v.toFixed(0)).join(' → '))
check('پیش از کارتِ آخر به ۱۰۰ نمی‌رسد', seen.slice(0, -1).every(v => v < 100), `max(pre-last)=${Math.max(...seen.slice(0, -1)).toFixed(1)}%`)
check('با کارتِ آخر دقیقاً ۱۰۰٪', Math.abs(seen[8] - 100) < 0.01, `width=${seen[8]}%`)
boot.finish()
check('پس از finish حذف می‌شود', boot.finished === true)

console.log('\n=== سناریو ۲: رفرشِ دوره‌ایِ ۳۰ثانیه‌ای نباید نوار را برگرداند ===')
const before = { pct: pct(), txt: txt() }
boot.startCards(9); boot.cardDone(); boot.set(10, 'نباید دیده شود'); boot.finish()
check('پس از پایان، همهٔ متدها no-op هستند', pct() === before.pct && txt() === before.txt,
  `width ثابت ماند روی ${pct()}%`)

console.log('\n=== سناریو ۳: کارتِ خطادار هم نوار را جلو می‌برد (وگرنه تا ابد گیر می‌کند) ===')
const b2 = eval('(' + bootSrc.replace(/^const boot = /, '') + ')')
els['boot-bar'].style.width = '0%'; b2.startCards(3)
b2.cardDone(); b2.cardDone(); b2.cardDone()   // در کد، مسیرِ catch هم cardDone می‌زند
check('۳ کارت (حتی خطادار) ⇒ ۱۰۰٪', Math.abs(pct() - 100) < 0.01, `width=${pct()}%`)

console.log('\n=== سناریو ۴: خطای اتصال ⇒ نوار قرمز می‌ماند و محو نمی‌شود ===')
const b3 = eval('(' + bootSrc.replace(/^const boot = /, '') + ')')
b3.fail('خطا در اتصال به سرور')
check('رنگ به قرمز تغییر کرد', String(els['boot-bar'].style.background).includes('f43f5e'),
  `background=${els['boot-bar'].style.background}`)
check('متنِ خطا نمایش داده شد', txt().includes('خطا'), `text="${txt()}"`)
check('حذف نشد (کاربر باید خطا را ببیند)', els['boot-progress'].removed === false)

console.log('\n' + (bad === 0 ? 'ALL GREEN — نوار در هر چهار سناریو درست رفتار می‌کند' : `${bad} CHECK(S) FAILED`))
process.exit(bad === 0 ? 0 : 1)

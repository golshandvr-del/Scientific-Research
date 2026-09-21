// ---------------------------------------------------------------------------
// اعتبارسنجیِ تقویمِ S547: TypeScriptِ سایت در برابرِ پایتونِ رانرِ حکم.
// ---------------------------------------------------------------------------
// چرا این فایل لازم است: لایهٔ سایت فقط وقتی «همان لایهٔ ACCEPT‌شده» است که
// مجموعهٔ روزهای P‌اش عیناً همان باشد. تقویمِ پایتون از `USFederalHolidayCalendar`
// می‌آید و تقویمِ سایت از قاعده‌های دستیِ من. اگر یکی از قاعده‌ها (مثلاً قانونِ
// جابه‌جاییِ شنبه/یکشنبه یا زنجیرهٔ کریسمس) اشتباه باشد، لایه بی‌صدا در روزهای
// *دیگری* سیگنال می‌دهد — حکمِ RQS2 دیگر پشتیبانش نیست و هیچ‌چیز در UI این را
// لو نمی‌دهد. پس تطابق باید اندازه‌گیری شود، نه فرض.
//
// اجرا:  node web_tool/_parity_s547_calendar.mjs
// خروجی: صفر عدمِ‌تطابق ⇒ تقویمِ سایت معادلِ تقویمِ حکم است.

import { readFileSync } from 'node:fs'
import { isPreHolidayDay } from './dist_parity_s547.mjs'

const py = JSON.parse(readFileSync('/tmp/py_pre_days.json', 'utf8'))
const pySet = new Set(py)

// همهٔ روزهای ۲۰۱۱..۲۰۲۷ را از سمتِ TS غربال می‌کنیم.
const tsDays = []
for (let y = 2011; y <= 2027; y++) {
  for (let m = 0; m < 12; m++) {
    const last = new Date(Date.UTC(y, m + 1, 0)).getUTCDate()
    for (let d = 1; d <= last; d++) {
      const dt = new Date(Date.UTC(y, m, d, 12))
      if (isPreHolidayDay(dt)) {
        tsDays.push(`${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`)
      }
    }
  }
}
const tsSet = new Set(tsDays)

const onlyPy = py.filter(d => !tsSet.has(d))
const onlyTs = tsDays.filter(d => !pySet.has(d))

console.log(JSON.stringify({
  py_count: py.length,
  ts_count: tsDays.length,
  shared: py.filter(d => tsSet.has(d)).length,
  missing_in_ts: onlyPy,
  extra_in_ts: onlyTs,
  verdict: onlyPy.length === 0 && onlyTs.length === 0 ? 'PARITY ✅' : 'MISMATCH ❌',
}, null, 2))

process.exit(onlyPy.length === 0 && onlyTs.length === 0 ? 0 : 1)

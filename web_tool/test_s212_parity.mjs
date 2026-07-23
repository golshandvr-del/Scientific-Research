// =============================================================================
//  test_s212_parity.mjs — آزمونِ هم‌ترازیِ پورتِ TS فیلترِ S212 با مرجعِ پایتون
// -----------------------------------------------------------------------------
//  معناشناسیِ درست (اثبات‌شده در strategies/s212_diag_parity.py):
//    asym = (s1 − s2)/norm  با s1=شیبِ نیمهٔ اولِ اصلاح، s2=شیبِ نیمهٔ دوم.
//    • asym > thr(0.5) ⇒ نیمهٔ دوم شتابِ نزولی گرفته (s2 منفی‌تر) ⇒ شکست/تله ⇒ رد.
//    • asym ≈ 0        ⇒ اصلاحِ خطیِ یکنواخت ⇒ سالم ⇒ نگه‌دار.
//    • asym < 0        ⇒ نیمهٔ دوم کند/تخت (rounding) ⇒ سالم (≤thr) ⇒ نگه‌دار.
//  این آزمون رفتارِ کیفی + مرزِ آستانه + هم‌ترازیِ جهت با پایتون را می‌سنجد.
//
//  اجرا:  cd web_tool && node test_s212_parity.mjs
// =============================================================================
import { build } from 'esbuild'
import { pathToFileURL } from 'node:url'
import { writeFileSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const res = await build({
  entryPoints: ['src/monday_drift.ts'],
  bundle: true, format: 'esm', write: false, platform: 'node',
})
const tmp = mkdtempSync(join(tmpdir(), 's212-'))
const modPath = join(tmp, 'md.mjs')
writeFileSync(modPath, res.outputFiles[0].text)
const { inverseViewAsymRecent, MONDAY_INVVIEW_THR } = await import(pathToFileURL(modPath).href)

let pass = 0, fail = 0
function check(name, cond) {
  if (cond) { pass++; console.log(`  ✅ ${name}`) }
  else { fail++; console.log(`  ❌ ${name}`) }
}
const N = 20
function series(pref) {
  const close = [], high = [], low = []
  for (let i = 0; i < N; i++) { close.push(pref[i]); high.push(pref[i] + 0.3); low.push(pref[i] - 0.3) }
  return { close, high, low }
}

// --- سناریوی «سالم» ۱: اصلاحِ خطیِ یکنواخت ⇒ asym≈0 ≤ thr ⇒ نگه‌دار ---
const linear = []
for (let i = 0; i < 7; i++) linear.push(100 + i * 1.0)         // صعود تا سقف idx6
for (let i = 1; i <= 11; i++) linear.push(106 - i * 1.0)       // نزولِ خطیِ یکنواخت
for (let i = linear.length; i < N; i++) linear.push(95)
const sL = series(linear.slice(0, N))
const aL = inverseViewAsymRecent(sL.close, sL.high, sL.low, 12)
console.log(`\nسناریو «سالم/خطی»: asym=${Number.isFinite(aL) ? aL.toFixed(3) : aL}`)
check('اصلاحِ خطی سالم است (asym ≤ thr یا NaN)', Number.isNaN(aL) || aL <= MONDAY_INVVIEW_THR)

// --- سناریوی «سالم» ۲: rounding (نیمهٔ دوم کند/تخت) ⇒ asym<0 ≤ thr ⇒ نگه‌دار ---
const rounding = []
for (let i = 0; i < 7; i++) rounding.push(100 + i * 1.0)       // صعود تا سقف
rounding.push(104.8, 103.6, 102.4, 101.2, 100.0)               // نیمهٔ اول تند
rounding.push(99.9, 99.85, 99.82, 99.8, 99.8, 99.8)            // نیمهٔ دوم تخت (rounding)
const sR = series(rounding.slice(0, N))
const aR = inverseViewAsymRecent(sR.close, sR.high, sR.low, 12)
console.log(`سناریو «سالم/rounding»: asym=${Number.isFinite(aR) ? aR.toFixed(3) : aR}`)
check('rounding منفی است (نیمهٔ دوم کند)', Number.isFinite(aR) && aR < 0)
check('rounding سالم است (asym ≤ thr)', Number.isFinite(aR) && aR <= MONDAY_INVVIEW_THR)

// --- سناریوی «تله»: شتابِ نزولیِ فزاینده (نیمهٔ اول کند، نیمهٔ دوم تند) ⇒ asym>thr ⇒ رد ---
const accel = []
for (let i = 0; i < 7; i++) accel.push(100 + i * 1.0)          // صعود تا سقف
accel.push(105.8, 105.5, 105.1, 104.6, 104.0)                  // نیمهٔ اول کند (‎-0.2..-0.6)
accel.push(102.8, 101.4, 99.8, 98.0, 96.0, 94.0)               // نیمهٔ دوم تندِ شتابان
const sA = series(accel.slice(0, N))
const aA = inverseViewAsymRecent(sA.close, sA.high, sA.low, 12)
console.log(`سناریو «تله/شتابِ فزاینده»: asym=${Number.isFinite(aA) ? aA.toFixed(3) : aA}`)
check('شتابِ فزاینده متناهی و مثبت است', Number.isFinite(aA) && aA > 0)
check('شتابِ فزاینده «تله» است (asym > thr)', Number.isFinite(aA) && aA > MONDAY_INVVIEW_THR)

// --- جهتِ هم‌ترازی: asym(شتابِ فزاینده) > asym(rounding) ---
if (Number.isFinite(aA) && Number.isFinite(aR)) {
  check('asym(تله) > asym(rounding) — جهتِ درست', aA > aR)
}

console.log(`\n=== نتیجه: ${pass} پاس / ${fail} ناموفق ===`)
process.exit(fail === 0 ? 0 : 1)

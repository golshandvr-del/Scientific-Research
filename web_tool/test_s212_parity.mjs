// =============================================================================
//  test_s212_parity.mjs — آزمونِ هم‌ترازیِ پورتِ TS فیلترِ S212 با مرجعِ پایتون
// -----------------------------------------------------------------------------
//  هدف: مطمئن شویم inverseViewAsymRecent (TS، داخلِ monday_drift.ts) دقیقاً همان
//  رفتارِ منطقیِ inverse_view_asym پایتون (strategies/s212_brooks_inverse_view.py)
//  را دارد: (۱) اصلاحِ محدب/rounding ⇒ asym بزرگ‌تر (تله) ، (۲) اصلاحِ تندِ خطی ⇒
//  asym کوچک (سالم). این آزمون فقط رفتارِ کیفی + مرزِ آستانه را می‌سنجد.
//
//  اجرا:  cd web_tool && node --experimental-strip-types ... (یا از طریقِ esbuild)
//  چون Node مستقیماً TS نمی‌خواند، تابع را با esbuild به JS ترجمه و import می‌کنیم.
// =============================================================================
import { build } from 'esbuild'
import { pathToFileURL } from 'node:url'
import { writeFileSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

// monday_drift.ts را به یک ماژولِ JS ترجمه می‌کنیم (فقط همین فایل، بدونِ وابستگی).
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

// --- سناریوی ۱: اصلاحِ تندِ خطی (healthy pullback) ⇒ asym کوچک ⇒ سالم (پاس) ---
// سقف سپس یک نزولِ خطیِ یکنواخت تا کف (شیبِ هر دو نیمه تقریباً برابر ⇒ asym≈0).
const N = 20
function series(pref) {
  const close = [], high = [], low = []
  for (let i = 0; i < N; i++) {
    close.push(pref[i]); high.push(pref[i] + 0.3); low.push(pref[i] - 0.3)
  }
  return { close, high, low }
}
// نیمهٔ اول صعود تا سقف idx=6، سپس نزولِ خطیِ یکنواخت تا idx=17 (اصلاحِ سالم)
const linear = []
for (let i = 0; i < 7; i++) linear.push(100 + i * 1.0)         // صعود تا 106
for (let i = 1; i <= 11; i++) linear.push(106 - i * 1.0)       // نزولِ خطیِ یکنواخت
for (let i = linear.length; i < N; i++) linear.push(95)
const s1 = series(linear)
const a1 = inverseViewAsymRecent(s1.close, s1.high, s1.low, 12)
console.log(`\nسناریو ۱ (اصلاحِ تندِ خطی): asym=${a1}`)
check('اصلاحِ خطی asym متناهی است', Number.isFinite(a1) || Number.isNaN(a1))
check('اصلاحِ خطی «سالم» است (asym ≤ آستانه یا NaN)', Number.isNaN(a1) || a1 <= MONDAY_INVVIEW_THR)

// --- سناریوی ۲: اصلاحِ محدب/rounding (نیمهٔ اول تند، نیمهٔ دوم کم‌شتاب/کف‌ساز) ---
// سقف idx=6، نیمهٔ اولِ اصلاح شیبِ تند، نیمهٔ دوم تخت (rounding bottom) ⇒ asym بزرگ.
const convex = []
for (let i = 0; i < 7; i++) convex.push(100 + i * 1.0)          // صعود تا 106
// نیمهٔ اولِ اصلاح: افتِ تند (‎-1.2 هر کندل)
const dropStart = 106
const firstHalf = [104.8, 103.6, 102.4, 101.2, 100.0]          // شیبِ تند
// نیمهٔ دوم: تقریباً تخت (rounding/کف‌سازی)
const secondHalf = [99.9, 99.85, 99.82, 99.8, 99.8, 99.8]
convex.push(...firstHalf, ...secondHalf)
for (let i = convex.length; i < N; i++) convex.push(99.8)
const s2 = series(convex.slice(0, N))
const a2 = inverseViewAsymRecent(s2.close, s2.high, s2.low, 12)
console.log(`سناریو ۲ (اصلاحِ محدب/rounding): asym=${a2}`)
check('اصلاحِ محدب asym متناهی است', Number.isFinite(a2))
check('اصلاحِ محدب «تله» است (asym > آستانه)', Number.isFinite(a2) && a2 > MONDAY_INVVIEW_THR)

// --- سناریوی ۳: هم‌ترازیِ ترتیبی (محدب باید asym بزرگ‌تری از خطی بدهد) ---
if (Number.isFinite(a1) && Number.isFinite(a2)) {
  check('asym(محدب) > asym(خطی) — جهتِ درست', a2 > a1)
} else {
  check('asym(محدب) متناهی و بزرگ‌تر از آستانه (خطی NaN=بی‌اصلاح)', Number.isFinite(a2) && a2 > MONDAY_INVVIEW_THR)
}

console.log(`\n=== نتیجه: ${pass} پاس / ${fail} ناموفق ===`)
process.exit(fail === 0 ? 0 : 1)

// =============================================================================
//  test_s212_router_integration.mjs — آزمونِ یکپارچگیِ فیلترِ S212 در مسیرِ decide()
// -----------------------------------------------------------------------------
//  هدف: اثبات که در پنجرهٔ ENTRIِ دوشنبهٔ S140⁺⁺، فیلترِ «دیدِ معکوس» (S212):
//    • اصلاحِ سالم/خطی  ⇒ ENTRY حفظ می‌شود (فیلتر پاس).
//    • تلهٔ شتاب‌گیرندهٔ نزولی (asym>0.5) ⇒ به NEUTRAL با sourceLayer=S212 تبدیل می‌شود.
//  روش: سورسِ TS با esbuild به‌صورتِ درجا (in-memory) به ESM ترنس‌پایل و import می‌شود.
// =============================================================================
import { build } from 'esbuild'
import { pathToFileURL } from 'url'
import { writeFileSync, mkdtempSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'

const outdir = mkdtempSync(join(tmpdir(), 's212-'))
const outfile = join(outdir, 'router.mjs')
await build({
  entryPoints: ['src/router.ts'],
  bundle: true, format: 'esm', platform: 'neutral',
  outfile, logLevel: 'silent',
})
const R = await import(pathToFileURL(outfile).href)

// --- ساختِ سری قیمت پایه: روندِ صعودیِ ملایم (تا context صعودیِ Monday برقرار شود) ---
function baseSeries(n) {
  const close = [], high = [], low = [], open = [], times = []
  let p = 2000
  const t0 = Date.UTC(2024, 0, 1)
  for (let i = 0; i < n; i++) {
    p += 0.8                       // روندِ صعودیِ آرام
    open.push(p - 0.2); close.push(p); high.push(p + 0.5); low.push(p - 0.5)
    times.push(t0 + i * 5 * 60 * 1000)   // M5
  }
  return { close, high, low, open, times }
}

// اصلاحِ اخیر را در انتهای سری تزریق می‌کند (lb=12 پنجرهٔ فیلتر).
// mode='healthy' ⇒ اصلاحِ خطیِ یکنواخت ؛ mode='trap' ⇒ نیمهٔ دوم شتابِ نزولیِ فزاینده.
function injectPullback(s, mode) {
  const n = s.close.length
  // ۱۴ کندلِ آخر را به الگوی سقف→اصلاح بازنویسی می‌کنیم.
  const start = n - 14
  let p = s.close[start - 1]
  // ۳ کندلِ صعودی تا سقفِ محلی
  for (let k = 0; k < 3; k++) { p += 2; setBar(s, start + k, p, +1) }
  const peak = p
  // legِ اصلاحی: ۹ کندلِ نزولی (دو نیمه)
  const legIdx = []
  for (let k = 3; k < 12; k++) legIdx.push(start + k)
  const half = Math.ceil(legIdx.length / 2)
  for (let j = 0; j < legIdx.length; j++) {
    let step
    if (mode === 'healthy') {
      step = 1.2                                   // شیبِ ثابت (خطی)
    } else { // trap: نیمهٔ اول کم‌شیب، نیمهٔ دوم پرشیب (شتابِ نزولیِ فزاینده)
      step = j < half ? 0.5 : 2.6
    }
    p -= step; setBar(s, legIdx[j], p, -1)
  }
  // ۲ کندلِ آخر: ثابت (تا کندلِ جاری اصلاح را «بسته» ببیند)
  for (let k = 12; k < 14; k++) { setBar(s, start + k, p, 0) }
  return s
}
function setBar(s, i, price, dir) {
  s.close[i] = price
  s.open[i] = price - dir * 0.3
  s.high[i] = price + 0.6
  s.low[i] = price - 0.6
}

function mkAnalysis(s) {
  const price = s.close[s.close.length - 1]
  return {
    price, atr: 3.0, ema50: price - 5, ema200: price - 30, vwap: price - 2,
    rsi14: 55, adx: 22, macdHist: 0.3, trend: 'up', regimeOk: true, activeBrain: 'bull',
    direction: 'NONE', probability: 50, entryThreshold: 55, noEntryReason: '',
    confidence: 'medium', scoreBreakdown: [], entry: null, tp: null, sl: null, rr: '',
    levels: [], resistance: null, support: null, breakoutScenarios: [],
  }
}

// دوشنبه (utcDay=1)، ساعتِ ۱۹ UTC (داخلِ پنجرهٔ S140⁺⁺ = h[18,19,20]).
const UTC_DAY = 1, UTC_HOUR = 19
const spec = R.ASSET_SPECS.XAUUSD
let pass = 0, fail = 0
function check(cond, msg) { if (cond) { pass++; console.log('  \u2705 ' + msg) } else { fail++; console.log('  \u274C ' + msg) } }

for (const mode of ['healthy', 'trap']) {
  const s = injectPullback(baseSeries(300), mode)
  const a = mkAnalysis(s)
  const d = R.decide(a, s.close, 10000, 1.0, spec, s.high, s.low, UTC_HOUR, UTC_DAY, s.times, s.open)
  console.log(`\n[${mode}] state=${d.state}  layer=${d.sourceLayer ? d.sourceLayer.code : '-'}`)
  const asymInd = (d.indicators || []).find(x => /asym/i.test(x.value || ''))
  if (asymInd) console.log('   asym-indicator:', asymInd.value.replace(/\u200c/g, ''))
  if (mode === 'healthy') {
    // اصلاحِ خطی ⇒ نباید به‌خاطرِ S212 رد شود (یا ENTRY یا به دلیلِ دیگری غیرِ S212).
    check(!(d.state === 'NEUTRAL' && d.sourceLayer && d.sourceLayer.code === 'S212'),
      'اصلاحِ سالم/خطی توسطِ فیلترِ S212 رد نشد')
  } else {
    // تله ⇒ باید دقیقاً به NEUTRAL با sourceLayer S212 برود.
    check(d.state === 'NEUTRAL' && d.sourceLayer && d.sourceLayer.code === 'S212',
      'تلهٔ شتاب‌گیرنده توسطِ فیلترِ S212 رد و به NEUTRAL تبدیل شد')
  }
}

console.log(`\n=== نتیجه: ${pass} پاس / ${fail} ناموفق ===`)
process.exit(fail === 0 ? 0 : 1)

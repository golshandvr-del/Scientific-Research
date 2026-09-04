// پریتی S966: پایتون (strategies/s966_kyle_permanence_drift.py) ↔ TS
// (web_tool/src/kyle_permanence_drift_s966.ts).
//
// روش: fixture شاملِ ۳۰۰۰ کندلِ آخرِ H8 + مرجعِ پایتون که روی **کلِ ۱۱٬۹۷۸
// کندل** محاسبه شده. عمیق‌ترین نگاهِ به‌عقبِ S966 گیتِ درفت است (K=180 + ۱)
// ⇒ برای ایندکس‌های ≥ ۲×۱۸۱ خروجیِ «فقط-پنجره» باید عیناً با «کل-تاریخ» یکی
// باشد. اگر پورت به warm-up وابسته باشد، همین‌جا لو می‌رود.
//
// شش چیز مقایسه می‌شود:
//   ① مجموعهٔ ایندکسِ LONG/SHORT بازوی aligned (فینالیستِ کارت)
//   ② بردارهای درفتِ علّی (driftUp/driftDn) بولی-به-بولی — دامِ ④ سرصفحهٔ ماژول
//   ③ atr_prev و rho عددبه‌عدد (خطای نسبی)
//   ④ SL/TP پیپیِ هر سیگنال (هندسهٔ شناور)
//   ⑤ replay زنده: computeS966 روی پنجرهٔ منتهی به هر سیگنال باید همان را بدهد
//   ⑥ کنترلِ منفیِ **دو لایه‌ای**:
//        (الف) کندل‌های بی‌سیگنال نباید active شوند؛
//        (ب) 🔑 کندل‌هایی که پایهٔ S965 روشن است ولی گیتِ درفت بسته
//            (base ∖ aligned) **باید خاموش** بمانند — این تنها آزمونی است که
//            ثابت می‌کند گیت واقعاً سیم‌کشی شده و S966 کپیِ S965 نیست.
//
// اجرا: cd web_tool && node --import tsx parity_s966_signal.mjs
import fs from 'node:fs'
import { s966Features, S966_CFG, computeS966 } from './src/kyle_permanence_drift_s966.ts'

const fx = JSON.parse(fs.readFileSync('../results/_scan_S966/parity_h8_fixture.json', 'utf8'))
const cfg = S966_CFG['XAUUSD-H8']
const candles = fx.candles
const n = candles.length
const GOLD_PIP = 0.1

const f = s966Features(candles, cfg)

// آستانهٔ مقایسهٔ سخت: از ۲×(driftK+1) به بعد هر دو طرف کاملاً گرم‌اند.
const cut = 2 * (cfg.driftK + 1)

// ── ① سیگنال‌های aligned ────────────────────────────────────────────────
const tsLong = [], tsShort = []
for (let t = cut; t < n; t++) {
  const atrPrev = f.atrPrev[t], rng = f.rng[t]
  if (!(atrPrev > 1e-12) || !(rng > 0)) continue
  if (!(rng >= cfg.theta * atrPrev)) continue
  if (!(f.rho[t] >= cfg.rhoMin)) continue
  if (f.bodySgn[t] > 0 && f.driftUp[t]) tsLong.push(t)
  else if (f.bodySgn[t] < 0 && f.driftDn[t]) tsShort.push(t)
}
const pyLong = fx.py.idx_long.filter(i => i >= cut)
const pyShort = fx.py.idx_short.filter(i => i >= cut)

const eqArr = (a, b) => a.length === b.length && a.every((v, i) => v === b[i])
const okLong = eqArr(tsLong, pyLong)
const okShort = eqArr(tsShort, pyShort)

// ── ② بردارِ درفت بولی-به-بولی ──────────────────────────────────────────
let driftMismatch = 0
for (let t = cut; t < n; t++) {
  if (f.driftUp[t] !== fx.py.drift_up[t]) driftMismatch++
  if (f.driftDn[t] !== fx.py.drift_dn[t]) driftMismatch++
}

// ── ③ ویژگی‌ها عددبه‌عدد ────────────────────────────────────────────────
let maxAtrErr = 0, maxRhoErr = 0
for (let t = cut; t < n; t++) {
  const pa = fx.py.atr_prev[t], pr = fx.py.rho[t]
  const da = Math.abs(f.atrPrev[t] - pa) / Math.max(Math.abs(pa), 1e-12)
  const dr = Math.abs(f.rho[t] - pr) / Math.max(Math.abs(pr), 1e-12)
  if (da > maxAtrErr) maxAtrErr = da
  if (dr > maxRhoErr) maxRhoErr = dr
}

// ── ④ هندسهٔ شناور روی خودِ سیگنال‌ها ────────────────────────────────────
let maxSlErr = 0, maxTpErr = 0
for (const t of [...pyLong, ...pyShort]) {
  const tsSl = Math.max((cfg.kSl * f.atrPrev[t]) / GOLD_PIP, 1e-9)
  const tsTp = Math.max((cfg.kTp * f.atrPrev[t]) / GOLD_PIP, 1e-9)
  const ds = Math.abs(tsSl - fx.py.sl_pip[t]) / Math.max(fx.py.sl_pip[t], 1e-12)
  const dt = Math.abs(tsTp - fx.py.tp_pip[t]) / Math.max(fx.py.tp_pip[t], 1e-12)
  if (ds > maxSlErr) maxSlErr = ds
  if (dt > maxTpErr) maxTpErr = dt
}

// ── ⑤ replay زنده ───────────────────────────────────────────────────────
// سایت همیشه فقط «تا آخرین کندلِ بسته» را می‌بیند ⇒ باید همان سیگنال را بدهد.
let liveOk = 0, liveBad = 0
for (const t of [...pyLong, ...pyShort]) {
  const win = candles.slice(0, t + 1)      // آخرین کندلِ بسته = t
  const raw = computeS966(win, cfg)
  const wantDir = pyLong.includes(t) ? 'LONG' : 'SHORT'
  if (raw.active && raw.direction === wantDir) liveOk++
  else { liveBad++; console.log(`  ✗ live mismatch @${t}: active=${raw.active} dir=${raw.direction} want=${wantDir}`) }
}

// ── ⑥الف کنترلِ منفیِ عمومی ─────────────────────────────────────────────
const sigSet = new Set([...pyLong, ...pyShort])
let falsePos = 0, checked = 0
for (let t = cut; t < n && checked < 200; t += 7) {
  if (sigSet.has(t)) continue
  checked++
  const raw = computeS966(candles.slice(0, t + 1), cfg)
  if (raw.active) { falsePos++; console.log(`  ✗ false positive @${t}`) }
}

// ── ⑥ب 🔑 کنترلِ منفیِ گیت: base ∖ aligned باید خاموش باشد ───────────────
// اگر گیتِ درفت اشتباه سیم‌کشی شده باشد (یا اصلاً وصل نشده باشد)، این
// کندل‌ها active می‌شوند و همین‌جا لو می‌رود. تنها آزمونِ تفکیک‌گرِ S965↔S966.
const pyBase = [...fx.py.base_long, ...fx.py.base_short].filter(i => i >= cut)
const gateBlocked = pyBase.filter(i => !sigSet.has(i))
let gateLeak = 0
for (const t of gateBlocked) {
  const raw = computeS966(candles.slice(0, t + 1), cfg)
  if (raw.active) { gateLeak++; console.log(`  ✗ GATE LEAK @${t}: S965 base fired and S966 did not block it`) }
}

// ── گزارش ───────────────────────────────────────────────────────────────
console.log('\n════════ PARITY S966 (XAUUSD-H8 · aligned · K=180) ════════')
console.log(`bars(tail)=${n}  bars(full)=${fx.bars_full}  cut=${cut}`)
console.log(`① signals LONG : py=${pyLong.length} ts=${tsLong.length}  ${okLong ? '✅' : '❌'}`)
console.log(`① signals SHORT: py=${pyShort.length} ts=${tsShort.length}  ${okShort ? '✅' : '❌'}`)
console.log(`② drift vectors mismatch = ${driftMismatch}  ${driftMismatch === 0 ? '✅' : '❌'}`)
console.log(`③ max rel err  atr_prev=${maxAtrErr.toExponential(2)}  rho=${maxRhoErr.toExponential(2)}`)
console.log(`④ max rel err  sl_pip=${maxSlErr.toExponential(2)}  tp_pip=${maxTpErr.toExponential(2)}`)
console.log(`⑤ live replay  ok=${liveOk} bad=${liveBad}  ${liveBad === 0 ? '✅' : '❌'}`)
console.log(`⑥a negative control (no-signal bars): checked=${checked} falsePos=${falsePos}  ${falsePos === 0 ? '✅' : '❌'}`)
console.log(`⑥b GATE control (S965 base fired, drift opposed): blocked=${gateBlocked.length} leak=${gateLeak}  ${gateLeak === 0 ? '✅' : '❌'}`)

const TOL = 1e-9
const pass = okLong && okShort && driftMismatch === 0 && liveBad === 0 &&
  falsePos === 0 && gateLeak === 0 && gateBlocked.length > 0 &&
  maxAtrErr < TOL && maxRhoErr < TOL && maxSlErr < TOL && maxTpErr < TOL
console.log(pass ? '\n✅ PARITY PASS — S966 port is bit-faithful and the drift gate is proven wired\n'
                 : '\n❌ PARITY FAIL\n')

const report = {
  layer: 'S966', card: 'XAUUSD-H8',
  module: 'web_tool/src/kyle_permanence_drift_s966.ts',
  reference: 'strategies/s966_kyle_permanence_drift.py',
  fixture: 'results/_scan_S966/parity_h8_fixture.json',
  harness: 'web_tool/parity_s966_signal.mjs',
  member: { gate: 'aligned', K: cfg.driftK, th: cfg.theta, rho: cfg.rhoMin },
  bars_tail: n, bars_full: fx.bars_full, cut,
  signals: {
    long: { py: pyLong.length, ts: tsLong.length, match: okLong },
    short: { py: pyShort.length, ts: tsShort.length, match: okShort },
  },
  drift_vector_mismatch: driftMismatch,
  max_rel_err: {
    atr_prev: Number(maxAtrErr.toExponential(3)),
    rho: Number(maxRhoErr.toExponential(3)),
    sl_pip: Number(maxSlErr.toExponential(3)),
    tp_pip: Number(maxTpErr.toExponential(3)),
  },
  live_replay: { ok: liveOk, bad: liveBad },
  negative_control: { checked, false_positives: falsePos },
  gate_control: { s965_base_blocked_by_drift: gateBlocked.length, leaks: gateLeak },
  verdict: pass ? 'PASS' : 'FAIL',
}
fs.writeFileSync('../results/_scan_S966/parity_web_s966.json', JSON.stringify(report, null, 1))
process.exit(pass ? 0 : 1)

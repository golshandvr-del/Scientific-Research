// پریتی S965: پایتون (strategies/s965_kyle_intrabar_permanence.py) ↔ TS
// (web_tool/src/kyle_intrabar_s965.ts).
//
// روش: fixture شاملِ ۳۰۰۰ کندلِ آخرِ H8 + مرجعِ پایتون که روی **کلِ ۱۱٬۹۷۸
// کندل** محاسبه شده. ویژگی‌های S965 حداکثر ATR21+شیفتِ۱ = ۲۲ کندل به عقب
// نگاه می‌کنند ⇒ برای ایندکس‌های ≥ ۲×۲۲ خروجیِ «فقط-پنجره» باید عیناً با
// «کل-تاریخ» یکی باشد. اگر پورت به warm-up وابسته باشد، همین‌جا لو می‌رود.
//
// سه چیز مقایسه می‌شود (نه فقط سیگنال):
//   ① مجموعهٔ ایندکسِ LONG/SHORT
//   ② atr_prev و rho عددبه‌عدد (tol=1e-9 نسبی)
//   ③ SL/TP پیپیِ هر سیگنال (هندسهٔ شناور — دامِ ③ سرصفحهٔ ماژول)
//
// اجرا: cd web_tool && node --import tsx parity_s965_signal.mjs
import fs from 'node:fs'
import { s965Features, S965_CFG, computeS965 } from './src/kyle_intrabar_s965.ts'

const fx = JSON.parse(fs.readFileSync('../results/_scan_S965/parity_h8_fixture.json', 'utf8'))
const cfg = S965_CFG['XAUUSD-H8']
const candles = fx.candles
const n = candles.length
const GOLD_PIP = 0.1

const f = s965Features(candles, cfg)

// آستانهٔ مقایسهٔ سخت: از ۲×(ATR21+1) به بعد هر دو طرف کاملاً گرم‌اند.
const cut = 2 * (cfg.atrWin + 1)

// ── ① سیگنال‌ها ─────────────────────────────────────────────────────────
const tsLong = [], tsShort = []
for (let t = cut; t < n; t++) {
  const atrPrev = f.atrPrev[t], rng = f.rng[t]
  if (!(atrPrev > 1e-12) || !(rng > 0)) continue
  const shock = rng >= cfg.theta * atrPrev
  if (!shock) continue
  if (!(f.rho[t] >= cfg.rhoMin)) continue
  if (f.bodySgn[t] > 0) tsLong.push(t)
  else if (f.bodySgn[t] < 0) tsShort.push(t)
}
const pyLong = fx.py.idx_long.filter(i => i >= cut)
const pyShort = fx.py.idx_short.filter(i => i >= cut)

const eqArr = (a, b) => a.length === b.length && a.every((v, i) => v === b[i])
const okLong = eqArr(tsLong, pyLong)
const okShort = eqArr(tsShort, pyShort)

// ── ② ویژگی‌ها عددبه‌عدد ────────────────────────────────────────────────
let maxAtrErr = 0, maxRhoErr = 0
for (let t = cut; t < n; t++) {
  const pa = fx.py.atr_prev[t], pr = fx.py.rho[t]
  const da = Math.abs(f.atrPrev[t] - pa) / Math.max(Math.abs(pa), 1e-12)
  const dr = Math.abs(f.rho[t] - pr) / Math.max(Math.abs(pr), 1e-12)
  if (da > maxAtrErr) maxAtrErr = da
  if (dr > maxRhoErr) maxRhoErr = dr
}

// ── ③ هندسهٔ شناور روی خودِ سیگنال‌ها ────────────────────────────────────
let maxSlErr = 0, maxTpErr = 0
for (const t of [...pyLong, ...pyShort]) {
  const tsSl = Math.max((cfg.kSl * f.atrPrev[t]) / GOLD_PIP, 1e-9)
  const tsTp = Math.max((cfg.kTp * f.atrPrev[t]) / GOLD_PIP, 1e-9)
  const ds = Math.abs(tsSl - fx.py.sl_pip[t]) / Math.max(fx.py.sl_pip[t], 1e-12)
  const dt = Math.abs(tsTp - fx.py.tp_pip[t]) / Math.max(fx.py.tp_pip[t], 1e-12)
  if (ds > maxSlErr) maxSlErr = ds
  if (dt > maxTpErr) maxTpErr = dt
}

// ── ④ آزمونِ سرتاسری: computeS965 روی پنجرهٔ منتهی به هر سیگنال ─────────
// سایت همیشه فقط «تا آخرین کندلِ بسته» را می‌بیند ⇒ باید همان سیگنال را بدهد.
let liveOk = 0, liveBad = 0
for (const t of [...pyLong, ...pyShort]) {
  const win = candles.slice(0, t + 1)      // آخرین کندلِ بسته = t
  const raw = computeS965(win, cfg)
  const wantDir = pyLong.includes(t) ? 'LONG' : 'SHORT'
  if (raw.active && raw.direction === wantDir) liveOk++
  else { liveBad++; console.log(`  ✗ live mismatch @${t}: active=${raw.active} dir=${raw.direction} want=${wantDir}`) }
}
// و کنترلِ منفی: ۲۰۰ کندلِ تصادفیِ **بدونِ** سیگنالِ پایتون نباید active شوند.
const sigSet = new Set([...pyLong, ...pyShort])
let falsePos = 0, checked = 0
for (let t = cut; t < n && checked < 200; t += 13) {
  if (sigSet.has(t)) continue
  checked++
  const raw = computeS965(candles.slice(0, t + 1), cfg)
  if (raw.active) { falsePos++; console.log(`  ✗ false positive @${t}`) }
}

const TOL = 1e-9
const pass = okLong && okShort && maxAtrErr < TOL && maxRhoErr < TOL &&
  maxSlErr < TOL && maxTpErr < TOL && liveBad === 0 && falsePos === 0

console.log('── S965 parity (python ↔ TS) ─────────────────────────────')
console.log(`  bars=${n} (tail of ${fx.n_bars_full})  cut=${cut}  src=${fx.src}`)
console.log(`  ① signals  LONG  py=${pyLong.length} ts=${tsLong.length} → ${okLong ? 'OK' : 'MISMATCH'}`)
console.log(`             SHORT py=${pyShort.length} ts=${tsShort.length} → ${okShort ? 'OK' : 'MISMATCH'}`)
console.log(`  ② features maxRelErr atr_prev=${maxAtrErr.toExponential(2)} rho=${maxRhoErr.toExponential(2)}`)
console.log(`  ③ geometry maxRelErr sl=${maxSlErr.toExponential(2)} tp=${maxTpErr.toExponential(2)}`)
console.log(`  ④ live     computeS965 on window: ok=${liveOk} bad=${liveBad} · falsePos=${falsePos}/${checked}`)
console.log(pass ? '✅ PARITY PASS — پورت بیت‌به‌بیت' : '❌ PARITY FAIL')
process.exit(pass ? 0 : 1)

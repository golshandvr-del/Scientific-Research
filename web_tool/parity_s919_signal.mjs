// پریتی S919: پایتون (strategies/s919_convention_aligned_shock.py) ↔ TS
// (web_tool/src/convention_shock_s919.ts).
//
// روش: fixture شاملِ ۳۰۰۰ کندلِ آخرِ H6 + مرجعِ پایتون که روی **کلِ ۱۵٬۹۶۶
// کندل** محاسبه شده. عمیق‌ترین نگاهِ به‌عقبِ S919 گیتِ قرارداد است (K=240 + ۱)
// ⇒ برای ایندکس‌های ≥ ۲×۲۴۱ خروجیِ «فقط-پنجره» باید عیناً با «کل-تاریخ» یکی
// باشد. اگر پورت به warm-up وابسته باشد، همین‌جا لو می‌رود.
//
// هفت چیز مقایسه می‌شود:
//   ① مجموعهٔ ایندکسِ **کندلِ رویداد** (بازوی gated) LONG/SHORT
//   ② بردارهای shock / driftUp / driftDn بولی-به-بولی — دامِ ⑤
//   ③ atr_prev و rho عددبه‌عدد (خطای نسبی) — دامِ ①②
//   ④ SL/TP پیپیِ هر سیگنال از atr_prev[ماسک] (هندسهٔ شناور) — دامِ ③
//   ⑤ 🔴 **زمان‌بندی:** ورودِ موتور باید = رویداد+۲ باشد — دامِ ④ (مرگبار)
//   ⑥ replay زنده: computeS919 روی پنجرهٔ منتهی به هر ماسک باید active بدهد
//      با همان جهت و همان هندسه
//   ⑦ کنترلِ منفیِ **سه لایه‌ای**:
//        (الف) کندل‌های بی‌سیگنال نباید active شوند؛
//        (ب) 🔑 کندل‌هایی که پایهٔ S965 روشن است ولی گیتِ قرارداد بسته
//            (base ∖ gated) باید خاموش بمانند — ثابت می‌کند گیت سیم‌کشی شده؛
//        (ج) 🔴 پنجرهٔ منتهی به **خودِ کندلِ رویداد** باید خاموش باشد (چون
//            ورود دو کندل بعد است) — ثابت می‌کند شیفت رعایت شده و لایه
//            یک کندل زود شلیک نمی‌کند.
//
// اجرا: cd web_tool && node --import tsx parity_s919_signal.mjs
import fs from 'node:fs'
import { s919Features, s919EventAt, S919_CFG, computeS919 } from './src/convention_shock_s919.ts'

const fx = JSON.parse(fs.readFileSync('../results/_s919_ckpt/parity_h6_fixture.json', 'utf8'))
const cfg = S919_CFG['XAUUSD-H6']
const candles = fx.candles
const n = candles.length
const GOLD_PIP = 0.1

// نگهبانِ ثابت‌ها: اگر کسی cfg را دست بزند، پریتی باید بترکد نه اینکه سبز بماند.
const cfgChecks = [
  ['theta', cfg.theta, fx.cfg.theta],
  ['rhoMin', cfg.rhoMin, fx.cfg.rho_min],
  ['atrWin', cfg.atrWin, fx.cfg.atr_win],
  ['kSl', cfg.kSl, fx.cfg.k_sl],
  ['kTp', cfg.kTp, fx.cfg.k_tp],
  ['maxHold', cfg.maxHold, fx.cfg.max_hold],
  ['driftK', cfg.driftK, fx.K],
]
const cfgBad = cfgChecks.filter(([, a, b]) => a !== b)

const f = s919Features(candles, cfg)

// آستانهٔ مقایسهٔ سخت: از ۲×(driftK+1) به بعد هر دو طرف کاملاً گرم‌اند.
const cut = 2 * (cfg.driftK + 1)

// ── ① ایندکسِ کندلِ رویداد (بازوی gated) ────────────────────────────────
const tsEvLong = [], tsEvShort = []
for (let t = cut; t < n; t++) {
  const d = s919EventAt(f, t, cfg)
  if (d > 0) tsEvLong.push(t)
  else if (d < 0) tsEvShort.push(t)
}
const pyEvLong = fx.py.idx_event_long.filter(i => i >= cut)
const pyEvShort = fx.py.idx_event_short.filter(i => i >= cut)

const eqArr = (a, b) => a.length === b.length && a.every((v, i) => v === b[i])
const okEvLong = eqArr(tsEvLong, pyEvLong)
const okEvShort = eqArr(tsEvShort, pyEvShort)

// ── ② بردارهای بولی: shock / driftUp / driftDn ──────────────────────────
let shockMis = 0, driftMis = 0
for (let t = cut; t < n; t++) {
  if (f.shock[t] !== fx.py.shock[t]) shockMis++
  if (f.driftUp[t] !== fx.py.drift_up[t]) driftMis++
  if (f.driftDn[t] !== fx.py.drift_dn[t]) driftMis++
}

// ── ③ atr_prev و rho عددبه‌عدد ──────────────────────────────────────────
let maxAtrErr = 0, maxRhoErr = 0
for (let t = cut; t < n; t++) {
  const pa = fx.py.atr_prev[t]
  if (pa !== null && Number.isFinite(f.atrPrev[t])) {
    const e = Math.abs(f.atrPrev[t] - pa) / Math.max(Math.abs(pa), 1e-12)
    if (e > maxAtrErr) maxAtrErr = e
  }
  const pr = fx.py.rho[t]
  if (pr !== null) {
    const e = Math.abs(f.rho[t] - pr)
    if (e > maxRhoErr) maxRhoErr = e
  }
}

// ── ④ هندسهٔ شناورِ هر ماسک (پایتون sl_arr[mask] را می‌خواند) ───────────
// ماسک = رویداد+۱ ⇒ هندسه از atrPrev[event+1].
let maxGeomErr = 0, geomChecked = 0
for (const [maskStr, [pySl, pyTp]] of Object.entries(fx.py.geom_by_mask)) {
  const m = Number(maskStr)
  if (m < cut) continue
  const ap = f.atrPrev[m]
  if (!Number.isFinite(ap)) { maxGeomErr = Infinity; continue }
  const tsSl = Math.max((cfg.kSl * ap) / GOLD_PIP, 1e-9)
  const tsTp = Math.max((cfg.kTp * ap) / GOLD_PIP, 1e-9)
  maxGeomErr = Math.max(
    maxGeomErr,
    Math.abs(tsSl - pySl) / Math.max(pySl, 1e-12),
    Math.abs(tsTp - pyTp) / Math.max(pyTp, 1e-12),
  )
  geomChecked++
}

// ── ⑤ 🔴 زمان‌بندی: ورودِ موتور = رویداد+۲ ──────────────────────────────
let timingBad = 0, timingChecked = 0
for (const tr of fx.py.trades) {
  if (tr.event_bar < cut) continue
  timingChecked++
  if (tr.mask_bar !== tr.event_bar + 1) timingBad++
  if (tr.entry_bar !== tr.event_bar + 2) timingBad++
  // و رویدادِ همان کندل باید در TS هم فعال و هم‌جهت باشد
  const d = s919EventAt(f, tr.event_bar, cfg)
  const want = tr.direction === 'long' ? 1 : -1
  if (d !== want) timingBad++
}

// ── ⑥ replay زنده: پنجرهٔ منتهی به ماسک باید active بدهد ────────────────
// computeS919 رویداد را روی i−1 می‌سنجد ⇒ پنجرهٔ [0..mask] باید فعال شود.
let replayBad = 0, replayChecked = 0, replayGeomErr = 0
for (const tr of fx.py.trades) {
  if (tr.event_bar < cut) continue
  const win = candles.slice(0, tr.mask_bar + 1)
  const r = computeS919(win, cfg)
  replayChecked++
  const wantDir = tr.direction === 'long' ? 'LONG' : 'SHORT'
  if (!r.active || r.direction !== wantDir) { replayBad++; continue }
  const slPip = r.slDist / GOLD_PIP
  replayGeomErr = Math.max(replayGeomErr, Math.abs(slPip - tr.sl_pip) / Math.max(tr.sl_pip, 1e-12))
}

// ── ⑦ کنترلِ منفیِ سه لایه‌ای ───────────────────────────────────────────
const maskSet = new Set([...fx.py.idx_mask_long, ...fx.py.idx_mask_short])
const evSet = new Set([...pyEvLong, ...pyEvShort])

// (الف) کندل‌های بی‌سیگنال
let falsePos = 0, negChecked = 0
for (let m = cut; m < n; m++) {
  if (maskSet.has(m)) continue
  const win = candles.slice(0, m + 1)
  const r = computeS919(win, cfg)
  negChecked++
  if (r.active) falsePos++
}

// (ب) پایهٔ S965 روشن ولی گیتِ قرارداد بسته ⇒ باید خاموش
let baseNotGated = 0, gateLeak = 0
for (let t = cut; t < n; t++) {
  const isBase = f.shock[t] && f.rho[t] >= cfg.rhoMin && f.bodySgn[t] !== 0
  if (!isBase) continue
  if (s919EventAt(f, t, cfg) !== 0) continue    // gated ⇒ صرف‌نظر
  baseNotGated++
  // ماسکِ متناظر = t+1 ⇒ پنجرهٔ [0..t+1] نباید active شود
  if (t + 1 >= n) continue
  const r = computeS919(candles.slice(0, t + 2), cfg)
  if (r.active) gateLeak++
}

// (ج) 🔴 پنجرهٔ منتهی به خودِ کندلِ رویداد باید خاموش باشد (زود شلیک نکند)
let earlyFire = 0, earlyChecked = 0
for (const t of evSet) {
  const r = computeS919(candles.slice(0, t + 1), cfg)
  earlyChecked++
  if (r.active) earlyFire++
}

// ── گزارش ───────────────────────────────────────────────────────────────
const pass =
  cfgBad.length === 0 &&
  okEvLong && okEvShort &&
  shockMis === 0 && driftMis === 0 &&
  maxAtrErr < 1e-9 && maxRhoErr < 1e-12 &&
  maxGeomErr < 1e-9 && geomChecked > 0 &&
  timingBad === 0 && timingChecked > 0 &&
  replayBad === 0 && replayChecked > 0 && replayGeomErr < 1e-9 &&
  falsePos === 0 &&
  gateLeak === 0 &&
  earlyFire === 0 && earlyChecked > 0

console.log('════════ پریتی S919 (XAUUSD-H6) ════════')
console.log(`داده: ${fx.src}`)
console.log(`کلِ تاریخ: ${fx.total_bars} کندل · پنجرهٔ fixture: ${n} · cut=${cut}`)
console.log(`مرجعِ کلِ تاریخ: events L=${fx.whole_history_totals.events_long} S=${fx.whole_history_totals.events_short} · trades=${fx.whole_history_totals.trades} · WR=${fx.whole_history_totals.wr}٪`)
console.log('')
console.log(`⓪ ثابت‌های cfg == پایتون                     : ${cfgBad.length === 0 ? 'PASS' : 'FAIL ' + JSON.stringify(cfgBad)}`)
console.log(`① ایندکسِ رویدادِ LONG  (py=${pyEvLong.length}, ts=${tsEvLong.length})        : ${okEvLong ? 'PASS' : 'FAIL'}`)
console.log(`① ایندکسِ رویدادِ SHORT (py=${pyEvShort.length}, ts=${tsEvShort.length})        : ${okEvShort ? 'PASS' : 'FAIL'}`)
console.log(`② بردارِ shock (اختلاف=${shockMis})                  : ${shockMis === 0 ? 'PASS' : 'FAIL'}`)
console.log(`② بردارِ drift up/dn (اختلاف=${driftMis})            : ${driftMis === 0 ? 'PASS' : 'FAIL'}`)
console.log(`③ atr_prev (خطای نسبیِ بیشینه=${maxAtrErr.toExponential(2)})  : ${maxAtrErr < 1e-9 ? 'PASS' : 'FAIL'}`)
console.log(`③ rho (خطای مطلقِ بیشینه=${maxRhoErr.toExponential(2)})       : ${maxRhoErr < 1e-12 ? 'PASS' : 'FAIL'}`)
console.log(`④ هندسهٔ SL/TP روی ${geomChecked} ماسک (خطا=${maxGeomErr.toExponential(2)})  : ${maxGeomErr < 1e-9 ? 'PASS' : 'FAIL'}`)
console.log(`⑤ 🔴 زمان‌بندی ورود=رویداد+۲ (${timingChecked} معامله، خطا=${timingBad}) : ${timingBad === 0 && timingChecked > 0 ? 'PASS' : 'FAIL'}`)
console.log(`⑥ replay زنده (${replayChecked} پنجره، خطا=${replayBad}، هندسه=${replayGeomErr.toExponential(2)}) : ${replayBad === 0 && replayChecked > 0 && replayGeomErr < 1e-9 ? 'PASS' : 'FAIL'}`)
console.log(`⑦الف کنترلِ منفی (${negChecked} کندلِ بی‌سیگنال، مثبتِ کاذب=${falsePos}) : ${falsePos === 0 ? 'PASS' : 'FAIL'}`)
console.log(`⑦ب  گیتِ قرارداد (${baseNotGated} پایهٔ ردشده، نشتی=${gateLeak})   : ${gateLeak === 0 ? 'PASS' : 'FAIL'}`)
console.log(`⑦ج  🔴 زود-شلیک روی خودِ رویداد (${earlyChecked} مورد، شلیک=${earlyFire}) : ${earlyFire === 0 && earlyChecked > 0 ? 'PASS' : 'FAIL'}`)
console.log('')
console.log(pass ? '✅ پریتی S919: PASS — صفر اختلاف با پایتونِ داوری‌شده' : '❌ پریتی S919: FAIL')
process.exit(pass ? 0 : 1)

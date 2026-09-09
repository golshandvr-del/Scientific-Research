// پریتی S1911: پایتون (strategies/s1911_kyle_shock_calm.py) ↔ TS
// (web_tool/src/kyle_shock_calm_s1911.ts).
//
// چرا این آزمون لازم است: سایت فقط حق دارد چیزی را نشان دهد که داور دیده.
// اگر پورت حتی یک کندل اختلاف داشته باشد، کاربر سیگنالی می‌بیند که هرگز
// RQS2 نگرفته است. پس پیش از وصل کردن، عددها مقایسه می‌شوند.
//
// روش: fixture شاملِ ۳۰۰۰ کندلِ آخرِ H8 است، ولی مرجعِ پایتون روی **کلِ
// ۱۱٬۹۷۸ کندل** حساب شده. تفاوتِ کلیدی با پریتیِ S965: آنجا حافظهٔ لایه
// ۲۲ کندل بود، اینجا گیتِ آرامش ۲۳۳ کندل میانه + ۵۰ کندل گرم‌شدنِ σ حافظه
// دارد. پس آستانهٔ مقایسه از 2×(233+50) به بعد گرفته می‌شود تا هر دو طرف
// کاملاً گرم باشند؛ اگر پورت به warm-up وابسته باشد همین‌جا لو می‌رود.
//
// چهار چیز مقایسه می‌شود:
//   ① مجموعهٔ ایندکسِ LONG/SHORT بازوی gated (تصمیمِ نهایی)
//   ② atr_prev و rho عددبه‌عدد (میراثِ S965)
//   ③ reg = σ ÷ میانهٔ σ عددبه‌عدد (گیتِ آرامش — قطعهٔ تازهٔ این لایه)
//   ④ SL/TP پیپیِ هر سیگنال (هندسهٔ شناور)
//
// اجرا: cd web_tool && node --import tsx parity_s1911_signal.mjs
import fs from 'node:fs'
import { s965Features } from './src/kyle_intrabar_s965.ts'
import { ewmaZ, regimeRatio } from './src/engle_dual_gate_s607.ts'
import { S1911_CFG } from './src/kyle_shock_calm_s1911.ts'

const fx = JSON.parse(
  fs.readFileSync('../results/_s1911_ckpt/parity_h8_fixture.json', 'utf8'))
const cfg = S1911_CFG['XAUUSD-H8']
const candles = fx.candles
const n = candles.length
const off = fx.offset            // candles[k] ≡ ایندکسِ کلِ تاریخِ off+k
const GOLD_PIP = 0.1

// ── محاسبهٔ TS، فقط از روی پنجرهٔ ۳۰۰۰ کندلی ────────────────────────────
const f = s965Features(candles, cfg)
const close = candles.map(c => c.close)
const { sigma } = ewmaZ(close, cfg.lam)
const reg = regimeRatio(sigma, cfg.calmW)

// آستانهٔ سخت: هر دو طرف پس از 2×(W_calm + 50) کاملاً گرم‌اند.
const cutLocal = 2 * (cfg.calmW + 50)

// ── ① سیگنال‌های بازوی gated ────────────────────────────────────────────
const tsLong = [], tsShort = []
for (let t = cutLocal; t < n; t++) {
  const atrPrev = f.atrPrev[t], rng = f.rng[t]
  if (!(atrPrev > 1e-12) || !(rng > 0)) continue
  if (!(rng >= cfg.theta * atrPrev)) continue          // شوک
  if (!(f.rho[t] >= cfg.rhoMin)) continue              // ماندگاری
  if (f.bodySgn[t] === 0) continue
  const r = reg[t]
  if (!Number.isFinite(r) || !(r <= cfg.regMax)) continue   // گیتِ آرامش
  if (f.bodySgn[t] > 0) tsLong.push(t + off)
  else tsShort.push(t + off)
}
const pyLong = fx.py.idx_long.filter(i => i - off >= cutLocal)
const pyShort = fx.py.idx_short.filter(i => i - off >= cutLocal)

const eqArr = (a, b) => a.length === b.length && a.every((v, i) => v === b[i])
const okLong = eqArr(tsLong, pyLong)
const okShort = eqArr(tsShort, pyShort)

// ── ②③ ویژگی‌ها عددبه‌عدد ───────────────────────────────────────────────
const relErr = (ts, py) => {
  if (py === null || py === undefined) return null
  if (!Number.isFinite(ts)) return Infinity
  return Math.abs(ts - py) / Math.max(Math.abs(py), 1e-12)
}
let maxAtrErr = 0, maxRhoErr = 0, maxRegErr = 0, regCmp = 0
for (let t = cutLocal; t < n; t++) {
  const g = t + off
  const ea = relErr(f.atrPrev[t], fx.py.atr_prev[g])
  const er = relErr(f.rho[t], fx.py.rho[g])
  if (ea !== null && ea > maxAtrErr) maxAtrErr = ea
  if (er !== null && er > maxRhoErr) maxRhoErr = er
  const pyReg = fx.py.reg[g]
  if (pyReg !== null && pyReg !== undefined) {
    const eg = relErr(reg[t], pyReg)
    if (eg !== null) { regCmp++; if (eg > maxRegErr) maxRegErr = eg }
  }
}

// ── ④ هندسهٔ شناور روی خودِ سیگنال‌ها ───────────────────────────────────
let maxSlErr = 0, maxTpErr = 0
for (const g of [...pyLong, ...pyShort]) {
  const t = g - off
  const tsSl = Math.max((cfg.kSl * f.atrPrev[t]) / GOLD_PIP, 1e-9)
  const tsTp = Math.max((cfg.kTp * f.atrPrev[t]) / GOLD_PIP, 1e-9)
  const pySl = Math.max((fx.cfg.k_sl * fx.py.atr_prev[g]) / GOLD_PIP, 1e-9)
  const pyTp = Math.max((fx.cfg.k_tp * fx.py.atr_prev[g]) / GOLD_PIP, 1e-9)
  const es = relErr(tsSl, pySl), et = relErr(tsTp, pyTp)
  if (es > maxSlErr) maxSlErr = es
  if (et > maxTpErr) maxTpErr = et
}

const TOL = 1e-9
const okFeat = maxAtrErr <= TOL && maxRhoErr <= TOL
const okReg = maxRegErr <= 1e-6 && regCmp > 0     // میانهٔ لغزان: tol شل‌تر
const okGeom = maxSlErr <= TOL && maxTpErr <= TOL
const green = okLong && okShort && okFeat && okReg && okGeom

console.log(JSON.stringify({
  what: 'پریتیِ S1911 · XAUUSD-H8 · TS در برابرِ مرجعِ پایتون',
  window: { tail: n, offset: off, cut_local: cutLocal, cut_global: cutLocal + off },
  signals: {
    ts_long: tsLong.length, py_long: pyLong.length, long_identical: okLong,
    ts_short: tsShort.length, py_short: pyShort.length, short_identical: okShort,
    ts_total: tsLong.length + tsShort.length,
    py_total_full_history: fx.py.n_events_gated,
    py_ungated_full_history: fx.py.n_events_ungated,
  },
  features: {
    max_rel_err_atr_prev: maxAtrErr,
    max_rel_err_rho: maxRhoErr,
    max_rel_err_reg: maxRegErr,
    reg_points_compared: regCmp,
    tol: TOL,
  },
  geometry: { max_rel_err_sl: maxSlErr, max_rel_err_tp: maxTpErr },
  checks: { okLong, okShort, okFeat, okReg, okGeom },
  verdict: green ? 'GREEN — پورت با مرجع یکی است' : 'RED — اختلاف دارد',
}, null, 1))

if (!green) process.exit(1)

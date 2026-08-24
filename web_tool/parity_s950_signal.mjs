// پریتی S950: پایتون (strategies/s950_jump_aftermath.py) ↔ TS (jump_aftermath_s950.ts)
// روش: fixture شاملِ ۳۰۰۰ کندلِ آخرِ H8 + ایندکس‌های سیگنالِ پایتون (محاسبه روی
// کلِ تاریخ). ویژگی‌های S950 حداکثر ۹۱ کندل به عقب نگاه می‌کنند ⇒ برای ایندکس‌های
// پنجره‌ای ≥ warm+1 خروجیِ «فقط-پنجره» باید عیناً با «کل-تاریخ» یکی باشد.
// اجرا: node --import tsx parity_s950_signal.mjs
import fs from 'node:fs'
import { s950Features, S950_CFG } from './src/jump_aftermath_s950.ts'

const fx = JSON.parse(fs.readFileSync('../results/_scan_S950/parity_h8_fixture.json', 'utf8'))
const cfg = S950_CFG['XAUUSD-H8']
const candles = fx.candles
const n = candles.length
const warm = cfg.bvWin + 2          // 91

const f = s950Features(candles, cfg)
const tsLong = [], tsShort = []
for (let t = 0; t < n; t++) {
  const valid = t >= warm && f.sigmaBv[t] > 0
  if (!valid) continue
  const thr = cfg.kJump * f.sigmaBv[t]
  if (f.r[t] > thr && f.drift[t] > 0) tsLong.push(t)
  if (f.r[t] < -thr && f.drift[t] < 0) tsShort.push(t)
}

// مقایسه فقط در ناحیهٔ معتبرِ پنجره (t ≥ warm+1؛ در t=warm خودِ پایتون هم روی
// کل تاریخ سیگنال دارد ولی smaConvolve جزئی در ۸۸ عضو اول پنجره فرق دارد ⇒
// از t ≥ 2*warm مقایسهٔ سخت می‌کنیم تا هر دو کاملاً گرم باشند).
const cut = 2 * warm
const pyL = fx.py.idx_long.filter(i => i >= cut)
const pyS = fx.py.idx_short.filter(i => i >= cut)
const tsL = tsLong.filter(i => i >= cut)
const tsS = tsShort.filter(i => i >= cut)

const eq = (a, b) => a.length === b.length && a.every((v, i) => v === b[i])
const okL = eq(pyL, tsL), okS = eq(pyS, tsS)

// پریتی مقادیر: σ_BV / ATR / drift پنج کندلِ آخر (پایتون روی کلِ تاریخ — باید
// تا دقتِ float با TSِ فقط-پنجره یکی باشد چون lookback ≤ 91).
const relErr = (a, b) => Math.abs(a - b) / Math.max(Math.abs(a), 1e-12)
let maxErr = 0
for (let k = 0; k < 5; k++) {
  maxErr = Math.max(maxErr,
    relErr(fx.py.sigma_tail[k], f.sigmaBv[n - 5 + k]),
    relErr(fx.py.atr_tail[k], f.atrPx[n - 5 + k]),
    fx.py.drift_tail[k] !== 0 ? relErr(fx.py.drift_tail[k], f.drift[n - 5 + k]) : 0)
}

const report = {
  n_bars: n, cut,
  py: { long: pyL.length, short: pyS.length },
  ts: { long: tsL.length, short: tsS.length },
  signals_long_match: okL, signals_short_match: okS,
  max_rel_err_features: maxErr,
  verdict: (okL && okS && maxErr < 1e-9) ? 'PARITY-PASS' : 'PARITY-FAIL',
}
if (!okL) report.diff_long = { py_only: pyL.filter(x => !tsL.includes(x)).slice(0, 10), ts_only: tsL.filter(x => !pyL.includes(x)).slice(0, 10) }
if (!okS) report.diff_short = { py_only: pyS.filter(x => !tsS.includes(x)).slice(0, 10), ts_only: tsS.filter(x => !pyS.includes(x)).slice(0, 10) }
fs.writeFileSync('../results/_scan_S950/parity_h8_ts.json', JSON.stringify(report, null, 1))
console.log(JSON.stringify(report, null, 1))
if (report.verdict !== 'PARITY-PASS') process.exit(1)

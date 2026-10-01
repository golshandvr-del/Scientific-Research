// ---------------------------------------------------------------------------
// آزمونِ برابریِ S798 — پورتِ TS در برابرِ مرجعِ پایتون روی کلِ ۱۵.۶ سال H8.
//
// مرجع: results/_s798_parity/XAUUSD_H8.json (tools/export_s798_parity.py — ماشینِ
//   منجمدِ حکم؛ کنترلِ ۷۹ سیگنال / ۷۹ معامله / WR 74.68 را بازتولید کرد).
//
// چک‌ها:
//   ① روی H8ِ بومیِ MT5: مجموعهٔ کاملِ سیگنال‌ها (زمان + جهت) بیت‌به‌بیت
//   ② ATR[i−1] و SL (دلار) روی هر سیگنال (|Δ| < 1e-6)
//   ③ ATR روی ۴۰۰ کندلِ آخر (|Δ| < 1e-6)
//   ④ مسیرِ واقعیِ سایت: H1 → aggregateCandles(×8) ⇒ همان ۷۹ زمانِ سیگنال
//   ⑤ maxHold = ۱۲ و > بیشینهٔ نگه‌داریِ واقعی (۱۱)
//   ⑥ کنترلِ منفیِ گیتِ نشست: بدونِ شرطِ ساعت، شوک‌ها اکیداً بیشترند (۲۲۱ > ۷۹)
//   ⑦ شاهدِ منفیِ MTF: S798_CFG فقط کلیدِ XAUUSD-H8 دارد
//   ⑧ computeS798 روی پیشوندِ منتهی به آخرین سیگنالِ واقعی ⇒ active و جهت درست؛
//      روی کندلِ بعدش ⇒ active=false
//
// اجرا: npx tsx tools/_parity_s798.mts
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import zlib from 'node:zlib'
import { S798_CFG, s798AtrPrev, s798SignalAt, computeS798 } from '../src/london_shock_s798.js'
import { aggregateCandles } from '../src/price/gold_source.js'
import type { Candle } from '../src/indicators.js'

const ROOT = new URL('../../', import.meta.url).pathname
const TOL = 1e-6

function loadCsv(name: string): Candle[] {
  const txt = zlib.gunzipSync(fs.readFileSync(`${ROOT}data/mt5_full/${name}.csv.gz`)).toString('utf8')
  const lines = txt.trim().split('\n')
  const out: Candle[] = []
  for (let i = 1; i < lines.length; i++) {
    const p = lines[i].trim().split(',')
    if (p.length < 6) continue
    out.push({ time: +p[0], open: +p[1], high: +p[2], low: +p[3], close: +p[4], volume: +p[5] })
  }
  return out
}

const ref = JSON.parse(fs.readFileSync(`${ROOT}results/_s798_parity/XAUUSD_H8.json`, 'utf8'))
const cfg = S798_CFG['XAUUSD-H8']
let fails = 0
const log: string[] = []
function ok(c: boolean, m: string) { const s = `${c ? '✅' : '❌'} ${m}`; console.log(s); log.push(s); if (!c) fails++ }

// ① ② ③ — H8 بومی
const h8 = loadCsv('XAUUSD_H8')
ok(h8.length === ref.bars, `H8 bars ${h8.length} = ${ref.bars}`)
const ap = s798AtrPrev(h8, cfg.atrWin)
const tsSig: { t: number; d: number; i: number }[] = []
for (let i = 0; i < h8.length; i++) { const d = s798SignalAt(h8, ap, i, cfg); if (d) tsSig.push({ t: h8[i].time, d, i }) }
const same = tsSig.length === ref.signal_times.length &&
  tsSig.every((s, k) => s.t === ref.signal_times[k] && s.d === ref.signal_dirs[k])
ok(same, `① سیگنال‌ها: TS ${tsSig.length} / PY ${ref.signal_times.length} — زمان و جهت یکسان`)
let mA = 0, mS = 0
tsSig.forEach((s, k) => {
  if (k >= ref.signal_atr_prev.length) return
  mA = Math.max(mA, Math.abs(ap[s.i] - ref.signal_atr_prev[k]))
  mS = Math.max(mS, Math.abs(cfg.kSl * ap[s.i] - ref.signal_sl_usd[k]))
})
ok(mA < TOL && mS < TOL, `② max|ΔATR|=${mA.toExponential(1)} · max|ΔSL|=${mS.toExponential(1)}`)
let mT = 0
ref.tail_times.forEach((t: number, k: number) => {
  const j = h8.findIndex(c => c.time === t); mT = Math.max(mT, Math.abs(ap[j] - ref.tail_atr_prev[k]))
})
ok(mT < TOL, `③ ATR روی ۴۰۰ کندلِ آخر: max|Δ|=${mT.toExponential(1)}`)

// ④ مسیرِ سایت: H1×8
const agg = aggregateCandles(loadCsv('XAUUSD_H1'), 8)
const apA = s798AtrPrev(agg, cfg.atrWin)
const aggT: number[] = []
for (let i = 0; i < agg.length; i++) if (s798SignalAt(agg, apA, i, cfg)) aggT.push(agg[i].time)
const setRef = new Set<number>(ref.signal_times)
const inter = aggT.filter(t => setRef.has(t)).length
ok(inter === ref.signal_times.length && aggT.length === ref.signal_times.length,
  `④ مسیرِ سایت (H1×8): ${aggT.length} سیگنال، ${inter} مشترک با مرجعِ ${ref.signal_times.length}`)

// ⑤ ⑥ ⑦
ok(cfg.maxHold === 12 && cfg.maxHold > ref.bars_held_max, `⑤ maxHold=${cfg.maxHold} > bars_held_max=${ref.bars_held_max}`)
let anyHour = 0
for (let i = 0; i < h8.length; i++) {
  const k = h8[i]; if (ap[i] === ap[i] && k.high - k.low >= cfg.theta * ap[i] && k.close !== k.open) anyHour++
}
ok(anyHour === ref.shock_any_hour && anyHour > tsSig.length, `⑥ گیتِ نشست زنده: شوکِ هر ساعت ${anyHour} > ${tsSig.length}`)
ok(JSON.stringify(Object.keys(S798_CFG)) === '["XAUUSD-H8"]', `⑦ کلیدهای S798_CFG = ${Object.keys(S798_CFG).join(',')}`)

// ⑧ لبه
const last = tsSig[tsSig.length - 1]
const r1 = computeS798(h8.slice(0, last.i + 1), cfg)
const r2 = computeS798(h8.slice(0, last.i + 2), cfg)
ok(r1.active && (r1.direction === 'LONG' ? 1 : -1) === last.d && Math.abs(r1.slDist - r1.tpDist) < 1e-12,
  `⑧ آخرین سیگنالِ واقعی ${new Date(last.t * 1000).toISOString()} ⇒ active ${r1.direction}, SL=TP=${r1.slDist.toFixed(3)}$`)
ok(!r2.active, `⑧ کندلِ بعد ⇒ active=${r2.active}`)

const res = { layer: 'S798', card: 'XAUUSD-H8', status: fails ? 'RED' : 'GREEN', fails, ts_signals: tsSig.length,
  py_signals: ref.signal_times.length, site_path_signals: aggT.length, max_d_atr: mA, max_d_sl: mS, log }
fs.writeFileSync(`${ROOT}results/_s798_parity/parity_result.json`, JSON.stringify(res, null, 1))
console.log(`\n${res.status} (${log.length - fails}/${log.length})`)
process.exit(fails ? 1 : 0)

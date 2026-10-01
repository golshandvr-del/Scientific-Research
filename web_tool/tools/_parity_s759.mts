// ---------------------------------------------------------------------------
// آزمونِ برابریِ S759 — پورتِ TS در برابرِ مرجعِ پایتون روی کلِ ۱۵.۶ سال.
//
// مرجع: results/_s759_parity/XAUUSD_H4.json (tools/export_s759_parity.py — ماشینِ
//   منجمدِ حکم، کنترلِ ۱۷۵ معامله/WR 52.00 را بازتولید کرد).
// داده: data/mt5_full/XAUUSD_H1.csv.gz → H4 با سطل‌های ۴ ساعتهٔ UTC (عینِ
//   pandas resample('4h') + dropna). سایت هم H4 را از H1×4 می‌سازد.
//
// چک‌ها:
//   ① مجموعهٔ **کاملِ** سیگنال‌های گیت‌شده (۱۹۹) بیت‌به‌بیت
//   ② مجموعهٔ کاملِ سیگنال‌های بی‌گیت (۳۵۰) ⇒ ساختارِ داو مستقل از ρ درست است
//   ③ ATR89 و SL (دلار) روی هر کندلِ سیگنال (|Δ| < 1e-4)
//   ④ ATR روی ۴۰۰ کندلِ آخر (|Δ| < 1e-4)
//   ⑤ maxHold پورت = ۵۵ (پارامترِ حکم) و > بیشینهٔ نگه‌داریِ واقعی
//   ⑥ کنترلِ منفیِ گیتِ ρ: بی‌گیت باید اکیداً بیشتر باشد
//   ⑦ شاهدِ منفیِ MTF: S759_CFG فقط کلیدِ XAUUSD-H4 دارد (H3 REJECT 30.3)
//   ⑧ computeS759 روی پیشوندِ دادهٔ منتهی به یک سیگنالِ واقعی ⇒ active=true،
//      و روی کندلِ بعدِ آن ⇒ active=false (لبهٔ اول، نه حالت)
//
// اجرا: npx tsx tools/_parity_s759.mts
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import zlib from 'node:zlib'
import { S759_CFG, s759Features, computeS759 } from '../src/informed_structure_s759.js'
import type { Candle } from '../src/indicators.js'

const ROOT = new URL('../../', import.meta.url).pathname
const TOL = 1e-4

function loadH1(): Candle[] {
  const txt = zlib.gunzipSync(fs.readFileSync(`${ROOT}data/mt5_full/XAUUSD_H1.csv.gz`)).toString('utf8')
  const lines = txt.trim().split('\n')
  const out: Candle[] = []
  for (let i = 1; i < lines.length; i++) {
    const p = lines[i].trim().split(',')
    if (p.length < 6) continue
    out.push({ time: +p[0], open: +p[1], high: +p[2], low: +p[3], close: +p[4], volume: +p[5] })
  }
  return out
}

export function toH4(h1: Candle[]): Candle[] {
  const out: Candle[] = []
  let cur: Candle | null = null
  for (const c of h1) {
    const b = Math.floor(c.time / 14400) * 14400
    if (!cur || cur.time !== b) {
      if (cur) out.push(cur)
      cur = { time: b, open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume }
    } else {
      if (c.high > cur.high) cur.high = c.high
      if (c.low < cur.low) cur.low = c.low
      cur.close = c.close
      cur.volume += c.volume
    }
  }
  if (cur) out.push(cur)
  return out
}

let fails = 0
const check = (name: string, ok: boolean, detail = '') => {
  console.log(`${ok ? '✅' : '❌'} ${name}${detail ? ' — ' + detail : ''}`)
  if (!ok) fails++
}

const ref = JSON.parse(fs.readFileSync(`${ROOT}results/_s759_parity/XAUUSD_H4.json`, 'utf8'))
const cfg = S759_CFG['XAUUSD-H4']
const c = toH4(loadH1())
check('bars (H1→H4)', c.length === ref.bars, `${c.length} vs ${ref.bars}`)
check('first/last time', c[0].time === ref.first_time && c[c.length - 1].time === ref.last_time)

const f = s759Features(c, cfg)
const tIdx = new Map(c.map((x, i) => [x.time, i]))
const gated: number[] = [], ungated: number[] = []
for (let i = cfg.warmup; i < c.length; i++) {
  if (f.sig[i]) gated.push(c[i].time)
  if (f.structural[i]) ungated.push(c[i].time)
}
const sameSet = (a: number[], b: number[]) => {
  const A = new Set(a), B = new Set(b)
  const onlyA = a.filter(x => !B.has(x)), onlyB = b.filter(x => !A.has(x))
  return { ok: onlyA.length === 0 && onlyB.length === 0, onlyA, onlyB }
}
const g = sameSet(gated, ref.sig_times)
check('① gated signal set (full history)', g.ok,
  `ts=${gated.length} py=${ref.sig_times.length} onlyTS=${g.onlyA.slice(0, 5)} onlyPY=${g.onlyB.slice(0, 5)}`)
const u = sameSet(ungated, ref.ungated_times)
check('② ungated structure set', u.ok,
  `ts=${ungated.length} py=${ref.ungated_times.length} onlyTS=${u.onlyA.slice(0, 5)} onlyPY=${u.onlyB.slice(0, 5)}`)

let maxAtr = 0, maxSl = 0
ref.sig_times.forEach((t: number, k: number) => {
  const i = tIdx.get(t)!
  maxAtr = Math.max(maxAtr, Math.abs(f.atr[i] - ref.sig_atr_usd[k]))
  maxSl = Math.max(maxSl, Math.abs(cfg.slK * f.atr[i] - ref.sig_sl_usd[k]))
})
check('③ ATR89 / SL at every signal', maxAtr < TOL && maxSl < TOL, `max|ΔATR|=${maxAtr.toExponential(2)} max|ΔSL|=${maxSl.toExponential(2)}`)

let maxTail = 0
ref.last400.times.forEach((t: number, k: number) => {
  const i = tIdx.get(t)!
  maxTail = Math.max(maxTail, Math.abs(f.atr[i] - ref.last400.atr_usd[k]))
})
check('④ ATR last 400 bars', maxTail < TOL, `max|Δ|=${maxTail.toExponential(2)}`)

check('⑤ maxHold = verdict param 55 and > measured max hold', cfg.maxHold === ref.max_hold && cfg.maxHold > ref.bars_held.max,
  `cfg=${cfg.maxHold} ref=${ref.max_hold} maxHeld=${ref.bars_held.max}`)
check('⑥ negative control: rho gate is live', ungated.length > gated.length, `${ungated.length} > ${gated.length}`)
check('⑦ MTF negative witness: only XAUUSD-H4 configured', JSON.stringify(Object.keys(S759_CFG)) === '["XAUUSD-H4"]')

// ⑧ آخرین سیگنالِ واقعی از مسیرِ computeS759 (پیشوندِ داده — مثلِ فیدِ زنده)
const lastSig = ref.sig_times[ref.sig_times.length - 1]
const iS = tIdx.get(lastSig)!
const r1 = computeS759(c.slice(0, iS + 1), cfg)
const r2 = computeS759(c.slice(0, iS + 2), cfg)
const slOk = Math.abs(r1.slDist - ref.sig_sl_usd[ref.sig_sl_usd.length - 1]) < TOL
  && Math.abs(r1.tpDist - cfg.rr * r1.slDist) < 1e-9
check('⑧ computeS759 fires on the real last signal, not on the next bar', r1.active && !r2.active && slOk,
  `t=${new Date(lastSig * 1000).toISOString()} active=${r1.active} next=${r2.active} SL=${r1.slDist.toFixed(3)}$`)

const result = {
  layer: 'S759', card: 'XAUUSD-H4', status: fails === 0 ? 'GREEN' : 'RED', fails,
  gated_ts: gated.length, gated_py: ref.sig_times.length,
  ungated_ts: ungated.length, ungated_py: ref.ungated_times.length,
  max_abs_atr: maxAtr, max_abs_sl: maxSl, max_abs_atr_tail: maxTail,
  last_signal_utc: new Date(lastSig * 1000).toISOString(), last_signal_sl_usd: r1.slDist,
}
if (process.argv.includes('--write')) {
  fs.writeFileSync(`${ROOT}results/_s759_parity/parity_result.json`, JSON.stringify(result, null, 1))
}
console.log(JSON.stringify(result))
process.exit(fails ? 1 : 0)

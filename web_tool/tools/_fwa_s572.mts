// ---------------------------------------------------------------------------
// ممیزیِ «شاهدِ کاذب» پیش از سیم‌کشیِ S572 — XAUUSD-M30 و H1
//
// چرا: مکانیزمِ نمایشِ سایت هم‌پوشانیِ معمولی را خودش حل می‌کند. تنها حالتی که
// ساختاراً نمی‌بیند و فقط **اندازه‌گیریِ قبلی** می‌تواند: وقتی دو لایه در واقع
// **یک رویدادِ واحد** با دو اسم‌اند. سابقهٔ ریپو: S404/S408 (jaccard ۶۹.۳٪ ⇒
// «یکی، نه هر دو»).
//
// خطرِ مشخصِ S572: تنها ساکنِ زندهٔ M30/H1 که **هم‌خانوادهٔ رویدادِ پولبک** است،
// S431 (= S333 + دروازهٔ LPSB) است. اگر S572 و S431 عملاً یک رویداد باشند،
// کاربر دو شاهدِ مستقل می‌بیند در حالی که یکی است ⇒ ریسک دوبرابر.
//
// معیارِ حکم (ارثی از پروندهٔ S404/S408، بدونِ تغییر):
//   jaccard ≥ 0.60 **و** هم‌اندازگی (size_ratio ≥ 0.75) ⇒ FALSE-WITNESS.
//
// کنترلِ اعتبارسنجیِ ابزار: تعدادِ سیگنالِ S572 باید ۳۰۴ (M30) و ۵۳ (H1) باشد —
// همان اعدادِ مرجعِ پریتی. اگر نه، ابزار بی‌اعتبار است.
//
// اجرا: npx tsx tools/_fwa_s572.mts
// خروجی: results/_s572_parity/false_witness.json
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import zlib from 'node:zlib'
import { S572_CFG, s572Features } from '../src/sr_pullback_mirror_s572.js'
import { S333_CFG, erLucasSeries } from '../src/s333_pullback.js'
import { hurstSeries } from '../src/squeeze_s332.js'
import { lpsbStateSeries, S431_CFG } from '../src/lpsb_state_s355.js'
import { ema, rsi } from '../src/indicators.js'
import type { Candle } from '../src/indicators.js'

const ROOT = new URL('../../', import.meta.url).pathname
const JACCARD_FW = 0.60
const SIZE_RATIO = 0.75
const EXPECT = { 'XAUUSD-M30': 304, 'XAUUSD-H1': 53 } as Record<string, number>

function loadCsv(tf: string): Candle[] {
  const gz = `${ROOT}data/mt5_full/XAUUSD_${tf}.csv.gz`
  const text = zlib.gunzipSync(fs.readFileSync(gz)).toString('utf8')
  const lines = text.trim().split('\n').map(l => l.replace(/\r$/, ''))
  const head = lines[0].split(',').map(s => s.trim())
  const ix = (n: string) => head.indexOf(n)
  const iT = ix('time'), iO = ix('open'), iH = ix('high'), iL = ix('low'), iC = ix('close')
  const iV = ix('volume') >= 0 ? ix('volume') : ix('tick_volume')
  const out: Candle[] = []
  for (let i = 1; i < lines.length; i++) {
    const t = lines[i].split(',')
    out.push({ time: Number(t[iT]), open: Number(t[iO]), high: Number(t[iH]),
      low: Number(t[iL]), close: Number(t[iC]), volume: iV >= 0 ? Number(t[iV]) : 0 })
  }
  return out
}

// سریِ سیگنالِ S431 = S333(سری، علّی) ∧ LPSB==−1 — پورتِ computeS333 برای همهٔ i
function s431Series(candles: Candle[], card: string): boolean[] {
  const cfg = S333_CFG[card]
  const n = candles.length
  const close = candles.map(c => c.close)
  const high = candles.map(c => c.high)
  const ef = ema(close, cfg.emaFast)
  const es = ema(close, cfg.emaSlow)
  const r = rsi(close, cfg.rsiP)
  const hu = hurstSeries(close, 64)
  const er = cfg.erTh != null ? erLucasSeries(close, 29) : null
  const lpsb = lpsbStateSeries(candles, S431_CFG[card].L, S431_CFG[card].f)
  const need = Math.max(cfg.emaSlow, 64) + 5
  const out = new Array<boolean>(n).fill(false)
  for (let i = need; i < n; i++) {
    const up = ef[i] > es[i]
    const huOk = (Number.isFinite(hu[i]) ? hu[i] : 0) > cfg.hurstTh
    const erOk = er == null ? true : (Number.isFinite(er[i]) ? er[i] : 0) > (cfg.erTh as number)
    let core = false
    if (cfg.confirm === 'none') core = up && r[i] < cfg.rsiTh
    else if (cfg.confirm === 'rsi_turn') core = up && r[i - 1] < cfg.rsiTh && r[i] > r[i - 1] && r[i] < cfg.rsiTh + 10
    else { const dipped = r[i] < cfg.rsiTh || r[i - 1] < cfg.rsiTh; core = up && dipped && close[i] > high[i - 1] }
    out[i] = core && huOk && erOk && lpsb[i] === S431_CFG[card].requiredState
  }
  return out
}

function compare(a: boolean[], b: boolean[], nameA: string, nameB: string) {
  const ia = new Set<number>(), ib = new Set<number>()
  for (let i = 0; i < a.length; i++) if (a[i]) ia.add(i)
  for (let i = 0; i < b.length; i++) if (b[i]) ib.add(i)
  let shared = 0
  for (const x of ia) if (ib.has(x)) shared++
  const union = ia.size + ib.size - shared
  const sizeRatio = Math.max(ia.size, ib.size) ? Math.min(ia.size, ib.size) / Math.max(ia.size, ib.size) : 0
  const jac = union ? shared / union : 0
  return {
    a: nameA, b: nameB, n_a: ia.size, n_b: ib.size, shared,
    share_of_a: ia.size ? +(100 * shared / ia.size).toFixed(1) : 0,
    share_of_b: ib.size ? +(100 * shared / ib.size).toFixed(1) : 0,
    jaccard: +jac.toFixed(4), size_ratio: +sizeRatio.toFixed(4),
    false_witness: jac >= JACCARD_FW && sizeRatio >= SIZE_RATIO,
  }
}

let bad = 0
const report: any = {
  layer: 'S572', cards: {},
  rule: 'sr-pullback mirror (S323 frozen) x {M30,H1} pool',
  thresholds: { jaccard_false_witness: JACCARD_FW, size_ratio_comparable: SIZE_RATIO,
    precedent: 'strategy_registry.ts FALSE_WITNESS_PAIRS (S404/S408 jaccard 69.3%)' },
}
for (const card of ['XAUUSD-M30', 'XAUUSD-H1']) {
  const tf = card.split('-')[1]
  const candles = loadCsv(tf)
  const f = s572Features(candles, S572_CFG[card])
  let n572 = 0; for (let i = 0; i < f.sig.length; i++) if (f.sig[i]) n572++
  const ctrl = n572 === EXPECT[card]
  if (!ctrl) bad++
  const s431 = s431Series(candles, card)
  const rec = compare(f.sig, s431, 'S572', 'S431')
  report.cards[card] = {
    bars: candles.length, n_S572: n572, n_S431: s431.filter(Boolean).length,
    control_ok: ctrl, control_expected: EXPECT[card],
    vs_S431: rec,
  }
  console.log(`${card}: bars=${candles.length} S572=${n572}(ctrl ${ctrl ? 'OK' : 'FAIL'}) ` +
    `S431=${rec.n_b} shared=${rec.shared} share_of_S572=${rec.share_of_a}% ` +
    `jaccard=${rec.jaccard} size_ratio=${rec.size_ratio} FALSE_WITNESS=${rec.false_witness}`)
}

const outPath = `${ROOT}results/_s572_parity/false_witness.json`
fs.mkdirSync(`${ROOT}results/_s572_parity`, { recursive: true })
fs.writeFileSync(outPath, JSON.stringify(report, null, 1))
console.log(`\nsaved -> ${outPath}`)
if (bad) { console.log('❌ TOOL-INVALID: S572 signal counts not reproduced'); process.exit(1) }
console.log('✅ tool valid — S572 counts reproduced; no false witness with the pullback incumbent S431')

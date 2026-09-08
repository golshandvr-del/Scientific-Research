// ---------------------------------------------------------------------------
// آزمونِ برابریِ S1520 — پورتِ TS در برابرِ مرجعِ **پایتون** روی دادهٔ کاملِ MT5.
//
// مرجع: results/_s1520_parity/<CARD>.json (ساختهٔ tools/export_s1520_parity.py
//   که خودش ماشینِ منجمدِ حکمِ ACCEPT 90.6 را وارد می‌کند — نه یک فرمولِ
//   بازنویسی‌شده — و گیتِ سلامتش n/WR/SL/TP حکم را بازتولید کرد).
//
// چه چیزی سنجیده می‌شود (۵ چک روی هر کارت):
//   ① سری‌های علّی روی **همهٔ** کندل‌های دنبالهٔ صادرشده: priorMax90 · rho · ATR100
//   ② پرچمِ رویداد: fresh (لبهٔ تازه) و gated (لبهٔ تازه ∧ ρ≥0.618) بیت‌به‌بیت
//   ③ مجموعهٔ کاملِ سیگنال‌ها: مقایسهٔ **مجموعه‌ای** ایندکس‌ها (نه فقط شمارش) —
//      یک سیگنالِ جابه‌جاشده با یک سیگنالِ گم‌شده هم‌شمار است ولی هم‌ارز نیست.
//   ④ هندسه: slPip/tpPip منجمدِ S1520_CFG در برابرِ geometry مرجع
//   ⑤ شاهدِ منفیِ MTF: کارت‌های H4 و H12 باید سیگنالِ **یکسان** بسازند
//      (پورت درست است) ولی **نباید** در S1520_CFG باشند (وصل نمی‌شوند).
//      این تفکیکِ «پورتِ درست» از «حکمِ منفی» است — بدون آن، نبودِ کارت را
//      نمی‌توان از یک باگِ سکوت تشخیص داد.
//
// 🔴 تلهٔ روش‌شناسیِ این آزمون: هم ATR100 (ویلدر، بازگشتی) و هم سقفِ غلتانِ ۹۰
//   کندلی به تاریخِ **قبل** از دنبالهٔ صادرشده وابسته‌اند. پس سری‌ها روی **کلِ
//   تاریخ** محاسبه می‌شوند (عیناً مثلِ پایتون) و فقط روی دنباله مقایسه می‌شوند.
//   بریدنِ داده از ابتدا مقدارِ ATR را برای همیشه منحرف می‌کند.
//
// اجرا: npx tsx tools/_parity_s1520.mts          (هر سه کارت + شاهدِ منفی)
//       npx tsx tools/_parity_s1520.mts H8       (یک کارت)
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import zlib from 'node:zlib'
import {
  S1520_CFG, s1520Features, atrWilderS1520, type S1520Config,
} from '../src/informed_fresh_high_s1520.js'

const TOL_PRICE = 1e-6      // priorMax: قیمت، ۶ رقم کافی
const TOL_RHO = 1e-9        // ρ نسبتِ ساده است ⇒ سخت‌گیرانه
const TOL_ATR = 1e-6        // ATR ویلدر بازگشتی است ⇒ خطای انباشتِ float
const TOL_PIP = 1e-6

// پیکربندیِ منجمدِ کارت‌های **وصل‌نشده** — فقط برای پریتی، تا اثبات شود پورت
// روی آن‌ها هم درست کار می‌کند. عددها از results/_s1520_parity/<CARD>.json.
// ⚠️ این‌ها عمداً در S1520_CFG **نیستند** (قانونِ MTF: تعمیمِ بدونِ حکم ممنوع).
const NEG_CFG: Record<string, S1520Config> = {
  'XAUUSD-H4': {
    id: 'XAUUSD-H4', tfFa: 'H4', lookback: 90, rhoMin: 0.618, atrP: 100,
    slK: 1.5, rr: 1.5, slPip: 123.01, tpPip: 184.51,
    maxHold: 96, approachFrac: 0.995, rqs2: 16.7,
  },
  'XAUUSD-H12': {
    id: 'XAUUSD-H12', tfFa: 'H12', lookback: 90, rhoMin: 0.618, atrP: 100,
    slK: 1.5, rr: 1.5, slPip: 228.09, tpPip: 342.14,
    maxHold: 96, approachFrac: 0.995, rqs2: 27.1,
  },
}

type RefSeries = {
  i: number; t: number; o: number; h: number; l: number; c: number
  priorMax: number | null; rho: number; atr: number | null
  fresh: boolean; gated: boolean
}
type Ref = {
  card: string; bars: number; span_years: number
  frozen: { lookback: number; rhoThr: number; atrP: number; slK: number; rr: number }
  geometry: { medianAtr: number; slAbs: number; slPip: number; tpPip: number }
  counts: { fresh: number; gated: number; counter: number; gatePassRatePct: number; trades: number; wr: number | null }
  signalIdx: number[]; counterIdx: number[]
  tailFrom: number; series: RefSeries[]
}
type Candle = { time: number; open: number; high: number; low: number; close: number; volume: number }

const ROOT = new URL('../../', import.meta.url).pathname   // ریشهٔ مخزن

function loadCandles(card: string): Candle[] {
  // عیناً همان مسیرِ load_card پایتون: data/full سپس gunzip از data/mt5_full.
  const plain = `${ROOT}data/full/${card}.csv`
  let text: string
  if (fs.existsSync(plain)) {
    text = fs.readFileSync(plain, 'utf8')
  } else {
    const gz = `${ROOT}data/mt5_full/${card}.csv.gz`
    text = zlib.gunzipSync(fs.readFileSync(gz)).toString('utf8')
  }
  const lines = text.trim().split('\n')
  const head = lines[0].split(',').map(s => s.trim())
  const ix = (k: string) => head.indexOf(k)
  const [it, io, ih, il, ic] = [ix('time'), ix('open'), ix('high'), ix('low'), ix('close')]
  const iv = ix('volume')
  const out: Candle[] = []
  for (let k = 1; k < lines.length; k++) {
    const p = lines[k].split(',')
    if (p.length < 5) continue
    out.push({
      time: Number(p[it]), open: Number(p[io]), high: Number(p[ih]),
      low: Number(p[il]), close: Number(p[ic]),
      volume: iv >= 0 ? Number(p[iv]) : 0,
    })
  }
  return out
}

type Fail = { check: string; detail: string }

function checkCard(card: string): { card: string; fails: Fail[]; stats: Record<string, string> } {
  const refPath = `${ROOT}results/_s1520_parity/${card}.json`
  const ref: Ref = JSON.parse(fs.readFileSync(refPath, 'utf8'))
  const cardId = card.replace('_', '-')
  const wired = cardId in S1520_CFG
  const cfg = wired ? S1520_CFG[cardId] : NEG_CFG[cardId]
  if (!cfg) throw new Error(`no config (wired or negative-control) for ${cardId}`)

  const candles = loadCandles(card)
  const fails: Fail[] = []
  const stats: Record<string, string> = {}

  // --- چکِ ۰: طولِ داده باید با مرجع یکی باشد، وگرنه بقیهٔ چک‌ها بی‌معنی‌اند
  if (candles.length !== ref.bars) {
    fails.push({ check: 'bars', detail: `ts=${candles.length} py=${ref.bars}` })
    return { card, fails, stats }
  }
  stats.bars = String(candles.length)

  // --- سری‌ها روی کلِ تاریخ (تلهٔ روش‌شناسی)، مقایسه فقط روی دنباله
  const f = s1520Features(candles, cfg)
  const atr = atrWilderS1520(candles, cfg.atrP)

  let maxdPMax = 0, maxdRho = 0, maxdAtr = 0
  let nFreshMismatch = 0, nGatedMismatch = 0
  let firstFreshMismatch = -1, firstGatedMismatch = -1

  for (const r of ref.series) {
    const i = r.i
    // ① priorMax
    if (r.priorMax !== null && isFinite(f.priorMax[i])) {
      maxdPMax = Math.max(maxdPMax, Math.abs(f.priorMax[i] - r.priorMax))
    } else if ((r.priorMax === null) !== !isFinite(f.priorMax[i])) {
      fails.push({ check: 'priorMax-nullness', detail: `bar ${i}: ts=${f.priorMax[i]} py=${r.priorMax}` })
    }
    // ① rho
    maxdRho = Math.max(maxdRho, Math.abs(f.rho[i] - r.rho))
    // ① atr
    if (r.atr !== null) maxdAtr = Math.max(maxdAtr, Math.abs(atr[i] - r.atr))
    // ② پرچم‌ها
    if (f.fresh[i] !== r.fresh) { nFreshMismatch++; if (firstFreshMismatch < 0) firstFreshMismatch = i }
    if (f.gated[i] !== r.gated) { nGatedMismatch++; if (firstGatedMismatch < 0) firstGatedMismatch = i }
  }

  stats['max|dPriorMax|'] = maxdPMax.toExponential(2)
  stats['max|dRho|'] = maxdRho.toExponential(2)
  stats['max|dAtr|'] = maxdAtr.toExponential(2)

  if (maxdPMax > TOL_PRICE) fails.push({ check: 'priorMax', detail: `max|d|=${maxdPMax.toExponential(3)} > ${TOL_PRICE}` })
  if (maxdRho > TOL_RHO) fails.push({ check: 'rho', detail: `max|d|=${maxdRho.toExponential(3)} > ${TOL_RHO}` })
  if (maxdAtr > TOL_ATR) fails.push({ check: 'atr', detail: `max|d|=${maxdAtr.toExponential(3)} > ${TOL_ATR}` })
  if (nFreshMismatch) fails.push({ check: 'fresh-flag', detail: `${nFreshMismatch} mismatches, first at bar ${firstFreshMismatch}` })
  if (nGatedMismatch) fails.push({ check: 'gated-flag', detail: `${nGatedMismatch} mismatches, first at bar ${firstGatedMismatch}` })

  // --- ③ مقایسهٔ **مجموعه‌ای** سیگنال‌ها روی کلِ تاریخ (نه فقط دنباله)
  const tsIdx: number[] = []
  for (let i = 0; i < candles.length; i++) if (f.gated[i]) tsIdx.push(i)
  const pySet = new Set(ref.signalIdx)
  const tsSet = new Set(tsIdx)
  const missing = ref.signalIdx.filter(i => !tsSet.has(i))
  const extra = tsIdx.filter(i => !pySet.has(i))
  stats.signals = `ts=${tsIdx.length} py=${ref.signalIdx.length}`
  stats.gatePassRate = `${ref.counts.gatePassRatePct}%`
  if (missing.length) fails.push({ check: 'signals-missing', detail: `${missing.length} py signals absent in TS, first=${missing[0]}` })
  if (extra.length) fails.push({ check: 'signals-extra', detail: `${extra.length} TS signals absent in py, first=${extra[0]}` })

  // شمارشِ لبه‌های تازه هم مستقلاً (تا اگر گیت درست ولی رویداد غلط بود، دیده شود)
  let nFresh = 0
  for (let i = 0; i < candles.length; i++) if (f.fresh[i]) nFresh++
  stats.fresh = `ts=${nFresh} py=${ref.counts.fresh}`
  if (nFresh !== ref.counts.fresh) fails.push({ check: 'fresh-count', detail: `ts=${nFresh} py=${ref.counts.fresh}` })

  // --- ④ هندسهٔ منجمد
  const dSl = Math.abs(cfg.slPip - ref.geometry.slPip)
  const dTp = Math.abs(cfg.tpPip - ref.geometry.tpPip)
  stats.geometry = `SL ${cfg.slPip} vs ${ref.geometry.slPip.toFixed(2)} · TP ${cfg.tpPip} vs ${ref.geometry.tpPip.toFixed(2)}`
  // مرجع با ۴ رقم گرد شده و CFG با ۲ رقم ⇒ رواداریِ نیم‌صدم pip
  if (dSl > 0.005 + TOL_PIP) fails.push({ check: 'slPip', detail: `cfg=${cfg.slPip} ref=${ref.geometry.slPip}` })
  if (dTp > 0.005 + TOL_PIP) fails.push({ check: 'tpPip', detail: `cfg=${cfg.tpPip} ref=${ref.geometry.tpPip}` })

  // --- ⑤ شاهدِ منفیِ MTF
  const shouldBeWired = card === 'XAUUSD_H8'
  stats.wiring = wired ? 'WIRED' : 'not wired (negative control)'
  if (shouldBeWired && !wired) {
    fails.push({ check: 'mtf-wiring', detail: 'H8 is the ACCEPT card (90.6) but is MISSING from S1520_CFG' })
  }
  if (!shouldBeWired && wired) {
    fails.push({
      check: 'mtf-negative-control',
      detail: `${cardId} is present in S1520_CFG but its verdict is NOT ACCEPT ` +
        `(H4=REJECT 16.7, H12=UNPROVEN 27.1) — forbidden generalisation`,
    })
  }

  return { card, fails, stats }
}

function main() {
  const only = process.argv[2]
  const cards = (only ? [only] : ['H8', 'H4', 'H12']).map(s =>
    s.startsWith('XAUUSD') ? s : `XAUUSD_${s}`)

  console.log('=== S1520 parity: TS port vs python reference (frozen verdict machinery) ===')
  console.log(`reference: results/_s1520_parity/  ·  rule: fresh-high(90) x signed rho >= 0.618, LONG-only`)
  console.log('')

  let allFails = 0
  for (const card of cards) {
    const { fails, stats } = checkCard(card)
    const wiredMark = card === 'XAUUSD_H8' ? 'ACCEPT 90.6 -> WIRED' : 'not accepted -> negative control'
    console.log(`--- ${card}  (${wiredMark})`)
    for (const [k, v] of Object.entries(stats)) console.log(`    ${k.padEnd(16)} ${v}`)
    if (fails.length === 0) {
      console.log('    RESULT           GREEN (all 5 checks pass)')
    } else {
      console.log(`    RESULT           RED (${fails.length} failure(s))`)
      for (const f of fails) console.log(`      x ${f.check}: ${f.detail}`)
    }
    console.log('')
    allFails += fails.length
  }

  if (allFails === 0) {
    console.log('PARITY GREEN — the TypeScript port reproduces the python verdict machinery')
    console.log('exactly on series, event flags, signal sets and geometry, and the MTF')
    console.log('negative control holds (H4/H12 port correctly yet stay unwired).')
    process.exit(0)
  }
  console.log(`PARITY RED — ${allFails} failure(s). Do NOT wire the layer until this is green.`)
  process.exit(1)
}

main()

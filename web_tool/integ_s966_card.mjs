// ---------------------------------------------------------------------------
// integ_s966_card.mjs — آزمونِ **یکپارچگیِ کارت** برای S966 (XAUUSD-H8).
//
// پریتی (`parity_s966_signal.mjs`) ثابت کرد خودِ *ماژول* درست است. این فایل
// چیزِ دیگری را ثابت می‌کند: **سیم‌کشی**. یعنی `runCard('XAUUSD-H8')` — همان
// تابعی که `/api/decision` صدا می‌زند — واقعاً S966 را اجرا می‌کند و نتیجه‌اش
// در تصمیمِ کارت (primary یا otherLayers) دیده می‌شود.
//
// چرا لازم است؟ چون یک لایه می‌تواند بی‌عیب باشد ولی هرگز صدا زده نشود
// (import شده، آداپتر ساخته شده، ولی به CARD_LAYERS اضافه نشده). آن حالت در
// UI عیناً شبیهِ «سیگنالی نیست» دیده می‌شود و می‌تواند **بی‌صدا** پنهان بماند.
// درسِ ثبت‌شدهٔ پروژه (S382): «مدرکِ اتصال، نه ادعای اتصال».
//
// روش: کندل‌های واقعیِ H8 از فیکسچرِ پریتی (که خودش از data/mt5_full ساخته شد)
// برداشته می‌شود و کارت روی سه نوع نقطه اجرا می‌شود:
//   ① بارهایی که مرجعِ پایتون سیگنالِ S966 دارد  ⇒ باید S966 در کارت دیده شود
//   ② بارهایی که S965 شلیک کرده ولی درفت مخالف بود ⇒ S966 نباید ENTRY باشد
//   ③ بارهای بی‌سیگنال ⇒ S966 نباید ENTRY باشد
// همچنین شمارشِ لایه‌های کارت چک می‌شود (باید ۴ باشد: S950, S965, S770, S966).
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import { CARD_LAYERS, runCard } from './src/strategy_registry.ts'
import { S966_CFG } from './src/kyle_permanence_drift_s966.ts'

const FX = JSON.parse(fs.readFileSync('../results/_scan_S966/parity_h8_fixture.json', 'utf8'))
const CARD = 'XAUUSD-H8'
const cfg = S966_CFG[CARD]

// ---- ۱) کارت باید ۴ لایه داشته باشد و S966 جزوِ آن‌ها باشد ----------------
const layers = CARD_LAYERS[CARD] || []
console.log(`\n════════ INTEG S966 — card ${CARD} ════════`)
console.log(`① card layer count = ${layers.length}`)

// ---- ساختِ AnalysisResult حداقلی (لایه فقط price را از آن می‌خواند) --------
function mkAnalysis(price) {
  return {
    price, atr: 0, ema50: 0, ema200: 0, vwap: 0, rsi14: 50, adx: 0, macdHist: 0,
    trend: 'range', regimeOk: false, activeBrain: 'none', direction: 'NONE',
    probability: 0, entryThreshold: 0, noEntryReason: '', confidence: 'low',
    scoreBreakdown: [], entry: null, tp: null, sl: null, rr: '—',
    levels: [], resistance: null, support: null,
  }
}

function runAt(i) {
  // کندل‌های تا و شاملِ i (عینِ سایت: آخرین کندلِ **بسته**)
  const candles = FX.candles.slice(0, i + 1)
  const last = candles[candles.length - 1]
  const ctx = {
    cardId: CARD,
    a: mkAnalysis(last.close),
    candles,
    utcHour: new Date(last.time * 1000).getUTCHours(),
    times: candles.map(c => c.time),
    capital: 10000,
    riskPct: 1.0,
  }
  return runCard(ctx)
}

// کدهای همهٔ لایه‌هایی که در تصمیمِ کارت دیده می‌شوند
function codesIn(dec) {
  const out = []
  if (dec?.sourceLayer?.code) out.push({ code: dec.sourceLayer.code, state: dec.state, primary: true })
  for (const o of dec?.otherLayers || []) out.push({ code: o.code, state: o.state, primary: false })
  return out
}

const py = FX.py
// دروازهٔ دادهٔ لایه: درفتِ K=180 به close[t−181] نگاه می‌کند ⇒ کفِ 182 کندل.
const FLOOR = cfg.driftK + 2
const sigBars = [...py.idx_long.map(i => ({ i, dir: 'LONG' })),
                 ...py.idx_short.map(i => ({ i, dir: 'SHORT' }))]
  .filter(x => x.i >= FLOOR)
  .sort((a, b) => a.i - b.i)

// ---- ② روی بارهای سیگنالِ مرجع، S966 باید در کارت حاضر و ENTRY باشد -------
let seen = 0, entry = 0, dirOk = 0
const rows = []
for (const s of sigBars) {
  const dec = runAt(s.i)
  const found = codesIn(dec).find(x => x.code === 'S966')
  if (found) {
    seen++
    if (found.state === 'ENTRY') entry++
    // جهت: اگر primary باشد از dec، وگرنه از otherLayers
    const d = found.primary ? dec.direction
      : (dec.otherLayers || []).find(o => o.code === 'S966')?.direction
    if (d === s.dir) dirOk++
    rows.push(`   bar ${s.i} → S966 ${found.state} ${d || '—'} (expect ENTRY ${s.dir})${found.primary ? ' [primary]' : ' [otherLayers]'}`)
  } else {
    rows.push(`   bar ${s.i} → ❌ S966 ABSENT from card decision`)
  }
}
console.log(`② signal bars (i ≥ ${FLOOR}) = ${sigBars.length}`)
rows.forEach(r => console.log(r))
console.log(`   S966 present=${seen}/${sigBars.length} · ENTRY=${entry}/${sigBars.length} · direction ok=${dirOk}/${sigBars.length}`)

// ---- ③ کنترلِ دروازه: S965 شلیک کرد ولی درفت مخالف ⇒ S966 نباید ENTRY باشد --
const baseAll = [...py.base_long.map(i => ({ i, dir: 'LONG' })),
                 ...py.base_short.map(i => ({ i, dir: 'SHORT' }))]
const alignedSet = new Set([...py.idx_long, ...py.idx_short])
const blockedBars = baseAll.filter(x => x.i >= FLOOR && !alignedSet.has(x.i))
let leak = 0
for (const b of blockedBars) {
  const dec = runAt(b.i)
  const found = codesIn(dec).find(x => x.code === 'S966')
  if (found && found.state === 'ENTRY') leak++
}
console.log(`③ GATE control via card: base-fired-but-drift-opposed bars = ${blockedBars.length} · S966 ENTRY leak = ${leak}`)

// ---- ④ کنترلِ منفی: بارهای بی‌سیگنال ⇒ S966 نباید ENTRY باشد ---------------
const allSig = new Set([...py.base_long, ...py.base_short])
let checked = 0, falsePos = 0
for (let i = FX.candles.length - 1; i >= FLOOR && checked < 120; i -= 7) {
  if (allSig.has(i)) continue
  checked++
  const dec = runAt(i)
  const found = codesIn(dec).find(x => x.code === 'S966')
  if (found && found.state === 'ENTRY') falsePos++
}
console.log(`④ negative control: checked=${checked} · S966 false ENTRY = ${falsePos}`)

// ---- ⑤ گاردِ دادهٔ ناکافی: زیرِ کفِ ۱۸۲ کندل نباید ENTRY بسازد -------------
let shallowEntry = 0
for (const i of [40, 80, 120, 170]) {
  const dec = runAt(i)
  const found = codesIn(dec).find(x => x.code === 'S966')
  if (found && found.state === 'ENTRY') shallowEntry++
}
console.log(`⑤ shallow-feed guard (i < ${FLOOR}): false ENTRY = ${shallowEntry}`)

const pass = layers.length === 4
  && sigBars.length > 0 && seen === sigBars.length && entry === sigBars.length
  && dirOk === sigBars.length && leak === 0 && falsePos === 0 && shallowEntry === 0

console.log(pass
  ? '\n✅ INTEG PASS — S966 is genuinely wired into the XAUUSD-H8 card (not just imported)\n'
  : '\n❌ INTEG FAIL — S966 is not correctly reachable from runCard()\n')

fs.writeFileSync('../results/_scan_S966/integ_card_s966.json', JSON.stringify({
  what: 'آزمونِ یکپارچگیِ کارت: آیا runCard(XAUUSD-H8) واقعاً S966 را اجرا می‌کند؟',
  why: 'یک لایه می‌تواند بی‌عیب ولی وصل‌نشده باشد؛ آن حالت در UI شبیهِ «سیگنالی نیست» دیده می‌شود و بی‌صدا پنهان می‌ماند (درسِ S382).',
  card: CARD,
  card_layer_count: layers.length,
  card_layers_expected: ['S950', 'S965', 'S770', 'S966'],
  data_floor_bars: FLOOR,
  signal_bars: sigBars.length,
  s966_present: seen,
  s966_entry: entry,
  direction_ok: dirOk,
  gate_control: { blocked_bars: blockedBars.length, entry_leak: leak },
  negative_control: { checked, false_entry: falsePos },
  shallow_feed_guard: { false_entry: shallowEntry },
  verdict: pass ? 'PASS' : 'FAIL',
  date: '2026-09-05',
}, null, 1))
process.exit(pass ? 0 : 1)

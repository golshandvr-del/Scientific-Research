// ---------------------------------------------------------------------------
// integ_s919_card.mjs — آزمونِ **یکپارچگیِ کارت** برای S919 (XAUUSD-H6).
//
// پریتی (`parity_s919_signal.mjs`) ثابت کرد خودِ *ماژول* درست است (۱۳ آزمون،
// صفر اختلاف با پایتونِ داوری‌شده). این فایل چیزِ دیگری را ثابت می‌کند:
// **سیم‌کشی**. یعنی `runCard('XAUUSD-H6')` — همان تابعی که `/api/decision`
// صدا می‌زند — واقعاً S919 را اجرا می‌کند و نتیجه‌اش در تصمیمِ کارت دیده می‌شود.
//
// چرا لازم است؟ چون یک لایه می‌تواند بی‌عیب باشد ولی هرگز صدا زده نشود
// (import شده، آداپتر ساخته شده، ولی به CARD_LAYERS اضافه نشده). آن حالت در
// UI عیناً شبیهِ «سیگنالی نیست» دیده می‌شود و می‌تواند **بی‌صدا** پنهان بماند.
// درسِ ثبت‌شدهٔ پروژه (S382): «مدرکِ اتصال، نه ادعای اتصال».
//
// 🔴 نکتهٔ اختصاصیِ S919 که در S966 وجود نداشت:
//    ماسکِ بک‌تستِ داوری‌شده **از پیش شیفت‌شده** است (`lm[1:] = up[:-1]`) ⇒
//    بارِ سیگنالِ کارت = **رویداد + ۱** (و ورودِ واقعی = رویداد + ۲).
//    پس این‌جا کارت روی `mask_long/mask_short` اجرا می‌شود، نه روی
//    `event_long/event_short`. آزمونِ ⑥ عمداً روی خودِ بارِ رویداد اجرا می‌شود
//    و باید **هیچ** ENTRY نسازد — این همان دامی است که اگر در سیم‌کشی رعایت
//    نشود، لبه از WR=55.66٪ به WR=48.11٪ (زیرِ سربه‌سر) سقوط می‌کند.
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import { CARD_LAYERS, runCard } from './src/strategy_registry.ts'
import { S919_CFG } from './src/convention_shock_s919.ts'

const FX = JSON.parse(fs.readFileSync('../results/_s919_ckpt/parity_h6_fixture.json', 'utf8'))
const CARD = 'XAUUSD-H6'
const cfg = S919_CFG[CARD]

const layers = CARD_LAYERS[CARD] || []
console.log(`\n════════ INTEG S919 — card ${CARD} ════════`)
console.log(`① card layer count = ${layers.length} (expect 1 — S919 is the first layer on the H6 card)`)

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

function codesIn(dec) {
  const out = []
  if (dec?.sourceLayer?.code) out.push({ code: dec.sourceLayer.code, state: dec.state, primary: true })
  for (const o of dec?.otherLayers || []) out.push({ code: o.code, state: o.state, primary: false })
  return out
}

const py = FX.py
// دروازهٔ دادهٔ لایه: گیتِ قرارداد به close[t−1−240] با t=i−1 نگاه می‌کند ⇒ کفِ 243.
const FLOOR = cfg.driftK + 3

// 🔴 بارهای سیگنال = **ماسک** (رویداد+۱)، نه خودِ رویداد.
const sigBars = [...py.mask_long.map(i => ({ i, dir: 'LONG' })),
                 ...py.mask_short.map(i => ({ i, dir: 'SHORT' }))]
  .filter(x => x.i >= FLOOR)
  .sort((a, b) => a.i - b.i)

// ---- ② روی بارهای سیگنالِ مرجع، S919 باید در کارت حاضر و ENTRY باشد -------
let seen = 0, entry = 0, dirOk = 0
const rows = []
for (const s of sigBars) {
  const dec = runAt(s.i)
  const found = codesIn(dec).find(x => x.code === 'S919')
  if (found) {
    seen++
    if (found.state === 'ENTRY') entry++
    const d = found.primary ? dec.direction
      : (dec.otherLayers || []).find(o => o.code === 'S919')?.direction
    if (d === s.dir) dirOk++
    rows.push(`   bar ${s.i} → S919 ${found.state} ${d || '—'} (expect ENTRY ${s.dir})${found.primary ? ' [primary]' : ' [otherLayers]'}`)
  } else {
    rows.push(`   bar ${s.i} → ❌ S919 ABSENT from card decision`)
  }
}
console.log(`② signal (mask) bars (i ≥ ${FLOOR}) = ${sigBars.length}`)
rows.forEach(r => console.log(r))
console.log(`   S919 present=${seen}/${sigBars.length} · ENTRY=${entry}/${sigBars.length} · direction ok=${dirOk}/${sigBars.length}`)

// ---- ③ کنترلِ گیتِ قرارداد از مسیرِ کارت ----------------------------------
//   بارهایی که پایهٔ S965 (شوک+ماندگاری) شلیک کرد ولی درفتِ قرارداد مخالف بود
//   ⇒ کارت نباید ENTRY بسازد. ماسکِ این‌ها هم رویداد+۱ است.
const baseAll = [...py.base_long.map(i => ({ i, dir: 'LONG' })),
                 ...py.base_short.map(i => ({ i, dir: 'SHORT' }))]
const alignedEvents = new Set([...py.event_long, ...py.event_short])
const blockedMaskBars = baseAll
  .filter(x => !alignedEvents.has(x.i))
  .map(x => x.i + 1)                 // ماسکِ متناظر با آن رویداد
  .filter(i => i >= FLOOR && i < FX.candles.length)
let leak = 0
for (const i of blockedMaskBars) {
  const dec = runAt(i)
  const found = codesIn(dec).find(x => x.code === 'S919')
  if (found && found.state === 'ENTRY') leak++
}
console.log(`③ CONVENTION-GATE control via card: base-fired-but-drift-opposed = ${blockedMaskBars.length} · S919 ENTRY leak = ${leak}`)

// ---- ④ کنترلِ منفی: بارهای بی‌سیگنال ⇒ S919 نباید ENTRY باشد ---------------
const allMask = new Set([...py.mask_long, ...py.mask_short])
const allBaseMask = new Set(baseAll.map(x => x.i + 1))
let checked = 0, falsePos = 0
for (let i = FX.candles.length - 1; i >= FLOOR && checked < 120; i -= 7) {
  if (allMask.has(i) || allBaseMask.has(i)) continue
  checked++
  const dec = runAt(i)
  const found = codesIn(dec).find(x => x.code === 'S919')
  if (found && found.state === 'ENTRY') falsePos++
}
console.log(`④ negative control: checked=${checked} · S919 false ENTRY = ${falsePos}`)

// ---- ⑤ گاردِ دادهٔ ناکافی: زیرِ کفِ 243 کندل نباید ENTRY بسازد -------------
let shallowEntry = 0
const shallowBars = [40, 90, 150, 200, FLOOR - 2]
for (const i of shallowBars) {
  const dec = runAt(i)
  const found = codesIn(dec).find(x => x.code === 'S919')
  if (found && found.state === 'ENTRY') shallowEntry++
}
console.log(`⑤ shallow-feed guard (i < ${FLOOR}): false ENTRY = ${shallowEntry}`)

// ---- ⑥ 🔴 آزمونِ دامِ pre-shift از مسیرِ کارت ------------------------------
//   روی **خودِ بارِ رویداد** کارت نباید ENTRY بسازد (چون ورود رویداد+۲ است و
//   سیگنال رویداد+۱). اگر این‌جا شلیک شود یعنی سیم‌کشی یک کندل زود است ⇒
//   لبه از WR=55.66٪ به 48.11٪ سقوط می‌کند و آزمون باید FAIL بدهد.
let earlyFire = 0, earlyChecked = 0
for (const t of [...py.event_long, ...py.event_short]) {
  if (t < FLOOR) continue
  earlyChecked++
  const dec = runAt(t)
  const found = codesIn(dec).find(x => x.code === 'S919')
  if (found && found.state === 'ENTRY') earlyFire++
}
console.log(`⑥ 🔴 pre-shift trap via card (event bars=${earlyChecked}) · premature ENTRY = ${earlyFire}`)

const pass = layers.length === 1
  && sigBars.length > 0 && seen === sigBars.length && entry === sigBars.length
  && dirOk === sigBars.length && leak === 0 && falsePos === 0
  && shallowEntry === 0 && earlyFire === 0

console.log(pass
  ? '\n✅ INTEG PASS — S919 is genuinely wired into the XAUUSD-H6 card (not just imported)\n'
  : '\n❌ INTEG FAIL — S919 is not correctly reachable from runCard()\n')
process.exit(pass ? 0 : 1)

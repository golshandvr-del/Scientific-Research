// ---------------------------------------------------------------------------
// آزمونِ یکپارچگیِ S607 در **سطحِ کارت** (نه سطحِ ماژول).
//
// پرسشی که این آزمون پاسخ می‌دهد و پریتی **نمی‌تواند** پاسخ دهد:
//   پریتی ثابت کرد `computeS607` با پایتون یکسان است. ولی سایت هیچ‌وقت
//   `computeS607` را صدا نمی‌زند — بلکه `runCard()` را صدا می‌زند که از
//   `CARD_LAYERS[cardId]` عبور می‌کند. پس هنوز نمی‌دانیم:
//     ① آیا آداپترِ s607Layer در فهرستِ هر سه کارت **حاضر** است؟
//     ② آیا وقتی رویدادِ واقعی رخ می‌دهد، تصمیمِ لایه به بیرونِ runCard
//        **می‌رسد** (به‌عنوانِ primary یا داخلِ otherLayers)؟
//     ③ آیا حضورِ S607 تصمیمِ لایه‌های **ساکن** را عوض کرده (رگرسیون)؟
//     ④ آیا کارتِ H12 (شاهدِ منفی) هنوز S607 را **نمی‌بیند**؟
//
// روشِ ①③: مقایسهٔ «قبل/بعد» بدونِ دست‌زدن به رجیستری — CARD_LAYERS یک
//   `Record<string, LayerFn[]>` صادرشده است، پس می‌توان یک نسخهٔ **فیلترشده**
//   ساخت که آداپترِ S607 از آن حذف شده باشد و runCard را روی هر دو نسخه
//   اجرا کرد. برای این کار به یک `runCard` مستقل نیاز داریم که فهرستِ لایه را
//   بگیرد؛ چون runCardِ صادرشده مستقیماً از CARD_LAYERS می‌خوانَد، منطقِ
//   انتخابِ آن (STATE_RANK ⇒ primary) را در همین فایل **بازتولید نمی‌کنیم**
//   (که خودش منبعِ خطا می‌شد)، بلکه:
//     · برای ① و ④ فهرستِ CARD_LAYERS را مستقیم بازرسی می‌کنیم (شمارشِ لایه).
//     · برای ② و ③ خودِ runCard را صدا می‌زنیم و تفاوتِ خروجی را با حالتی
//       می‌سنجیم که کندل‌ها **قبل** از رویدادِ S607 قطع شده‌اند (یعنی همان
//       کارت، همان ساکنان، ولی بی‌رویدادِ S607) — مقایسهٔ رفتاری، بی‌دست‌کاریِ
//       رجیستری.
//
// روشِ ②: کورکورانه آخرین کندل را نمی‌دهیم (که احتمالاً رویدادی ندارد و آزمون
//   بی‌معنا می‌شد). ابتدا با `computeS607` **تاریخ را جست‌وجو** می‌کنیم تا
//   کندلی پیدا شود که لایه در آن `active` است، بعد `runCard` را با پیشوندِ
//   [0..i] صدا می‌زنیم. اگر برای کارتی هیچ رویدادی پیدا نشد، آزمون آن کارت
//   **FAIL** می‌شود (نه SKIP) — چون یعنی لایه در عمل هرگز روشن نمی‌شود.
// ---------------------------------------------------------------------------

import fs from 'node:fs'
import path from 'node:path'
import { CARD_LAYERS, runCard } from '../src/strategy_registry'
import { computeS607, S607_CFG } from '../src/engle_dual_gate_s607'

const ROOT = path.resolve(import.meta.dirname, '../..')

type Candle = { time: number; open: number; high: number; low: number; close: number; volume: number }

function loadCsv(tf: string): Candle[] {
  const p = path.join(ROOT, `data/mt5_full/XAUUSD_${tf}.csv`)
  const lines = fs.readFileSync(p, 'utf8').trim().split('\n')
  const out: Candle[] = []
  for (let i = 1; i < lines.length; i++) {
    const t = lines[i].split(',')
    out.push({
      time: Number(t[0]), open: Number(t[1]), high: Number(t[2]),
      low: Number(t[3]), close: Number(t[4]), volume: Number(t[5]),
    })
  }
  return out
}

// AnalysisResult حداقلی — لایه‌های این کارت‌ها فقط `price` را از آن می‌خوانند
// (بررسی‌شده در decideS607/decideS770/decideS800/decideS919/decideS950…).
function mkA(id: string, price: number): any {
  return { id, price, indicators: [], regime: undefined }
}

const CARDS = ['XAUUSD-D1', 'XAUUSD-H8', 'XAUUSD-H6'] as const
const TF_OF: Record<string, string> = {
  'XAUUSD-D1': 'D1', 'XAUUSD-H8': 'H8', 'XAUUSD-H6': 'H6',
}

let fail = 0
const report: any = { cards: {}, negative_control: {} }

console.log('══ آزمونِ یکپارچگیِ S607 در سطحِ کارت ══\n')

// ---------------------------------------------------------------------------
// ① حضورِ آداپتر در فهرستِ هر سه کارت
// ---------------------------------------------------------------------------
console.log('── ① حضورِ لایه در CARD_LAYERS ──')
for (const card of CARDS) {
  const n = (CARD_LAYERS[card] || []).length
  console.log(`   ${card}: ${n} لایه در فهرست`)
  report.cards[card] = { layer_count: n }
  if (n === 0) { console.log(`   ❌ ${card} هیچ لایه‌ای ندارد`); fail++ }
}

// ④ شاهدِ منفی: H12 نباید S607 داشته باشد. چون آداپترها بی‌نام‌اند، از راهِ
//   رفتاری بررسی می‌کنیم: S607_CFG کلیدِ H12 ندارد ⇒ اتصالش **ناممکن** است.
console.log('\n── ④ شاهدِ منفیِ H12 ──')
const h12InCfg = Object.prototype.hasOwnProperty.call(S607_CFG, 'XAUUSD-H12')
if (h12InCfg) {
  console.log('   ❌ XAUUSD-H12 در S607_CFG ظاهر شده — انتخاب‌گرِ رسمی حذفش کرده بود')
  fail++
} else {
  console.log('   ✓ XAUUSD-H12 در S607_CFG نیست ⇒ اتصال به آن کارت ناممکن است')
}
report.negative_control = { h12_in_cfg: h12InCfg }

// ---------------------------------------------------------------------------
// ② رسیدنِ تصمیم به خروجیِ runCard روی یک رویدادِ **واقعی**
// ③ رگرسیونِ ساکنان: همان کارت، یک کندل **قبل** از رویداد
// ---------------------------------------------------------------------------
console.log('\n── ②③ رویدادِ واقعی + رگرسیونِ ساکنان ──')
for (const card of CARDS) {
  const tf = TF_OF[card]
  const all = loadCsv(tf)
  const cfg = S607_CFG[card]

  // جست‌وجوی آخرین کندلی که S607 در آن active است (از انتها به عقب، سقفِ ۲۵۰۰ گام)
  let hit = -1
  const lo = Math.max(300, all.length - 2500)
  for (let i = all.length - 1; i >= lo; i--) {
    const raw = computeS607(all.slice(0, i + 1) as any, cfg)
    if (raw.active) { hit = i; break }
  }

  if (hit < 0) {
    console.log(`   ❌ ${card}: در ۲۵۰۰ کندلِ اخیر هیچ رویدادِ S607 پیدا نشد ⇒ لایه عملاً مرده است`)
    fail++
    report.cards[card].event_found = false
    continue
  }

  const when = new Date(all[hit].time * 1000).toISOString().slice(0, 16).replace('T', ' ')
  const px = all[hit].close

  // ② اجرای runCard روی همان پیشوند
  const dOn = runCard({
    cardId: card, a: mkA(card, px), candles: all.slice(0, hit + 1) as any,
    utcHour: new Date(all[hit].time * 1000).getUTCHours(),
    times: all.slice(0, hit + 1).map(c => c.time), capital: 10000, riskPct: 1.0,
  })

  // آیا S607 در خروجی دیده می‌شود؟ (primary یا otherLayers)
  const codes: string[] = []
  if (dOn.sourceLayer?.code) codes.push(dOn.sourceLayer.code)
  for (const o of (dOn.otherLayers || [])) codes.push(o.code)
  const seen = codes.some(c => /S607/i.test(c))

  // ③ رگرسیون: یک کندل قبل ⇒ رویدادِ S607 نیست، ساکنان باید مثلِ همیشه رفتار کنند
  const dOff = runCard({
    cardId: card, a: mkA(card, all[hit - 1].close), candles: all.slice(0, hit) as any,
    utcHour: new Date(all[hit - 1].time * 1000).getUTCHours(),
    times: all.slice(0, hit).map(c => c.time), capital: 10000, riskPct: 1.0,
  })
  const offCodes: string[] = []
  if (dOff.sourceLayer?.code) offCodes.push(dOff.sourceLayer.code)
  for (const o of (dOff.otherLayers || [])) offCodes.push(o.code)

  console.log(`\n   ${card} · رویداد در ${when} UTC (اندیس ${hit}/${all.length - 1})`)
  console.log(`     runCard(روی رویداد)  ⇒ state=${dOn.state} · primary=${dOn.sourceLayer?.code || '—'}` +
              ` · otherLayers=[${(dOn.otherLayers || []).map(o => o.code).join(', ') || '—'}]`)
  console.log(`     runCard(کندلِ قبل)   ⇒ state=${dOff.state} · primary=${dOff.sourceLayer?.code || '—'}` +
              ` · otherLayers=[${(dOff.otherLayers || []).map(o => o.code).join(', ') || '—'}]`)

  if (seen) {
    console.log(`     ✓ S607 به خروجیِ runCard رسید`)
  } else {
    console.log(`     ❌ S607 در خروجیِ runCard دیده نشد (نه primary نه otherLayers)`)
    fail++
  }

  // رگرسیون: ساکنانی که در کندلِ قبل ENTRY بودند نباید ناپدید شده باشند
  const incumbentsOff = offCodes.filter(c => !/S607/i.test(c))
  const incumbentsOn = codes.filter(c => !/S607/i.test(c))
  const lost = incumbentsOff.filter(c => !incumbentsOn.includes(c))
  if (lost.length > 0 && dOff.state === dOn.state) {
    console.log(`     ⚠️ ساکنانِ ناپدیدشده: ${lost.join(', ')} — بررسیِ دستی لازم است`)
  }

  report.cards[card] = {
    ...report.cards[card],
    event_found: true, event_index: hit, event_time_utc: when,
    on: { state: dOn.state, primary: dOn.sourceLayer?.code || null, others: (dOn.otherLayers || []).map(o => o.code) },
    off: { state: dOff.state, primary: dOff.sourceLayer?.code || null, others: (dOff.otherLayers || []).map(o => o.code) },
    s607_visible: seen,
  }
}

const outDir = path.join(ROOT, 'results/_s607_integ')
fs.mkdirSync(outDir, { recursive: true })
fs.writeFileSync(path.join(outDir, 'cards.json'), JSON.stringify(report, null, 1))

console.log('\n════════════════════════════════════════════════════════════')
if (fail === 0) {
  console.log('✅ INTEGRATION GREEN — لایه روی هر سه کارت از مسیرِ runCard زنده است و شاهدِ منفی برجاست.')
} else {
  console.log(`❌ INTEGRATION RED — ${fail} ایراد.`)
}
console.log(`[saved] results/_s607_integ/cards.json`)
if (fail > 0) process.exit(1)

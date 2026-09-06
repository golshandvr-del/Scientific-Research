// ---------------------------------------------------------------------------
// LIVE PROBE — آیا S607 روی **فیدِ واقعیِ سایت** محاسبه می‌شود؟
//
// چرا این آزمون لازم است و آزمون‌های قبلی کافی نیستند:
//   · پریتی روی دادهٔ **MT5** اجرا شد (۱۱۹۷۸ کندلِ H8) ⇒ ثابت کرد ریاضیات درست
//     است، ولی چیزی دربارهٔ **عمقِ فیدِ زنده** نمی‌گوید.
//   · آزمونِ یکپارچگی هم روی دادهٔ MT5 اجرا شد ⇒ همان محدودیت.
//   · اما سایتِ زنده کندل‌ها را از Yahoo با `interval=1h` می‌گیرد و بعد
//     `aggregateCandles(·, 24/8/6)` می‌زند. اگر عمقِ حاصل از کفِ لایه کمتر شود،
//     لایه صادقانه «دادهٔ ناکافی» می‌دهد و **هرگز روشن نمی‌شود** — یک لایهٔ
//     ACCEPTِ عملاً مرده، بدون هیچ خطایی در لاگ.
//
// روش: عیناً همان مسیرِ دادهٔ سایت را بازتولید می‌کنیم — `/api/candles` را از
//   سرورِ لوکال می‌گیریم (که خودش `fetchGold` را صدا زده) و با همان ضریبِ
//   تجمیعِ کارت جمع می‌کنیم، بعد `computeS607` را صدا می‌زنیم و می‌بینیم آیا
//   پیامِ «دادهٔ ناکافی» می‌دهد یا یک تصمیمِ واقعی (فعال یا خنثی).
//
// معیارِ قبولی (پیش‌ثبت‌شده، قبل از دیدنِ عدد):
//   ✅ PASS = هر سه کارت یک تصمیمِ **محاسبه‌شده** بدهند (کفِ داده تأمین شود).
//   ❌ FAIL = هر کارتی که به کفِ دادهٔ خودش نرسد ⇒ باید در README به‌عنوانِ
//      محدودیتِ صریح ثبت شود، نه پنهان بماند.
// ---------------------------------------------------------------------------

import fs from 'node:fs'
import path from 'node:path'
import { computeS607, S607_CFG } from '../src/engle_dual_gate_s607'

const ROOT = path.resolve(import.meta.dirname, '../..')
const BASE = process.env.PROBE_BASE || 'http://localhost:3000'

type Candle = { time: number; open: number; high: number; low: number; close: number; volume: number }

// بازتولیدِ aggregateCandles سایت (مرزِ t % (3600*f) == 0 — همان الگوی H4/H8/H6/D1)
function aggregate(src: Candle[], f: number): Candle[] {
  if (f <= 1) return src
  const out: Candle[] = []
  const sec = 3600 * f
  let cur: Candle | null = null
  for (const c of src) {
    const bucket = Math.floor(c.time / sec) * sec
    if (!cur || cur.time !== bucket) {
      if (cur) out.push(cur)
      cur = { time: bucket, open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume }
    } else {
      cur.high = Math.max(cur.high, c.high)
      cur.low = Math.min(cur.low, c.low)
      cur.close = c.close
      cur.volume += c.volume
    }
  }
  if (cur) out.push(cur)
  return out
}

const CARDS: Array<{ id: string; agg: number; floor: number }> = [
  { id: 'XAUUSD-D1', agg: 24, floor: 51 },
  { id: 'XAUUSD-H8', agg: 8, floor: 234 },
  { id: 'XAUUSD-H6', agg: 6, floor: 242 },
]

console.log('══ LIVE PROBE — S607 روی فیدِ واقعیِ سایت ══\n')
console.log(`پایه: ${BASE}\n`)

let fail = 0
const report: any = { base: BASE, at: new Date().toISOString(), cards: {} }

for (const card of CARDS) {
  const cfg = S607_CFG[card.id]
  let raw1h: Candle[] = []
  try {
    const r = await fetch(`${BASE}/api/candles?asset=${card.id}`)
    const j: any = await r.json()
    raw1h = (j.candles || j.data || []) as Candle[]
  } catch (e) {
    console.log(`   ❌ ${card.id}: دریافتِ کندل شکست — ${(e as Error).message}`)
    fail++
    continue
  }

  const agg = aggregate(raw1h, card.agg)
  const dec = computeS607(agg as any, cfg)

  // تشخیصِ «دادهٔ ناکافی»: ماژول در آن حالت active=false با پیامِ مشخص می‌دهد
  const insufficient = /دادهٔ کافی نیست/.test(dec.reason || '')
  const enough = agg.length >= card.floor

  console.log(`── ${card.id} ──`)
  console.log(`   کندلِ خامِ H1 از سایت : ${raw1h.length}`)
  console.log(`   بعد از تجمیعِ ×${card.agg}      : ${agg.length} کندلِ ${cfg.tfFa}`)
  console.log(`   کفِ لایه               : ${card.floor} ⇒ ${enough ? `✓ تأمین (حاشیه ${agg.length - card.floor})` : `❌ کمبودِ ${card.floor - agg.length}`}`)
  console.log(`   خروجیِ computeS607     : active=${dec.active} · ${insufficient ? '⚠️ دادهٔ ناکافی' : 'محاسبه شد'}`)
  if (!insufficient) console.log(`   دلیل                   : ${(dec.reason || '').slice(0, 110)}`)

  if (insufficient) {
    console.log(`   ❌ لایه روی این کارت **محاسبه نمی‌شود** ⇒ عملاً مرده`)
    fail++
  } else {
    console.log(`   ✓ لایه زنده است`)
  }
  console.log()

  report.cards[card.id] = {
    raw_1h: raw1h.length, aggregated: agg.length, agg_factor: card.agg,
    floor: card.floor, floor_met: enough, margin: agg.length - card.floor,
    computed: !insufficient, active: dec.active,
    reason: (dec.reason || '').slice(0, 200),
  }
}

const outDir = path.join(ROOT, 'results/_s607_integ')
fs.mkdirSync(outDir, { recursive: true })
fs.writeFileSync(path.join(outDir, 'liveprobe.json'), JSON.stringify(report, null, 1))

console.log('════════════════════════════════════════════════════════════')
if (fail === 0) {
  console.log('✅ LIVE PROBE PASS — هر سه کارت روی فیدِ واقعی کفِ داده را دارند و لایه محاسبه می‌شود.')
} else {
  console.log(`❌ LIVE PROBE FAIL — ${fail} کارت روی فیدِ زنده محاسبه نمی‌شود (باید در README ثبت شود).`)
}
console.log('[saved] results/_s607_integ/liveprobe.json')
if (fail > 0) process.exit(1)

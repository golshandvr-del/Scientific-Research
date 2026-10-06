// ---------------------------------------------------------------------------
// REPLAY — «چرا هیچ سیگنالی نمی‌بینم؟» (User Note، اندازه‌گیری نه حدس)
//
// روش: همان فیدِ زندهٔ سایت (`/api/candles` از سرورِ لوکال، با همان interval/range
//   و همان ضریبِ تجمیعِ GOLD_TF) گرفته می‌شود؛ سپس روی **هر کندلِ بستهٔ اخیر**
//   مسیرِ واقعیِ `runCard` (همان چیزی که decideAsset صدا می‌زند) بازپخش می‌شود.
//   برای هر کارت: چند بار ENTRY/APPROACHING داد، کدام لایه، آخرین بار کِی.
//   و برای هر لایه جداگانه: چند بار فعال شد و آیا پیامِ «دادهٔ ناکافی» داد.
//
// خروجی: results/_signal_drought/replay.json
// اجرا: PROBE_BASE=http://localhost:3000 npx tsx tools/_replay_signal_drought.mts
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import path from 'node:path'
import { CARD_LAYERS, runCard } from '../src/strategy_registry'
import { analyze } from '../src/signal'
import { aggregateCandles } from '../src/price/gold_source'

const ROOT = path.resolve(import.meta.dirname, '../..')
const BASE = process.env.PROBE_BASE || 'http://localhost:3000'
const REPLAY = parseInt(process.env.REPLAY_BARS || '400', 10)

const ALL_CARDS: Array<{ id: string; key?: string; interval: string; range: string; agg: number; gap: number }> = [
  { id: 'XAUUSD-M5', interval: '5m', range: '5d', agg: 1, gap: 300 },
  { id: 'XAUUSD', key: 'XAUUSD-M15', interval: '15m', range: '1mo', agg: 1, gap: 900 },
  { id: 'XAUUSD-M30', interval: '30m', range: '1mo', agg: 1, gap: 1800 },
  { id: 'XAUUSD-H1', interval: '1h', range: '3mo', agg: 1, gap: 3600 },
  { id: 'XAUUSD-H4', interval: '1h', range: '1y', agg: 4, gap: 14400 },
  { id: 'XAUUSD-H6', interval: '1h', range: '2y', agg: 6, gap: 21600 },
  { id: 'XAUUSD-H8', interval: '1h', range: '1y', agg: 8, gap: 28800 },
  { id: 'XAUUSD-H12', interval: '1h', range: '2y', agg: 12, gap: 43200 },
  { id: 'XAUUSD-D1', interval: '1h', range: '2y', agg: 24, gap: 86400 },
]
// ⚠️ کارتِ M15 شناسهٔ تاریخیِ `XAUUSD` دارد ولی کلیدِ رجیستری‌اش `XAUUSD-M15` است.
const ONLY = (process.env.CARDS || '').split(',').filter(Boolean)
const CARDS = ONLY.length ? ALL_CARDS.filter(c => ONLY.includes(c.id)) : ALL_CARDS

const iso = (t: number) => new Date(t * 1000).toISOString().slice(0, 16).replace('T', ' ')
const report: any = { base: BASE, at: new Date().toISOString(), replayBars: REPLAY, cards: {} }

for (const card of CARDS) {
  const r = await fetch(`${BASE}/api/candles?interval=${card.interval}&range=${card.range}`)
  const j: any = await r.json()
  let candles = (j.candles || []) as any[]
  if (card.agg > 1) candles = aggregateCandles(candles, card.agg)
  // کندلِ آخر (در حالِ شکل‌گیری) حذف ⇒ فقط کندل‌های بسته (معادلِ closedBars)
  const nowSec = Math.floor(Date.now() / 1000)
  if (candles.length && candles[candles.length - 1].time >= Math.floor(nowSec / card.gap) * card.gap) candles = candles.slice(0, -1)
  const KEY = card.key || card.id
  const layers = CARD_LAYERS[KEY] || []
  // ⚠️ کفِ ۳۲۰ کندل: برش‌های کوتاه‌تر «دادهٔ ناکافیِ» مصنوعی می‌دهند (سایت همیشه کلِ پنجره را دارد).
  const start = Math.max(320, candles.length - REPLAY)
  const perLayer: Record<string, { entry: number; approaching: number; insufficient: number; last?: string; lastDir?: string }> = {}
  const cardEvents: any[] = []
  for (let i = start; i < candles.length; i++) {
    const slice = candles.slice(0, i + 1)
    const last = slice[slice.length - 1]
    let a: any
    try { a = analyze(slice) } catch { continue }
    const ctx: any = { cardId: KEY, a, candles: slice, utcHour: new Date(last.time * 1000).getUTCHours(), times: slice.map((k: any) => k.time), capital: 10000, riskPct: 1 }
    for (const fn of layers) {
      let d: any = null
      try { d = fn(ctx) } catch { /* */ }
      if (!d) continue
      const code = d.sourceLayer?.code || fn.name || '?'
      const p = (perLayer[code] ||= { entry: 0, approaching: 0, insufficient: 0 })
      if (d.state === 'ENTRY') { p.entry++; p.last = iso(last.time); p.lastDir = d.direction }
      else if (d.state === 'APPROACHING') p.approaching++
      if (/ناکافی|insufficient/i.test(`${d.headline || ''} ${d.reason || ''}`)) p.insufficient++
    }
    const dec: any = runCard(ctx)
    if (dec.state === 'ENTRY') cardEvents.push({ bar: iso(last.time), dir: dec.direction, code: dec.sourceLayer?.code, entry: dec.entry, tp: dec.tp, sl: dec.sl })
  }
  // اپیزود = رشتهٔ کندل‌های پیاپیِ ENTRY با همان لایه/جهت (یک «رویداد»، نه N کندل)
  let episodes = 0, prevKey = '', prevIdx = -2
  const entryIdx = new Set<string>(cardEvents.map(e => e.bar))
  for (let i = start; i < candles.length; i++) {
    const b = iso(candles[i].time); const e = cardEvents.find(x => x.bar === b)
    const key = e ? `${e.code}|${e.dir}` : ''
    if (e && !(key === prevKey && prevIdx === i - 1)) episodes++
    if (e) { prevKey = key; prevIdx = i }
  }
  const replayed = candles.length - start
  const visibleFrac = replayed ? entryIdx.size / replayed : 0
  const spanDays = replayed ? (candles[candles.length - 1].time - candles[start].time) / 86400 : 0
  report.cards[card.id] = { bars: candles.length, replayed, spanDays: +spanDays.toFixed(1), entries: cardEvents.length, episodes, visibleFrac: +visibleFrac.toFixed(4), events: cardEvents.slice(-10), perLayer }
  console.log(`\n══ ${card.id} — ${candles.length} کندل، بازپخشِ ${replayed} (≈${spanDays.toFixed(1)} روز) ⇒ کندلِ ENTRY: ${cardEvents.length} · اپیزود: ${episodes} · سهمِ زمانِ نمایش: ${(visibleFrac*100).toFixed(1)}٪`)
  for (const [code, p] of Object.entries(perLayer)) console.log(`   ${code.padEnd(8)} ENTRY=${p.entry} APPR=${p.approaching} ناکافی=${p.insufficient} آخرین=${p.last || '—'} ${p.lastDir || ''}`)
  for (const e of cardEvents.slice(-3)) console.log(`   ↳ ${e.bar} ${e.code} ${e.dir} @${e.entry?.toFixed?.(2)} TP=${e.tp?.toFixed?.(2)} SL=${e.sl?.toFixed?.(2)}`)
}

const out = path.join(ROOT, 'results', '_signal_drought')
fs.mkdirSync(out, { recursive: true })
fs.writeFileSync(path.join(out, 'replay.json'), JSON.stringify(report, null, 2))
console.log('\n→ results/_signal_drought/replay.json')

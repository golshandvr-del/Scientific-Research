// ---------------------------------------------------------------------------
// AUDIT — هر رکوردِ دفترِ تاریخچه را با «دادهٔ تمیزِ نهایی» دوباره داوری می‌کند.
//
// پرسشِ کاربر: «چطور RQS2 را پاس کردند ولی سیگنالِ غلط می‌دهند؟»
// پاسخِ درست فقط با یک آزمون ممکن است: آیا سایت **همان قاعده‌ای را اجرا کرد که
// داوری شد؟** برای هر رکورد چهار سؤال، همه روی دادهٔ نهاییِ Yahoo (futures، بدونِ
// rebase، بدونِ ردیفِ تیک، فقط کندل‌های واقعاً بسته):
//   Q1  کندلی که سیگنال رویش نشست، در لحظهٔ ثبت واقعاً بسته بود؟
//   Q2  اگر فقط کندل‌های واقعاً بستهٔ همان لحظه را به همان لایه بدهیم، ENTRY می‌دهد؟
//   Q3  وقتی آن کندل واقعاً بسته شد، لایه روی آن ENTRY می‌دهد؟ (نسخهٔ «داوری‌شده»)
//   Q4  نتیجهٔ تمیز: اگر Q3 بله ⇒ از openِ کندلِ بعد با همان فاصلهٔ TP/SL چه شد؟
//
// اجرا: npx tsx tools/_audit_journal.mts [مسیرِ signals.json]
// خروجی: results/_signal_quality/journal_audit.json
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import path from 'node:path'
import { CARD_LAYERS } from '../src/strategy_registry'
import { analyze } from '../src/signal'
import { _fetchGoldRaw, aggregateCandles } from '../src/price/gold_source'

const ROOT = path.resolve(import.meta.dirname, '../..')
const file = process.argv[2] || path.join(ROOT, 'local-mobile', 'data', 'journal', 'signals.json')
const recs: any[] = JSON.parse(fs.readFileSync(file, 'utf8')).records

const TF: Record<string, { interval: string; range: string; agg: number; base: number }> = {
  'XAUUSD-M5': { interval: '5m', range: '5d', agg: 1, base: 300 },
  'XAUUSD-M15': { interval: '15m', range: '1mo', agg: 1, base: 900 },
  'XAUUSD-M30': { interval: '30m', range: '1mo', agg: 1, base: 1800 },
  'XAUUSD-H1': { interval: '1h', range: '3mo', agg: 1, base: 3600 },
  'XAUUSD-H4': { interval: '1h', range: '1y', agg: 4, base: 3600 },
  'XAUUSD-H6': { interval: '1h', range: '2y', agg: 6, base: 3600 },
  'XAUUSD-H8': { interval: '1h', range: '1y', agg: 8, base: 3600 },
  'XAUUSD-H12': { interval: '1h', range: '2y', agg: 12, base: 3600 },
  'XAUUSD-D1': { interval: '1h', range: '2y', agg: 24, base: 3600 },
}
const iso = (t: number) => new Date(t * 1000).toISOString().slice(5, 16).replace('T', ' ')
const cache: Record<string, any[]> = {}
async function clean(card: string) {
  if (cache[card]) return cache[card]
  const c = TF[card]
  const raw = (await _fetchGoldRaw(c.interval, c.range)).candles.filter(k => k.time % c.base === 0)  // بدونِ ردیفِ تیک
  cache[card] = c.agg > 1 ? aggregateCandles(raw, c.agg) : raw
  return cache[card]
}
function layerOn(card: string, code: string, bars: any[]) {
  const last = bars[bars.length - 1]
  const ctx: any = { cardId: card, a: analyze(bars), candles: bars, utcHour: new Date(last.time * 1000).getUTCHours(), times: bars.map(k => k.time), capital: 10000, riskPct: 1 }
  for (const fn of CARD_LAYERS[card] || []) {
    let d: any; try { d = fn(ctx) } catch { continue }
    if ((d?.sourceLayer?.code || '') === code) return d
  }
  return null
}

const out: any[] = []
for (const r of recs) {
  const bars = await clean(r.card)
  const barSec = TF[r.card].agg * TF[r.card].base
  const created = Math.floor(r.createdAt / 1000)
  const aligned = r.barTime % barSec === 0
  const q1 = aligned && r.barTime + barSec <= created
  // Q2: فقط کندل‌هایی که تا لحظهٔ ثبت واقعاً بسته بودند (+۱۰ دقیقه تأخیرِ Yahoo لحاظ نمی‌شود — سخاوتمندانه)
  const pre = bars.filter(k => k.time + barSec <= created)
  const d2 = pre.length > 300 ? layerOn(r.card, r.layer, pre) : null
  // Q3: کندلی که سیگنال مدعیِ آن بود (یا سطلِ دربرگیرنده‌اش)، وقتی کامل شد
  const bucket = Math.floor(r.barTime / barSec) * barSec
  const idx = bars.findIndex(k => k.time === bucket)
  const d3 = idx > 300 ? layerOn(r.card, r.layer, bars.slice(0, idx + 1)) : null
  const q3 = d3?.state === 'ENTRY' && d3.direction === r.direction
  // Q4: نتیجهٔ تمیز (futures، openِ کندلِ بعد، همان فاصله‌ها، کندلِ دوطرفه ⇒ SL)
  let q4: any = null
  if (q3 && bars[idx + 1]) {
    const long = r.direction === 'LONG', e = bars[idx + 1].open
    const tpD = Math.abs(r.tp - r.entry), slD = Math.abs(r.entry - r.sl)
    const hold = r.maxHoldBars || 500
    q4 = { status: 'OPEN' }
    for (let i = idx + 1, n = 0; i < bars.length && n < hold; i++, n++) {
      const b = bars[i]
      const hitSl = long ? b.low <= e - slD : b.high >= e + slD
      const hitTp = long ? b.high >= e + tpD : b.low <= e - tpD
      if (hitSl) { q4 = { status: 'SL', bars: n + 1 }; break }
      if (hitTp) { q4 = { status: 'TP', bars: n + 1 }; break }
      if (n + 1 >= hold) { q4 = { status: 'EXPIRED', pnl: +((long ? b.close - e : e - b.close) / 0.1).toFixed(1) }; break }
    }
  }
  const verdict = !q1 ? (q3 ? 'زودهنگام (روی کندلِ ناتمام) — قاعده بعداً واقعاً برقرار شد'
    : 'جعلی — روی دادهٔ ناتمام/معیوب؛ دادهٔ تمیز این سیگنال را نمی‌دهد')
    : (q3 ? 'معتبر' : 'ناسازگار با دادهٔ تمیز')
  const row = {
    seq: r.seq, card: r.card, layer: r.layer, dir: r.direction, bar: iso(r.barTime), created: iso(created),
    journalStatus: r.status, q1_barClosedAtSignal: q1, q1_barAligned: aligned,
    q2_firesOnTrulyClosedBars: d2 ? `${d2.state}${d2.direction ? ' ' + d2.direction : ''}` : 'n/a',
    q3_firesWhenBarComplete: q3, q4_cleanOutcome: q4, verdict,
  }
  out.push(row)
  console.log(`#${r.seq} ${r.tf} ${r.layer} ${r.direction} bar=${row.bar} ثبت=${row.created} | Q1 بسته؟ ${q1 ? '✓' : '✗'}${aligned ? '' : ' (ردیفِ تیک)'} | Q2 ${row.q2_firesOnTrulyClosedBars} | Q3 ${q3 ? '✓' : '✗'} | Q4 ${q4 ? JSON.stringify(q4) : '—'} | دفتر: ${r.status} ⇒ ${verdict}`)
}
const dir = path.join(ROOT, 'results', '_signal_quality')
fs.mkdirSync(dir, { recursive: true })
fs.writeFileSync(path.join(dir, 'journal_audit.json'), JSON.stringify({ at: new Date().toISOString(), source: file, rows: out }, null, 2))
console.log('→ results/_signal_quality/journal_audit.json')

// ---------------------------------------------------------------------------
// REPRO — «چرا تاریخچه پر از سیگنالِ غلط است؟» (اندازه‌گیری، نه حدس)
//
// کشف: Yahoo وقتی بازار باز است، آخرین کندل (در حالِ شکل‌گیری) را با **زمانِ تیکِ
//   زنده** (مثلاً 13:28:22) برمی‌گرداند، نه شروعِ سطل (13:15:00). شاهدِ زنده: BTC-USD
//   (بازارِ ۲۴/۷ — هر لحظه قابلِ بازتولید). شاهدِ تاریخی: ۱۹۵ کندلِ نا‌هم‌ترازِ M15 و
//   ۲۵۸ کندلِ M5 در local-mobile/data/history که همه OHLC تخت (o=h=l=c) و volume=0 دارند.
//
// زنجیرهٔ خرابی که این ابزار مرحله‌به‌مرحله بازتولید می‌کند:
//   ① rebaseFuturesToSpot: last.time (13:28:22) ≥ curBucketStart (13:15) ⇒ «همان کندلِ
//      جاری» فرض و فقط close=spot می‌شود (time همان 13:28:22 می‌ماند).
//   ② closedBars: last.time ≥ curBucketStart ⇒ حذف ⇒ ✓ درست.
//   ③ ولی وقتی **سطل عوض می‌شود** (مثلاً 13:30:10) و Yahoo هنوز کندلِ 13:30 را نداده،
//      تیکِ 13:28:22 دیگر «جاری» نیست ⇒ rebase یک کندلِ نوِ 13:30 می‌سازد و closedBars
//      **تیکِ 13:28:22 را به‌عنوانِ کندلِ بسته** نگه می‌دارد. حالا آرایه دو کندلِ
//      13:15 و 13:28:22 دارد که فاصله‌شان ۸۰۲s است، نه ۹۰۰ ⇒ هر لایه‌ای که با «فاصلهٔ
//      زمانیِ کندل‌ها» مرزِ روز/گپ می‌سازد (S408/S562/S560) یا با سری کار می‌کند،
//      روی یک کندلِ جعلیِ تخت تصمیم می‌گیرد.
//   ④ persistHistoryShadow همین کندلِ جعلی را روی دیسک می‌نویسد (۱۹۵ تا روی M15).
//
// اجرا:  npx tsx tools/_repro_tick_bar.mts
// خروجی: results/_signal_quality/tick_bar_repro.json
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import path from 'node:path'
import { rebaseFuturesToSpot, closedBars } from '../src/price/gold_source'

const ROOT = path.resolve(import.meta.dirname, '../..')
const iso = (t: number) => new Date(t * 1000).toISOString().slice(5, 19)
const out: any = { at: new Date().toISOString() }

// --- ① شاهدِ زنده: BTC-USD (۲۴/۷) ------------------------------------------
try {
  const r = await fetch('https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD?interval=15m&range=1d',
    { headers: { 'User-Agent': 'Mozilla/5.0' } })
  const j: any = await r.json()
  const ts: number[] = j.chart.result[0].timestamp
  const tail = ts.slice(-3).map(t => ({ t: iso(t), mod900: t % 900 }))
  out.liveYahooTail = tail
  console.log('① دمِ زندهٔ Yahoo (BTC-USD, 15m):', tail)
} catch (e: any) { out.liveYahooTail = 'fetch failed: ' + e?.message }

// --- ② بازتولیدِ قطعیِ زنجیره با ساعتِ ساختگی ---------------------------------
const realNow = Date.now
const mk = (t: number, p: number, v = 500) => ({ time: t, open: p, high: p + 1, low: p - 1, close: p, volume: v })
const T0 = Date.parse('2026-10-08T04:00:00Z') / 1000
const feed = [mk(T0 - 900, 4130), mk(T0, 4132), { ...mk(T0 + 467, 4136.5, 0), high: 4136.5, low: 4136.5 }] // تیکِ 04:07:47
const steps: any[] = []
for (const nowIso of ['2026-10-08T04:10:00Z', '2026-10-08T04:17:57Z']) {
  ;(Date as any).now = () => Date.parse(nowIso)
  const rb = rebaseFuturesToSpot(feed as any, { price: 4136.7, ageSec: 0, source: 'test' } as any, 900)
  const sig = closedBars(rb.candles, 900)
  const tail = sig.slice(-3).map(k => ({ t: iso(k.time), aligned: k.time % 900 === 0, flat: k.high === k.low, vol: k.volume }))
  const fake = tail.some(k => !k.aligned)
  steps.push({ now: nowIso, closedTail: tail, fakeClosedBar: fake })
  console.log(`② now=${nowIso.slice(11, 19)} ⇒ دمِ «کندل‌های بسته»:`, tail.map(k => `${k.t}${k.aligned ? '' : ' ⚠️جعلی'}`).join(' · '))
}
;(Date as any).now = realNow
out.deterministicRepro = steps

// --- ③ شاهدِ تاریخی روی دیسکِ همین سرور --------------------------------------
const hdir = path.join(ROOT, 'local-mobile', 'data', 'history')
const hist: any = {}
for (const [f, gap] of [['XAUUSD-M5.jsonl', 300], ['XAUUSD-M15.jsonl', 900], ['XAUUSD-M30.jsonl', 1800], ['XAUUSD-H1.jsonl', 3600]] as const) {
  const p = path.join(hdir, f)
  if (!fs.existsSync(p)) continue
  const rows = fs.readFileSync(p, 'utf8').trim().split('\n').filter(Boolean).map(l => JSON.parse(l))
  const bad = rows.filter((r: any) => r[0] % gap !== 0)
  const flat = bad.filter((r: any) => r[1] === r[2] && r[2] === r[3] && r[3] === r[4] && !(r[5] > 0))
  hist[f] = { total: rows.length, nonAligned: bad.length, nonAlignedFlatZeroVol: flat.length }
}
out.historyOnDisk = hist
console.log('③ کندل‌های جعلیِ ذخیره‌شده روی دیسک:', hist)

const dir = path.join(ROOT, 'results', '_signal_quality')
fs.mkdirSync(dir, { recursive: true })
fs.writeFileSync(path.join(dir, 'tick_bar_repro.json'), JSON.stringify(out, null, 2))
console.log('→ results/_signal_quality/tick_bar_repro.json')

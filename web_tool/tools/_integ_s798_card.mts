// ---------------------------------------------------------------------------
// آزمونِ یکپارچگیِ S798 در **سطحِ کارت** (XAUUSD-H8) — از مسیرِ واقعیِ runCard.
//   ① آداپتر در CARD_LAYERS['XAUUSD-H8'] حاضر است (۹ لایه) و CARD_LAYER_CODES هم‌گام است.
//   ② روی آخرین رویدادِ واقعیِ تاریخی (۲۰۲۶-۰۳-۲۳ ۰۸:۰۰، از مرجعِ پریتی) S798 به
//      خروجیِ runCard می‌رسد (sourceLayer یا otherLayers).
//   ③ هندسه: SL ≈ 1.618×ATR21[i−1] مرجعِ پایتون (پنجرهٔ ~۱ ساله؛ EMA از ابتدای پنجره
//      گرم می‌شود ⇒ تفاوتِ < 0.5٪ مجاز) و TP = SL (RR 1.0).
//   ④ قیدِ شاهدِ کاذب: S798 به‌عنوانِ شاهدِ کاذب حذف نمی‌شود (ممیزی CLEAR).
//   ⑤ شاهدِ منفیِ MTF: S798 روی هیچ کارتِ دیگری نیست.
//   ⑥ رگرسیون: تصمیمِ تک‌تکِ ۸ ساکنِ H8 با/بی S798 بی‌تغییر است، و primaryِ کارت
//      روی همین رویداد با/بی S798 یکی است اگر ساکنی روشن باشد.
// داده: H1 رسمیِ mt5_full → H8 با aggregateCandles (همان مسیرِ سایت).
// اجرا: npx tsx tools/_integ_s798_card.mts [--write]
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'
import { CARD_LAYERS, CARD_LAYER_CODES, runCard } from '../src/strategy_registry'
import { S798_CFG } from '../src/london_shock_s798'
import { aggregateCandles } from '../src/price/gold_source'

const ROOT = path.resolve(import.meta.dirname, '../..')
type Candle = { time: number; open: number; high: number; low: number; close: number; volume: number }

function loadH1(): Candle[] {
  const txt = zlib.gunzipSync(fs.readFileSync(path.join(ROOT, 'data/mt5_full/XAUUSD_H1.csv.gz'))).toString('utf8')
  const out: Candle[] = []
  for (const line of txt.trim().split('\n').slice(1)) {
    const p = line.trim().split(',')
    if (p.length < 6) continue
    out.push({ time: +p[0], open: +p[1], high: +p[2], low: +p[3], close: +p[4], volume: +p[5] })
  }
  return out
}

let fail = 0
const ok = (c: boolean, m: string) => { console.log(`   ${c ? '✓' : '❌'} ${m}`); if (!c) fail++ }
const card = 'XAUUSD-H8'
const report: any = { card }
const ref = JSON.parse(fs.readFileSync(path.join(ROOT, 'results/_s798_parity/XAUUSD_H8.json'), 'utf8'))
const EXPECT = ['S955', 'S965', 'S770', 'S966', 'S1911', 'S607', 'S1520', 'S589', 'S798']

console.log('══ آزمونِ یکپارچگیِ S798 در سطحِ کارت (H8) ══')
const nLayers = (CARD_LAYERS[card] || []).length
report.layer_count = nLayers
ok(nLayers === 9, `① ${nLayers} لایه روی H8 (انتظار ۹)`)
ok(JSON.stringify(CARD_LAYER_CODES[card]) === JSON.stringify(EXPECT), `① CARD_LAYER_CODES = ${CARD_LAYER_CODES[card]}`)
ok(JSON.stringify(Object.keys(S798_CFG)) === '["XAUUSD-H8"]', '⑤ S798_CFG فقط H8')
const others = Object.entries(CARD_LAYER_CODES).filter(([k, v]) => k !== card && v.includes('S798')).map(([k]) => k)
ok(others.length === 0, `⑤ S798 روی کارتِ دیگری نیست (${others.join(',') || '—'})`)

const all = aggregateCandles(loadH1() as any, 8) as Candle[]
const tLast = ref.signal_times[ref.signal_times.length - 1]
const hit = all.findIndex(c => c.time === tLast)
ok(hit > 0, `② رویدادِ مرجع پیدا شد: ${new Date(tLast * 1000).toISOString()}`)
const sl = all.slice(Math.max(0, hit + 1 - 900), hit + 1)   // ≈ فیدِ زندهٔ H8 (range=1y ≈ ۹۰۴ کندل)
const ctx: any = {
  cardId: card, a: { id: card, price: all[hit].close, indicators: [], regime: undefined },
  candles: sl, utcHour: new Date(tLast * 1000).getUTCHours(),
  times: sl.map(c => c.time), capital: 10000, riskPct: 1.0,
}
const d: any = runCard(ctx)
const codes = [d.sourceLayer?.code, ...(d.otherLayers || []).map((o: any) => o.code)].filter(Boolean)
report.event = { utc: new Date(tLast * 1000).toISOString(), close: all[hit].close, window_bars: sl.length }
report.codes_on = codes
report.state = d.state
report.primary = d.sourceLayer?.code
console.log(`   خروجی: [${codes.join(', ')}] · state=${d.state} · primary=${d.sourceLayer?.code}`)
ok(codes.includes('S798'), '② S798 به خروجیِ runCard می‌رسد')

const raw: any = CARD_LAYERS[card].map(fn => fn(ctx)).find((x: any) => x?.sourceLayer?.code === 'S798')
const refSl = ref.signal_sl_usd[ref.signal_sl_usd.length - 1]
if (raw && raw.entry && raw.sl && raw.tp) {
  const slOut = Math.abs(raw.entry - raw.sl), tpOut = Math.abs(raw.tp - raw.entry)
  report.sl_usd_out = slOut; report.tp_usd_out = tpOut; report.sl_usd_ref = refSl
  ok(Math.abs(slOut - refSl) / refSl < 0.005, `③ SL=${slOut.toFixed(3)}$ در برابرِ مرجع ${refSl.toFixed(3)}$`)
  ok(Math.abs(tpOut / slOut - 1) < 1e-6, `③ TP/SL = ${(tpOut / slOut).toFixed(4)}`)
  ok(raw.direction === (ref.signal_dirs[ref.signal_dirs.length - 1] > 0 ? 'LONG' : 'SHORT'), `③ جهت = ${raw.direction}`)
} else ok(false, '③ تصمیمِ خامِ S798 entry/sl/tp ندارد')

const fw = (d.falseWitness || []).map((x: any) => x.code)
report.false_witness_dropped = fw
ok(!fw.includes('S798'), `④ S798 به‌عنوانِ شاهدِ کاذب حذف نشد (dropped=[${fw.join(',')}])`)

const snap = (fns: any[]) => fns.map(fn => { try { const x: any = fn(ctx); return x ? `${x.sourceLayer?.code}:${x.state}:${x.direction || '—'}` : null } catch { return 'ERR' } })
  .filter(Boolean).filter((s: any) => !/^S798:/.test(s)).sort()
const backup = CARD_LAYERS[card]
const snapOn = snap(backup)
CARD_LAYERS[card] = backup.filter(fn => (fn(ctx) as any)?.sourceLayer?.code !== 'S798')
let snapOff: any[] = []
let primaryOff: string | undefined
try {
  snapOff = snap(CARD_LAYERS[card]); ok(CARD_LAYERS[card].length === 8, '⑥ فیلتر دقیقاً یک لایه را جدا کرد')
  primaryOff = (runCard(ctx) as any).sourceLayer?.code
} finally { CARD_LAYERS[card] = backup }
report.incumbents = snapOff
report.primary_without_s798 = primaryOff
ok(JSON.stringify(snapOn) === JSON.stringify(snapOff), `⑥ ساکنان بی‌تغییر: [${snapOff.join(' | ')}]`)
const incumbentFires = codes.some(c => c !== 'S798')
ok(!incumbentFires || primaryOff === d.sourceLayer?.code,
  `⑥ primary با/بی S798: ${primaryOff} / ${d.sourceLayer?.code} (ساکنِ روشن: ${incumbentFires ? 'بله' : 'خیر'})`)

report.status = fail === 0 ? 'GREEN' : 'RED'
report.fails = fail
if (process.argv.includes('--write')) {
  fs.mkdirSync(path.join(ROOT, 'results/_s798'), { recursive: true })
  fs.writeFileSync(path.join(ROOT, 'results/_s798/integ_card.json'), JSON.stringify(report, null, 1))
}
console.log(fail === 0 ? '\n✅ GREEN' : `\n❌ RED — ${fail}`)
process.exit(fail === 0 ? 0 : 1)

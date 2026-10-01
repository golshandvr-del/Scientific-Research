// ---------------------------------------------------------------------------
// آزمونِ یکپارچگیِ S759 در **سطحِ کارت** (XAUUSD-H4) — از مسیرِ واقعیِ runCard.
//   ① آداپتر در CARD_LAYERS['XAUUSD-H4'] حاضر است (۵ لایه) و CARD_LAYER_CODES هم‌گام است.
//   ② روی آخرین رویدادِ واقعیِ تاریخی (۲۰۲۶-۰۳-۳۱ ۱۶:۰۰، از مرجعِ پریتی)، S759 به
//      خروجیِ runCard می‌رسد (sourceLayer یا otherLayers).
//   ③ هندسهٔ رسیده به تصمیم = 1.45×ATR89 روی همان کندل (عددِ مرجعِ پایتون) و TP=1.618×SL.
//   ④ قیدِ شاهدِ کاذب: S759 در هیچ جفتِ FALSE_WITNESS حذف نمی‌شود (ممیزی CLEAR بود) ⇒
//      falseWitness خروجی نباید S759 را حذف‌شده گزارش کند.
//   ⑤ شاهدِ منفیِ MTF: S759 روی هیچ کارتِ دیگری نیست (H3/H6/H8 REJECT).
//   ⑥ رگرسیون: تصمیمِ تک‌تکِ ساکنانِ H4 با/بی S759 بی‌تغییر است.
// داده: H1 رسمیِ mt5_full → H4 (همان تجمیعِ پریتی و سایت).
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'
import { CARD_LAYERS, CARD_LAYER_CODES, runCard } from '../src/strategy_registry'
import { S759_CFG } from '../src/informed_structure_s759'

const ROOT = path.resolve(import.meta.dirname, '../..')
type Candle = { time: number; open: number; high: number; low: number; close: number; volume: number }

function loadH4(): Candle[] {
  const txt = zlib.gunzipSync(fs.readFileSync(path.join(ROOT, 'data/mt5_full/XAUUSD_H1.csv.gz'))).toString('utf8')
  const out: Candle[] = []
  let cur: Candle | null = null
  for (const line of txt.trim().split('\n').slice(1)) {
    const p = line.trim().split(',')
    const t = +p[0], o = +p[1], h = +p[2], l = +p[3], c = +p[4], v = +p[5]
    const b = Math.floor(t / 14400) * 14400
    if (!cur || cur.time !== b) { if (cur) out.push(cur); cur = { time: b, open: o, high: h, low: l, close: c, volume: v } }
    else { cur.high = Math.max(cur.high, h); cur.low = Math.min(cur.low, l); cur.close = c; cur.volume += v }
  }
  if (cur) out.push(cur)
  return out
}

let fail = 0
const ok = (c: boolean, m: string) => { console.log(`   ${c ? '✓' : '❌'} ${m}`); if (!c) fail++ }
const card = 'XAUUSD-H4'
const report: any = { card }
const ref = JSON.parse(fs.readFileSync(path.join(ROOT, 'results/_s759_parity/XAUUSD_H4.json'), 'utf8'))

console.log('══ آزمونِ یکپارچگیِ S759 در سطحِ کارت (H4) ══')
const nLayers = (CARD_LAYERS[card] || []).length
report.layer_count = nLayers
ok(nLayers === 5, `① ${nLayers} لایه روی H4 (انتظار ۵)`)
ok(JSON.stringify(CARD_LAYER_CODES[card]) === JSON.stringify(['S382', 'S589', 'S759', 'S547', 'S1516']),
  `① CARD_LAYER_CODES = ${CARD_LAYER_CODES[card]}`)
ok(JSON.stringify(Object.keys(S759_CFG)) === '["XAUUSD-H4"]', '⑤ S759_CFG فقط H4')
const others = Object.entries(CARD_LAYER_CODES).filter(([k, v]) => k !== card && v.includes('S759')).map(([k]) => k)
ok(others.length === 0, `⑤ S759 روی کارتِ دیگری نیست (${others.join(',') || '—'})`)

const all = loadH4()
const tLast = ref.sig_times[ref.sig_times.length - 1]
const hit = all.findIndex(c => c.time === tLast)
ok(hit > 0, `② رویدادِ مرجع پیدا شد: ${new Date(tLast * 1000).toISOString()}`)
const sl = all.slice(Math.max(0, hit + 1 - 1500), hit + 1)   // پنجره‌ای هم‌اندازهٔ فیدِ زنده (~۱ سال H1)
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
ok(codes.includes('S759'), '② S759 به خروجیِ runCard می‌رسد')

const raw: any = CARD_LAYERS[card].map(fn => fn(ctx)).find((x: any) => x?.sourceLayer?.code === 'S759')
const refSl = ref.sig_sl_usd[ref.sig_sl_usd.length - 1]
if (raw && raw.entry && raw.sl && raw.tp) {
  const slOut = Math.abs(raw.entry - raw.sl), tpOut = Math.abs(raw.tp - raw.entry)
  report.sl_usd_out = slOut; report.tp_usd_out = tpOut; report.sl_usd_ref = refSl
  // پنجرهٔ ۱۵۰۰ کندلی ATRِ وایلدر را از ابتدای پنجره گرم می‌کند ⇒ تفاوتِ ناچیز با سریِ کامل مجاز (<0.5٪)
  ok(Math.abs(slOut - refSl) / refSl < 0.005, `③ SL=${slOut.toFixed(3)}$ در برابرِ مرجع ${refSl.toFixed(3)}$`)
  ok(Math.abs(tpOut / slOut - 1.618) < 1e-6, `③ TP/SL = ${(tpOut / slOut).toFixed(4)}`)
  ok(raw.direction === 'LONG', `③ جهت = ${raw.direction}`)
} else ok(false, '③ تصمیمِ خامِ S759 entry/sl/tp ندارد')

const fw = (d.falseWitness || []).map((x: any) => x.code)
report.false_witness_dropped = fw
ok(!fw.includes('S759'), `④ S759 به‌عنوانِ شاهدِ کاذب حذف نشد (dropped=[${fw.join(',')}])`)

const snap = (fns: any[]) => fns.map(fn => { try { const x: any = fn(ctx); return x ? `${x.sourceLayer?.code}:${x.state}:${x.direction || '—'}` : null } catch { return 'ERR' } })
  .filter(Boolean).filter((s: any) => !/^S759:/.test(s)).sort()
const backup = CARD_LAYERS[card]
const snapOn = snap(backup)
CARD_LAYERS[card] = backup.filter(fn => (fn(ctx) as any)?.sourceLayer?.code !== 'S759')
let snapOff: any[] = []
try { snapOff = snap(CARD_LAYERS[card]); ok(CARD_LAYERS[card].length === 4, '⑥ فیلتر دقیقاً یک لایه را جدا کرد') }
finally { CARD_LAYERS[card] = backup }
report.incumbents = snapOff
ok(JSON.stringify(snapOn) === JSON.stringify(snapOff), `⑥ ساکنان بی‌تغییر: [${snapOff.join(' | ')}]`)

report.status = fail === 0 ? 'GREEN' : 'RED'
report.fails = fail
if (process.argv.includes('--write')) {
  fs.writeFileSync(path.join(ROOT, 'results/_s759/integ_card.json'), JSON.stringify(report, null, 1))
}
console.log(fail === 0 ? '\n✅ GREEN' : `\n❌ RED — ${fail}`)
process.exit(fail === 0 ? 0 : 1)

// ---------------------------------------------------------------------------
// آزمونِ یکپارچگیِ S1581 در **سطحِ کارتِ H6** — از مسیرِ واقعیِ runCard.
//
// پریتی (`_parity_s1581.mts`) ماژول را جدا می‌سنجد؛ سایت ولی `runCard()` را
// صدا می‌زند. این آزمون شش چیز را از مسیرِ **واقعی** می‌بندد:
//   ① آداپتر در CARD_LAYERS کارتِ H6 حاضر است (H6: ۵ لایه).
//   ② روی رویدادِ واقعیِ تاریخی، S1581 به خروجیِ runCard **می‌رسد**.
//   ③ هندسهٔ **دلاری** درست است: فاصلهٔ SL ≈ ۱۵.۲۱$ (نه ۱.۵۲$ — دامِ pip ۰.۱
//      در برابرِ ۰.۰۱). این همان باگی است که S1516 دارد و اینجا مهار می‌شود.
//   ④ قیدِ شاهدِ کاذبِ **هم‌کارت** واقعاً اجرا می‌شود: روی کندلی که هم S1516 و
//      هم S1581 فعال‌اند، فقط **یکی** در خروجی می‌ماند و دیگری در `falseWitness`
//      گزارش می‌شود (jaccard ۶۳.۵) — «یک رویداد، نه دو شاهد».
//   ⑤ شاهدِ منفیِ H8/H4 (POWER-LIMITED): نه در S1581_CFG و نه کارتی به این نام.
//   ⑥ رگرسیون: تصمیمِ تک‌تکِ ساکنان با/بی S1581 بی‌تغییر است.
// اگر رویدادی پیدا نشود ⇒ FAIL (نه SKIP)، چون یعنی لایه در عمل روشن نمی‌شود.
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'
import { CARD_LAYERS, runCard } from '../src/strategy_registry'
import { computeS1581, S1581_CFG } from '../src/volume_fresh_floor_s1581'
import { computeS1516, S1516_CFG } from '../src/cal_fresh_floor_s1516'

const ROOT = path.resolve(import.meta.dirname, '../..')
type Candle = { time: number; open: number; high: number; low: number; close: number; volume: number }

function loadCsv(tf: string): Candle[] {
  const gz = path.join(ROOT, `data/mt5_full/XAUUSD_${tf}.csv.gz`)
  const text = zlib.gunzipSync(fs.readFileSync(gz)).toString('utf8')
  const lines = text.trim().split('\n').map(l => l.replace(/\r$/, ''))
  const head = lines[0].split(',')
  const ix = (n: string) => head.indexOf(n)
  const iT = ix('time'), iO = ix('open'), iH = ix('high'), iL = ix('low'), iC = ix('close')
  const iV = ix('tick_volume') >= 0 ? ix('tick_volume') : ix('volume')
  const out: Candle[] = []
  for (let i = 1; i < lines.length; i++) {
    const t = lines[i].split(',')
    out.push({ time: Number(t[iT]), open: Number(t[iO]), high: Number(t[iH]),
      low: Number(t[iL]), close: Number(t[iC]), volume: iV >= 0 ? Number(t[iV]) : 0 })
  }
  return out
}

let fail = 0
const ok = (c: boolean, m: string) => { console.log(`   ${c ? '✓' : '❌'} ${m}`); if (!c) fail++ }
const report: any = { cards: {} }

console.log('══ آزمونِ یکپارچگیِ S1581 در سطحِ کارتِ H6 ══\n')
console.log('── ⑤ شاهدِ منفیِ H8/H4 (POWER-LIMITED) ──')
ok(!Object.prototype.hasOwnProperty.call(S1581_CFG, 'XAUUSD-H8'), 'XAUUSD-H8 در S1581_CFG نیست')
ok(!Object.prototype.hasOwnProperty.call(S1581_CFG, 'XAUUSD-H4'), 'XAUUSD-H4 در S1581_CFG نیست')
ok(!('XAUUSD-H8' in CARD_LAYERS) || CARD_LAYERS['XAUUSD-H8'].length === 9, 'کارتِ H8 بی‌تغییر ماند (۹ لایه)')

const card = 'XAUUSD-H6'
const tf = 'H6'
const expectLayers = 5
const slPip = 152.10

console.log(`\n══════ ${card} ══════`)
const rep: any = {}; report.cards[card] = rep
const nLayers = (CARD_LAYERS[card] || []).length
rep.layer_count = nLayers
ok(nLayers === expectLayers, `① ${nLayers} لایه (انتظار ${expectLayers})`)

const cfg = S1581_CFG[card]
ok(!!cfg && cfg.slPip === slPip, `③ SL=${cfg?.slPip} pip (سند: ${slPip})`)

const all = loadCsv(tf)
const cfg1516 = S1516_CFG[card]

// ② رویدادِ **مستقلِ** S1581 (S1516 هم‌زمان فعال نیست) در ۳۰۰۰ کندلِ اخیر.
//    فقط روی رویدادهای مستقل انتظار داریم S1581 واقعاً به تصمیم برسد؛ روی
//    رویدادِ مشترک، قیدِ شاهدِ کاذب عامدانه آن را حذف می‌کند (پایین‌تر سنجیده می‌شود).
const lo = Math.max(cfg.lookback + 5, all.length - 3000)
let hit = -1
for (let i = all.length - 1; i >= lo; i--) {
  const c = all.slice(0, i + 1) as any
  if (computeS1581(c, cfg).active && !computeS1516(c, cfg1516).active) { hit = i; break }
}
if (hit < 0) { ok(false, '② در ۳۰۰۰ کندلِ اخیر هیچ رویدادِ مستقلِ S1581 نیست'); }
else {
  const when = new Date(all[hit].time * 1000).toISOString().slice(0, 16).replace('T', ' ')
  rep.event = { bar: hit, utc: when, close: all[hit].close }
  console.log(`   رویدادِ مستقلِ S1581: ${when} UTC · close=${all[hit].close}`)

  const sl = all.slice(0, hit + 1)
  const ctx: any = {
    cardId: card, a: { id: card, price: all[hit].close, indicators: [], regime: undefined },
    candles: sl, utcHour: new Date(all[hit].time * 1000).getUTCHours(),
    times: sl.map(c => c.time), capital: 10000, riskPct: 1.0,
  }
  const dOn: any = runCard(ctx)
  const codes = [dOn.sourceLayer?.code, ...((dOn.otherLayers || []).map((o: any) => o.code))]
  rep.codes_on = codes
  console.log(`   خروجی: [${codes.join(', ')}] · state=${dOn.state}`)
  ok(codes.includes('S1581'), '② روی رویدادِ مستقل، S1581 به خروجیِ runCard می‌رسد')

  // ③ هندسهٔ دلاریِ رسیده به تصمیم (دامِ pip)
  const raw = CARD_LAYERS[card].map(fn => fn(ctx)).find((d: any) => /S1581/.test(d?.sourceLayer?.code || '')) as any
  if (raw && raw.sl && raw.entry) {
    const slPipOut = Math.round(Math.abs(raw.entry - raw.sl) / 0.1 * 100) / 100
    rep.sl_pip_out = slPipOut
    ok(Math.abs(slPipOut - slPip) < 0.05, `③ SLِ رسیده به تصمیم = ${slPipOut} pip (≈ ${(slPipOut * 0.1).toFixed(2)}$، نه ۱۰× کوچک‌تر)`)
  }
}

// ④ قیدِ شاهدِ کاذب: کندلی که هم S1516 و هم S1581 فعال‌اند
let both = -1
for (let i = all.length - 1; i >= lo; i--) {
  const c = all.slice(0, i + 1) as any
  if (computeS1581(c, cfg).active && computeS1516(c, cfg1516).active) { both = i; break }
}
if (both < 0) { ok(false, '④ کندلِ هم‌زمانِ S1516∧S1581 پیدا نشد') }
else {
  const when = new Date(all[both].time * 1000).toISOString().slice(0, 16).replace('T', ' ')
  console.log(`   کندلِ هم‌زمان: ${when} UTC`)
  const sl = all.slice(0, both + 1)
  const ctx: any = {
    cardId: card, a: { id: card, price: all[both].close, indicators: [], regime: undefined },
    candles: sl, utcHour: new Date(all[both].time * 1000).getUTCHours(),
    times: sl.map(c => c.time), capital: 10000, riskPct: 1.0,
  }
  const d: any = runCard(ctx)
  const codes = [d.sourceLayer?.code, ...((d.otherLayers || []).map((o: any) => o.code))]
  rep.both_codes = codes
  const nBoth = codes.filter(c => c === 'S1516' || c === 'S1581').length
  console.log(`   خروجی: [${codes.join(', ')}] · falseWitness=${JSON.stringify(d.falseWitness || null)}`)
  ok(nBoth === 1, `④ از {S1516,S1581} فقط یکی در خروجی ماند (${nBoth})`)
  ok(Array.isArray(d.falseWitness) && d.falseWitness.length === 1
     && (d.falseWitness[0].code === 'S1516' || d.falseWitness[0].code === 'S1581'),
     '④ دیگری در falseWitness گزارش شد (شفاف، نه ناپدیدِ بی‌دلیل)')
  if (Array.isArray(d.falseWitness) && d.falseWitness[0]) {
    ok(d.falseWitness[0].jaccard === 63.5, `④ jaccardِ گزارش‌شده = ${d.falseWitness[0].jaccard}`)
  }
}

// ⑥ رگرسیون: ساکنانِ H6 با/بی S1581
{
  const sl = all.slice(0, Math.max(1, all.length - 1))
  const ctx: any = {
    cardId: card, a: { id: card, price: sl[sl.length - 1].close, indicators: [], regime: undefined },
    candles: sl, utcHour: new Date(sl[sl.length - 1].time * 1000).getUTCHours(),
    times: sl.map(c => c.time), capital: 10000, riskPct: 1.0,
  }
  const snap = (fns: any[]) => fns.map(fn => { try { const d = fn(ctx); return d ? `${d.sourceLayer?.code}:${d.state}:${d.direction || '—'}` : null } catch { return 'ERR' } })
    .filter(Boolean).filter((s: any) => !/S1581/.test(s)).sort()
  const backup = CARD_LAYERS[card]
  const snapOn = snap(backup)
  CARD_LAYERS[card] = backup.filter(fn => !/S1581/.test((fn(ctx) as any)?.sourceLayer?.code || ''))
  let snapOff: any[] = []
  try { snapOff = snap(CARD_LAYERS[card]); ok(CARD_LAYERS[card].length === expectLayers - 1, '⑥ فیلتر دقیقاً یک لایه را جدا کرد') }
  finally { CARD_LAYERS[card] = backup }
  ok(JSON.stringify(snapOn) === JSON.stringify(snapOff), `⑥ ساکنان بی‌تغییر: [${snapOff.join(' | ')}]`)
}

const OUT = path.join(ROOT, 'results/_s1581/integ_card.json')
fs.mkdirSync(path.dirname(OUT), { recursive: true })
fs.writeFileSync(OUT, JSON.stringify(report, null, 1))
console.log(`\nذخیره شد -> ${OUT}`)
console.log(fail === 0 ? '\n✅ GREEN — S1581 روی H6 زنده، هندسهٔ ۱۵.۲۱$، قیدِ شاهدِ کاذب فعال، صفر رگرسیون' : `\n❌ RED — ${fail} چکِ ناموفق`)
process.exit(fail === 0 ? 0 : 1)

// ---------------------------------------------------------------------------
// آزمونِ یکپارچگیِ S572 در سطحِ کارت‌های M30 و H1 — از مسیرِ واقعیِ runCard.
//
// پریتی (`_parity_s572.mts`) ماژول را جدا می‌سنجد؛ سایت ولی `runCard()` را صدا
// می‌زند. این آزمون از مسیرِ **واقعی** می‌بندد:
//   ① آداپتر در CARD_LAYERS کارتِ M30 (۴ لایه) و H1 (۵ لایه) حاضر است.
//   ② روی رویدادِ واقعیِ تاریخی، S572 به خروجیِ runCard **می‌رسد**.
//   ③ هندسهٔ **دلاری** درست است (SL ≈ ۳.۴۷$ روی M30 و ۶.۶۰$ روی H1 — pip=۰.۱).
//   ④ روی پنجرهٔ **واقع‌گرایانهٔ سایت** (کوتاه‌تر از کلِ تاریخ) هم فعال می‌شود —
//      وگرنه لایه فقط روی کاغذ وصل شده. (S572 به ۳۰۰ کندلِ گرم‌شدن نیاز دارد.)
//   ⑤ قیدِ هم‌رویدادیِ **بین‌کارتی** اجرا می‌شود: کارتِ غیرِمرجع (H1) برچسبِ
//      `sameEventFamily` با isPrimary=false و primaryCard=XAUUSD-M30 می‌گیرد.
//   ⑥ رگرسیون: تصمیمِ ساکنانِ هر دو کارت با/بی S572 بی‌تغییر است.
// اگر رویدادی پیدا نشود ⇒ FAIL (نه SKIP)، چون یعنی لایه در عمل روشن نمی‌شود.
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'
import { CARD_LAYERS, runCard } from '../src/strategy_registry'
import { S572_CFG, s572Features } from '../src/sr_pullback_mirror_s572'

const ROOT = path.resolve(import.meta.dirname, '../..')
type Candle = { time: number; open: number; high: number; low: number; close: number; volume: number }

function loadCsv(tf: string): Candle[] {
  const gz = path.join(ROOT, `data/mt5_full/XAUUSD_${tf}.csv.gz`)
  const text = zlib.gunzipSync(fs.readFileSync(gz)).toString('utf8')
  const lines = text.trim().split('\n').map(l => l.replace(/\r$/, ''))
  const head = lines[0].split(',')
  const ix = (n: string) => head.indexOf(n)
  const iT = ix('time'), iO = ix('open'), iH = ix('high'), iL = ix('low'), iC = ix('close')
  const iV = ix('volume') >= 0 ? ix('volume') : ix('tick_volume')
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

const SPEC: Record<string, { tf: string; expectLayers: number; slPip: number; win: number }> = {
  'XAUUSD-M30': { tf: 'M30', expectLayers: 4, slPip: 34.7, win: 1200 },
  'XAUUSD-H1': { tf: 'H1', expectLayers: 5, slPip: 66.0, win: 1800 },
}

console.log('══ آزمونِ یکپارچگیِ S572 روی کارت‌های M30 و H1 ══\n')

for (const card of ['XAUUSD-M30', 'XAUUSD-H1']) {
  const spec = SPEC[card]
  const cfg = S572_CFG[card]
  console.log(`══════ ${card} ══════`)
  const rep: any = {}; report.cards[card] = rep
  const nLayers = (CARD_LAYERS[card] || []).length
  rep.layer_count = nLayers
  ok(nLayers === spec.expectLayers, `① ${nLayers} لایه (انتظار ${spec.expectLayers})`)

  const all = loadCsv(spec.tf)
  const full = s572Features(all, cfg)
  // رویدادِ واقعی با حداقلِ «پنجره» کندلِ پیش از خودش (تا آزمونِ پنجرهٔ کوتاه ممکن باشد)
  let hit = -1
  for (let i = all.length - 1; i >= spec.win + 50; i--) { if (full.sig[i]) { hit = i; break } }
  if (hit < 0) { ok(false, '② رویدادِ واقعیِ S572 پیدا نشد'); continue }
  const when = new Date(all[hit].time * 1000).toISOString().slice(0, 16).replace('T', ' ')
  rep.event = { bar: hit, utc: when, close: all[hit].close }
  console.log(`   رویدادِ S572: ${when} UTC · close=${all[hit].close}`)

  // ② runCard روی کلِ پیشوندِ تاریخ
  const mkCtx = (slice: Candle[]) => ({
    cardId: card, a: { id: card, price: slice[slice.length - 1].close, indicators: [], regime: undefined },
    candles: slice, utcHour: new Date(slice[slice.length - 1].time * 1000).getUTCHours(),
    times: slice.map(c => c.time), capital: 10000, riskPct: 1.0,
  })
  const prefix = all.slice(0, hit + 1)
  const dOn: any = runCard(mkCtx(prefix) as any)
  const codes = [dOn.sourceLayer?.code, ...((dOn.otherLayers || []).map((o: any) => o.code))]
  rep.codes_on = codes
  console.log(`   خروجی (کلِ پیشوند): [${codes.join(', ')}] · state=${dOn.state}`)
  ok(codes.includes('S572'), '② روی رویدادِ واقعی، S572 به خروجیِ runCard می‌رسد')

  // ③ هندسهٔ دلاریِ رسیده به تصمیم (دامِ pip ۰.۱)
  const raw = CARD_LAYERS[card].map(fn => fn(mkCtx(prefix) as any)).find((d: any) => /S572/.test(d?.sourceLayer?.code || '')) as any
  if (raw && raw.entry && raw.sl) {
    const slPipOut = Math.round(Math.abs(raw.entry - raw.sl) / 0.1 * 100) / 100
    rep.sl_pip_out = slPipOut
    ok(Math.abs(slPipOut - spec.slPip) < 0.05,
      `③ SLِ رسیده به تصمیم = ${slPipOut} pip (≈ ${(slPipOut * 0.1).toFixed(2)}$، سند ${spec.slPip})`)
  } else {
    ok(false, '③ تصمیمِ ENTRYِ S572 با entry/sl پیدا نشد')
  }

  // ④ پنجرهٔ واقع‌گرایانهٔ سایت (کوتاه‌تر از کلِ تاریخ) — همان رویداد، پنجرهٔ win کندل
  const winSlice = all.slice(Math.max(0, hit + 1 - spec.win), hit + 1)
  const dWin: any = runCard(mkCtx(winSlice) as any)
  const winCodes = [dWin.sourceLayer?.code, ...((dWin.otherLayers || []).map((o: any) => o.code))]
  rep.window = { bars: winSlice.length, codes: winCodes }
  console.log(`   خروجی (پنجرهٔ ${winSlice.length} کندلی): [${winCodes.join(', ')}]`)
  ok(winCodes.includes('S572'),
    `④ روی پنجرهٔ ${winSlice.length} کندلی هم S572 فعال می‌شود (زنده‌بودن روی سایت)`)

  // ⑤ قیدِ هم‌رویدادیِ بین‌کارتی: H1 باید isPrimary=false بگیرد
  if (card === 'XAUUSD-H1') {
    const fam = (dOn as any).sameEventFamily || (dOn.otherLayers || []).map((o: any) => o.sameEventFamily).find(Boolean)
    rep.sameEventFamily = fam || null
    console.log(`   sameEventFamily = ${JSON.stringify(fam || null)}`)
    ok(!!fam && fam.code === 'S572' && fam.isPrimary === false && fam.primaryCard === 'XAUUSD-M30',
      '⑤ کارتِ غیرِمرجع (H1) برچسبِ بدیل با primaryCard=M30 گرفت')
  }

  // ⑥ رگرسیون: ساکنان با/بی S572 بی‌تغییر
  {
    const backup = CARD_LAYERS[card]
    const snap = (fns: any[]) => fns.map(fn => { try { const d = fn(mkCtx(prefix) as any); return d ? `${d.sourceLayer?.code}:${d.state}` : null } catch { return 'ERR' } })
      .filter(Boolean).filter((s: any) => !/S572/.test(s)).sort()
    const snapOn = snap(backup)
    CARD_LAYERS[card] = backup.filter(fn => !/S572/.test((fn(mkCtx(prefix) as any) as any)?.sourceLayer?.code || ''))
    let snapOff: any[] = []
    try { snapOff = snap(CARD_LAYERS[card]); ok(CARD_LAYERS[card].length === spec.expectLayers - 1, '⑥ فیلتر دقیقاً یک لایه را جدا کرد') }
    finally { CARD_LAYERS[card] = backup }
    ok(JSON.stringify(snapOn) === JSON.stringify(snapOff), `⑥ ساکنان بی‌تغییر: [${snapOff.join(' | ')}]`)
  }
  console.log('')
}

console.log('═══ شاهدِ منفی: فقط دو کارتِ ACCEPT ═══')
const ids = Object.keys(S572_CFG).sort()
ok(ids.length === 2 && ids[0] === 'XAUUSD-H1' && ids[1] === 'XAUUSD-M30', 'دقیقاً دو کارت (H1,M30)', ids.join(', '))

const OUT = path.join(ROOT, 'results/_s572_parity/integ_cards.json')
fs.mkdirSync(path.dirname(OUT), { recursive: true })
fs.writeFileSync(OUT, JSON.stringify(report, null, 1))
console.log(`\nذخیره شد -> ${OUT}`)
console.log(fail === 0 ? '\n✅ GREEN — S572 روی M30 و H1 زنده، هندسهٔ درست، قیدِ بین‌کارتی فعال، صفر رگرسیون' : `\n❌ RED — ${fail} چکِ ناموفق`)
process.exit(fail === 0 ? 0 : 1)

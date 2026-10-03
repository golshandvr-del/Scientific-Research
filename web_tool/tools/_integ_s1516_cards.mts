// ---------------------------------------------------------------------------
// آزمونِ یکپارچگیِ S1516 در **سطحِ کارت** — هر دو کارتِ ACCEPT (H6 و H4).
//
// پریتی (`_parity_s1516.mts`) ماژول را جدا می‌سنجد؛ سایت ولی `runCard()` را صدا
// می‌زند. این آزمون پنج چیز را از مسیرِ **واقعیِ** runCard می‌بندد:
//   ① آداپتر در CARD_LAYERS هر دو کارت حاضر است (H6: ۴ لایه، H4: ۴ لایه).
//   ② روی رویدادِ واقعیِ تاریخی، S1516 به خروجیِ runCard **می‌رسد**.
//   ③ هر کارت هندسهٔ **خودش** را می‌دهد (H6 ۱۵۲.۱۰ / H4 ۱۲۳.۳۲) — دامِ کلیدِ اشتباه.
//   ④ قیدِ شاهدِ کاذبِ **بین‌کارتی** واقعاً به خروجی می‌رسد: روی H6 برچسبِ
//      sameEventFamily با isPrimary=true و روی H4 با isPrimary=false.
//   ⑤ شاهدِ منفیِ H3 (REJECT 16.5): نه در S1516_CFG و نه کارتی به این نام.
//   ⑥ رگرسیون: تصمیمِ تک‌تکِ ساکنان با/بی S1516 بی‌تغییر است.
// اگر رویدادی پیدا نشود ⇒ FAIL (نه SKIP)، چون یعنی لایه در عمل روشن نمی‌شود.
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'
import { CARD_LAYERS, runCard } from '../src/strategy_registry'
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

console.log('══ آزمونِ یکپارچگیِ S1516 در سطحِ کارت (H6 · H4) ══\n')
console.log('── ⑤ شاهدِ منفیِ H3 (REJECT 16.5) ──')
ok(!Object.prototype.hasOwnProperty.call(S1516_CFG, 'XAUUSD-H3'), 'XAUUSD-H3 در S1516_CFG نیست')
ok(!('XAUUSD-H3' in CARD_LAYERS), 'کارتِ XAUUSD-H3 در CARD_LAYERS وجود ندارد')

const CARDS = [
  // H6: ۴ → ۵ پس از افزودنِ S1581 (کفِ تازهٔ ۹۰ × حجم) در همین نشست.
  { card: 'XAUUSD-H6', tf: 'H6', expectLayers: 5, slPip: 152.10, primary: true },
  { card: 'XAUUSD-H4', tf: 'H4', expectLayers: 5, slPip: 123.32, primary: false },
]

for (const spec of CARDS) {
  const { card, tf } = spec
  console.log(`\n══════ ${card} ══════`)
  const rep: any = {}; report.cards[card] = rep
  const nLayers = (CARD_LAYERS[card] || []).length
  rep.layer_count = nLayers
  ok(nLayers === spec.expectLayers, `① ${nLayers} لایه (انتظار ${spec.expectLayers})`)

  const cfg = S1516_CFG[card]
  ok(!!cfg && cfg.slPip === spec.slPip, `③ SL=${cfg?.slPip} pip (سند/امروز: ${spec.slPip})`)

  const all = loadCsv(tf)
  const lo = Math.max(cfg.lookback + 5, all.length - 3000)
  let hit = -1
  for (let i = all.length - 1; i >= lo; i--) {
    if (computeS1516(all.slice(0, i + 1) as any, cfg).active) { hit = i; break }
  }
  if (hit < 0) { ok(false, '② در ۳۰۰۰ کندلِ اخیر هیچ رویدادی نیست'); continue }
  const when = new Date(all[hit].time * 1000).toISOString().slice(0, 16).replace('T', ' ')
  rep.event = { bar: hit, utc: when, close: all[hit].close }
  console.log(`   رویدادِ واقعی: ${when} UTC · close=${all[hit].close}`)

  const sl = all.slice(0, hit + 1)
  const ctx: any = {
    cardId: card, a: { id: card, price: all[hit].close, indicators: [], regime: undefined },
    candles: sl, utcHour: new Date(all[hit].time * 1000).getUTCHours(),
    times: sl.map(c => c.time), capital: 10000, riskPct: 1.0,
  }
  const dOn: any = runCard(ctx)
  const entries: any[] = [{ code: dOn.sourceLayer?.code, fam: dOn.sameEventFamily }]
  for (const o of (dOn.otherLayers || [])) entries.push({ code: o.code, fam: o.sameEventFamily })
  rep.codes_on = entries.map(e => e.code)
  console.log(`   خروجی: [${rep.codes_on.join(', ')}] · state=${dOn.state}`)
  const mine = entries.find(e => /S1516/.test(e.code || ''))
  ok(!!mine, '② S1516 به خروجیِ runCard می‌رسد')

  // خروجیِ خامِ لایه (مستقل از رتبه‌بندی) برای سنجشِ هندسهٔ رسیده به تصمیم
  const raw = CARD_LAYERS[card].map(fn => fn(ctx)).find((d: any) => /S1516/.test(d?.sourceLayer?.code || '')) as any
  if (raw && raw.sl && raw.entry) {
    // 🔴 اصلاحِ باگِ آزمون: این‌جا قبلاً `/ 0.01` بود، یعنی آزمون **همان باگِ
    //    pip را تأیید می‌کرد** که ماژول داشت (استاپِ ۱۰× تنگ). قراردادِ پروژه
    //    GOLD_PIP=0.1 است ⇒ با `/ 0.1` سنجیده می‌شود تا اگر کسی دوباره ۰.۰۱
    //    بگذارد، این آزمون قرمز شود.
    const slPipOut = Math.round(Math.abs(raw.entry - raw.sl) / 0.1 * 100) / 100
    rep.sl_pip_out = slPipOut
    ok(Math.abs(slPipOut - spec.slPip) < 0.05, `③ SLِ رسیده به تصمیم = ${slPipOut} pip`)
  }

  const fam = mine?.fam
  rep.same_event_family = fam || null
  ok(!!fam && fam.code === 'S1516', '④ برچسبِ sameEventFamily روی S1516 نشسته')
  ok(!!fam && fam.isPrimary === spec.primary,
    `④ isPrimary=${fam?.isPrimary} (انتظار ${spec.primary} — مرجع H6، H4 بدیل)`)

  const snap = (fns: any[]) => fns.map(fn => { try { const d = fn(ctx); return d ? `${d.sourceLayer?.code}:${d.state}:${d.direction || '—'}` : null } catch { return 'ERR' } })
    .filter(Boolean).filter((s: any) => !/S1516/.test(s)).sort()
  const backup = CARD_LAYERS[card]
  const snapOn = snap(backup)
  CARD_LAYERS[card] = backup.filter(fn => !/S1516/.test((fn(ctx) as any)?.sourceLayer?.code || ''))
  let snapOff: any[] = []
  try { snapOff = snap(CARD_LAYERS[card]); ok(CARD_LAYERS[card].length === spec.expectLayers - 1, '⑥ فیلتر دقیقاً یک لایه را جدا کرد') }
  finally { CARD_LAYERS[card] = backup }
  ok(JSON.stringify(snapOn) === JSON.stringify(snapOff), `⑥ ساکنان بی‌تغییر: [${snapOff.join(' | ')}]`)
}

const OUT = path.join(ROOT, 'results/_s1516/integ_cards.json')
fs.mkdirSync(path.dirname(OUT), { recursive: true })
fs.writeFileSync(OUT, JSON.stringify(report, null, 1))
console.log(`\nذخیره شد -> ${OUT}`)
console.log(fail === 0 ? '\n✅ GREEN — S1516 روی H6 و H4 زنده، هندسهٔ مخصوص، قیدِ بین‌کارتی فعال، صفر رگرسیون' : `\n❌ RED — ${fail} چکِ ناموفق`)
process.exit(fail === 0 ? 0 : 1)

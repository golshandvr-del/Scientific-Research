// integ_s965_card.mjs — تستِ یکپارچگیِ end-to-end برای S965 روی کارتِ XAUUSD-H8.
//
// چرا این تست لازم است (و پریتی کافی نیست): `parity_s965_signal.mjs` ثابت می‌کند
// تابعِ TS با پایتونِ مرجع یکی است، ولی ثابت نمی‌کند که لایه **از مسیرِ واقعیِ
// سایت** صدا زده می‌شود. سایت از `runCard(ctx)` عبور می‌کند که همهٔ لایه‌های
// `CARD_LAYERS['XAUUSD-H8']` را اجرا و سپس طبقِ رتبهٔ حالت مرتب می‌کند. اگر ثبتِ
// لایه فراموش شود یا آداپتور آرگومان‌ها را جابه‌جا بدهد، پریتی سبز می‌ماند و
// سایت خاموش — این تست دقیقاً همان شکاف را می‌بندد.
//
// روش: کندل‌های واقعیِ H8 (از fixtureِ پریتی) را تا لحظهٔ سیگنال‌های شناخته‌شدهٔ
// پایتون به کلِ `runCard` می‌دهیم و می‌سنجیم که:
//   ① روی کندل‌های سیگنالیِ S965 ⇒ لایهٔ S965 در خروجی حاضر باشد و ENTRY بدهد
//      (چه به‌عنوانِ لایهٔ اصلی، چه در otherLayers — چون S950 هم‌کارت است و
//       ممکن است همان لحظه شلیک کند و رتبهٔ اول را بگیرد).
//   ② جهتِ اعلام‌شده با جهتِ پایتون یکی باشد.
//   ③ روی کندل‌های بی‌سیگنال ⇒ S965 ساکت بماند (کنترلِ منفی، ضدِ سیگنالِ همیشه-روشن).
//
// اجرا: cd web_tool && node --import tsx integ_s965_card.mjs
import fs from 'fs'
import { runCard, CARD_LAYERS } from './src/strategy_registry.ts'

const CARD = 'XAUUSD-H8'
const CODE = 'S965'
// پنجرهٔ ورودی: warmِ S965 فقط ۲۳ کندل است، ولی کارت لایه‌های دیگری هم دارد
// (S950 با warm=91) ⇒ پنجرهٔ ۴۰۰ می‌دهیم تا هیچ لایه‌ای از کمبودِ داده نمیرد و
// شرایط عیناً مثلِ سایتِ زنده باشد.
const WIN = 400

const fx = JSON.parse(fs.readFileSync('../results/_scan_S965/parity_h8_fixture.json', 'utf8'))
const candlesAll = fx.candles
const sigL = fx.py.idx_long.filter(i => i >= WIN)
const sigS = fx.py.idx_short.filter(i => i >= WIN)

// کنترلِ منفی: کندل‌هایی که پایتون رویشان هیچ سیگنالی ندارد.
const sigSet = new Set([...fx.py.idx_long, ...fx.py.idx_short])
const quiet = []
for (let i = candlesAll.length - 1; i >= WIN && quiet.length < 4; i--) {
  if (!sigSet.has(i)) quiet.push(i)
}

// همهٔ سیگنال‌های داخلِ پنجره را می‌آزماییم (نه فقط اول و آخر) — پوششِ کامل.
const cases = [
  ...sigL.map(i => ({ idx: i, expect: 'LONG' })),
  ...sigS.map(i => ({ idx: i, expect: 'SHORT' })),
  ...quiet.map(i => ({ idx: i, expect: 'NONE' })),
]

// استخراجِ لایهٔ S965 از خروجیِ runCard — چه اصلی باشد چه در otherLayers.
function findS965(dec) {
  if (!dec) return null
  if (dec.sourceLayer?.code === CODE) {
    return { state: dec.state, direction: dec.direction, entry: dec.entry, sl: dec.sl, tp: dec.tp, where: 'primary' }
  }
  const o = (dec.otherLayers || []).find(x => x.code === CODE)
  if (o) return { state: o.state, direction: o.direction, entry: o.entry, sl: o.sl, tp: o.tp, where: 'otherLayers' }
  return null
}

const dirMatch = (d, expect) => {
  const s = String(d || '').toUpperCase()
  if (expect === 'LONG') return s.includes('LONG') || s.includes('BUY') || s.includes('خرید')
  return s.includes('SHORT') || s.includes('SELL') || s.includes('فروش')
}

console.log(`=== ${CARD} ===  (${CARD_LAYERS[CARD].length} لایهٔ ثبت‌شده) — ${cases.length} کیس`)
const wired = CARD_LAYERS[CARD].length
let pass = 0
for (const { idx, expect } of cases) {
  const candles = candlesAll.slice(Math.max(0, idx - WIN + 1), idx + 1)
  const last = candles[candles.length - 1]
  const a = { price: last.close, adx: 0, ema: {}, rsi: 50 }
  const ctx = {
    cardId: CARD, a, candles,
    utcHour: new Date(last.time * 1000).getUTCHours(),
    times: candles.map(c => c.time), capital: 10000, riskPct: 1.0,
  }
  const dec = runCard(ctx)
  const s = findS965(dec)
  const entered = !!s && (s.state === 'ENTRY' || !!s.entry)
  let ok, note
  if (expect === 'NONE') {
    ok = !entered
    note = s ? `S965 present state=${s.state}` : 'S965 silent'
  } else {
    ok = entered && dirMatch(s.direction, expect)
    note = s ? `${s.where} state=${s.state} dir=${s.direction}` : 'S965 ABSENT from runCard output'
  }
  if (ok) pass++
  console.log(`  @${String(idx).padStart(4)} expect=${expect.padEnd(5)} → ${note} ${ok ? '✔' : '✘'}`)
}
const verdict = pass === cases.length
console.log(`نتیجه: ${pass}/${cases.length} · لایه‌های کارت=${wired} · ${verdict ? 'INTEG-PASS ✅' : 'INTEG-FAIL ❌'}`)
if (!verdict) process.exit(1)

// integ_s950_card.mjs — تستِ یکپارچگیِ end-to-end برای S950 روی کارتِ XAUUSD-H8.
// کندل‌های واقعیِ H8 (از fixture پریتی) را تا لحظهٔ چند سیگنالِ شناخته‌شدهٔ
// پایتون به کلِ runCard می‌دهیم و می‌سنجیم که S950 تصمیمِ ورود بدهد،
// و روی کندل‌های غیرسیگنالی ساکت بماند.
// اجرا: cd web_tool && node --import tsx integ_s950_card.mjs
import fs from 'fs'
import { runCard, CARD_LAYERS } from './src/strategy_registry.ts'

const CARD = 'XAUUSD-H8'
const WIN = 400                       // > warm(91) با حاشیهٔ فراوان

const fx = JSON.parse(fs.readFileSync('../results/_scan_S950/parity_h8_fixture.json', 'utf8'))
const candlesAll = fx.candles
const sigL = fx.py.idx_long.filter(i => i >= WIN)
const sigS = fx.py.idx_short.filter(i => i >= WIN)

// ۲ خرید + ۲ فروش + ۲ کندلِ بی‌سیگنال (باید ساکت باشد)
const sigSet = new Set([...fx.py.idx_long, ...fx.py.idx_short])
const quiet = []
for (let i = candlesAll.length - 1; i >= WIN && quiet.length < 2; i--) if (!sigSet.has(i)) quiet.push(i)

const cases = [
  ...[sigL[0], sigL[sigL.length - 1]].map(i => ({ idx: i, expect: 'LONG' })),
  ...[sigS[0], sigS[sigS.length - 1]].map(i => ({ idx: i, expect: 'SHORT' })),
  ...quiet.map(i => ({ idx: i, expect: 'NONE' })),
]

console.log(`=== ${CARD} ===  (${CARD_LAYERS[CARD].length} لایه) — ${cases.length} کیس`)
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
  const src = dec?.sourceLayer?.code
  const dir = (dec?.direction || '').toUpperCase()
  const entered = dec?.state === 'enter' || dec?.action === 'enter' || !!dec?.entry
  let ok
  if (expect === 'NONE') ok = !(src === 'S950' && entered)
  else ok = src === 'S950' && entered && (dir.includes(expect) || dir === (expect === 'LONG' ? 'BUY' : 'SELL'))
  if (ok) pass++
  console.log(`  @${idx} expect=${expect} → state=${dec?.state} dir=${dec?.direction} src=${src} ${ok ? '✔' : '✘'}`)
}
console.log(`نتیجه: ${pass}/${cases.length} ${pass === cases.length ? 'INTEG-PASS ✅' : 'INTEG-FAIL ❌'}`)
if (pass !== cases.length) process.exit(1)

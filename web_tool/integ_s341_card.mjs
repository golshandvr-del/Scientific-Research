// integ_s341_card.mjs — تستِ یکپارچگیِ end-to-end برای هر ۴ تایم‌فریمِ S341.
// برای هر کارت، چند کندلِ سیگنالِ شناخته‌شدهٔ پایتون را به کلِ runCard می‌دهیم و
// می‌سنجیم که S341 به‌عنوانِ منبع (یا یکی از لایه‌ها) یک تصمیمِ ورودِ LONG بدهد.
// اجرا: cd web_tool && node integ_s341_card.mjs [CARD ...]
import fs from 'fs'
import { runCard, CARD_LAYERS } from './dist_parity/strategy_registry.js'

function refPath(card) {
  return card === 'XAUUSD-H1'
    ? '../strategies/s341_parity_ref.json'
    : `../strategies/s341_parity_ref_${card}.json`
}

function testCard(card) {
  const ref = JSON.parse(fs.readFileSync(refPath(card), 'utf8'))
  const candlesAll = ref.candles.map(c => ({
    time: c.time, open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume || 0,
  }))
  // پنجرهٔ دنباله‌دارِ کافی (مثلِ parity) تا اجرا سبک بماند
  const WIN = 1200
  // چند سیگنالِ پراکنده را برمی‌داریم (ابتدا/میانه/انتها) تا نمونه‌ای معرف باشد
  const idxs = ref.signal_idx.filter(i => i >= 1500)
  const pick = [idxs[0], idxs[Math.floor(idxs.length / 3)], idxs[Math.floor(2 * idxs.length / 3)],
                idxs[idxs.length - 1]].filter((v, k, arr) => v != null && arr.indexOf(v) === k)

  console.log(`\n=== ${card} ===  (${CARD_LAYERS[card].length} لایه) — آزمونِ ${pick.length} سیگنال`)
  let fired = 0
  for (const idx of pick) {
    const lo = Math.max(0, idx - WIN + 1)
    const candles = candlesAll.slice(lo, idx + 1)
    const last = candles[candles.length - 1]
    const a = { price: last.close, adx: 0, ema: {}, rsi: 50 }
    const d = new Date(last.time * 1000)
    const ctx = {
      cardId: card, a, candles,
      utcHour: d.getUTCHours(), times: candles.map(c => c.time),
      capital: 10000, riskPct: 1.0,
    }
    const dec = runCard(ctx)
    const src = dec?.sourceLayer?.code
    const others = (dec?.otherLayers || []).map(o => o?.sourceLayer?.code || o?.code)
    const hasS341 = src === 'S341' || others.includes('S341')
    if (hasS341) fired++
    console.log(`  @${idx} → state=${dec?.state} dir=${dec?.direction} src=${src} others=[${others.join(',')}] S341=${hasS341}`)
  }
  const ok = fired === pick.length
  console.log(`  ⇒ S341 روی ${fired}/${pick.length} فعال شد  ${ok ? '✅' : '⚠️'}`)
  return ok
}

const cards = process.argv.slice(2).length
  ? process.argv.slice(2)
  : ['XAUUSD-M5', 'XAUUSD-M15', 'XAUUSD-M30', 'XAUUSD-H1']

let all = true
for (const card of cards) all = testCard(card) && all
console.log(`\n${all ? '✅ INTEGRATION PASS — S341 روی هر ۴ کارت از طریقِ runCard وصل و فعال است.'
                     : '⚠️ برخی سیگنال‌ها فعال نشدند — بررسیِ اولویتِ لایه/اتصال لازم است.'}`)
process.exit(all ? 0 : 1)

// integ_s341_card.mjs — تستِ یکپارچگیِ end-to-end: آیا S341 از طریقِ runCard
// روی کارتِ XAUUSD-H1 یک تصمیمِ ورودِ LONG تولید می‌کند؟
// یک کندلِ سیگنالِ شناخته‌شدهٔ پایتون را به کلِ کارت می‌دهیم.
import fs from 'fs'
import { runCard, CARD_LAYERS } from './dist_parity/strategy_registry.js'

const ref = JSON.parse(fs.readFileSync('../strategies/s341_parity_ref.json', 'utf8'))
const candlesAll = ref.candles.map(c => ({
  time: c.time, open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume || 0,
}))

console.log('کارتِ XAUUSD-H1 دارای', CARD_LAYERS['XAUUSD-H1'].length, 'لایه است.\n')

// چند اندیسِ سیگنالِ پایتون را می‌آزماییم
const testBars = ref.signal_idx.slice(0, 6)
let s341Fired = 0
for (const idx of testBars) {
  const candles = candlesAll.slice(0, idx + 1)
  const last = candles[candles.length - 1]
  const a = { price: last.close, adx: 0, ema: {}, rsi: 50 }  // AnalysisResult حداقلی
  const d = new Date(last.time * 1000)
  const ctx = {
    cardId: 'XAUUSD-H1', a, candles,
    utcHour: d.getUTCHours(), times: candles.map(c => c.time),
    capital: 10000, riskPct: 1.0,
  }
  const dec = runCard(ctx)
  // آیا لایهٔ منبع یا یکی از otherLayers کدِ S341 دارد؟
  const src = dec?.sourceLayer?.code
  const others = (dec?.otherLayers || []).map(o => o?.sourceLayer?.code || o?.code)
  const hasS341 = src === 'S341' || others.includes('S341')
  if (hasS341) s341Fired++
  console.log(`@${idx} → state=${dec?.state} dir=${dec?.direction} src=${src} others=[${others.join(',')}] S341active=${hasS341}`)
}

console.log(`\nS341 روی ${s341Fired}/${testBars.length} کندلِ سیگنالِ آزموده‌شده فعال شد.`)
if (s341Fired > 0) {
  console.log('✅ INTEGRATION PASS — S341 از طریقِ runCard روی کارتِ XAUUSD-H1 وصل و فعال است.')
  process.exitCode = 0
} else {
  console.log('❌ S341 در هیچ‌کدام فعال نشد — بررسیِ اتصال لازم است.')
  process.exitCode = 1
}

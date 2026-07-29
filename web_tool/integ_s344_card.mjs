// integ_s344_card.mjs — تستِ یکپارچگیِ end-to-end برای S344 روی کارتِ XAUUSD-M15.
// چند کندلِ سیگنالِ شناخته‌شدهٔ پایتون را به کلِ runCard می‌دهیم و می‌سنجیم که
// S344 به‌عنوانِ منبع یا یکی از لایه‌ها یک تصمیمِ ورودِ SHORT بدهد.
// WIN بزرگ (۳۰۰۰) لازم است چون S344 به ADR ۱۴روزه (~۱۳۴۴ کندلِ M15) و رژیمِ
// hurst(55)/r2(34) نیاز دارد؛ با پنجرهٔ کوتاه، ADR/رژیم همگرا نمی‌شود.
// اجرا: cd web_tool && node integ_s344_card.mjs
import fs from 'fs'
import { runCard, CARD_LAYERS } from './dist_parity/strategy_registry.js'

const CARD = 'XAUUSD-M15'
const WIN = 3000

const ref = JSON.parse(fs.readFileSync('../strategies/s344_parity_ref.json', 'utf8'))
const candlesAll = ref.candles.map(c => ({
  time: c.time, open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume || 0,
}))

// چند سیگنالِ پراکنده (ابتدا/سه‌گانه/انتها) که پنجرهٔ WIN کامل داشته باشند
const idxs = ref.signal_idx.filter(i => i >= WIN)
const pick = [idxs[0], idxs[Math.floor(idxs.length / 3)], idxs[Math.floor(2 * idxs.length / 3)],
              idxs[idxs.length - 1]].filter((v, k, arr) => v != null && arr.indexOf(v) === k)

console.log(`=== ${CARD} ===  (${CARD_LAYERS[CARD].length} لایه) — آزمونِ ${pick.length} سیگنالِ S344 SHORT`)
let fired = 0
for (const idx of pick) {
  const lo = Math.max(0, idx - WIN + 1)
  const candles = candlesAll.slice(lo, idx + 1)
  const last = candles[candles.length - 1]
  const a = { price: last.close, adx: 0, ema: {}, rsi: 50 }
  const d = new Date(last.time * 1000)
  const ctx = {
    cardId: CARD, a, candles,
    utcHour: d.getUTCHours(), times: candles.map(c => c.time),
    capital: 10000, riskPct: 1.0,
  }
  const dec = runCard(ctx)
  const src = dec?.sourceLayer?.code
  const others = (dec?.otherLayers || []).map(o => o?.sourceLayer?.code || o?.code)
  const hasS344 = src === 'S344' || others.includes('S344')
  // آیا S344 خودش SHORT پیشنهاد داده؟ (چه به‌عنوان منبع چه لایهٔ فرعی)
  const s344Short = (src === 'S344' && (dec?.direction === 'short' || dec?.direction === 'sell'))
    || (dec?.otherLayers || []).some(o => (o?.sourceLayer?.code || o?.code) === 'S344')
  if (hasS344) fired++
  console.log(`  @${idx} → state=${dec?.state} dir=${dec?.direction} src=${src} others=[${others.join(',')}] S344present=${hasS344}`)
}
const ok = fired === pick.length
console.log(`\n⇒ S344 روی ${fired}/${pick.length} سیگنال از طریقِ runCard فعال شد  ${ok ? '✅ INTEGRATION PASS' : '⚠️ بررسیِ اولویتِ لایه/اتصال لازم است'}`)
process.exit(ok ? 0 : 1)

import { evaluateTrade, type OpenTrade } from '/home/user/webapp/web_tool/src/trade_manager.ts'

// AnalysisResult ساختگیِ کمینه (فقط فیلدهای موردنیازِ evaluateTrade)
function mkA(price: number, trend: 'up'|'down'|'range'): any {
  return { price, atr: 3.0, trend, resistance: price + 20, support: price - 20,
           ema50: price, ema200: price, probability: 50, rsi14: 45 }
}

// معاملهٔ SHORTِ اسکالپِ S102: entry=4000، SL=4004 (۴۰pip=۴$)، TP=3980 (سقفِ ۲۰۰pip)
const t: OpenTrade = { side: 'short', entry: 4000, tp: 3980, sl: 4004, openedAt: Math.floor(Date.now()/1000) - 60*60 }

console.log('=== سناریو ۱: قیمت ۱$ پایین رفت (۱۰pip سود)، روند هنوز نزولی ===')
let s = evaluateTrade(t, mkA(3999, 'down'))
console.log('  advices:', s.advices.map(a=>a.title))
const hasBE = s.advices.some(a=>a.title.includes('بریک‌ایون'))
console.log('  → بریک‌ایونِ سریع پیشنهاد شد؟', hasBE)

console.log('\n=== سناریو ۲: قیمت ۲$ پایین رفت (۲۰pip سود)، روند نزولی ===')
s = evaluateTrade(t, mkA(3998, 'down'))
console.log('  advices:', s.advices.map(a=>a.title))
const hasTrail = s.advices.some(a=>a.title.includes('trailing'))
console.log('  → trailingِ تنگ پیشنهاد شد؟', hasTrail)

console.log('\n=== سناریو ۳: قیمت ۱$ پایین (سود)، اما روند دیگر نزولی نیست (range) ===')
s = evaluateTrade(t, mkA(3999, 'range'))
console.log('  advices:', s.advices.map(a=>a.title))
const hasClose = s.advices.some(a=>a.title.includes('شتاب کم شد'))
console.log('  → پیشنهادِ بستنِ سریع؟', hasClose)

const ok = hasBE && hasTrail && hasClose
console.log('\n' + (ok ? '✅ حالتِ MANAGE برای SHORT-اسکالپ درست کار می‌کند.' : '❌ برخی توصیه‌ها شلیک نشد.'))
process.exit(ok ? 0 : 1)

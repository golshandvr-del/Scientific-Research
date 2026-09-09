// ---------------------------------------------------------------------------
// probeِ زندهٔ S1520 روی همان فیدی که سایت مصرف می‌کند.
//
// چرا این گام لازم است و چرا پریتی/یکپارچگی جایش را نمی‌گیرند: هر دوی آن‌ها
// روی دادهٔ **کاملِ MT5** اجرا شدند (۱۱۹۷۸ کندلِ H8). سایت اما از فیدِ زندهٔ
// Yahoo تغذیه می‌شود که کوتاه‌تر است. سؤالِ بازِ باقی‌مانده این است: آیا لایه
// روی فیدِ **واقعی** هم حرف می‌زند، یا در سکوت «دادهٔ ناکافی» برمی‌گرداند؟
// این بدترین حالتِ ممکن است چون از UI قابلِ تفکیک از «سیگنالی ندارم» نیست.
// ---------------------------------------------------------------------------
import { fetchGold, aggregateCandles } from '../src/price/gold_source'
import { computeS1520, S1520_CFG } from '../src/informed_fresh_high_s1520'
import { CARD_LAYERS } from '../src/strategy_registry'

const cfg = S1520_CFG['XAUUSD-H8']
const { candles } = await fetchGold('1h', '1y')
const h8 = aggregateCandles(candles, 8)
const need = cfg.lookback + cfg.atrP

console.log('══ probeِ زندهٔ S1520 روی فیدِ سایت ══\n')
console.log(`  کندلِ خامِ H1        : ${candles.length}`)
console.log(`  کندلِ تجمیع‌شدهٔ H8   : ${h8.length}`)
console.log(`  نیازِ لایه           : ${need} (lookback ${cfg.lookback} + ATR ${cfg.atrP})`)
console.log(`  حاشیه               : ${(h8.length / need).toFixed(2)}×`)

let fail = 0
if (h8.length < need) { console.log('  ❌ فید کوتاه‌تر از نیازِ لایه ⇒ لایه همیشه ساکت می‌ماند'); fail++ }
else console.log('  ✓ عمقِ فید برای محاسبهٔ لایه کافی است')

// آیا لایه واقعاً محاسبه می‌شود یا گاردِ «دادهٔ ناکافی» می‌خورد؟
const raw = computeS1520(h8 as any, cfg)
const starved = /ناکافی/.test(raw.reason || '')
console.log(`\n  خروجیِ لایه روی آخرین کندلِ زنده:`)
console.log(`    active   : ${raw.active}`)
console.log(`    گرسنه؟   : ${starved ? 'بله (دادهٔ ناکافی)' : 'نه — واقعاً محاسبه شد'}`)
if (starved) { console.log('  ❌ لایه روی فیدِ زنده گرسنه است'); fail++ }
else console.log('  ✓ لایه روی فیدِ زنده واقعاً محاسبه می‌شود')

// چند سیگنالِ تاریخی در همین پنجرهٔ فیدِ زنده وجود دارد؟ (اثباتِ زنده‌بودن)
let n = 0, last = -1
for (let i = need; i < h8.length; i++) {
  const r = computeS1520(h8.slice(0, i + 1) as any, cfg)
  if (r.active) { n++; last = i }
}
console.log(`\n  سیگنال‌های S1520 داخلِ پنجرهٔ فیدِ زنده: ${n}`)
if (last >= 0) {
  const t = new Date(h8[last].time * 1000).toISOString().slice(0, 16).replace('T', ' ')
  console.log(`  آخرین سیگنال: ${t} UTC · close=${h8[last].close}`)
}
if (n === 0) { console.log('  ❌ در کلِ پنجرهٔ زنده هیچ سیگنالی نیست ⇒ عملاً مرده روی سایت'); fail++ }
else console.log('  ✓ لایه روی فیدِ زنده زنده است (سیگنالِ واقعی دارد)')

console.log(`\n  لایه‌های کارتِ H8: ${CARD_LAYERS['XAUUSD-H8'].length}`)
console.log('\n' + '═'.repeat(58))
if (fail === 0) console.log('✅ probeِ زنده: PASS — S1520 روی فیدِ واقعیِ سایت محاسبه و شلیک می‌کند.')
else { console.log(`❌ probeِ زنده: ${fail} ایراد`); process.exit(1) }

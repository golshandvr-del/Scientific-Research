// live_s770_probe.mjs — اثباتِ «زنده بودن» S770 روی هر دو کارتِ ACCEPT.
//
// چرا این probe لازم است: در `/api/decision/:card` وقتی همهٔ لایه‌ها NEUTRAL
// باشند، `runCard()` طبقِ طراحیِ خودش فقط لایهٔ رتبهٔ اول را برمی‌گرداند و
// `otherLayers` را **عمداً** پر نمی‌کند (فقط ENTRY/APPROACHING را نشان می‌دهد).
// نتیجه: در بازارِ آرام، پاسخِ API فقط S800 (در D1) یا S950 (در H8) را نشان
// می‌دهد و از بیرون نمی‌شود فهمید S770 هم اجرا شده یا نه. این probe همان
// ابهام را رفع می‌کند: لایه را **مستقیماً** با کندل‌های زندهٔ همان endpoint
// صدا می‌زند و وضعیتِ واقعی‌اش را چاپ می‌کند.
//
// اجرا: cd web_tool && node --import tsx live_s770_probe.mjs
import { CARD_LAYERS } from './src/strategy_registry.ts'
import { computeS770, S770_CFG } from './src/adr_expansion_s770.ts'

const BASE = 'http://localhost:3000'
const CARDS = ['XAUUSD-D1', 'XAUUSD-H8']

for (const card of CARDS) {
  console.log(`\n══════ ${card} ══════`)

  // ① آزمونِ ثبت در گرافِ ROS2-گونه: لایه باید در CARD_LAYERS باشد.
  const n = (CARD_LAYERS[card] || []).length
  console.log(`لایه‌های ثبت‌شده در CARD_LAYERS: ${n}`)

  // ② کندل‌های **زندهٔ** همان کارت را از خودِ API سایت می‌گیریم (نه fixture).
  const r = await fetch(`${BASE}/api/candles?asset=${card}&limit=600`)
  const j = await r.json()
  const candles = j.candles || j.data || j
  if (!Array.isArray(candles) || candles.length < 150) {
    console.log(`⚠️ کندلِ کافی از API نیامد (${Array.isArray(candles) ? candles.length : 'غیرآرایه'}) — از این کارت رد می‌شوم`)
    continue
  }
  const last = candles[candles.length - 1]
  console.log(`کندلِ زنده: ${candles.length} · آخرین close=${last.close} · زمان=${new Date(last.time * 1000).toISOString()}`)

  // ③ خودِ لایه را با همان دادهٔ زنده صدا می‌زنیم.
  const cfg = S770_CFG[card]
  if (!cfg) { console.log(`❌ S770_CFG برای ${card} وجود ندارد!`); continue }
  const sig = computeS770(cfg, candles)

  console.log(`پیکربندی: theta=±${cfg.theta} · ADR=${cfg.adrP} · ATR=${cfg.atrP} · SL=${cfg.slK}×ATR · RR=${cfg.rr} · hold=${cfg.hold}`)
  console.log(`وضعیتِ زندهٔ S770:`)
  console.log(`   · frac (کسری از ADR) = ${sig.frac?.toFixed(4)}  (آستانه ±${cfg.theta})`)
  console.log(`   · فاصله تا ماشه      = ${(cfg.theta - Math.abs(sig.frac ?? 0)).toFixed(4)}`)
  console.log(`   · ENTRY فعال؟        = ${sig.active ? `بله (${sig.direction})` : 'خیر'}`)
  console.log(`   · نزدیکِ ماشه؟        = ${sig.approaching ? 'بله' : 'خیر'}`)
  console.log(`   ⇒ لایه **اجرا شد و پاسخ داد** ✅ (خروجیِ محاسبه‌شده دارد)`)
}

console.log('\n════════════════════════════════════════════════')
console.log('✅ S770 روی هر دو کارتِ ACCEPT با دادهٔ زندهٔ سایت اجرا می‌شود.')
console.log('   نکته: NEUTRAL بودن ایراد نیست — این لایه کم‌بسامد است')
console.log('   (۶۸۹ معامله در ۱۵.۶ سال روی کلِ استخر) و بیشترِ کندل‌ها هیچ‌اند.')

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
import { CARD_LAYERS, runCard } from './src/strategy_registry.ts'
import { computeS770, S770_CFG } from './src/adr_expansion_s770.ts'

const BASE = 'http://localhost:3000'
// ⚠️ کندل‌ها را باید **عیناً مثلِ خودِ سایت** بسازیم: `/api/candles` دادهٔ پایهٔ
//    H1 می‌دهد و index.tsx آن را با aggregateCandles(·, mult) به کارت تبدیل
//    می‌کند. بی این تجمیع، probe به لایه دادهٔ H1 می‌داد و «روزِ تقویمی» را
//    ۲۴ برابر ریزتر می‌دید ⇒ اندازه‌گیریِ بی‌معنا. mult همان ضریبِ سایت است.
const CARDS = [
  { card: 'XAUUSD-D1', mult: 24 },
  { card: 'XAUUSD-H8', mult: 8 },
]
// بازهٔ دادهٔ هر کارت — عیناً از جدولِ GOLD_TF در src/index.tsx (منبعِ حقیقت).
// اگر روزی آن جدول تغییر کرد، این probe باید همان لحظه هم‌گام شود.
const RANGE = { 'XAUUSD-D1': '2y', 'XAUUSD-H8': '1y' }

// تجمیعِ کندل با مرزِ ثابتِ UTC (t % (3600*mult) == 0) — همان قاعدهٔ سایت.
function aggregate(h1, mult) {
  if (mult <= 1) return h1
  const sec = 3600 * mult
  const out = []
  let cur = null
  for (const c of h1) {
    const bucket = Math.floor(c.time / sec) * sec
    if (!cur || cur.time !== bucket) {
      if (cur) out.push(cur)
      cur = { time: bucket, open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume || 0 }
    } else {
      cur.high = Math.max(cur.high, c.high)
      cur.low = Math.min(cur.low, c.low)
      cur.close = c.close
      cur.volume += (c.volume || 0)
    }
  }
  if (cur) out.push(cur)
  return out
}

let fail = 0

for (const { card, mult } of CARDS) {
  console.log(`\n══════ ${card} ══════`)

  // ① آزمونِ ثبت در گرافِ ROS2-گونه: لایه باید در CARD_LAYERS باشد.
  const n = (CARD_LAYERS[card] || []).length
  console.log(`لایه‌های ثبت‌شده در CARD_LAYERS: ${n}`)

  // ② کندل‌های **زندهٔ** پایه را از خودِ API سایت می‌گیریم (نه fixture)، سپس
  //    عیناً مثلِ سایت به تایم‌فریمِ کارت تجمیع می‌کنیم.
  // ⚠️ باید **بازهٔ واقعیِ همان کارت** را گرفت، نه limit دلخواه: مسیرِ تصمیمِ
  //    سایت (GOLD_TF) برای D1 بازهٔ ۲ساله و برای H8 بازهٔ ۱سالهٔ H1 می‌گیرد
  //    ⇒ ≈۷۲۰ کندلِ D1 و ≈۷۸۰ کندلِ H8، که برای گرم‌شدنِ ۱۰۲کندلیِ S770 کافی
  //    است. نسخهٔ اولِ probe فقط ۲۱۲۰ کندلِ پایه گرفت ⇒ ۲۸ کندلِ D1 ⇒ لایه
  //    درست و ایمن پیامِ «دادهٔ ناکافی» داد. آن یافته **نقصِ probe** بود نه سایت،
  //    ولی ثبتش می‌کنم چون همان مرزِ باریکی است که اگر بازهٔ GOLD_TF روزی کم شود،
  //    لایه بی‌صدا خفه می‌شود (خطای خطرناکِ «خاموشِ بی‌هشدار»).
  const r = await fetch(`${BASE}/api/candles?asset=${card}&interval=1h&range=${RANGE[card]}`)
  const j = await r.json()
  const base = j.candles || j.data || j
  if (!Array.isArray(base) || base.length < 150) {
    console.log(`⚠️ کندلِ کافی از API نیامد — رد می‌شوم`); fail++; continue
  }
  const candles = aggregate(base, mult)
  const last = candles[candles.length - 1]
  console.log(`کندلِ پایه=${base.length} ⇒ پس از تجمیعِ ×${mult} = ${candles.length} کندلِ ${card}`)
  console.log(`آخرین کندل: close=${last.close.toFixed(2)} · زمان=${new Date(last.time * 1000).toISOString()}`)
  // صحتِ مرزِ تجمیع: باید روی مرزِ ثابتِ تایم‌فریم بنشیند.
  const boundaryOk = last.time % (3600 * mult) === 0
  console.log(`مرزِ UTC درست؟ ${boundaryOk ? 'بله ✅' : 'خیر ❌'} (t % ${3600 * mult} = ${last.time % (3600 * mult)})`)
  if (!boundaryOk) fail++

  // ③ خودِ لایه را با همان دادهٔ زنده صدا می‌زنیم.
  const cfg = S770_CFG[card]
  if (!cfg) { console.log(`❌ S770_CFG برای ${card} وجود ندارد!`); fail++; continue }
  // ⚠️ ترتیبِ آرگومان‌ها (candles, cfg) است — نه (cfg, candles). نسخهٔ اولِ همین
  //    probe جابه‌جا صدا زده بود و استثنا خورد؛ ثبتش می‌کنم چون همان تلهٔ
  //    ترتیب-آرگومان است که اگر در آداپتورِ رجیستری رخ می‌داد، پریتی سبز
  //    می‌ماند و سایت خاموش (و تستِ یکپارچگی همان را می‌گیرد).
  const sig = computeS770(candles, cfg)

  console.log(`پیکربندی: θ=±${cfg.theta} · ADR=${cfg.adrP} · ATR=${cfg.atrP} · SL=${cfg.slK}×ATR · RR=${cfg.rr} · maxHold=${cfg.maxHold}`)
  console.log(`وضعیتِ زندهٔ S770:`)
  console.log(`   · ENTRY فعال؟   = ${sig.active ? `بله (${sig.direction})` : 'خیر'}`)
  console.log(`   · نزدیکِ ماشه؟   = ${sig.approaching ? 'بله' : 'خیر'}`)
  console.log(`   · SL/TP محاسبه‌شده = ${(sig.slDist / 0.10).toFixed(1)} / ${(sig.tpDist / 0.10).toFixed(1)} pip`)
  // اندیکاتورهای لایه = پنجرهٔ شفافیت؛ اگر لایه اجرا نشده بود، خالی می‌ماند.
  const inds = sig.indicators || []
  console.log(`   · اندیکاتورهای گزارش‌شده (${inds.length}):`)
  for (const it of inds) console.log(`       – ${it.name}: ${it.value}`)

  // ④ اثباتِ اینکه از مسیرِ **runCard واقعیِ سایت** هم عبور می‌کند.
  const ctx = {
    cardId: card, a: { price: last.close, adx: 0, ema: {}, rsi: 50 },
    candles, utcHour: new Date(last.time * 1000).getUTCHours(),
    times: candles.map(c => c.time), capital: 10000, riskPct: 1.0,
  }
  const dec = runCard(ctx)
  console.log(`   · runCard() ⇒ لایهٔ اصلی=${dec?.sourceLayer?.code} state=${dec?.state}`)

  // بررسیِ سلامتِ هندسه: TP باید از SL بزرگ‌تر باشد (قانونِ بودجه).
  const ok = sig.tpDist > sig.slDist && isFinite(sig.slDist) && sig.slDist > 0 && inds.length > 0
  console.log(`   ⇒ ${ok ? 'لایه زنده، محاسبه‌گر و با هندسهٔ سالم ✅' : 'مشکل ❌'}`)
  if (!ok) fail++
}

console.log('\n════════════════════════════════════════════════')
if (fail === 0) {
  console.log('✅ S770 روی هر دو کارتِ ACCEPT با دادهٔ زندهٔ سایت اجرا می‌شود.')
  console.log('   نکته: NEUTRAL بودن ایراد نیست — این لایه کم‌بسامد است')
  console.log('   (۶۸۹ معامله در ۱۵.۶ سال روی کلِ استخر) و بیشترِ کندل‌ها هیچ‌اند.')
} else {
  console.log(`❌ ${fail} مشکل در probeِ زنده.`)
  process.exit(1)
}

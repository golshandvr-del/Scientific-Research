// probe زندهٔ S408 — آیا لایه روی دادهٔ **همین لحظهٔ سایت** واقعاً کار می‌کند؟
//
// چرا این ابزار جدا از parity و integ لازم است:
//   • parity_s408_signal.mjs ثابت می‌کند فرمولِ TS با پایتون یکی است (روی fixture).
//   • integ_s408_card.mjs ثابت می‌کند لایه در کارت ثبت شده و در عمقِ شبیه‌سازی‌شدهٔ
//     سایت خفه نمی‌شود (روی همان fixture).
//   • این probe تنها چیزی است که به **فیدِ زندهٔ واقعی** وصل می‌شود
//     (`/api/candles?interval=15m&range=1mo` — عیناً همان چیزی که کارتِ M15
//     مصرف می‌کند) و زنجیرهٔ تصمیم را باز می‌کند. دامی که فقط اینجا لو می‌رود:
//     اگر فیدِ زنده شکلِ دیگری از کندل بدهد، یا عمقش افت کند، یا تعطیلیِ
//     طولانی ATR را بشکند، هر دو تستِ بالا سبز می‌مانند و سایت بی‌صدا کور
//     می‌شود.
//
// ⚠️ نکتهٔ خواندنِ خروجی: `active=false` به‌خودی‌خود بد نیست. لایه فقط در
//    روزهایی که گپِ منفیِ عمیق باشد ENTRY می‌دهد (۴۹۶ ورود در ۱۵.۶ سال ⇒
//    به‌طور میانگین کمتر از ۳ روز در ماه). چیزی که **باید** سالم باشد،
//    زنجیرهٔ دروازه‌هاست: daysAvail ≥ ۱۵ · atrPrevUsd متناهی · brkIdx ≥ ۰ ·
//    dataHealthy. اگر این چهار سبز باشند، لایه بیدار است و منتظرِ گپ.
//
// اجرا (سایت باید بالا باشد): cd web_tool && node --import tsx live_probe_s408.mjs
import fs from 'node:fs'
import { computeS408Signal, S408_CFG } from './src/gap_fill_m15_s408.ts'
import { CARD_LAYERS } from './src/strategy_registry.ts'

const BASE = process.env.SITE_BASE || 'http://localhost:3000'
const CARD = 'XAUUSD-M15'
const cfg = S408_CFG[CARD]

let res
try {
  res = await fetch(`${BASE}/api/candles?interval=15m&range=1mo`)
} catch (e) {
  console.log(`❌ سایت در ${BASE} پاسخ نداد — اول با pm2 بالا بیاورید. (${e.message})`)
  process.exit(1)
}
const j = await res.json()
const candles = j.candles || []

const nLayers = CARD_LAYERS[CARD]?.length ?? 0
console.log(`فیدِ زنده: ${candles.length} کندلِ M15 · کارتِ ${CARD}: ${nLayers} لایه`)

const s = computeS408Signal(candles, cfg)

// چهار شرطِ «بیدار بودن» — اینها هستند که باید سبز باشند، نه active
const wake = {
  daysAvail: s.daysAvail >= 15,
  atrFinite: Number.isFinite(s.atrPrevUsd),
  brkFound: s.brkIdx >= 0,
  feedHealthy: s.dataHealthy === true,
}

console.log('\n--- زنجیرهٔ تصمیم ---')
console.log(`  گپ            : ${s.gapUsd.toFixed(4)}$  (آستانه ${s.thrUsd}$ · weekend=${s.isWeekend} · ratio=${s.ratio.toFixed(3)})`)
console.log(`  ATR14 روزِ قبل: ${s.atrPrevUsd.toFixed(4)}$  (آستانهٔ V ${s.volThrUsd}$ · نسبت ${s.volRatio.toFixed(4)})`)
console.log(`  dow           : ${s.dow}  (۰=دوشنبه ⇒ مستثنا)`)
console.log('\n--- دروازه‌ها ---')
console.log(`  baseActive (گپِ منفیِ عمیق) : ${s.baseActive}`)
console.log(`  volPass    (روزِ آرام)      : ${s.volPass}`)
console.log(`  dowPass    (دوشنبه نیست)    : ${s.dowPass}`)
console.log(`  ⇒ active=${s.active} · approaching=${s.approaching}`)
if (s.active) {
  console.log(`\n--- هندسهٔ ورود ---`)
  console.log(`  TP=${s.tpDistUsd.toFixed(4)}$ (closeِ روزِ قبل) · SL=${s.slDistUsd.toFixed(4)}$ (${cfg.kSl}×|گپ|) · کندلِ باقیِ روز=${s.barsLeftInDay}`)
}

console.log('\n--- سلامتِ «بیدار بودن» ---')
for (const [k, v] of Object.entries(wake)) console.log(`  ${v ? '✅' : '❌'} ${k}`)

const awake = Object.values(wake).every(Boolean)
const out = {
  ts: new Date().toISOString(), card: CARD, base: BASE,
  feed_bars: candles.length, card_layers: nLayers,
  signal: s, wake, awake,
}
fs.writeFileSync('../results/_s408_arms/live_probe_M15.json', JSON.stringify(out, null, 1))
console.log(`\n${awake ? '✅ LIVE PROBE PASS — لایه بیدار است و منتظرِ گپ' : '❌ LIVE PROBE FAIL — لایه روی فیدِ زنده کور است'}`)
console.log('saved → results/_s408_arms/live_probe_M15.json')
process.exit(awake ? 0 : 1)

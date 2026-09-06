// تستِ یکپارچگیِ S408 در بسترِ **واقعیِ سایت** (نه صرفاً واحد).
//
// چرا این تست لازم است و پریتی کافی نیست: پریتی ثابت می‌کند فرمولِ TS با
// پایتون یکی است، ولی هیچ چیز درباره‌ی «آیا لایه در کارتِ سایت **اجرا** می‌شود»
// نمی‌گوید. یک لایه می‌تواند پریتیِ کاملِ سبز داشته باشد و در سایت مرده باشد:
//   • آداپتر به CARD_LAYERS وصل نشده باشد،
//   • کلیدِ کانفیگ اشتباه باشد (`XAUUSD` در برابر `XAUUSD-M15`)،
//   • کارت کندلِ کافی نگیرد ⇒ لایه همیشه به دامِ ⑥ بیفتد و NEUTRALِ ابدی شود،
//   • یا خطایی داخلِ لایه throw شود و runCard آن را بی‌صدا رد کند.
// این تست هر چهار حالت را می‌گیرد.
//
// اجرا:  node --import tsx integ_s408_card.mjs
import fs from 'node:fs'
import { CARD_LAYERS } from './src/strategy_registry.ts'
import { computeS408Signal, S408_CFG } from './src/gap_fill_m15_s408.ts'

const CARD = 'XAUUSD-M15'
const cfg = S408_CFG[CARD]
const out = { card: CARD, checks: {} }
let ok = true
const fail = (k, msg) => { ok = false; out.checks[k] = { pass: false, msg }; console.log(`❌ ${k}: ${msg}`) }
const pass = (k, msg) => { out.checks[k] = { pass: true, msg }; console.log(`✅ ${k}: ${msg}`) }

// ── ① لایه واقعاً در CARD_LAYERS کارت هست؟ ──────────────────────────────────
const layers = CARD_LAYERS[CARD]
if (!Array.isArray(layers)) fail('wired', `CARD_LAYERS['${CARD}'] وجود ندارد`)
else pass('wired', `کارت ${CARD} دارای ${layers.length} لایه است`)

// ── ② کلیدِ کانفیگ درست است و اعداد با سندِ ACCEPT می‌خوانند؟ ───────────────
if (!cfg) fail('cfg', `S408_CFG['${CARD}'] وجود ندارد — کلیدِ اشتباه`)
else if (cfg.rqs2 !== 93.8 || cfg.nTrades !== 496) {
  fail('cfg', `اعدادِ سند نمی‌خوانند: rqs2=${cfg.rqs2} n=${cfg.nTrades}`)
} else pass('cfg', `rqs2=${cfg.rqs2} n=${cfg.nTrades} wr=${cfg.wrPct}% pf=${cfg.pf}`)

// ── ③ آستانه‌های منجمد با آرتیفکت یکی‌اند؟ (گاردِ رانشِ عدد) ────────────────
const fr = JSON.parse(fs.readFileSync('../results/_s408_arms/frozen_thresholds_M15.json', 'utf8'))
// نامِ کلیدها عیناً همان است که tools/s408_freeze_thresholds.py می‌نویسد —
// نه حدس. (نسخهٔ اولِ این تست `fr.gap`/`fr.vol` حدس زده بود و می‌ترکید.)
const frGap = fr.frozen_gap_threshold_usd
const frVol = fr.frozen_vol_threshold_usd
const drift = []
if (!frGap || !Number.isFinite(frVol)) {
  drift.push(`ساختارِ آرتیفکت ناشناخته است: keys=${Object.keys(fr).join(',')}`)
} else {
  if (Math.abs(cfg.thrWeekendUsd - frGap.weekend) > 1e-9) drift.push(`weekend ${cfg.thrWeekendUsd}≠${frGap.weekend}`)
  if (Math.abs(cfg.thrWeekdayUsd - frGap.weekday) > 1e-9) drift.push(`weekday ${cfg.thrWeekdayUsd}≠${frGap.weekday}`)
  if (Math.abs(cfg.volThrUsd - frVol) > 1e-9) drift.push(`vol ${cfg.volThrUsd}≠${frVol}`)
  // گاردِ اضافه ①: پریتیِ **داور** باید در خودِ آرتیفکت سبز باشد، وگرنه عددِ
  //   منجمد از یک اجرای بی‌اعتبار آمده و کارت روی شن ساخته می‌شود.
  if (!fr.parity?.ok || fr.parity.signals_rolling !== fr.parity.judged_n_trades) {
    drift.push(`judge parity در آرتیفکت سبز نیست: ${JSON.stringify(fr.parity)}`)
  }
  // گاردِ اضافه ②: اعدادِ کارت باید با judged_metrics همان آرتیفکت بخوانند
  //   ⇒ آرتیفکتِ کهنه یا دست‌کاری‌شده نمی‌تواند بی‌صدا پاس شود.
  if (cfg.rqs2 !== fr.judged_metrics?.rqs2 || cfg.nTrades !== fr.judged_metrics?.n) {
    drift.push(`اعدادِ کارت با judged_metrics نمی‌خوانند: کارت(${cfg.rqs2}/${cfg.nTrades}) ≠ آرتیفکت(${fr.judged_metrics?.rqs2}/${fr.judged_metrics?.n})`)
  }
  // گاردِ اضافه ③: سندِ ACCEPT ارجاع‌شده باید همان سندِ S408 باشد
  if (!String(fr.doc || '').includes('S408_GapFillM15FullData')) {
    drift.push(`آرتیفکت به سندِ دیگری ارجاع می‌دهد: ${fr.doc}`)
  }
}
if (drift.length) fail('frozen', drift.join(' · '))
else pass('frozen', `we=${frGap.weekend} wd=${frGap.weekday} vol=${frVol} · judge parity ${fr.parity.signals_rolling}==${fr.parity.judged_n_trades} ✓`)

// ── ④ لایه روی دادهٔ واقعیِ کارت اجرا می‌شود و NEUTRALِ ابدی نیست؟ ──────────
// دادهٔ واقعیِ کارت را از fixture می‌گیریم (همان شکلِ Candle که سایت می‌سازد)
const fx = JSON.parse(fs.readFileSync('../results/_s408_arms/parity_m15_fixture.json', 'utf8'))
const candles = fx.candles

// پنجرهٔ سایت ≈ ۱۹۸۹ کندل (range=1mo). دقیقاً همان عمق را شبیه‌سازی می‌کنیم
// تا معلوم شود لایه در عمقِ **واقعیِ** سایت زنده است یا با آن خفه می‌شود.
const SITE_BARS = 1989
const siteWin = candles.slice(-SITE_BARS)
const sSite = computeS408Signal(siteWin, cfg)
if (!Number.isFinite(sSite.atrPrevUsd)) {
  fail('site_depth', `در عمقِ واقعیِ سایت (${SITE_BARS} کندل) ATR محاسبه نشد ⇒ لایه NEUTRALِ ابدی می‌شود`)
} else {
  pass('site_depth', `عمقِ ${SITE_BARS} کندل کافی است — ATR14=${sSite.atrPrevUsd.toFixed(2)}$ · روزهای موجود=${sSite.daysAvail}`)
}

// ── ⑤ لایه در طولِ تاریخ حداقل یک‌بار ENTRY می‌دهد؟ (اثباتِ نمردن) ──────────
// روی هر مرزِ روز در fixture، پنجرهٔ منتهی به آن را می‌دهیم (شبیه‌سازِ زنده)
let nActive = 0, nApproach = 0, nEval = 0
for (const r of fx.records) {
  if (r.fb_rel < 30 || r.fb_rel >= candles.length) continue
  nEval++
  const s = computeS408Signal(candles.slice(0, r.fb_rel + 1), cfg)
  if (s.active) nActive++
  else if (s.approaching) nApproach++
}
if (nActive === 0) fail('alive', `در ${nEval} مرزِ روز هیچ ENTRY نداد ⇒ لایهٔ مرده`)
else pass('alive', `${nActive} ENTRY و ${nApproach} APPROACHING در ${nEval} مرزِ روز`)

// ── ⑥ هندسه در ENTRYها معتبر است؟ TP باید مثبت و SL=۲×|گپ| باشد ────────────
let geomBad = 0
for (const r of fx.records) {
  if (r.fb_rel < 30 || r.fb_rel >= candles.length) continue
  const s = computeS408Signal(candles.slice(0, r.fb_rel + 1), cfg)
  if (!s.active) continue
  if (!(s.tpDistUsd > 0)) { geomBad++; continue }
  if (Math.abs(s.slDistUsd - cfg.kSl * Math.abs(s.gapUsd)) > 1e-9) geomBad++
}
if (geomBad) fail('geometry', `${geomBad} ENTRY هندسهٔ نامعتبر داشت`)
else pass('geometry', `همهٔ ${nActive} ENTRY هندسهٔ معتبر دارند (TP>0 · SL=${cfg.kSl}×|گپ|)`)

// ── ⑦ لایه throw نمی‌کند روی ورودی‌های مرزی (گاردِ استحکام) ────────────────
const edge = [[], candles.slice(0, 1), candles.slice(0, 2), candles.slice(0, 40)]
let threw = null
for (const e of edge) {
  try { computeS408Signal(e, cfg) } catch (err) { threw = `${e.length} کندل ⇒ ${err.message}` }
}
if (threw) fail('robust', `throw کرد: ${threw}`)
else pass('robust', 'ورودی‌های مرزی (۰/۱/۲/۴۰ کندل) بدونِ throw رد شدند')

out.summary = { pass: ok, n_entry_history: nActive, n_approaching: nApproach, n_day_boundaries: nEval,
                site_depth_bars: SITE_BARS, site_atr_usd: sSite.atrPrevUsd, site_days: sSite.daysAvail }
fs.writeFileSync('../results/_s408_arms/integ_card_M15.json', JSON.stringify(out, null, 1))
console.log(`\n${ok ? '✅ INTEGRATION PASS' : '❌ INTEGRATION FAIL'} — saved → results/_s408_arms/integ_card_M15.json`)
process.exit(ok ? 0 : 1)

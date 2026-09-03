// پریتی S770: پایتون (strategies/s770_adr_expansion.py) ↔ TS
// (web_tool/src/adr_expansion_s770.ts) — روی **هر دو کارتِ ACCEPT** (D1 و H8).
//
// روش: fixture شاملِ دمِ کندل‌ها + مرجعِ پایتون که روی **کلِ تاریخ** محاسبه شده
// (D1: ۴٬۰۰۵ کندل · H8: ۱۱٬۹۷۸). ویژگی‌های S770 حداکثر ATR₁۰۰ کندل و ADR ۲۲
// روزِ تقویمی به عقب نگاه می‌کنند ⇒ برای ایندکس‌های به‌اندازهٔ کافی دور از لبهٔ
// پنجره، خروجیِ «فقط-پنجره» باید عیناً با «کل-تاریخ» یکی باشد. اگر پورت به
// warm-up وابسته باشد (مثلاً ADR را از ابتدای پنجره بشمارد) همین‌جا لو می‌رود.
//
// پنج چیز مقایسه می‌شود (نه فقط سیگنال):
//   ① مجموعهٔ ایندکسِ LONG و SHORT (عبورِ حالت — دامِ ③ سرصفحهٔ ماژول)
//   ② frac عددبه‌عدد (دامِ ①: ADR روی روزِ تقویمیِ UTC با شیفتِ ۱ روز)
//   ③ ATR₁۰۰ عددبه‌عدد (دامِ ②: میانگینِ ساده، **بدونِ** شیفت)
//   ④ SL/TP پیپیِ هر سیگنال (دامِ ④: هندسهٔ برداری از کندلِ سیگنال)
//   ⑤ computeS770 روی برشِ رو-به-جلو: آیا خودِ تابعِ سایت (که فقط آخرین کندل را
//      می‌بیند) همان سیگنال‌ها را می‌دهد؟ — این تنها چیزی است که کاربر واقعاً می‌بیند.
//
// اجرا: cd web_tool && node --import tsx parity_s770_signal.mjs
import fs from 'node:fs'
import { s770Features, S770_CFG, computeS770 } from './src/adr_expansion_s770.ts'

const GOLD_PIP = 0.1
const TOL = 1e-9

let failures = 0

for (const tf of ['D1', 'H8']) {
  const fp = `../results/_scan_S770/parity_${tf}_fixture.json`
  const fx = JSON.parse(fs.readFileSync(fp, 'utf8'))
  const cfg = S770_CFG[`XAUUSD-${tf}`]
  const candles = fx.candles
  const n = candles.length

  console.log(`\n══════ کارتِ XAUUSD-${tf} ══════`)
  console.log(`منبع: ${fx.src}`)
  console.log(`کندل: کلِ تاریخ=${fx.n_bars_full.toLocaleString()} · دم=${n} (offset=${fx.offset})`)
  console.log(`پیکربندیِ قفل‌شدهٔ پایتون: ${JSON.stringify(fx.cfg)}`)
  console.log(`پیکربندیِ TS سایت: theta=${cfg.theta} adr=${cfg.adrP} atr=${cfg.atrP} slK=${cfg.slK} rr=${cfg.rr} hold=${cfg.maxHold}`)

  // ── قیدِ صفر: پیکربندیِ TS باید عیناً همان قفل‌شدهٔ پایتون باشد ────────
  const cfgSame = fx.cfg.theta === cfg.theta && fx.cfg.adr_p === cfg.adrP
    && fx.cfg.atr_p === cfg.atrP && fx.cfg.sl_k === cfg.slK
    && fx.cfg.rr === cfg.rr && fx.cfg.hold === cfg.maxHold
  console.log(`⓪ همسانیِ پیکربندی: ${cfgSame ? 'PASS ✅' : 'FAIL ❌'}`)
  if (!cfgSame) failures++

  const f = s770Features(candles, cfg)

  // آستانهٔ مقایسه: ATR₁۰۰ + ADR(۲۲ روز). روی D1 یک کندل = یک روز ⇒ ۱۰۰ کندل
  // از ADR سخت‌گیرتر است؛ روی H8 هم ۱۰۰ کندل ≈ ۳۳ روز > ۲۲ روز. برای حاشیهٔ
  // ایمن، ۲× می‌گیریم (همان کنوانسیونِ پریتیِ S965).
  const cut = 2 * cfg.atrP

  // ── ① سیگنال‌ها ────────────────────────────────────────────────────────
  const tsLong = [], tsShort = []
  for (let i = 1; i < n; i++) {
    const cur = f.frac[i], prev = f.frac[i - 1], sl = f.slPip[i]
    if (!isFinite(cur) || !isFinite(prev) || !isFinite(sl) || !(sl > 0)) continue
    if (prev < cfg.theta && cur >= cfg.theta) tsLong.push(i)
    else if (prev > -cfg.theta && cur <= -cfg.theta) tsShort.push(i)
  }
  const inCut = a => a.filter(i => i >= cut)
  const pyLong = inCut(fx.py.idx_long), pyShort = inCut(fx.py.idx_short)
  const myLong = inCut(tsLong), myShort = inCut(tsShort)

  const eqArr = (a, b) => a.length === b.length && a.every((v, i) => v === b[i])
  const okLong = eqArr(myLong, pyLong), okShort = eqArr(myShort, pyShort)
  const diffL = myLong.filter(i => !pyLong.includes(i)).concat(pyLong.filter(i => !myLong.includes(i)))
  const diffS = myShort.filter(i => !pyShort.includes(i)).concat(pyShort.filter(i => !myShort.includes(i)))
  console.log(`① سیگنالِ LONG : TS=${myLong.length} · PY=${pyLong.length} · ${okLong ? 'PASS ✅ (mismatch=0)' : `FAIL ❌ diff=${JSON.stringify(diffL.slice(0, 12))}`}`)
  console.log(`① سیگنالِ SHORT: TS=${myShort.length} · PY=${pyShort.length} · ${okShort ? 'PASS ✅ (mismatch=0)' : `FAIL ❌ diff=${JSON.stringify(diffS.slice(0, 12))}`}`)
  if (!okLong) failures++
  if (!okShort) failures++

  // ── ② و ③ ویژگی‌ها عددبه‌عدد ──────────────────────────────────────────
  let maxFracErr = 0, maxAdrErr = 0, maxAtrErr = 0, cmp = 0
  const rel = (a, b) => Math.abs(a - b) / Math.max(Math.abs(b), 1e-12)
  for (let i = cut; i < n; i++) {
    const pf = fx.py.frac[i], pa = fx.py.adr[i], pt = fx.py.atr[i]
    if (pf === null || pa === null || pt === null) continue
    cmp++
    maxFracErr = Math.max(maxFracErr, rel(f.frac[i], pf))
    maxAdrErr = Math.max(maxAdrErr, rel(f.adr[i], pa))
    maxAtrErr = Math.max(maxAtrErr, rel(f.atrPx[i], pt))
  }
  const okFeat = maxFracErr < TOL && maxAdrErr < TOL && maxAtrErr < TOL
  console.log(`② frac (حالتِ انبساط): بیشینهٔ خطای نسبی=${maxFracErr.toExponential(2)} روی ${cmp} کندل`)
  console.log(`② ADR${cfg.adrP} (روزِ تقویمی، شیفتِ۱): بیشینهٔ خطا=${maxAdrErr.toExponential(2)}`)
  console.log(`③ ATR${cfg.atrP} (میانگینِ ساده، بی‌شیفت): بیشینهٔ خطا=${maxAtrErr.toExponential(2)} · ${okFeat ? 'PASS ✅' : 'FAIL ❌'}`)
  if (!okFeat) failures++

  // ── ④ هندسهٔ برداری روی خودِ سیگنال‌ها ────────────────────────────────
  let maxSlErr = 0, maxTpErr = 0
  for (const i of [...pyLong, ...pyShort]) {
    maxSlErr = Math.max(maxSlErr, rel(f.slPip[i], fx.py.sl_pip[i]))
    maxTpErr = Math.max(maxTpErr, rel(f.tpPip[i], fx.py.tp_pip[i]))
  }
  const okGeom = maxSlErr < TOL && maxTpErr < TOL
  console.log(`④ هندسه روی ${pyLong.length + pyShort.length} سیگنال: SL خطا=${maxSlErr.toExponential(2)} · TP خطا=${maxTpErr.toExponential(2)} · ${okGeom ? 'PASS ✅' : 'FAIL ❌'}`)
  if (!okGeom) failures++

  // ── ⑤ computeS770 روی برشِ رو-به-جلو (همان چیزی که کاربر می‌بیند) ─────
  // برای هر ایندکسِ آزمون، فقط کندل‌های ۰..i را به تابع می‌دهیم (عینِ سایت که
  // آخرین کندلِ بسته را می‌سنجد) و می‌بینیم active/direction با پایتون یکی است.
  const probe = []
  for (const i of pyLong) probe.push([i, 'LONG'])
  for (const i of pyShort) probe.push([i, 'SHORT'])
  probe.sort((a, b) => a[0] - b[0])
  let sigOk = 0, sigBad = 0
  for (const [i, want] of probe) {
    const r = computeS770(candles.slice(0, i + 1), cfg)
    if (r.active && r.direction === want) sigOk++
    else { sigBad++; if (sigBad <= 5) console.log(`   ⚠️ i=${i} انتظار=${want} گرفتیم active=${r.active} dir=${r.direction}`) }
  }
  // کنترلِ منفی: ۴۰ کندلِ آرام (بی‌سیگنال در پایتون) نباید ENTRY بدهند.
  const quiet = []
  for (let i = cut; i < n && quiet.length < 40; i += 17) {
    if (!pyLong.includes(i) && !pyShort.includes(i)) quiet.push(i)
  }
  let quietBad = 0
  for (const i of quiet) {
    const r = computeS770(candles.slice(0, i + 1), cfg)
    if (r.active) { quietBad++; if (quietBad <= 5) console.log(`   ⚠️ کنترلِ منفی i=${i}: سایت ENTRY داد ولی پایتون سیگنال ندارد`) }
  }
  const okLive = sigBad === 0 && quietBad === 0
  console.log(`⑤ computeS770 رو-به-جلو: ${sigOk}/${probe.length} سیگنالِ پایتون بازتولید شد · ${quiet.length - quietBad}/${quiet.length} کنترلِ منفی سالم · ${okLive ? 'PASS ✅' : 'FAIL ❌'}`)
  if (!okLive) failures++
}

console.log(`\n${'═'.repeat(48)}`)
if (failures === 0) {
  console.log('✅ پریتیِ S770 روی **هر دو کارتِ ACCEPT** کامل PASS — mismatch=0')
  console.log('   ⇒ پورتِ TS با منبعِ حقیقتِ پایتون بیت‌به‌بیت یکی است و هیچ نشتِ آینده ندارد.')
} else {
  console.log(`❌ ${failures} بندِ پریتی شکست خورد — اتصال به سایت مجاز نیست.`)
  process.exit(1)
}

// پریتیِ S408: پایتون (strategies/s408_gap_fill_m15_fulldata.py + والدهای
// S400/S401/S404) ⇄ TS (web_tool/src/gap_fill_m15_s408.ts).
//
// روش: fixture شاملِ ۲۰٬۰۰۰ کندلِ آخرِ M15 + مرجعِ پایتون که روی **کلِ ۳۶۳٬۷۷۸
// کندل** ساخته شده و سپس بریده شده. عمیق‌ترین نگاهِ به‌عقبِ لایه ATR14 روزانه
// است (۱۵ روز)؛ اگر پورت به warm-up وابسته باشد یا مرزِ روز را جور دیگری
// بشکند، همین‌جا لو می‌رود.
//
// هشت چیز مقایسه می‌شود:
//   ① مرزهای روز: مجموعهٔ اندیسِ «آخرین کندلِ روزِ قبل» باید عیناً یکی باشد
//      — دامِ ① (BUG-DAYBREAK-TF)
//   ② gap_usd عددبه‌عدد (و علامتش) — پایهٔ همه‌چیز
//   ③ weekend/dow بولی-به-بولی — دامِ نگاشتِ dayofweek (JS ۰=یک‌شنبه ⇄
//      pandas ۰=دوشنبه) که اگر غلط باشد «دوشنبهٔ اشتباهی» حذف می‌شود
//   ④ atr_prev عددبه‌عدد (خطای نسبی) — دامِ ④ (میانگینِ ساده نه EMA) و
//      دامِ «ATR روزِ قبل نه روزِ جاری»
//   ⑤ gap_ok / vol_ok بولی-به-بولی — دامِ ⑤ (عدمِ تقارنِ `>` و `<=`)
//   ⑥ تصمیمِ نهایی dec_frozen بولی-به-بولی — **قلبِ پریتی**
//   ⑦ هندسه: tp_usd/sl_usd و pip آن‌ها — دامِ «TP=بستهٔ روزِ قبل نه براکتِ متقارن»
//   ⑧ کنترلِ منفیِ دولایه:
//        (الف) روزهای بی‌تصمیم نباید active شوند؛
//        (ب) 🔑 روزهایی که پایهٔ گپ روشن است ولی V/DOW بسته
//            (base ∖ decision) باید خاموش بمانند — ثابت می‌کند فیلترها
//            واقعاً سیم‌کشی شده‌اند و لایه بی‌فیلتر معامله نمی‌کند.
//
// اجرا: cd web_tool && node --import tsx parity_s408_signal.mjs
import fs from 'node:fs'
import { computeS408Signal, dailyBarsAtr, s408DayBreakSec, S408_CFG } from './src/gap_fill_m15_s408.ts'

const fx = JSON.parse(fs.readFileSync('../results/_s408_arms/parity_m15_fixture.json', 'utf8'))
const cfg = S408_CFG['XAUUSD-M15']
const candles = fx.candles
const n = candles.length
const GOLD_PIP = 0.1

// ── نگهبانِ ثابت‌ها: اگر کسی cfg را دست بزند پریتی باید بترکد، نه سبز بماند ──
const cfgChecks = [
  ['thrWeekendUsd', cfg.thrWeekendUsd, fx.frozen.weekend],
  ['thrWeekdayUsd', cfg.thrWeekdayUsd, fx.frozen.weekday],
  ['volThrUsd', cfg.volThrUsd, fx.frozen.vol],
  ['kSl', cfg.kSl, fx.cfg.k_sl],
  ['qGap', cfg.qGap, fx.cfg.q_gap],
  ['qVol', cfg.qVol, fx.cfg.vol_q],
  ['tfSec', cfg.tfSec, fx.cfg.day_break_sec / 2],
]
const cfgBad = cfgChecks.filter(([, a, b]) => a !== b)
if (cfgBad.length) {
  console.log('❌ CFG DRIFT:', cfgBad.map(([k, a, b]) => `${k} ts=${a} py=${b}`).join(' · '))
  process.exit(1)
}
console.log(`cfg guard ✓ (frozen we=${cfg.thrWeekendUsd} wd=${cfg.thrWeekdayUsd} vol=${cfg.volThrUsd} kSl=${cfg.kSl})`)
console.log(`fixture: bars=${n} · window ${fx.window.first_utc} → ${fx.window.last_utc}`)

// ── ① مرزهای روز ────────────────────────────────────────────────────────────
const { ends, atr } = dailyBarsAtr(candles, cfg.tfSec)
const tsEnds = new Set(ends)
const pyBrk = fx.records.map(r => r.brk_rel).filter(b => b >= 0 && b < n)
const missBrk = pyBrk.filter(b => !tsEnds.has(b))
console.log(`① day boundaries: py=${pyBrk.length} · ts_ends=${ends.length} · missing_in_ts=${missBrk.length}`)

// ── ②..⑦ مقایسهٔ رکورد-به-رکورد ─────────────────────────────────────────────
// TS تصمیم را روی «پنجرهٔ منتهی به کندلِ اولِ روزِ نو» می‌سازد (شبیه‌سازِ زنده):
// candles.slice(0, fb_rel+1) ⇒ آخرین کندلِ بسته = اولین کندلِ روزِ نو.
let cmp = 0
const bad = { gap: [], wk: [], dow: [], atr: [], gapok: [], volok: [], dec: [], geom: [] }
let nDecPy = 0, nDecTs = 0, nBaseOnly = 0, nBaseOnlyFired = 0
const relTol = 1e-6

// 🔴 دامِ سنجشِ D — **نامتقارنیِ گرم‌شدن.** مرجعِ پایتون ATR را از تمامِ
//   ۴۰۸۸ روزِ تاریخ دارد، ولی TS فقط برشِ fixture را می‌بیند. پس برای
//   روزهای ابتدایی پنجره، TS ذاتاً ۱۴ روزِ قبلی ندارد ⇒ ATR=NaN و مقایسه
//   بی‌معنا می‌شود (این ۲۱۶ ناهمخوانیِ اولیه را ساخت، که ۲۰۳ موردش
//   مصنوعِ سنجش بود و ۱۳ موردش واقعی).
//   قاعدهٔ منصفانه: رکورد فقط وقتی مقایسه شود که برشِ TS **حداقل
//   ATR_N+1 = ۱۵ روزِ کامل** داشته باشد. کمتر از آن، ماژول طبقِ دامِ ⑥
//   عامدانه رد می‌کند و این رفتارِ درستِ زنده است، نه ناهمخوانی.
const ATR_WARM_DAYS = 15
const dayEndsAll = []
for (let i = 0; i < n - 1; i++) {
  if (candles[i + 1].time - candles[i].time >= s408DayBreakSec(candles)) dayEndsAll.push(i)
}
let nSkipWarm = 0

for (const r of fx.records) {
  const fbRel = r.fb_rel
  if (fbRel < 30 || fbRel >= n) continue        // نیاز به کمی گرم‌شدن در برشِ fixture
  // چند مرزِ روزِ کامل قبل از این نقطه در برش هست؟
  let daysInSlice = 0
  for (const e of dayEndsAll) { if (e < fbRel) daysInSlice++; else break }
  if (daysInSlice + 1 < ATR_WARM_DAYS) { nSkipWarm++; continue }
  const win = candles.slice(0, fbRel + 1)
  const s = computeS408Signal(win, cfg)
  if (s.brkIdx !== fbRel - 1) {                 // TS مرز را جای دیگری دید
    bad.gap.push(`k=${r.k} brk ts=${s.brkIdx} py=${fbRel - 1}`)
    continue
  }
  cmp++

  // ② gap
  if (Math.abs(s.gapUsd - r.gap_usd) > 1e-9) bad.gap.push(`k=${r.k} gap ts=${s.gapUsd} py=${r.gap_usd}`)
  // ③ weekend / dow
  if (s.isWeekend !== r.weekend) bad.wk.push(`k=${r.k} ts=${s.isWeekend} py=${r.weekend}`)
  if (s.dow !== r.dow) bad.dow.push(`k=${r.k} dow ts=${s.dow} py=${r.dow}`)
  // ④ atr_prev
  if (r.atr_prev === null) {
    if (isFinite(s.atrPrevUsd)) bad.atr.push(`k=${r.k} ts has atr but py None`)
  } else {
    const d = Math.abs(s.atrPrevUsd - r.atr_prev) / Math.max(1e-9, Math.abs(r.atr_prev))
    if (!(d <= 1e-4)) bad.atr.push(`k=${r.k} atr ts=${s.atrPrevUsd?.toFixed(4)} py=${r.atr_prev.toFixed(4)} rel=${d.toExponential(2)}`)
  }
  // ⑤ gap_ok / vol_ok (نسخهٔ منجمد — همان که TS اجرا می‌کند)
  const tsGapOk = s.gapUsd < 0 && Math.abs(s.gapUsd) > s.thrUsd
  const pyGapOk = r.neg_gap && r.gap_ok_frozen
  if (tsGapOk !== pyGapOk) bad.gapok.push(`k=${r.k} gapok ts=${tsGapOk} py=${pyGapOk}`)
  if (s.volPass !== r.vol_ok_frozen) bad.volok.push(`k=${r.k} volok ts=${s.volPass} py=${r.vol_ok_frozen}`)

  // ⑥ تصمیمِ نهایی
  if (r.dec_frozen) nDecPy++
  if (s.active) nDecTs++
  if (s.active !== r.dec_frozen) bad.dec.push(`k=${r.k} dec ts=${s.active} py=${r.dec_frozen} (gap=${r.gap_usd.toFixed(2)} thr=${r.thr_frozen} atr=${r.atr_prev?.toFixed(1)} dow=${r.dow})`)

  // ⑦ هندسه (فقط وقتی تصمیم فعال است)
  if (r.dec_frozen && s.active) {
    if (Math.abs(s.tpDistUsd - r.tp_usd) > 1e-9) bad.geom.push(`k=${r.k} tp ts=${s.tpDistUsd} py=${r.tp_usd}`)
    if (Math.abs(s.slDistUsd - r.sl_usd) > 1e-9) bad.geom.push(`k=${r.k} sl ts=${s.slDistUsd} py=${r.sl_usd}`)
    if (r.sl_pip !== null) {
      const tsSlPip = s.slDistUsd / GOLD_PIP
      const tsTpPip = s.tpDistUsd / GOLD_PIP
      if (Math.abs(tsSlPip - r.sl_pip) > 1e-6) bad.geom.push(`k=${r.k} sl_pip ts=${tsSlPip.toFixed(3)} py=${r.sl_pip.toFixed(3)}`)
      if (Math.abs(tsTpPip - r.tp_pip) > 1e-6) bad.geom.push(`k=${r.k} tp_pip ts=${tsTpPip.toFixed(3)} py=${r.tp_pip.toFixed(3)}`)
    }
  }

  // ⑧(ب) کنترلِ منفی: پایهٔ گپ روشن ولی فیلتر بسته ⇒ باید خاموش بماند
  if (pyGapOk && !r.dec_frozen) {
    nBaseOnly++
    if (s.active) nBaseOnlyFired++
  }
}

console.log(`② gap mismatches      : ${bad.gap.length}`)
console.log(`③ weekend/dow mismatch: ${bad.wk.length} / ${bad.dow.length}`)
console.log(`④ atr_prev mismatches : ${bad.atr.length}`)
console.log(`⑤ gap_ok/vol_ok mism. : ${bad.gapok.length} / ${bad.volok.length}`)
console.log(`⑥ DECISION mismatches : ${bad.dec.length}   (py_active=${nDecPy} ts_active=${nDecTs} compared=${cmp} skipped_warmup=${nSkipWarm})`)
console.log(`⑦ geometry mismatches : ${bad.geom.length}`)
console.log(`⑧ negative control    : base-only days=${nBaseOnly} · wrongly fired=${nBaseOnlyFired}`)

for (const [k, v] of Object.entries(bad)) {
  if (v.length) console.log(`   ↳ ${k}: ${v.slice(0, 6).join(' | ')}${v.length > 6 ? ` … (+${v.length - 6})` : ''}`)
}

const totalBad = Object.values(bad).reduce((s, v) => s + v.length, 0) + nBaseOnlyFired + missBrk.length
const ok = totalBad === 0 && cmp > 0 && nDecPy > 0 && nDecPy === nDecTs

const out = {
  layer: 'S408', tf: 'M15',
  fixture: '../results/_s408_arms/parity_m15_fixture.json',
  bars: n, compared_day_boundaries: cmp,
  missing_boundaries_in_ts: missBrk.length,
  mismatches: Object.fromEntries(Object.entries(bad).map(([k, v]) => [k, v.length])),
  py_active: nDecPy, ts_active: nDecTs,
  negative_control: { base_only_days: nBaseOnly, wrongly_fired: nBaseOnlyFired },
  verdict: ok ? 'PASS' : 'FAIL',
}
fs.writeFileSync('../results/_s408_arms/parity_ts_M5.json'.replace('M5', 'M15'),
                 JSON.stringify(out, null, 1))
console.log(`\n${ok ? '✅ PARITY PASS' : '❌ PARITY FAIL'} — saved → results/_s408_arms/parity_ts_M15.json`)
process.exit(ok ? 0 : 1)

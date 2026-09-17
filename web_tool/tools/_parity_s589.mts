// ---------------------------------------------------------------------------
// آزمونِ برابریِ S589 — پورتِ TS در برابرِ مرجعِ **پایتون** روی دادهٔ کاملِ MT5.
//
// مرجع: results/_s589_parity/<CARD>.json (ساختهٔ tools/export_s589_parity.py که
//   خودش ماشینِ منجمدِ حکمِ ACCEPT 88.3/86.3 را بازتولید می‌کند و گیتِ سلامتش
//   ۱۰/۱۰ سنجهٔ حکم را عیناً درآورد).
//
// چه چیزی سنجیده می‌شود:
//   ① سری‌های علّی روی **همهٔ** کندل‌های دنبالهٔ صادرشده: rvol هم‌اسلات،
//      لبهٔ تازه (fresh)، و پرچمِ نهایی (gated)
//   ② مجموعهٔ **کاملِ** سیگنال‌ها روی کلِ ۱۵.۶ سال (بیت‌به‌بیت، نه نمونه‌ای)
//   ③ هندسهٔ منجمدِ هر کارت: S589_CFG باید عیناً همان SL/TP مرجع را داشته باشد
//   ④ **شاهدِ منفیِ H12**: مرجع وجود دارد (REJECT 25.1) ولی S589_CFG **نباید**
//      این کارت را داشته باشد — ضدِ تعمیمِ ممنوعِ MTF
//   ⑤ **کنترلِ منفیِ گیتِ حجم**: اگر گیت را برداریم باید سیگنال‌ها بیشتر شوند و
//      تعدادشان با n_edges مرجع بخواند. این ثابت می‌کند گیت **واقعاً کار می‌کند**
//      و به‌طورِ تصادفی همیشه-true نیست (اگر گیت بی‌اثر بود، پورت هم سبز
//      می‌شد و هم بی‌معنا).
//
// 🔴 تلهٔ اصلیِ این آزمون: سری‌ها باید روی **کلِ تاریخ** محاسبه و بعد روی دنباله
//    مقایسه شوند. rvol هم‌اسلات به تاریخِ کندل‌های **همان ساعتِ روز** وابسته است
//    و سقفِ غلتانِ ۹۰ هم بازگشتی است؛ بریدنِ داده از ابتدا هر دو را عوض می‌کند.
//
// ⚠️ کارتِ H4 از **فایلِ دورانِ حکم** خوانده می‌شود، نه از mt5_full — چون
//    data/XAUUSD_H4.csv بالادست حذف شده (کامیت a8cd44cc) و mt5_full نسخهٔ
//    بعدی است. مرجع خودش این را در فیلدِ data_src ثبت کرده و این آزمون
//    همان منبع را بازیابی می‌کند (جزئیات در هدرِ صادرکننده).
//
// اجرا: npx tsx tools/_parity_s589.mts            (هر سه کارت + شاهدِ منفی)
//       npx tsx tools/_parity_s589.mts XAUUSD_H8  (یک کارت)
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import zlib from 'node:zlib'
import { execFileSync } from 'node:child_process'
import { S589_CFG, s589Features, type S589Config } from '../src/volume_fresh_high_s589.js'
import type { Candle } from '../src/indicators.js'

const ROOT = new URL('../../', import.meta.url).pathname
const TOL_RVOL = 1e-6       // مرجع با ۶ رقمِ اعشار گرد شده
const TOL_PIP = 1e-9

// همان ثابت‌های مرجع — برای کارت‌هایی که در S589_CFG نیستند (شاهدِ منفی)
const FROZEN_H12: S589Config = {
  id: 'XAUUSD-H12', tfFa: 'H12',
  lookback: 90, rvolThr: 1.0, slotWin: 30, slotMinP: 20, atrP: 100,
  slK: 1.5, rr: 1.5, slPip: 228.09, tpPip: 342.14,
  maxHold: 96, approachFrac: 0.995, rqs2: 25.1,
}

type Ref = {
  card: string
  bars: number
  data_src: string
  span_years: number
  frozen: {
    lookback: number; rvol_thr: number; slot_win: number; slot_minp: number
    atr_p: number; sl_k: number; rr: number; sl_pip: number; tp_pip: number
    entry: string; max_hold: number | null; side: string
  }
  counts: {
    n_edges: number; n_signals: number; n_trades: number
    wr: number; gate_pass_rate: number
  }
  signal_bars: number[]
  trades: { entry_bar: number; exit_bar: number; outcome: string; pnl_pip: number }[]
  tail_series: {
    from_bar: number
    time: number[]; close: number[]; volume: number[]
    rvol_slot: (number | null)[]
    fresh_edge: boolean[]
    gated: boolean[]
  }
}

function loadCandles(card: string, ref: Ref): Candle[] {
  let text: string
  if (ref.data_src.startsWith('git:')) {
    // فایلِ دورانِ حکم از تاریخِ گیت (کارتِ H4 — بالا را ببینید)
    const blob = ref.data_src.slice(4)
    text = execFileSync('git', ['show', blob], { cwd: ROOT, maxBuffer: 1 << 28 }).toString()
  } else {
    const gz = fs.readFileSync(`${ROOT}data/mt5_full/${card}.csv.gz`)
    text = zlib.gunzipSync(gz).toString()
  }
  const lines = text.trim().split('\n')
  const out: Candle[] = []
  for (let i = 1; i < lines.length; i++) {
    const p = lines[i].trim().split(',')
    if (p.length < 6) continue
    out.push({
      time: Number(p[0]), open: Number(p[1]), high: Number(p[2]),
      low: Number(p[3]), close: Number(p[4]), volume: Number(p[5]),
    })
  }
  return out
}

let failures = 0
const fail = (m: string) => { failures++; console.log(`   ❌ ${m}`) }
const ok = (m: string) => console.log(`   ✅ ${m}`)

function checkCard(card: string): void {
  const refPath = `${ROOT}results/_s589_parity/${card}.json`
  if (!fs.existsSync(refPath)) { fail(`${card}: مرجع پیدا نشد — اول export_s589_parity.py را اجرا کن`); return }
  const ref: Ref = JSON.parse(fs.readFileSync(refPath, 'utf8'))

  const cfgKey = card.replace('_', '-')
  const isOfficial = cfgKey in S589_CFG
  const cfg = isOfficial ? S589_CFG[cfgKey] : FROZEN_H12

  console.log(`\n── ${card} ${isOfficial ? '(کارتِ رسمیِ ACCEPT)' : '(شاهدِ منفی — REJECT، نباید در CFG باشد)'}`)

  const candles = loadCandles(card, ref)
  if (candles.length !== ref.bars) {
    fail(`تعدادِ کندل: ts=${candles.length} py=${ref.bars} — منبعِ داده هم‌تراز نیست (${ref.data_src})`)
    return
  }
  ok(`دادهٔ هم‌تراز: ${candles.length} کندل · span ${ref.span_years}y · منبع ${ref.data_src}`)

  // ── ③ هندسهٔ منجمد ────────────────────────────────────────────────────────
  if (Math.abs(cfg.slPip - ref.frozen.sl_pip) > TOL_PIP ||
      Math.abs(cfg.tpPip - ref.frozen.tp_pip) > TOL_PIP) {
    fail(`هندسه: ts SL/TP=${cfg.slPip}/${cfg.tpPip} py=${ref.frozen.sl_pip}/${ref.frozen.tp_pip}`)
  } else {
    ok(`هندسهٔ منجمد برابر: SL=${cfg.slPip} TP=${cfg.tpPip} pip (RR ${cfg.rr})`)
  }
  for (const [k, tsv, pyv] of [
    ['lookback', cfg.lookback, ref.frozen.lookback],
    ['rvolThr', cfg.rvolThr, ref.frozen.rvol_thr],
    ['slotWin', cfg.slotWin, ref.frozen.slot_win],
    ['slotMinP', cfg.slotMinP, ref.frozen.slot_minp],
    ['atrP', cfg.atrP, ref.frozen.atr_p],
  ] as [string, number, number][]) {
    if (tsv !== pyv) fail(`پارامترِ ${k}: ts=${tsv} py=${pyv}`)
  }

  // ── سری‌ها روی کلِ تاریخ (تلهٔ اصلی) ─────────────────────────────────────
  const f = s589Features(candles, cfg)

  // ── ② مجموعهٔ کاملِ سیگنال‌ها ─────────────────────────────────────────────
  const tsSignals: number[] = []
  for (let i = 0; i < candles.length; i++) if (f.gated[i]) tsSignals.push(i)
  if (tsSignals.length !== ref.signal_bars.length) {
    fail(`تعدادِ سیگنال: ts=${tsSignals.length} py=${ref.signal_bars.length}`)
  } else {
    let mism = 0
    for (let k = 0; k < tsSignals.length; k++) {
      if (tsSignals[k] !== ref.signal_bars[k]) mism++
    }
    if (mism) fail(`ایندکسِ سیگنال: ${mism} ناهمخوانی از ${tsSignals.length}`)
    else ok(`مجموعهٔ سیگنال بیت‌به‌بیت برابر: ${tsSignals.length} سیگنال روی کلِ ${ref.span_years} سال`)
  }

  // ── ① سری‌های علّی روی دنبالهٔ صادرشده ───────────────────────────────────
  const t = ref.tail_series
  let badR = 0, badF = 0, badG = 0, maxDR = 0
  for (let k = 0; k < t.rvol_slot.length; k++) {
    const i = t.from_bar + k
    const pyR = t.rvol_slot[k]
    const tsR = f.rvol[i]
    const tsFinite = isFinite(tsR)
    if (pyR === null) { if (tsFinite) badR++ }
    else if (!tsFinite) badR++
    else {
      const d = Math.abs(tsR - pyR)
      if (d > maxDR) maxDR = d
      if (d > TOL_RVOL) badR++
    }
    if (f.fresh[i] !== t.fresh_edge[k]) badF++
    if (f.gated[i] !== t.gated[k]) badG++
  }
  if (badR) fail(`rvol هم‌اسلات: ${badR} ناهمخوانی از ${t.rvol_slot.length} (max|Δ|=${maxDR.toExponential(2)})`)
  else ok(`rvol هم‌اسلات برابر روی ${t.rvol_slot.length} کندل (max|Δ|=${maxDR.toExponential(2)})`)
  if (badF) fail(`لبهٔ تازه: ${badF} ناهمخوانی`); else ok('لبهٔ تازه (رویداد، نه حالت) برابر')
  if (badG) fail(`پرچمِ gated: ${badG} ناهمخوانی`); else ok('پرچمِ نهاییِ gated برابر')

  // ── ⑤ کنترلِ منفیِ گیتِ حجم ───────────────────────────────────────────────
  // اگر گیت را برداریم باید به n_edges مرجع برسیم. این نشان می‌دهد گیت
  // واقعاً غربال می‌کند و پورت به‌طور تصادفی همیشه-true نیست.
  let edges = 0
  for (let i = 0; i < candles.length; i++) if (f.fresh[i]) edges++
  if (edges !== ref.counts.n_edges) {
    fail(`کنترلِ منفی — رویدادِ بی‌گیت: ts=${edges} py=${ref.counts.n_edges}`)
  } else {
    const passRate = (100 * tsSignals.length / edges)
    ok(`کنترلِ منفی: ${edges} رویدادِ خام ⇒ ${tsSignals.length} با تأییدِ حجم ` +
       `(نرخِ عبور ${passRate.toFixed(1)}٪ ≈ py ${ref.counts.gate_pass_rate}٪) ` +
       `⇒ گیت **زنده** است، نه همیشه-true`)
    if (Math.abs(passRate - ref.counts.gate_pass_rate) > 0.15) {
      fail(`نرخِ عبور واگرا: ts=${passRate.toFixed(1)} py=${ref.counts.gate_pass_rate}`)
    }
    // قانونِ S529: نرخِ عبورِ >۷۵٪ = گیتِ مرده. برای کارت‌های ACCEPT باید زیر باشد.
    if (isOfficial && passRate > 75.0) {
      fail(`قانونِ S529: نرخِ عبور ${passRate.toFixed(1)}٪ > ۷۵٪ روی یک کارتِ ACCEPT`)
    }
  }
}

// ── ④ شاهدِ منفیِ MTF ───────────────────────────────────────────────────────
function checkMtfNegative(): void {
  console.log('\n── شاهدِ منفیِ MTF (قانون: فقط کارت‌های ACCEPT وصل می‌شوند)')
  const keys = Object.keys(S589_CFG).sort()
  const want = ['XAUUSD-H4', 'XAUUSD-H8']
  if (JSON.stringify(keys) !== JSON.stringify(want)) {
    fail(`S589_CFG باید دقیقاً ${want.join(' و ')} باشد — یافت: ${keys.join(', ')}`)
  } else {
    ok(`S589_CFG دقیقاً دو کارتِ ACCEPT را دارد: ${keys.join(' · ')}`)
  }
  if ('XAUUSD-H12' in S589_CFG) {
    fail('XAUUSD-H12 در S589_CFG است ولی حکمش REJECT 25.1 است (تعمیمِ ممنوع)')
  } else {
    ok('XAUUSD-H12 (REJECT 25.1) در CFG **نیست** — و مرجعش اجراشدنی مانده تا ثابت شود تصمیمِ حکمی بود، نه سکوتِ پورت')
  }
}

const only = process.argv[2]
const cards = only ? [only] : ['XAUUSD_H8', 'XAUUSD_H4', 'XAUUSD_H12']
console.log('═══ آزمونِ برابریِ S589 (TS ↔ پایتون) — سقفِ تازهٔ ۹۰ × تأییدِ حجمِ هم‌اسلات ═══')
for (const c of cards) checkCard(c)
if (!only) checkMtfNegative()

console.log(`\n${failures === 0 ? '✅ GREEN — همهٔ چک‌ها پاس' : `❌ RED — ${failures} چکِ ناموفق`}`)
process.exit(failures === 0 ? 0 : 1)

// ---------------------------------------------------------------------------
// آزمونِ برابریِ S572 — پورتِ TS در برابرِ مرجعِ **پایتون** روی XAUUSD-M30 و H1.
//
// مرجع: results/_s572_parity/XAUUSD_{M30,H1}.json (ساختهٔ tools/export_s572_parity.py
//   که ماشینِ منجمدِ S323 را عیناً اجرا می‌کند؛ گاردِ سلامت: ۱۵۶ و ۳۷ معاملهٔ
//   پس از FIFO بازتولید شد).
//
// چه چیزی سنجیده می‌شود:
//   ① مجموعهٔ **کاملِ** سیگنال‌ها روی کلِ ۱۵.۶ سال — بیت‌به‌بیت (زمان/اندیس)، نه
//      فقط تعداد (پورت می‌تواند ۳۰۴ رویداد بدهد ولی بعضی را جابه‌جا بگذارد).
//   ② سری‌های تفکیکیِ دنبالهٔ ۴۰۰ کندلِ آخر: support · resistance · atr14 ·
//      ema50 · ema200 · rsi14 · adx14 · slope · sig. اگر فرق کنند، می‌گوید کدام
//      جزءِ قاعده مقصر است.
//   ③ هندسهٔ منجمدِ آینه‌ای: SL/TP و maxHold باید عیناً مرجع باشند.
//   ④ شاهدِ منفی: فقط دو کارتِ ACCEPT (M30,H1) در S572_CFG باشند.
//   ⑤ کنترلِ منفیِ گیتِ طلایی: با خاموش‌کردنِ پنجرهٔ طلایی سیگنال‌ها **بیشتر**
//      می‌شوند (اگر نه، یعنی گیت در پورت بی‌اثر است).
//
// اجرا: npx tsx tools/_parity_s572.mts
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import zlib from 'node:zlib'
import { S572_CFG, s572Features } from '../src/sr_pullback_mirror_s572.js'
import type { Candle } from '../src/indicators.js'

const ROOT = new URL('../../', import.meta.url).pathname
const TOL = 1e-4

type Tail = {
  from_index: number
  support: (number | null)[]
  resistance: (number | null)[]
  atr14: (number | null)[]
  ema50: (number | null)[]
  ema200: (number | null)[]
  rsi14: (number | null)[]
  adx14: (number | null)[]
  slope: (number | null)[]
  close: (number | null)[]
  sig: number[]
}
type Ref = {
  card: string; bars: number
  frozen: Record<string, number | string | boolean>
  counts: { n_signals: number; n_trades: number }
  signal_bars: number[]
  trade_entry_bars: number[]
  tail: Tail
  health_ok: boolean
}

function readRef(card: string): Ref {
  const p = `${ROOT}results/_s572_parity/${card.replace('-', '_')}.json`
  if (!fs.existsSync(p)) throw new Error(`مرجع نیست: ${p} — اول tools/export_s572_parity.py را اجرا کن`)
  return JSON.parse(fs.readFileSync(p, 'utf8'))
}

function loadCsv(tf: string): Candle[] {
  const gz = `${ROOT}data/mt5_full/XAUUSD_${tf}.csv.gz`
  const text = zlib.gunzipSync(fs.readFileSync(gz)).toString('utf8')
  const lines = text.trim().split('\n').map(l => l.replace(/\r$/, ''))
  const head = lines[0].split(',').map(s => s.trim())
  const ix = (n: string) => head.indexOf(n)
  const iT = ix('time'), iO = ix('open'), iH = ix('high'), iL = ix('low'), iC = ix('close')
  const iV = ix('volume') >= 0 ? ix('volume') : ix('tick_volume')
  const out: Candle[] = []
  for (let i = 1; i < lines.length; i++) {
    const t = lines[i].split(',')
    if (t.length < 5) continue
    out.push({ time: Number(t[iT]), open: Number(t[iO]), high: Number(t[iH]),
      low: Number(t[iL]), close: Number(t[iC]), volume: iV >= 0 ? Number(t[iV]) : 0 })
  }
  return out
}

let failures = 0
const checks: { ok: boolean; label: string; detail: string }[] = []
function check(ok: boolean, label: string, detail = ''): void {
  checks.push({ ok, label, detail })
  if (ok) console.log(`  ✅ ${label}`)
  else { failures++; console.log(`  ❌ ${label}${detail ? ` — ${detail}` : ''}`) }
}
const numEq = (a: number, b: number | null, tol = TOL) =>
  b === null ? !Number.isFinite(a) : (Number.isFinite(a) && Math.abs(a - b) < tol)

function runCard(card: string): void {
  console.log(`\n══════ ${card} ══════`)
  const ref = readRef(card)
  const cfg = S572_CFG[card]
  check(ref.health_ok, 'مرجع خودش گاردِ سلامت را پاس کرده (۱۵۶/۳۷ معاملهٔ FIFO بازتولید شد)')
  if (!cfg) { check(false, 'کارت در S572_CFG هست'); return }

  const tf = card.split('-')[1]
  const candles = loadCsv(tf)
  check(candles.length === ref.bars, 'تعدادِ کندل با مرجع یکی است', `TS=${candles.length} ref=${ref.bars}`)

  const F = ref.frozen
  check(cfg.nearMax === F.nearMax, `nearMax = ${F.nearMax}`, `cfg=${cfg.nearMax}`)
  check(cfg.roomMin === F.roomMin, `roomMin = ${F.roomMin}`, `cfg=${cfg.roomMin}`)
  check(cfg.rsiMax === F.rsiMax, `rsiMax = ${F.rsiMax}`, `cfg=${cfg.rsiMax}`)
  check(cfg.adxMin === F.adxMin, `adxMin = ${F.adxMin}`, `cfg=${cfg.adxMin}`)
  check(cfg.hLo === F.hLo && cfg.hHi === F.hHi, `پنجرهٔ طلایی ${F.hLo}–${F.hHi}`, `cfg=${cfg.hLo}–${cfg.hHi}`)
  check(cfg.pivotLeft === 6 && cfg.pivotRight === 6, 'پیوتِ ۶/۶', `cfg=${cfg.pivotLeft}/${cfg.pivotRight}`)
  check(cfg.srTol === F.srTol || Math.abs(cfg.srTol - 0.0015) < 1e-9, 'tolِ S/R = 0.0015')
  check(Math.abs(cfg.slPip - Number(F.mirror_sl_pip)) < 0.01, `SL = ${F.mirror_sl_pip} pip`, `cfg=${cfg.slPip}`)
  check(Math.abs(cfg.tpPip - Number(F.mirror_tp_pip)) < 0.01, `TP = ${F.mirror_tp_pip} pip`, `cfg=${cfg.tpPip}`)
  check(cfg.maxHold === F.maxHold, `maxHold = ${F.maxHold}`, `cfg=${cfg.maxHold}`)
  check(cfg.tpPip >= cfg.slPip, 'هندسهٔ آینه‌ای TP≥SL')

  const f = s572Features(candles, cfg)

  // ① مجموعهٔ کاملِ سیگنال‌ها — اندیس‌به‌اندیس
  const tsBars: number[] = []
  for (let i = 0; i < candles.length; i++) if (f.sig[i]) tsBars.push(i)
  check(tsBars.length === ref.counts.n_signals,
    `تعدادِ سیگنال = ${ref.counts.n_signals}`, `TS=${tsBars.length}`)
  const refSet = new Set(ref.signal_bars)
  const tsSet = new Set(tsBars)
  const onlyTs = tsBars.filter(b => !refSet.has(b))
  const onlyRef = ref.signal_bars.filter(b => !tsSet.has(b))
  check(onlyTs.length === 0 && onlyRef.length === 0,
    'مجموعهٔ سیگنال‌ها بیت‌به‌بیت برابرِ مرجع است',
    `فقط در TS=${onlyTs.length} · فقط در مرجع=${onlyRef.length}`)

  // ② سری‌های تفکیکیِ دنباله
  const t = ref.tail
  const off = t.from_index
  const diffs: Record<string, number> = { support: 0, resistance: 0, atr14: 0, ema50: 0, ema200: 0, rsi14: 0, adx14: 0, slope: 0, sig: 0 }
  for (let k = 0; k < t.sig.length; k++) {
    const i = off + k
    if (!numEq(f.support[i], t.support[k])) diffs.support++
    if (!numEq(f.resistance[i], t.resistance[k])) diffs.resistance++
    if (!numEq(f.atr14[i], t.atr14[k])) diffs.atr14++
    if (!numEq(f.ema50[i], t.ema50[k])) diffs.ema50++
    if (!numEq(f.ema200[i], t.ema200[k])) diffs.ema200++
    if (!numEq(f.rsi14[i], t.rsi14[k])) diffs.rsi14++
    const adxT = Number.isFinite(f.adx14[i]) ? f.adx14[i] : 0
    if (!numEq(adxT, t.adx14[k])) diffs.adx14++
    const slT = Number.isFinite(f.slope[i]) ? f.slope[i] : 0
    if (!numEq(slT, t.slope[k])) diffs.slope++
    if ((f.sig[i] ? 1 : 0) !== t.sig[k]) diffs.sig++
  }
  for (const key of Object.keys(diffs)) {
    check(diffs[key] === 0, `سریِ «${key}» روی دنباله برابر است`, `${diffs[key]} اختلاف`)
  }

  // ⑤ کنترلِ منفیِ گیتِ طلایی
  const noGolden = s572Features(candles, { ...cfg, golden: false })
  let nNoGold = 0
  for (let i = 0; i < candles.length; i++) if (noGolden.sig[i]) nNoGold++
  check(nNoGold > tsBars.length,
    `کنترلِ منفی: بدونِ پنجرهٔ طلایی سیگنال‌ها بیشتر می‌شوند (${nNoGold} > ${tsBars.length})`,
    'گیتِ طلایی در پورت بی‌اثر است')
}

function main(): void {
  console.log('آزمونِ برابریِ S572 — پورتِ TS در برابرِ مرجعِ پایتون')
  runCard('XAUUSD-M30')
  runCard('XAUUSD-H1')

  console.log('\n═══ شاهدِ منفی: فقط دو کارتِ ACCEPT ═══')
  const ids = Object.keys(S572_CFG).sort()
  check(ids.length === 2 && ids[0] === 'XAUUSD-H1' && ids[1] === 'XAUUSD-M30',
    'دقیقاً دو کارت (H1,M30) پیکربندی شده‌اند', ids.join(', '))

  const res = { layer: 'S572', status: failures === 0 ? 'GREEN' : 'RED', fails: failures, total: checks.length, checks }
  const outPath = `${ROOT}results/_s572_parity/parity_result.json`
  fs.mkdirSync(`${ROOT}results/_s572_parity`, { recursive: true })
  fs.writeFileSync(outPath, JSON.stringify(res, null, 1))
  console.log(`\nذخیره شد -> ${outPath}`)
  console.log(failures === 0
    ? `\n✅ همهٔ آزمون‌ها سبز (${checks.length - failures}/${checks.length}) — پورت با مرجع برابر است`
    : `\n❌ ${failures} آزمون شکست خورد`)
  if (failures) process.exit(1)
}

main()

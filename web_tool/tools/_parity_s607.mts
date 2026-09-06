// ---------------------------------------------------------------------------
// آزمونِ برابریِ S607 — پورتِ TS در برابرِ مرجعِ **پایتون** روی دادهٔ کاملِ MT5.
//
// مرجع: results/_s607_parity/<TF>.json (ساختهٔ tools/export_s607_parity.py که
//   خودش ماشینِ منجمدِ حکمِ ACCEPT 83.1 را وارد می‌کند و نه فرمولِ بازنویسی‌شده).
//
// چه چیزی سنجیده می‌شود (۴ چک روی هر کارت):
//   ① سری‌های علّی: z · sigma · atr روی **همهٔ** کندل‌های دنبالهٔ صادرشده
//   ② مجموعهٔ سیگنال‌های dual: ایندکس + جهت + SL/TP (بیت‌به‌بیت)
//   ③ خودِ گیت‌ها به‌تفکیک (drift و calm) روی هر کندلِ سیگنالِ خام
//   ④ شاهدِ منفیِ H12: مرجع باید official_member=false باشد و S607_CFG
//      **نباید** این کارت را داشته باشد (ضدِ تعمیمِ ممنوعِ MTF)
//
// نکتهٔ روش‌شناسی: سری‌ها روی **کلِ تاریخ** محاسبه می‌شوند (عیناً مثلِ پایتون)
//   و بعد فقط روی دنبالهٔ صادرشده مقایسه می‌شوند — چون z و σ بازگشتی‌اند و
//   بریدنِ داده از ابتدا مقدارشان را عوض می‌کند. این تلهٔ اصلیِ این آزمون است.
//
// اجرا: npx tsx tools/_parity_s607.mts            (هر سه کارت + شاهدِ منفی)
//       npx tsx tools/_parity_s607.mts H8         (یک کارت)
// ---------------------------------------------------------------------------
import fs from 'node:fs'
import zlib from 'node:zlib'
import {
  S607_CFG, ewmaZ, atrWilder, regimeRatio, type S607Config,
} from '../src/engle_dual_gate_s607.js'

const GOLD_PIP = 0.1
const TOL_Z = 1e-8          // مرجع با ۸ رقمِ اعشار گرد شده
const TOL_ATR = 1e-6        // ۶ رقم
const TOL_SIG = 1e-10       // ۱۰ رقم
const TOL_PIP = 1e-6

type Ref = {
  tf: string; card: string; official_member: boolean
  params: { z_thr: number; mode: string; sl_k: number; rr: number; hold: number; warmup: number; atr_p: number; lam: number }
  gate: { K_days: number; K_bars: number; W: number; bars_per_day: number } | null
  member_stats: { n: number; wr: number; lift: number } | null
  n_bars_total: number; tail_from: number; tail_len: number
  series: { bar: number; z: number | null; atr: number | null; sigma: number | null }[]
  signals: { bar: number; time: number; dir: string; z: number; atr: number; sigma: number; reg: number | null; sl_pip: number; tp_pip: number }[]
}

function loadCandles(tf: string) {
  const gz = `../data/mt5_full/XAUUSD_${tf}.csv.gz`
  const plain = `../data/mt5_full/XAUUSD_${tf}.csv`
  const csv = fs.existsSync(gz)
    ? zlib.gunzipSync(fs.readFileSync(gz)).toString()
    : fs.readFileSync(plain).toString()
  const lines = csv.trim().split('\n')
  lines.shift()
  return lines.map((l) => {
    const p = l.split(',')
    return { time: +p[0], open: +p[1], high: +p[2], low: +p[3], close: +p[4], volume: +p[5] }
  })
}

let failures = 0
function check(cond: boolean, msg: string) {
  if (!cond) { failures++; console.log(`   ✗ ${msg}`) }
}

function runCard(tf: string) {
  const refPath = `../results/_s607_parity/${tf}.json`
  const ref: Ref = JSON.parse(fs.readFileSync(refPath, 'utf8'))
  const cfg: S607Config | undefined = S607_CFG[ref.card]

  console.log(`\n── ${ref.card} ${ref.official_member ? '(عضوِ رسمی)' : '(شاهدِ منفی)'} ──`)

  // ④ شاهدِ منفی: کارتِ غیررسمی نباید در پیکربندیِ سایت باشد
  if (!ref.official_member) {
    check(cfg === undefined,
      `کارتِ ${ref.card} عضوِ رسمیِ استخر نیست ولی در S607_CFG وجود دارد — تعمیمِ ممنوعِ MTF!`)
    if (cfg === undefined) {
      console.log(`   ✓ شاهدِ منفی درست: ${ref.card} در S607_CFG **نیست** ` +
        `(انتخاب‌گرِ رسمی حذفش کرد؛ n_dual مرجع=${ref.signals.length} در دنباله)`)
    }
    return
  }
  if (cfg === undefined) {
    failures++
    console.log(`   ✗ کارتِ رسمیِ ${ref.card} در S607_CFG غایب است!`)
    return
  }

  // پارامترهای منجمد باید عیناً بخوانند
  check(cfg.zThr === ref.params.z_thr, `z_thr: TS=${cfg.zThr} py=${ref.params.z_thr}`)
  check(cfg.slK === ref.params.sl_k, `sl_k: TS=${cfg.slK} py=${ref.params.sl_k}`)
  check(cfg.rr === ref.params.rr, `rr: TS=${cfg.rr} py=${ref.params.rr}`)
  check(cfg.maxHold === ref.params.hold, `hold: TS=${cfg.maxHold} py=${ref.params.hold}`)
  check(cfg.warm === ref.params.warmup, `warmup: TS=${cfg.warm} py=${ref.params.warmup}`)
  check(cfg.atrP === ref.params.atr_p, `atr_p: TS=${cfg.atrP} py=${ref.params.atr_p}`)
  check(cfg.lam === ref.params.lam, `lam: TS=${cfg.lam} py=${ref.params.lam}`)
  check(ref.params.mode === 'follow', `mode باید follow باشد: ${ref.params.mode}`)
  if (ref.gate) {
    check(cfg.driftK === ref.gate.K_bars, `K_bars: TS=${cfg.driftK} py=${ref.gate.K_bars}`)
    check(cfg.sigmaW === ref.gate.W, `W: TS=${cfg.sigmaW} py=${ref.gate.W}`)
    check(cfg.barsPerDay === ref.gate.bars_per_day,
      `bars_per_day: TS=${cfg.barsPerDay} py=${ref.gate.bars_per_day}`)
  } else {
    check(cfg.driftK === null && cfg.sigmaW === null,
      `کارتِ خام نباید گیت داشته باشد: driftK=${cfg.driftK} sigmaW=${cfg.sigmaW}`)
  }

  // سری‌ها روی کلِ تاریخ (نه دنبالهٔ بریده) — تلهٔ اصلیِ آزمون
  const candles = loadCandles(tf)
  check(candles.length === ref.n_bars_total,
    `تعدادِ کندل: TS=${candles.length} py=${ref.n_bars_total}`)

  const close = candles.map((c) => c.close)
  const { z, sigma } = ewmaZ(close, cfg.lam)
  const atr = atrWilder(candles as any, cfg.atrP)
  const reg = cfg.sigmaW == null ? null : regimeRatio(sigma, cfg.sigmaW)

  // ① برابریِ سری‌ها
  let dz = 0, datr = 0, dsig = 0, nCmp = 0
  for (const s of ref.series) {
    const i = s.bar
    if (s.z != null) { dz = Math.max(dz, Math.abs(z[i] - s.z)); nCmp++ }
    else check(!Number.isFinite(z[i]), `z[${i}] باید NaN باشد ولی TS=${z[i]}`)
    if (s.atr != null) datr = Math.max(datr, Math.abs(atr[i] - s.atr))
    else check(!Number.isFinite(atr[i]), `atr[${i}] باید NaN باشد ولی TS=${atr[i]}`)
    if (s.sigma != null) dsig = Math.max(dsig, Math.abs(sigma[i] - s.sigma))
    else check(!Number.isFinite(sigma[i]), `sigma[${i}] باید NaN باشد ولی TS=${sigma[i]}`)
  }
  check(dz <= TOL_Z, `max|Δz|=${dz.toExponential(3)} > ${TOL_Z}`)
  check(datr <= TOL_ATR, `max|Δatr|=${datr.toExponential(3)} > ${TOL_ATR}`)
  check(dsig <= TOL_SIG, `max|Δsigma|=${dsig.toExponential(3)} > ${TOL_SIG}`)
  console.log(`   سری‌ها روی ${nCmp} کندل: max|Δz|=${dz.toExponential(2)} · ` +
    `max|Δatr|=${datr.toExponential(2)} · max|Δσ|=${dsig.toExponential(2)}`)

  // ②/③ بازتولیدِ سیگنال‌های dual با همان منطقِ لایه
  const lo = ref.tail_from
  const mine: { bar: number; dir: string; slPip: number; tpPip: number }[] = []
  for (let i = lo; i < candles.length; i++) {
    if (i < cfg.warm) continue
    const valid = Number.isFinite(z[i]) && Number.isFinite(atr[i]) && atr[i] > 0
    if (!valid) continue
    const up = z[i] >= cfg.zThr
    const dn = z[i] <= -cfg.zThr
    if (!up && !dn) continue
    const isLong = up                       // mode=follow
    // گیتِ روندِ علّی
    if (cfg.driftK != null) {
      const K = cfg.driftK
      if (i - 1 - K < 0) continue
      const d = candles[i - 1].close - candles[i - 1 - K].close
      if (!(isLong ? d > 0 : d < 0)) continue
    }
    // گیتِ رژیمِ σ
    if (cfg.sigmaW != null) {
      const rv = reg![i]
      if (!Number.isFinite(rv) || !(rv <= 1.0)) continue
    }
    const slPrice = cfg.slK * atr[i]
    const tpPrice = Math.max(cfg.rr * slPrice, slPrice)
    mine.push({
      bar: i, dir: isLong ? 'long' : 'short',
      slPip: slPrice / GOLD_PIP, tpPip: tpPrice / GOLD_PIP,
    })
  }

  check(mine.length === ref.signals.length,
    `تعدادِ سیگنالِ dual در دنباله: TS=${mine.length} py=${ref.signals.length}`)
  const m = Math.min(mine.length, ref.signals.length)
  let dsl = 0, dtp = 0
  for (let k = 0; k < m; k++) {
    const a = mine[k], b = ref.signals[k]
    check(a.bar === b.bar, `سیگنالِ ${k}: bar TS=${a.bar} py=${b.bar}`)
    check(a.dir === b.dir, `سیگنالِ ${k} (bar ${b.bar}): جهت TS=${a.dir} py=${b.dir}`)
    // مرجع sl_pip را بر حسبِ **قیمت** ذخیره کرده (sl_k×atr)، پس به pip تبدیل می‌کنیم
    dsl = Math.max(dsl, Math.abs(a.slPip - b.sl_pip / GOLD_PIP))
    dtp = Math.max(dtp, Math.abs(a.tpPip - b.tp_pip / GOLD_PIP))
  }
  check(dsl <= TOL_PIP / GOLD_PIP, `max|ΔSL|=${dsl.toExponential(3)} pip`)
  check(dtp <= TOL_PIP / GOLD_PIP, `max|ΔTP|=${dtp.toExponential(3)} pip`)
  const dirs = mine.map((x) => x.dir)
  console.log(`   سیگنال‌های dual: ${mine.length} (long=${dirs.filter((d) => d === 'long').length} ` +
    `short=${dirs.filter((d) => d === 'short').length}) · max|ΔSL|=${dsl.toExponential(2)} pip · ` +
    `max|ΔTP|=${dtp.toExponential(2)} pip`)
  if (ref.member_stats) {
    console.log(`   سهمِ رسمیِ این کارت در استخر: n=${ref.member_stats.n} · ` +
      `WR=${ref.member_stats.wr}٪ · lift=+${ref.member_stats.lift.toFixed(2)}pp`)
  }
}

const only = process.argv[2]
const cards = only ? [only] : ['D1', 'H8', 'H6', 'H12']
console.log('══ آزمونِ برابریِ S607 — TS در برابرِ مرجعِ پایتون ══')
for (const tf of cards) runCard(tf)

console.log('\n' + '═'.repeat(60))
if (failures === 0) {
  console.log('✅ PARITY GREEN — صفر اختلاف روی همهٔ کارت‌ها ' +
    '(سری‌ها، سیگنال‌ها، هندسه، و شاهدِ منفیِ H12).')
} else {
  console.log(`❌ PARITY RED — ${failures} اختلاف. اتصال به سایت مجاز نیست.`)
  process.exit(1)
}
